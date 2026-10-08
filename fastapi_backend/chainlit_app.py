"""
IntelliServe 智能客服 Chainlit 对话自测客户端
通过 HTTP 与 FastAPI 后端 (/api/chat) 进行全链路交互自测
默认连接端口：http://127.0.0.1:8000（严格规避 macOS 5000 端口 AirPlay 502 冲突）
"""

import os
import time
from typing import Dict, Any, Tuple
import httpx
import chainlit as cl

# 关键：彻底禁用系统/环境代理拦截（如 macOS 上的 Clash/Surge/V2Ray 等网络代理工具）
# 代理软件通常会将 localhost/127.0.0.1 转发至本地代理端口（如 7890），从而返回 HTTP 502 Bad Gateway
os.environ["NO_PROXY"] = "127.0.0.1,localhost,0.0.0.0"
os.environ["no_proxy"] = "127.0.0.1,localhost,0.0.0.0"
# 清除当前进程中可能存在的本地代理设置
for proxy_key in ["HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(proxy_key, None)

# 确定 FastAPI 后端基础端口（默认为 8000）
# 注：macOS 系统默认将 5000 端口分配给 AirPlay Receiver（隔空播放），请求 5000 会被系统拦截并返回 502 Bad Gateway
# 因此无论本地配置如何，客户端默认优先直连 8000 端口
DEFAULT_PORT = 8000

# 优先读取环境变量 BACKEND_URL，如果包含 5000 则安全重定向至 8000
_raw_backend_url = os.getenv("BACKEND_URL", f"http://127.0.0.1:{DEFAULT_PORT}").rstrip("/")
if ":5000" in _raw_backend_url:
    DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
else:
    DEFAULT_BACKEND_URL = _raw_backend_url

# 预设测试画像
PROFILES: Dict[str, Dict[str, Any]] = {
    "vip": {"userName": "王女士", "tier": "GOLD", "vipLevel": "黄金会员"},
    "normal": {"userName": "张先生", "tier": "NORMAL", "vipLevel": "普通会员"},
    "frustrated": {"userName": "李先生", "tier": "DIAMOND", "vipLevel": "钻石会员"},
}

# 预设自测典型用例
BENCHMARKS = [
    ("7天无理由退货", "我刚收到商品不喜欢，可以在7天内申请无理由退货吗？运费谁出？"),
    ("黄金会员免运费", "我是黄金会员，退货的话运费平台会补贴吗？"),
    ("生鲜定制不可退", "我买的刻字定制水杯和生鲜水果能申请7天无理由退货吗？"),
    ("退款到账时效", "退货寄回去之后，仓库几天能质检完？退款多久能到账？"),
    ("转人工投诉", "太慢了！你们到底什么服务态度，马上给我转人工客服主管！"),
]


async def probe_backend_endpoint() -> Tuple[str, bool, str]:
    """
    智能探测可用后端地址，优先探测 8000 端口，坚决不主动探测 5000 端口（避免在终端产生无关的 502 日志）
    返回: (目标地址, 是否在线, 提示信息)
    """
    # 候选地址列表：只探测 8000 和自定义非 5000 的地址
    candidates = []
    if DEFAULT_BACKEND_URL and ":5000" not in DEFAULT_BACKEND_URL:
        candidates.append(DEFAULT_BACKEND_URL)
    
    for c in ["http://127.0.0.1:8000", "http://localhost:8000"]:
        if c not in candidates:
            candidates.append(c)

    for base_url in candidates:
        try:
            async with httpx.AsyncClient(timeout=1.5, trust_env=False) as client:
                # 优先请求 /api/health，若 404 则检查 /api/chat
                res = await client.get(f"{base_url}/api/health")
                if res.status_code == 200:
                    return base_url, True, "🟢 已就绪 (API 在线)"
                
                res_chat = await client.get(f"{base_url}/api/chat")
                if res_chat.status_code in (200, 405):  # 200 或 405 说明 FastAPI 路由正常监听
                    return base_url, True, "🟢 已就绪 (API 在线)"
        except Exception:
            continue

    return "http://127.0.0.1:8000", False, "⚠️ 尚未启动 (请在终端执行 python app.py)"


@cl.on_chat_start
async def on_chat_start():
    """对话初始化：探测 FastAPI 后端健康状态并展示快捷操作卡片"""
    session_id = f"cl_{int(time.time())}"
    profile = PROFILES["vip"]
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("user_profile", profile)

    # 探测后端真实状态
    target_url, is_online, status_text = await probe_backend_endpoint()
    cl.user_session.set("backend_url", target_url)

    if is_online:
        status_banner = f"> **服务状态**: {status_text} | 目标地址: `{target_url}/api/chat`\n\n"
    else:
        status_banner = (
            f"> **服务状态**: {status_text}\n"
            f"> 💡 提示：若尚未启动后端，请先在另一个终端窗口运行：\n"
            f"> ```bash\n> cd fastapi_backend\n> python app.py\n> ```\n"
            f"> 后端就绪后（端口 8000），直接在下方输入框提问或点击预设按钮即可开始！\n\n"
        )

    welcome_md = (
        f"### 🚀 IntelliServe 智能客服自测工作台 (HTTP 链路模式)\n"
        f"- **测试会话 ID**: `{session_id}`\n"
        f"- **当前模拟客户**: `{profile['userName']}` ({profile['vipLevel']})\n"
        f"- **后端接口地址**: `{target_url}/api/chat`\n\n"
        f"{status_banner}"
        "点击下方常用用例一键测试，或直接输入任意售后问题体验 **LangGraph 编排 + Qdrant 知识召回 + DeepSeek 生成** 全链路："
    )

    actions = [
        cl.Action(name="test_preset", payload={"query": query}, label=f"🧪 {label}")
        for label, query in BENCHMARKS
    ]
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
        await handle_chat(query)


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


@cl.on_message
async def on_message(message: cl.Message):
    """用户在输入框键入消息"""
    user_text = (message.content or "").strip()
    if not user_text:
        return
    await handle_chat(user_text)


async def handle_chat(user_input: str):
    """向 FastAPI 后端 /api/chat 发起真实 HTTP 请求，并完整展示状态轨迹与引用来源"""
    session_id = cl.user_session.get("session_id", f"cl_{int(time.time())}")
    profile = cl.user_session.get("user_profile", PROFILES["vip"])
    backend_url = cl.user_session.get("backend_url", "http://127.0.0.1:8000")

    # 严格确保 backend_url 不指向 5000
    if ":5000" in backend_url:
        backend_url = "http://127.0.0.1:8000"
        cl.user_session.set("backend_url", backend_url)

    payload = {
        "sessionId": session_id,
        "message": user_input,
        "userProfile": profile
    }

    t0 = time.time()
    data = None

    async with cl.Step(name=f"HTTP POST {backend_url}/api/chat", type="run") as step:
        step.input = user_input
        
        # 尝试发送请求，具备端口自动容灾与回退能力
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

    # 侧边栏展示后端检索召回的知识库条款
    refs = data.get("references", [])
    elements = []
    if refs:
        refs_content = "### 📚 Qdrant 检索知识条款 (后端实时召回)\n\n" + "\n\n".join(
            f"**[{i}] {r.get('title', '知识点')}** (匹配度: {r.get('score', 0):.2f})\n> {r.get('snippet', '')}"
            for i, r in enumerate(refs, 1)
        )
        elements.append(cl.Text(name="知识库引用条款", content=refs_content, display="side"))

    # 状态头与最终答复
    escalated = data.get("escalatedToHuman", False)
    badge = "🚨 已转接人工客服" if escalated else "🤖 AI 自动回复"
    latency = data.get("latencyMs", int((time.time() - t0) * 1000))
    info_header = (
        f"> **{badge}** | 意图: `{data.get('intent')}` | "
        f"情绪: `{data.get('sentiment')}` | 耗时: `{latency}ms`\n\n"
    )

    await cl.Message(content=info_header + data.get("reply", ""), elements=elements).send()
