"""
Pytest 全局夹具与测试上下文配置 (Pytest Conftest & Fixtures)
提供 FastAPI TestClient、内存重置钩子以及常用测试数据
"""

import sys
import os
import pytest

# 确保 fastapi_backend 加入 Python 模块搜索路径
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import app
from fastapi.testclient import TestClient
from services.memory_service import memory_service
from core.qdrant_store import qdrant_store


@pytest.fixture(scope="session", autouse=True)
def setup_qdrant_knowledge():
    """测试会话级别：确保 Qdrant 知识库集合已初始化并注入测试 FAQ"""
    qdrant_store.init_collection_with_faq()
    yield


@pytest.fixture(autouse=True)
def reset_memory_state():
    """用例级别：每个测试用例执行前后重置会话内存与转接记录，保证用例相互独立隔离"""
    memory_service.sessions.clear()
    memory_service.transfer_logs.clear()
    yield
    memory_service.sessions.clear()
    memory_service.transfer_logs.clear()


@pytest.fixture
def client():
    """提供统一的 FastAPI 同步测试客户端 (基于 starlette.testclient / httpx)"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_vip_profile():
    """提供标准 VIP 客户画像测试数据"""
    return {
        "userId": "vip_user_888",
        "userName": "王女士",
        "tier": "GOLD",
        "benefits": ["退货免运费", "专属客服", "闪电退款"],
        "recentOrder": {
            "orderId": "ORD-2026-9901",
            "item": "高端智能空气炸锅 Pro",
            "amount": 899.0,
            "status": "已签收",
            "signedDays": 3
        }
    }


@pytest.fixture
def sample_chat_request(sample_vip_profile):
    """提供标准客户问答请求数据"""
    return {
        "sessionId": "test_session_pytest_001",
        "message": "黄金会员退货免运费怎么申请？",
        "userProfile": sample_vip_profile
    }
