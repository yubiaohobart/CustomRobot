"""
LangGraph 状态图契约定义 (CSState - 工业级重构版与全字段详细注释)
包含 InputState、OutputState、CSState 及辅助类型定义。
将状态定义收敛至 workflow 目录下，贴合 LangGraph 工作流架构设计。
"""

import operator
from typing import Annotated, Literal, TypedDict, List, Dict, Any, Optional
from langgraph.graph.message import add_messages

Intent = Literal[
    "refund_request", 
    "refund_status", 
    "order_status", 
    "faq", 
    "handoff", 
    "chitchat",
    "订单查询与物流追踪",
    "退换货运费承担与会员权益",
    "7天无理由退货政策",
    "特殊不可退换商品范围",
    "退款到账时效查询",
    "退款申请与审批",
    "1年联保与硬件保修条款",
    "常规售后咨询"
]

class Hit(TypedDict):
    """Qdrant 向量知识库检索命中的知识切片结构"""
    id: str           # 知识切片唯一标识符 (UUID / Chunk ID)
    title: str        # 知识点标题或政策条款名称
    score: float      # 向量相似度得分 (Vector Cosine Similarity Score, 0.0 - 1.0)
    snippet: str      # 知识点正文精简片段 (只留核心文本，减少上下文膨胀)

class RefundDraft(TypedDict):
    """订单退款草稿与幂等状态机控制结构"""
    order_id: str     # 关联的商城订单编号 (例: ORD-2026-88992)
    amount_cents: int # 退款金额（以“分”为单位存储，严防浮点数精度误差，例: 299900 表示 ¥2999.00）
    request_id: str   # 幂等键 (Idempotency Key)，防止网络重试或重复触发退款
    status: Literal["PENDING_CONFIRM", "PENDING_AUDIT", "SUBMITTED", "CANCELED"] 
                      # 退款草稿状态机: 待客户确认、待人工审核、已提交/处理中、已取消

class InputState(TypedDict):
    """每轮 API 请求由外部传入的初始输入契约 (Input Schema)"""
    session_id: str                                        # 对话会话唯一标识符 (Session ID)
    user_id: str                                           # 用户唯一标识符 (User ID)
    user_message: str                                      # 客户本轮输入的自然语言问题或诉求
    confirm_action: Literal["confirm", "cancel"] | None    # 前端退款确认交互卡片的点击动作选择 ('confirm' 或 'cancel')

class OutputState(TypedDict):
    """LangGraph 状态图执行完毕后最终返回给 API 接口的输出契约 (Output Schema)"""
    reply: str          # 智能客服最终生成的回复文本内容
    cards: list[dict]   # 携带的交互式卡片数据（如订单卡片、退款确认卡片等）
    handoff: bool       # 是否触发人工客服转接标识 (True 表示需要转人工坐席)

class CSState(InputState, OutputState, total=False):
    """
    LangGraph 多智能体客服工作流的核心状态总线 (Core State Graph Schema)
    继承自 InputState 与 OutputState，并包含内部中间流转状态。
    """
    # 1. 对话历史消息列表（使用 LangGraph add_messages reducer 自动合并多轮历史消息）
    messages: Annotated[list, add_messages]
    
    # 2. 真正的滚动摘要记忆（限长压缩存储，防止长对话导致 Token 超限）
    memory_summary: str
    
    # 3. 客户意图枚举分类（便于图节点进行精准的条件分支路由）
    intent: Intent
    
    # 4. 客户情绪分析判定（支持 calm, neutral, frustrated, angry 四档）
    sentiment: Literal["calm", "neutral", "frustrated", "angry"]
    
    # 5. 关联订单唯一引用标识（只存 ID 引用，避免完整对象序列化导致检查点膨胀）
    order_id: str | None
    
    # 6. 知识库向量检索命中的知识切片列表
    hits: list[Hit]
    
    # 7. 退款草稿及幂等状态槽位
    refund: RefundDraft | None
    
    # 8. 工作流全链路执行追踪（使用 operator.add reducer，每个节点自动追加 ["xxx"]）
    trace: Annotated[list[str], operator.add]

    # ==================== 9. 兼容性扩展字段（支持现有节点无缝运行） ====================
    user_profile: Dict[str, Any]          # 客户完整画像（包含姓名、手机号、VIP等级等）
    current_order: Optional[Dict[str, Any]] # 当前完整订单实体数据缓存
    refund_gate: Optional[Dict[str, Any]]   # 旧版退款挂起槽位兼容
    retrieved_docs: List[Dict[str, Any]]    # 检索出的文档原始字典列表
    retrieval_ran: bool                     # 标志位：是否已执行过知识库检索
    top_similarity_score: float             # 最高相似度得分数值
    escalated_to_human: bool                # 标志位：是否已升级至人工转接
    escalation_reason: str                  # 转人工的具体触发原因说明
    step_trace: Annotated[list[str], operator.add] # 兼容旧版字典结构化追踪
