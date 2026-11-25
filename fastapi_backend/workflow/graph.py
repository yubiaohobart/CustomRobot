"""
LangGraph 状态图组装与编译 (Graph Pipeline Assembly - PostgreSQL 持久化 Checkpointer 版)
采用 AsyncPostgresSaver + psycopg_pool.AsyncConnectionPool 将断点现场与历史状态固化到 PostgreSQL。
"""

import asyncio
from typing import Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from config import settings
from core.logger import cprint, LogColor
from .state import AgentState, InputState, OutputState
from .nodes import (
    analyze_query_node,
    order_query_node,
    order_refund_node,
    qdrant_retrieve_node,
    deepseek_generate_node,
    human_escalation_node,
    router_after_analysis,
    router_after_order_query,
    router_after_retrieval
)

# 构建客服问答状态机（采用输入输出模式分离的 AgentState）
builder = StateGraph(AgentState, input_schema=InputState, output_schema=OutputState)

# 注册所有执行节点
builder.add_node("analyze_query", analyze_query_node)
builder.add_node("order_query", order_query_node)
builder.add_node("order_refund", order_refund_node)
builder.add_node("qdrant_retrieve", qdrant_retrieve_node)
builder.add_node("deepseek_generate", deepseek_generate_node)
builder.add_node("human_escalation", human_escalation_node)

# 定义状态流转
builder.add_edge(START, "analyze_query")

# 节点 1 后的条件分支 (意图分析 -> 人工转接 / 订单查询 / 知识检索)
builder.add_conditional_edges(
    "analyze_query",
    router_after_analysis,
    {
        "human_escalation": "human_escalation",
        "order_query": "order_query",
        "qdrant_retrieve": "qdrant_retrieve"
    }
)

# 订单查询完成后的智能条件路由：
# - 若涉及退款意图或二次确认：进入 order_refund 节点
# - 若仅查询物流/订单明细：直接跳过退款节点，直奔 qdrant_retrieve 节点
builder.add_conditional_edges(
    "order_query",
    router_after_order_query,
    {
        "order_refund": "order_refund",
        "qdrant_retrieve": "qdrant_retrieve"
    }
)
builder.add_edge("order_refund", END)

# 节点 2 后的条件分支 (检索 -> 人工升级 / DeepSeek 生成)
builder.add_conditional_edges(
    "qdrant_retrieve",
    router_after_retrieval,
    {
        "human_escalation": "human_escalation",
        "deepseek_generate": "deepseek_generate"
    }
)

# 终点连接
builder.add_edge("deepseek_generate", END)
builder.add_edge("human_escalation", END)

# PostgreSQL 持久化 Checkpointer 与编译后状态图（在 FastAPI lifespan 或首次调用时异步初始化）
_pg_pool: Optional[AsyncConnectionPool] = None
postgres_saver: Optional[AsyncPostgresSaver] = None
customer_service_graph = None
_init_lock: Optional[asyncio.Lock] = None


def get_checkpoint_db_uri() -> str:
    """将 SQLAlchemy 连接串规范化为 psycopg3/libpq 标准 postgresql:// URI"""
    uri = settings.DATABASE_URL.strip()
    if uri.startswith("postgresql+"):
        return "postgresql://" + uri.split("://", 1)[1]
    if uri.startswith("postgres://"):
        return "postgresql://" + uri.split("://", 1)[1]
    return uri


async def init_postgres_checkpointer():
    """初始化 AsyncConnectionPool、建表 (setup) 并绑定 AsyncPostgresSaver 编译状态图"""
    global _pg_pool, postgres_saver, customer_service_graph, _init_lock

    if customer_service_graph is not None:
        return customer_service_graph

    if _init_lock is None:
        _init_lock = asyncio.Lock()

    async with _init_lock:
        if customer_service_graph is not None:
            return customer_service_graph

        db_uri = get_checkpoint_db_uri()
        target_label = db_uri.split("@")[-1] if "@" in db_uri else db_uri
        pool = AsyncConnectionPool(
            conninfo=db_uri,
            min_size=1,
            max_size=max(2, settings.DB_POOL_SIZE),
            open=False,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
        )
        try:
            await pool.open(wait=True, timeout=15.0)
            saver = AsyncPostgresSaver(pool)
            await saver.setup()

            _pg_pool = pool
            postgres_saver = saver
            customer_service_graph = builder.compile(checkpointer=saver)
            cprint(
                f"[LangGraph] AsyncPostgresSaver 初始化成功，Checkpointer 已持久化至 PostgreSQL ({target_label})",
                LogColor.GREEN,
            )
            return customer_service_graph
        except Exception as e:
            await pool.close()
            _pg_pool = None
            postgres_saver = None
            customer_service_graph = None
            cprint.error(f"[LangGraph] PostgreSQL Checkpointer 初始化失败 ({target_label}): {e}")
            raise


async def get_customer_service_graph():
    """获取已绑定 PostgreSQL Checkpointer 的编译态状态图（未初始化时按需初始化）"""
    if customer_service_graph is not None:
        return customer_service_graph
    return await init_postgres_checkpointer()


async def close_postgres_checkpointer() -> None:
    """应用关闭时释放 PostgreSQL Checkpointer 异步连接池"""
    global _pg_pool, postgres_saver, customer_service_graph
    if _pg_pool is not None:
        await _pg_pool.close()
    _pg_pool = None
    postgres_saver = None
    customer_service_graph = None
