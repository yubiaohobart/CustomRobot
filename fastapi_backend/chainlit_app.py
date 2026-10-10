"""
IntelliServe 智能客服 Chainlit 对话自测客户端
支持全链路：
1. 🤖 AI 自主接待 (LangGraph + Qdrant 知识召回 + DeepSeek 生成)
2. 🎧 人工客服服务与人机双向协同沟通 (转人工接管、坐席快捷回复、Copilot 话术生成、交接快照工单)
3. 🔁 双向角色自测：既能作为客户提问，也能作为人工坐席回复（/agent 消息 或 点击快捷话术）
"""

import os
import time
from typing import Dict, Any, Tuple, Optional
import httpx
import chainlit as cl

# 彻底禁用系统/环境代理拦截（macOS Clash/Surge 等常见代理）
os.environ["NO_PROXY"] = "127.0.0.1,localhost,0.0.0.0"
os.environ["no_proxy"] = "127.0.0.1,localhost,0.0.0.0"
for proxy_key in ["HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(proxy_key, None)

DEFAULT_PORT = 8000
_raw_backend_url = os.getenv("BACKEND_URL", f"http://127.0.0.1:{DEFAULT_PORT}").rstrip("/")
DEFAULT_BACKEND_URL = "http://127.0.0.1:8000" if ":5000" in _raw_backend_url else _raw_backend_url

# 预设测试画像
PROFILES: Dict[str, Dict[str, Any]] = {
    "vip": {"userName": "王女士", "tier": "GOLD", "vipLevel": "黄金会员"},
    "normal": {"userName": "张先生", "tier": "NORMAL", "vipLevel": "普通会员"},
    "frustrated": {"userName": "李先生", "tier": "DIAMOND", "vipLevel": "钻石会员"},
}

# 预设自测典型用例
BENCHMARKS = [
    ("📦 订单物流追踪", "帮我查一下订单 ORD-2026-88992 的最新物流状态到哪了？还能申请退货吗？"),
    ("7天无理由退货", "我刚收到商品不喜欢，可以在7天内申请无理由退货吗？运费谁出？"),
    ("黄金会员免运费", "我是黄金会员，退货的话运费平台会补贴吗？"),
    ("生鲜定制不可退", "我买的刻字定制水杯和生鲜水果能申请7天无理由退货吗？"),
    ("退款到账时效", "退货寄回去之后，仓库几天能质检完？退款多久能到账？"),
    ("🎧 申请转人工客服", "你好，我对处理结果不满意，请立刻帮我转接人工客服专员沟通！"),
]

# 坐席预设快捷话术库
AGENT_QUICK_RESPONSES = [
    ("🚚 申请顺丰免费上门取件", "您好，我是售后值班主管张小雅。已为您办理顺丰免费上门取件，快递员今天下午两点将联系您取走包裹，运费由平台先行全额补贴！"),
    ("⚡ 办理极速闪电退款", "王女士您好，鉴于您是优质黄金会员，系统已为您开启极速退款绿色通道，款项将在寄出商品后即时冲正到账，请您放心！"),
    ("📦 查询订单并加急催单", "经调阅您关联的订单 ORD-2026-88992，已为您向华东中央售后仓发起加急质检工单，质检工程师将在2小时内出具报告。"),
]


async def probe_backend_endpoint() -> Tuple[str, bool, str]:
    """智能探测可用后端地址，优先 8000 端口，避开 5000 端口 AirPlay 冲突"""
    candidates = []
    if DEFAULT_BACKEND_URL and ":5000" not in DEFAULT_BACKEND_URL:
        candidates.append(DEFAULT_BACKEND_URL)
    for c in ["http://127.0.0.1:8000", "http://localhost:8000"]:
        if c not in candidates:
            candidates.append(c)

    for base_url in candidates:
        try:
            async with httpx.AsyncClient(timeout=1.5, trust_env=False) as client:
                res = await client.get(f"{base_url}/api/health")
                if res.status_code == 200:
                    return base_url, True, "🟢 已就绪 (API 在线)"
                res_chat = await client.get(f"{base_url}/api/chat")
                if res_chat.status_code in (200, 405):
                    return base_url, True, "🟢 已就绪 (API 在线)"
        except Exception:
            continue

    return "http://127.0.0.1:8000", False, "⚠️ 尚未启动 (请在终端执行 python app.py)"


def get_agent_action_buttons() -> list:
    """生成人工坐席互动快捷操作按钮"""
    actions = [
        cl.Action(
            name="agent_quick_reply",
            payload={"text": AGENT_QUICK_RESPONSES[0][1], "label": AGENT_QUICK_RESPONSES[0][0]},
            label=f"💬 {AGENT_QUICK_RESPONSES[0][0]}"
        ),
        cl.Action(
            name="agent_quick_reply",
            payload={"text": AGENT_QUICK_RESPONSES[1][1], "label": AGENT_QUICK_RESPONSES[1][0]},
            label=f"💬 {AGENT_QUICK_RESPONSES[1][0]}"
        ),
        cl.Action(
            name="agent_copilot_reply",
            payload={},
            label="💡 AI Copilot 推荐话术"
        ),
        cl.Action(
            name="view_handover",
            payload={},
            label="📋 查看交接单工单"
        ),
        cl.Action(
            name="release_to_ai",
            payload={},
            label="🤖 切回 AI 智能接待"
        ),
    ]
    return actions


@cl.on_chat_start
async def on_chat_start():
    """对话初始化：探测后端、初始化会话，展示快捷操作卡片"""
    session_id = f"cl_{int(time.time())}"
    profile = PROFILES["vip"]
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("user_profile", profile)
    cl.user_session.set("is_human_mode", False)
    cl.user_session.set("assigned_agent", None)

    target_url, is_online, status_text = await probe_backend_endpoint()
    cl.user_session.set("backend_url", target_url)

    if is_online:
        status_banner = f"> **服务状态**: {status_text} | 目标地址: `{target_url}`\n\n"
    else:
        status_banner = (
            f"> **服务状态**: {status_text}\n"
            f"> 💡 提示：若尚未启动后端，请先在另一个终端窗口运行：\n"
            f"> ```bash\n> cd fastapi_backend\n> python app.py\n> ```\n\n"
        )

    welcome_md = (
        f"### 🚀 IntelliServe 智能客服自测工作台 (人机协同版)\n"
        f"- **测试会话 ID**: `{session_id}`\n"
        f"- **当前模拟客户**: `{profile['userName']}` ({profile['vipLevel']})\n"
        f"- **当前服务模式**: `🤖 AI 智能客服自动接待`\n"
        f"- **双向自测支持**: 支持客户提问，随时一键 **转人工客服**，并可使用 `/agent <回复>` 模拟坐席实时对话！\n\n"
        f"{status_banner}"
        "点击下方常用用例一键测试，或直接输入售后问题开始自测："
    )

    actions = [
        cl.Action(name="test_preset", payload={"query": query}, label=f"🧪 {label}")
        for label, query in BENCHMARKS
    ]
    actions.append(cl.Action(name="transfer_human", payload={}, label="🎧 立即转人工客服"))
    actions.append(cl.Action(name="switch_profile", payload={}, label="👤 切换会员画像"))

    await cl.Message(content=welcome_md, actions=actions).send()


@cl.action_callback("test_preset")
async def on_test_preset(action: cl.Action):
    """点击预设测试问题按钮"""
    query = ""
    if hasattr(action, "payload") and isinstance(action.payload, dict):
        query = action.payload.get("query", "")
    elif hasattr(action, "value") and action.value:
        query = str(action.value)
    
    if query:
        await handle_user_input(query)


@cl.action_callback("switch_profile")
async def on_switch_profile(action: cl.Action):
    """切换测试客户画像 (普通 / 黄金 / 钻石会员)"""
    curr = cl.user_session.get("user_profile", PROFILES["vip"])
    cycle = {
        "黄金会员": PROFILES["normal"],
        "普通会员": PROFILES["frustrated"],
        "钻石会员": PROFILES["vip"]
    }
    new_profile = cycle.get(curr.get("vipLevel", ""), PROFILES["vip"])
    cl.user_session.set("user_profile", new_profile)
    await cl.Message(
        content=f"🔄 **已切换客户画像**：`{new_profile['userName']}`（**{new_profile['vipLevel']}**）"
    ).send()


@cl.action_callback("transfer_human")
async def on_transfer_human(action: cl.Action):
    """主动转接人工客服"""
    await trigger_human_escalation("客户在界面主动申请人工客服接入")


@cl.action_callback("release_to_ai")
async def on_release_to_ai(action: cl.Action):
    """人工坐席将对话交还给 AI 智能客服"""
    session_id = cl.user_session.get("session_id")
    backend_url = cl.user_session.get("backend_url", DEFAULT_BACKEND_URL)
    
    try:
        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
            await client.post(
                f"{backend_url}/api/sessions/{session_id}/intervene",
                json={"action": "release", "note": "Chainlit 自测客户端释放回 AI"}
            )
    except Exception as e:
        pass

    cl.user_session.set("is_human_mode", False)
    cl.user_session.set("assigned_agent", None)

    actions = [
        cl.Action(name="test_preset", payload={"query": BENCHMARKS[0][1]}, label="🧪 继续提问测试"),
        cl.Action(name="transfer_human", payload={}, label="🎧 重新转接人工")
    ]

    await cl.Message(
        content="🤖 **【服务模式切换】已交还 AI 智能客服接待**\n\n人工坐席已退出本次会话，当前已由 AI 智能客服继续为您提供 7x24 小时服务。您可以继续正常提问！",
        actions=actions
    ).send()


@cl.action_callback("agent_quick_reply")
async def on_agent_quick_reply(action: cl.Action):
    """坐席快捷回复点击"""
    text = ""
    if hasattr(action, "payload") and isinstance(action.payload, dict):
        text = action.payload.get("text", "")
    elif hasattr(action, "value") and action.value:
        text = str(action.value)

    if text:
        await send_human_agent_reply(text)


@cl.action_callback("agent_copilot_reply")
async def on_agent_copilot_reply(action: cl.Action):
    """请求后端 Copilot 生成推荐话术并由坐席发出"""
    session_id = cl.user_session.get("session_id")
    backend_url = cl.user_session.get("backend_url", DEFAULT_BACKEND_URL)

    async with cl.Step(name="AI Copilot 智能话术推荐", type="llm") as step:
        step.input = f"基于会话 {session_id} 的历史咨询，为人工坐席推荐最佳答复草稿"
        suggestion = "您好！我是值班客服专员。我已经全面了解您的诉求，已为您提交平台极速审核流程，稍后会短信通知您最新处理进度！"
        try:
            async with httpx.AsyncClient(timeout=8.0, trust_env=False) as client:
                res = await client.post(
                    f"{backend_url}/api/generate-suggestion",
                    json={"sessionId": session_id}
                )
                if res.status_code == 200:
                    data = res.json()
                    suggestion = data.get("suggestion", suggestion)
                    step.output = f"命中参考条款: {', '.join(data.get('matchedClauses', []))}\n推荐草稿: {suggestion}"
        except Exception as e:
            step.output = f"请求降级默认推荐: {e}"

    await send_human_agent_reply(suggestion)


@cl.action_callback("view_handover")
async def on_view_handover(action: cl.Action):
    """查看转接上下文快照与工单"""
    session_id = cl.user_session.get("session_id")
    backend_url = cl.user_session.get("backend_url", DEFAULT_BACKEND_URL)

    snapshot_md = "⚠️ 暂未查询到工单快照信息。"
    try:
        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
            res = await client.get(f"{backend_url}/api/sessions/{session_id}")
            if res.status_code == 200:
                s = res.json().get("session", {})
                snap = s.get("contextSnapshot")
                if snap:
                    snapshot_md = (
                        f"### 📋 人工客服交接工单快照 [{snap.get('snapshotId', 'TRF-001')}]\n\n"
                        f"- **状态**: **{s.get('status', 'HUMAN_INTERVENED')}**\n"
                        f"- **责任坐席**: **{snap.get('targetAgentName', '张小雅')}** (工号: `{snap.get('targetAgentId', 'agent_101')}`)\n"
                        f"- **转接原因**: `{snap.get('reason', '客户申请转人工')}`\n"
                        f"- **转接时间**: `{snap.get('createdAt', '')}`\n"
                        f"- **对话轮数**: `{snap.get('dialogueRounds', 0)}` 轮\n"
                        f"- **客户画像**: {snap.get('customerProfile', {}).get('name', '客户')} ({snap.get('customerProfile', {}).get('vipLevel', '普通会员')})\n\n"
                        f"#### 🧠 会话记忆摘要\n> {snap.get('summaryMemory', '无')}\n\n"
                        f"#### 💡 推荐开场白\n> {snap.get('suggestedGreeting', '您好，值班客服为您服务！')}"
                    )
                else:
                    snapshot_md = (
                        f"### 📋 会话状态 [{s.get('id', session_id)}]\n\n"
                        f"- **状态**: **{s.get('status', 'AI_HANDLING')}**\n"
                        f"- **当值坐席**: {s.get('assignedAgent', '暂未分配')}\n"
                        f"- **消息总数**: {len(s.get('messages', []))} 条\n"
                        f"- **记忆摘要**: {s.get('summaryMemory', '无')}"
                    )
    except Exception as e:
        snapshot_md = f"查询失败: {e}"

    await cl.Message(
        content=snapshot_md,
        elements=[cl.Text(name="工单详情", content=snapshot_md, display="side")]
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    """用户在输入框键入消息"""
    user_text = (message.content or "").strip()
    if not user_text:
        return

    # 命令分发
    if user_text.startswith("/agent ") or user_text.startswith("/kefu ") or user_text.startswith("/坐席 "):
        parts = user_text.split(" ", 1)
        agent_reply_text = parts[1].strip() if len(parts) > 1 else ""
        if agent_reply_text:
            await send_human_agent_reply(agent_reply_text)
            return
    elif user_text in ["/ai", "/reset", "/退出人工", "/返回ai"]:
        await on_release_to_ai(cl.Action(name="release_to_ai", payload={}))
        return
    elif user_text in ["/human", "/人工", "/转人工"]:
        await trigger_human_escalation("用户输入命令转接人工客服")
        return
    elif user_text in ["/status", "/工单", "/快照"]:
        await on_view_handover(cl.Action(name="view_handover", payload={}))
        return

    await handle_user_input(user_text)


async def send_human_agent_reply(reply_text: str):
    """以人工坐席身份向客户发送回复"""
    session_id = cl.user_session.get("session_id", f"cl_{int(time.time())}")
    backend_url = cl.user_session.get("backend_url", DEFAULT_BACKEND_URL)
    agent_info = cl.user_session.get("assigned_agent") or {
        "id": "agent_101",
        "name": "张小雅",
        "title": "金牌客服专员",
        "skill": "退换货疑难 / VIP加急"
    }

    t0 = time.time()
    async with cl.Step(name=f"👨‍💼 人工坐席 [{agent_info['name']}] 回复客户", type="run") as step:
        step.input = reply_text
        try:
            async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
                res = await client.post(
                    f"{backend_url}/api/sessions/{session_id}/human-message",
                    json={
                        "message": reply_text,
                        "agentId": agent_info["id"],
                        "agentName": agent_info["name"]
                    }
                )
                if res.status_code == 200:
                    step.output = f"HTTP 200 OK | 消息已成功同步至后端会话记忆库 (耗时 {int((time.time()-t0)*1000)}ms)"
                else:
                    step.output = f"HTTP {res.status_code}: {res.text}"
        except Exception as e:
            step.output = f"请求后端异常: {e}"

    agent_card_md = (
        f"> 👨‍💼 **人工客服在线** | 坐席: **{agent_info['name']}** (工号: `{agent_info['id']}`) | 岗位: `{agent_info['title']}`\n\n"
        f"{reply_text}"
    )

    await cl.Message(
        content=agent_card_md,
        actions=get_agent_action_buttons()
    ).send()


async def trigger_human_escalation(reason: str):
    """执行转接人工客服全流程：调用后端 transfer 接口、冻结上下文、切换会话模式"""
    session_id = cl.user_session.get("session_id", f"cl_{int(time.time())}")
    backend_url = cl.user_session.get("backend_url", DEFAULT_BACKEND_URL)
    profile = cl.user_session.get("user_profile", PROFILES["vip"])

    agent_info = {
        "id": "agent_101",
        "name": "张小雅",
        "title": "金牌客服专员",
        "skill": "退换货疑难与退款加速",
        "rating": "4.98 ★"
    }
    cl.user_session.set("assigned_agent", agent_info)
    cl.user_session.set("is_human_mode", True)

    async with cl.Step(name="触发人工转接与工单快照冻结", type="tool") as step:
        step.input = f"会话 ID: {session_id} | 触发原因: {reason}"
        try:
            async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
                res = await client.post(
                    f"{backend_url}/api/sessions/{session_id}/transfer",
                    json={
                        "targetAgentId": agent_info["id"],
                        "reason": reason,
                        "operatorNote": f"Chainlit 自测请求，客户 {profile['userName']}({profile['vipLevel']})",
                        "triggerType": "user_escalated"
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    step.output = f"✅ 转接成功！已冻结快照，指派坐席: {agent_info['name']} (工号 {agent_info['id']})"
                else:
                    step.output = f"HTTP {res.status_code}: {res.text}"
        except Exception as e:
            step.output = f"转接本地自愈接管: {e}"

    escalation_banner = (
        f"### 🎧【人工客服服务专线已接通】\n\n"
        f"您好，**{profile['userName']}**！由于您需要人工协助，系统已为您无缝接入值班人工客服：\n\n"
        f"- **当值坐席**: **{agent_info['name']}**（工号: `{agent_info['id']}`）\n"
        f"- **专业资质**: `{agent_info['title']}` | 好评率: `{agent_info['rating']}`\n"
        f"- **专长领域**: `{agent_info['skill']}`\n"
        f"- **交接状态**: 对话历史、Qdrant 检索记录与会员权益已完整同步至坐席工作台。\n\n"
        f"---\n"
        f"💬 **坐席开场白**: *“您好！我是值班专员{agent_info['name']}，您的咨询快照我已经全面调阅，请问有什么可以全力协助您的？”*\n\n"
        f"> 💡 **人机沟通双向测试指南**：\n"
        f"> 1. **作为客户**：在下方直接输入您的问题，人工坐席将实时为您协同跟进；\n"
        f"> 2. **作为坐席**：可输入 `/agent <回复内容>` 发送坐席答复，或直接点击下方【坐席快捷回复】按钮！"
    )

    await cl.Message(
        content=escalation_banner,
        actions=get_agent_action_buttons()
    ).send()


async def handle_user_input(user_input: str):
    """处理用户输入消息（根据当前会话模式智能流转）"""
    is_human_mode = cl.user_session.get("is_human_mode", False)
    session_id = cl.user_session.get("session_id", f"cl_{int(time.time())}")
    backend_url = cl.user_session.get("backend_url", DEFAULT_BACKEND_URL)
    profile = cl.user_session.get("user_profile", PROFILES["vip"])

    # 检查用户是否主动要求转人工
    human_keywords = ["转人工", "人工客服", "找人工", "人工服务", "人工主管", "我要人工", "找真人"]
    if any(k in user_input for k in human_keywords):
        await trigger_human_escalation(f"客户输入 '{user_input}' 主动请求转人工")
        return

    # 处于人工坐席模式下的双向沟通
    if is_human_mode:
        agent_info = cl.user_session.get("assigned_agent") or {"name": "张小雅", "id": "agent_101"}
        
        async with cl.Step(name="客户消息同步至坐席工作台", type="run") as step:
            step.input = user_input
            # 同步客户消息至后端会话
            try:
                async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
                    await client.post(
                        f"{backend_url}/api/chat",
                        json={
                            "sessionId": session_id,
                            "message": user_input,
                            "userProfile": profile
                        }
                    )
                step.output = f"已推送到坐席工作台（坐席: {agent_info['name']}）"
            except Exception as e:
                step.output = f"已暂存: {e}"

        # 智能生成坐席应答建议，模拟两方实时对话交互
        async with cl.Step(name=f"坐席工作台实时推演回复", type="tool") as agent_step:
            agent_step.input = f"坐席 {agent_info['name']} 正在处理客户诉求: '{user_input}'"
            simulated_reply = f"您好，针对您提到的“{user_input}”，我已在售后系统为您开辟绿色处理通道，请您稍候片刻！"
            try:
                async with httpx.AsyncClient(timeout=8.0, trust_env=False) as client:
                    sugg_res = await client.post(
                        f"{backend_url}/api/generate-suggestion",
                        json={"sessionId": session_id}
                    )
                    if sugg_res.status_code == 200:
                        simulated_reply = sugg_res.json().get("suggestion", simulated_reply)
                        agent_step.output = "已通过 Copilot 生成坐席回复建议并自动发送"
            except Exception:
                agent_step.output = "使用坐席标准专业应答"

        # 展现人工坐席回复
        await send_human_agent_reply(simulated_reply)
        return

    # 正常 AI 模式：向 FastAPI 后端 /api/chat 发起请求
    payload = {
        "sessionId": session_id,
        "message": user_input,
        "userProfile": profile
    }

    t0 = time.time()
    data = None

    async with cl.Step(name=f"HTTP POST {backend_url}/api/chat", type="run") as step:
        step.input = user_input
        
        client_candidates = [backend_url]
        if backend_url != "http://127.0.0.1:8000":
            client_candidates.append("http://127.0.0.1:8000")
        if "http://localhost:8000" not in client_candidates:
            client_candidates.append("http://localhost:8000")

        last_error = None
        for target in client_candidates:
            try:
                async with httpx.AsyncClient(timeout=35.0, trust_env=False) as client:
                    res = await client.post(f"{target}/api/chat", json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        if target != backend_url:
                            cl.user_session.set("backend_url", target)
                            backend_url = target
                        step.output = (
                            f"HTTP 200 OK | 后端总耗时: {data.get('latencyMs', 0)}ms\n"
                            f"识别意图: {data.get('intent')} | 情绪感知: {data.get('sentiment')}\n"
                            f"人工接管: {data.get('escalatedToHuman')}"
                        )
                        break
                    else:
                        last_error = f"HTTP {res.status_code}: {res.text}"
            except httpx.ConnectError:
                last_error = f"无法连接到后端 {target} (ConnectError)"
            except Exception as e:
                last_error = str(e)

        if not data:
            step.output = f"请求失败: {last_error}"
            err_msg = (
                f"⚠️ **无法连接到 FastAPI 后端服务**\n\n"
                f"- **尝试目标**: `http://127.0.0.1:8000/api/chat`\n"
                f"- **错误详情**: `{last_error}`\n\n"
                f"### 💡 请检查后端服务是否启动：\n"
                f"1. 打开终端，进入后端目录：\n"
                f"   ```bash\n"
                f"   cd fastapi_backend\n"
                f"   python app.py\n"
                f"   ```\n"
                f"2. 确保终端输出包含 `服务监听地址: http://0.0.0.0:8000`；\n"
                f"3. 启动完成后，直接重新发送消息即可自测成功！"
            )
            await cl.Message(content=err_msg).send()
            return

    # 展示后端 LangGraph 执行返回的 stepTrace 状态流转轨迹
    traces = data.get("stepTrace", [])
    if traces:
        async with cl.Step(name="后端 LangGraph 状态图流转轨迹", type="tool") as trace_step:
            trace_logs = [
                f"• **[{tr.get('node', 'Node')}]** ({tr.get('durationMs', 0)}ms): {tr.get('description', '')}"
                for tr in traces
            ]
            trace_step.output = "\n".join(trace_logs)

    # 侧边栏展示后端检索召回的知识库条款与订单卡片
    refs = data.get("references", [])
    order_info = data.get("queriedOrder")
    elements = []

    if order_info:
        items_str = "\n".join([f"- **{it['title']}** (¥{it['price']} x{it['quantity']})" for it in order_info.get("items", [])])
        express = order_info.get("express", {})
        timeline_str = "\n".join([f"- `{t.get('time', '')}`: {t.get('context', '')}" for t in express.get("timeline", [])[:3]])
        after_sale = order_info.get("afterSales", {})
        
        order_md = (
            f"### 📦 关联订单详情 [{order_info.get('orderId')}]\n\n"
            f"- **当前状态**: **【{order_info.get('statusText', '已签收')}】**\n"
            f"- **买家姓名**: {order_info.get('userName')} ({order_info.get('vipLevel')})\n"
            f"- **实付金额**: ¥{order_info.get('paidAmount', 0):.2f}\n"
            f"- **物流公司**: {express.get('company', '顺丰速运')} (单号: `{express.get('trackingNumber', '')}`)\n\n"
            f"#### 🛍️ 购买商品\n{items_str}\n\n"
            f"#### 🚚 最新物流轨迹\n{timeline_str}\n\n"
            f"#### 🛡️ 售后权益\n"
            f"- **7天退换**: {'支持 (剩余 ' + str(after_sale.get('returnDaysRemaining', 0)) + ' 天)' if after_sale.get('canReturn7Days') else '不支持 (' + after_sale.get('returnPolicy', '') + ')'}\n"
            f"- **运费政策**: {after_sale.get('shippingSubsidy', '')}\n"
            f"- **保修条款**: {after_sale.get('warrantyPolicy', '')}\n"
        )
        elements.append(cl.Text(name="📦 订单与物流卡片", content=order_md, display="side"))

    if refs:
        refs_content = "### 📚 Qdrant 检索知识条款 (后端实时召回)\n\n" + "\n\n".join(
            f"**[{i}] {r.get('title', '知识点')}** (匹配度: {r.get('score', 0):.2f})\n> {r.get('snippet', '')}"
            for i, r in enumerate(refs, 1)
        )
        elements.append(cl.Text(name="知识库引用条款", content=refs_content, display="side"))

    # 状态头与最终答复
    escalated = data.get("escalatedToHuman", False)
    badge = "🚨 建议转接人工客服" if escalated else "🤖 AI 自动回复"
    latency = data.get("latencyMs", int((time.time() - t0) * 1000))
    info_header = (
        f"> **{badge}** | 意图: `{data.get('intent')}` | "
        f"情绪: `{data.get('sentiment')}` | 耗时: `{latency}ms`\n\n"
    )

    actions = []
    if escalated:
        actions.append(cl.Action(name="transfer_human", payload={}, label="🎧 立即接入人工客服"))
        actions.append(cl.Action(name="test_preset", payload={"query": BENCHMARKS[0][1]}, label="🧪 测试其他用例"))
    else:
        actions.append(cl.Action(name="transfer_human", payload={}, label="🎧 转人工客服"))

    await cl.Message(
        content=info_header + data.get("reply", ""),
        elements=elements,
        actions=actions
    ).send()

    # 若情绪激烈且自动触发升级，则提示转人工
    if escalated:
        await trigger_human_escalation(data.get("escalationReason") or "智能风控检测到客户情绪激烈或强烈人工诉求")
