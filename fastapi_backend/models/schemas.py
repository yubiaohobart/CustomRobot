"""
Pydantic 业务请求与响应模型定义 (Schemas)
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class KnowledgeDocItem(BaseModel):
    id: str
    title: str
    category: str = "售后政策"
    content: str
    tags: List[str] = Field(default_factory=list)
    keywords: Optional[List[str]] = Field(default_factory=list)
    updatedAt: str = "2026-01-15T09:00:00Z"

class ChatRequest(BaseModel):
    sessionId: str = Field(default="session_user_001", description="客户端会话唯一标识")
    message: str = Field(..., min_length=1, description="用户咨询内容")
    userProfile: Optional[Dict[str, Any]] = Field(default=None, description="客户画像（VIP等级、关联订单等）")

class ChatResponse(BaseModel):
    sessionId: str
    reply: str
    confidenceScore: float = 0.90
    sentiment: str = "neutral"
    intent: str = "售后服务咨询"
    escalatedToHuman: bool = False
    escalationReason: Optional[str] = None
    references: List[Dict[str, Any]] = Field(default_factory=list)
    latencyMs: int = 35
    stepTrace: List[Dict[str, Any]] = Field(default_factory=list)
    session: Optional[Dict[str, Any]] = None

class TransferRequest(BaseModel):
    targetAgentId: str = Field(default="agent_101", description="指派目标坐席工号")
    reason: str = Field(default="客户要求人工介入", description="转接原因说明")
    operatorNote: Optional[str] = Field(default="", description="前台坐席补充备忘")
    triggerType: Optional[str] = Field(default="user_requested", description="触发类型：user_requested / low_confidence / emotion_warning")

class InterveneRequest(BaseModel):
    action: str = Field(..., description="'takeover' (人工接管) 或 'release' (交还AI)")
    agentId: Optional[str] = Field(default="agent_101")
    note: Optional[str] = Field(default="")

class HumanMessageRequest(BaseModel):
    message: str = Field(..., min_length=1)
    agentId: Optional[str] = Field(default="agent_101")

class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="检索文本")
    topK: int = Field(default=3, ge=1, le=10, description="召回 Top-K 数量")
    minScore: float = Field(default=0.0, ge=0.0, le=1.0, description="最低相似度过滤阈值")

class GenerateSuggestionRequest(BaseModel):
    sessionId: str = Field(default="session_user_001")
    context: Optional[str] = Field(default=None)

class TestRequest(BaseModel):
    query: Optional[str] = Field(default="黄金会员退货免运费怎么申请？", description="待测试的提问文本")
    testOllama: bool = Field(default=True, description="是否测试本地 Ollama 向量化")
    testQdrant: bool = Field(default=True, description="是否测试 Qdrant 纯内存检索")
    testLLM: bool = Field(default=False, description="是否调用真实 DeepSeek 产生答复")
