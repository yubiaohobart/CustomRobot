"""
LangGraph 状态图执行器 (Workflow Runner)
封装 InputState 组装、按会话串行锁、interrupt 挂起提取与 Command(resume) 恢复。
"""

import asyncio
from typing import Dict, Any, Optional
from langgraph.types import Command
from core.logger import cprint
from workflow.state import InputState
from workflow.graph import customer_service_graph
from workflow.nodes import qdrant_retrieve_node, deepseek_generate_node

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
    """将 API 请求与持久化会话上下文组装为状态图 InputState"""
    profile = session.get("customerProfile") or {}
    return {
        "session_id": session_id,
        "user_id": profile.get("userId") or "user_001",
        "user_message": message,
        "confirm_action": confirm_action if confirm_action in ("confirm", "cancel") else None,
        "user_profile": profile,
        "memory_summary": session.get("summaryMemory", ""),
    }


def _has_pending_interrupt(snapshot: Any) -> bool:
    """检测当前 thread_id 是否正处于 LangGraph interrupt 挂起态，以便决定是否用 Command(resume=...) 唤醒"""
    if not snapshot:
        return False
    tasks = getattr(snapshot, "tasks", None) or ()
    return any(getattr(t, "interrupts", None) for t in tasks) or bool(getattr(snapshot, "next", None))


def _apply_interrupt_payload(final_state: Dict[str, Any]) -> Dict[str, Any]:
    """当图因 interrupt() 挂起返回时，从 __interrupt__ 提取退款确认卡片、提示文案与 PENDING_CONFIRM 状态"""
    interrupts = final_state.get("__interrupt__") or []
    if not interrupts:
        return final_state

    first = interrupts[0]
    intr_val = first.value if hasattr(first, "value") else first
    if not isinstance(intr_val, dict):
        return final_state

    intr_order_id = intr_val.get("order_id") or final_state.get("order_id") or ""
    final_state["reply"] = intr_val.get("reply") or final_state.get("reply")
    final_state["order_id"] = intr_order_id or final_state.get("order_id")
    final_state["intent"] = "退款申请与审批"
    final_state["refund"] = {
        "order_id": intr_order_id,
        "amount_cents": intr_val.get("amount_cents", 0),
        "request_id": intr_val.get("request_id", ""),
        "status": "PENDING_CONFIRM",
    }
    if intr_val.get("card"):
        cards = [c for c in (final_state.get("cards") or []) if c.get("type") != "refund_gate"]
        cards.append(intr_val["card"])
        final_state["cards"] = cards

    final_state["trace"] = list(final_state.get("trace") or []) + [
        f"order_refund: [LangGraph interrupt 挂起] 订单 {intr_order_id} 等待客户交互确认"
    ]
    return final_state


async def _execute_graph(
    session_id: str,
    input_state: InputState,
) -> Dict[str, Any]:
    graph_config = {"configurable": {"thread_id": session_id}}
    try:
        invoke_payload: Any = input_state
        # 若携带确认/取消回调且图当前处于挂起态，使用 Command(resume=...) 从中断点继续执行
        if input_state.get("confirm_action") in ("confirm", "cancel"):
            snapshot = await customer_service_graph.aget_state(graph_config)
            if _has_pending_interrupt(snapshot):
                invoke_payload = Command(resume={"action": input_state["confirm_action"]})

        final_state = dict(await customer_service_graph.ainvoke(invoke_payload, config=graph_config))
        return _apply_interrupt_payload(final_state)
    except Exception as e:
        # 图编排执行异常时的兜底降级：直接串行调用向量检索与大模型生成，保证问答可用性
        cprint.error(f"[Graph Fallback 降级]: {e}")
        fallback_state: Dict[str, Any] = {**input_state, "intent": "常规售后咨询", "sentiment": "neutral"}
        fallback_state.update(qdrant_retrieve_node(fallback_state))
        gen = await deepseek_generate_node(fallback_state)
        gen["trace"] = list(fallback_state.get("trace") or []) + list(gen.get("trace") or [])
        fallback_state.update(gen)
        return fallback_state


async def run_customer_service_graph(
    session_id: str,
    message: str,
    confirm_action: Optional[str],
    session: Dict[str, Any],
    acquire_lock: bool = True,
) -> Dict[str, Any]:
    """执行指定会话的 LangGraph 状态图，统一处理中断挂起与 Command 唤醒"""
    input_state = build_input_state(session_id, message, confirm_action, session)
    if acquire_lock:
        async with get_session_lock(session_id):
            return await _execute_graph(session_id, input_state)
    return await _execute_graph(session_id, input_state)
