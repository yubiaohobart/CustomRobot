"""
LangGraph 状态图执行节点与路由定义 (Workflow Nodes)
职责清晰拆分：
1. analyze_query_node: 意图分类、情绪识别、单轮瞬态状态复位
2. order_query_node: 订单与物流中台检索
3. order_refund_node: 退款门控 (LangGraph interrupt) 与二次确认执行
4. qdrant_retrieve_node: 向量知识库检索（保留完整政策切片）
5. deepseek_generate_node: 大模型回复生成（前置确定性答复直接透传）
6. human_escalation_node: 人工接入兜底节点
"""

from typing import Dict, Any, List, Optional, Tuple
import time

try:
    from langgraph.types import interrupt
except ImportError:
    try:
        from langgraph.checkpoint.base import interrupt
    except ImportError:
        def interrupt(value: Any) -> Any:
            return value

try:
    from langgraph.errors import GraphInterrupt, GraphBubbleUp
    _INTERRUPT_EXCEPTIONS = (GraphInterrupt, GraphBubbleUp)
except ImportError:
    try:
        from langgraph.errors import GraphInterrupt
        _INTERRUPT_EXCEPTIONS = (GraphInterrupt,)
    except ImportError:
        class GraphInterrupt(Exception):
            pass
        _INTERRUPT_EXCEPTIONS = (GraphInterrupt,)

from .state import AgentState, Hit, RefundDraft, Intent
from core.qdrant_store import qdrant_store
from core.llm import deepseek_client
from services.order_service import order_service
from config import settings
from core.logger import cprint, LogColor

# ================= 规则配置常量（单一数据源） =================

_POLICY_GUARD_KEYWORDS = (
    "运费", "谁出", "谁付", "包邮", "免运费",
    "到账", "几天能收到", "几天到", "多久到账", "打款时间", "退款多久", "时效", "几天",
    "7天", "七天", "无理由", "政策", "规定", "条件", "流程是什么",
    "可以退吗", "能不能退", "怎么退", "如何退",
    "进度", "状态", "审核到哪", "特殊商品", "不能退", "不给退", "定制", "生鲜", "拆封",
)

_REFUND_APPLY_KEYWORDS = (
    "申请退款", "我要退款", "办理退款", "退钱给我", "我要退货退款",
    "提交退款", "申请退货", "我要退货", "退款", "退货", "退钱", "要退", "退掉",
)

_HANDOFF_PURE_KEYWORDS = (
    "转人工", "找人工", "人工客服", "投诉", "消协", "找领导", "不要机器人", "马上帮我转接人工",
)

_INTENT_RULES: Tuple[Tuple[Intent, Tuple[str, ...]], ...] = (
    ("退款到账时效查询", ("到账", "几天能收到", "几天到", "多久到账", "打款时间", "退款多久", "时效", "几天")),
    ("退换货运费承担与会员权益", ("运费", "谁出", "谁付", "包邮", "免运费")),
    ("特殊不可退换商品范围", ("特殊商品", "不能退", "不给退", "定制", "生鲜", "内裤", "母婴", "拆封")),
    ("7天无理由退货政策", ("7天", "七天", "无理由", "退货", "退换", "规定", "政策", "条件", "怎么退", "如何退")),
    ("订单查询与物流追踪", ("订单", "查订单", "物流", "快递", "运单", "发货", "到哪了", "什么时候到", "送达", "签收", "收件地址", "进度", "状态", "ord-", "88992", "90412", "77310")),
    ("1年联保与硬件保修条款", ("保修", "维修", "坏了", "换新", "质保", "联保", "进水", "摔坏")),
)

_ORDER_QUERY_INTENTS = frozenset({
    "订单查询与物流追踪",
    "退款申请与审批",
    "退款到账时效查询",
    "退换货运费承担与会员权益",
    "7天无理由退货政策",
})


# ================= 内部纯辅助函数 =================

def _detect_sentiment(msg: str, explicit_handoff: bool) -> str:
    if any(k in msg for k in ("骗子", "投诉", "消协", "火大", "气死", "态度差", "打死")):
        return "angry"
    if explicit_handoff or any(k in msg for k in ("差评", "太慢", "生气", "催", "急", "不要机器人")):
        return "frustrated"
    if any(k in msg for k in ("谢谢", "感谢", "好的", "明白了", "点赞", "挺快")):
        return "calm"
    return "neutral"


def _upsert_card(cards: Optional[List[Dict[str, Any]]], card_type: str, new_card: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """按 card['type'] 去重覆盖，避免多轮交互卡片堆叠"""
    filtered = [c for c in (cards or []) if c.get("type") != card_type]
    if new_card is not None:
        filtered.append(new_card)
    return filtered


def _make_refund_draft(order_id: str, amount_cents: int, request_id: str, status: str) -> RefundDraft:
    return {
        "order_id": order_id,
        "amount_cents": amount_cents,
        "request_id": request_id,
        "status": status,  # type: ignore[typeddict-item]
    }


def _resolve_owned_order(state: AgentState) -> Optional[Dict[str, Any]]:
    order_id = state.get("order_id")
    if not order_id:
        return None
    persisted = order_service.get_order_by_id(order_id)
    if not persisted:
        return None
    profile_name = (state.get("user_profile") or {}).get("name", "")
    is_placeholder = not profile_name or "客户" in profile_name or "访客" in profile_name
    if is_placeholder or profile_name in persisted.get("userName", ""):
        return persisted
    return None


def _build_refund_gate_reply(order_id: str, amount: float, rule_text: str, current_status: str) -> str:
    header = f"收到您针对订单【{order_id}】（实付 ¥{amount:.2f} 元）的退款申请。\n"
    if current_status == "REFUND_PENDING_AUDIT":
        return (
            f"{header}该订单当前正处于【退款待人工审核】状态（因金额 >= 3.00 元触发资金安全人工干涉）。\n"
            f"如需确认或变更诉求，请在下方卡片中点击【确认提交退款】或【取消 / 我再想想】："
        )
    if current_status == "REFUNDED":
        return (
            f"{header}系统显示该订单此前已完成退款解冻。\n"
            f"您可在下方卡片中点击【确认提交退款】复核退款状态，或点击【取消 / 我再想想】退出："
        )
    return (
        f"{header}根据商城退款规则（{rule_text}），在正式提交前，请您确认以下权益调整：\n"
        f"• 订单对应的黄金/钻石会员积分及运费补贴将同步收回；\n"
        f"• 退款将通过原支付渠道（支付宝/微信/银行卡）解冻退回。\n\n"
        f"请在下方卡片中点击【确认提交退款】或【取消 / 我再想想】："
    )


def _execute_refund_action(
    order: Dict[str, Any],
    action: str,
    amount: float,
    amount_cents: int,
    request_id: str,
) -> Tuple[Dict[str, Any], str, RefundDraft, bool, str]:
    """执行退款二次确认动作 ('confirm' / 'cancel')"""
    oid = order["orderId"]
    current_status = order.get("status", "")

    if action == "cancel":
        cprint.node("order_refund", "用户点击取消退款申请", "恢复正常状态")
        return (
            order,
            f"已为您取消退款申请，订单【{oid}】将保持正常签收状态。如需其他帮助，随时联系我！",
            _make_refund_draft(oid, amount_cents, request_id, "CANCELED"),
            False,
            "",
        )

    if current_status == "REFUNDED":
        return (
            order,
            f"【温馨提示】订单【{oid}】此前已完成退款，款项已原路退回解冻，请您查收账户通知！",
            _make_refund_draft(oid, amount_cents, request_id, "SUBMITTED"),
            False,
            "",
        )

    if current_status == "REFUND_PENDING_AUDIT":
        return (
            order,
            f"【温馨提示】订单【{oid}】的退款审核工单已在处理中，无需重复提交，专员正在加急核验！",
            _make_refund_draft(oid, amount_cents, request_id, "PENDING_AUDIT"),
            False,
            "",
        )

    if amount_cents < 300:
        updated = order_service.process_refund_request(oid, reason="用户二次确认提交退款(自动秒退)", refund_amount=amount)
        cprint.node("order_refund", f"[幂等秒退成功] 订单 {oid} 金额 {amount_cents}分", "秒退完成")
        return (
            updated,
            f"【智能客服秒退成功】您已二次确认！订单【{oid}】实付金额为 ¥{amount:.2f} 元 (< 3.00 元)，智能客服已为您直接原路退回解冻，请查收！",
            _make_refund_draft(oid, amount_cents, request_id, "SUBMITTED"),
            False,
            "",
        )

    updated = order_service.process_refund_request(oid, reason="用户二次确认提交退款(人工审核)", refund_amount=amount)
    cprint.node("order_refund", f"[转人工干涉队列] 订单 {oid} 金额 {amount_cents}分", "转人工核验")
    reason = f"订单 {oid} 申请退款金额 ¥{amount:.2f} 元 (>= 3.00 元)，涉及资金安全，已通过二次确认提交至人工干涉与审核队列"
    reply = f"【退款审核工单已提交】您已二次确认！订单【{oid}】实付金额为 ¥{amount:.2f} 元 (>= 3.00 元)，涉及商城资金安全，已自动为您无缝对接人工客服加急干涉与核验！"
    return (
        updated,
        reply,
        _make_refund_draft(oid, amount_cents, request_id, "PENDING_AUDIT"),
        True,
        reason,
    )


# ================= LangGraph 核心节点 =================

def analyze_query_node(state: AgentState) -> Dict[str, Any]:
    """1. 意图分类、情绪识别与单轮瞬态状态复位节点"""
    t0 = time.time()
    msg = state.get("user_message", "").lower()

    is_policy_q = any(k in msg for k in _POLICY_GUARD_KEYWORDS)
    is_refund_apply = (not is_policy_q) and any(k in msg for k in _REFUND_APPLY_KEYWORDS)
    explicit_handoff = any(k in msg for k in _HANDOFF_PURE_KEYWORDS) or (
        ("人工" in msg or "主管" in msg) and not is_refund_apply
    )
    sentiment = _detect_sentiment(msg, explicit_handoff)

    intent: Intent = "常规售后咨询"
    if explicit_handoff:
        intent = "handoff"
    elif is_refund_apply:
        intent = "退款申请与审批"
    else:
        for candidate_intent, keywords in _INTENT_RULES:
            if any(k in msg for k in keywords):
                intent = candidate_intent
                break

    duration = int((time.time() - t0) * 1000)
    cprint.node(
        "analyze_query",
        f"意图: {LogColor.BRIGHT_WHITE}{intent}{LogColor.RESET} | 情绪: {sentiment}",
        f"耗时 {duration}ms",
    )

    # 显式复位单轮瞬态字段，防止 MemorySaver 跨轮残留上一轮的 reply / handoff / refund / order_id / cards
    clean_cards = [c for c in (state.get("cards") or []) if c.get("type") not in ("refund_gate", "order_card")]
    return {
        "intent": intent,
        "sentiment": sentiment,
        "order_id": None,
        "refund": None,
        "reply": None,
        "handoff": False,
        "escalation_reason": None,
        "hits": [],
        "cards": clean_cards,
        "trace": [f"analyze_query: 意图={intent}, 情绪={sentiment} ({duration}ms)"],
    }


def order_query_node(state: AgentState) -> Dict[str, Any]:
    """2. 订单与物流中台实时检索节点"""
    t0 = time.time()
    order = order_service.detect_and_query_order(
        state.get("user_message", ""),
        state.get("user_profile", {}),
    )
    order_id = order["orderId"] if order else None
    new_card = {"type": "order_card", "order_id": order_id, "order": order} if order else None
    cards = _upsert_card(state.get("cards"), "order_card", new_card)

    duration = int((time.time() - t0) * 1000)
    return {
        "order_id": order_id,
        "cards": cards,
        "trace": [f"order_query: 命中订单 [{order_id or '无'}] ({duration}ms)"],
    }


def order_refund_node(state: AgentState) -> Dict[str, Any]:
    """3. 订单退款与人工干涉控制节点 (LangGraph interrupt + resume)"""
    t0 = time.time()
    action = state.get("confirm_action")
    cards = _upsert_card(state.get("cards"), "refund_gate")
    order = None
    refund_draft: Optional[RefundDraft] = None
    override_response: Optional[str] = None
    escalate_human = False
    escalation_reason = ""

    try:
        order = _resolve_owned_order(state)
        if not order:
            return {
                "order_id": None,
                "refund": None,
                "reply": "未检测到您关联的有效订单信息，请提供正确的订单编号，我来为您核验办理。",
                "cards": cards,
                "trace": ["order_refund: 未命中有效归属订单，流程终止 (1ms)"],
            }

        oid = order["orderId"]
        amount = round(float(order.get("paidAmount", 0.0)), 2)
        amount_cents = int(round(amount * 100))
        prev_refund = state.get("refund") or {}
        request_id = prev_refund.get("request_id") or f"ref_{oid}_{int(time.time() * 1000)}"
        is_refund_intent = state.get("intent") == "退款申请与审批"

        if not action and is_refund_intent:
            rule_text = "金额 < 3.00 元，确认后将由智能客服直接秒退" if amount_cents < 300 else "金额 >= 3.00 元，确认后将提交人工干涉与资金安全审核"
            override_response = _build_refund_gate_reply(oid, amount, rule_text, order.get("status", ""))
            gate_card = {
                "type": "refund_gate",
                "order_id": oid,
                "amount_cents": amount_cents,
                "amount": amount,
                "rule_text": rule_text,
                "status": "PENDING_CONFIRM",
            }
            cards.append(gate_card)

            cprint.node("order_refund", f"[触发 LangGraph interrupt 挂起] 订单 {oid}", "等待用户确认")
            resume_data = interrupt({
                "type": "refund_confirmation_gate",
                "order_id": oid,
                "amount_cents": amount_cents,
                "amount": amount,
                "rule_text": rule_text,
                "request_id": request_id,
                "reply": override_response,
                "card": gate_card,
                "prompt": "退款前风险与权益确认挂起",
            })

            if isinstance(resume_data, dict):
                action = resume_data.get("action") or resume_data.get("confirm_action") or action
            elif isinstance(resume_data, str) and resume_data in ("confirm", "cancel"):
                action = resume_data

            if not action:
                refund_draft = _make_refund_draft(oid, amount_cents, request_id, "PENDING_CONFIRM")

        if action in ("confirm", "cancel"):
            order, override_response, refund_draft, escalate_human, escalation_reason = _execute_refund_action(
                order, action, amount, amount_cents, request_id
            )

    except _INTERRUPT_EXCEPTIONS:
        raise
    except Exception as e:
        cprint.error(f"[order_refund_node 异常兜底]: {e}")
        override_response = "系统在处理您的退款申请时遇到临时校验异常，已为您转接人工客服专员为您紧急处理，请稍候..."
        escalate_human = True
        escalation_reason = f"退款处理节点异常兜底: {e}"

    duration = int((time.time() - t0) * 1000)
    status_str = refund_draft["status"] if refund_draft else "none"
    res: Dict[str, Any] = {
        "order_id": order.get("orderId") if order else None,
        "refund": refund_draft,
        "cards": cards,
        "trace": [f"order_refund: action={action}, status={status_str} ({duration}ms)"],
    }
    if override_response:
        res["reply"] = override_response
    if escalate_human:
        res["handoff"] = True
        res["escalation_reason"] = escalation_reason
    return res


def qdrant_retrieve_node(state: AgentState) -> Dict[str, Any]:
    """4. 基于 BGE-M3 向量嵌入检索 FAQ 条款（已有确定性答复时跳过检索）"""
    if state.get("reply"):
        return {
            "hits": [],
            "trace": ["qdrant_retrieve: 前置节点已产出确定性回复，跳过检索 (0ms)"],
        }

    t0 = time.time()
    query = state.get("user_message", "")
    hits = qdrant_store.similarity_search(query, k=settings.TOP_K_RETRIEVAL)
    top_score = hits[0]["score"] if hits else 0.0
    top_title = hits[0]["doc"].get("title", "无直接匹配") if hits else "无"

    valid_hits = [h for h in hits if h.get("score", 0.0) >= settings.SIMILARITY_THRESHOLD]
    formatted_hits: List[Hit] = [
        {
            "id": str(h.get("id") or h["doc"].get("id", f"hit_{i}")),
            "title": h["doc"].get("title", ""),
            "score": round(float(h.get("score", 0.0)), 4),
            "snippet": h["doc"].get("content", ""),
        }
        for i, h in enumerate(valid_hits)
    ]

    duration = int((time.time() - t0) * 1000)
    cprint.rag(query, len(formatted_hits), top_score, top_title)
    return {
        "hits": formatted_hits,
        "trace": [f"qdrant_retrieve: hits={len(formatted_hits)}, top_score={top_score:.2f} ({duration}ms)"],
    }


async def deepseek_generate_node(state: AgentState) -> Dict[str, Any]:
    """5. 调用 DeepSeek 大模型生成严谨回答"""
    t0 = time.time()
    existing_reply = state.get("reply")
    cards = list(state.get("cards") or [])

    if existing_reply:
        return {
            "reply": existing_reply,
            "cards": cards,
            "handoff": state.get("handoff", False),
            "trace": ["deepseek_generate: 保留前置确定性回复文案 (0ms)"],
        }

    reply = await deepseek_client.generate_response(
        user_message=state.get("user_message", ""),
        hits=state.get("hits", []),
        memory_summary=state.get("memory_summary", ""),
        user_profile=state.get("user_profile", {}),
        order_id=state.get("order_id"),
    )

    duration = int((time.time() - t0) * 1000)
    cprint.node(
        "deepseek_generate",
        f"DeepSeek 推理完成，生成回复: {LogColor.BRIGHT_GREEN}{len(reply)} 字{LogColor.RESET}",
        f"耗时: {duration}ms",
    )
    return {
        "reply": reply,
        "cards": cards,
        "handoff": False,
        "trace": [f"deepseek_generate: 生成答复 ({len(reply)} 字) ({duration}ms)"],
    }


def human_escalation_node(state: AgentState) -> Dict[str, Any]:
    """6. 人工接入触发节点 (主动要求或低置信度兜底)"""
    t0 = time.time()
    hits = state.get("hits", [])
    top_score = hits[0]["score"] if hits else 0.0

    if state.get("intent") == "handoff":
        reason = "客户主动要求转人工客服服务"
    elif not hits or top_score < settings.SIMILARITY_THRESHOLD:
        reason = f"Qdrant 向量匹配得分较低 (< {settings.SIMILARITY_THRESHOLD})，转人工以防误答"
    elif state.get("sentiment") in ("frustrated", "angry"):
        reason = "客户情绪预警，启动人工跟进"
    else:
        reason = "知识库无可用依据，转人工兜底处理"

    session_id = state.get("session_id", "当前会话")
    cprint.transfer(session_id, "值班客服专员", reason)

    duration = int((time.time() - t0) * 1000)
    return {
        "reply": "【智能管家温馨提示】收到您的需求，正在为您无缝转接 XX商城 官方售后值班专员。我们将保留您的完整对话快照与政策咨询记录，请稍候片刻...",
        "handoff": True,
        "escalation_reason": reason,
        "cards": list(state.get("cards") or []),
        "trace": [f"human_escalation: 触发转人工 (原因: {reason}) ({duration}ms)"],
    }


# ================= 智能条件路由 =================

def router_after_analysis(state: AgentState) -> str:
    """第一级路由：确认动作或订单/退款类意图先查订单，主动呼叫人工直接转人工"""
    if state.get("confirm_action") in ("confirm", "cancel"):
        return "order_query"
    if state.get("intent") == "handoff":
        return "human_escalation"
    if state.get("intent", "") in _ORDER_QUERY_INTENTS:
        return "order_query"
    return "qdrant_retrieve"


def router_after_order_query(state: AgentState) -> str:
    """订单查询后的条件路由：仅退款申请或确认动作进入退款节点"""
    if state.get("confirm_action") in ("confirm", "cancel") or state.get("intent") == "退款申请与审批":
        return "order_refund"
    return "qdrant_retrieve"


def router_after_retrieval(state: AgentState) -> str:
    """第二级路由：已有前置确定性答复时不误转人工；否则低置信度且情绪烦躁时转人工"""
    if state.get("reply"):
        return "deepseek_generate"
    hits = state.get("hits", [])
    top_score = hits[0]["score"] if hits else 0.0
    if top_score < settings.SIMILARITY_THRESHOLD and state.get("sentiment") in ("frustrated", "angry"):
        return "human_escalation"
    return "deepseek_generate"
