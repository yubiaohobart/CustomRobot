"""
FastAPI 原生 WebSocket 连接池与实时广播管理器 (WebSocket Connection Manager)
负责按会话房间广播、按角色定向广播、单连接写锁串行化与僵尸连接清理。
"""

import asyncio
import datetime
import json
import time
from typing import Any, Collection, Dict, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect

from core.logger import log, cprint

DEFAULT_ROLE_NAMES: Dict[str, str] = {
    "customer": "客户",
    "agent": "人工坐席",
    "supervisor": "客服主管",
    "dual_observer": "同屏观测台",
}


def build_ws_event(
    event_type: str,
    data: Optional[Dict[str, Any]] = None,
    *,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """构建统一 WebSocket 下行事件信封: { type, sessionId?, timestamp, data }"""
    envelope: Dict[str, Any] = {
        "type": event_type,
        "timestamp": datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
        "data": data if data is not None else {},
    }
    if session_id is not None:
        envelope["sessionId"] = session_id
    return envelope


class WebSocketConnectionManager:
    """管理活跃的 WebSocket 长连接，支持按会话房间与角色并发广播"""

    def __init__(self, send_timeout: float = 5.0):
        self.session_connections: Dict[str, Set[WebSocket]] = {}
        self.connection_meta: Dict[WebSocket, Dict[str, Any]] = {}
        self._send_locks: Dict[WebSocket, asyncio.Lock] = {}
        self.send_timeout = send_timeout

    async def _send_text_safe(self, connection: WebSocket, text: str) -> bool:
        lock = self._send_locks.get(connection)
        if lock is None or connection not in self.connection_meta:
            return False
        try:
            async with lock:
                await asyncio.wait_for(connection.send_text(text), timeout=self.send_timeout)
            return True
        except (WebSocketDisconnect, RuntimeError, ConnectionError, OSError, asyncio.TimeoutError) as exc:
            log.debug(f"WebSocket 发送失败，连接将注销: {type(exc).__name__}")
            return False

    async def _dispatch_text(self, recipients: List[WebSocket], text: str) -> int:
        if not recipients:
            return 0
        results = await asyncio.gather(
            *(self._send_text_safe(conn, text) for conn in recipients),
            return_exceptions=True,
        )
        delivered = 0
        for conn, ok in zip(recipients, results):
            if ok is True:
                delivered += 1
            else:
                self.disconnect(conn)
        return delivered

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str = "default",
        role: str = "customer",
        name: str = "",
    ) -> None:
        await websocket.accept()
        try:
            self._send_locks[websocket] = asyncio.Lock()
            meta = self.register_session(websocket, session_id=session_id, role=role, name=name)
            cprint.websocket("握手成功", meta["session_id"], f"角色: {meta['role']}, 在线数: {len(self.connection_meta)}")
            await self.send_to_connection(
                websocket,
                build_ws_event("joined", {"role": meta["role"], "name": meta["name"]}, session_id=meta["session_id"]),
            )
        except Exception:
            self.disconnect(websocket)
            raise

    def register_session(
        self,
        websocket: WebSocket,
        session_id: str,
        role: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """绑定或切换连接所属会话房间"""
        now = time.time()
        old_meta = self.connection_meta.get(websocket)
        if old_meta:
            old_sid = old_meta.get("session_id")
            if old_sid and old_sid != session_id and old_sid in self.session_connections:
                self.session_connections[old_sid].discard(websocket)
                if not self.session_connections[old_sid]:
                    del self.session_connections[old_sid]

        resolved_role = (role or "").strip() or (old_meta or {}).get("role") or "customer"
        resolved_name = (name or "").strip() or DEFAULT_ROLE_NAMES.get(resolved_role, "客户")

        self._send_locks.setdefault(websocket, asyncio.Lock())
        self.session_connections.setdefault(session_id, set()).add(websocket)

        meta = {
            "session_id": session_id,
            "role": resolved_role,
            "name": resolved_name,
            "last_seen_at": now,
        }
        self.connection_meta[websocket] = meta
        cprint.websocket("会话绑定", session_id, f"角色: {resolved_role}, 房间连接数: {len(self.session_connections[session_id])}")
        return dict(meta)

    def touch(self, websocket: WebSocket) -> None:
        meta = self.connection_meta.get(websocket)
        if meta is not None:
            meta["last_seen_at"] = time.time()

    def get_connection_meta(self, websocket: WebSocket) -> Dict[str, Any]:
        meta = self.connection_meta.get(websocket)
        return dict(meta) if meta else {}

    def disconnect(self, websocket: WebSocket) -> None:
        """幂等断开并清理连接资源"""
        self._send_locks.pop(websocket, None)
        meta = self.connection_meta.pop(websocket, None)
        if not meta:
            return
        sid = meta.get("session_id")
        if sid and sid in self.session_connections:
            self.session_connections[sid].discard(websocket)
            if not self.session_connections[sid]:
                del self.session_connections[sid]
        cprint.websocket("连接断开", sid or "unknown", f"角色: {meta.get('role')}, 剩余在线: {len(self.connection_meta)}")

    async def send_to_connection(self, websocket: WebSocket, payload: Dict[str, Any]) -> bool:
        text = json.dumps(payload, ensure_ascii=False)
        ok = await self._send_text_safe(websocket, text)
        if not ok:
            self.disconnect(websocket)
        return ok

    async def broadcast_to_session(
        self,
        session_id: str,
        payload: Dict[str, Any],
        exclude: Optional[WebSocket] = None,
    ) -> int:
        targets = [c for c in self.session_connections.get(session_id, ()) if c != exclude]
        if not targets:
            return 0
        text = json.dumps(payload, ensure_ascii=False)
        return await self._dispatch_text(targets, text)

    async def broadcast_to_roles(
        self,
        roles: Collection[str],
        payload: Dict[str, Any],
        exclude: Optional[WebSocket] = None,
        exclude_session: Optional[str] = None,
    ) -> int:
        allowed = set(roles)
        recipients = [
            conn
            for conn, meta in list(self.connection_meta.items())
            if conn != exclude
            and meta.get("role") in allowed
            and (exclude_session is None or meta.get("session_id") != exclude_session)
        ]
        if not recipients:
            return 0
        text = json.dumps(payload, ensure_ascii=False)
        return await self._dispatch_text(recipients, text)

    async def prune_stale_connections(self, max_idle_seconds: float = 120.0) -> int:
        """清理超时未活跃连接"""
        now = time.time()
        stale = [
            conn
            for conn, meta in list(self.connection_meta.items())
            if now - float(meta.get("last_seen_at", now)) > max_idle_seconds
        ]
        for conn in stale:
            try:
                await asyncio.wait_for(conn.close(code=1001, reason="Idle timeout"), timeout=1.0)
            except Exception:
                pass
            self.disconnect(conn)
        return len(stale)


ws_manager = WebSocketConnectionManager()
