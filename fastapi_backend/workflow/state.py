"""
LangGraph 状态图契约定义 (InputState / OutputState / AgentState)
"""

import operator
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict

Intent = Literal[
    "订单查询与物流追踪",
    "退换货运费承担与会员权益",
    "7天无理由退货政策",
    "特殊不可退换商品范围",
    "退款到账时效查询",
    "退款申请与审批",
    "1年联保与硬件保修条款",
    "常规售后咨询",
    "handoff",
]


class Hit(TypedDict):
    """Qdrant 向量检索命中的知识切片"""
    id: str
    title: str
    score: float
    snippet: str


class RefundDraft(TypedDict):
    """订单退款草稿与幂等控制结构"""
    order_id: str
    amount_cents: int
    request_id: str
    status: Literal["PENDING_CONFIRM", "PENDING_AUDIT", "SUBMITTED", "CANCELED"]


class InputState(TypedDict, total=False):
    """每轮 API 请求传入的最小输入契约"""
    session_id: str
    user_id: str
    user_message: str
    confirm_action: Optional[Literal["confirm", "cancel"]]
    user_profile: Optional[Dict[str, Any]]
    memory_summary: str


class OutputState(TypedDict, total=False):
    """状态图执行完毕返回给 API 的输出契约"""
    reply: Optional[str]
    cards: List[Dict[str, Any]]
    handoff: bool
    intent: Intent
    sentiment: Literal["calm", "neutral", "frustrated", "angry"]
    order_id: Optional[str]
    refund: Optional[RefundDraft]
    hits: List[Hit]
    trace: List[str]
    escalation_reason: Optional[str]


class AgentState(InputState, OutputState, total=False):
    """图内部共享状态总线：复用 Input/Output 字段，仅对 trace 追加 Reducer"""
    trace: Annotated[List[str], operator.add]
