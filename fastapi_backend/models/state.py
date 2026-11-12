"""
LangGraph 对话状态契约定义 (AgentState - 优化精简版)
作为整个客服多智能体工作流的状态总线 (State Schema)，
剔除了冗余的文本事实与重复对象，采用单一数据源原则。
"""

from typing import TypedDict, List, Dict, Any, Optional


class AgentState(TypedDict):
    # ==================== 1. 会话元数据 ====================
    session_id: str
    user_message: str

    # ==================== 2. 意图与情绪判定 ====================
    intent: str
    sentiment: str
    explicit_human_request: bool

    # ==================== 3. 知识库检索 ====================
    retrieved_docs: List[Dict[str, Any]]
    retrieval_ran: bool
    top_similarity_score: float

    # ==================== 4. 用户画像与长期记忆 ====================
    user_profile: Dict[str, Any]
    summary_memory: str

    # ==================== 5. 业务中台实体 (单一数据源) ====================
    current_order: Optional[Dict[str, Any]]
    """
    【当前关联订单实体】
    - 统一存储关联的完整 OrderData 对象，消除了多份重复对象及 Markdown 文本的内存冗余。
    """

    refund_gate: Optional[Dict[str, Any]]
    """
    【退款二次确认挂起状态槽位】
    - 结构示例：{"pending": bool, "action": Optional[str]}
    """

    # ==================== 6. 人工介入与风控标记 ====================
    escalated_to_human: bool
    escalation_reason: str

    # ==================== 7. 全链路追踪 ====================
    step_trace: List[Dict[str, Any]]
