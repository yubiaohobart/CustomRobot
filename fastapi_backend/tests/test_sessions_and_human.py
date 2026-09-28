"""
测试模块：会话管理、人机协同转接、坐席接管与审计监控接口
覆盖接口：
- GET  /api/sessions
- GET  /api/sessions/{session_id}
- POST /api/sessions/{session_id}/transfer
- POST /api/sessions/{session_id}/intervene
- POST /api/sessions/{session_id}/human-message
- GET  /api/agents
- GET  /api/transfer-logs
- GET  /api/metrics
"""

import pytest
from fastapi.testclient import TestClient
from services.memory_service import memory_service


def test_list_sessions_initially_empty(client: TestClient):
    """
    测试场景：获取会话列表 GET /api/sessions
    期望结果：返回 HTTP 200，sessions 字段为列表
    """
    response = client.get("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert isinstance(data["sessions"], list)


def test_get_single_session_not_found(client: TestClient):
    """
    测试场景：查询不存在的会话 GET /api/sessions/{session_id}
    期望结果：返回 HTTP 404 Not Found
    """
    response = client.get("/api/sessions/non_existent_session_999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found"


def test_session_lifecycle_and_details(client: TestClient):
    """
    测试场景：创建会话后查询会话详情
    期望结果：成功返回会话画像、消息流与状态
    """
    session_id = "test_lifecycle_001"
    profile = {"userId": "u100", "userName": "张先生", "tier": "SILVER"}
    
    # 初始化会话与添加消息
    memory_service.get_or_create_session(session_id, profile)
    memory_service.add_message(session_id, "user", "我想查询退款进度")

    # 调用接口查询详情
    response = client.get(f"/api/sessions/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert "session" in data
    session = data["session"]
    assert session["id"] == session_id
    assert session["status"] == "AI_HANDLING"
    assert len(session["messages"]) == 1
    assert session["messages"][0]["content"] == "我想查询退款进度"


def test_transfer_session_to_human(client: TestClient):
    """
    测试场景：人工转接接口 POST /api/sessions/{session_id}/transfer
    期望结果：会话状态变为 TRANSFERRED_TO_HUMAN，生成不可变上下文快照并指派目标坐席
    """
    session_id = "test_transfer_001"
    memory_service.get_or_create_session(session_id, {"userName": "李女士", "tier": "GOLD"})
    memory_service.add_message(session_id, "user", "我不信任机器人，请立刻找人工！")

    payload = {
        "targetAgentId": "agent_101",
        "reason": "客户情绪激动要求人工接入",
        "operatorNote": "客户购买商品有破损，需优先安抚",
        "triggerType": "user_requested"
    }

    response = client.post(f"/api/sessions/{session_id}/transfer", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "transferLog" in data
    assert "session" in data

    log = data["transferLog"]
    assert log["targetAgentId"] == "agent_101"
    assert log["reason"] == payload["reason"]
    assert "contextSnapshot" in log
    assert log["contextSnapshot"]["summaryMemory"] is not None

    session = data["session"]
    assert session["status"] == "TRANSFERRED_TO_HUMAN"
    assert session["assignedAgentId"] == "agent_101"


def test_intervene_session_takeover_and_release(client: TestClient):
    """
    测试场景：坐席接管会话与交还 AI 处理 POST /api/sessions/{session_id}/intervene
    期望结果：
    1. action='takeover' 时状态切换为 HUMAN_INTERVENED
    2. action='release' 时状态恢复为 AI_HANDLING
    """
    session_id = "test_intervene_001"
    memory_service.get_or_create_session(session_id)

    # 1. 坐席接管
    takeover_payload = {
        "action": "takeover",
        "agentId": "agent_101",
        "note": "高级督导介入解答"
    }
    takeover_resp = client.post(f"/api/sessions/{session_id}/intervene", json=takeover_payload)
    assert takeover_resp.status_code == 200
    takeover_data = takeover_resp.json()
    assert takeover_data["success"] is True
    assert takeover_data["session"]["status"] == "HUMAN_INTERVENED"

    # 2. 坐席交还 AI
    release_payload = {
        "action": "release",
        "agentId": "agent_101",
        "note": "疑难已解答，交还AI处理常规咨询"
    }
    release_resp = client.post(f"/api/sessions/{session_id}/intervene", json=release_payload)
    assert release_resp.status_code == 200
    release_data = release_resp.json()
    assert release_data["success"] is True
    assert release_data["session"]["status"] == "AI_HANDLING"


def test_send_human_agent_message(client: TestClient):
    """
    测试场景：人工坐席在工作台发送客服答复 POST /api/sessions/{session_id}/human-message
    期望结果：消息被记录为 role='human_agent'，会话历史消息数量递增
    """
    session_id = "test_human_msg_001"
    memory_service.get_or_create_session(session_id)

    payload = {
        "message": "您好，我是客服督导陈浩，已经为您核实并开通绿色换货通道！",
        "agentId": "agent_101"
    }
    response = client.post(f"/api/sessions/{session_id}/human-message", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "message" in data
    assert data["message"]["role"] == "human_agent"
    assert data["message"]["content"] == payload["message"]
    assert len(data["session"]["messages"]) == 1


def test_get_agents_roster(client: TestClient):
    """
    测试场景：获取坐席人员技能矩阵与状态 GET /api/agents
    期望结果：返回预置的专业客服坐席列表，包含专长领域与工号
    """
    response = client.get("/api/agents")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    agents = data["agents"]
    assert len(agents) >= 4
    
    agent_ids = [a["id"] for a in agents]
    assert "agent_101" in agent_ids
    assert "agent_102" in agent_ids


def test_get_transfer_logs_audit(client: TestClient):
    """
    测试场景：查询转接快照审计流水 GET /api/transfer-logs
    期望结果：发生转接后，审计接口能查到包含快照、触发原因与操作时间的记录
    """
    session_id = "test_audit_001"
    memory_service.get_or_create_session(session_id)
    memory_service.transfer_session(
        session_id=session_id,
        target_agent_id="agent_102",
        reason="退款核算专席处理",
        operator_note="已核对支付凭证",
        trigger_type="low_confidence"
    )

    response = client.get("/api/transfer-logs")
    assert response.status_code == 200
    data = response.json()
    assert "logs" in data
    assert len(data["logs"]) >= 1
    latest_log = data["logs"][-1]
    assert latest_log["targetAgentId"] == "agent_102"
    assert latest_log["triggerType"] == "low_confidence"


def test_get_dashboard_metrics(client: TestClient):
    """
    测试场景：获取大屏实时监控指标 GET /api/metrics
    期望结果：返回 totalSessions, totalMessages, aiResolvedRate, vectorDatabase 等各项指标
    """
    # 构造测试会话数据
    s1 = "metric_s1"
    s2 = "metric_s2"
    memory_service.get_or_create_session(s1)
    memory_service.add_message(s1, "user", "问个问题")
    memory_service.add_message(s1, "assistant", "这是回答")
    
    memory_service.get_or_create_session(s2)
    memory_service.transfer_session(s2, "agent_101", "转人工")

    response = client.get("/api/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "totalSessions" in data
    assert data["totalSessions"] == 2
    assert "totalMessages" in data
    assert data["totalMessages"] >= 2
    assert "aiResolvedRate" in data
    assert "vectorDatabase" in data
    assert data["vectorDatabase"] == "Qdrant"
    assert "llmModel" in data
