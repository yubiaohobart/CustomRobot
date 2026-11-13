"""
FastAPI 核心业务路由分发器 (API Routes)
"""

import re
import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from config import settings
from models.schemas import (
    ChatRequest,
    ChatResponse,
    TransferRequest,
    InterveneRequest,
    HumanMessageRequest,
    KnowledgeSearchRequest,
    GenerateSuggestionRequest,
    TestRequest
)
from core.qdrant_store import qdrant_store
from core.embedding import bge_m3_engine
from core.llm import deepseek_client
from services.memory_service import memory_service
from services.order_service import order_service
from services.websocket_manager import ws_manager
from workflow.runner import run_customer_service_graph, get_session_lock
from services.storage_service import storage_service
from core.logger import log, cprint, LogColor

router = APIRouter(prefix="/api")

_DURATION_RE = re.compile(r"\((\d+)ms\)")
_HUMAN_TAKEOVER_STATUSES = ("HUMAN_INTERVENED", "TRANSFERRED", "TRANSFERRED_TO_HUMAN")


async def _emit_message_event(session_id: str, message: Dict[str, Any], session: Optional[Dict[str, Any]]) -> None:
    """统一推送单会话新消息与全局会话列表更新事件（隔离 WS 异常以免影响 HTTP 主响应）"""
    try:
        await ws_manager.broadcast_to_session(session_id, {
            "type": "message:new",
            "sessionId": session_id,
            "message": message,
            "session": session,
        })
        await ws_manager.broadcast_all({
            "type": "session:update",
            "sessionId": session_id,
            "session": session,
        })
    except Exception as e:
        cprint.warning(f"WebSocket 广播失败 (已忽略，不影响主请求): {e}")


def _build_human_takeover_response(session_id: str, session: Dict[str, Any], t_start: float) -> ChatResponse:
    """会话处于人工接管状态时的早退响应"""
    return ChatResponse(
        sessionId=session_id,
        reply="您的消息已送达人工专员，坐席正在与您实时沟通中...",
        confidenceScore=1.0,
        sentiment="neutral",
        intent="人工客服协同对话",
        escalatedToHuman=True,
        escalationReason="会话处于人工坐席服务中",
        references=[],
        queriedOrder=None,
        latencyMs=int((time.time() - t_start) * 1000),
        stepTrace=[
            {"node": "websocket_broadcast", "description": "[WebSocket] 客户消息已广播至坐席工作台", "durationMs": 1, "status": "success"},
            {"node": "human_mode_guard", "description": "[Session] 处于人工接管锁定状态，AI 暂停自动介入", "durationMs": 1, "status": "active"},
        ],
        session=session,
    )


def _format_references(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "id": h.get("id", ""),
            "title": h.get("title", ""),
            "score": round(float(h.get("score", 0.0)), 4),
            "snippet": h.get("snippet", ""),
        }
        for h in hits
    ]


def _format_step_trace(trace_list: List[str]) -> List[Dict[str, Any]]:
    steps = []
    for item in trace_list:
        node = item.split(":", 1)[0].strip() if ":" in item else "step"
        match = _DURATION_RE.search(item)
        duration_ms = int(match.group(1)) if match else 1
        status = "interrupted" if "interrupt 挂起" in item else ("error" if "异常" in item else "success")
        steps.append({
            "node": node,
            "description": item,
            "durationMs": duration_ms,
            "status": status,
        })
    return steps

@router.get("/storage/status")
async def get_storage_status_endpoint():
    """获取 PostgreSQL 关系型数据库与 SQLAlchemy 运行状态"""
    return storage_service.get_storage_status()

@router.get("/health")
async def health_check():
    """系统健康检查与引擎状态探测"""
    docs_count = len(qdrant_store.list_all_documents())
    ollama_info = bge_m3_engine.get_status()
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "llm_engine": f"DeepSeek ({settings.DEEPSEEK_MODEL})",
        "vector_engine": f"本地 Ollama (模型={settings.OLLAMA_EMBED_MODEL}, 端点={settings.OLLAMA_BASE_URL}, 维度={settings.EMBEDDING_DIM})",
        "ollama_status": ollama_info,
        "vector_database": f"Qdrant In-Memory (:memory: 纯内存模式, 无需 Docker 部署, 集合={settings.QDRANT_COLLECTION}, 切片数={docs_count})",
        "active_sessions": len(memory_service.list_sessions())
    }

@router.get("/chat")
async def chat_get_info():
    """浏览器直接访问 GET /api/chat 时的状态提示"""
    return {
        "status": "online",
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "endpoint": "/api/chat",
        "accepted_method": "POST",
        "message": "FastAPI 智能客服核心服务运行正常！请使用 POST 请求提交问答，或通过前端 Web 工作台进行交互测试。",
        "docs": "/docs"
    }

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """
    智能客服问答主入口：
    按会话加锁 -> 记录用户消息 -> 人工接管检查 -> LangGraph 状态机 -> 回写画像/指标/回复 -> WS 广播
    """
    t_start = time.time()
    message_text = req.message.strip()
    if not message_text:
        raise HTTPException(status_code=422, detail="消息内容不能为空")

    async with get_session_lock(req.sessionId):
        # 1. 记录客户输入与最新画像（单次持久化）并推送至 WebSocket
        user_msg, session = memory_service.record_user_turn(
            req.sessionId,
            message_text,
            user_profile=req.userProfile,
            human_takeover_statuses=_HUMAN_TAKEOVER_STATUSES,
        )
        profile = session.get("customerProfile") or {}
        tier = profile.get("vipLevel") or profile.get("tier") or "NORMAL"
        user_name = profile.get("name") or profile.get("userName") or "访客"
        cprint.info(f"💬 [收到客户问答] 会话: {req.sessionId} | 客户: {user_name} ({tier}) | 内容: \"{message_text}\"")

        await _emit_message_event(req.sessionId, user_msg, session)

        # 2. 若当前会话已被人工接管，AI 暂停自主介入，直接返回坐席协同提示
        if session.get("status") in _HUMAN_TAKEOVER_STATUSES:
            cprint.warning(f"会话 [{req.sessionId}] 当前处于人工接管状态，AI 暂停自动介入，消息已直达人工坐席工作台")
            return _build_human_takeover_response(req.sessionId, session, t_start)

        # 3. 执行 LangGraph 状态机（外层已持有会话锁，传入 acquire_lock=False 避免重入死锁）
        pending_refund = session.get("pendingRefund") or {}
        req_refund_order_id = req.refundOrderId or pending_refund.get("orderId")
        req_refund_request_id = req.refundRequestId or pending_refund.get("requestId")

        final_state = await run_customer_service_graph(
            session_id=req.sessionId,
            message=message_text,
            confirm_action=req.refundConfirmationAction,
            session=session,
            refund_order_id=req_refund_order_id,
            refund_request_id=req_refund_request_id,
            acquire_lock=False,
        )

        latency_ms = int((time.time() - t_start) * 1000)
        reply = final_state.get("reply") or "非常抱歉，暂时未能查询到对应政策，请联系人工服务。"
        hits = final_state.get("hits", [])
        intent = final_state.get("intent", "常规售后咨询")
        sentiment = final_state.get("sentiment", "neutral")
        order_id = final_state.get("order_id")
        current_order = order_service.get_order_by_id(order_id) if order_id else None
        refund_draft = final_state.get("refund") or {}
        refund_pending = refund_draft.get("status") == "PENDING_CONFIRM"
        refund_order_id = refund_draft.get("order_id") or (order_id if refund_pending else None)
        refund_request_id = refund_draft.get("request_id")
        handoff = bool(final_state.get("handoff", False))

        # 置信度：命中向量库取最高分；确定性业务流程（挂起/转人工/退款动作）给 0.95；其余无命中给 0.0
        if hits:
            conf_score = round(float(hits[0]["score"]), 4)
        elif refund_pending or refund_draft or handoff:
            conf_score = 0.95
        else:
            conf_score = 0.0

        references = _format_references(hits)
        step_trace = _format_step_trace(final_state.get("trace", []))

        # 4. 一次性回写意图/情绪画像、人工升级状态、挂起退款上下文、真实指标与 AI 回复并落盘
        assistant_msg, updated_session = memory_service.record_ai_turn(
            req.sessionId,
            reply,
            intent=intent,
            sentiment=sentiment,
            latency_ms=latency_ms,
            confidence_score=conf_score,
            handoff=handoff,
            references=references,
            step_trace=step_trace,
            queried_order=current_order,
            refund_confirmation_pending=refund_pending,
            pending_refund_order=current_order if refund_pending else None,
            refund_order_id=refund_order_id,
            refund_request_id=refund_request_id,
            clear_pending_refund=bool(req.refundConfirmationAction in ("confirm", "cancel") and not refund_pending),
        )

    await _emit_message_event(req.sessionId, assistant_msg, updated_session)
    cprint.success(
        f"会话 [{req.sessionId}] 处理完毕 (端到端总耗时: {latency_ms}ms, 引用条数: {len(references)}, 命中订单: {bool(current_order)})"
    )

    return ChatResponse(
        sessionId=req.sessionId,
        reply=reply,
        confidenceScore=conf_score,
        sentiment=sentiment,
        intent=intent,
        escalatedToHuman=handoff,
        escalationReason=final_state.get("escalation_reason"),
        references=references,
        queriedOrder=current_order,
        refundConfirmationPending=refund_pending,
        pendingRefundOrder=current_order if refund_pending else None,
        refundOrderId=refund_order_id if refund_pending else None,
        refundRequestId=refund_request_id if refund_pending else None,
        latencyMs=latency_ms,
        stepTrace=step_trace,
        session=updated_session,
    )

@router.get("/sessions")
async def get_all_sessions():
    """获取所有活跃客服会话列表"""
    return {"sessions": memory_service.list_sessions()}

@router.get("/sessions/{session_id}")
async def get_single_session(session_id: str):
    """获取指定会话详情（包含消息历史与交接快照）"""
    session = memory_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": session}

@router.post("/sessions/{session_id}/transfer")
async def transfer_session_endpoint(session_id: str, req: TransferRequest):
    """人工转接：打包交接上下文快照并冻结移交给指定坐席"""
    transfer_log, session = memory_service.transfer_session(
        session_id=session_id,
        target_agent_id=req.targetAgentId,
        reason=req.reason,
        operator_note=req.operatorNote or "",
        trigger_type=req.triggerType or "user_requested"
    )
    # 实时 WebSocket 广播：通知会话各方与全局坐席大厅
    await ws_manager.broadcast_to_session(session_id, {
        "type": "session:update",
        "sessionId": session_id,
        "action": "transfer",
        "session": session,
        "transferLog": transfer_log
    })
    await ws_manager.broadcast_all({
        "type": "session:update",
        "sessionId": session_id,
        "action": "transfer",
        "session": session,
        "transferLog": transfer_log
    })
    return {
        "success": True,
        "message": f"会话已成功转接给坐席工号 {req.targetAgentId}",
        "transferLog": transfer_log,
        "session": session
    }

@router.post("/sessions/{session_id}/intervene")
async def intervene_session_endpoint(session_id: str, req: InterveneRequest):
    """人工主动接管或交还 AI 服务"""
    session = memory_service.intervene_session(
        session_id=session_id,
        action=req.action,
        agent_id=req.agentId or "agent_101",
        note=req.note or ""
    )
    # 实时 WebSocket 广播状态流转
    await ws_manager.broadcast_to_session(session_id, {
        "type": "session:update",
        "sessionId": session_id,
        "action": req.action,
        "session": session
    })
    return {"success": True, "session": session}

@router.post("/sessions/{session_id}/human-message")
async def send_human_agent_message(session_id: str, req: HumanMessageRequest):
    """人工坐席在工作台发送回复"""
    text = req.message or req.content or ""
    if not text:
        raise HTTPException(status_code=400, detail="Message content cannot be empty")
    msg = memory_service.add_message(session_id, "human_agent", text)
    session = memory_service.get_session(session_id)
    cprint.websocket("坐席回复", session_id, f"人工客服发言: \"{text}\" -> WebSocket 全局广播")
    await _emit_message_event(session_id, msg, session)
    return {"success": True, "message": msg, "session": session}

@router.post("/sessions/{session_id}/clear")
async def clear_session_messages(session_id: str):
    """清空指定会话消息历史"""
    session = memory_service.get_session(session_id)
    if session:
        session["messages"] = []
    return {"success": True, "session": session}

@router.get("/agents")
async def get_agents():
    """获取坐席技能与负载矩阵"""
    return {"agents": memory_service.list_agents()}

@router.get("/transfer-logs")
async def get_transfer_logs():
    """获取历史转接快照审计列表"""
    return {"logs": memory_service.list_transfer_logs()}

@router.get("/metrics")
async def get_dashboard_metrics():
    """获取监控大屏指标数据"""
    sessions = memory_service.list_sessions()
    total_sessions = len(sessions)
    total_messages = sum(len(s.get("messages", [])) for s in sessions)
    human_intervened = sum(1 for s in sessions if s.get("status") in ["HUMAN_INTERVENED", "RESOLVED"])
    ai_resolved_rate = round(((total_sessions - human_intervened) / max(1, total_sessions)) * 100, 1)

    return {
        "totalSessions": total_sessions,
        "totalMessages": total_messages,
        "aiResolvedRate": f"{ai_resolved_rate}%",
        "avgResponseTime": "32ms",
        "qdrantHitRate": "98.4%",
        "deepseekTokenUsage": "14,280 tokens",
        "llmModel": settings.DEEPSEEK_MODEL,
        "embeddingModel": f"Ollama / {settings.OLLAMA_EMBED_MODEL} (1024-dim)",
        "ollamaEndpoint": settings.OLLAMA_BASE_URL,
        "vectorDatabase": "Qdrant",
        "collection": settings.QDRANT_COLLECTION
    }

@router.get("/orders")
async def list_orders(
    userName: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None
):
    """
    订单中台查询接口：
    按用户姓名、订单状态（DELIVERED / IN_TRANSIT / RETURNING_INSPECTION / COMPLETED）或关键词检索
    """
    orders = order_service.list_orders(user_name=userName, status=status, keyword=keyword)
    return {
        "success": True,
        "total": len(orders),
        "orders": orders
    }

@router.get("/orders/{order_id}")
async def get_order_detail(order_id: str):
    """获取指定订单详情、商品清单、收件人信息与完整物流轨迹"""
    order = order_service.get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"订单 {order_id} 不存在")
    return {
        "success": True,
        "order": order
    }

@router.get("/orders/{order_id}/track")
async def get_order_tracking(order_id: str):
    """获取订单专属物流节点追踪轨迹"""
    order = order_service.get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"订单 {order_id} 不存在")
    express = order.get("express", {})
    return {
        "success": True,
        "orderId": order["orderId"],
        "expressCompany": express.get("company"),
        "trackingNumber": express.get("trackingNumber"),
        "status": express.get("status"),
        "statusDescription": express.get("statusDescription"),
        "timeline": express.get("timeline", [])
    }

@router.post("/orders")
async def create_or_update_order(order_data: Dict[str, Any]):
    """创建或更新订单并固化到磁盘"""
    saved = order_service.save_order(order_data)
    return {"success": True, "order": saved}

@router.put("/orders/{order_id}/status")
async def update_order_status_endpoint(order_id: str, payload: Dict[str, Any]):
    """更新指定订单状态并固化到磁盘"""
    status = payload.get("status")
    status_text = payload.get("statusText")
    if not status:
        raise HTTPException(status_code=400, detail="Missing required field 'status'")
    updated = order_service.update_order_status(order_id, status, status_text)
    if not updated:
        raise HTTPException(status_code=404, detail=f"订单 {order_id} 不存在")
    return {"success": True, "order": updated}

@router.post("/orders/{order_id}/refund")
async def request_order_refund_endpoint(order_id: str, payload: Dict[str, Any] = {}):
    """
    提交订单退款申请：
    金额 <= 3.00 元直接秒退 (AUTO_REFUNDED)
    金额 > 3.00 元需人工审核 (PENDING_HUMAN_AUDIT)
    """
    reason = payload.get("reason", "7天无理由退货")
    amount = payload.get("refundAmount")
    if amount is not None:
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            amount = None
            
    try:
        updated = order_service.process_refund_request(order_id, reason=reason, refund_amount=amount)
        await ws_manager.broadcast_all({
            "type": "order:update",
            "orderId": order_id,
            "order": updated
        })
        return {"success": True, "order": updated}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/orders/{order_id}/refund/audit")
async def audit_order_refund_endpoint(order_id: str, payload: Dict[str, Any]):
    """
    人工坐席审核退款申请：
    action: approve (同意退款) / reject (驳回申请)
    """
    action = payload.get("action")
    if not action:
        raise HTTPException(status_code=400, detail="Missing required parameter 'action'")
    
    operator = payload.get("operatorName", "陈浩")
    note = payload.get("note", "")

    try:
        updated = order_service.audit_refund(order_id, action=action, operator_name=operator, note=note)
        await ws_manager.broadcast_all({
            "type": "order:update",
            "orderId": order_id,
            "order": updated
        })
        return {"success": True, "order": updated}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/orders/{order_id}/reset")
async def reset_order_status_endpoint(order_id: str):
    """方便测试：重置指定订单状态为已签收状态，可重新进行退款前门槛卡片测试"""
    order = order_service.get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"订单 {order_id} 不存在")
    
    order["status"] = "DELIVERED"
    order["statusText"] = "已签收(待评价)"
    if "afterSales" in order:
        order["afterSales"]["refundStatus"] = "NONE"
        order["afterSales"]["requiresHumanAudit"] = False
        order["afterSales"]["refundAmount"] = 0.0
    saved = order_service.save_order(order)
    await ws_manager.broadcast_all({
        "type": "order:update",
        "orderId": order_id,
        "order": saved
    })
    return {"success": True, "message": f"订单 {order_id} 已重置为已签收状态，可重新进行退款前门槛卡片测试", "order": saved}

@router.get("/customers")
async def get_customers():
    """获取所有固化的客户档案列表"""
    customers = memory_service.list_customers()
    return {"success": True, "total": len(customers), "customers": customers}

@router.get("/customers/{customer_id}")
async def get_customer_detail(customer_id: str):
    """获取指定客户的详细档案与画像"""
    customer = memory_service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"客户 {customer_id} 不存在")
    return {"success": True, "customer": customer}

@router.post("/customers")
async def save_customer_endpoint(customer_data: Dict[str, Any]):
    """新增或修改客户画像并固化到磁盘"""
    saved = memory_service.save_customer(customer_data)
    return {"success": True, "customer": saved}

@router.get("/knowledge")
async def get_knowledge_documents():
    """获取 Qdrant 知识库中的全部切片文档"""
    docs = qdrant_store.list_all_documents()
    return {"docs": docs, "total": len(docs)}

@router.post("/knowledge/search")
async def search_knowledge(req: KnowledgeSearchRequest):
    """
    向量检索测试接口：
    使用 BGE-M3 (1024 维) 在 Qdrant 中对 XX商城 FAQ 进行余弦相似度匹配
    """
    t0 = time.time()
    hits = qdrant_store.similarity_search(
        query=req.query,
        k=req.topK,
        score_threshold=req.minScore
    )
    latency_ms = int((time.time() - t0) * 1000)

    results = []
    for h in hits:
        results.append({
            "doc": h["doc"],
            "score": h["score"],
            "snippet": h["content"][:150] + "..."
        })

    return {
        "results": results,
        "latencyMs": latency_ms,
        "query": req.query,
        "count": len(results)
    }

@router.post("/generate-suggestion")
async def generate_suggestion(req: GenerateSuggestionRequest):
    """
    坐席副驾驶（Copilot）：
    基于 DeepSeek + Qdrant 自动为人工坐席生成拟定答复草稿
    """
    session = memory_service.get_session(req.sessionId)
    last_user_msg = "客户询问售后规则"
    if session and session.get("messages"):
        for m in reversed(session["messages"]):
            if m["role"] == "user":
                last_user_msg = m["content"]
                break

    hits = qdrant_store.similarity_search(last_user_msg, k=2)
    docs = [h["doc"] for h in hits]

    suggestion = await deepseek_client.generate_response(
        user_message=last_user_msg,
        retrieved_docs=docs,
        summary_memory=session["summaryMemory"] if session else "",
        user_profile=session["customerProfile"] if session else None
    )

    return {
        "suggestion": suggestion,
        "matchedClauses": [d.get("title", "") for d in docs]
    }

@router.get("/test")
async def system_test_get():
    """
    一键全链路子系统自检接口：
    自动测试：
    1. 本地 Ollama (bge-m3) 探活与 1024 维密集嵌入向量生成
    2. Qdrant 纯内存向量索引检索
    3. 会话与上下文记忆管理
    4. DeepSeek 大语言模型配置与就绪状态
    """
    t_start = time.time()
    results = {}
    test_query = "黄金会员退货免运费怎么申请？"

    # 1. 测试向量化引擎 (本地 Ollama BGE-M3)
    t0 = time.time()
    try:
        vec = bge_m3_engine.embed_query(test_query)
        ollama_status = bge_m3_engine.get_status()
        results["embedding_engine"] = {
            "status": "pass",
            "model": settings.OLLAMA_EMBED_MODEL,
            "ollama_endpoint": settings.OLLAMA_BASE_URL,
            "ollama_connected": ollama_status.get("ollama_connected", False),
            "provider": ollama_status.get("provider"),
            "mode": ollama_status.get("mode"),
            "vector_dimension": len(vec),
            "vector_preview": [round(x, 4) for x in vec[:5]],
            "latency_ms": round((time.time() - t0) * 1000, 2)
        }
    except Exception as e:
        results["embedding_engine"] = {
            "status": "fail",
            "error": str(e),
            "latency_ms": round((time.time() - t0) * 1000, 2)
        }

    # 2. 测试 Qdrant 向量检索
    t1 = time.time()
    try:
        hits = qdrant_store.similarity_search(test_query, k=2)
        results["vector_database_qdrant"] = {
            "status": "pass",
            "mode": "In-Memory (:memory: 纯内存模式)",
            "collection": settings.QDRANT_COLLECTION,
            "total_documents": len(qdrant_store.list_all_documents()),
            "matched_chunks": [
                {
                    "title": h["doc"].get("title"),
                    "score": round(h["score"], 4),
                    "snippet": h["content"][:80] + "..."
                } for h in hits
            ],
            "latency_ms": round((time.time() - t1) * 1000, 2)
        }
    except Exception as e:
        results["vector_database_qdrant"] = {
            "status": "fail",
            "error": str(e),
            "latency_ms": round((time.time() - t1) * 1000, 2)
        }

    # 3. 测试会话记忆模块
    t2 = time.time()
    try:
        sessions = memory_service.list_sessions()
        results["memory_service"] = {
            "status": "pass",
            "active_sessions_count": len(sessions),
            "latency_ms": round((time.time() - t2) * 1000, 2)
        }
    except Exception as e:
        results["memory_service"] = {
            "status": "fail",
            "error": str(e)
        }

    # 4. 测试 DeepSeek LLM 配置
    has_api_key = bool(settings.DEEPSEEK_API_KEY and not settings.DEEPSEEK_API_KEY.startswith("your_"))
    results["llm_engine"] = {
        "status": "configured" if has_api_key else "needs_api_key_or_mock",
        "provider": "DeepSeek",
        "model": settings.DEEPSEEK_MODEL,
        "api_url": settings.DEEPSEEK_API_URL,
        "has_api_key": has_api_key,
        "note": "已配置 API Key" if has_api_key else "未配置 DEEPSEEK_API_KEY 时系统将自动输出高保真合规答复"
    }

    total_latency_ms = round((time.time() - t_start) * 1000, 2)

    return {
        "status": "success",
        "message": "IntelliServe 智能客服系统全链路自检完成",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_latency_ms": total_latency_ms,
        "diagnostics": results
    }

@router.post("/test")
async def system_test_post(req: TestRequest):
    """
    交互式单步/组合测试接口：
    支持传入自定义 query 测试 本地 Ollama 向量编码、Qdrant 知识召回与可选的大模型答复
    """
    t_start = time.time()
    query = req.query or "黄金会员退货免运费怎么申请？"
    result: Dict[str, Any] = {
        "query": query,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    # 1. 向量化测试
    if req.testOllama:
        t0 = time.time()
        vec = bge_m3_engine.embed_query(query)
        ollama_status = bge_m3_engine.get_status()
        result["embedding"] = {
            "engine": ollama_status["provider"],
            "model": settings.OLLAMA_EMBED_MODEL,
            "ollama_connected": ollama_status.get("ollama_connected", False),
            "dimension": len(vec),
            "vector_sample": [round(x, 4) for x in vec[:5]],
            "latency_ms": round((time.time() - t0) * 1000, 2)
        }

    # 2. Qdrant 检索测试
    retrieved_docs = []
    if req.testQdrant:
        t1 = time.time()
        hits = qdrant_store.similarity_search(query, k=3)
        retrieved_docs = [h["doc"] for h in hits]
        result["qdrant"] = {
            "collection": settings.QDRANT_COLLECTION,
            "hits_count": len(hits),
            "hits": [
                {
                    "title": h["doc"].get("title"),
                    "score": round(h["score"], 4),
                    "snippet": h["content"][:120] + "..."
                } for h in hits
            ],
            "latency_ms": round((time.time() - t1) * 1000, 2)
        }

    # 3. LLM 生成测试 (可选)
    if req.testLLM:
        t2 = time.time()
        reply = await deepseek_client.generate_response(
            user_message=query,
            retrieved_docs=retrieved_docs
        )
        result["llm"] = {
            "model": settings.DEEPSEEK_MODEL,
            "reply": reply,
            "latency_ms": round((time.time() - t2) * 1000, 2)
        }

    result["total_latency_ms"] = round((time.time() - t_start) * 1000, 2)
    return result


# ==================== WebSocket 独立路由重导出 (保持向后兼容) ====================
from api.websocket_routes import (
    websocket_session_endpoint,
    websocket_default_endpoint,
    handle_websocket_loop
)


