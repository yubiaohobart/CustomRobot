"""
LangGraph 对话状态定义 (AgentState)
维持整个问答生命周期的数据流转与状态检查点
"""

from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    # 会话元数据
    session_id: str
    user_message: str
    
    # 意图与情绪判定
    intent: str
    sentiment: str
    explicit_human_request: bool
    
    # Qdrant 向量召回结果
    retrieved_docs: List[Dict[str, Any]]
    top_similarity_score: float
    
    # 客户画像与记忆
    user_profile: Dict[str, Any]
    summary_memory: str
    
    # DeepSeek 提示词与回复
    assembled_prompt: str
    generated_response: str
    
    # 人工介入与风控标记
    escalated_to_human: bool
    escalation_reason: str
    
    # 执行链路追踪
    step_trace: List[Dict[str, Any]]
