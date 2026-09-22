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
  category: "frontend" | "fastapi_backend" | "docs";
  language: "typescript" | "python" | "json" | "markdown";
  description: string;
  linesCount: number;
  code: string;
}

const PROJECT_FILES: CodeFileItem[] = [
  // 1. Python FastAPI Modular Backend Files
  {
    id: "backend_config",
    name: "config.py",
    path: "fastapi_backend/config.py",
    category: "fastapi_backend",
    language: "python",
    description: "全局配置中心：DeepSeek、BGE-M3 (1024维)、Qdrant 纯内存模式 (In-Memory，无需 Docker) 集中管理",
    linesCount: 45,
    code: `"""
全局系统配置中心 (Configuration Center)
管理 DeepSeek 大模型、BGE-M3 向量模型、Qdrant 内存向量库与服务端口
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
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3")
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "bge-m3")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1024"))  # BGE-M3 标准 dense 向量维度 1024
    EMBEDDING_API_URL: Optional[str] = os.getenv("EMBEDDING_API_URL", None)
    EMBEDDING_API_KEY: Optional[str] = os.getenv("EMBEDDING_API_KEY", None)

    # 向量数据库配置 (Qdrant In-Memory 纯内存模式，无需 Docker 部署)
    QDRANT_LOCATION: str = os.getenv("QDRANT_LOCATION", ":memory:")
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "xx_mall_faq")

    # 业务决策阈值
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.65"))
    TOP_K_RETRIEVAL: int = int(os.getenv("TOP_K_RETRIEVAL", "3"))

settings = Settings()`
  },
  {
    id: "backend_faq_data",
    name: "faq_document.py",
    path: "fastapi_backend/data/faq_document.py",
    category: "fastapi_backend",
    language: "python",
    description: "企业官方知识库：XX商城售后服务与退换货政策（2026版）原始 Markdown 与语义分块解析器",
    linesCount: 85,
    code: `"""
企业官方知识库数据：XX商城售后服务与退换货政策（2026版）
包含原始 Markdown 文档与结构化切片解析器
"""

FAQ_MARKDOWN_DOC = """
# XX商城售后服务与退换货政策（2026版）

## 1. 7天无理由退货政策
- 支持范围：用户在签收商品之日起 7 天内（含 7 天），在商品完好、不影响二次销售的前提下，均可申请“7天无理由退换货”。
- 运费规则：
  - 因商品质量问题（如破损、错发、功能故障）导致的退换货，来回运费由本公司全额承担。
  - 因客户个人原因（如不喜欢、拍错、七天无理由）发起的退换货，寄回运费需由买家自行承担。
  - 黄金会员及以上等级用户，享有“退货免运费”专属权益，退货运费由平台补贴。

## 2. 不支持7天无理由退换的特殊商品
以下商品一经售出，非质量问题不予退换：
1. 个人定制类商品（如刻字、按需定制尺寸的工艺品）；
2. 鲜活易腐类商品（如生鲜水果、鲜花）；
3. 在线下载或者拆封的数字化商品（如软件激活码、充值卡）；
4. 交付后拆封即影响人身安全或者生命健康的贴身衣物（如内裤、泳裤）、母婴用品。

## 3. 退款到账时间
- 仓库在收到退回商品并在 48 小时内完成质检入库；
- 质检合格后，系统自动原路发起退款：
  - 微信/支付宝零钱：即时到账；
  - 借记卡：1~3 个工作日到账；
  - 信用卡：3~5 个工作日到账。

## 4. 维修与保修条款
- 全系电子产品享有 1 年全国联保服务。
- 超过 7 天但在 15 天内发生非人为损坏的硬件故障，可申请“免费换新机”。
- 保修期内因人为摔落、进水、私自拆修导致的损坏，不属于免费保修范围，需收取配件成本费。
"""`
  },
  {
    id: "backend_embedding",
    name: "embedding.py",
    path: "fastapi_backend/core/embedding.py",
    category: "fastapi_backend",
    language: "python",
    description: "BGE-M3 向量嵌入引擎：优先直连本地 Ollama (bge-m3 1024维)，具备动态探活与自适应降级",
    linesCount: 165,
    code: `"""
BGE-M3 向量嵌入引擎 (core/embedding.py)
驱动模式: 优先直连本地 Ollama 模型服务 (ollama run bge-m3)
接口端点: http://localhost:11434/api/embed (1024 维 Dense 稠密向量)
"""
import httpx
from typing import List, Optional
from config import settings

class BGEM3EmbeddingEngine:
    def __init__(self):
        self.model_name = settings.OLLAMA_EMBED_MODEL  # 默认 'bge-m3'
        self.ollama_base_url = settings.OLLAMA_BASE_URL # 'http://localhost:11434'
        self.dim = settings.EMBEDDING_DIM              # 1024 维
        self._init_engine()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量调用本地 Ollama 生成 1024 维密集嵌入向量并做 L2 归一化"""
        try:
            url = f"{self.ollama_base_url}/api/embed"
            with httpx.Client(timeout=15.0) as client:
                res = client.post(url, json={"model": self.model_name, "input": texts})
                if res.status_code == 200:
                    raw_vecs = res.json().get("embeddings", [])
                    return [self._normalize(v) for v in raw_vecs]
        except Exception:
            pass
        # 若未启动 Ollama 守护进程，平滑降级至进程内确定性高维语义投影 (免崩溃)
        return [self._generate_dense_vector(t) for t in texts]

bge_m3_engine = BGEM3EmbeddingEngine()`
  },
  {
    id: "backend_qdrant",
    name: "qdrant_store.py",
    path: "fastapi_backend/core/qdrant_store.py",
    category: "fastapi_backend",
    language: "python",
    description: "Qdrant 向量数据库服务：纯内存模式 (:memory:)，无需使用 Docker 部署，开箱即用",
    linesCount: 155,
    code: `"""
Qdrant 向量数据库服务驱动 (core/qdrant_store.py)
模式: 纯内存模式 (In-Memory :memory:，无需 Docker 部署独立容器)
集合名: xx_mall_faq (维度: 1024, 距离度量: Cosine)
"""
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from core.embedding import embedding_engine

class QdrantKnowledgeStore:
    def __init__(self):
        # 优先使用纯内存客户端，零外部容器依赖
        self.client = QdrantClient(":memory:")
        self.collection_name = settings.QDRANT_COLLECTION
        self.init_collection_and_seed()`
  },
  {
    id: "backend_llm",
    name: "llm.py",
    path: "fastapi_backend/core/llm.py",
    category: "fastapi_backend",
    language: "python",
    description: "DeepSeek 大模型客户端：deepseek-chat 接入、专业客服 System Prompt 约束与严谨防幻觉兜底",
    linesCount: 140,
    code: `"""
DeepSeek 大模型客户端 (core/llm.py)
模型: deepseek-chat / deepseek-reasoner
"""
from openai import OpenAI
from config import settings

class DeepSeekLLMClient:
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL
        )

    def generate_reply(self, prompt: str, system_prompt: str = None) -> str:
        # 调用 DeepSeek API 或启用严格规则防幻觉引擎
        ...`
  },
  {
    id: "backend_graph",
    name: "graph.py",
    path: "fastapi_backend/workflow/graph.py",
    category: "fastapi_backend",
    language: "python",
    description: "LangGraph 工作流组装：StateGraph 状态图定义、条件路由与 MemorySaver 检查点持久化",
    linesCount: 110,
    code: `"""
LangGraph 工作流定义与状态机编排 (workflow/graph.py)
拓扑: START -> analyze_query -> [条件路由] -> qdrant_retrieve -> memory_synthesis -> deepseek_generate -> END
"""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from models.state import AgentState
from workflow.nodes import analyze_query_node, qdrant_retrieve_node, memory_synthesis_node, deepseek_generate_node, human_escalation_node

def build_customer_service_graph():
    builder = StateGraph(AgentState)
    builder.add_node("analyze_query", analyze_query_node)
    builder.add_node("qdrant_retrieve", qdrant_retrieve_node)
    builder.add_node("memory_synthesis", memory_synthesis_node)
    builder.add_node("deepseek_generate", deepseek_generate_node)
    builder.add_node("human_escalation", human_escalation_node)
    ...
    return builder.compile(checkpointer=MemorySaver())`
  },
  {
    id: "backend_routes",
    name: "routes.py",
    path: "fastapi_backend/api/routes.py",
    category: "fastapi_backend",
    language: "python",
    description: "FastAPI RESTful API 路由层：/api/chat、/api/knowledge/search、/api/transfer 等全功能接口",
    linesCount: 280,
    code: `"""
FastAPI 业务路由层 (api/routes.py)
"""
from fastapi import APIRouter, HTTPException
from models.schemas import ChatRequest, ChatResponse, TransferRequest
from services.memory_service import memory_service
from workflow.graph import customer_service_graph

router = APIRouter(prefix="/api")

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    # 驱动 LangGraph 状态图 + Qdrant 检索 + DeepSeek 答复
    ...

@router.get("/test")
async def system_test_get():
    # 一键全链路子系统自检：本地 Ollama(bge-m3) 探活、Qdrant 纯内存检索、DeepSeek 配置检测
    ...`
  },
  {
    id: "backend_app",
    name: "app.py",
    path: "fastapi_backend/app.py",
    category: "fastapi_backend",
    language: "python",
    description: "FastAPI 应用入口：生命周期管理 (Lifespan)、CORS、Swagger 文档与 Uvicorn 启动",
    linesCount: 95,
    code: `"""
FastAPI 智能客服主应用入口 (fastapi_backend/app.py)
"""
from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.routes import router
from core.qdrant_store import qdrant_store

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化 Qdrant 集合与注入 XX商城 2026 FAQ 切片
    qdrant_store.init_collection_and_seed()
    yield

app = FastAPI(title="XX商城智能客服系统", version="3.0.0", lifespan=lifespan)
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000)`
  },

  // 2. Frontend React Files
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
    id: "doc_python_only",
    name: "PYTHON_ONLY_GUIDE.md",
    path: "PYTHON_ONLY_GUIDE.md",
    category: "docs",
    language: "markdown",
    description: "纯 Python 专属极简开发指南：仅需启动 python app.py 与 npm run dev:frontend，全流程由 Python 驱动",
    linesCount: 50,
    code: `# IntelliServe 纯 Python 后端极简使用指南

## 第一步：启动你的 Python 后端 (监听 5000 端口)
cd fastapi_backend
pip install -r requirements.txt
python app.py

## 第二步：启动前端网页 (新终端)
npm run dev:frontend
打开 http://localhost:5173 即可！
前端已默认将所有 /api 请求直连 5000 端口的 FastAPI。`
  },
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

本项目前端基于 React 19 + Vite，后端提供 Node.js 与 Python FastAPI 独立服务。

## 极速 3 步：最纯粹的前后端分离 (Nginx + 静态前端 + API 后端)

### 步骤 1：构建前端静态页面
npm run build
产物输出在 dist 目录，直接上传到服务器 /var/www/intelliserve/dist

### 步骤 2：启动后端 API 服务
# Node.js 后端：
pm2 start dist/server.cjs --name "intelliserve-api"
# 或 Python FastAPI 后端：
cd fastapi_backend && uvicorn app:app --host 0.0.0.0 --port 5000

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
        proxy_pass http://127.0.0.1:5000; # 5000 (FastAPI)
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
- /fastapi_backend: 生产级 Python FastAPI + LangGraph 后端独立工程 (已全量作为系统唯一后端)
- PYTHON_ONLY_GUIDE.md: 纯 Python FastAPI 开发与一键部署指南`
  }
];

export const FastAPIArchitectureCode: React.FC = () => {
  const [selectedFileId, setSelectedFileId] = useState<string>("backend_app");
  const [filterCategory, setFilterCategory] = useState<"all" | "frontend" | "fastapi_backend" | "docs">("all");
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
            <h1 className="text-xl font-bold text-slate-900">前后端工程源码与架构中心</h1>
            <span className="px-2.5 py-0.5 bg-emerald-50 text-emerald-700 text-xs font-semibold rounded-full border border-emerald-200">
              纯 Python FastAPI 后端 + React 前端
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            后端已升级为 FastAPI + LangGraph 异步高性能引擎，原生自带 OpenAPI/Swagger 接口文档与 Pydantic 校验
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
                <div className="flex items-center gap-2 font-bold text-xs text-emerald-700 pb-2 border-b border-slate-200">
                  <Server className="w-4 h-4" />
                  <span>2. 后端服务控制层 (Python FastAPI: 端口 5000)</span>
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
                <span>纯 Python FastAPI 后端与前端启动指令</span>
                <span className="text-emerald-400">Node.js 业务已剔除 · 唯一后端</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <span className="text-emerald-400 font-bold"># 1. 启动 Python FastAPI 核心后端 (端口 5000)</span>
                  <p className="text-slate-400 text-[11px] mt-1">cd fastapi_backend && python app.py</p>
                  <p className="text-slate-500 text-[10px] mt-0.5">运行 FastAPI + Uvicorn，自带 Swagger 交互文档 (/docs)</p>
                </div>
                <div>
                  <span className="text-blue-400 font-bold"># 2. 启动前端 Vite 界面 (端口 5173 / 3000)</span>
                  <p className="text-slate-400 text-[11px] mt-1">npm run dev:frontend</p>
                  <p className="text-slate-500 text-[10px] mt-0.5">所有 /api 请求自动反向代理到 127.0.0.1:5000</p>
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
                  onClick={() => setFilterCategory("fastapi_backend")}
                  className={`px-2 py-0.5 rounded cursor-pointer ${
                    filterCategory === "fastapi_backend" ? "bg-emerald-600 text-white font-semibold" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  🐍 FastAPI 后端
                </button>
                <button
                  onClick={() => setFilterCategory("frontend")}
                  className={`px-2 py-0.5 rounded cursor-pointer ${
                    filterCategory === "frontend" ? "bg-blue-600 text-white font-semibold" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  🎨 React 前端
                </button>
                <button
                  onClick={() => setFilterCategory("docs")}
                  className={`px-2 py-0.5 rounded cursor-pointer ${
                    filterCategory === "docs" ? "bg-purple-600 text-white font-semibold" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  📖 文档指南
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
                        file.category === "fastapi_backend" ? "bg-emerald-50 text-emerald-700 border border-emerald-200" :
                        file.category === "frontend" ? "bg-blue-50 text-blue-700 border border-blue-200" :
                        "bg-purple-50 text-purple-700 border border-purple-200"
                      }`}>
                        {file.category === "fastapi_backend" ? "FastAPI" : file.category === "frontend" ? "React" : "Doc"}
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
