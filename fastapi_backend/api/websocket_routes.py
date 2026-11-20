"""
WebSocket 独立路由模块 (WebSocket Route & Event Dispatcher)
职责划分：
1. 负责管理 /ws 与 /ws/{session_id} 原生全双工长连接
2. 负责 WebSocket 连接鉴权、握手、订阅与生命周期管理
3. 负责解析与分发各类型事件 (subscribe, ping, typing, human_message, customer_message)
4. 与常规 REST API 严格解耦，保障连接池健康与异常边界隔离
"""

from typing import Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.websocket_manager import ws_manager
from services.memory_service import memory_service
from core.logger import log, cprint

ws_router = APIRouter(tags=["WebSocket 实时通信"])


# ==================== 事件处理器 (Event Handlers) ====================

async def handle_subscribe_event(websocket: WebSocket, data: Dict[str, Any], meta: Dict[str, Any], current_session_id: str):
    """处理终端加入/订阅会话事件"""
    target_session_id = data.get("sessionId") or current_session_id
    role = data.get("role") or meta.get("role", "customer")
    name = data.get("name") or meta.get("name", "")
    
    ws_manager.register_session(websocket, session_id=target_session_id, role=role, name=name)

    await websocket.send_json({
        "type": "subscribed",
        "sessionId": target_session_id,
        "role": role,
        "name": name,
    })
    return target_session_id


async def handle_ping_event(websocket: WebSocket):
    """处理心跳探活"""
    await websocket.send_json({"type": "pong"})


async def handle_typing_event(websocket: WebSocket, data: Dict[str, Any], meta: Dict[str, Any], current_session_id: str):
    """处理输入状态实时同步 (正在输入...)"""
    target_session_id = data.get("sessionId") or current_session_id
    sender_role = data.get("sender") or meta.get("role", "unknown")
    sender_name = data.get("name") or meta.get("name", "")
    is_typing = bool(data.get("isTyping", False))

    await ws_manager.broadcast_to_session(target_session_id, {
        "type": "typing",
        "sessionId": target_session_id,
        "sender": sender_role,
        "name": sender_name,
        "isTyping": is_typing,
    }, exclude=websocket)


async def handle_human_message_event(websocket: WebSocket, data: Dict[str, Any], meta: Dict[str, Any], current_session_id: str):
    """处理人工客服发言"""
    target_session_id = data.get("sessionId") or current_session_id
    content = data.get("content", "").strip()
    if not content:
        return

    agent_name = data.get("agentName") or meta.get("name") or "人工客服"
    agent_id = data.get("agentId", "agent_101")

    cprint.websocket("坐席发言", target_session_id, f"收到坐席 [{agent_name} ({agent_id})] 消息 ({len(content)} 字符)")

    # 状态机标记：人工介入中
    session = memory_service.get_session(target_session_id)
    if session:
        session["status"] = "HUMAN_INTERVENED"
        session["assignedAgent"] = agent_name
        session["assignedAgentId"] = agent_id

    # 持久化存储到会话记忆
    msg = memory_service.add_message(target_session_id, "human_agent", content)
    updated_session = memory_service.get_session(target_session_id)
    session_meta = memory_service.build_session_meta(updated_session) if updated_session else None

    # 1. 广播给该会话房间内的其他订阅者（仅发单条消息与轻量元数据）
    await ws_manager.broadcast_to_session(target_session_id, {
        "type": "message:new",
        "sessionId": target_session_id,
        "message": msg,
        "sessionMeta": session_meta,
    }, exclude=websocket)

    # 2. 广播给房间外的坐席/主管/同屏台（刷新队列与徽标）
    await ws_manager.broadcast_to_roles(
        ("agent", "supervisor", "dual_observer"),
        {
            "type": "session:update",
            "sessionId": target_session_id,
            "sessionMeta": session_meta,
        },
        exclude=websocket,
        exclude_session=target_session_id,
    )


async def handle_customer_message_event(websocket: WebSocket, data: Dict[str, Any], meta: Dict[str, Any], current_session_id: str):
    """处理客户发言"""
    target_session_id = data.get("sessionId") or current_session_id
    content = (data.get("content") or data.get("message") or "").strip()
    if not content:
        return

    cprint.websocket("客户发言", target_session_id, f"收到客户消息 ({len(content)} 字符)")

    msg = memory_service.add_message(target_session_id, "user", content)
    updated_session = memory_service.get_session(target_session_id)
    session_meta = memory_service.build_session_meta(updated_session) if updated_session else None

    # 广播给会话房间（排除发送方连接，仅发增量消息与轻量元数据）
    await ws_manager.broadcast_to_session(target_session_id, {
        "type": "message:new",
        "sessionId": target_session_id,
        "message": msg,
        "sessionMeta": session_meta,
    }, exclude=websocket)

    # 广播给房间外的坐席/主管/同屏台
    await ws_manager.broadcast_to_roles(
        ("agent", "supervisor", "dual_observer"),
        {
            "type": "session:update",
            "sessionId": target_session_id,
            "sessionMeta": session_meta,
        },
        exclude=websocket,
        exclude_session=target_session_id,
    )


async def handle_transfer_event(websocket: WebSocket, data: Dict[str, Any], meta: Dict[str, Any], current_session_id: str):
    """处理主动申请转接人工事件 (WebSocket 原生事件)"""
    target_session_id = data.get("sessionId") or current_session_id
    reason = data.get("reason", "客户端请求人工客服接入")
    target_agent_id = data.get("targetAgentId", "agent_101")
    operator_note = data.get("operatorNote", "WebSocket 转人工请求")
    trigger_type = data.get("triggerType", "user_requested")

    cprint.websocket("转接请求", target_session_id, f"WS 触发人工转接 -> 指派坐席工号: {target_agent_id}")

    _, session = memory_service.transfer_session(
        session_id=target_session_id,
        target_agent_id=target_agent_id,
        reason=reason,
        operator_note=operator_note,
        trigger_type=trigger_type
    )

    session_meta = memory_service.build_session_meta(session)
    last_msg = session["messages"][-1] if session.get("messages") else None
    room_payload: Dict[str, Any] = {
        "type": "session:update",
        "sessionId": target_session_id,
        "action": "transfer",
        "sessionMeta": session_meta,
    }
    if last_msg:
        room_payload["message"] = last_msg

    await ws_manager.broadcast_to_session(target_session_id, room_payload)
    await ws_manager.broadcast_to_roles(
        ("agent", "supervisor", "dual_observer"),
        {
            "type": "session:update",
            "sessionId": target_session_id,
            "action": "transfer",
            "sessionMeta": session_meta,
        },
        exclude_session=target_session_id,
    )


async def handle_intervene_event(websocket: WebSocket, data: Dict[str, Any], meta: Dict[str, Any], current_session_id: str):
    """处理人工坐席接管或释放回 AI 事件 (WebSocket 原生事件)"""
    target_session_id = data.get("sessionId") or current_session_id
    action = data.get("action", "takeover")  # "takeover" 或 "release"
    agent_id = data.get("agentId", "agent_101")
    note = data.get("note", "")

    session = memory_service.intervene_session(
        session_id=target_session_id,
        action=action,
        agent_id=agent_id,
        note=note
    )

    session_meta = memory_service.build_session_meta(session)
    last_msg = session["messages"][-1] if session.get("messages") else None
    room_payload: Dict[str, Any] = {
        "type": "session:update",
        "sessionId": target_session_id,
        "action": action,
        "sessionMeta": session_meta,
    }
    if last_msg:
        room_payload["message"] = last_msg

    await ws_manager.broadcast_to_session(target_session_id, room_payload)
    await ws_manager.broadcast_to_roles(
        ("agent", "supervisor", "dual_observer"),
        {
            "type": "session:update",
            "sessionId": target_session_id,
            "action": action,
            "sessionMeta": session_meta,
        },
        exclude_session=target_session_id,
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
            msg_type = data.get("type", "")
            meta = ws_manager.connection_meta.get(websocket, {})
            current_session_id = meta.get("session_id", current_session_id)
            
            # 依据事件类型进行优雅路由分发
            if msg_type in ("subscribe", "join"):
                current_session_id = await handle_subscribe_event(websocket, data, meta, current_session_id)
                
            elif msg_type == "ping":
                await handle_ping_event(websocket)
                
            elif msg_type == "typing":
                await handle_typing_event(websocket, data, meta, current_session_id)
                
            elif msg_type in ("human_message", "agent_message"):
                await handle_human_message_event(websocket, data, meta, current_session_id)
                
            elif msg_type in ("customer_message", "user_message"):
                await handle_customer_message_event(websocket, data, meta, current_session_id)
                
            elif msg_type in ("transfer", "request_human", "escalate"):
                await handle_transfer_event(websocket, data, meta, current_session_id)
                
            elif msg_type in ("intervene", "release", "takeover"):
                await handle_intervene_event(websocket, data, meta, current_session_id)

            elif msg_type in ("message", "chat"):
                # 兼容通用泛型消息结构
                role = data.get("role") or meta.get("role", "customer")
                if role in ("human_agent", "agent", "supervisor"):
                    await handle_human_message_event(websocket, data, meta, current_session_id)
                else:
                    await handle_customer_message_event(websocket, data, meta, current_session_id)
                
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
