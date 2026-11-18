"""
意图识别、情绪分析、寒暄判定与人工升级策略服务 (Intent & Escalation Service)
独立于 LangGraph 编排层，负责自然语言规则分类与客服策略判定。
"""

from typing import Any, Dict, List, Tuple

# 政策/规则/时效咨询保护词：命中此类词时优先走知识库问答，避免“退货运费谁出”等纯咨询误触发退款确认卡片
_POLICY_GUARD_KEYWORDS = (
    "运费", "谁出", "谁付", "包邮", "免运费",
    "到账", "几天能收到", "几天到", "多久到账", "打款时间", "退款多久", "时效", "几天",
    "7天", "七天", "无理由", "政策", "规定", "条件", "流程是什么",
    "可以退吗", "能不能退", "怎么退", "如何退",
    "进度", "状态", "审核到哪", "特殊商品", "不能退", "不给退", "定制", "生鲜", "拆封",
)

# 显式退款/退货申请触发词（仅在未命中政策咨询保护词时生效）
_REFUND_APPLY_KEYWORDS = (
    "申请退款", "我要退款", "办理退款", "退钱给我", "我要退货退款",
    "提交退款", "申请退货", "我要退货", "退款", "退货", "退钱", "要退", "退掉",
)

# 强转人工客服关键词（优先级最高，命中后直接路由到人工坐席）
_HANDOFF_PURE_KEYWORDS = (
    "转人工", "找人工", "人工客服", "投诉", "消协", "找领导", "不要机器人", "马上帮我转接人工",
)

# 按业务优先级排序的意图规则表
_INTENT_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("退款到账时效查询", ("到账", "几天能收到", "几天到", "多久到账", "打款时间", "退款多久", "时效", "几天")),
    ("退换货运费承担与会员权益", ("运费", "谁出", "谁付", "包邮", "免运费")),
    ("特殊不可退换商品范围", ("特殊商品", "不能退", "不给退", "定制", "生鲜", "内裤", "母婴", "拆封")),
    ("7天无理由退货政策", ("7天", "七天", "无理由", "退货", "退换", "规定", "政策", "条件", "怎么退", "如何退")),
    ("订单查询与物流追踪", ("订单", "查订单", "物流", "快递", "运单", "发货", "到哪了", "什么时候到", "送达", "签收", "收件地址", "进度", "状态", "ord-", "88992", "90412", "77310")),
    ("1年联保与硬件保修条款", ("保修", "维修", "坏了", "换新", "质保", "联保", "进水", "摔坏")),
)

# 需要先查询关联订单中台数据的意图集合
ORDER_QUERY_INTENTS = frozenset({
    "订单查询与物流追踪",
    "退款申请与审批",
    "退款到账时效查询",
    "退换货运费承担与会员权益",
    "7天无理由退货政策",
})

_CHITCHAT_KEYWORDS = ("你好", "您好", "在吗", "在不在", "谢谢", "感谢", "再见", "拜拜", "好的", "明白了", "收到", "嗯")


class IntentService:
    """意图分类、情绪识别与转人工决策服务"""

    def detect_sentiment(self, msg: str, explicit_handoff: bool) -> str:
        msg_lower = msg.lower()
        if any(k in msg_lower for k in ("骗子", "投诉", "消协", "火大", "气死", "态度差", "打死")):
            return "angry"
        if explicit_handoff or any(k in msg_lower for k in ("差评", "太慢", "生气", "催", "急", "不要机器人")):
            return "frustrated"
        if any(k in msg_lower for k in ("谢谢", "感谢", "好的", "明白了", "点赞", "挺快")):
            return "calm"
        return "neutral"

    def classify_query(self, user_message: str) -> Tuple[str, str]:
        """返回 (intent, sentiment)"""
        msg = user_message.lower()
        is_policy_q = any(k in msg for k in _POLICY_GUARD_KEYWORDS)
        is_refund_apply = (not is_policy_q) and any(k in msg for k in _REFUND_APPLY_KEYWORDS)
        explicit_handoff = any(k in msg for k in _HANDOFF_PURE_KEYWORDS) or (
            ("人工" in msg or "主管" in msg) and not is_refund_apply
        )
        sentiment = self.detect_sentiment(msg, explicit_handoff)

        if explicit_handoff:
            return "handoff", sentiment
        if is_refund_apply:
            return "退款申请与审批", sentiment

        for candidate_intent, keywords in _INTENT_RULES:
            if any(k in msg for k in keywords):
                return candidate_intent, sentiment
        return "常规售后咨询", sentiment

    def requires_order_query(self, intent: str) -> bool:
        return intent in ORDER_QUERY_INTENTS

    def is_chitchat(self, user_message: str) -> bool:
        """判断是否为纯礼貌问候/寒暄短句，避免知识库无命中时把打招呼误转人工"""
        text = user_message.strip().lower()
        return len(text) <= 12 and any(k in text for k in _CHITCHAT_KEYWORDS)

    def build_escalation_info(
        self,
        intent: str,
        sentiment: str,
        hits: List[Dict[str, Any]],
        similarity_threshold: float,
    ) -> Tuple[str, str]:
        """生成转人工原因与统一安抚话术，返回 (reason, reply)"""
        top_score = hits[0]["score"] if hits else 0.0
        if intent == "handoff":
            reason = "客户主动要求转人工客服服务"
        elif not hits or top_score < similarity_threshold:
            reason = f"Qdrant 向量匹配得分较低 (< {similarity_threshold})，转人工以防误答"
        elif sentiment in ("frustrated", "angry"):
            reason = "客户情绪预警，启动人工跟进"
        else:
            reason = "知识库无可用依据，转人工兜底处理"

        reply = (
            "【智能管家温馨提示】收到您的需求，正在为您无缝转接 XX商城 官方售后值班专员。"
            "我们将保留您的完整对话快照与政策咨询记录，请稍候片刻..."
        )
        return reason, reply


intent_service = IntentService()
