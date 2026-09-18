# IntelliServe - 智能客服与实时监控人工介入系统 (全栈代码架构)

本项目提供了一套完整的前后端协同智能客服系统架构，包含基于 **LangChain / LangGraph** 的对话状态机、**向量数据库**语义检索增强 (RAG)、**会话记忆管理**、**实时监控大盘**以及**无缝人工介入与转接接口**。

---

## 整体项目结构与前后端组织全景

```
.
├── 📁 src/                             # 前端工程源码 (React 19 + TypeScript + Vite + Tailwind CSS)
│   ├── components/
│   │   ├── CustomerChatView.tsx        # 客户对话界面 (支持AI问答、低置信度警告、一键主动呼叫转人工)
│   │   ├── AgentWorkbench.tsx          # 坐席工作台 (多会话列表、实时聊天、完整交接单快照、坐席改派)
│   │   ├── MonitoringDashboard.tsx     # 实时监控大盘 (并发指标、高危队列、转接流水审计日志)
│   │   ├── VectorKnowledgeBase.tsx     # 向量知识库工作台 (分块管理、相似度检索测试)
│   │   ├── LangGraphVisualizer.tsx     # LangGraph 状态图与状态检查点可视化
│   │   └── FullStackCodeViewer.tsx     # 全栈工程源码与架构中心 (前后端统一浏览与导出)
│   ├── types.ts                        # 前后端共享 TypeScript 数据契约定义
│   ├── App.tsx                         # 顶层导航与主控入口
│   └── main.tsx                        # React 启动入口
│
├── 📁 server/                          # 当前运行的 Node.js/Express 后端服务
│   ├── langGraphEngine.ts              # LangGraph 状态机实现 (意图分析、检索、记忆、生成、介入节点)
│   ├── memoryManager.ts                # 会话记忆与转接交接单快照管理中心 (持久化与审计流水)
│   ├── vectorStore.ts                  # 向量知识库检索服务 (Top-K 语义匹配与置信度打分)
│   └── gemini.ts                       # Gemini 3.8 Flash 接口安全桥接
├── server.ts                           # Express Web API 统一入口与静态资源托管
│
├── 📁 flask_backend/                   # Python Flask + LangGraph 后端服务实现 (可直接独立运行)
│   ├── app.py                          # Flask 路由服务 (含 /api/chat, /api/transfer, /api/metrics 等)
│   ├── graph_pipeline.py               # 纯 Python LangGraph StateGraph 管线与条件路由
│   ├── vector_store.py                 # Python 向量库与相似度检索模块
│   ├── memory_manager.py               # 会话记忆、完整上下文封存与流水审计模块
│   ├── requirements.txt                # Python 依赖清单 (LangGraph, Flask, ChromaDB 等)
│   └── README.md                       # Python 后端运行指南
│
├── package.json                        # Node 全栈依赖与编译脚本
├── tsconfig.json                       # TypeScript 配置
├── vite.config.ts                      # Vite 8 构建配置
└── README.md                           # 本全栈项目架构文档
```

---

## 核心技术选型

| 模块 | 前端技术栈 | 后端技术栈 (Node.js 运行态) | 后端技术栈 (Python Flask 态) |
| :--- | :--- | :--- | :--- |
| **基础框架** | React 19 + TypeScript + Vite 8 | Express 4 + TypeScript (tsx) | Flask 3 + flask-cors |
| **工作流引擎** | 实时状态流转可视化 | LangGraph 状态图模型 (StateGraph) | LangGraph (StateGraph + MemorySaver) |
| **向量检索 (RAG)** | 检索测试与置信度热度展示 | 向量余弦相似度与知识切片引擎 | ChromaDB / 向量相似度算法 |
| **记忆管理** | 长期记忆与交接快照展示 | MemoryManager 滑动窗口与快照封存 | PythonMemoryManager + 上下文打包 |
| **人工介入** | 坐席工作台 + 智能问候生成 | `/api/sessions/:id/transfer` 流水归档 | REST API + TransferLog 审计表 |
| **实时监控** | 3s 轮询监控大盘 + 预警队列 | `/api/metrics` 吞吐与情绪聚合 | `/api/monitor/metrics` 统计 |

---

## 前后端接口规范与数据流转

### 1. 对话与工作流接口 (`/api/chat`)
- **方法**：`POST`
- **入参**：`{ sessionId: string, message: string }`
- **执行过程**：
  1. 检索该用户的长期记忆与历史 Checkpoint；
  2. 意图与情绪分析 (`analyze_query`)，判断是否急躁或带有投诉倾向；
  3. 向量数据库相似度检索 (`vector_retrieve`) 召回 Top-3 切片；
  4. 置信度评估：若 `< 0.65` 或检测到强人工指令，自动流转至 `human_escalation` 节点；
  5. 组装 Prompt 调用大模型生成针对性答复并返回客户端。

### 2. 无缝人工介入接口 (`/api/sessions/:id/transfer`)
- **方法**：`POST`
- **入参**：`{ targetAgentId: string, reason: string, operatorNote?: string, triggerType: string }`
- **核心逻辑**：
  1. 提取自会话创建以来的**全量用户问题清单**；
  2. 提取**智能客服历史答复**与**最后一次作答**；
  3. 提取 LangGraph 沉淀的**长期会话记忆摘要 (summaryMemory)**；
  4. 锁定客户画像 (VIP 等级、情绪、关联订单号)；
  5. 生成全局唯一交接流水号（如 `TRF-1742...`），封存 `TransferContextSnapshot`；
  6. 将会话状态无缝置为 `HUMAN_INTERVENED`，指定人工坐席立即在工作台看到该会话及交接单。

### 3. 实时大盘与状态同步 (`/api/metrics` / `/api/sessions`)
- 前端通过统一的 REST API 轮询机制获取各会话的实时状态、情绪分布、待介入队列与交接单流水。

---

## 运行与部署说明

### 模式 A：运行当前 Node.js + Express 全栈工程（默认）
```bash
# 启动全栈一体化服务 (端口 3000)
npm run dev
```

### 模式 B：运行 Python Flask 后端
```bash
cd flask_backend
pip install -r requirements.txt
python app.py
```
