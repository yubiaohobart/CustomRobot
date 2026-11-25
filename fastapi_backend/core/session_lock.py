"""
极简 Redis 分布式会话互斥锁 (Redis 7.2.3 / redis.asyncio)
直接复用官方 client.lock() 原语实现跨进程互斥与阻塞超时快速失败 (HTTP 429)。
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import HTTPException
import redis.asyncio as aioredis
from redis.exceptions import LockError

from config import settings

_redis_client: Optional[aioredis.Redis] = None


def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL.strip(),
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=5.0,
        )
    return _redis_client


async def close_session_lock_redis() -> None:
    """应用关闭时释放 Redis 异步连接池"""
    global _redis_client
    client = _redis_client
    _redis_client = None
    if client is not None:
        await client.aclose()


@asynccontextmanager
async def acquire_session_lock(session_id: str) -> AsyncIterator[None]:
    """按 session_id 加 Redis 分布式锁（TTL 默认 90s 覆盖单轮最大耗时）"""
    client = _get_redis()
    lock = client.lock(
        f"intelliserve:lock:session:{session_id}",
        timeout=settings.SESSION_LOCK_TTL_SECONDS,
        sleep=0.05,
        blocking=True,
        blocking_timeout=settings.SESSION_LOCK_TIMEOUT_SECONDS,
    )
    if not await lock.acquire():
        raise HTTPException(
            status_code=429,
            detail=f"会话 [{session_id}] 当前请求正在处理中，请稍后再试",
        )
    try:
        yield
    finally:
        try:
            await lock.release()
        except LockError:
            pass
