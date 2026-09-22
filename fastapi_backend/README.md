# IntelliServe 智能客服后端服务 (FastAPI + LangGraph + Qdrant + BGE-M3 + DeepSeek)

本项目是基于 **FastAPI** 异步高性能框架、**LangGraph** 状态图工作流引擎、**Qdrant** 向量数据库、**BGE-M3** 嵌入模型与 **DeepSeek** 大模型构建的工业级智能客服与人机协同平台。

默认内置并精准装载 **《XX商城售后服务与退换货政策（2026版）》** 官方 FAQ 知识库。

---

## 核心技术栈与选型

| 组件 | 选型 | 说明 |
| :--- | :--- | :--- |
| **Web 框架** | **FastAPI** (Python 3.10+) | 原生异步非阻塞 I/O、Pydantic v2 强类型校验、自动 OpenAPI (Swagger) 交互式文档 |
| **工作流编排** | **LangGraph** | 状态图有向无环工作流、分支条件路由、MemorySaver 检查点与会话记忆合成 |
| **向量嵌入模型** | **本地 Ollama (BGE-M3)** | 本地搭建与运行 Ollama `bge-m3` 模型，1024 维 Dense 稠密向量，直连本地 `http://localhost:11434`，具备高精度语义对齐与低延迟 |
| **向量数据库** | **Qdrant (In-Memory)** (`:memory:`) | **纯内存模式**、1024 维余弦相似度匹配、随应用直接常驻内存，**无需安装或使用 Docker 部署独立容器**，零运维依赖 |
| **大语言模型** | **DeepSeek** (`deepseek-chat`) | 支持 DeepSeek-V3 / DeepSeek-R1，遵循严格的商城售后政策 Prompt 约束，防幻觉无缝作答 |
| **知识库** | **XX商城 2026版售后新规** | 涵盖7天无理由退货、退货运费规则(含黄金会员免运费)、特殊商品、48小时退款到账、1年联保/15天换新 |

---

## 模块分层与代码结构 (分目录模块化封装)

整个后端严格按照高内聚、低耦合的模块化设计封装，目录清晰规范：

```
fastapi_backend/
├── config.py                 # ⚙️ 全局配置中心 (DeepSeek/BGE-M3/Qdrant 参数及阈值)
├── data/
│   ├── __init__.py
│   └── faq_document.py       # 📄 XX商城售后服务与退换货政策（2026版）Markdown 及切片解析器
├── models/
│   ├── __init__.py
│   ├── schemas.py            # 📐 Pydantic 数据契约模型 (ChatRequest, ChatResponse, Transfer 等)
│   └── state.py              # 🧠 LangGraph 对话状态定义 (AgentState)
├── core/
│   ├── __init__.py
│   ├── embedding.py          # 🔢 BGE-M3 向量嵌入引擎 (1024 维密集向量)
│   ├── qdrant_store.py       # 🗄️ Qdrant 向量数据库服务 (集合创建、切片入库、余弦相似度检索)
│   └── llm.py                # 🤖 DeepSeek 大模型客户端 (支持 deepseek-chat/reasoner 与严谨兜底)
├── workflow/
│   ├── __init__.py
│   ├── nodes.py              # 🔀 LangGraph 状态图执行节点 (意图分析、Qdrant召回、记忆合成、DeepSeek生成、人工升级)
│   └── graph.py              # 🌐 LangGraph 状态图流转编排与编译 (StateGraph + MemorySaver)
├── services/
│   ├── __init__.py
│   └── memory_service.py     # 💾 会话历史、长期记忆、客户画像与人工转接快照审计服务
├── api/
│   ├── __init__.py
│   └── routes.py             # 🔌 FastAPI RESTful 业务路由集中分发
├── app.py                    # 🚀 FastAPI 主服务启动入口与生命周期管理
├── requirements.txt          # 📦 Python 核心依赖清单
├── Dockerfile.fastapi        # 🐳 容器化构建文件
└── README.md                 # 📖 后端完整开发指南与架构说明
```

---

## 环境变量配置说明

可在系统环境变量或 `.env` 中配置：

```bash
# 服务基础配置
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=5000
DEBUG=false

# DeepSeek 大模型配置
DEEPSEEK_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxx"
DEEPSEEK_BASE_URL="https://api.deepseek.com"
DEEPSEEK_MODEL="deepseek-chat"               # 或 deepseek-reasoner
DEEPSEEK_TEMPERATURE=0.3

# 本地 Ollama 向量模型配置 (BGE-M3)
OLLAMA_BASE_URL="http://localhost:11434"      # 本地 Ollama 服务监听地址
OLLAMA_EMBED_MODEL="bge-m3"                   # 本地已拉取的嵌入模型 (ollama pull bge-m3)
EMBEDDING_DIM=1024                            # BGE-M3 标准 dense 向量维度

# Qdrant 向量数据库配置 (纯内存模式，无需 Docker 部署)
QDRANT_LOCATION=":memory:"                   # 纯内存模式，随应用秒级自启，无需 Docker 容器
QDRANT_COLLECTION="xx_mall_faq"

# 业务判定阈值
SIMILARITY_THRESHOLD=0.65                    # 低于此分流转人工或提示低置信度
TOP_K_RETRIEVAL=3
```

> 💡 **零 Docker 依赖说明**：向量数据库已默认配置为纯内存运行模式 (`QDRANT_LOCATION=":memory:"`)，直接内嵌在 Python 进程中，**完全无需安装或运行 Docker Qdrant 容器**。只需执行 `pip install -r requirements.txt` 和 `python app.py` 即可立即跑通全套向量检索流程！

---

## 快速安装与启动

### 1. 本地直接运行

```bash
# 0. (本地推荐) 启动 Ollama 并拉取 bge-m3
ollama pull bge-m3

cd fastapi_backend

# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动 FastAPI 服务
python app.py

# 启动后输出：
# 🚀 IntelliServe 智能客服系统 v3.0.0 正在启动...
# 🔹 大语言模型 (LLM):       DeepSeek (deepseek-chat)
# 🔹 向量模型 (Embedding):  本地 Ollama (模型: bge-m3, 地址: http://localhost:11434, 维度: 1024)
# 🔹 向量数据库 (Vector DB): Qdrant 纯内存模式 (In-Memory :memory:，无需 Docker 部署)
# 🔹 默认知识库:             XX商城售后服务与退换货政策（2026版）
# 🌐 服务监听地址: http://0.0.0.0:5000
# 📖 Swagger 交互文档: http://0.0.0.0:5000/docs
```

### 2. Docker 容器化运行

```bash
docker build -f Dockerfile.fastapi -t intelliserve-fastapi:latest .
docker run -d -p 5000:5000 -e DEEPSEEK_API_KEY="your_key" intelliserve-fastapi:latest
```

---

## 核心接口速查 (RESTful API)

### 1. 客户问答接口 (`POST /api/chat`)
- 请求体：
  ```json
  {
    "sessionId": "session_user_001",
    "message": "7天无理由退货运费谁承担？黄金会员免运费吗？"
  }
  ```
- 流程：
  1. `analyze_query`：识别用户意图为【退换货运费承担与会员权益】，情绪为 neutral；
  2. `qdrant_retrieve`：使用 BGE-M3 生成 1024 维向量并在 Qdrant 集合 `xx_mall_faq` 中余弦检索；
  3. `memory_synthesis`：结合客户画像（王女士·黄金会员）与长期记忆合成 Prompt；
  4. `deepseek_generate`：DeepSeek 生成准确且温馨的解答，主动提示黄金会员专属免运费特权；
  5. 记录会话流转与 `stepTrace` 链路。

### 2. 向量检索调试接口 (`POST /api/knowledge/search`)
- 请求体：
  ```json
  {
    "query": "电子产品坏了保修期多久？",
    "topK": 3,
    "minScore": 0.3
  }
  ```
- 返回 Qdrant 中匹配的【维修与保修条款】分块、相似度得分及切片信息。

### 3. 系统全链路自检测试接口 (`GET /api/test` & `POST /api/test`)
- `GET /api/test`：一键全链路自动探测。自动检测本地 Ollama (bge-m3) 探活与 1024 维向量生成、Qdrant 纯内存切片检索、会话记忆与 DeepSeek LLM 配置，返回各子系统诊断数据与响应耗时。
- `POST /api/test`：自定义测试接口。支持请求体 `{"query": "黄金会员退货免运费怎么申请？", "testOllama": true, "testQdrant": true, "testLLM": false}`，返回向量维度、前5维预览、召回切片与可选的大模型答复。

### 4. 会话与人工协同接口
- `GET /api/sessions`：获取所有会话状态
- `GET /api/sessions/{session_id}`：获取单个会话上下文详情
- `POST /api/sessions/{session_id}/transfer`：转接人工并封存生成 `TransferContextSnapshot`
- `POST /api/sessions/{session_id}/intervene`：人工坐席主动接管或释放会话
- `POST /api/sessions/{session_id}/human-message`：人工坐席直接向客户发送消息
- `GET /api/agents`：在线坐席矩阵与负载
- `GET /api/transfer-logs`：审计日志
- `GET /api/metrics`：监控大盘指标
- `POST /api/generate-suggestion`：AI 坐席副驾驶回复草稿推荐

---

## 附录：公司 FAQ 知识库内容（2026版）

系统内置在 `fastapi_backend/data/faq_document.py` 中的完整政策：

```markdown
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
```
