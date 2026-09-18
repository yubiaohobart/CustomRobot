# IntelliServe - Flask + LangGraph 智能客服后端服务

本项目是基于 **Flask** 框架与 **LangGraph** 状态图引擎构建的生产级智能客服系统后端，实现了向量数据库检索增强 (RAG)、会话记忆管理 (MemorySaver)、实时监控与无缝人工介入接口。

## 目录结构

```
flask_backend/
├── app.py              # Flask Web API 核心入口服务 (路由、CORS、转接调度)
├── graph_pipeline.py   # LangGraph 状态图管线 (AgentState, 多节点流转与条件路由)
├── vector_store.py     # 向量知识库存储与余弦相似度检索
├── memory_manager.py   # 会话上下文记忆、快照封存与转接流水审计管理器
├── requirements.txt    # Python 依赖清单
└── README.md           # 本说明文档
```

## 快速启动

1. **安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```

2. **环境变量配置（可选）**：
   ```bash
   export FLASK_PORT=5000
   export GEMINI_API_KEY="your_api_key_here"
   ```

3. **启动 Flask 服务**：
   ```bash
   python app.py
   ```
   服务将运行在 `http://localhost:5000`。
