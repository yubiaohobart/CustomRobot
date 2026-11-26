"""
测试模块：系统状态、根路由与健康检查接口
覆盖接口：
- GET  /
- GET  /api/health
"""

import pytest
from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient):
    """
    测试场景：访问根路径 GET /
    期望结果：返回 HTTP 200，包含系统欢迎信息、Swagger 文档链接及技术栈说明
    """
    response = client.get("/")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert data["docs"] == "/docs"
    assert data["health"] == "/api/health"
    assert "tech_stack" in data
    assert data["tech_stack"]["web_framework"] == "FastAPI"
    assert data["tech_stack"]["workflow_orchestrator"] == "LangGraph"
    assert data["tech_stack"]["vector_database"] == "Qdrant"


def test_health_check_endpoint(client: TestClient):
    """
    测试场景：访问系统探活接口 GET /api/health
    期望结果：返回 HTTP 200，status 为 'ok'，包含向量数据库与大模型引擎就绪状态
    """
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "app" in data
    assert "version" in data
    assert "llm_engine" in data
    assert "vector_engine" in data
    assert "vector_database" in data
    assert "active_sessions" in data
    assert isinstance(data["active_sessions"], int)
    assert data["active_sessions"] >= 0

