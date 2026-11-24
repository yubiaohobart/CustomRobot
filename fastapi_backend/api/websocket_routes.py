"""
WebSocket 独立路由模块 (WebSocket Route & Event Dispatcher)
职责划分：
1. 负责管理 /ws 与 /ws/{session_id} 原生全双工长连接
2. 负责 WebSocket 连接鉴权、握手、订阅与生命周期管理
3. 负责解析与分发轻量实时事件 (join, typing, ping)；业务写入统一走 REST API + 服务端广播
4. 与常规 REST API 严格解耦，保障连接池健康与异常边界隔离
"""

from typing import Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.websocket_manager import ws_manager, build_ws_event
from core.logger import log

ws_router = APIRouter(tags=["WebSocket 实时通信"])


def _extract_event_data(payload: Dict[str, Any]) -> Dict[str, Any]:
    """提取客户端消息体（优先读取统一信封 data 字段，兼容平铺传参）"""
    nested = payload.get("data")
    return nested if isinstance(nested, dict) else payload


# ==================== 事件处理器 (Event Handlers) ====================

async def handle_join_event(websocket: WebSocket, payload: Dict[str, Any], meta: Dict[str, Any], current_session_id: str) -> str:
    """处理终端加入/切换会话事件"""
    body = _extract_event_data(payload)
    target_session_id = payload.get("sessionId") or body.get("sessionId") or current_session_id
    role = body.get("role") or meta.get("role", "customer")
    name = body.get("name") if "name" in body else meta.get("name", "")

    registered = ws_manager.register_session(websocket, session_id=target_session_id, role=role, name=name)

    await ws_manager.send_to_connection(
        websocket,
        build_ws_event(
            "joined",
            {"role": registered["role"], "name": registered["name"]},
            session_id=registered["session_id"],
        ),
    )
    return registered["session_id"]


async def handle_ping_event(websocket: WebSocket) -> None:
    """处理心跳探活"""
    await ws_manager.send_to_connection(websocket, build_ws_event("pong", {}))


async def handle_typing_event(websocket: WebSocket, payload: Dict[str, Any], meta: Dict[str, Any], current_session_id: str) -> None:
    """处理输入状态实时同步 (正在输入...)"""
    body = _extract_event_data(payload)
    target_session_id = payload.get("sessionId") or body.get("sessionId") or current_session_id
    role = body.get("role") or meta.get("role", "unknown")
    name = body.get("name") or meta.get("name", "")
    is_typing = bool(body.get("isTyping", False))

    await ws_manager.broadcast_to_session(
        target_session_id,
        build_ws_event(
            "typing",
            {"role": role, "name": name, "isTyping": is_typing},
            session_id=target_session_id,
        ),
        exclude=websocket,
    )


# ==================== WebSocket 连接主循环 ====================

async def handle_websocket_loop(websocket: WebSocket, initial_session_id: str):
    """
    WebSocket 连接事件监听主循环：
    严格隔离异常边界，保障长连接断线自动注销与资源回收
    """
    await ws_manager.connect(websocket, session_id=initial_session_id)
    current_session_id = initial_session_id

    try:
        while True:
            data = await websocket.receive_json()
            ws_manager.touch(websocket)
            if not isinstance(data, dict):
                log.warning(f"收到非对象 JSON WebSocket 帧，已忽略: {type(data).__name__}")
                continue

            msg_type = data.get("type", "")
            meta = ws_manager.get_connection_meta(websocket)
            current_session_id = meta.get("session_id", current_session_id)

            if msg_type == "join":
                current_session_id = await handle_join_event(websocket, data, meta, current_session_id)
            elif msg_type == "typing":
                await handle_typing_event(websocket, data, meta, current_session_id)
            elif msg_type == "ping":
                await handle_ping_event(websocket)
            else:
                log.warning(f"收到未识别的 WebSocket 消息类型: {msg_type}")

    except WebSocketDisconnect:
        log.info(f"WebSocket 正常断开连接: {current_session_id}")
        ws_manager.disconnect(websocket)
    except Exception as e:
        log.error(f"WebSocket 连接异常退出: {e}", exc_info=True)
        ws_manager.disconnect(websocket)


# ==================== 路由端点注册 ====================

@ws_router.websocket("/ws/{session_id}")
async def websocket_session_endpoint(websocket: WebSocket, session_id: str):
    """FastAPI 原生 WebSocket 端点 (按会话路由: /ws/{session_id} 或 /api/ws/{session_id})"""
    await handle_websocket_loop(websocket, initial_session_id=session_id)


@ws_router.websocket("/ws")
async def websocket_default_endpoint(websocket: WebSocket):
    """FastAPI 原生 WebSocket 端点 (默认连接端点: /ws 或 /api/ws，支持后续消息包动态加入会话)"""
    await handle_websocket_loop(websocket, initial_session_id="session_user_001")
