"""
LangGraph 状态图执行节点与路由定义 (Workflow Nodes - 轻量化编排适配层)
具体业务规则与决策收口至 services/ 目录，节点仅负责状态流转、interrupt 断点控制与 trace 记账。
"""

from typing import Dict, Any, List, Optional, Tuple
import time
from langgraph.types import interrupt

from .state import AgentState, Hit, RefundDraft
from core.qdrant_store import qdrant_store
from core.llm import deepseek_client
from services.intent_service import intent_service
from services.order_service import order_service
from services.storage_service import storage_service
from config import settings
from core.logger import cprint, trace_node


def _resolve_refund_request_id(state: AgentState, oid: str) -> str:
    """提取断点中已保存的流水号，若为全新申请则生成新流水号"""
    state_refund = state.get("refund") or {}
    if state_refund.get("request_id") and state.get("order_id") == oid:
        return state_refund["request_id"]
    return f"ref_{oid}_{int(time.time() * 1000)}"


def _parse_resume_payload(resume_data: Any, fallback_request_id: str) -> Tuple[Optional[str], str]:
    """从 Command(resume=...) 载荷中提取确认动作与幂等流水号"""
    if isinstance(resume_data, dict):
        action = resume_data.get("action") or resume_data.get("confirm_action")
        request_id = resume_data.get("request_id") or fallback_request_id
        return action, request_id
    if isinstance(resume_data, str) and resume_data in ("confirm", "cancel"):
        return resume_data, fallback_request_id
    return None, fallback_request_id


@trace_node("analyze_query", "意图分类、情绪识别与瞬态字段复位")
def analyze_query_node(state: AgentState) -> Dict[str, Any]:
    """1. 意图分类、情绪识别与单轮瞬态字段复位"""
    t0 = time.time()
    intent, sentiment = intent_service.classify_query(state.get("user_message", ""))
    duration = int((time.time() - t0) * 1000)

    # PostgreSQL Checkpointer 会持久化同 thread_id 的历史状态，每轮入口复位瞬态输出字段以防跨轮污染
    return {
        "intent": intent,
        "sentiment": sentiment,
        "order_id": None,
        "refund": None,
        "reply": None,
        "handoff": False,
        "escalation_reason": None,
        "hits": [],
        "trace": ["__RESET__", f"analyze_query: 意图={intent}, 情绪={sentiment} ({duration}ms)"],
    }


@trace_node("order_query", "订单与物流中台检索")
def order_query_node(state: AgentState) -> Dict[str, Any]:
    """2. 订单与物流中台检索"""
    t0 = time.time()
    order = order_service.detect_and_query_order(
        state.get("user_message", ""),
        state.get("user_profile", {}),
    )
    order_id = order["orderId"] if order else None
    duration = int((time.time() - t0) * 1000)

    return {
        "order_id": order_id,
        "trace": [f"order_query: 命中订单 [{order_id or '无'}] ({duration}ms)"],
    }


@trace_node("order_refund", "订单退款门控与二次确认执行")
def order_refund_node(state: AgentState) -> Dict[str, Any]:
    """3. 订单退款门控 (LangGraph interrupt) 与二次确认执行"""
    t0 = time.time()
    order = order_service.get_owned_order(state.get("order_id"), state.get("user_profile"))
    if not order:
        duration = int((time.time() - t0) * 1000)
        return {
            "order_id": None,
            "refund": None,
            "reply": "未检测到您关联的有效订单信息，请提供正确的订单编号，我来为您核验办理。",
            "trace": [f"order_refund: 未命中有效归属订单，流程终止 ({duration}ms)"],
        }

    oid = order["orderId"]
    action = state.get("confirm_action")
    request_id = _resolve_refund_request_id(state, oid)

    # 首次发起退款申请：触发 LangGraph interrupt 挂起，等待 Command(resume=...) 唤醒
    if not action and state.get("intent") == "退款申请与审批":
        gate_reply = order_service.build_refund_gate_reply(order)
        resume_data = interrupt({
            "order_id": oid,
            "request_id": request_id,
            "reply": gate_reply,
        })
        action, request_id = _parse_resume_payload(resume_data, request_id)

    if action not in ("confirm", "cancel"):
        duration = int((time.time() - t0) * 1000)
        return {
            "order_id": oid,
            "refund": None,
            "reply": "未收到有效的确认操作，请在退款确认卡片中点击【确认提交退款】或【取消 / 我再想想】。",
            "trace": [f"order_refund: 无效确认动作 action={action} ({duration}ms)"],
        }

    try:
        outcome = order_service.execute_refund_decision(order, action, request_id)
        duration = int((time.time() - t0) * 1000)
        draft: RefundDraft = {"request_id": outcome["request_id"], "status": outcome["status"]}
        res: Dict[str, Any] = {
            "order_id": outcome["order_id"],
            "refund": draft,
            "reply": outcome["reply"],
            "trace": [f"order_refund: action={action}, status={outcome['status']} ({duration}ms)"],
        }
        if outcome.get("handoff"):
            res["handoff"] = True
            res["escalation_reason"] = outcome.get("escalation_reason")
        return res
    except Exception as e:
        duration = int((time.time() - t0) * 1000)
        cprint.error(f"[order_refund_node 异常兜底]: {e}")
        return {
            "order_id": oid,
            "refund": None,
            "reply": "系统在处理您的退款申请时遇到临时校验异常，已为您转接人工客服专员为您紧急处理，请稍候...",
            "handoff": True,
            "escalation_reason": f"退款处理节点异常兜底: {e}",
            "trace": [f"order_refund: action={action}, status=error ({duration}ms)"],
        }


@trace_node("qdrant_retrieve", "BGE-M3 向量编码与 Qdrant FAQ 检索")
def qdrant_retrieve_node(state: AgentState) -> Dict[str, Any]:
    """4. 基于 BGE-M3 向量嵌入检索 FAQ 条款（保留完整切片）"""
    t0 = time.time()
    query = state.get("user_message", "")
    hits = qdrant_store.similarity_search(query, k=settings.TOP_K_RETRIEVAL)
    top_score = hits[0]["score"] if hits else 0.0
    top_title = hits[0]["doc"].get("title", "无直接匹配") if hits else "无"

    formatted_hits: List[Hit] = [
        {
            "id": str(h.get("id") or h["doc"].get("id", f"hit_{i}")),
            "title": h["doc"].get("title", ""),
            "score": round(float(h.get("score", 0.0)), 4),
            "snippet": h["doc"].get("content", ""),
        }
        for i, h in enumerate(hits)
        if h.get("score", 0.0) >= settings.SIMILARITY_THRESHOLD
    ]

    duration = int((time.time() - t0) * 1000)
    return {
        "hits": formatted_hits,
        "trace": [
            f"qdrant_retrieve: hits={len(formatted_hits)}, top_score={top_score:.2f}, 最佳=《{top_title}》 ({duration}ms)"
        ],
    }


@trace_node("deepseek_generate", "组装上下文并调用 DeepSeek 生成答复")
async def deepseek_generate_node(state: AgentState) -> Dict[str, Any]:
    """5. 调用 DeepSeek 大模型生成严谨回答（按需加载会话记忆摘要与订单事实）"""
    t0 = time.time()
    session_id = state.get("session_id")
    session_data = storage_service.get_session(session_id) if session_id else None
    memory_summary = (session_data or {}).get("summaryMemory", "")

    order_id = state.get("order_id")
    business_facts = ""
    if order_id:
        target_order = order_service.get_owned_order(order_id, state.get("user_profile"))
        if target_order:
            business_facts = order_service.format_order_summary_text(target_order)

    reply = await deepseek_client.generate_response(
        user_message=state.get("user_message", ""),
        hits=state.get("hits", []),
        memory_summary=memory_summary,
        user_profile=state.get("user_profile", {}),
        business_facts=business_facts,
        order_id=order_id,
    )
    duration = int((time.time() - t0) * 1000)
    return {
        "reply": reply,
        "handoff": False,
        "trace": [f"deepseek_generate: 生成答复 ({len(reply)} 字) ({duration}ms)"],
    }


@trace_node("human_escalation", "触发人工客服接入与转接升级")
def human_escalation_node(state: AgentState) -> Dict[str, Any]:
    """6. 人工接入触发节点"""
    t0 = time.time()
    reason, reply = intent_service.build_escalation_info(
        intent=state.get("intent", ""),
        sentiment=state.get("sentiment", "neutral"),
        hits=state.get("hits", []),
        similarity_threshold=settings.SIMILARITY_THRESHOLD,
    )
    duration = int((time.time() - t0) * 1000)
    return {
        "reply": reply,
        "handoff": True,
        "escalation_reason": reason,
        "trace": [f"human_escalation: 触发转人工 (原因: {reason}) ({duration}ms)"],
    }


# ================= 智能条件路由 =================


def router_after_analysis(state: AgentState) -> str:
    """意图分析后的路由：二次确认动作或涉订单意图先查订单，纯转人工直接升级，其余直接走向量检索"""
    confirm_action = state.get("confirm_action")
    intent = state.get("intent", "")
    if confirm_action in ("confirm", "cancel"):
        return "order_query"
    if intent == "handoff":
        return "human_escalation"
    if intent_service.requires_order_query(intent):
        return "order_query"
    return "qdrant_retrieve"


def router_after_order_query(state: AgentState) -> str:
    """订单查询后的路由：退款申请或确认回调进 order_refund，纯查物流/查政策进知识检索"""
    confirm_action = state.get("confirm_action")
    intent = state.get("intent", "")
    if confirm_action in ("confirm", "cancel") or intent == "退款申请与审批":
        return "order_refund"
    return "qdrant_retrieve"


def router_after_retrieval(state: AgentState) -> str:
    """向量检索后的路由：低分情绪预警转人工；常规未知咨询且无任何知识/订单依据时也转人工防大模型幻觉"""
    hits = state.get("hits", [])
    top_score = hits[0]["score"] if hits else 0.0
    sentiment = state.get("sentiment", "neutral")
    if top_score < settings.SIMILARITY_THRESHOLD and sentiment in ("frustrated", "angry"):
        return "human_escalation"
    if (
        state.get("intent") == "常规售后咨询"
        and not hits
        and not state.get("order_id")
        and not intent_service.is_chitchat(state.get("user_message", ""))
    ):
        return "human_escalation"
    return "deepseek_generate"
