"""
IntelliServe 智能客服 Chainlit 对话自测应用
基于 Chainlit + LangGraph + Qdrant + DeepSeek
"""

import time
import chainlit as cl
from core.qdrant_store import qdrant_store
from workflow.graph import customer_service_graph

# 预设测试画像
PROFILES = {
    "vip": {"name": "王女士", "vipLevel": "黄金会员", "sentiment": "neutral"},
    "normal": {"name": "张先生", "vipLevel": "普通会员", "sentiment": "neutral"},
    "frustrated": {"name": "李先生", "vipLevel": "钻石会员", "sentiment": "frustrated"},
}

# 预设自测题
BENCHMARKS = [
    ("7天无理由退货", "我刚收到商品不喜欢，可以在7天内申请无理由退货吗？运费谁出？"),
    ("黄金会员免运费", "我是黄金会员，退货的话运费平台会补贴吗？"),
    ("生鲜定制不可退", "我买的刻字定制水杯和生鲜水果能申请7天无理由退货吗？"),
    ("退款到账时效", "退货寄回去之后，仓库几天能质检完？退款多久能到账？"),
    ("转人工投诉", "太慢了！你们到底什么服务态度，马上给我转人工客服主管！"),
    ("保修换新条款", "买的蓝牙耳机用了10天充不进电了，可以免费换新吗？"),
]


@cl.on_chat_start
async def on_chat_start():
    """对话初始化：加载知识库，设置会话及快捷自测按钮"""
    qdrant_store.init_collection_with_faq()

    profile = PROFILES["vip"]
    cl.user_session.set("user_profile", profile)
    cl.user_session.set("session_id", f"cl_{int(time.time())}")

    welcome = (
        "### 🚀 IntelliServe 智能客服自测台\n"
        f"- 当前测试客户：`{profile['name']}`（**{profile['vipLevel']}**）\n"
        "- 底层架构：**LangGraph + Qdrant + DeepSeek**\n\n"
        "你可以直接在下方输入框提问，或点击预设快捷用例进行测试："
    )

    actions = [
        cl.Action(name="test_preset", payload={"query": query}, label=f"🧪 {label}")
        for label, query in BENCHMARKS
    ]
    actions.append(cl.Action(name="switch_profile", payload={}, label="👤 切换会员画像"))

    await cl.Message(content=welcome, actions=actions).send()


@cl.action_callback("test_preset")
async def on_test_preset(action: cl.Action):
    """点击预设测试题目"""
    await handle_chat(action.payload.get("query", ""))


@cl.action_callback("switch_profile")
async def on_switch_profile(action: cl.Action):
    """切换模拟客户画像（黄金 -> 普通 -> 钻石 -> 黄金）"""
    curr = cl.user_session.get("user_profile", PROFILES["vip"])
    cycle = {"黄金会员": PROFILES["normal"], "普通会员": PROFILES["frustrated"], "钻石会员": PROFILES["vip"]}
    new_profile = cycle.get(curr.get("vipLevel", ""), PROFILES["vip"])

    cl.user_session.set("user_profile", new_profile)
    await cl.Message(content=f"🔄 已切换客户画像：`{new_profile['name']}`（**{new_profile['vipLevel']}**）").send()


@cl.on_message
async def on_message(message: cl.Message):
    """接收用户输入消息"""
    await handle_chat(message.content)


async def handle_chat(user_input: str):
    """执行 LangGraph 客服状态图并输出结果与知识链路"""
    session_id = cl.user_session.get("session_id", "cl_default")
    profile = cl.user_session.get("user_profile", PROFILES["vip"])

    initial_state = {
        "session_id": session_id,
        "user_message": user_input,
        "intent": "待识别",
        "sentiment": "neutral",
        "explicit_human_request": False,
        "retrieved_docs": [],
        "top_similarity_score": 0.0,
        "user_profile": profile,
        "summary_memory": f"客户是{profile.get('vipLevel', '普通会员')}。",
        "assembled_prompt": "",
        "generated_response": "",
        "escalated_to_human": False,
        "escalation_reason": "",
        "step_trace": [],
    }

    t0 = time.time()
    async with cl.Step(name="LangGraph Pipeline", type="run") as step:
        step.input = user_input
        state = await customer_service_graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": session_id}}
        )
        docs = state.get("retrieved_docs", [])
        top_score = state.get("top_similarity_score", 0.0)
        step.output = (
            f"意图: {state.get('intent')} | 情绪: {state.get('sentiment')}\n"
            f"召回知识: {len(docs)} 篇 (最高得分: {top_score:.3f})\n"
            f"人工转接: {'是' if state.get('escalated_to_human') else '否'}"
        )

    latency = int((time.time() - t0) * 1000)
    reply = state.get("generated_response", "抱歉，暂未查询到相关政策。")
    is_escalated = state.get("escalated_to_human", False)

    elements = []
    if docs:
        docs_text = "\n\n".join(
            f"**[{i}] {d.get('title', '相关条款')}**\n- 分类: `{d.get('category', '常规')}`\n- 正文: {d.get('content')}"
            for i, d in enumerate(docs, 1)
        )
        elements.append(cl.Text(name="Qdrant 匹配条款", content=docs_text, display="side"))

    tag = "🚨 已转接人工客服" if is_escalated else "🤖 AI 自动回复"
    header = f"> **{tag}** | 意图: `{state.get('intent')}` | 耗时: `{latency}ms`\n\n"

    await cl.Message(content=header + reply, elements=elements).send()
