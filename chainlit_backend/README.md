# IntelliServe Chainlit 对话界面与交互自测后端

本项目目录为 **IntelliServe 智能客服的 Chainlit 专用后端模块**，将 Chainlit 对话界面及其测试配置完整收拢于单一目录中，实现与 `fastapi_backend` 的高内聚、低耦合管理。

---

## 📁 目录结构

```text
chainlit_backend/
├── app.py                   # Chainlit 主服务入口（集成 LangGraph 状态机调用与 cl.Step 追踪）
├── .chainlit/
│   └── config.toml          # Chainlit 界面定制与主题配置文件
├── chainlit.md              # 对话初始首页说明看板 (Markdown)
├── requirements.txt         # Chainlit 运行所需依赖
├── run.sh                   # 一键启动脚本
└── README.md                # 模块使用与自测指南文档
```

---

## 🚀 快速启动指南

### 1. 安装依赖

```bash
cd chainlit_backend
pip install -r requirements.txt
```

### 2. 启动 Chainlit 服务

```bash
# 方式 A: 执行便捷脚本
chmod +x run.sh && ./run.sh

# 方式 B: 直接运行 chainlit 命令
chainlit run app.py -w --port 8000
```

服务启动后，在浏览器访问：
👉 `http://localhost:8000`

---

## 🧪 核心自测特性

1. **原生 `cl.Step` 树状追踪**：
   - `Step 1: analyze_query`：实时展示识别意图、情绪倾向及转人工标记；
   - `Step 2: qdrant_retrieve`：展示 BGE-M3 向量检索条数、最高余弦相似度及是否命中阈值（0.60）；
   - `Step 3: deepseek_generate / human_escalation`：展示模型推理字数或人工升级风控原因。
2. **预设 6 个基准测试题目**：
   - 7 天无理由退货、黄金会员免运费、生鲜定制不可退、48 小时质检退款、强烈不满转人工、保修换新条款，1 键点击即可验证。
3. **客户画像角色秒切 (`cl.Action`)**：
   - 支持黄金会员、普通会员、催单不满客户画像无缝轮换测试。
4. **Qdrant 向量检索证据侧边抽屉 (`cl.Text Elements`)**：
   - 包含政策条款标题、标签、相似度评分及参考正文。
5. **AgentState 状态契约实时监视**：
   - 侧边抽屉实时输出当前会话的 `AgentState(TypedDict)` 检查点快照，便于开发与测试排查。
