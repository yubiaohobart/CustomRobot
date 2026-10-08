"""
IntelliServe 智能客服 Chainlit 对话自测客户端
通过 HTTP 与 FastAPI 后端 (/api/chat) 进行全链路交互自测
内置 macOS 端口 5000 (AirPlay Receiver 502) 智能避障与自动端口探测
"""

import os
import time
import httpx
import chainlit as cl

# 动态读取 FastAPI 后端基础配置（默认 8000，避开 macOS 5000 端口 AirPlay 冲突）
try:
    from config import settings
    _DEFAULT_PORT = settings.FASTAPI_PORT
except Exception:
    _DEFAULT_PORT = 8000

DEFAULT_BACKEND_URL = os.getenv("BACKEND_URL", f"http://127.0.0.1:{_DEFAULT_PORT}")

# 预设测试画像
PROFILES = {
    "vip": {"userName": "王女士", "tier": "GOLD", "vipLevel": "黄金会员"},
    "normal": {"userName": "张先生", "tier": "NORMAL", "vipLevel": "普通会员"},
    "frustrated": {"userName": "李先生", "tier": "DIAMOND", "vipLevel": "钻石会员"},
}

BENCHMARKS = [
    ("7天无理由退货", "我刚收到商品不喜欢，可以在7天内申请无理由退货吗？运费谁出？"),
    ("黄金会员免运费", "我是黄金会员，退货的话运费平台会补贴吗？"),
    ("生鲜定制不可退", "我买的刻字定制水杯和生鲜水果能申请7天无理由退货吗？"),
    ("退款到账时效", "退货寄回去之后，仓库几天能质检完？退款多久能到账？"),
    ("转人工投诉", "太慢了！你们到底什么服务态度，马上给我转人工客服主管！"),
]


async def probe_backend_endpoints():
    """
    智能探测可用后端地址，自动避开 macOS AirPlay 5000 端口冲突
    """
    explicit = os.getenv("BACKEND_URL")
    candidates = []
    if explicit:
        candidates.append(explicit.rstrip("/"))
    
    for c in [f"http://127.0.0.1:{_DEFAULT_PORT}", "http://127.0.0.1:8000", "http://localhost:8000", "http://127.0.0.1:5000"]:
        if c not in candidates:
            candidates.append(c)

    airplay_5000_conflict = False

    # 优先检测候选地址
    for url in candidates:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{url}/api/health")
                if resp.status_code == 200:
                    return url, "🟢 已就绪 (API 在线)", airplay_5000_conflict
                elif resp.status_code == 502 and "5000" in url:
                    airplay_5000_conflict = True
        except Exception:
            continue

    # 检查 5000 是否是 AirPlay 占用
    if not airplay_5000_conflict:
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                r5000 = await client.get("http://127.0.0.1:5000/api/health")
                if r5000.status_code == 502:
                    airplay_5000_conflict = True
        except Exception:
            pass

    preferred = candidates[0] if "5000" not in candidates[0] else "http://127.0.0.1:8000"
    return preferred, "⚠️ 尚未启动 (请确保先运行 python app.py)", airplay_5000_conflict


@cl.on_chat_start
async def on_chat_start():
    """对话初始化：探测 FastAPI 后端健康状态并展示快捷操作"""
    session_id = f"cl_{int(time.time())}"
    profile = PROFILES["vip"]
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("user_profile", profile)

    # 智能探测后端地址
    active_url, backend_status, airplay_warning = await probe_backend_endpoints()
    cl.user_session.set("backend_url", active_url)

    warning_block = ""
    if airplay_warning:
        warning_block = (
            "> ⚠️ **macOS 端口 5000 冲突提醒**：\n"
            "> 检测到 `http://127.0.0.1:5000` 返回 **502 Bad Gateway**！\n"
            "> 这是因为 **macOS 系统的「隔空播放接收器 (AirPlay Receiver)」** 默认独占了 5000 端口，并非程序错误。\n"
            "> 💡 **本客户端已自动将目标后端切换为标准端口 `8000`**，请在终端执行 `python app.py` 启动后端！\n\n"
        )

    welcome = (
        f"### 🚀 IntelliServe 智能客服自测端 (HTTP 交互模式)\n"
        f"- **后端目标接口**: `{active_url}/api/chat` ({backend_status})\n"
        f"- **当前测试客户**: `{profile['userName']}` ({profile['vipLevel']})\n"
        f"- **测试会话 ID**: `{session_id}`\n\n"
        f"{warning_block}"
        "本客户端直接通过 HTTP 调用 FastAPI 真实业务接口，全面验证**路由分发、LangGraph 编排、Qdrant 向量检索与 DeepSeek 回复**："
    )

    actions = [
        cl.Action(name="test_preset", payload={"query": q}, label=f"🧪 {lbl}")
        for lbl, q in BENCHMARKS
    ]
    actions.append(cl.Action(name="switch_profile", payload={}, label="👤 切换会员画像"))

    await cl.Message(content=welcome, actions=actions).send()


@cl.action_callback("test_preset")
async def on_test_preset(action: cl.Action):
    """点击预设测试问题"""
    await handle_chat(action.payload.get("query", ""))


@cl.action_callback("switch_profile")
async def on_switch_profile(action: cl.Action):
    """切换测试客户画像"""
    curr = cl.user_session.get("user_profile", PROFILES["vip"])
    cycle = {"黄金会员": PROFILES["normal"], "普通会员": PROFILES["frustrated"], "钻石会员": PROFILES["vip"]}
    new_profile = cycle.get(curr.get("vipLevel", ""), PROFILES["vip"])
    cl.user_session.set("user_profile", new_profile)
    await cl.Message(content=f"🔄 已切换客户画像：`{new_profile['userName']}`（**{new_profile['vipLevel']}**）").send()


@cl.on_message
async def on_message(message: cl.Message):
    """在对话框输入消息时发送给后端"""
    await handle_chat(message.content)


async def handle_chat(user_input: str):
    """向 FastAPI 后端 /api/chat 发起 HTTP 请求，并展示结果与状态机链路"""
    session_id = cl.user_session.get("session_id", "cl_default")
    profile = cl.user_session.get("user_profile", PROFILES["vip"])
    backend_url = cl.user_session.get("backend_url", DEFAULT_BACKEND_URL)

    payload = {
        "sessionId": session_id,
        "message": user_input,
        "userProfile": profile
    }

    t0 = time.time()
    data = None

    async with cl.Step(name=f"HTTP POST {backend_url}/api/chat", type="run") as step:
        step.input = user_input
        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                res = await client.post(f"{backend_url}/api/chat", json=payload)

                # 处理 502 Bad Gateway 特殊情况（常见于 macOS 5000 端口 AirPlay 拦截）
                if res.status_code == 502:
                    # 尝试自动降级/重定向至 8000 端口
                    if "5000" in backend_url:
                        alt_url = "http://127.0.0.1:8000"
                        try:
                            alt_res = await client.post(f"{alt_url}/api/chat", json=payload)
                            if alt_res.status_code == 200:
                                cl.user_session.set("backend_url", alt_url)
                                backend_url = alt_url
                                res = alt_res
                        except Exception:
                            pass

                if res.status_code != 200:
                    step.output = f"后端响应异常: HTTP {res.status_code} - {res.text}"
                    if res.status_code == 502 and "5000" in backend_url:
                        err_msg = (
                            "❌ **HTTP 502 Bad Gateway (macOS AirPlay 端口冲突)**\n\n"
                            "### 🔍 为什么会返回 502？\n"
                            "在 **macOS** 系统中，**端口 5000 默认被系统的「隔空播放接收器 (AirPlay Receiver)」占用**。\n"
                            "当 Chainlit 请求 `http://127.0.0.1:5000` 时，请求直接被 macOS 系统接收并拒绝，因此返回了 `502 Bad Gateway`！FastAPI 并没有收到请求。\n\n"
                            "### 💡 解决方案（任选一种）：\n"
                            "1. **切换至 8000 端口运行后端（推荐）**：\n"
                            "   ```bash\n"
                            "   cd fastapi_backend\n"
                            "   python app.py\n"
                            "   ```\n"
                            "   （当前系统代码已将默认端口调整为 8000，运行 `python app.py` 将自动使用 8000 端口）\n\n"
                            "2. **关闭 macOS 隔空播放占用**：\n"
                            "   打开 Mac「系统设置」→「通用」→「隔空投送与隔空播放」→ 关闭「隔空播放接收器」。\n"
                        )
                    else:
                        err_msg = f"❌ **请求失败**: HTTP {res.status_code}\n```{res.text}```"
                    await cl.Message(content=err_msg).send()
                    return

                data = res.json()
                step.output = (
                    f"HTTP 200 OK | 后端总耗时: {data.get('latencyMs', 0)}ms\n"
                    f"识别意图: {data.get('intent')} | 情绪感知: {data.get('sentiment')}\n"
                    f"人工接管: {data.get('escalatedToHuman')}"
                )
        except httpx.ConnectError:
            step.output = f"连接失败: 无法连接至 {backend_url}"
            await cl.Message(
                content=(
                    f"⚠️ **无法连接到 FastAPI 后端服务 (`{backend_url}`)**\n\n"
                    f"请先打开另一个终端窗口，进入 `fastapi_backend/` 目录启动后端：\n"
                    f"```bash\ncd fastapi_backend\npython app.py\n```\n"
                    f"后端启动就绪后（端口 8000），点击用例或发送消息即可正常自测！"
                )
            ).send()
            return
        except Exception as e:
            step.output = f"请求异常: {str(e)}"
            await cl.Message(content=f"❌ **发生异常**: {str(e)}").send()
            return

    # 展示后端 LangGraph 执行返回的 stepTrace 节点链路
    traces = data.get("stepTrace", [])
    if traces:
        async with cl.Step(name="后端 LangGraph 状态图流转轨迹", type="tool") as trace_step:
            trace_logs = [
                f"• **[{tr.get('node')}]** ({tr.get('durationMs', 0)}ms): {tr.get('description', '')}"
                for tr in traces
            ]
            trace_step.output = "\n".join(trace_logs)

    # 侧边栏展示后端检索召回的知识库条款
    refs = data.get("references", [])
    elements = []
    if refs:
        refs_content = "### 📚 Qdrant 检索条款 (由后端召回)\n\n" + "\n\n".join(
            f"**[{i}] {r.get('title')}** (相似度: {r.get('score')})\n> {r.get('snippet')}"
            for i, r in enumerate(refs, 1)
        )
        elements.append(cl.Text(name="知识库引用条款", content=refs_content, display="side"))

    # 状态头与最终答复
    escalated = data.get("escalatedToHuman", False)
    badge = "🚨 已转接人工客服" if escalated else "🤖 AI 自动回复"
    latency = data.get("latencyMs", int((time.time() - t0) * 1000))
    info_header = f"> **{badge}** | 意图: `{data.get('intent')}` | 情绪: `{data.get('sentiment')}` | 耗时: `{latency}ms`\n\n"

    await cl.Message(content=info_header + data.get("reply", ""), elements=elements).send()
