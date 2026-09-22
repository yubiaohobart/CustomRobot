# IntelliServe 纯 Python FastAPI 后端极简使用指南（小白友好）

如果你只熟悉 Python，不需要懂任何前端或 Node.js 代码，后端已全面升级为 **FastAPI + LangGraph** 异步高性能引擎，支持原生 OpenAPI/Swagger 接口文档交互：

---

## 第一步：启动你的 Python FastAPI 后端（监听 5000 端口）

进入 `fastapi_backend` 目录，安装依赖并一键启动：

```bash
# 1. 进入 Python 后端代码目录
cd fastapi_backend

# 2. 安装 Python 依赖包 (包含 fastapi, uvicorn, langgraph 等)
pip install -r requirements.txt

# 3. 启动 FastAPI 后端服务
python app.py
```

当终端打印出以下日志时，说明 FastAPI 后端已启动成功：
```text
FastAPI + LangGraph Intelligent Customer Service Server starting on port 5000...
Interactive Swagger Docs available at: http://127.0.0.1:5000/docs
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:5000 (Press CTRL+C to quit)
```

> 💡 **超棒的额外福利**：
> 启动后，你可以在浏览器直接打开 **`http://localhost:5000/docs`**，查看 FastAPI 自动生成的 **Swagger UI 交互式接口文档**，在这里可以直接测试发消息、查记忆、派单转接等所有接口！

> **所有核心业务都在这个目录下**：
> - `app.py`：FastAPI 接口入口（Pydantic 校验、CORS、RESTful API）
> - `graph_pipeline.py`：基于 LangGraph 的客服状态图编排逻辑
> - `vector_store.py`：向量知识库语义检索 (RAG)
> - `memory_manager.py`：会话记忆、人工坐席派发与交接单流转

---

## 第二步：打开另一个终端，启动前端展示界面

保持上面的 Python 终端不要关，在项目根目录下新开一个终端：

```bash
# 启动前端界面（自动直连 5000 端口的 FastAPI）
npm run dev:frontend
```

终端会输出：
```text
  VITE v6.x.x  ready in 200 ms

  ➜  Local:   http://localhost:5173/
```

此时在浏览器中打开 **`http://localhost:5173`**：
1. 在网页里发一条消息：“我要退货”，你可以立刻在第一个终端的 **Python 控制台里看到 FastAPI / Uvicorn 在打印请求日志**！
2. 如果你按 `Ctrl + C` 把 Python 停掉，前端发消息就会直接报错，验证了**整个系统是由你的 FastAPI Python 代码完全驱动的**！

---

## 你常用的 Python 接口速查表

你在 Python `fastapi_backend/app.py` 中写的所有接口都已生效：
- `POST /api/chat`：客户发送消息，由 Python 驱动 LangGraph 状态图与大模型；
- `GET /api/sessions`：查询 Python `mem_manager` 中的会话列表；
- `POST /api/sessions/{session_id}/transfer`：人工介入转接，生成 Python 审计交接单；
- `GET /api/metrics`：监控大盘实时统计；
- `GET /api/knowledge`：知识库全量列表；
- `POST /api/knowledge/search`：向量知识库检索；
- `POST /api/generate-suggestion`：AI Copilot 坐席辅助建议生成。
