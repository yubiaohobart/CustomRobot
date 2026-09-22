"""
LangGraph 状态图组装与编译 (Graph Pipeline Assembly)
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from models.state import AgentState
from .nodes import (
    analyze_query_node,
    qdrant_retrieve_node,
    memory_synthesis_node,
    deepseek_generate_node,
    human_escalation_node,
    router_after_analysis,
    router_after_retrieval
)

# 内存检查点状态管理器
memory_saver = MemorySaver()

# 构建客服问答状态机
builder = StateGraph(AgentState)

# 注册所有执行节点
builder.add_node("analyze_query", analyze_query_node)
builder.add_node("qdrant_retrieve", qdrant_retrieve_node)
builder.add_node("memory_synthesis", memory_synthesis_node)
builder.add_node("deepseek_generate", deepseek_generate_node)
builder.add_node("human_escalation", human_escalation_node)

# 定义状态流转
builder.add_edge(START, "analyze_query")

# 节点 1 后的条件分支
builder.add_conditional_edges(
    "analyze_query",
    router_after_analysis,
    {
        "human_escalation": "human_escalation",
        "qdrant_retrieve": "qdrant_retrieve"
    }
)

# 节点 2 后的条件分支
builder.add_conditional_edges(
    "qdrant_retrieve",
    router_after_retrieval,
    {
        "human_escalation": "human_escalation",
        "memory_synthesis": "memory_synthesis"
    }
)

# 正常生成路径
builder.add_edge("memory_synthesis", "deepseek_generate")
builder.add_edge("deepseek_generate", END)
builder.add_edge("human_escalation", END)

# 编译为可调用的 Graph 应用
customer_service_graph = builder.compile(checkpointer=memory_saver)
