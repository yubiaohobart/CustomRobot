# IntelliServe FastAPI 后端接口单元测试文档

本目录 `fastapi_backend/tests` 为 IntelliServe 智能客服与人机协同后端系统的**全接口单元测试套件**。

测试基于 **FastAPI TestClient (基于 HTTPX/Starlette)** 与 **Pytest** 构建，覆盖全链路 RESTful 接口与状态机核心业务。

---

## 📁 目录架构与测试分工

```text
fastapi_backend/tests/
├── __init__.py                  # 测试套件 Python 包声明
├── conftest.py                  # Pytest 全局夹具 (Fixtures、TestClient、内存隔离钩子)
├── test_health_and_root.py      # 系统探活、根路由、自检诊断接口测试
├── test_knowledge_search.py     # Qdrant 向量知识切片、语义搜索与 Copilot 推荐测试
├── test_sessions_and_human.py   # 会话生命周期、人机转接快照、坐席接管与审计监控测试
├── test_chat_pipeline.py        # 智能客服核心问答流水线 (LangGraph + RAG + 意图与情绪) 测试
├── run_tests.py                 # 一键免配置测试驱动脚本 (支持 Pytest 与内置驱动双模)
└── README.md                    # 本测试说明文档
```

---

## 🎯 接口覆盖率与用例明细表

| 序号 | 接口路由 (HTTP Method + Path) | 对应测试文件 | 覆盖的核心场景与断言说明 |
|:---:|:---|:---|:---|
| **1** | `GET /` | `test_health_and_root.py` | 验证根路由欢迎信息、Swagger 文档链接与技术栈说明 |
| **2** | `GET /api/health` | `test_health_and_root.py` | 验证系统存活状态、向量库连接状态及活跃会话计数 |
| **3** | `GET /api/test` | `test_health_and_root.py` | 全链路一键自检（向量化、Qdrant 纯内存库、记忆服务、DeepSeek 配置） |
| **4** | `POST /api/test` | `test_health_and_root.py` | 交互式自检诊断，支持自定义 query 与各子引擎独立开关 |
| **5** | `GET /api/knowledge` | `test_knowledge_search.py` | 获取知识库全部切片文档，校验文档元数据（id, title, content, category） |
| **6** | `POST /api/knowledge/search` | `test_knowledge_search.py` | 验证 BGE-M3 语义向量检索、相似度过滤与 Pydantic 入参合法性校验 |
| **7** | `POST /api/generate-suggestion` | `test_knowledge_search.py` | 坐席副驾驶（Copilot）拟定话术推荐与匹配法规条款召回 |
| **8** | `GET /api/sessions` | `test_sessions_and_human.py` | 获取所有活跃会话列表 |
| **9** | `GET /api/sessions/{session_id}` | `test_sessions_and_human.py` | 验证会话详情获取及 404 Not Found 异常处理 |
| **10** | `POST /api/sessions/{session_id}/transfer` | `test_sessions_and_human.py` | 验证转人工交接、不可变上下文快照打包、状态机流转与坐席指派 |
| **11** | `POST /api/sessions/{session_id}/intervene` | `test_sessions_and_human.py` | 坐席主动接管（`takeover`）与释放交还 AI（`release`）双向状态切换 |
| **12** | `POST /api/sessions/{session_id}/human-message` | `test_sessions_and_human.py` | 坐席工作台消息发送与会话历史追加 |
| **13** | `GET /api/agents` | `test_sessions_and_human.py` | 校验客服坐席矩阵列表、技能专长与工号 |
| **14** | `GET /api/transfer-logs` | `test_sessions_and_human.py` | 查询交接快照审计流水日志 |
| **15** | `GET /api/metrics` | `test_sessions_and_human.py` | 监控大屏聚合统计数据（总会话数、总消息数、AI 自主解决率等） |
| **16** | `POST /api/chat` | `test_chat_pipeline.py` | **核心主链路**：常规问答、VIP 会员画像联动、转人工意图熔断、多轮记忆连续性与空入参校验 |

---

## 🚀 如何运行测试

### 方式一：使用一键免配置运行脚本（最推荐）

无论当前 Python 环境是否已经安装 pytest，都可以直接通过以下命令执行：

```bash
cd fastapi_backend
python tests/run_tests.py
```

终端将逐条输出各接口的测试结果及耗时毫秒数，并在最后输出汇总报表：
```text
======================================================================
🚀 IntelliServe 智能客服后端 API 接口单元测试驱动
📌 测试范围：根路由 / 健康探活 / Qdrant知识检索 / 会话记忆 / 人机转接 / LangGraph问答
======================================================================

📂 【系统状态与自检 (Health & Diagnostics)】
  ✅ [PASS] test_root_endpoint                        (3.2ms) - 测试场景：访问根路径 GET /
  ✅ [PASS] test_health_check_endpoint                (2.1ms) - 测试场景：访问系统探活接口 GET /api/health
  ✅ [PASS] test_system_test_get_diagnostics          (6.5ms) - 测试场景：触发全链路自检接口 GET /api/test
  ...
======================================================================
📊 单元测试执行总结报告:
   总用例数 (Total):  20
   通过用例 (Passed): 20
   失败用例 (Failed): 0
   总耗时间 (Time):   145.2 ms
======================================================================
🎉 全部接口单元测试 100% 顺利通过！
```

---

### 方式二：使用标准 Pytest 命令

在已安装依赖的虚拟环境中，可直接运行 pytest：

```bash
# 1. 确保安装了测试依赖 (在 fastapi_backend 目录下)
pip install -r requirements.txt

# 2. 执行全部单元测试
pytest tests/ -v

# 3. 指定某个测试文件单独运行
pytest tests/test_chat_pipeline.py -v

# 4. 指定用例过滤运行
pytest tests/ -k "test_chat" -v
```

---

## 🔒 测试设计与隔离保证

1. **零外部 Docker / 零网络硬依赖**：
   - 知识库采用 Qdrant 纯内存 `:memory:` 模式，测试无需事先启动 Qdrant 容器；
   - 嵌入引擎与大语言模型已内置高质量 Mock 与高保真离线降级兜底逻辑，无须启动 Ollama 或购买付费 API Key 也能 100% 通过测试。
2. **测试用例强隔离（Fixture Autouse）**：
   - 每个用例执行前由 `conftest.py` 中的 `reset_memory_state` 钩子清理 `memory_service.sessions` 与 `transfer_logs`，防止测试用例之间互相污染状态。
3. **Pydantic 异常边界拦截校验**：
   - 包含了空 query、非法字段长度、超出范围的数值等边界参数校验测试（HTTP 422 预期断言）。
