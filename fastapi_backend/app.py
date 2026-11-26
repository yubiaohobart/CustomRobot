"""
FastAPI 主服务启动入口 (Main Application Entrypoint)
基于 FastAPI + LangGraph + Qdrant + BGE-M3 + DeepSeek 构建
"""

import asyncio
import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# 将当前目录加入系统路径以支持子包清晰导入
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from config import settings
from api.routes import router as api_router
from api.websocket_routes import ws_router
from core.qdrant_store import qdrant_store
from core.embedding import bge_m3_engine
from core.llm import deepseek_client
from core.session_lock import close_session_lock_redis
from core.database import dispose_engine
from core.logger import log, cprint, LogColor
from services.storage_service import storage_service
from services.websocket_manager import ws_manager
from workflow.graph import init_postgres_checkpointer, close_postgres_checkpointer

async def _ws_prune_loop() -> None:
    """周期性清理超时未活跃的僵尸 WebSocket 连接"""
    while True:
        await asyncio.sleep(60)
        try:
            await ws_manager.prune_stale_connections(max_idle_seconds=120.0)
        except Exception as exc:
            log.warning(f"WebSocket 僵尸连接清理异常: {exc}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务生命周期管理：服务启动时初始化 PostgreSQL 业务库、Qdrant 知识库与 LangGraph Checkpointer"""
    cprint.banner(
        f"{settings.APP_NAME} v{settings.VERSION} 正在启动...",
        f"FastAPI + LangGraph + Qdrant (BGE-M3) + DeepSeek 智能客服中枢"
    )

    api_key_status = (
        cprint.colorize(f"已配置 ({settings.DEEPSEEK_API_KEY[:4]}...)", LogColor.BRIGHT_GREEN)
        if settings.DEEPSEEK_API_KEY
        else cprint.colorize("未配置 (自动使用智能规则兜底)", LogColor.BRIGHT_YELLOW)
    )
    if settings.QDRANT_HOST:
        qdrant_mode = f"Qdrant 远程服务 ({settings.QDRANT_HOST}:{settings.QDRANT_PORT})"
    elif settings.QDRANT_LOCATION == ":memory:":
        qdrant_mode = "Qdrant 纯内存模式 (In-Memory :memory:)"
    else:
        qdrant_mode = f"Qdrant 本地持久化 ({settings.QDRANT_LOCATION})"

    cprint.startup_item("大语言模型 (LLM):", f"DeepSeek ({settings.DEEPSEEK_MODEL})", LogColor.BRIGHT_CYAN, f"[API Key: {api_key_status}]")
    cprint.startup_item(
        "向量模型 (Embed):",
        f"Ollama ({settings.OLLAMA_EMBED_MODEL}, {settings.OLLAMA_BASE_URL}, {settings.EMBEDDING_DIM}维)",
        LogColor.BRIGHT_BLUE,
    )
    cprint.startup_item("向量数据库 (VDB):", f"{qdrant_mode} · Hybrid(Dense+Sparse RRF)", LogColor.BRIGHT_GREEN)
    cprint.startup_item("默认知识库:", "XX商城售后服务与退换货政策（2026版）", LogColor.WHITE)
    cprint.divider("=", 68, LogColor.BRIGHT_CYAN)

    # 初始化 PostgreSQL 业务表结构与初始种子数据
    storage_service.init_database()

    # 确保 Qdrant 集合就绪并执行内容哈希增量同步
    await asyncio.to_thread(qdrant_store.init_collection_with_faq)
    cprint.success("Qdrant 向量知识库初始化完成，FAQ 语义切片已同步！")

    # 初始化 LangGraph PostgreSQL Checkpointer（自动建表并绑定连接池）
    await init_postgres_checkpointer()
    cprint.success("LangGraph PostgreSQL Checkpointer 已就绪（状态与中断断点固化存储）！")

    cprint(f"🌐 服务监听地址: http://{settings.FASTAPI_HOST}:{settings.FASTAPI_PORT}", LogColor.BRIGHT_CYAN)
    cprint(f"📖 Swagger 交互文档: http://{settings.FASTAPI_HOST}:{settings.FASTAPI_PORT}/docs\n", LogColor.BRIGHT_CYAN)
    
    prune_task = asyncio.create_task(_ws_prune_loop())

    try:
        yield
    finally:
        prune_task.cancel()
        try:
            await prune_task
        except asyncio.CancelledError:
            pass
        cprint.warning("服务正常关闭中，释放连接池与 HTTP 客户端资源...")
        await deepseek_client.close()
        await close_session_lock_redis()
        bge_m3_engine.close()
        dispose_engine()
        await close_postgres_checkpointer()

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

# 挂载 API 业务路由与独立 WebSocket 实时双向通信路由
app.include_router(api_router)
app.include_router(ws_router)

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
            "checkpointer": "PostgreSQL (AsyncPostgresSaver)",
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
