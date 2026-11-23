"""
FastAPI 原生 WebSocket 连接池与实时广播管理器 (WebSocket Connection Manager)
纯 Python 后端全双工实时通信中枢：
1. 客户终端与人工客服坐席双向实时对话、毫秒级响应
2. 输入状态（typing indicator）毫秒级感知与广播
3. 人工转接（Transfer）、主动接管（Intervene）与交还 AI 的状态同步
4. 订阅会话动态切换、按角色定向广播、并发推送与僵尸连接清理
"""

import asyncio
import json
import time
from typing import Any, Collection, Dict, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from core.logger import log, cprint


DEFAULT_ROLE_NAMES: Dict[str, str] = {
    "customer": "客户",
    "agent": "人工坐席",
    "supervisor": "客服主管",
    "dual_observer": "同屏观测台",
}


class WebSocketConnectionManager:
    """管理活跃的 WebSocket 长连接，支持按会话房间广播、按角色广播与全局广播"""

    def __init__(self, send_timeout: float = 5.0):
        # 活跃连接映射表: session_id -> Set[WebSocket]
        self.session_connections: Dict[str, Set[WebSocket]] = {}
        # 连接元信息: WebSocket -> dict(session_id, role, name, has_custom_name, connected_at, last_seen_at)
        self.connection_meta: Dict[WebSocket, Dict[str, Any]] = {}
        # 所有已建立连接的集合
        self.all_connections: Set[WebSocket] = set()
        # 单连接串行写锁，防止多协程交错写入同一 WebSocket 触发协议异常
        self._send_locks: Dict[WebSocket, asyncio.Lock] = {}
        # 单次发送超时保护，防止单个慢连接阻塞整次广播
        self.send_timeout = send_timeout

    @staticmethod
    def _default_name_for_role(role: str) -> str:
        return DEFAULT_ROLE_NAMES.get(role, "客户")

    @staticmethod
    def _serialize_payload(payload: Dict[str, Any]) -> Optional[str]:
        """预序列化一次 JSON，隔离序列化异常（避免 TypeError 误伤全部在线连接）"""
        try:
            return json.dumps(payload, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            log.error(
                f"WebSocket payload JSON 序列化失败 (type={payload.get('type')}): {exc}",
                exc_info=True,
            )
            return None

    @staticmethod
    def _summarize_payload(payload: Dict[str, Any]) -> str:
        """生成脱敏的广播日志摘要（避免将客户/坐席完整聊天原文打印到日志）"""
        m_type = payload.get("type", "message")
        if m_type == "message:new":
            msg = payload.get("message") or {}
            content_len = len(str(msg.get("content") or ""))
            return f"新消息[{msg.get('role', 'unknown')}] ({content_len} 字符)"
        if m_type == "session:update":
            patch = payload.get("sessionPatch") or {}
            return f"状态变更[{payload.get('action', 'update')}] -> {patch.get('status', 'UPDATE')}"
        if m_type == "typing":
            return f"[{payload.get('role', 'unknown')}] 正在输入: {bool(payload.get('isTyping'))}"
        return f"事件: {m_type}"

    async def _send_text_safe(self, connection: WebSocket, text: str) -> bool:
        """带状态检查、单连接写锁与超时保护的安全发送"""
        if connection not in self.all_connections:
            return False

        client_state = getattr(connection, "client_state", WebSocketState.CONNECTED)
        app_state = getattr(connection, "application_state", WebSocketState.CONNECTED)
        if client_state != WebSocketState.CONNECTED or app_state != WebSocketState.CONNECTED:
            return False

        lock = self._send_locks.setdefault(connection, asyncio.Lock())
        try:
            async with lock:
                if connection not in self.all_connections:
                    return False
                await asyncio.wait_for(connection.send_text(text), timeout=self.send_timeout)
            return True
        except (WebSocketDisconnect, RuntimeError, ConnectionError, OSError) as exc:
            meta = self.connection_meta.get(connection, {})
            log.debug(
                f"WebSocket 发送时检测到连接已断开 (session={meta.get('session_id')}, role={meta.get('role')}): {exc}"
            )
            return False
        except asyncio.TimeoutError:
            meta = self.connection_meta.get(connection, {})
            log.warning(
                f"WebSocket 发送超时 (>{self.send_timeout}s)，将清理慢连接 "
                f"(session={meta.get('session_id')}, role={meta.get('role')})"
            )
            return False
        except Exception as exc:
            meta = self.connection_meta.get(connection, {})
            log.warning(
                f"WebSocket 发送发生异常 (session={meta.get('session_id')}, role={meta.get('role')}): {exc}",
                exc_info=True,
            )
            return False

    async def _dispatch_text(self, recipients: List[WebSocket], text: str) -> int:
        """并发推送已序列化文本并统一回收失效连接"""
        if not recipients:
            return 0

        results = await asyncio.gather(
            *(self._send_text_safe(conn, text) for conn in recipients),
            return_exceptions=True,
        )

        delivered = 0
        dead_connections: List[WebSocket] = []
        for conn, result in zip(recipients, results):
            if result is True:
                delivered += 1
            else:
                dead_connections.append(conn)

        for dead in dead_connections:
            self.disconnect(dead)

        return delivered

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str = "default",
        role: str = "customer",
        name: str = "",
    ) -> None:
        """接受并注册新的 WebSocket 连接；握手回包失败时自动回滚清理，避免僵尸连接泄漏"""
        await websocket.accept()
        try:
            self.all_connections.add(websocket)
            self._send_locks.setdefault(websocket, asyncio.Lock())
            meta = self.register_session(websocket, session_id=session_id, role=role, name=name)

            client = getattr(websocket, "client", None)
            client_addr = f"{client.host}:{client.port}" if client else "unknown"
            cprint.websocket(
                "握手成功",
                meta["session_id"],
                f"全双工长连接已就绪 (角色: {meta['role']}, 来源: {client_addr}, 在线连接数: {len(self.all_connections)})",
            )

            ack_payload = {
                "type": "subscribed",
                "sessionId": meta["session_id"],
                "role": meta["role"],
                "name": meta["name"],
            }
            ack_text = json.dumps(ack_payload, ensure_ascii=False)
            lock = self._send_locks[websocket]
            async with lock:
                await asyncio.wait_for(websocket.send_text(ack_text), timeout=self.send_timeout)
        except Exception as exc:
            log.warning(f"WebSocket 握手注册或确认包发送失败，回滚连接 (session={session_id}): {exc!r}")
            self.disconnect(websocket)
            raise

    def register_session(
        self,
        websocket: WebSocket,
        session_id: str,
        role: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """动态将会话与连接绑定或迁移（支持客户端后续发送 join/subscribe 切换会话）"""
        now = time.time()
        old_meta = self.connection_meta.get(websocket)
        if old_meta:
            old_session = old_meta.get("session_id")
            if old_session and old_session != session_id and old_session in self.session_connections:
                self.session_connections[old_session].discard(websocket)
                if not self.session_connections[old_session]:
                    del self.session_connections[old_session]

        clean_role = role.strip() if isinstance(role, str) else ""
        resolved_role = clean_role or (old_meta.get("role") if old_meta else None) or "customer"

        clean_name = name.strip() if isinstance(name, str) else ""
        if clean_name:
            resolved_name = clean_name
            has_custom_name = True
        elif old_meta and old_meta.get("has_custom_name"):
            resolved_name = old_meta["name"]
            has_custom_name = True
        else:
            # 若仅切换了角色而未显式指定姓名，避免沿用旧角色的默认称呼（如“客户”带到“agent”）
            resolved_name = self._default_name_for_role(resolved_role)
            has_custom_name = False

        self.all_connections.add(websocket)
        self._send_locks.setdefault(websocket, asyncio.Lock())
        self.session_connections.setdefault(session_id, set()).add(websocket)

        new_meta = {
            "session_id": session_id,
            "role": resolved_role,
            "name": resolved_name,
            "has_custom_name": has_custom_name,
            "connected_at": old_meta.get("connected_at", now) if old_meta else now,
            "last_seen_at": now,
        }
        self.connection_meta[websocket] = new_meta

        cprint.websocket(
            "会话绑定",
            session_id,
            f"连接绑定至会话房间 [{session_id}] (角色: {resolved_role}, 姓名: {resolved_name}, 房间内连接数: {len(self.session_connections[session_id])})",
        )
        return dict(new_meta)

    def touch(self, websocket: WebSocket) -> None:
        """刷新连接最近活跃时间（可在收到消息或 ping 时调用）"""
        meta = self.connection_meta.get(websocket)
        if meta is not None:
            meta["last_seen_at"] = time.time()

    def get_connection_meta(self, websocket: WebSocket) -> Dict[str, Any]:
        """安全获取连接元信息副本"""
        meta = self.connection_meta.get(websocket)
        return dict(meta) if meta else {}

    def disconnect(self, websocket: WebSocket) -> None:
        """幂等断开并清理连接"""
        was_tracked = websocket in self.all_connections or websocket in self.connection_meta
        self.all_connections.discard(websocket)
        self._send_locks.pop(websocket, None)
        meta = self.connection_meta.pop(websocket, None)

        if meta:
            session_id = meta.get("session_id")
            role = meta.get("role", "unknown")
            if session_id and session_id in self.session_connections:
                self.session_connections[session_id].discard(websocket)
                if not self.session_connections[session_id]:
                    del self.session_connections[session_id]
            cprint.websocket(
                "连接断开",
                session_id or "unknown",
                f"客户端注销 (角色: {role}, 剩余在线总数: {len(self.all_connections)})",
            )
        elif was_tracked:
            for sid in list(self.session_connections.keys()):
                self.session_connections[sid].discard(websocket)
                if not self.session_connections[sid]:
                    del self.session_connections[sid]

    async def send_to_connection(self, websocket: WebSocket, payload: Dict[str, Any]) -> bool:
        """向单个指定连接安全发送 JSON 消息"""
        text = self._serialize_payload(payload)
        if text is None:
            return False
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
        """向特定会话房间内的订阅者并发广播消息"""
        targets = list(self.session_connections.get(session_id, set()))
        echo_back = bool(payload.get("echoBack", False))
        recipients = [
            conn for conn in targets if not (conn == exclude and not echo_back)
        ]
        if not recipients:
            return 0

        text = self._serialize_payload(payload)
        if text is None:
            return 0

        summary = self._summarize_payload(payload)
        cprint.websocket(
            "房间广播",
            session_id,
            f"向会话房间 [{session_id}] 广播 {summary} (推送给 {len(recipients)} 个在线终端)",
        )
        return await self._dispatch_text(recipients, text)

    async def broadcast_all(
        self,
        payload: Dict[str, Any],
        exclude: Optional[WebSocket] = None,
        exclude_session: Optional[str] = None,
        roles: Optional[Collection[str]] = None,
    ) -> int:
        """向全局（或指定角色/排除指定会话的）在线连接并发广播系统事件"""
        allowed_roles = set(roles) if roles is not None else None
        recipients: List[WebSocket] = []
        for conn in list(self.all_connections):
            if exclude is not None and conn == exclude:
                continue
            meta = self.connection_meta.get(conn)
            if exclude_session is not None and meta and meta.get("session_id") == exclude_session:
                continue
            if allowed_roles is not None and (not meta or meta.get("role") not in allowed_roles):
                continue
            recipients.append(conn)

        if not recipients:
            return 0

        text = self._serialize_payload(payload)
        if text is None:
            return 0

        scope_label = (
            f"ROLES({','.join(sorted(allowed_roles))})" if allowed_roles is not None else "GLOBAL"
        )
        cprint.websocket(
            "全网广播",
            scope_label,
            f"向 {len(recipients)} 个目标终端并发广播事件: [{payload.get('type')}]",
        )
        return await self._dispatch_text(recipients, text)

    async def broadcast_to_roles(
        self,
        roles: Collection[str],
        payload: Dict[str, Any],
        exclude: Optional[WebSocket] = None,
        exclude_session: Optional[str] = None,
    ) -> int:
        """按角色定向广播（例如仅向 agent / supervisor / dual_observer 推送工作台全局事件，避免推给无关顾客）"""
        return await self.broadcast_all(
            payload,
            exclude=exclude,
            exclude_session=exclude_session,
            roles=roles,
        )

    async def prune_stale_connections(self, max_idle_seconds: float = 120.0) -> int:
        """清理超时未活跃或已半关闭的僵尸连接"""
        now = time.time()
        stale: List[WebSocket] = []
        for conn in list(self.all_connections):
            meta = self.connection_meta.get(conn, {})
            idle = now - float(meta.get("last_seen_at", now))
            client_state = getattr(conn, "client_state", WebSocketState.CONNECTED)
            if idle > max_idle_seconds or client_state != WebSocketState.CONNECTED:
                stale.append(conn)

        for conn in stale:
            try:
                await asyncio.wait_for(conn.close(code=1001, reason="Idle timeout"), timeout=1.0)
            except Exception:
                pass
            self.disconnect(conn)

        return len(stale)

    def get_stats(self) -> Dict[str, Any]:
        """获取当前 WebSocket 连接统计数据"""
        role_counts: Dict[str, int] = {}
        for meta in self.connection_meta.values():
            r = meta.get("role", "unknown")
            role_counts[r] = role_counts.get(r, 0) + 1

        return {
            "total_connections": len(self.all_connections),
            "active_sessions_count": len(self.session_connections),
            "sessions": list(self.session_connections.keys()),
            "session_connection_counts": {
                sid: len(conns) for sid, conns in self.session_connections.items()
            },
            "roles": role_counts,
        }


# 全局单例
ws_manager = WebSocketConnectionManager()

