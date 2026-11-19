"""
LangGraph 状态图执行器 (Workflow Runner)
封装 InputState 组装、按会话串行锁、interrupt 挂起提取与 Command(resume) 恢复。
"""

import asyncio
from contextlib import nullcontext
from typing import Dict, Any, Optional
from langgraph.types import Command
from core.logger import cprint
from workflow.state import InputState
from workflow.graph import get_customer_service_graph

# 按 session_id 维护的异步互斥锁，确保同一会话的 Checkpointer 读写串行化，防止并发消息产生状态竞争
_session_locks: Dict[str, asyncio.Lock] = {}


def get_session_lock(session_id: str) -> asyncio.Lock:
    """获取按 session_id 隔离的异步互斥锁"""
    return _session_locks.setdefault(session_id, asyncio.Lock())


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


def _has_pending_interrupt(snapshot: Any, expected_order_id: Optional[str] = None) -> bool:
    """仅当 checkpoint 中存在与目标订单匹配的挂起 interrupt 时返回 True"""
    return _extract_pending_interrupt(snapshot, expected_order_id=expected_order_id) is not None


def _apply_interrupt_payload(final_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    当图因 interrupt() 挂起返回时，从 __interrupt__ 提取退款确认卡片、提示文案与 request_id 写入本次输出状态。
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
    intr_request_id = intr_val.get("request_id", "")
    refund_draft = {
        "request_id": intr_request_id,
        "status": "PENDING_CONFIRM",
    }

    final_state["reply"] = intr_val.get("reply") or final_state.get("reply")
    final_state["order_id"] = intr_order_id or final_state.get("order_id")
    final_state["intent"] = "退款申请与审批"
    final_state["refund"] = refund_draft
    final_state["trace"] = list(final_state.get("trace") or []) + [
        f"order_refund: [LangGraph interrupt 挂起] 订单 {intr_order_id} (req={intr_request_id}) 等待客户交互确认"
    ]
    return final_state


async def _execute_graph(
    session_id: str,
    input_state: InputState,
    refund_order_id: Optional[str] = None,
    refund_request_id: Optional[str] = None,
) -> Dict[str, Any]:
    graph_config = {"configurable": {"thread_id": session_id}}
    try:
        graph = await get_customer_service_graph()
        invoke_payload: Any = input_state

        # 仅当存在真实挂起 interrupt（且与回调目标订单匹配）时，才通过 Command(resume=...) 从断点恢复
        if input_state.get("confirm_action") in ("confirm", "cancel"):
            snapshot = await graph.aget_state(graph_config)
            pending_intr = _extract_pending_interrupt(snapshot, expected_order_id=refund_order_id)
            if pending_intr is not None:
                resolved_request_id = refund_request_id or pending_intr.get("request_id")
                invoke_payload = Command(resume={
                    "action": input_state["confirm_action"],
                    "request_id": resolved_request_id,
                })

        final_state = dict(await graph.ainvoke(invoke_payload, config=graph_config))
        return _apply_interrupt_payload(final_state)
    except Exception as e:
        cprint.error(f"[Graph 执行异常兜底]: {e}")
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
    refund_request_id: Optional[str] = None,
    acquire_lock: bool = True,
) -> Dict[str, Any]:
    """执行指定会话的 LangGraph 状态图，统一处理中断挂起与 Command 唤醒"""
    pending = session.get("pendingRefund") or {}
    target_order_id = refund_order_id or pending.get("orderId")
    target_request_id = refund_request_id or pending.get("requestId")
    input_state = build_input_state(session_id, message, confirm_action, session)

    lock_ctx = get_session_lock(session_id) if acquire_lock else nullcontext()
    async with lock_ctx:
        return await _execute_graph(
            session_id,
            input_state,
            refund_order_id=target_order_id,
            refund_request_id=target_request_id,
        )
