"""
意图识别、情绪分析、语义路由与人工升级策略服务 (Cascade NLU & Escalation Service)
采用工业界经典三级漏斗架构：
- L0: 确定性硬规则与安全护栏（confirm_action 回调、红线转人工、寒暄拦截、否定/多意图/指代检测）
- L1: 基于 BGE-M3 向量的 Semantic Router（低延迟语义匹配 + Margin 置信度评估）
- L2: 灰区/歧义/多轮指代走 DeepSeek 结构化分类 + Query 改写，异常或离线时自动回退规则兜底
"""

import asyncio
from dataclasses import dataclass, field
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from config import settings
from core.embedding import bge_m3_engine
from core.llm import deepseek_client
from core.logger import cprint

VALID_INTENTS: Tuple[str, ...] = (
    "订单查询与物流追踪",
    "退换货运费承担与会员权益",
    "7天无理由退货政策",
    "特殊不可退换商品范围",
    "退款到账时效查询",
    "退款申请与审批",
    "1年联保与硬件保修条款",
    "常规售后咨询",
    "handoff",
)

VALID_SENTIMENTS: Tuple[str, ...] = ("calm", "neutral", "frustrated", "angry")

# 政策/规则/时效咨询保护词：命中此类词时优先走知识库问答，避免“退货运费谁出”等纯咨询误触发退款确认卡片
_POLICY_GUARD_KEYWORDS = (
    "运费", "谁出", "谁付", "包邮", "免运费",
    "到账", "几天能收到", "几天到", "多久到账", "打款时间", "退款多久", "时效", "几天",
    "7天", "七天", "无理由", "政策", "规定", "条件", "流程是什么",
    "可以退吗", "能不能退", "怎么退", "如何退", "换新",
    "进度", "状态", "审核到哪", "特殊商品", "不能退", "不给退", "定制", "生鲜", "拆封",
)

# 显式退款/退货申请触发词（仅在未命中政策咨询保护词与否定词时生效）
_REFUND_APPLY_KEYWORDS = (
    "申请退款", "我要退款", "办理退款", "退钱给我", "我要退货退款",
    "提交退款", "申请退货", "我要退货", "退款", "退货", "退钱", "要退", "退掉",
)

# 否定/转折/多意图歧义信号：命中时强制交由 L1/L2 深度语义判定，避免关键词误杀
_NEGATION_OR_COMPLEX_RE = re.compile(
    r"(不是要退|不想退|不要退|不退款|不退货|并非退|只是问|顺便|另外|顺带|但是|不过|虽然)"
)

# 规范化订单号正则（替代硬编码示例单号）
_ORDER_ID_PATTERN = re.compile(r"\bORD[-_]?\d{4}[-_]?\d{4,6}\b|\bORD[-_]?\d{5,6}\b", re.IGNORECASE)

# 强转人工客服关键词（L0 红线直通）
_HANDOFF_PURE_KEYWORDS = (
    "转人工", "找人工", "人工客服", "投诉", "消协", "12315", "找领导", "不要机器人", "马上帮我转接人工",
)

# 按业务优先级排序的兜底规则表
_INTENT_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("退款到账时效查询", ("到账", "几天能收到", "几天到", "多久到账", "打款时间", "退款多久", "时效", "几天")),
    ("退换货运费承担与会员权益", ("运费", "谁出", "谁付", "包邮", "免运费")),
    ("特殊不可退换商品范围", ("特殊商品", "不能退", "不给退", "定制", "生鲜", "内裤", "母婴", "拆封")),
    ("7天无理由退货政策", ("7天", "七天", "无理由", "退货", "退换", "规定", "政策", "条件", "怎么退", "如何退")),
    ("订单查询与物流追踪", ("订单", "查订单", "物流", "快递", "运单", "发货", "到哪了", "什么时候到", "送达", "签收", "收件地址", "进度", "状态")),
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

# L1 语义路由标准锚点库（覆盖各类高频与长尾口语表达）
_SEMANTIC_INTENT_ANCHORS: Dict[str, Tuple[str, ...]] = {
    "订单查询与物流追踪": (
        "帮我查一下我的订单状态和快递物流到哪了",
        "我的包裹什么时候发货，预计几天能送达签收",
        "查一下收件地址和快递运单号",
    ),
    "退款申请与审批": (
        "我要申请退款，把这笔订单退掉并退钱给我",
        "请帮我办理退货退款，直接提交退款申请",
        "这单商品我不想要了，现在就要申请退货退款",
    ),
    "退款到账时效查询": (
        "退款提交后多久能到账，打款时间是几天",
        "我的退款审核到哪一步了，钱什么时候退回银行卡",
    ),
    "退换货运费承担与会员权益": (
        "退换货的快递运费由谁承担，黄金会员退货免运费怎么申请",
        "我有VIP会员权益，退货是不是平台包邮补贴运费",
    ),
    "7天无理由退货政策": (
        "7天无理由退货有什么规定和条件，具体怎么办理退货",
        "刚收到商品几天，符合无理由退货政策吗",
    ),
    "特殊不可退换商品范围": (
        "拆封了未使用的电子产品或者定制商品、生鲜可以退货吗",
        "哪些属于特殊商品不支持7天无理由退货",
    ),
    "1年联保与硬件保修条款": (
        "设备坏了在1年质保联保期内怎么申请免费换新或维修",
        "电子产品进水或摔坏了还能保修吗",
    ),
    "handoff": (
        "机器人解决不了问题，请立刻帮我转接人工客服",
        "我要投诉，别用智能客服了，马上找人工专员或主管处理",
    ),
}

_L1_HIGH_CONFIDENCE_THRESHOLD = 0.72
_L1_MARGIN_THRESHOLD = 0.05
_L1_RETRY_COOLDOWN_SEC = 60.0


@dataclass(slots=True)
class IntentAnalysisResult:
    intent: str
    sentiment: str
    confidence: float
    route_source: str
    rewritten_query: str
    top_candidates: List[Tuple[str, float]] = field(default_factory=list)


class IntentService:
    """三级漏斗意图分类、情绪识别与转人工决策服务"""

    def __init__(self) -> None:
        self._anchor_lock = threading.RLock()
        self._anchor_vectors: Optional[List[Tuple[str, List[float]]]] = None
        self._l1_cooldown_until: float = 0.0

    def detect_sentiment(self, msg: str, explicit_handoff: bool) -> str:
        msg_lower = msg.lower()
        if any(k in msg_lower for k in ("骗子", "投诉", "消协", "12315", "火大", "气死", "态度差", "打死")):
            return "angry"
        if explicit_handoff or any(k in msg_lower for k in ("差评", "太慢", "生气", "催", "急", "不要机器人")):
            return "frustrated"
        if any(k in msg_lower for k in ("谢谢", "感谢", "好的", "明白了", "点赞", "挺快")):
            return "calm"
        return "neutral"

    def _is_explicit_handoff(self, msg_lower: str, has_negation: bool) -> bool:
        if any(k in msg_lower for k in _HANDOFF_PURE_KEYWORDS):
            return True
        if ("人工" in msg_lower or "主管" in msg_lower) and not has_negation:
            if not any(k in msg_lower for k in ("人工审核", "无需人工", "自动")):
                return True
        return False

    def _fallback_rule_classify(self, user_message: str) -> Tuple[str, str]:
        """确定性关键词兜底分类（含否定词与订单号正则保护）"""
        msg = user_message.lower()
        has_negation = bool(_NEGATION_OR_COMPLEX_RE.search(msg))
        is_policy_q = any(k in msg for k in _POLICY_GUARD_KEYWORDS)
        is_refund_apply = (not is_policy_q) and (not has_negation) and any(k in msg for k in _REFUND_APPLY_KEYWORDS)
        explicit_handoff = self._is_explicit_handoff(msg, has_negation)
        sentiment = self.detect_sentiment(msg, explicit_handoff)

        if explicit_handoff:
            return "handoff", sentiment
        if is_refund_apply:
            return "退款申请与审批", sentiment

        for candidate_intent, keywords in _INTENT_RULES:
            if any(k in msg for k in keywords):
                return candidate_intent, sentiment
        if _ORDER_ID_PATTERN.search(user_message):
            return "订单查询与物流追踪", sentiment
        return "常规售后咨询", sentiment

    def _ensure_anchor_vectors(self) -> Optional[List[Tuple[str, List[float]]]]:
        """懒加载并缓存各意图的 BGE-M3 标准锚点向量（Ollama 不可用时带冷却熔断）"""
        now = time.time()
        if self._anchor_vectors is not None:
            return self._anchor_vectors
        if now < self._l1_cooldown_until:
            return None

        with self._anchor_lock:
            if self._anchor_vectors is not None:
                return self._anchor_vectors
            if time.time() < self._l1_cooldown_until:
                return None

            anchor_pairs: List[Tuple[str, str]] = []
            for intent_name, examples in _SEMANTIC_INTENT_ANCHORS.items():
                for example in examples:
                    anchor_pairs.append((intent_name, example))
            try:
                vecs = bge_m3_engine.embed_documents([text for _, text in anchor_pairs])
                self._anchor_vectors = [
                    (intent_name, vec) for (intent_name, _), vec in zip(anchor_pairs, vecs)
                ]
                return self._anchor_vectors
            except Exception as exc:
                self._l1_cooldown_until = time.time() + _L1_RETRY_COOLDOWN_SEC
                cprint.warning(f"[Intent L1] BGE-M3 语义路由锚点初始化跳过，已熔断降级: {exc}")
                return None

    def _semantic_score_sync(self, query_text: str) -> List[Tuple[str, float]]:
        """同步计算输入文本与所有意图锚点的余弦相似度（向量已 L2 归一化，点积即余弦）"""
        anchors = self._ensure_anchor_vectors()
        if not anchors:
            return []
        try:
            q_vec = bge_m3_engine.embed_query(query_text)
        except Exception as exc:
            self._l1_cooldown_until = time.time() + _L1_RETRY_COOLDOWN_SEC
            cprint.warning(f"[Intent L1] 查询向量化失败，降级后续分支: {exc}")
            return []

        best_per_intent: Dict[str, float] = {}
        for intent_name, a_vec in anchors:
            sim = sum(q * a for q, a in zip(q_vec, a_vec))
            prev = best_per_intent.get(intent_name, -1.0)
            if sim > prev:
                best_per_intent[intent_name] = sim

        ranked = sorted(best_per_intent.items(), key=lambda x: x[1], reverse=True)
        return [(k, round(v, 4)) for k, v in ranked]

    @staticmethod
    def _build_l1_query_text(user_message: str, recent_messages: Optional[List[Dict[str, Any]]]) -> str:
        """若用户发的是超短省略句且存在历史对话，拼接上一轮语境以提升 L1 召回稳定性"""
        text = user_message.strip()
        if len(text) <= 14 and recent_messages:
            for item in reversed(recent_messages):
                if isinstance(item, dict) and item.get("role") in ("user", "assistant", "human_agent"):
                    prev_text = str(item.get("content") or "").strip()
                    if prev_text and prev_text != text:
                        return f"{prev_text[:60]} -> {text}"
        return text

    async def analyze_query(
        self,
        user_message: str,
        *,
        confirm_action: Optional[str] = None,
        recent_messages: Optional[List[Dict[str, Any]]] = None,
        memory_summary: str = "",
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> IntentAnalysisResult:
        """
        三级漏斗异步 NLU 分析入口（供 LangGraph analyze_query_node 调用）：
        L0 确定性护栏 -> L1 BGE-M3 语义路由 -> L2 DeepSeek 灰区结构化分类与上下文改写 -> 规则兜底
        """
        raw_msg = (user_message or "").strip()
        msg_lower = raw_msg.lower()
        has_complex_signal = bool(_NEGATION_OR_COMPLEX_RE.search(msg_lower))

        # --- L0: 确定性硬规则与安全护栏 ---
        if confirm_action in ("confirm", "cancel"):
            return IntentAnalysisResult(
                intent="退款申请与审批",
                sentiment="neutral",
                confidence=1.0,
                route_source="L0_CONFIRM",
                rewritten_query=raw_msg,
            )

        explicit_handoff = self._is_explicit_handoff(msg_lower, has_complex_signal)
        sentiment = self.detect_sentiment(msg_lower, explicit_handoff)
        if explicit_handoff:
            return IntentAnalysisResult(
                intent="handoff",
                sentiment=sentiment,
                confidence=1.0,
                route_source="L0_HANDOFF",
                rewritten_query=raw_msg,
            )

        if self.is_chitchat(raw_msg) and not has_complex_signal:
            return IntentAnalysisResult(
                intent="常规售后咨询",
                sentiment=sentiment,
                confidence=0.95,
                route_source="L0_CHITCHAT",
                rewritten_query=raw_msg,
            )

        # --- L1: BGE-M3 语义向量路由 ---
        l1_input = self._build_l1_query_text(raw_msg, recent_messages)
        ranked_candidates = await asyncio.to_thread(self._semantic_score_sync, l1_input) if raw_msg else []
        top_intent, top_score = ranked_candidates[0] if ranked_candidates else ("常规售后咨询", 0.0)
        second_score = ranked_candidates[1][1] if len(ranked_candidates) > 1 else 0.0
        margin = top_score - second_score

        # 短句省略/存在历史上下文/否定或复合多意图时，不直接信任 L1，放行给 L2 做语境改写
        is_elliptical_followup = len(raw_msg) <= 10 and bool(recent_messages)
        l1_confident = (
            bool(ranked_candidates)
            and top_score >= _L1_HIGH_CONFIDENCE_THRESHOLD
            and margin >= _L1_MARGIN_THRESHOLD
            and not has_complex_signal
            and not is_elliptical_followup
        )
        # 政策保护词二次护栏：若 L1 误将纯政策咨询（如“拆封可以退吗”）判成直接退款，退回灰区由 L2/规则校准
        if l1_confident and top_intent == "退款申请与审批" and any(k in msg_lower for k in _POLICY_GUARD_KEYWORDS):
            l1_confident = False

        if l1_confident:
            return IntentAnalysisResult(
                intent=top_intent,
                sentiment=sentiment,
                confidence=top_score,
                route_source="L1_SEMANTIC",
                rewritten_query=raw_msg,
                top_candidates=ranked_candidates[:3],
            )

        # --- L2: 灰区 / 歧义 / 上下文指代 -> DeepSeek 结构化分类 + Query 改写 ---
        l2_res = await deepseek_client.classify_intent_structured(
            raw_msg,
            valid_intents=list(VALID_INTENTS),
            valid_sentiments=list(VALID_SENTIMENTS),
            recent_messages=recent_messages,
            memory_summary=memory_summary,
            user_profile=user_profile,
        )
        if l2_res is not None:
            return IntentAnalysisResult(
                intent=l2_res["intent"],
                sentiment=l2_res["sentiment"],
                confidence=l2_res["confidence"],
                route_source="L2_LLM",
                rewritten_query=l2_res["rewritten_query"],
                top_candidates=ranked_candidates[:3],
            )

        # --- 离线/无 Key 兜底：若 L1 有一定把握且未命中政策冲突则采用 L1，否则回退规则 ---
        rule_intent, rule_sentiment = self._fallback_rule_classify(raw_msg)
        if rule_intent != "常规售后咨询":
            return IntentAnalysisResult(
                intent=rule_intent,
                sentiment=rule_sentiment,
                confidence=0.75,
                route_source="L0_RULE_FALLBACK",
                rewritten_query=raw_msg,
                top_candidates=ranked_candidates[:3],
            )
        if ranked_candidates and top_score >= 0.62 and not (
            top_intent == "退款申请与审批" and any(k in msg_lower for k in _POLICY_GUARD_KEYWORDS)
        ):
            return IntentAnalysisResult(
                intent=top_intent,
                sentiment=sentiment,
                confidence=top_score,
                route_source="L1_FALLBACK",
                rewritten_query=raw_msg,
                top_candidates=ranked_candidates[:3],
            )
        return IntentAnalysisResult(
            intent=rule_intent,
            sentiment=rule_sentiment,
            confidence=0.5,
            route_source="L0_RULE_FALLBACK",
            rewritten_query=raw_msg,
            top_candidates=ranked_candidates[:3],
        )

    def classify_query(self, user_message: str) -> Tuple[str, str]:
        """兼容同步调用接口：返回 (intent, sentiment)"""
        return self._fallback_rule_classify(user_message)

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
