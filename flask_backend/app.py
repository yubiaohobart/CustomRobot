"""
IntelliServe - Flask + LangGraph 智能客服系统后端服务
集成了向量知识库检索 (RAG)、会话记忆管理 (MemorySaver)、实时监控大盘与无缝人工介入/转接接口
"""

import os
import time
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
from graph_pipeline import customer_service_graph, memory_store
from vector_store import VectorKnowledgeStore
from memory_manager import PythonMemoryManager

app = Flask(__name__)
CORS(app)

# 1. 初始化核心模块
kb_store = VectorKnowledgeStore()
mem_manager = PythonMemoryManager()

MONITORING_METRICS = {
    "total_requests": 0,
    "ai_resolved": 0,
    "human_escalated": 0,
    "total_latency_ms": 0
}

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "service": "IntelliServe Flask + LangGraph Engine",
        "version": "2.0.0",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })

# ==================== 会话与对话接口 ====================

@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    """获取所有客服会话列表"""
    sessions = mem_manager.get_all_sessions()
    return jsonify({"sessions": sessions})

@app.route("/api/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    """获取指定会话详情"""
    session = mem_manager.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    return jsonify({"session": session})

@app.route("/api/chat", methods=["POST"])
def chat():
    """客户对话接口：由 LangGraph 状态图驱动检索、记忆与智能生成"""
    start_time = time.time()
    data = request.json or {}
    session_id = data.get("sessionId", "session_user_001")
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "message is required"}), 400

    session = mem_manager.get_or_create_session(session_id)

    # 检查是否已处于人工坐席接管状态
    if session.get("status") == "HUMAN_INTERVENED":
        reply = f"【人工客服服务中】值班坐席 {session.get('assignedAgent', '客服主管')} 正在为您回复..."
        mem_manager.add_message(session_id, "user", user_message)
        mem_manager.add_message(session_id, "human_agent", reply)
        return jsonify({
            "sessionId": session_id,
            "reply": reply,
            "session": mem_manager.get_session(session_id),
            "escalatedToHuman": True,
            "status": "HUMAN_INTERVENED"
        })

    # 记录用户提问至会话记忆
    mem_manager.add_message(session_id, "user", user_message)

    # 组装 LangGraph 执行输入
    initial_state = {
        "session_id": session_id,
        "user_message": user_message,
        "step_trace": [],
        "user_profile": session.get("customerProfile", {}),
        "summary_memory": session.get("summaryMemory", "")
    }

    # 执行 LangGraph 编排计算
    config = {"configurable": {"thread_id": session_id}}
    result_state = customer_service_graph.invoke(initial_state, config=config)

    latency_ms = int((time.time() - start_time) * 1000)
    MONITORING_METRICS["total_requests"] += 1
    MONITORING_METRICS["total_latency_ms"] += latency_ms

    ai_reply = result_state.get("generated_response", "非常抱歉，智能客服当前遇到网络波动，已为您安排人工接入。")
    confidence = result_state.get("top_similarity_score", 0.88)
    needs_escalate = result_state.get("escalated_to_human", False)
    escalate_reason = result_state.get("escalation_reason", "")

    # 更新记忆与 AI 回复
    mem_manager.add_message(
        session_id, 
        "assistant", 
        ai_reply, 
        confidence_score=confidence,
        references=result_state.get("retrieved_docs", [])
    )

    if needs_escalate:
        MONITORING_METRICS["human_escalated"] += 1
        mem_manager.update_status(session_id, "NEEDS_INTERVENTION", reason=escalate_reason)
    else:
        MONITORING_METRICS["ai_resolved"] += 1

    # 触发检查点保存
    mem_manager.record_checkpoint(session_id, "generate_agent_response", {
        "latency_ms": latency_ms,
        "confidence": confidence,
        "intent": result_state.get("intent")
    })

    return jsonify({
        "sessionId": session_id,
        "reply": ai_reply,
        "confidenceScore": confidence,
        "sentiment": result_state.get("sentiment", "neutral"),
        "intent": result_state.get("intent", "常规咨询"),
        "escalatedToHuman": needs_escalate,
        "escalationReason": escalate_reason,
        "references": result_state.get("retrieved_docs", []),
        "latencyMs": latency_ms,
        "session": mem_manager.get_session(session_id)
    })

# ==================== 无缝人工介入与转接接口 ====================

@app.route("/api/agents", methods=["GET"])
def get_agents():
    """获取所有在岗值班人工坐席及其专长领域与负荷"""
    agents = mem_manager.get_available_agents()
    return jsonify({"agents": agents})

@app.route("/api/transfer-logs", methods=["GET"])
def get_transfer_logs():
    """获取全系统人工转接流水审计日志"""
    logs = mem_manager.get_transfer_logs()
    return jsonify({"transferLogs": logs})

@app.route("/api/sessions/<session_id>/transfer", methods=["POST"])
def transfer_session(session_id):
    """
    无缝转接接口：当智能客服无法回答或用户要求时，
    将完整上下文（用户问题、客服回答、会话记忆）转接给指定坐席并生成流水审计
    """
    data = request.json or {}
    target_agent_id = data.get("targetAgentId", "agent_101")
    reason = data.get("reason", "客户主动要求人工介入")
    operator_note = data.get("operatorNote", "")
    trigger_type = data.get("triggerType", "user_requested")

    transfer_log, session = mem_manager.transfer_session(
        session_id=session_id,
        target_agent_id=target_agent_id,
        reason=reason,
        operator_note=operator_note,
        trigger_type=trigger_type
    )

    if not session:
        return jsonify({"error": "Session not found"}), 404

    return jsonify({
        "success": True,
        "transferLog": transfer_log,
        "session": session
    })

@app.route("/api/sessions/<session_id>/intervene", methods=["POST"])
def intervene_session(session_id):
    """人工坐席接管或交还 AI 接口"""
    data = request.json or {}
    action = data.get("action", "takeover") # 'takeover' or 'release'
    agent_name = data.get("agentName", "人工客服坐席")

    session = mem_manager.handle_intervention(session_id, action, agent_name)
    return jsonify({"success": True, "session": session})

@app.route("/api/sessions/<session_id>/human-message", methods=["POST"])
def send_human_message(session_id):
    """人工坐席下发消息接口：写入会话记录并同步 LangGraph 记忆"""
    data = request.json or {}
    content = data.get("content", "").strip()
    agent_name = data.get("agentName", "人工坐席")

    if not content:
        return jsonify({"error": "content is required"}), 400

    session = mem_manager.add_message(session_id, "human_agent", content)
    return jsonify({"success": True, "session": session})

# ==================== 监控指标与知识库检索 ====================

@app.route("/api/metrics", methods=["GET"])
def get_metrics():
    """实时监控大盘指标"""
    return jsonify(mem_manager.get_metrics())

@app.route("/api/knowledge/search", methods=["POST"])
def search_knowledge():
    """向量知识库即时相似度检索接口"""
    data = request.json or {}
    query = data.get("query", "")
    top_k = int(data.get("topK", 3))
    results = kb_store.similarity_search(query, k=top_k)
    return jsonify({"query": query, "results": results})

if __name__ == "__main__":
    port = int(os.environ.get("FLASK_PORT", 5000))
    print(f"Flask + LangGraph Intelligent Customer Service Server starting on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
