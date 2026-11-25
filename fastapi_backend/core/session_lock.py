"""
分布式会话互斥锁管理器 (Distributed Session Lock Manager)
- 配置 REDIS_URL 且 Redis 可用时：使用 Redis 分布式锁（SET NX PX + Lua 原子校验续期/释放 + Watchdog）
- 未配置 REDIS_URL 或 Redis 暂不可用时：优雅降级为基于 WeakValueDictionary 的进程内异步锁（按事件循环隔离，自动 GC 防泄漏）
- 支持同一协程任务内可重入、获取锁超时快速失败 (SessionLockTimeoutError -> HTTP 429)
"""

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any, AsyncIterator, Dict, Optional, Tuple
import time
import uuid
import weakref

from config import settings
from core.logger import cprint

try:
    import redis.asyncio as aioredis
    from redis.exceptions import RedisError
except ImportError:  # pragma: no cover - 未安装 redis 包时自动走本地降级锁
    aioredis = None  # type: ignore[assignment]

    class RedisError(Exception):
        pass


_RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

_RENEW_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("pexpire", KEYS[1], ARGV[2])
else
    return 0
end
"""

# 记录当前 asyncio.Task 已持有的 session_id，避免同任务重入死锁且不被 create_task 子任务误继承
_held_lock_owners: ContextVar[Dict[str, Optional[asyncio.Task[Any]]]] = ContextVar(
    "_held_lock_owners", default={}
)


class SessionLockTimeoutError(TimeoutError):
    """获取会话锁超时异常（供路由层统一映射为 HTTP 429）"""

    def __init__(self, session_id: str, timeout: float):
        self.session_id = session_id
        self.timeout = timeout
        super().__init__(f"会话 [{session_id}] 当前请求正在处理中，请稍后再试（等待锁超时 {timeout:.1f}s）")


class SessionLockManager:
    """支持 Redis 分布式锁与本地 WeakValueDictionary 锁无缝切换的会话锁管理器"""

    def __init__(self) -> None:
        self._local_locks: "weakref.WeakValueDictionary[Tuple[int, str], asyncio.Lock]" = (
            weakref.WeakValueDictionary()
        )
        self._redis_client: Any = None
        self._redis_key: Optional[Tuple[int, str]] = None
        self._redis_cooldown_until: float = 0.0

    def _get_redis_url(self) -> str:
        return (getattr(settings, "REDIS_URL", None) or "").strip()

    async def _get_redis_client(self) -> Any:
        redis_url = self._get_redis_url()
        if not redis_url or aioredis is None:
            return None
        if time.monotonic() < self._redis_cooldown_until:
            return None

        loop = asyncio.get_running_loop()
        target_key = (id(loop), redis_url)
        if self._redis_client is not None and self._redis_key == target_key:
            return self._redis_client

        if self._redis_client is not None and self._redis_key and self._redis_key[0] == id(loop):
            try:
                await self._redis_client.aclose()
            except Exception:
                pass

        self._redis_client = aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=5.0,
        )
        self._redis_key = target_key
        return self._redis_client

    async def close(self) -> None:
        """关闭底层 Redis 异步连接池"""
        client, key = self._redis_client, self._redis_key
        self._redis_client = None
        self._redis_key = None
        if client is not None:
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None
            if key is None or (running_loop is not None and id(running_loop) == key[0]):
                try:
                    await client.aclose()
                except Exception:
                    pass

    @asynccontextmanager
    async def _acquire_local(self, session_id: str, timeout: float) -> AsyncIterator[None]:
        loop = asyncio.get_running_loop()
        key = (id(loop), session_id)
        lock = self._local_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._local_locks[key] = lock

        try:
            await asyncio.wait_for(lock.acquire(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise SessionLockTimeoutError(session_id, timeout) from exc

        try:
            yield
        finally:
            if lock.locked():
                lock.release()

    async def _watchdog_loop(
        self,
        client: Any,
        lock_key: str,
        token: str,
        ttl_ms: int,
    ) -> None:
        interval = max(1.0, (ttl_ms / 1000.0) / 3.0)
        while True:
            await asyncio.sleep(interval)
            try:
                ok = await client.eval(_RENEW_LUA, 1, lock_key, token, ttl_ms)
                if not ok:
                    break
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                cprint.warning(f"[SessionLock] Redis 锁续期异常 ({lock_key}): {exc}")
                break

    @asynccontextmanager
    async def _acquire_redis(
        self,
        client: Any,
        session_id: str,
        timeout: float,
        ttl_seconds: float,
    ) -> AsyncIterator[None]:
        lock_key = f"intelliserve:lock:session:{session_id}"
        token = uuid.uuid4().hex
        ttl_ms = max(2000, int(ttl_seconds * 1000))
        deadline = time.monotonic() + max(0.1, timeout)
        acquired = False

        while True:
            try:
                acquired = bool(await client.set(lock_key, token, nx=True, px=ttl_ms))
            except (RedisError, OSError) as exc:
                self._redis_cooldown_until = time.monotonic() + 30.0
                cprint.warning(f"[SessionLock] Redis 不可用，30s 内降级为本地锁 ({type(exc).__name__}): {exc}")
                async with self._acquire_local(session_id, timeout):
                    yield
                return

            if acquired:
                break

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SessionLockTimeoutError(session_id, timeout)
            await asyncio.sleep(min(0.05, remaining))

        watchdog = asyncio.create_task(self._watchdog_loop(client, lock_key, token, ttl_ms))
        try:
            yield
        finally:
            watchdog.cancel()
            try:
                await watchdog
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
            try:
                await client.eval(_RELEASE_LUA, 1, lock_key, token)
            except Exception as exc:
                cprint.warning(f"[SessionLock] Redis 释放锁失败 ({lock_key}): {exc}")

    @asynccontextmanager
    async def acquire(
        self,
        session_id: str,
        *,
        timeout: Optional[float] = None,
        ttl_seconds: Optional[float] = None,
    ) -> AsyncIterator[None]:
        """获取按 session_id 隔离的互斥锁（同一 Task 内自动支持可重入）"""
        current_task = asyncio.current_task()
        held = _held_lock_owners.get()
        if session_id in held and held[session_id] is current_task:
            yield
            return

        wait_timeout = timeout if timeout is not None else getattr(settings, "SESSION_LOCK_TIMEOUT_SECONDS", 5.0)
        lock_ttl = ttl_seconds if ttl_seconds is not None else getattr(settings, "SESSION_LOCK_TTL_SECONDS", 60.0)

        next_held = dict(held)
        next_held[session_id] = current_task
        ctx_token = _held_lock_owners.set(next_held)
        try:
            client = await self._get_redis_client()
            if client is not None:
                async with self._acquire_redis(client, session_id, wait_timeout, lock_ttl):
                    yield
            else:
                async with self._acquire_local(session_id, wait_timeout):
                    yield
        finally:
            _held_lock_owners.reset(ctx_token)


session_lock_manager = SessionLockManager()


def acquire_session_lock(
    session_id: str,
    *,
    timeout: Optional[float] = None,
    ttl_seconds: Optional[float] = None,
):
    """获取按 session_id 隔离的分布式/本地异步互斥锁上下文管理器"""
    return session_lock_manager.acquire(session_id, timeout=timeout, ttl_seconds=ttl_seconds)
