"""
LangGraph 状态图执行器与降级调度器 (Workflow Runner)
将图调用、InputState 组装、HITL 中断检测与唤醒、__interrupt__ 解包以及兜底降级从路由层剥离。
"""

import asyncio
from typing import Dict, Any, Optional
from core.logger import cprint
from workflow.state import InputState
from workflow.graph import customer_service_graph
from workflow.nodes import (
    analyze_query_node,
    order_query_node,
    order_refund_node,
    qdrant_retrieve_node,
    deepseek_generate_node,
    human_escalation_node,
    router_after_analysis,
    router_after_order_query,
    router_after_retrieval,
    _INTERRUPT_EXCEPTIONS,
)

try:
    from langgraph.types import Command
except ImportError:
    Command = None

_session_locks: Dict[str, asyncio.Lock] = {}


def _get_session_lock(session_id: str) -> asyncio.Lock:
    lock = _session_locks.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _session_locks[session_id] = lock
    return lock


def build_input_state(
    session_id: str,
    message: str,
    confirm_action: Optional[str],
    session: Dict[str, Any]
) -> InputState:
    """严格基于 InputState 最小契约构建每轮输入，避免覆盖 checkpointer 内的多轮状态"""
    profile = session.get("customerProfile") or {}
    user_id = profile.get("userId") or "user_001"
    return {
        "session_id": session_id,
        "user_id": user_id,
        "user_message": message,
        "confirm_action": confirm_action if confirm_action in ("confirm", "cancel") else None,
        "user_profile": profile,
    }


def _has_pending_interrupt(snapshot: Any) -> bool:
    """精准判断当前线程是否真正挂起在 LangGraph interrupt 上"""
    if not snapshot:
        return False
    tasks = getattr(snapshot, "tasks", None) or ()
    if any(getattr(t, "interrupts", None) for t in tasks):
        return True
    return bool(getattr(snapshot, "next", None))


def _apply_interrupt_payload(final_state: Dict[str, Any]) -> Dict[str, Any]:
    """从 LangGraph __interrupt__ 提取挂起确认文案、订单号与交互卡片状态"""
    interrupts = final_state.get("__interrupt__") or []
    if not interrupts:
        return final_state

    first_intr = interrupts[0]
    intr_val = first_intr.value if hasattr(first_intr, "value") else first_intr
    if not isinstance(intr_val, dict):
        return final_state

    if intr_val.get("reply"):
        final_state["reply"] = intr_val["reply"]

    intr_order_id = intr_val.get("order_id")
    if intr_order_id and not final_state.get("order_id"):
        final_state["order_id"] = intr_order_id

    if not final_state.get("intent") or final_state.get("intent") == "常规售后咨询":
        final_state["intent"] = "退款申请与审批"

    final_state["refund"] = {
        "order_id": intr_order_id or final_state.get("order_id") or "",
        "amount_cents": intr_val.get("amount_cents", 0),
        "request_id": intr_val.get("request_id", ""),
        "status": "PENDING_CONFIRM",
    }

    if intr_val.get("card"):
        existing_cards = [c for c in (final_state.get("cards") or []) if c.get("type") != "refund_gate"]
        existing_cards.append(intr_val["card"])
        final_state["cards"] = existing_cards

    trace_list = list(final_state.get("trace") or [])
    trace_list.append(f"order_refund: [LangGraph interrupt 挂起] 订单 {intr_order_id or ''} 等待客户交互确认")
    final_state["trace"] = trace_list
    return final_state


def _merge_node_update(state: Dict[str, Any], update: Dict[str, Any]) -> None:
    """降级直连执行时模拟 LangGraph 的 trace 追加 Reducer，防止覆盖前序日志"""
    if not update:
        return
    if "trace" in update:
        merged_trace = list(state.get("trace") or []) + list(update["trace"] or [])
        state["trace"] = merged_trace
        rest = {k: v for k, v in update.items() if k != "trace"}
        state.update(rest)
    else:
        state.update(update)


async def _run_fallback_pipeline(input_state: InputState, session: Dict[str, Any]) -> Dict[str, Any]:
    """当图引擎异常时的完整兜底流水线（保留意图分析、退款门控与人工转接链路）"""
    state: Dict[str, Any] = {
        **input_state,
        "memory_summary": session.get("summaryMemory", ""),
        "intent": "常规售后咨询",
        "sentiment": "neutral",
        "order_id": None,
        "hits": [],
        "refund": None,
        "cards": [],
        "trace": [],
    }
    _merge_node_update(state, analyze_query_node(state))

    route1 = router_after_analysis(state)
    if route1 == "human_escalation":
        _merge_node_update(state, human_escalation_node(state))
        return state

    if route1 == "order_query":
        _merge_node_update(state, order_query_node(state))
        if router_after_order_query(state) == "order_refund":
            try:
                _merge_node_update(state, order_refund_node(state))
            except _INTERRUPT_EXCEPTIONS as exc:
                intr_val = getattr(exc, "args", [None])[0]
                if isinstance(intr_val, (list, tuple)) and intr_val:
                    intr_val = intr_val[0]
                state["__interrupt__"] = [intr_val]
                return _apply_interrupt_payload(state)

    _merge_node_update(state, qdrant_retrieve_node(state))
    if not state.get("reply") and router_after_retrieval(state) == "human_escalation":
        _merge_node_update(state, human_escalation_node(state))
    else:
        _merge_node_update(state, await deepseek_generate_node(state))
    return state


async def run_customer_service_graph(
    session_id: str,
    message: str,
    confirm_action: Optional[str],
    session: Dict[str, Any],
) -> Dict[str, Any]:
    """串行化执行指定会话的 LangGraph 状态图，统一处理中断挂起、Command 恢复与异常降级"""
    input_state = build_input_state(session_id, message, confirm_action, session)
    graph_config = {"configurable": {"thread_id": session_id}}

    async with _get_session_lock(session_id):
        try:
            invoke_payload: Any = input_state
            if input_state.get("confirm_action") in ("confirm", "cancel") and Command is not None:
                try:
                    snapshot = await customer_service_graph.aget_state(graph_config)
                    if _has_pending_interrupt(snapshot):
                        invoke_payload = Command(resume={"action": input_state["confirm_action"]})
                except Exception:
                    pass

            raw_state = await customer_service_graph.ainvoke(invoke_payload, config=graph_config)
            final_state = dict(raw_state)
            return _apply_interrupt_payload(final_state)
        except Exception as e:
            cprint.error(f"[Graph Fallback 降级]: {e}")
            return await _run_fallback_pipeline(input_state, session)
