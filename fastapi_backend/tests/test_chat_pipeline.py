"""
测试模块：核心智能问答流水线 (LangGraph + RAG + 意图识别 + 记忆更新)
覆盖接口：
- POST /api/chat
"""

import pytest
from fastapi.testclient import TestClient


def test_chat_normal_refund_inquiry(client: TestClient, sample_chat_request: dict):
    """
    测试场景：客户发起常规售后政策咨询 POST /api/chat（增量返回模式）
    期望结果：
    1. 返回 HTTP 200 与增量 ChatResponse（不含全量历史 session.messages）
    2. userMessage 与 assistantMessage 均完整返回，且 aiMeta 仅保留 confidenceScore / references / stepTrace
    3. sessionPatch 仅包含实时同步所需轻量字段（不含冗余 metrics / pendingRefund / unreadForAgent）
    """
    response = client.post("/api/chat", json=sample_chat_request)
    assert response.status_code == 200, f"Expected 200, got: {response.text}"
    data = response.json()

    assert data["sessionId"] == sample_chat_request["sessionId"]
    assert "reply" in data and len(data["reply"]) > 0
    assert "confidenceScore" in data
    assert 0.0 <= data["confidenceScore"] <= 1.0
    assert "sentiment" in data
    assert "intent" in data
    assert data["escalatedToHuman"] is False
    assert "latencyMs" in data and data["latencyMs"] >= 0

    # 验证增量消息结构（无全量 session 冗余）
    assert "session" not in data
    assert "pendingRefundOrder" not in data
    assert data["userMessage"]["role"] == "user"
    assert data["userMessage"]["content"] == sample_chat_request["message"]

    assistant_msg = data["assistantMessage"]
    assert assistant_msg["role"] == "assistant"
    assert assistant_msg["content"] == data["reply"]
    ai_meta = assistant_msg.get("aiMeta") or {}
    assert "intent" not in ai_meta
    assert "sentiment" not in ai_meta
    assert isinstance(ai_meta.get("references"), list)
    assert isinstance(ai_meta.get("stepTrace"), list)

    patch = data["sessionPatch"]
    assert patch["status"] == "AI_HANDLING"
    assert "messages" not in patch
    assert "metrics" not in patch
    assert "pendingRefund" not in patch
    assert "unreadForAgent" not in patch
    assert isinstance(patch.get("summaryMemory"), str)


def test_chat_explicit_human_request(client: TestClient):
    """
    测试场景：客户明确要求转人工 ("请立刻帮我转人工客服")
    期望结果：
    1. escalatedToHuman 为 True
    2. sessionPatch.status 标记为待人工接入 (NEEDS_INTERVENTION 或 TRANSFERRED_TO_HUMAN)
    """
    payload = {
        "sessionId": "test_human_escalate_001",
        "message": "你们机器人根本解决不了，请立刻给我转人工客服！"
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["sessionId"] == payload["sessionId"]
    assert data["escalatedToHuman"] is True
    assert data["escalationReason"] is not None
    assert data["sessionPatch"]["status"] in ["NEEDS_INTERVENTION", "TRANSFERRED_TO_HUMAN"]


def test_chat_multi_turn_continuity(client: TestClient):
    """
    测试场景：同一会话多轮对话交互
    期望结果：
    1. 每轮 /api/chat 仅增量返回当轮 userMessage + assistantMessage（O(1) 体积）
    2. 服务端实际已持久化累加 4 条消息（通过 GET /api/sessions/{session_id} 核验）
    """
    session_id = "test_multiturn_001"

    # 第一轮
    resp1 = client.post("/api/chat", json={
        "sessionId": session_id,
        "message": "我想了解一下7天无理由退货的规定"
    })
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["userMessage"]["role"] == "user"
    assert data1["assistantMessage"]["role"] == "assistant"

    # 第二轮
    resp2 = client.post("/api/chat", json={
        "sessionId": session_id,
        "message": "如果是拆封了未使用的电子产品可以退吗？"
    })
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["userMessage"]["content"] == "如果是拆封了未使用的电子产品可以退吗？"
    assert data2["assistantMessage"]["role"] == "assistant"

    # 核验持久化的完整会话包含 4 条消息与 totalTurns=4
    detail = client.get(f"/api/sessions/{session_id}")
    assert detail.status_code == 200
    session_obj = detail.json()["session"]
    msgs = session_obj["messages"]
    assert len(msgs) == 4
    assert session_obj["metrics"]["totalTurns"] == 4
    assert msgs[2]["content"] == "如果是拆封了未使用的电子产品可以退吗？"


def test_chat_empty_message_validation(client: TestClient):
    """
    测试场景：发送内容为空的消息 POST /api/chat
    期望结果：Pydantic 校验拦截 (min_length=1)，返回 HTTP 422
    """
    payload = {
        "sessionId": "test_invalid_001",
        "message": ""
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 422


def test_chat_with_order_context_in_profile(client: TestClient):
    """
    测试场景：附带订单上下文信息的 VIP 用户咨询
    期望结果：成功响应，用户画像正确持久化在会话 customerProfile 中
    """
    session_id = "test_order_context_001"
    payload = {
        "sessionId": session_id,
        "message": "我的空气炸锅到了3天了，怎么申请免费换新？",
        "userProfile": {
            "tier": "GOLD",
            "recentOrder": {
                "orderId": "ORD-2026-8888",
                "item": "高端空气炸锅 Pro",
                "status": "已签收"
            }
        }
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200

    detail = client.get(f"/api/sessions/{session_id}")
    assert detail.status_code == 200
    profile = detail.json()["session"]["customerProfile"]
    assert profile["tier"] == "GOLD"
    assert "recentOrder" in profile
