# 🚀 IntelliServe 智能客服 Chainlit 自测工作台

欢迎来到 **IntelliServe** 交互式自测平台！

### 🛠️ 架构与链路
1. **工作流编排**: `LangGraph` 状态图 (涵盖 `analyze_query` -> `qdrant_retrieve` -> `memory_synthesis` -> `deepseek_generate` / `human_escalation`)
2. **知识库**: 《XX商城售后服务与退换货政策（2026版）》
3. **向量引擎**: `Qdrant` 内存模式 (`:memory:`) + `BGE-M3` 1024 维稠密向量
4. **大语言模型**: `DeepSeek` (支持 Prompt 注入与防幻觉兜底)
5. **高可用保障**: 极简方案 B 节点级容灾降级 (Graph 异常时秒级纯函数接管)

### 🧪 快速自测提示
直接在输入框输入问题，或点击页面预设测试动作即可查看全流程 Trace 步骤与状态流转！
