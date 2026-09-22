"""
FastAPI 主服务启动入口 (Main Application Entrypoint)
基于 FastAPI + LangGraph + Qdrant + BGE-M3 + DeepSeek 构建
"""

import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# 将当前目录加入系统路径以支持子包清晰导入
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from config import settings
from api.routes import router as api_router
from core.qdrant_store import qdrant_store

@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务生命周期管理：服务启动时初始化 Qdrant 知识库"""
    print("\n" + "=" * 65)
    print(f"🚀 {settings.APP_NAME} v{settings.VERSION} 正在启动...")
    print(f"🔹 大语言模型 (LLM):       DeepSeek ({settings.DEEPSEEK_MODEL})")
    print(f"🔹 向量模型 (Embedding):  本地 Ollama (模型: {settings.OLLAMA_EMBED_MODEL}, 地址: {settings.OLLAMA_BASE_URL}, 维度: {settings.EMBEDDING_DIM})")
    print(f"🔹 向量数据库 (Vector DB): Qdrant 纯内存模式 (In-Memory :memory:，无需 Docker 部署)")
    print(f"🔹 默认知识库:             XX商城售后服务与退换货政策（2026版）")
    print("=" * 65)
    
    # 确保 Qdrant 集合就绪
    qdrant_store.init_collection_with_faq()
    print("✅ Qdrant 向量知识库初始化完成，FAQ 语义切片已注入！")
    print(f"🌐 服务监听地址: http://{settings.FASTAPI_HOST}:{settings.FASTAPI_PORT}")
    print(f"📖 Swagger 交互文档: http://{settings.FASTAPI_HOST}:{settings.FASTAPI_PORT}/docs\n")
    
    yield
    print("\n🛑 服务正常关闭中...")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="基于 FastAPI + LangGraph + Qdrant (BGE-M3) + DeepSeek 的现代化智能客服与人机协同中枢",
    lifespan=lifespan
)

# 配置全局跨域支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载 API 业务路由
app.include_router(api_router)

@app.get("/")
async def root_index():
    return {
        "message": f"欢迎使用 {settings.APP_NAME}",
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/api/health",
        "tech_stack": {
            "web_framework": "FastAPI",
            "workflow_orchestrator": "LangGraph",
            "vector_database": "Qdrant",
            "embedding_engine": f"Local Ollama ({settings.OLLAMA_EMBED_MODEL})",
            "ollama_endpoint": settings.OLLAMA_BASE_URL,
            "large_language_model": "DeepSeek"
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=settings.FASTAPI_HOST,
        port=settings.FASTAPI_PORT,
        reload=settings.DEBUG
    )
