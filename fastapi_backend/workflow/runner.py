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
from workflow.nodes import (
    _ORDER_QUERY_INTENTS,
    analyze_query_node,
    order_query_node,
    qdrant_retrieve_node,
    deepseek_generate_node,
    human_escalation_node,
    router_after_retrieval,
)

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
    refund_order_id: Optional[str] = None,
    refund_request_id: Optional[str] = None,
) -> InputState:
    """将 API 请求与持久化会话上下文组装为状态图 InputState"""
    profile = session.get("customerProfile") or {}
    pending = session.get("pendingRefund") or {}
    return {
        "session_id": session_id,
        "user_id": profile.get("userId") or "user_001",
        "user_message": message,
        "confirm_action": confirm_action if confirm_action in ("confirm", "cancel") else None,
        "refund_order_id": refund_order_id or pending.get("orderId"),
        "refund_request_id": refund_request_id or pending.get("requestId"),
        "user_profile": profile,
        "memory_summary": session.get("summaryMemory", ""),
    }


def _has_pending_interrupt(snapshot: Any) -> bool:
    """仅当 checkpoint tasks 中确实存在挂起的 interrupts 时才返回 True，避免因 snapshot.next 非空误触发 Command(resume)"""
    if not snapshot:
        return False
    tasks = getattr(snapshot, "tasks", None) or ()
    return any(getattr(t, "interrupts", None) for t in tasks)


async def _apply_interrupt_payload(final_state: Dict[str, Any], graph_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    当图因 interrupt() 挂起返回时：
    1. 从 __interrupt__ 提取退款确认卡片、提示文案与 request_id；
    2. 通过 aupdate_state 将 refund 草稿与 order_id 写入挂起的 checkpoint，确保 resume 幂等闭环。
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
        "order_id": intr_order_id,
        "amount_cents": intr_val.get("amount_cents", 0),
        "request_id": intr_request_id,
        "status": "PENDING_CONFIRM",
    }

    final_state["reply"] = intr_val.get("reply") or final_state.get("reply")
    final_state["order_id"] = intr_order_id or final_state.get("order_id")
    final_state["intent"] = "退款申请与审批"
    final_state["refund"] = refund_draft
    if intr_val.get("card"):
        cards = [c for c in (final_state.get("cards") or []) if c.get("type") != "refund_gate"]
        cards.append(intr_val["card"])
        final_state["cards"] = cards

    # 将挂起阶段的 order_id / refund(含 request_id) 回写至 checkpoint，供 Command(resume) 恢复使用
    await customer_service_graph.aupdate_state(
        graph_config,
        {"order_id": final_state["order_id"], "refund": refund_draft},
    )

    final_state["trace"] = list(final_state.get("trace") or []) + [
        f"order_refund: [LangGraph interrupt 挂起] 订单 {intr_order_id} (req={intr_request_id}) 等待客户交互确认"
    ]
    return final_state


def _merge_fallback_step(state: Dict[str, Any], update: Dict[str, Any]) -> None:
    """降级路径辅助：合并节点输出并累加 trace"""
    existing_trace = list(state.get("trace") or [])
    new_trace = list(update.get("trace") or [])
    state.update(update)
    state["trace"] = existing_trace + new_trace


async def _execute_graph(
    session_id: str,
    input_state: InputState,
) -> Dict[str, Any]:
    graph_config = {"configurable": {"thread_id": session_id}}
    try:
        invoke_payload: Any = input_state
        # 仅当存在真实挂起 interrupt 且携带 confirm/cancel 动作时，才通过 Command(resume=...) 从断点恢复
        if input_state.get("confirm_action") in ("confirm", "cancel"):
            snapshot = await customer_service_graph.aget_state(graph_config)
            if _has_pending_interrupt(snapshot):
                invoke_payload = Command(resume={
                    "action": input_state["confirm_action"],
                    "order_id": input_state.get("refund_order_id"),
                    "request_id": input_state.get("refund_request_id"),
                })

        final_state = dict(await customer_service_graph.ainvoke(invoke_payload, config=graph_config))
        return await _apply_interrupt_payload(final_state, graph_config)
    except Exception as e:
        # 图编排执行异常时的全链路降级：保留意图分析、转人工判定、订单检索、知识检索与低置信度兜底
        cprint.error(f"[Graph Fallback 降级]: {e}")
        fallback_state: Dict[str, Any] = dict(input_state)
        _merge_fallback_step(fallback_state, analyze_query_node(fallback_state))

        if fallback_state.get("intent") == "handoff":
            _merge_fallback_step(fallback_state, human_escalation_node(fallback_state))
            return fallback_state

        if fallback_state.get("intent") in _ORDER_QUERY_INTENTS or fallback_state.get("confirm_action") in ("confirm", "cancel"):
            _merge_fallback_step(fallback_state, order_query_node(fallback_state))

        _merge_fallback_step(fallback_state, qdrant_retrieve_node(fallback_state))
        if router_after_retrieval(fallback_state) == "human_escalation":
            _merge_fallback_step(fallback_state, human_escalation_node(fallback_state))
            return fallback_state

        _merge_fallback_step(fallback_state, await deepseek_generate_node(fallback_state))
        return fallback_state


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
    input_state = build_input_state(
        session_id,
        message,
        confirm_action,
        session,
        refund_order_id=refund_order_id,
        refund_request_id=refund_request_id,
    )
    if acquire_lock:
        async with get_session_lock(session_id):
            return await _execute_graph(session_id, input_state)
    return await _execute_graph(session_id, input_state)
