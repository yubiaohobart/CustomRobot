"""
FastAPI 原生 WebSocket 连接池与实时广播管理器 (WebSocket Connection Manager)
纯 Python 后端全双工实时通信中枢：
1. 客户终端与人工客服坐席双向实时对话、毫秒级响应
2. 输入状态（typing indicator）毫秒级感知与广播
3. 人工转接（Transfer）、主动接管（Intervene）与交还 AI 的状态全员同步
4. 订阅会话动态切换与心跳保活
"""

from typing import Dict, List, Set, Any, Optional
import json
from fastapi import WebSocket, WebSocketDisconnect
from core.logger import log, cprint

class WebSocketConnectionManager:
    """管理活跃的 WebSocket 长连接，支持按会话分组广播与全局广播"""
    
    def __init__(self):
        # 活跃连接映射表: session_id -> Set[WebSocket]
        self.session_connections: Dict[str, Set[WebSocket]] = {}
        # 连接元信息: WebSocket -> dict(session_id, role, name, ...)
        self.connection_meta: Dict[WebSocket, Dict[str, Any]] = {}
        # 所有已建立连接的集合
        self.all_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, session_id: str = "default", role: str = "customer", name: str = ""):
        """接受并注册新的 WebSocket 连接"""
        await websocket.accept()
        self.all_connections.add(websocket)
        
        self.register_session(websocket, session_id=session_id, role=role, name=name)
        
        client_addr = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
        cprint.websocket("握手成功", session_id, f"全双工长连接已就绪 (角色: {role}, 来源: {client_addr}, 在线连接数: {len(self.all_connections)})")

        # 发送订阅成功握手确认包
        await websocket.send_json({
            "type": "subscribed",
            "sessionId": session_id,
            "role": role,
            "message": f"Python FastAPI WebSocket 长连接已就绪 (会话: {session_id}, 角色: {role})"
        })

    def register_session(self, websocket: WebSocket, session_id: str, role: Optional[str] = None, name: Optional[str] = None):
        """动态将会话与连接绑定或迁移（支持客户端后续发送 join/subscribe 切换会话）"""
        # 如果旧 session 存在，先解绑
        old_meta = self.connection_meta.get(websocket)
        if old_meta:
            old_session = old_meta.get("session_id")
            if old_session and old_session != session_id and old_session in self.session_connections:
                self.session_connections[old_session].discard(websocket)
                if not self.session_connections[old_session]:
                    del self.session_connections[old_session]
            if role is None:
                role = old_meta.get("role", "customer")
            if name is None:
                name = old_meta.get("name", "")

        # 注册到新 session
        if session_id not in self.session_connections:
            self.session_connections[session_id] = set()
        self.session_connections[session_id].add(websocket)

        self.connection_meta[websocket] = {
            "session_id": session_id,
            "role": role or "customer",
            "name": name or ("人工坐席" if role == "agent" else "客户")
        }
        cprint.websocket("会话绑定", session_id, f"连接绑定至会话房间 [{session_id}] (角色: {role or 'customer'}, 姓名: {name or '未知'}, 房间内连接数: {len(self.session_connections[session_id])})")

    def disconnect(self, websocket: WebSocket):
        """断开并清理连接"""
        self.all_connections.discard(websocket)
        meta = self.connection_meta.pop(websocket, None)
        if meta:
            session_id = meta.get("session_id")
            role = meta.get("role", "unknown")
            if session_id and session_id in self.session_connections:
                self.session_connections[session_id].discard(websocket)
                if not self.session_connections[session_id]:
                    del self.session_connections[session_id]
            cprint.websocket("连接断开", session_id or "unknown", f"客户端注销 (角色: {role}, 剩余在线总数: {len(self.all_connections)})")

    async def broadcast_to_session(self, session_id: str, payload: Dict[str, Any], exclude: Optional[WebSocket] = None):
        """向特定会话的所有订阅者广播消息"""
        targets = list(self.session_connections.get(session_id, set()))
        dead_connections = []

        m_type = payload.get("type", "message")
        summary = ""
        if m_type == "message:new":
            msg = payload.get("message", {})
            summary = f"[{msg.get('role')}]: {msg.get('content', '')[:25]}..."
        elif m_type == "session:update":
            summary = f"状态变更 -> {payload.get('session', {}).get('status', 'UPDATE')}"
        elif m_type == "typing":
            summary = f"[{payload.get('sender')}] 正在输入: {payload.get('isTyping')}"
        else:
            summary = f"事件: {m_type}"

        cprint.websocket("房间广播", session_id, f"向会话房间 [{session_id}] 广播 {summary} (推送给 {len(targets)} 个在线终端)")

        for connection in targets:
            if connection == exclude and not payload.get("echoBack", False):
                continue
            try:
                await connection.send_json(payload)
            except Exception:
                dead_connections.append(connection)

        # 清理异常断开的死连接
        for dead in dead_connections:
            self.disconnect(dead)

    async def broadcast_all(self, payload: Dict[str, Any]):
        """向所有连接广播系统事件（如全局大盘、转接通知、工作台会话更新）"""
        dead_connections = []
        cprint.websocket("全网广播", "GLOBAL", f"向所有已连接终端 ({len(self.all_connections)}个) 广播系统事件: [{payload.get('type')}]")
        for connection in list(self.all_connections):
            try:
                await connection.send_json(payload)
            except Exception:
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)

    def get_stats(self) -> Dict[str, Any]:
        """获取当前 WebSocket 连接统计数据"""
        return {
            "total_connections": len(self.all_connections),
            "active_sessions_count": len(self.session_connections),
            "sessions": list(self.session_connections.keys())
        }


# 全局单例
ws_manager = WebSocketConnectionManager()
