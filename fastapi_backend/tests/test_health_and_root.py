"""
测试模块：系统状态、根路由、健康检查与自检诊断接口
覆盖接口：
- GET  /
- GET  /api/health
- GET  /api/test
- POST /api/test
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


def test_system_test_get_diagnostics(client: TestClient):
    """
    测试场景：触发全链路自检接口 GET /api/test
    期望结果：返回 HTTP 200，各诊断子系统 (embedding, qdrant, memory, llm) 状态正常
    """
    response = client.get("/api/test")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "diagnostics" in data
    diagnostics = data["diagnostics"]

    # 1. 检验向量检索诊断项
    assert "vector_database_qdrant" in diagnostics
    assert diagnostics["vector_database_qdrant"]["status"] == "pass"
    assert diagnostics["vector_database_qdrant"]["total_documents"] > 0

    # 2. 检验会话记忆诊断项
    assert "memory_service" in diagnostics
    assert diagnostics["memory_service"]["status"] == "pass"

    # 3. 检验 LLM 配置状态项
    assert "llm_engine" in diagnostics
    assert diagnostics["llm_engine"]["provider"] == "DeepSeek"


def test_system_test_post_custom_query(client: TestClient):
    """
    测试场景：交互式自检接口 POST /api/test
    期望结果：根据传入测试入参返回自定义 query 的 embedding 与 qdrant 检索分析
    """
    payload = {
        "query": "退换货运费由谁承担？",
        "testOllama": True,
        "testQdrant": True,
        "testLLM": False
    }
    response = client.post("/api/test", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == payload["query"]
    assert "total_latency_ms" in data

    # 检验 Qdrant 检索结果
    assert "qdrant" in data
    assert data["qdrant"]["hits_count"] > 0
    assert len(data["qdrant"]["hits"]) > 0

    # 检验 Embedding 输出
    assert "embedding" in data
    assert "dimension" in data["embedding"]
    assert data["embedding"]["dimension"] == 1024


def test_system_test_post_default_payload(client: TestClient):
    """
    测试场景：交互式自检接口 POST /api/test 使用空入参
    期望结果：使用默认配置成功执行
    """
    response = client.post("/api/test", json={})
    assert response.status_code == 200
    data = response.json()
    assert "query" in data
    assert "total_latency_ms" in data
