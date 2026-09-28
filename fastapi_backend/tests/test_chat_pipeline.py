"""
测试模块：核心智能问答流水线 (LangGraph + RAG + 意图识别 + 记忆更新)
覆盖接口：
- POST /api/chat
"""

import pytest
from fastapi.testclient import TestClient


def test_chat_normal_refund_inquiry(client: TestClient, sample_chat_request: dict):
    """
    测试场景：客户发起常规售后政策咨询 POST /api/chat
    期望结果：
    1. 返回 HTTP 200 与结构化 ChatResponse
    2. reply 不为空，包含有价值的售后答复
    3. confidenceScore 在合理区间 (0.0 ~ 1.0)
    4. references 引用列表包含关联 FAQ 来源
    5. stepTrace 追踪链路记录了 LangGraph 节点的执行足迹
    6. latencyMs 记录了全流程执行耗时
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
    assert "references" in data
    assert isinstance(data["references"], list)
    assert "stepTrace" in data
    assert isinstance(data["stepTrace"], list)
    assert "latencyMs" in data
    assert data["latencyMs"] >= 0

    # 验证会话对象同步更新
    assert "session" in data
    session = data["session"]
    assert session["id"] == sample_chat_request["sessionId"]
    # 至少应有 2 条消息（1 条用户提问，1 条 AI 回复）
    assert len(session["messages"]) >= 2
    assert session["messages"][0]["role"] == "user"
    assert session["messages"][1]["role"] == "assistant"


def test_chat_explicit_human_request(client: TestClient):
    """
    测试场景：客户明确要求转人工 ("请立刻帮我转人工客服")
    期望结果：
    1. 意图/情绪分析节点或状态图识别人工诉求
    2. escalatedToHuman 为 True
    3. 会话状态标记为待人工接入 (NEEDS_INTERVENTION 或 status 变更)
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
    assert "session" in data
    assert data["session"]["status"] in ["NEEDS_INTERVENTION", "TRANSFERRED_TO_HUMAN"]


def test_chat_multi_turn_continuity(client: TestClient):
    """
    测试场景：同一会话多轮对话交互
    期望结果：第二轮对话中会话历史累积，包含两轮用户提问与两轮助手回复 (共计4条)
    """
    session_id = "test_multiturn_001"

    # 第一轮
    resp1 = client.post("/api/chat", json={
        "sessionId": session_id,
        "message": "我想了解一下7天无理由退货的规定"
    })
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert len(data1["session"]["messages"]) == 2

    # 第二轮
    resp2 = client.post("/api/chat", json={
        "sessionId": session_id,
        "message": "如果是拆封了未使用的电子产品可以退吗？"
    })
    assert resp2.status_code == 200
    data2 = resp2.json()
    # 消息记录应该累加到 4 条
    assert len(data2["session"]["messages"]) == 4
    assert data2["session"]["messages"][2]["content"] == "如果是拆封了未使用的电子产品可以退吗？"
    assert data2["session"]["messages"][3]["role"] == "assistant"


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
    期望结果：成功响应，用户画像正确保留在会话中
    """
    payload = {
        "sessionId": "test_order_context_001",
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
    data = response.json()
    assert data["session"]["customerProfile"]["tier"] == "GOLD"
    assert "recentOrder" in data["session"]["customerProfile"]
