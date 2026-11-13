"""
LangGraph 状态图契约定义 (InputState / OutputState / AgentState)
明确划分图输入契约、图输出契约与内部共享总线，保证节点间状态流转清晰可控。
"""

import operator
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict

# 客户咨询意图枚举，用于路由分发与客服工作台展示
Intent = Literal[
    "订单查询与物流追踪",
    "退换货运费承担与会员权益",
    "7天无理由退货政策",
    "特殊不可退换商品范围",
    "退款到账时效查询",
    "退款申请与审批",
    "1年联保与硬件保修条款",
    "常规售后咨询",
    "handoff",  # 客户主动请求转人工或触发升级接管
]


class Hit(TypedDict):
    """Qdrant 向量检索命中的知识切片结构"""
    id: str       # 知识文档/切片唯一标识
    title: str    # 售后政策或 FAQ 条目标题
    score: float  # BGE-M3 向量检索余弦相似度得分 (0.0 ~ 1.0)
    snippet: str  # 命中的政策原文切片内容，用于注入 Prompt 及前端参考来源展示


class RefundDraft(TypedDict):
    """订单退款草稿与幂等控制结构"""
    order_id: str      # 目标退款订单编号
    amount_cents: int  # 退款金额（单位：分，避免浮点误差；用于 < 300 分秒退 / >= 300 分转人工审核阈值判断）
    request_id: str    # 单次退款申请的幂等唯一流水号，防止重复提交或并发重入
    status: Literal[
        "PENDING_CONFIRM",  # 已触发 interrupt 挂起，等待客户在确认卡片点击确认/取消
        "PENDING_AUDIT",    # 金额 >= 3.00 元，已提交人工资金安全审核队列
        "SUBMITTED",        # 金额 < 3.00 元（或此前已退），已完成自动秒退/复核
        "CANCELED",         # 客户点击取消退款申请，订单保持原状态
    ]


class InputState(TypedDict, total=False):
    """每轮 API 请求传入状态图的最小输入契约（Graph 入口会自动过滤非此契约的字段）"""
    session_id: str                                     # 当前会话唯一 ID，对应 Checkpointer 的 thread_id
    user_id: str                                        # 客户唯一标识，用于日志追踪与归属校验
    user_message: str                                   # 本轮客户发送的原始消息文本
    confirm_action: Optional[Literal["confirm", "cancel"]]  # 退款确认卡片回调动作："confirm"=确认提交 / "cancel"=取消 / None=常规对话
    user_profile: Optional[Dict[str, Any]]              # 客户画像（姓名、会员等级 vipLevel/tier 等，用于订单校验与个性化回答）
    memory_summary: str                                 # 会话长期记忆摘要（跨轮次上下文沉淀，供 DeepSeek 生成连贯回复）


class OutputState(TypedDict, total=False):
    """状态图执行完毕后返回给 FastAPI 路由层的输出契约"""
    reply: Optional[str]                                # 最终返回给客户的文本回复内容
    cards: List[Dict[str, Any]]                         # 随回复下发给前端的结构化卡片列表（如 order_card 订单卡、refund_gate 退款确认卡）
    handoff: bool                                       # 是否需要转接人工客服（True 时路由层需同步更新会话状态为 NEEDS_INTERVENTION）
    intent: Intent                                      # 本轮分析得到的最终业务意图
    sentiment: Literal["calm", "neutral", "frustrated", "angry"]  # 客户实时情绪识别结果（用于低分召回时触发情绪升级兜底）
    order_id: Optional[str]                             # 本轮查询并关联成功的订单号（未命中时为 None）
    refund: Optional[RefundDraft]                       # 退款流程结果或挂起草稿（仅在触发退款流程时有值）
    hits: List[Hit]                                     # 经相似度阈值过滤后的有效知识库召回切片列表
    trace: List[str]                                    # 全链路节点执行轨迹日志，用于前端调试面板展示各步耗时与状态
    escalation_reason: Optional[str]                    # 触发人工转接或资金安全审核的具体原因说明


class AgentState(InputState, OutputState, total=False):
    """
    图内部共享状态总线：
    继承 InputState 与 OutputState 全部字段；
    由于 MemorySaver 会持久化同一 thread_id 的历史状态，analyze_query_node 会在每轮开始时主动复位瞬态输出字段。
    """
    # 使用 operator.add 作为 Reducer：各节点仅需返回本节点新增的 trace 列表，LangGraph 会自动按顺序累加而非覆盖
    trace: Annotated[List[str], operator.add]
