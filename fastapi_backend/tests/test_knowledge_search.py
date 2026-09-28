"""
测试模块：Qdrant 向量知识库切片管理、语义搜索与坐席 Copilot 推荐接口
覆盖接口：
- GET  /api/knowledge
- POST /api/knowledge/search
- POST /api/generate-suggestion
"""

import pytest
from fastapi.testclient import TestClient


def test_get_knowledge_documents(client: TestClient):
    """
    测试场景：获取售后政策全部 FAQ 向量切片列表 GET /api/knowledge
    期望结果：返回 HTTP 200，total > 0，列表内每个切片包含 id、title、category、content 等字段
    """
    response = client.get("/api/knowledge")
    assert response.status_code == 200
    data = response.json()
    assert "docs" in data
    assert "total" in data
    assert data["total"] > 0
    assert len(data["docs"]) == data["total"]

    first_doc = data["docs"][0]
    assert "id" in first_doc
    assert "title" in first_doc
    assert "content" in first_doc
    assert "category" in first_doc


def test_search_knowledge_valid_query(client: TestClient):
    """
    测试场景：使用正常业务查询检索向量库 POST /api/knowledge/search
    期望结果：返回 HTTP 200，results 列表中包含召回的匹配条款，包含 score 和 snippet
    """
    payload = {
        "query": "7天无理由退货的标准与运费规则",
        "topK": 3,
        "minScore": 0.0
    }
    response = client.post("/api/knowledge/search", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == payload["query"]
    assert "results" in data
    assert "latencyMs" in data
    assert len(data["results"]) <= payload["topK"]

    if len(data["results"]) > 0:
        first_hit = data["results"][0]
        assert "doc" in first_hit
        assert "score" in first_hit
        assert "snippet" in first_hit
        assert isinstance(first_hit["score"], (int, float))


def test_search_knowledge_min_score_filter(client: TestClient):
    """
    测试场景：设置极高相似度阈值 (minScore=0.999) 过滤
    期望结果：返回 HTTP 200，符合阈值过滤条件（返回为空或极少）
    """
    payload = {
        "query": "火星人登陆火山口退换货政策",
        "topK": 3,
        "minScore": 0.999
    }
    response = client.post("/api/knowledge/search", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 0


def test_search_knowledge_validation_empty_query(client: TestClient):
    """
    测试场景：传入空 query 字符串
    期望结果：Pydantic 参数校验生效，返回 HTTP 422 Unprocessable Entity
    """
    payload = {
        "query": "",
        "topK": 3
    }
    response = client.post("/api/knowledge/search", json=payload)
    assert response.status_code == 422


def test_search_knowledge_validation_invalid_topk(client: TestClient):
    """
    测试场景：传入超出范围的 topK (例如 topK=99，超出 le=10 限制)
    期望结果：Pydantic 校验拦截，返回 HTTP 422
    """
    payload = {
        "query": "退货规则",
        "topK": 99
    }
    response = client.post("/api/knowledge/search", json=payload)
    assert response.status_code == 422


def test_generate_suggestion_copilot_new_session(client: TestClient):
    """
    测试场景：坐席工作台调用 Copilot 推荐答复草稿 POST /api/generate-suggestion
    期望结果：返回 HTTP 200，输出 suggestion 拟定话术与 matchedClauses 匹配条款
    """
    payload = {
        "sessionId": "test_copilot_session_001"
    }
    response = client.post("/api/generate-suggestion", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "suggestion" in data
    assert "matchedClauses" in data
    assert isinstance(data["suggestion"], str)
    assert len(data["suggestion"]) > 0
    assert isinstance(data["matchedClauses"], list)
