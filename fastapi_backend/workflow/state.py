"""
LangGraph 状态图契约定义 (AgentState - 工业级精简加固版)
包含 InputState、OutputState、AgentState 及辅助类型定义。
收敛至 workflow 目录下，彻底剔除冗余字段与死代码，遵循单一数据源原则。
"""

import operator
from typing import Annotated, Literal, TypedDict, List, Dict, Any, Optional
from langgraph.graph.message import add_messages

Intent = Literal[
    "订单查询与物流追踪",
    "退换货运费承担与会员权益",
    "7天无理由退货政策",
    "特殊不可退换商品范围",
    "退款到账时效查询",
    "退款申请与审批",
    "1年联保与硬件保修条款",
    "常规售后咨询",
    "handoff"
]

class Hit(TypedDict):
    """Qdrant 向量知识库检索命中的知识切片结构"""
    id: str           # 知识切片唯一标识符 (UUID / Chunk ID)
    title: str        # 知识点标题或政策条款名称
    score: float      # 向量相似度得分 (Vector Cosine Similarity Score, 0.0 - 1.0)
    snippet: str      # 知识点正文片段 (保留完整条款，防止截断关键到账时效)

class RefundDraft(TypedDict):
    """订单退款草稿与幂等状态机控制结构"""
    order_id: str     # 关联的商城订单编号 (例: ORD-2026-88992)
    amount_cents: int # 退款金额（以“分”为单位存储，严防浮点数精度误差，例: 299900 表示 ¥2999.00）
    request_id: str   # 幂等键 (Idempotency Key)，防止网络重试或重复触发退款
    status: Literal["PENDING_CONFIRM", "PENDING_AUDIT", "SUBMITTED", "CANCELED"] 
                      # 退款草稿状态机: 待客户确认、待人工审核、已提交/处理中、已取消

class InputState(TypedDict, total=False):
    """每轮 API 请求由外部传入的初始输入契约 (Input Schema)"""
    session_id: str                                        # 对话会话唯一标识符 (Session ID)
    user_id: str                                           # 用户唯一标识符 (User ID)
    user_message: str                                      # 客户本轮输入的自然语言问题或诉求
    confirm_action: Literal["confirm", "cancel"] | None    # 前端退款确认交互卡片的点击动作选择 ('confirm' 或 'cancel')
    user_profile: Optional[Dict[str, Any]]                 # 外部注入画像与上下文

class OutputState(TypedDict, total=False):
    """LangGraph 状态图执行完毕后最终返回给 API 接口的输出契约 (Output Schema)"""
    reply: str                       # 智能客服最终生成的回复文本内容
    cards: list[dict]                # 携带的交互式卡片数据（如订单卡片、退款确认卡片等，同类型已去重）
    handoff: bool                    # 是否触发人工客服转接标识 (True 表示需要转人工坐席)
    order_id: Optional[str]          # 命中的关联订单 ID
    refund: Optional[RefundDraft]    # 退款处理草稿/凭据
    hits: list[Hit]                  # 命中的知识切片
    trace: list[str]                 # 全链路节点流转日志 (普通列表，供外部消费)
    escalation_reason: Optional[str] # 转人工原因（若 handoff=True）

class AgentState(InputState, OutputState, total=False):
    """
    LangGraph 客服多智能体核心状态总线 (Core State Graph Schema)
    仅保留单一数据源核心字段，去除了旧版冗余别名：
    - 去除 summary_memory (统一收敛为 memory_summary)
    - 去除 refund_gate (统一收敛为 confirm_action + refund)
    - 去除 retrieved_docs (统一收敛为 hits: list[Hit])
    - 去除 generated_response (统一收敛为 reply)
    - 去除 escalated_to_human (统一收敛为 handoff)
    - 去除 step_trace 冗余字典存储 (统一使用 trace Reducer)
    """
    messages: Annotated[list, add_messages]
    memory_summary: str                                           # 滚动摘要记忆
    intent: Intent                                                # 意图枚举 (纯净无死代码)
    sentiment: Literal["calm", "neutral", "frustrated", "angry"]      # 情绪识别
    order_id: str | None                                          # 订单唯一标识符
    hits: list[Hit]                                               # 检索切片
    refund: RefundDraft | None                                    # 退款幂等草稿
    # 状态图内部使用 operator.add Reducer 增量追加流转日志；OutputState 外部消费时为标准 list[str]
    trace: Annotated[list[str], operator.add]
