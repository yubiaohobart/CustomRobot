# IntelliServe - 智能客服与实时监控人工介入系统 (全栈代码架构)

本项目提供了一套完整的前后端协同智能客服系统架构，后端全面基于 **FastAPI + LangGraph + Qdrant + BGE-M3 + DeepSeek** 打造，结合**向量知识库语义检索 (RAG)**、**多轮会话记忆管理**、**实时监控大盘**以及**无缝人工介入与转接交接单快照**。

内置装载官方 **《XX商城售后服务与退换货政策（2026版）》** 知识库，支持 7 天无理由、运费分担规则、黄金会员免运费特权、特殊商品、48小时质检退款与全国联保条款。

---

## 整体项目结构与前后端组织全景

```
.
├── 📁 src/                             # 前端工程源码 (React 19 + TypeScript + Vite + Tailwind CSS)
│   ├── components/
│   │   ├── CustomerChatView.tsx        # 客户对话界面 (支持AI问答、低置信度警告、一键主动呼叫转人工)
│   │   ├── AgentWorkbench.tsx          # 坐席工作台 (多会话列表、实时聊天、完整交接单快照、坐席改派)
│   │   ├── MonitoringDashboard.tsx     # 实时监控大盘 (并发指标、高危队列、转接流水审计日志)
│   │   ├── VectorKnowledgeBase.tsx     # Qdrant + BGE-M3 知识库工作台 (分块管理、相似度检索测试)
│   │   ├── LangGraphVisualizer.tsx     # LangGraph 状态图与状态检查点可视化
│   │   └── FlaskArchitectureCode.tsx   # 前后端工程源码中心 (统一浏览与代码查看)
│   ├── types.ts                        # 前后端共享 TypeScript 数据契约定义
│   ├── App.tsx                         # 顶层导航与主控入口
│   └── main.tsx                        # React 启动入口
│
├── 📁 fastapi_backend/                 # 核心后端服务 (FastAPI + LangGraph + Qdrant + BGE-M3 + DeepSeek)
│   ├── config.py                       # ⚙️ 全局配置中心 (DeepSeek/BGE-M3/Qdrant 参数及阈值)
│   ├── data/
│   │   ├── __init__.py
│   │   └── faq_document.py             # 📄 XX商城售后服务与退换货政策（2026版）Markdown 及切片解析器
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py                  # 📐 Pydantic 数据契约模型 (ChatRequest, ChatResponse, Transfer 等)
│   │   └── state.py                    # 🧠 LangGraph 对话状态定义 (AgentState)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── embedding.py                # 🔢 BGE-M3 向量嵌入引擎 (1024 维密集向量)
│   │   ├── qdrant_store.py             # 🗄️ Qdrant 向量数据库驱动 (集合初始化、余弦相似度检索)
│   │   └── llm.py                      # 🤖 DeepSeek 大模型驱动 (接入 deepseek-chat/reasoner 与严谨兜底)
│   ├── workflow/
│   │   ├── __init__.py
│   │   ├── nodes.py                    # 🔀 LangGraph 状态图各节点 (意图分析、Qdrant召回、记忆合成、DeepSeek生成、人工升级)
│   │   └── graph.py                    # 🌐 LangGraph 状态机拓扑构建与编译 (StateGraph + MemorySaver)
│   ├── services/
│   │   ├── __init__.py
│   │   └── memory_service.py           # 💾 会话历史、长期记忆、客户画像与人工转接快照审计服务
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py                   # 🔌 FastAPI RESTful 业务路由集中分发
│   ├── app.py                          # 🚀 FastAPI 主服务启动入口与生命周期管理
│   ├── requirements.txt                # 📦 Python 核心依赖清单
│   ├── Dockerfile.fastapi              # 🐳 容器化构建文件 (FastAPI)
│   └── README.md                       # 📖 后端完整开发指南与架构说明
│
├── server.ts                           # 前端反向代理与静态资源宿主服务 (端口 3000 -> 代理至 5000)
├── package.json                        # 前端构建依赖与 NPM 启动脚本
├── vite.config.ts                      # Vite 构建配置
├── DEPLOYMENT.md                       # 生产环境综合部署手册 (Docker / Nginx / Uvicorn)
├── SEPARATE_DEPLOYMENT.md              # 前后端解耦独立部署指南
└── RAW_SEPARATE_GUIDE.md               # 裸机独立运行与双终端极速启动指南
```

---

## 核心技术选型

| 模块 | 前端技术栈 | 后端技术栈 (FastAPI 核心) |
| :--- | :--- | :--- |
| **基础框架** | React 19 + TypeScript + Vite | FastAPI 0.110+ (ASGI 异步高性能) |
| **应用服务器** | Vite Dev Server / Nginx 静态托管 | Uvicorn 异步 ASGI 服务器 (默认端口 5000) |
| **工作流编排** | 状态节点与拓扑图可视化 | LangGraph 0.2+ (StateGraph + MemorySaver) |
| **向量嵌入模型** | 检索测试与置信度热度展示 | **BGE-M3** (`BAAI/bge-m3`, Dense 1024 维) |
| **向量数据库** | 集合状态与余弦相似度展示 | **Qdrant (In-Memory 纯内存模式)** (直接常驻进程，**无需 Docker 部署**) |
| **大语言模型** | 聊天气泡与置信度指示器 | **DeepSeek** (`deepseek-chat` / `deepseek-reasoner`) |
| **知识库** | - | **XX商城售后服务与退换货政策（2026版）** |
| **接口契约** | TypeScript 强类型接口 | Pydantic v2 请求模型 + OpenAPI (Swagger) |
| **记忆管理** | 长期记忆与交接快照展示 | MemoryService 滑动窗口、记忆合成与快照封存 |
| **人工介入** | 坐席工作台 + 智能建议生成 | `/api/sessions/{id}/transfer` 流水归档 |
| **交互式文档** | - | Swagger UI (`/docs`) & ReDoc (`/redoc`) |

---

## 快速启动指南

### 1. 启动后端 FastAPI (端口 5000)

```bash
cd fastapi_backend

# 安装依赖
pip install -r requirements.txt

# 配置 DeepSeek API Key（可选，未配置时自动开启精准规则答复引擎）
export DEEPSEEK_API_KEY="your-deepseek-api-key"

# 启动服务
python app.py
```
- Swagger 接口文档：`http://localhost:5000/docs`
- 交互测试页面：`http://localhost:5000/redoc`

### 2. 启动前端界面 (端口 3000)

```bash
# 在项目根目录下
npm install
npm run dev
```
打开浏览器访问 `http://localhost:3000` 即可体验全套智能客服人机协同平台。

---

## 附录：XX商城售后服务与退换货政策（2026版）

知识库系统内置官方条款：
1. **7天无理由退货政策**：签收商品之日起 7 天内支持无理由退换；质量问题由公司承担往返运费，个人原因由买家承担寄回运费，**黄金会员及以上等级享有“退货免运费”专属权益**（平台全额补贴）。
2. **不支持7天无理由退换的特殊商品**：个人定制类、生鲜水果鲜花、数字化虚拟商品、贴身衣物及母婴用品非质量问题不予退换。
3. **退款到账时间**：仓库在收到商品并在 48 小时内完成质检入库后原路退款；微信/支付宝即时到账，借记卡 1~3 工作日，信用卡 3~5 工作日。
4. **维修与保修条款**：全系电子产品 1 年全国联保；15 天内非人为硬件故障可申请免费换新机；人为损坏收取配件成本费。
