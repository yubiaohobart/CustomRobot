"""
基于 Redis 的分布式会话互斥锁管理器 (Redis 7.2.3 / redis.asyncio)
直接使用官方 client.lock() 原语实现 SET NX PX、Lua 原子解锁/续期，并内置：
- 按事件循环隔离的异步 Redis 连接池复用
- Watchdog 后台定时调用 lock.extend() 防止长耗时 LLM 请求期间锁提前过期
- 同 asyncio.Task 内可重入保护 + 获取超时快速失败 (SessionLockTimeoutError -> HTTP 429)
"""

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any, AsyncIterator, Dict, Optional, Tuple

import redis.asyncio as aioredis
from redis.exceptions import LockError

from config import settings
from core.logger import cprint

# 记录当前 asyncio.Task 已持有的 session_id，避免同任务重入死锁且不被 create_task 子任务误继承
_held_lock_owners: ContextVar[Dict[str, Optional[asyncio.Task[Any]]]] = ContextVar(
    "_held_lock_owners", default={}
)


class SessionLockTimeoutError(TimeoutError):
    """获取会话分布式锁超时异常（由路由层统一映射为 HTTP 429）"""

    def __init__(self, session_id: str, timeout: float):
        self.session_id = session_id
        self.timeout = timeout
        super().__init__(f"会话 [{session_id}] 当前请求正在处理中，请稍后再试（等待锁超时 {timeout:.1f}s）")


class SessionLockManager:
    """基于 redis.asyncio.Redis.lock() 的分布式会话锁管理器"""

    def __init__(self) -> None:
        self._client: Optional[aioredis.Redis] = None
        self._client_key: Optional[Tuple[int, str]] = None

    async def _get_client(self) -> aioredis.Redis:
        redis_url = settings.REDIS_URL.strip()
        loop = asyncio.get_running_loop()
        target_key = (id(loop), redis_url)

        if self._client is not None and self._client_key == target_key:
            return self._client

        if self._client is not None and self._client_key and self._client_key[0] == id(loop):
            await self._client.aclose()

        self._client = aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=5.0,
        )
        self._client_key = target_key
        return self._client

    async def close(self) -> None:
        """优雅关闭 Redis 异步连接池"""
        client, key = self._client, self._client_key
        self._client = None
        self._client_key = None
        if client is not None:
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None
            if key is None or (running_loop is not None and id(running_loop) == key[0]):
                await client.aclose()

    async def _watchdog_loop(self, lock: Any, ttl_seconds: float) -> None:
        interval = max(1.0, ttl_seconds / 3.0)
        while True:
            await asyncio.sleep(interval)
            try:
                if not await lock.extend(ttl_seconds, replace_ttl=True):
                    break
            except asyncio.CancelledError:
                raise
            except LockError as exc:
                cprint.warning(f"[SessionLock] Redis 锁续期失败 ({lock.name}): {exc}")
                break

    @asynccontextmanager
    async def acquire(
        self,
        session_id: str,
        *,
        timeout: Optional[float] = None,
        ttl_seconds: Optional[float] = None,
    ) -> AsyncIterator[None]:
        """获取按 session_id 隔离的 Redis 分布式互斥锁（同一 Task 内支持可重入）"""
        current_task = asyncio.current_task()
        held = _held_lock_owners.get()
        if session_id in held and held[session_id] is current_task:
            yield
            return

        wait_timeout = timeout if timeout is not None else settings.SESSION_LOCK_TIMEOUT_SECONDS
        lock_ttl = max(2.0, ttl_seconds if ttl_seconds is not None else settings.SESSION_LOCK_TTL_SECONDS)

        client = await self._get_client()
        lock = client.lock(
            name=f"intelliserve:lock:session:{session_id}",
            timeout=lock_ttl,
            sleep=0.05,
            blocking=True,
            blocking_timeout=wait_timeout,
        )

        if not await lock.acquire():
            raise SessionLockTimeoutError(session_id, wait_timeout)

        next_held = dict(held)
        next_held[session_id] = current_task
        ctx_token = _held_lock_owners.set(next_held)
        watchdog = asyncio.create_task(self._watchdog_loop(lock, lock_ttl))
        try:
            yield
        finally:
            _held_lock_owners.reset(ctx_token)
            watchdog.cancel()
            try:
                await watchdog
            except asyncio.CancelledError:
                pass
            try:
                await lock.release()
            except LockError as exc:
                cprint.warning(f"[SessionLock] Redis 释放锁异常 ({lock.name}): {exc}")


session_lock_manager = SessionLockManager()


def acquire_session_lock(
    session_id: str,
    *,
    timeout: Optional[float] = None,
    ttl_seconds: Optional[float] = None,
):
    """获取按 session_id 隔离的 Redis 分布式会话互斥锁"""
    return session_lock_manager.acquire(session_id, timeout=timeout, ttl_seconds=ttl_seconds)
