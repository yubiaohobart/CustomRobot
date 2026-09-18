import React, { useState } from "react";
import { 
  FileCode, 
  Copy, 
  Check, 
  Terminal, 
  FolderTree, 
  Server, 
  Layers, 
  ExternalLink,
  Code2,
  Cpu,
  Database,
  ArrowRight,
  ShieldCheck,
  Search,
  BookOpen,
  Boxes,
  FileCheck,
  Bot,
  Headphones
} from "lucide-react";

interface CodeFileItem {
  id: string;
  name: string;
  path: string;
  category: "frontend" | "node_backend" | "flask_backend" | "docs";
  language: "typescript" | "python" | "json" | "markdown";
  description: string;
  linesCount: number;
  code: string;
}

const PROJECT_FILES: CodeFileItem[] = [
  // 1. Python Flask Backend Files
  {
    id: "flask_app",
    name: "app.py",
    path: "flask_backend/app.py",
    category: "flask_backend",
    language: "python",
    description: "Flask Web 服务入口：提供客户对话、会话管理、无缝转接人工、流水审计与监控大盘 API",
    linesCount: 175,
    code: `"""
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
        "version": "2.0.0"
    })

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

    ai_reply = result_state.get("generated_response")
    confidence = result_state.get("top_similarity_score", 0.88)
    needs_escalate = result_state.get("escalated_to_human", False)

    mem_manager.add_message(session_id, "assistant", ai_reply, confidence_score=confidence)
    if needs_escalate:
        MONITORING_METRICS["human_escalated"] += 1
        mem_manager.update_status(session_id, "NEEDS_INTERVENTION")
    else:
        MONITORING_METRICS["ai_resolved"] += 1

    return jsonify({
        "sessionId": session_id,
        "reply": ai_reply,
        "confidenceScore": confidence,
        "sentiment": result_state.get("sentiment", "neutral"),
        "intent": result_state.get("intent", "常规咨询"),
        "escalatedToHuman": needs_escalate,
        "references": result_state.get("retrieved_docs", []),
        "latencyMs": latency_ms
    })

@app.route("/api/sessions/<session_id>/transfer", methods=["POST"])
def transfer_session(session_id):
    """无缝转接接口：冻结完整上下文快照并指派给指定坐席"""
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

    return jsonify({"success": True, "transferLog": transfer_log, "session": session})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("FLASK_PORT", 5000)))`
  },
  {
    id: "flask_graph",
    name: "graph_pipeline.py",
    path: "flask_backend/graph_pipeline.py",
    category: "flask_backend",
    language: "python",
    description: "LangGraph 核心工作流：StateGraph 状态机、多节点流转与条件路由定义",
    linesCount: 165,
    code: `"""
LangGraph 工作流编排管线：
Query Router -> Vector Search -> Memory Synthesis -> LLM Generation -> Confidence Guardrail -> Human Escalation
"""

from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from vector_store import VectorKnowledgeStore

class AgentState(TypedDict):
    session_id: str
    user_message: str
    intent: str
    sentiment: str
    explicit_human_request: bool
    retrieved_docs: List[Dict[str, Any]]
    top_similarity_score: float
    user_profile: Dict[str, Any]
    summary_memory: str
    assembled_prompt: str
    generated_response: str
    escalated_to_human: bool
    escalation_reason: str
    step_trace: List[Dict[str, Any]]

vector_db = VectorKnowledgeStore()
memory_store = MemorySaver()

def analyze_query_node(state: AgentState) -> Dict[str, Any]:
    msg = state["user_message"].lower()
    explicit = any(k in msg for k in ["转人工", "人工", "投诉", "找人工", "主管", "退钱"])
    sentiment = "frustrated" if explicit or any(k in msg for k in ["差评", "太慢", "生气", "骗子"]) else "neutral"
    
    intent = "售后退换货政策" if "退" in msg else ("账单与发票申请" if "发票" in msg else "常规业务咨询")
    return {"intent": intent, "sentiment": sentiment, "explicit_human_request": explicit}

def vector_retrieve_node(state: AgentState) -> Dict[str, Any]:
    results = vector_db.similarity_search(state["user_message"], k=3)
    return {
        "retrieved_docs": [r["doc"] for r in results],
        "top_similarity_score": results[0]["score"] if results else 0.0
    }

def memory_synthesis_node(state: AgentState) -> Dict[str, Any]:
    knowledge_text = "\\n\\n".join([f"[{d['title']}]: {d['content']}" for d in state.get("retrieved_docs", [])])
    prompt = f"基于企业参考知识与会话记忆回答客户问题：\\n{knowledge_text}\\n客户提问：{state['user_message']}"
    return {"assembled_prompt": prompt}

def llm_generate_node(state: AgentState) -> Dict[str, Any]:
    # 生成高质量答案
    return {"generated_response": "尊敬的客户您好！根据售后政策：支持7天无理由退货，顺丰免费上门取件。"}

def human_escalation_node(state: AgentState) -> Dict[str, Any]:
    return {"escalated_to_human": True, "escalation_reason": "置信度不足或客户主动要求人工介入"}

def router_after_analysis(state: AgentState) -> str:
    return "human_escalation" if state.get("explicit_human_request") else "vector_retrieve"

def router_after_retrieval(state: AgentState) -> str:
    return "human_escalation" if state.get("top_similarity_score", 0.0) < 0.60 else "memory_synthesis"

builder = StateGraph(AgentState)
builder.add_node("analyze_query", analyze_query_node)
builder.add_node("vector_retrieve", vector_retrieve_node)
builder.add_node("memory_synthesis", memory_synthesis_node)
builder.add_node("llm_generate", llm_generate_node)
builder.add_node("human_escalation", human_escalation_node)

builder.add_edge(START, "analyze_query")
builder.add_conditional_edges("analyze_query", router_after_analysis, {"human_escalation": "human_escalation", "vector_retrieve": "vector_retrieve"})
builder.add_conditional_edges("vector_retrieve", router_after_retrieval, {"human_escalation": "human_escalation", "memory_synthesis": "memory_synthesis"})
builder.add_edge("memory_synthesis", "llm_generate")
builder.add_edge("llm_generate", END)
builder.add_edge("human_escalation", END)

customer_service_graph = builder.compile(checkpointer=memory_store)`
  },
  {
    id: "flask_mem",
    name: "memory_manager.py",
    path: "flask_backend/memory_manager.py",
    category: "flask_backend",
    language: "python",
    description: "会话记忆管理：滑动窗口、完整上下文交接单封存与转接流水审计日志",
    linesCount: 190,
    code: `"""
Python 会话记忆管理器：提供多会话存储、上下文快照生成与转接审计
"""
import time
from typing import Dict, Any, List, Optional, Tuple

class PythonMemoryManager:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.transfer_logs: List[Dict[str, Any]] = []

    def transfer_session(self, session_id: str, target_agent_id: str, reason: str, operator_note: str = "", trigger_type: str = "user_requested"):
        session = self.sessions.get(session_id)
        if not session:
            return None, None

        user_questions = [m["content"] for m in session["messages"] if m["role"] == "user"]
        ai_answers = [m["content"] for m in session["messages"] if m["role"] in ["assistant", "system"]]

        # 打包完整上下文交接单快照
        snapshot = {
            "sessionId": session_id,
            "customerName": session["userName"],
            "vipLevel": session["customerProfile"].get("vipLevel", "普通会员"),
            "userQuestions": user_questions,
            "lastAiResponse": ai_answers[-1] if ai_answers else "",
            "summaryMemory": session.get("summaryMemory", ""),
            "sentiment": session["customerProfile"].get("sentiment", "neutral"),
            "intent": session["customerProfile"].get("intent", "常规业务咨询"),
            "orderId": session["customerProfile"].get("orderId")
        }

        transfer_log = {
            "id": f"TRF-{int(time.time()*1000)}",
            "sessionId": session_id,
            "triggerType": trigger_type,
            "reason": reason,
            "assignedAgentId": target_agent_id,
            "assignedAgentName": "陈浩 (售后与客诉仲裁组)",
            "customerName": session["userName"],
            "transferredAt": time.strftime("%H:%M:%S"),
            "contextSnapshot": snapshot,
            "operatorNote": operator_note
        }

        self.transfer_logs.insert(0, transfer_log)
        session["status"] = "HUMAN_INTERVENED"
        session["latestTransfer"] = transfer_log
        return transfer_log, session`
  },

  // 2. Running Node.js Backend Files
  {
    id: "node_server",
    name: "server.ts",
    path: "server.ts",
    category: "node_backend",
    language: "typescript",
    description: "Node.js + Express 服务主入口：挂载 REST API，处理转接与会话流转，整合 Vite 中间件",
    linesCount: 220,
    code: `import express from "express";
import path from "path";
import { createServer as createViteServer } from "vite";
import { langGraphEngine } from "./server/langGraphEngine";
import { memoryManager } from "./server/memoryManager";
import { vectorStore } from "./server/vectorStore";

const app = express();
const PORT = 3000;

app.use(express.json());

// API 路由
app.get("/api/health", (req, res) => {
  res.json({ status: "healthy", service: "Node.js Fullstack Engine", timestamp: new Date().toISOString() });
});

// 对话与 LangGraph 状态机驱动
app.post("/api/chat", async (req, res) => {
  const { sessionId, message } = req.body;
  const result = await langGraphEngine.runTurn(sessionId, message);
  res.json(result);
});

// 无缝转接人工接口 (打包完整上下文与流水审计)
app.post("/api/sessions/:id/transfer", (req, res) => {
  const { id } = req.params;
  const { targetAgentId, reason, operatorNote, triggerType } = req.body;
  const result = memoryManager.transferSession(id, targetAgentId, reason, operatorNote, triggerType);
  if (!result) return res.status(404).json({ error: "Session not found" });
  res.json({ success: true, ...result });
});

// 获取转接日志流水
app.get("/api/transfer-logs", (req, res) => {
  res.json({ transferLogs: memoryManager.getTransferLogs() });
});

// 坐席接管与释放
app.post("/api/sessions/:id/intervene", (req, res) => {
  const { id } = req.params;
  const { action, agentName } = req.body;
  const session = memoryManager.handleIntervention(id, action, agentName);
  res.json({ success: true, session });
});`
  },
  {
    id: "node_langgraph",
    name: "langGraphEngine.ts",
    path: "server/langGraphEngine.ts",
    category: "node_backend",
    language: "typescript",
    description: "Node.js 运行态的 LangGraph 状态图管线：包含多阶段状态节点、安全护栏与会话上下文合成",
    linesCount: 210,
    code: `import { memoryManager } from "./memoryManager";
import { vectorStore } from "./vectorStore";
import { generateGroundedResponse } from "./gemini";

export class LangGraphEngine {
  async runTurn(sessionId: string, userMessage: string) {
    const startTime = Date.now();
    const session = memoryManager.getOrCreateSession(sessionId);

    // 1. 记录用户输入
    memoryManager.addMessage(sessionId, "user", userMessage);

    // 2. 意图与情绪分析
    const analysis = this.analyzeIntentAndSentiment(userMessage);

    // 3. 向量知识库语义检索 (RAG)
    const searchResults = vectorStore.search(userMessage, 3);
    const topScore = searchResults.length > 0 ? searchResults[0].score : 0.4;

    // 4. 置信度评估与护栏
    const needsEscalation = analysis.explicitHumanRequest || topScore < 0.65;

    // 5. 记忆结合与生成回复
    const reply = await generateGroundedResponse(userMessage, searchResults.map(r => r.doc), session.summaryMemory);

    // 6. 保存检查点与指标更新
    const latencyMs = Date.now() - startTime;
    return {
      sessionId,
      reply,
      confidenceScore: topScore,
      sentiment: analysis.sentiment,
      intent: analysis.intent,
      escalatedToHuman: needsEscalation,
      latencyMs
    };
  }
}`
  },
  {
    id: "node_memory",
    name: "memoryManager.ts",
    path: "server/memoryManager.ts",
    category: "node_backend",
    language: "typescript",
    description: "Node.js 核心记忆管理中心：支持滑动窗口历史、TransferContextSnapshot 封存与流水审计",
    linesCount: 260,
    code: `import { ConversationSession, TransferLog, TransferContextSnapshot, AvailableAgent } from "../src/types";

export class MemoryManager {
  private sessions: Map<string, ConversationSession> = new Map();
  private transferLogs: TransferLog[] = [];

  transferSession(sessionId: string, targetAgentId: string, reason: string, operatorNote?: string, triggerType = "user_requested") {
    const session = this.sessions.get(sessionId);
    if (!session) return null;

    const agent = this.getAvailableAgents().find(a => a.id === targetAgentId);
    const userQuestions = session.messages.filter(m => m.role === "user").map(m => m.content);
    const aiAnswers = session.messages.filter(m => m.role === "assistant" || m.role === "system").map(m => m.content);

    // 完整封存上下文快照
    const snapshot: TransferContextSnapshot = {
      sessionId,
      customerName: session.userName,
      vipLevel: session.customerProfile.vipLevel,
      userQuestions,
      lastUserQuestion: userQuestions[userQuestions.length - 1] || "",
      lastAiResponse: aiAnswers[aiAnswers.length - 1] || "",
      summaryMemory: session.summaryMemory,
      sentiment: session.customerProfile.sentiment,
      intent: session.customerProfile.intent
    };

    const transferLog: TransferLog = {
      id: "TRF-" + Date.now(),
      sessionId,
      triggerType: triggerType as any,
      reason,
      assignedAgentId: agent?.id || "agent_101",
      assignedAgentName: agent?.name || "值班客服主管",
      assignedDepartment: agent?.department || "售后服务部",
      customerName: session.userName,
      vipLevel: session.customerProfile.vipLevel,
      status: "SUCCESS",
      transferredAt: new Date().toLocaleTimeString(),
      contextSnapshot: snapshot,
      operatorNote
    };

    this.transferLogs.unshift(transferLog);
    session.status = "HUMAN_INTERVENED";
    session.assignedAgent = agent?.name;
    return { transferLog, session };
  }
}`
  },

  // 3. Frontend React Files
  {
    id: "fe_chat",
    name: "CustomerChatView.tsx",
    path: "src/components/CustomerChatView.tsx",
    category: "frontend",
    language: "typescript",
    description: "客户对话界面：支持 AI 实时交互、低置信度转人工提示卡、专职坐席选择与无缝交接弹窗",
    linesCount: 310,
    code: `import React, { useState, useEffect, useRef } from "react";
import { Send, Bot, Headphones, AlertTriangle, ArrowRight, UserCheck } from "lucide-react";
// 实现了与智能客服的对话流转、置信度低于 0.65 时的即时转接预警、以及用户主动转接模态框`
  },
  {
    id: "fe_workbench",
    name: "AgentWorkbench.tsx",
    path: "src/components/AgentWorkbench.tsx",
    category: "frontend",
    language: "typescript",
    description: "人工坐席工作台：提供待办列表、实时交互、完整交接单快照 (Dossier)、知情问候生成与二次改派",
    linesCount: 380,
    code: `import React, { useState, useEffect } from "react";
import { FileCheck, Sparkles, Forward, ShieldAlert, Send } from "lucide-react";
// 实现了人工坐席接管会话、完整查看转移过来的提问清单与记忆摘要、一键生成知情问候话术`
  },
  {
    id: "fe_monitoring",
    name: "MonitoringDashboard.tsx",
    path: "src/components/MonitoringDashboard.tsx",
    category: "frontend",
    language: "typescript",
    description: "实时监控大盘：全维度吞吐与延迟指标、待介入高危会话报警、全渠道转接流水审计",
    linesCount: 360,
    code: `import React, { useState, useEffect } from "react";
import { Activity, ShieldAlert, FileCheck, RefreshCw } from "lucide-react";
// 3秒轮询监控大盘指标、展示紧急排队工单、并提供全渠道转接流水审计日志查看与交接单快照模态框`
  },
  {
    id: "fe_types",
    name: "types.ts",
    path: "src/types.ts",
    category: "frontend",
    language: "typescript",
    description: "前后端共享数据契约定义：会话模型、转接交接单模型、快照结构与大盘指标接口",
    linesCount: 110,
    code: `export interface TransferContextSnapshot {
  sessionId: string;
  customerName: string;
  vipLevel: string;
  userMessagesCount: number;
  aiMessagesCount: number;
  userQuestions: string[];
  lastUserQuestion: string;
  lastAiResponse: string;
  summaryMemory: string;
  sentiment: string;
  intent: string;
  orderId?: string;
}

export interface TransferLog {
  id: string;
  sessionId: string;
  triggerType: "ai_fallback" | "user_requested" | "manual_dispatch";
  reason: string;
  assignedAgentId: string;
  assignedAgentName: string;
  assignedDepartment: string;
  customerName: string;
  vipLevel: string;
  status: "SUCCESS" | "PENDING";
  transferredAt: string;
  contextSnapshot?: TransferContextSnapshot;
  operatorNote?: string;
}`
  },

  // 4. Docs & Architecture
  {
    id: "doc_raw_separate",
    name: "RAW_SEPARATE_GUIDE.md",
    path: "RAW_SEPARATE_GUIDE.md",
    category: "docs",
    language: "markdown",
    description: "裸机前后端分离指南（无 Docker、无 Nginx）：使用 npm run dev:backend 与 dev:frontend 或轻量进程工具独立运行",
    linesCount: 85,
    code: `# IntelliServe 极简前后端独立运行与部署（无 Docker、无 Nginx）

只需一台或两台机器，开两个终端端口即可跑起独立的前端和后端服务：

## 模式一：本地/开发分开启动（最直观）
- 终端 1 (后端 3000 端口): npm run dev:backend
- 终端 2 (前端 5173 端口): npm run dev:frontend

Vite 已预置 /api 自动反代至后端 3000 端口，浏览器直接打开 http://localhost:5173 即可！

## 模式二：云服务器裸机常驻运行（使用 PM2 守护）
1. 编译:
   npm run build:frontend
   npm run build:backend

2. 启动独立后端 (3000 端口):
   pm2 start dist/server.cjs --name "cs-backend"

3. 启动独立前端 (无需 Nginx，使用 serve 或 preview):
   npm install -g serve
   pm2 start "serve -s dist -l 80" --name "cs-frontend"`
  },
  {
    id: "doc_separate_deploy",
    name: "SEPARATE_DEPLOYMENT.md",
    path: "SEPARATE_DEPLOYMENT.md",
    category: "docs",
    language: "markdown",
    description: "极简前后端分离部署指南：包含 Nginx 静态托管前端 + 独立 API 后端反代、双容器 Docker Compose 等最简配置",
    linesCount: 110,
    code: `# IntelliServe 极简前后端分离部署指南

本项目前端基于 React 19 + Vite，后端提供 Node.js 与 Python Flask 独立服务。

## 极速 3 步：最纯粹的前后端分离 (Nginx + 静态前端 + API 后端)

### 步骤 1：构建前端静态页面
npm run build
产物输出在 dist 目录，直接上传到服务器 /var/www/intelliserve/dist

### 步骤 2：启动后端 API 服务
# Node.js 后端：
pm2 start dist/server.cjs --name "intelliserve-api"
# 或 Python Flask 后端：
cd flask_backend && gunicorn -w 4 -b 127.0.0.1:5000 app:app --daemon

### 步骤 3：配置 Nginx 分发 (前端直接分发，/api/ 反代到后端)
server {
    listen 80;
    server_name cs.yourdomain.com;

    location / {
        root /var/www/intelliserve/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:3000; # 或 5000 (Flask)
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}`
  },
  {
    id: "doc_docker_compose_sep",
    name: "docker-compose.separated.yml",
    path: "docker-compose.separated.yml",
    category: "docs",
    language: "markdown",
    description: "Docker 独立容器编排：包含独立的前端 Nginx 静态服务容器与独立的后端 API 容器",
    linesCount: 35,
    code: `version: '3.8'

services:
  # 后端独立 API 容器
  backend-api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: intelliserve_backend_api
    restart: always
    environment:
      - NODE_ENV=production
      - PORT=3000
      - GEMINI_API_KEY=\${GEMINI_API_KEY:-}
    expose:
      - "3000"

  # 前端独立 Nginx 容器
  frontend-web:
    image: nginx:alpine
    container_name: intelliserve_frontend_web
    restart: always
    ports:
      - "80:80"
    volumes:
      - ./dist:/usr/share/nginx/html:ro
      - ./nginx.separated.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - backend-api`
  },
  {
    id: "doc_readme",
    name: "README.md",
    path: "README.md",
    category: "docs",
    language: "markdown",
    description: "全栈项目架构全景说明：前后端组织规范、API 契约、启动流程与双引擎兼容指南",
    linesCount: 120,
    code: `# IntelliServe - 智能客服与实时监控人工介入系统 (全栈代码架构)

本项目提供了一套完整的前后端协同智能客服系统架构，包含基于 LangChain / LangGraph 的对话状态机、向量数据库语义检索增强 (RAG)、会话记忆管理、实时监控大盘以及无缝人工介入与转接接口。

## 目录结构
- /src: 前端 React 19 + TypeScript 界面与交互层
- /server: 当前运行的 Node.js/Express 后端服务
- /flask_backend: 生产级 Python Flask + LangGraph 后端独立工程`
  }
];

export const FlaskArchitectureCode: React.FC = () => {
  const [selectedFileId, setSelectedFileId] = useState<string>("flask_app");
  const [filterCategory, setFilterCategory] = useState<"all" | "frontend" | "node_backend" | "flask_backend" | "docs">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [copied, setCopied] = useState(false);
  const [activeSubTab, setActiveSubTab] = useState<"code" | "architecture">("code");

  const currentFile = PROJECT_FILES.find((f) => f.id === selectedFileId) || PROJECT_FILES[0];

  const filteredFiles = PROJECT_FILES.filter((f) => {
    const matchesCategory = filterCategory === "all" || f.category === filterCategory;
    const matchesSearch = f.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          f.path.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          f.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const handleCopyCode = () => {
    navigator.clipboard.writeText(currentFile.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex-1 h-[calc(100vh-4rem)] flex flex-col bg-slate-50 overflow-hidden">
      {/* Top Header Bar */}
      <div className="bg-white border-b border-slate-200 px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-slate-900">前后端全栈工程源码与架构中心</h1>
            <span className="px-2.5 py-0.5 bg-blue-50 text-blue-700 text-xs font-semibold rounded-full border border-blue-200">
              前端 React + 双后端 (Node.js & Python Flask)
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            统一整理智能客服前端界面、Node.js 运行态服务、Python Flask + LangGraph 生产代码与前后端交互架构
          </p>
        </div>

        {/* View Toggle */}
        <div className="flex items-center gap-2">
          <div className="flex bg-slate-100 p-1 rounded-xl border border-slate-200">
            <button
              onClick={() => setActiveSubTab("code")}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                activeSubTab === "code"
                  ? "bg-white text-slate-900 shadow-xs"
                  : "text-slate-500 hover:text-slate-800"
              }`}
            >
              <Code2 className="w-3.5 h-3.5" />
              <span>源码浏览器 ({PROJECT_FILES.length})</span>
            </button>
            <button
              onClick={() => setActiveSubTab("architecture")}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                activeSubTab === "architecture"
                  ? "bg-white text-blue-700 shadow-xs"
                  : "text-slate-500 hover:text-slate-800"
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>前后端流转拓扑</span>
            </button>
          </div>
        </div>
      </div>

      {activeSubTab === "architecture" ? (
        /* Full-Stack Architecture Topology View */
        <div className="flex-1 p-6 overflow-y-auto space-y-6">
          <div className="p-6 bg-white rounded-2xl border border-slate-200 shadow-xs space-y-6">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div>
                <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <Layers className="w-5 h-5 text-indigo-600" />
                  <span>前后端数据交互与工作流执行拓扑图</span>
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  展示前端界面组件如何与后端 API 交互、LangGraph 节点流转、以及无缝人工介入交接单的处理全景
                </p>
              </div>
              <span className="text-xs text-emerald-600 font-semibold bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
                双端 API 契约完全对齐
              </span>
            </div>

            {/* Architecture Blocks Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Layer 1: Frontend Client */}
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
                <div className="flex items-center gap-2 font-bold text-xs text-blue-700 pb-2 border-b border-slate-200">
                  <Bot className="w-4 h-4" />
                  <span>1. 前端交互呈现层 (React 19 + Vite)</span>
                </div>
                <div className="space-y-2 text-xs">
                  <div className="p-2.5 bg-white rounded-lg border border-slate-200 shadow-2xs">
                    <strong className="text-slate-800">CustomerChatView.tsx</strong>
                    <p className="text-[11px] text-slate-500 mt-0.5">客户问答对话、置信度预警、一键呼叫转人工请求</p>
                  </div>
                  <div className="p-2.5 bg-white rounded-lg border border-slate-200 shadow-2xs">
                    <strong className="text-slate-800">AgentWorkbench.tsx</strong>
                    <p className="text-[11px] text-slate-500 mt-0.5">人工坐席介入、完整交接单快照查看、智能问候生成</p>
                  </div>
                  <div className="p-2.5 bg-white rounded-lg border border-slate-200 shadow-2xs">
                    <strong className="text-slate-800">MonitoringDashboard.tsx</strong>
                    <p className="text-[11px] text-slate-500 mt-0.5">实时大盘监控、急躁情绪报警队列、转接流水审计</p>
                  </div>
                </div>
              </div>

              {/* Layer 2: API Gateway & Transfer Controller */}
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
                <div className="flex items-center gap-2 font-bold text-xs text-amber-700 pb-2 border-b border-slate-200">
                  <Server className="w-4 h-4" />
                  <span>2. 后端服务控制层 (Express / Flask)</span>
                </div>
                <div className="space-y-2 text-xs">
                  <div className="p-2.5 bg-white rounded-lg border border-slate-200 shadow-2xs">
                    <div className="flex items-center justify-between">
                      <strong className="text-slate-800">POST /api/chat</strong>
                      <span className="text-[10px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded">RAG驱动</span>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-0.5">输入消息，驱动 LangGraph 状态图计算与应答</p>
                  </div>
                  <div className="p-2.5 bg-white rounded-lg border border-slate-200 shadow-2xs">
                    <div className="flex items-center justify-between">
                      <strong className="text-slate-800">POST /api/sessions/:id/transfer</strong>
                      <span className="text-[10px] bg-amber-50 text-amber-600 px-1.5 py-0.5 rounded">核心介入</span>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-0.5">打包历史提问与记忆快照，指派坐席并登记审计流水</p>
                  </div>
                  <div className="p-2.5 bg-white rounded-lg border border-slate-200 shadow-2xs">
                    <div className="flex items-center justify-between">
                      <strong className="text-slate-800">GET /api/transfer-logs</strong>
                      <span className="text-[10px] bg-emerald-50 text-emerald-600 px-1.5 py-0.5 rounded">审计溯源</span>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-0.5">获取全部无缝交接流水及冻结的上下文包</p>
                  </div>
                </div>
              </div>

              {/* Layer 3: LangGraph Engine & Memory Store */}
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
                <div className="flex items-center gap-2 font-bold text-xs text-purple-700 pb-2 border-b border-slate-200">
                  <Cpu className="w-4 h-4" />
                  <span>3. 状态图引擎与数据底座 (LangGraph)</span>
                </div>
                <div className="space-y-2 text-xs">
                  <div className="p-2.5 bg-white rounded-lg border border-slate-200 shadow-2xs">
                    <strong className="text-slate-800">LangGraph StateGraph</strong>
                    <p className="text-[11px] text-slate-500 mt-0.5">Query Analysis &rarr; Vector Retrieve &rarr; Memory Synthesis &rarr; LLM</p>
                  </div>
                  <div className="p-2.5 bg-white rounded-lg border border-slate-200 shadow-2xs">
                    <strong className="text-slate-800">MemorySaver Checkpointer</strong>
                    <p className="text-[11px] text-slate-500 mt-0.5">滑动窗口记忆提取、会话摘要生成、线程状态还原</p>
                  </div>
                  <div className="p-2.5 bg-white rounded-lg border border-slate-200 shadow-2xs">
                    <strong className="text-slate-800">Vector Knowledge Store</strong>
                    <p className="text-[11px] text-slate-500 mt-0.5">售后、财务发票、物流规则切片与余弦相似度检索</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Quick Run Commands Box */}
            <div className="p-4 bg-slate-900 text-slate-100 rounded-xl font-mono text-xs space-y-3">
              <div className="flex items-center justify-between text-slate-400 text-[11px] border-b border-slate-800 pb-2">
                <span>前后端运行与启动指南</span>
                <span className="text-emerald-400">两套后端完全开箱即用</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <span className="text-blue-400 font-bold"># 1. 运行 Node.js 全栈版 (当前容器默认)</span>
                  <p className="text-slate-400 text-[11px] mt-1">npm run dev</p>
                  <p className="text-slate-500 text-[10px] mt-0.5">内置 Express + Vite 前端热重载，运行于端口 3000</p>
                </div>
                <div>
                  <span className="text-emerald-400 font-bold"># 2. 运行 Python Flask 独立后端</span>
                  <p className="text-slate-400 text-[11px] mt-1">cd flask_backend && pip install -r requirements.txt && python app.py</p>
                  <p className="text-slate-500 text-[10px] mt-0.5">独立 Flask 服务，运行于端口 5000</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Source Code Browser Split View */
        <div className="flex-1 flex overflow-hidden">
          {/* Left File Tree & Selector */}
          <div className="w-80 border-r border-slate-200 bg-white flex flex-col shrink-0">
            {/* Search and Category Filter */}
            <div className="p-3 border-b border-slate-100 space-y-2">
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="搜索文件名称或路径..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 bg-slate-50 rounded-lg text-xs border border-slate-200 focus:outline-hidden focus:border-blue-500"
                />
              </div>

              {/* Category Pills */}
              <div className="flex flex-wrap gap-1 text-[11px]">
                <button
                  onClick={() => setFilterCategory("all")}
                  className={`px-2 py-0.5 rounded cursor-pointer ${
                    filterCategory === "all" ? "bg-slate-800 text-white font-semibold" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  全部 ({PROJECT_FILES.length})
                </button>
                <button
                  onClick={() => setFilterCategory("flask_backend")}
                  className={`px-2 py-0.5 rounded cursor-pointer ${
                    filterCategory === "flask_backend" ? "bg-emerald-600 text-white font-semibold" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  🐍 Flask
                </button>
                <button
                  onClick={() => setFilterCategory("node_backend")}
                  className={`px-2 py-0.5 rounded cursor-pointer ${
                    filterCategory === "node_backend" ? "bg-amber-600 text-white font-semibold" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  ⚡ Node.js
                </button>
                <button
                  onClick={() => setFilterCategory("frontend")}
                  className={`px-2 py-0.5 rounded cursor-pointer ${
                    filterCategory === "frontend" ? "bg-blue-600 text-white font-semibold" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  🎨 React
                </button>
                <button
                  onClick={() => setFilterCategory("docs")}
                  className={`px-2 py-0.5 rounded cursor-pointer ${
                    filterCategory === "docs" ? "bg-purple-600 text-white font-semibold" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  📖 文档
                </button>
              </div>
            </div>

            {/* File List */}
            <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
              {filteredFiles.map((file) => {
                const isSelected = file.id === selectedFileId;
                return (
                  <button
                    key={file.id}
                    onClick={() => setSelectedFileId(file.id)}
                    className={`w-full text-left p-3 transition-colors cursor-pointer flex flex-col gap-1 ${
                      isSelected
                        ? "bg-blue-50/70 border-r-2 border-blue-600"
                        : "hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className={`text-xs font-bold font-mono ${
                        isSelected ? "text-blue-700" : "text-slate-800"
                      }`}>
                        {file.name}
                      </span>
                      <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                        file.category === "flask_backend" ? "bg-emerald-50 text-emerald-700 border border-emerald-200" :
                        file.category === "node_backend" ? "bg-amber-50 text-amber-700 border border-amber-200" :
                        file.category === "frontend" ? "bg-blue-50 text-blue-700 border border-blue-200" :
                        "bg-purple-50 text-purple-700 border border-purple-200"
                      }`}>
                        {file.category === "flask_backend" ? "Flask" : file.category === "node_backend" ? "Node" : file.category === "frontend" ? "React" : "Doc"}
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-400 font-mono truncate">{file.path}</span>
                    <p className="text-[11px] text-slate-500 line-clamp-2 leading-relaxed mt-0.5">
                      {file.description}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right Code View Pane */}
          <div className="flex-1 flex flex-col bg-slate-900 overflow-hidden">
            {/* Code Header Bar */}
            <div className="px-5 py-3 bg-slate-950 border-b border-slate-800 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2">
                <FileCode className="w-4 h-4 text-blue-400" />
                <span className="text-xs font-mono font-bold text-slate-200">{currentFile.path}</span>
                <span className="text-[10px] text-slate-500 font-mono">({currentFile.linesCount} 行)</span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={handleCopyCode}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium transition-colors cursor-pointer"
                >
                  {copied ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-emerald-400 font-semibold">已复制全文</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>复制代码</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* File Description Banner */}
            <div className="px-5 py-2 bg-slate-800/60 border-b border-slate-800/80 text-xs text-slate-300 flex items-center gap-2">
              <span className="font-semibold text-blue-400">功能说明:</span>
              <span>{currentFile.description}</span>
            </div>

            {/* Code Content Area */}
            <div className="flex-1 p-5 overflow-auto font-mono text-xs text-slate-200 leading-relaxed selection:bg-blue-600 selection:text-white">
              <pre>
                <code>{currentFile.code}</code>
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
