"""
全局系统配置中心 (Configuration Center)
管理 DeepSeek 大模型、BGE-M3 向量模型、Qdrant 向量数据库与服务端口
"""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

from dotenv import load_dotenv

# 自动寻找并加载 .env 文件 (支持 fastapi_backend 目录内以及项目根目录的 .env)
current_dir = Path(__file__).resolve().parent
for env_path in (current_dir / ".env", current_dir.parent / ".env", Path.cwd() / ".env"):
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)

class Settings(BaseModel):
    # 服务端基础配置
    APP_NAME: str = "IntelliServe 智能客服系统"
    VERSION: str = "3.0.0"
    FASTAPI_HOST: str = os.getenv("FASTAPI_HOST", "0.0.0.0")
    # 默认 8000 端口（避免 macOS 默认隔空播放 AirPlay Receiver 占用 5000 端口导致 502 Bad Gateway）
    FASTAPI_PORT: int = int(os.getenv("FASTAPI_PORT", os.getenv("PORT", "8000")))
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

    # PostgreSQL 关系型数据库与 SQLAlchemy ORM 配置 (统一使用 Psycopg 3 驱动)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        os.getenv("POSTGRES_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/intelliserve")
    )
    DB_ECHO: bool = os.getenv("DB_ECHO", "false").lower() == "true"
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))

    # 业务决策阈值与模型超时配置
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.65"))  # 低于此分流转人工或提示低置信度
    TOP_K_RETRIEVAL: int = int(os.getenv("TOP_K_RETRIEVAL", "3"))
    AUTO_REFUND_LIMIT_YUAN: float = float(os.getenv("AUTO_REFUND_LIMIT_YUAN", "3.00"))  # 退款自动秒退与人工审核分界阈值(元)
    LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "45.0"))

    @property
    def auto_refund_limit_cents(self) -> int:
        """退款自动秒退阈值（单位：分，避免浮点精度误差）"""
        return int(round(self.AUTO_REFUND_LIMIT_YUAN * 100))

    @property
    def auto_refund_limit_text(self) -> str:
        """统一格式化后的退款阈值金额文本（如 '3.00'）"""
        return f"{self.AUTO_REFUND_LIMIT_YUAN:.2f}"


# 跨模块共享业务常量
HUMAN_TAKEOVER_STATUSES = ("HUMAN_INTERVENED", "TRANSFERRED", "TRANSFERRED_TO_HUMAN")
DETERMINISTIC_FLOW_CONFIDENCE = 0.95  # 确定性业务流（挂起确认/退款分流/转人工）默认置信度
PROCESSED_REQUEST_IDS_LIMIT = 20      # 单订单保留的幂等流水号历史上限

# 会话滑动窗口摘要裁剪常量
SUMMARY_USER_SNIPPET_LEN = 60
SUMMARY_REPLY_SNIPPET_LEN = 48
SUMMARY_MAX_SEGMENTS = 8
SUMMARY_MAX_CHARS = 500

settings = Settings()
