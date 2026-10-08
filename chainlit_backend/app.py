"""
IntelliServe 智能客服 Chainlit 对话与全链路自测程序 (Chainlit App)
基于 Chainlit + LangGraph + Qdrant (BGE-M3) + DeepSeek 构建

运行方式:
    pip install chainlit
    cd chainlit_backend
    chainlit run app.py -w --port 8000
"""

import os
import sys
import json
import time
from typing import Dict, Any, List

# 将当前目录和 fastapi_backend 目录加入系统路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FASTAPI_BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "fastapi_backend"))

if FASTAPI_BACKEND_DIR not in sys.path:
    sys.path.insert(0, FASTAPI_BACKEND_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

try:
    import chainlit as cl
except ImportError:
    # 允许在尚未安装 chainlit 时平稳导入并提示安装
    cl = None

try:
    from config import settings
    from core.qdrant_store import qdrant_store
    from services.memory_service import memory_service
    from workflow.graph import customer_service_graph
    from workflow.nodes import qdrant_retrieve_node, deepseek_generate_node
    from core.logger import cprint, LogColor
except ImportError as e:
    # 如果作为纯独立模块运行时的安全兜底
    print(f"[*] 正在从 {FASTAPI_BACKEND_DIR} 加载后端核心模块: {e}")
    settings = None
    qdrant_store = None
    customer_service_graph = None

# 预设自测常用客户画像
TEST_USER_PROFILES = {
    "profile_vip": {
        "name": "王女士",
        "phone": "138****8888",
        "vipLevel": "黄金会员",
        "sentiment": "neutral",
        "urgency": "medium",
        "intent": "退换货运费与政策咨询",
        "tags": ["黄金会员", "高频消费", "注重时效"],
        "orderId": "ORD_2026_998811"
    },
    "profile_normal": {
        "name": "张先生",
        "phone": "139****1234",
        "vipLevel": "普通会员",
        "sentiment": "neutral",
        "urgency": "low",
        "intent": "常规售后咨询",
        "tags": ["首购客户"],
        "orderId": "ORD_2026_112233"
    },
    "profile_frustrated": {
        "name": "李先生",
        "phone": "137****5678",
        "vipLevel": "钻石会员",
        "sentiment": "frustrated",
        "urgency": "high",
        "intent": "退款加急与投诉",
        "tags": ["重点客诉", "急躁情绪"],
        "orderId": "ORD_2026_556677"
    }
}

# 预设自测基准测试题
PRESET_BENCHMARKS = [
    {"label": "7天无理由退货", "value": "我刚收到商品不喜欢，可以在7天内申请无理由退货吗？运费谁出？"},
    {"label": "黄金会员免运费", "value": "我是黄金会员，退货的话运费平台会补贴吗？"},
    {"label": "生鲜/定制不可退", "value": "我买的刻字定制水杯和生鲜水果能申请7天无理由退货吗？"},
    {"label": "退款质检到账", "value": "退货寄回去之后，仓库几天能质检完？退款多久能到账？"},
    {"label": "强烈不满转人工", "value": "太慢了！你们到底什么服务态度，马上给我转人工客服主管！"},
    {"label": "保修与换新条款", "value": "买的蓝牙耳机用了10天突然充不进电了，可以免费换新吗？"},
]


if cl is not None:

    @cl.on_chat_start
    async def on_chat_start():
        """对话启动钩子：初始化知识库、会话上下文并展示快捷自测入口"""
        # 初始化 Qdrant 知识库（纯内存模式，秒级加载）
        if qdrant_store:
            qdrant_store.init_collection_with_faq()

        session_id = f"cl_test_{int(time.time())}"
        user_profile = TEST_USER_PROFILES["profile_vip"]

        cl.user_session.set("session_id", session_id)
        cl.user_session.set("user_profile", user_profile)
        cl.user_session.set("summary_memory", f"客户是{user_profile['vipLevel']}，咨询售后政策。")
        cl.user_session.set("step_history", [])

        # 发送欢迎卡片与自测快捷动作
        welcome_msg = (
            f"### 🚀 IntelliServe 智能客服全链路自测台 (Chainlit)\n"
            f"欢迎进入基于 **LangGraph + Qdrant (BGE-M3 1024维) + DeepSeek** 的端到端自测环境！\n\n"
            f"- **后端归档目录**: `chainlit_backend/` (已实现代码模块独立化)\n"
            f"- **当前模拟客户**: `{user_profile['name']}` ({user_profile['vipLevel']})\n"
            f"- **向量数据库**: `Qdrant 纯内存模式 (:memory:)`\n"
            f"- **基础知识库**: 《XX商城售后服务与退换货政策（2026版）》\n"
            f"- **会话标识**: `{session_id}`\n\n"
            f"👉 **点击下方快捷自测动作**，即可立即观测 LangGraph 状态图各节点链路流转与召回结果："
        )

        actions = [
            cl.Action(name="test_preset", payload={"query": item["value"]}, label=f"🧪 {item['label']}")
            for item in PRESET_BENCHMARKS
        ]
        actions.append(cl.Action(name="switch_profile", payload={"role": "toggle"}, label="👤 切换客户角色(普通/黄金/钻石)"))

        await cl.Message(content=welcome_msg, actions=actions).send()


    @cl.action_callback("test_preset")
    async def on_test_preset(action: cl.Action):
        """点击预设测试题目时触发执行"""
        query = action.payload.get("query", "")
        # 直接模拟用户消息触发流程
        await process_chat_message(query)


    @cl.action_callback("switch_profile")
    async def on_switch_profile(action: cl.Action):
        """切换模拟客户画像"""
        current = cl.user_session.get("user_profile", TEST_USER_PROFILES["profile_vip"])
        if current["vipLevel"] == "黄金会员":
            new_profile = TEST_USER_PROFILES["profile_normal"]
        elif current["vipLevel"] == "普通会员":
            new_profile = TEST_USER_PROFILES["profile_frustrated"]
        else:
            new_profile = TEST_USER_PROFILES["profile_vip"]

        cl.user_session.set("user_profile", new_profile)
        cl.user_session.set("summary_memory", f"已切换至{new_profile['name']}({new_profile['vipLevel']})。")

        await cl.Message(
            content=f"🔄 **已切换当前自测画像**：`{new_profile['name']}` (会员等级: **{new_profile['vipLevel']}** | 情绪基线: {new_profile['sentiment']})"
        ).send()


    @cl.on_message
    async def on_message(message: cl.Message):
        """用户或测试员在输入框发送消息时触发"""
        await process_chat_message(message.content)


    async def process_chat_message(user_input: str):
        """执行端到端 LangGraph 状态机调用，并用 Chainlit 原生 Step 树状追踪执行细节"""
        session_id = cl.user_session.get("session_id", "cl_test_default")
        user_profile = cl.user_session.get("user_profile", TEST_USER_PROFILES["profile_vip"])
        summary_memory = cl.user_session.get("summary_memory", "")

        t0 = time.time()

        # 构造 LangGraph 初始 AgentState
        initial_state = {
            "session_id": session_id,
            "user_message": user_input,
            "intent": "待识别",
            "sentiment": "neutral",
            "explicit_human_request": False,
            "retrieved_docs": [],
            "top_similarity_score": 0.0,
            "user_profile": user_profile,
            "summary_memory": summary_memory,
            "assembled_prompt": "",
            "generated_response": "",
            "escalated_to_human": False,
            "escalation_reason": "",
            "step_trace": []
        }

        # Step 根节点：LangGraph 状态图管线总调度
        async with cl.Step(name="LangGraph Pipeline (客服状态图执行)", type="run") as main_step:
            main_step.input = f"客户消息: {user_input}"

            final_state = None
            is_fallback = False

            # 执行 LangGraph 状态图
            try:
                if customer_service_graph is not None:
                    # 嵌套展示分析子步骤
                    async with cl.Step(name="Step 1: analyze_query (意图识别与情绪评估)", type="tool") as s1:
                        s1.input = user_input
                        # 执行 LangGraph
                        final_state = await customer_service_graph.ainvoke(
                            initial_state,
                            config={"configurable": {"thread_id": session_id}}
                        )
                        s1.output = (
                            f"意图: {final_state.get('intent')}\n"
                            f"情绪: {final_state.get('sentiment')}\n"
                            f"显式转人工: {final_state.get('explicit_human_request')}"
                        )

                    # 展示 Qdrant 检索子步骤
                    async with cl.Step(name="Step 2: qdrant_retrieve (BGE-M3 向量检索)", type="tool") as s2:
                        docs = final_state.get("retrieved_docs", [])
                        top_score = final_state.get("top_similarity_score", 0.0)
                        threshold = getattr(settings, "SIMILARITY_THRESHOLD", 0.6) if settings else 0.6
                        s2.output = (
                            f"召回条款数: {len(docs)} 条\n"
                            f"最高余弦相似度得分: {top_score:.4f}\n"
                            f"阈值要求: {threshold}"
                        )

                    # 展示决策与生成子步骤
                    if final_state.get("escalated_to_human"):
                        async with cl.Step(name="Step 3: human_escalation (触发人工坐席升级)", type="tool") as s3:
                            s3.output = f"升级原因: {final_state.get('escalation_reason')}"
                    else:
                        async with cl.Step(name="Step 3: deepseek_generate (DeepSeek 模型推理生成)", type="llm") as s3:
                            s3.output = f"完成回复生成，字数: {len(final_state.get('generated_response', ''))} 字"
                else:
                    raise RuntimeError("customer_service_graph 模块未就绪，使用极简降级方案")

            except Exception as e:
                # 极简方案 B 节点级容灾降级
                is_fallback = True
                async with cl.Step(name="⚠️ Graph Fallback 容灾降级 (方案 B)", type="tool") as err_step:
                    err_step.output = f"状态图异常接管: {str(e)}。无缝调用 qdrant_retrieve_node 与 deepseek_generate_node"
                    final_state = initial_state
                    if qdrant_retrieve_node:
                        final_state.update(qdrant_retrieve_node(final_state))
                    if deepseek_generate_node:
                        final_state.update(await deepseek_generate_node(final_state))

            latency_ms = int((time.time() - t0) * 1000)
            main_step.output = f"全流程完成，总耗时 {latency_ms}ms {'(方案B降级模式)' if is_fallback else '(LangGraph 正常调度)'}"

        # 整理输出
        reply = final_state.get("generated_response", "非常抱歉，暂时未能查询到对应政策，请联系人工服务。")
        docs = final_state.get("retrieved_docs", [])
        top_score = final_state.get("top_similarity_score", 0.0)
        intent = final_state.get("intent", "未分类")
        sentiment = final_state.get("sentiment", "neutral")
        is_escalated = final_state.get("escalated_to_human", False)

        # 构建 Chainlit 侧边栏/折叠附件元素 (Elements)
        elements = []

        # 1. 向量知识库检索条款卡片
        if docs:
            docs_content = f"### 📚 Qdrant 知识库匹配结果 (Top Cosine Score: {top_score:.4f})\n\n"
            for i, d in enumerate(docs, 1):
                docs_content += (
                    f"#### [{i}] {d.get('title', '未知条款')}\n"
                    f"- **分类**: `{d.get('category', '通用')}`\n"
                    f"- **标签**: `{', '.join(d.get('tags', []))}`\n"
                    f"- **核心正文**:\n```text\n{d.get('content', '')}\n```\n\n"
                )
            elements.append(
                cl.Text(name="Qdrant 参考知识条款", content=docs_content, display="side")
            )

        # 2. AgentState 状态检查点 JSON 卡片 (便于排查 state 字段流转)
        debug_state_data = {
            "session_id": final_state.get("session_id"),
            "intent": intent,
            "sentiment": sentiment,
            "explicit_human_request": final_state.get("explicit_human_request"),
            "top_similarity_score": top_score,
            "escalated_to_human": is_escalated,
            "escalation_reason": final_state.get("escalation_reason", ""),
            "retrieved_count": len(docs),
            "step_trace_count": len(final_state.get("step_trace", [])),
            "latency_ms": latency_ms
        }
        elements.append(
            cl.Text(
                name="AgentState 检查点摘要",
                content=f"```json\n{json.dumps(debug_state_data, ensure_ascii=False, indent=2)}\n```",
                display="side"
            )
        )

        # 状态标头小徽章
        sentiment_badge = "🟢 正常" if sentiment == "positive" else ("🔴 烦躁/急躁" if sentiment == "frustrated" else "⚪ 平静")
        human_badge = "🚨 已转接人工客服" if is_escalated else "🤖 AI 全权应答"

        header_status = (
            f"> 💡 **自测链路状态**: {human_badge} | 识别意图: `{intent}` | 客户情绪: {sentiment_badge} | 耗时: `{latency_ms}ms`\n\n"
        )

        # 发送最终回答
        await cl.Message(
            content=header_status + reply,
            elements=elements
        ).send()

else:
    # 当尚未安装 chainlit 时，执行 python app.py 会输出友好指导
    def main():
        print("=" * 60)
        print("【IntelliServe Chainlit 自测模块 (chainlit_backend)】")
        print("未检测到 chainlit 依赖，请在终端执行安装:")
        print("    pip install -r requirements.txt")
        print("或者:")
        print("    pip install chainlit")
        print("然后运行:")
        print("    cd chainlit_backend")
        print("    chainlit run app.py -w --port 8000")
        print("=" * 60)

    if __name__ == "__main__":
        main()
