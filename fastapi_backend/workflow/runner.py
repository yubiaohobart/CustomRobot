"""
LangGraph 状态图执行器 (Workflow Runner)
封装 InputState 组装、按会话串行锁、interrupt 挂起提取与 Command(resume) 恢复。
"""

import asyncio
import time
from contextlib import nullcontext
from typing import Dict, Any, Optional
from langgraph.types import Command
from core.logger import cprint
from core.session_lock import acquire_session_lock
from workflow.state import InputState
from workflow.graph import get_customer_service_graph


def build_input_state(
    session_id: str,
    message: str,
    confirm_action: Optional[str],
    session: Dict[str, Any],
) -> InputState:
    """将 API 请求与持久化会话上下文组装为状态图 InputState（裁剪冗余字段以减小 Checkpoint 体积）"""
    profile = session.get("customerProfile") or {}
    compact_profile = {
        k: profile[k]
        for k in ("name", "userName", "vipLevel", "tier", "orderId")
        if profile.get(k) not in (None, "")
    }
    return {
        "session_id": session_id,
        "user_message": message,
        "confirm_action": confirm_action if confirm_action in ("confirm", "cancel") else None,
        "user_profile": compact_profile,
    }


def _extract_pending_interrupt(
    snapshot: Any,
    expected_order_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    从 checkpoint StateSnapshot 中提取与目标订单匹配的挂起 interrupt 载荷。
    同时检查 snapshot.tasks[].interrupts 与 snapshot.interrupts，兼容不同版本 LangGraph。
    """
    if not snapshot:
        return None

    candidates = []
    for task in getattr(snapshot, "tasks", None) or ():
        for intr in getattr(task, "interrupts", None) or ():
            candidates.append(intr)
    for intr in getattr(snapshot, "interrupts", None) or ():
        candidates.append(intr)

    for intr in candidates:
        val = getattr(intr, "value", intr)
        if isinstance(val, dict):
            intr_oid = val.get("order_id")
            if expected_order_id and intr_oid and intr_oid != expected_order_id:
                continue
            return val
        if not expected_order_id:
            return {"raw": val}
    return None


def _apply_interrupt_payload(final_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    当图因 interrupt() 挂起返回时，从 __interrupt__ 提取退款确认卡片、提示文案与 out_refund_no 写入本次输出状态。
    注：不再在外部调用 graph.aupdate_state()，避免生成 source='update' 新 checkpoint 覆盖原挂起任务的 interrupts。
    """
    interrupts = final_state.get("__interrupt__") or []
    if not interrupts:
        return final_state

    first = interrupts[0]
    intr_val = first.value if hasattr(first, "value") else first
    if not isinstance(intr_val, dict):
        return final_state

    intr_order_id = intr_val.get("order_id") or final_state.get("order_id") or ""
    intr_out_refund_no = intr_val.get("out_refund_no", "")
    refund_draft = {
        "out_refund_no": intr_out_refund_no,
        "status": "PENDING_CONFIRM",
    }

    final_state["reply"] = intr_val.get("reply") or final_state.get("reply")
    final_state["order_id"] = intr_order_id or final_state.get("order_id")
    final_state["intent"] = "退款申请与审批"
    final_state["refund"] = refund_draft
    final_state["trace"] = list(final_state.get("trace") or []) + [
        f"order_refund: [LangGraph interrupt 挂起] 订单 {intr_order_id} (outRefundNo={intr_out_refund_no}) 等待客户交互确认"
    ]
    return final_state


async def _execute_graph(
    session_id: str,
    input_state: InputState,
    refund_order_id: Optional[str] = None,
    out_refund_no: Optional[str] = None,
) -> Dict[str, Any]:
    graph_config = {"configurable": {"thread_id": session_id}}
    t_graph = time.time()
    try:
        graph = await get_customer_service_graph()
        invoke_payload: Any = input_state
        is_resumed = False
        mode_label = "标准执行"

        # 仅当存在真实挂起 interrupt（且与回调目标订单匹配）时，才通过 Command(resume=...) 从断点恢复
        if input_state.get("confirm_action") in ("confirm", "cancel"):
            snapshot = await graph.aget_state(graph_config)
            pending_intr = _extract_pending_interrupt(snapshot, expected_order_id=refund_order_id)
            if pending_intr is not None:
                resolved_out_refund_no = out_refund_no or pending_intr.get("out_refund_no")
                invoke_payload = Command(resume={
                    "action": input_state["confirm_action"],
                    "out_refund_no": resolved_out_refund_no,
                })
                is_resumed = True
                mode_label = f"断点恢复({input_state['confirm_action']})"

        profile = input_state.get("user_profile") or {}
        user_name = profile.get("name") or profile.get("userName") or "访客"
        tier = profile.get("vipLevel") or profile.get("tier") or "NORMAL"
        cprint.flow_start(
            session_id=session_id,
            mode=mode_label,
            user_message=input_state.get("user_message", ""),
            confirm_action=None if is_resumed else input_state.get("confirm_action"),
            customer_label=f"{user_name}({tier})",
        )

        raw_state = dict(await graph.ainvoke(invoke_payload, config=graph_config))
        final_state = _apply_interrupt_payload(raw_state)
        duration_ms = int((time.time() - t_graph) * 1000)

        cprint.flow_summary(
            session_id=session_id,
            final_state=final_state,
            duration_ms=duration_ms,
            is_resumed=is_resumed,
        )
        return final_state
    except Exception as e:
        duration_ms = int((time.time() - t_graph) * 1000)
        cprint.error(f"[Graph 执行异常兜底]: {e}")
        cprint.flow_end(
            session_id=session_id,
            node_path=["START", "ERROR -> 兜底转人工"],
            status="ERROR",
            duration_ms=duration_ms,
        )
        return {
            "reply": "系统处理请求时遇到临时异常，已为您转接人工客服专员跟进处理，请稍候片刻...",
            "handoff": True,
            "intent": "handoff",
            "sentiment": "neutral",
            "order_id": None,
            "refund": None,
            "hits": [],
            "escalation_reason": f"状态图执行异常兜底: {e}",
            "trace": [f"graph_runner: 执行异常兜底转人工 ({e})"],
        }


async def run_customer_service_graph(
    session_id: str,
    message: str,
    confirm_action: Optional[str],
    session: Dict[str, Any],
    refund_order_id: Optional[str] = None,
    out_refund_no: Optional[str] = None,
    acquire_lock: bool = True,
) -> Dict[str, Any]:
    """执行指定会话的 LangGraph 状态图，统一处理中断挂起与 Command 唤醒"""
    input_state = build_input_state(session_id, message, confirm_action, session)

    lock_ctx = acquire_session_lock(session_id) if acquire_lock else nullcontext()
    async with lock_ctx:
        return await _execute_graph(
            session_id,
            input_state,
            refund_order_id=refund_order_id,
            out_refund_no=out_refund_no,
        )
