"""
全局系统配置中心 (Configuration Center)
管理 DeepSeek 大模型、BGE-M3 向量模型、Qdrant 向量数据库与服务端口
"""

import os
from typing import Optional
from pydantic import BaseModel, Field

class Settings(BaseModel):
    # 服务端基础配置
    APP_NAME: str = "IntelliServe 智能客服系统"
    VERSION: str = "3.0.0"
    FASTAPI_HOST: str = os.getenv("FASTAPI_HOST", "0.0.0.0")
    FASTAPI_PORT: int = int(os.getenv("FASTAPI_PORT", os.getenv("PORT", "5000")))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # 大语言模型配置 (DeepSeek)
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")  # deepseek-chat 或 deepseek-reasoner
    DEEPSEEK_TEMPERATURE: float = float(os.getenv("DEEPSEEK_TEMPERATURE", "0.3"))
    DEEPSEEK_MAX_TOKENS: int = int(os.getenv("DEEPSEEK_MAX_TOKENS", "1024"))

    # 本地 Ollama 向量嵌入模型配置 (BGE-M3)
    # 默认连接本地 Ollama 服务: http://localhost:11434，拉取 bge-m3 即可一键使用
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
    OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3")
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "bge-m3")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1024"))  # BGE-M3 标准 dense 向量维度 1024
    EMBEDDING_API_URL: Optional[str] = os.getenv("EMBEDDING_API_URL", None)
    EMBEDDING_API_KEY: Optional[str] = os.getenv("EMBEDDING_API_KEY", None)

    # 向量数据库配置 (Qdrant In-Memory 内存模式，无需 Docker 部署)
    # 采用进程内纯内存 (:memory:) 模式，随应用启动即时加载，零外部运维依赖
    QDRANT_LOCATION: str = os.getenv("QDRANT_LOCATION", ":memory:")
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "xx_mall_faq")
    QDRANT_HOST: Optional[str] = os.getenv("QDRANT_HOST", None)
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY", None)

    # 业务决策阈值
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.65"))  # 低于此分流转人工或提示低置信度
    TOP_K_RETRIEVAL: int = int(os.getenv("TOP_K_RETRIEVAL", "3"))

settings = Settings()
