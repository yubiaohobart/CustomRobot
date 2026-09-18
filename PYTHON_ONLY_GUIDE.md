# IntelliServe 纯 Python 后端极简使用指南（小白友好）

如果你只熟悉 Python，不需要懂任何前端或 Node.js 代码，按照以下**超简单的两步**即可完全由 Python Flask 接管所有服务：

---

## 第一步：启动你的 Python 后端（监听 5000 端口）

进入 `flask_backend` 目录，安装 Python 依赖并启动：

```bash
# 1. 进入 Python 后端代码目录
cd flask_backend

# 2. 安装 Python 依赖包
pip install -r requirements.txt

# 3. 启动 Flask 后端服务
python app.py
```

当终端打印出以下日志时，说明 Python 后端已启动成功：
```text
Flask + LangGraph Intelligent Customer Service Server starting on port 5000...
 * Running on http://127.0.0.1:5000
```
> **所有核心业务都在这个目录下**：
> - `app.py`：Flask 接口入口（RESTful API）
> - `graph_pipeline.py`：基于 LangGraph 的客服状态图编排逻辑
> - `vector_store.py`：向量数据库语义检索 (RAG)
> - `memory_manager.py`：会话记忆、人工坐席派发与交接单流转

---

## 第二步：打开另一个终端，启动前端展示界面

保持上面的 Python 终端不要关，在项目根目录下新开一个终端：

```bash
# 启动前端界面（自动直连 5000 端口的 Flask）
npm run dev:frontend
```

终端会输出：
```text
  VITE v6.x.x  ready in 200 ms

  ➜  Local:   http://localhost:5173/
```

此时在浏览器中打开 **`http://localhost:5173`**：
1. 在网页里发一条消息：“我要退货”，你可以立刻在第一个终端的 **Python 控制台里看到你的 Python 代码在打印日志并处理请求**！
2. 如果你按 `Ctrl + C` 把 Python 停掉，前端发消息就会直接报错，验证了**整个系统是由你的 Python 代码完全驱动的**！

---

## 你常用的 Python 接口速查表

你在 Python `flask_backend/app.py` 中写的所有接口都已生效：
- `POST /api/chat`：客户发送消息，由 Python 驱动 LangGraph 状态图与大模型；
- `GET /api/sessions`：查询 Python `mem_manager` 中的会话列表；
- `POST /api/transfer/execute`：人工介入转接，生成 Python 审计交接单；
- `GET /api/metrics`：监控大盘实时统计；
- `POST /api/knowledge/search`：向量知识库检索。
