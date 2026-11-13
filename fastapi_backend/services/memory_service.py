"""
会话记忆管理服务 (Session Memory & Human Transfer Service)
维持多轮会话状态、长期记忆、客户画像、转接上下文快照打包与审计日志
全面集成 storage_service 磁盘持久化固化存储，消息写入、坐席移交与画像变更实时写入磁盘文件
"""

import time
import uuid
import datetime
from typing import Dict, Any, List, Optional, Tuple
from core.logger import log, cprint, LogColor
from services.storage_service import storage_service
from models.entities import (
    SessionModel,
    ChatMessageModel,
    CustomerModel,
    AgentModel,
    TransferLogModel
)


class MemoryService:
    def __init__(self):
        # 依赖 storage_service 实现跨进程、跨重启持久化固化
        pass

    def _ensure_session_defaults(self, session: Dict[str, Any], user_profile: Optional[Dict[str, Any]] = None) -> bool:
        """补齐缺损字段并将新传入的 userProfile 增量合并进会话画像，返回是否发生变更"""
        changed = False
        if "metrics" not in session or not isinstance(session["metrics"], dict):
            session["metrics"] = {"totalTurns": len(session.get("messages", [])), "avgLatencyMs": 350, "avgConfidence": 0.95, "escalatedAt": None}
            changed = True
        if "customerProfile" not in session or not isinstance(session["customerProfile"], dict):
            session["customerProfile"] = {
                "name": session.get("userName", "客户"),
                "vipLevel": "普通会员",
                "sentiment": "neutral",
                "urgency": "中",
                "intent": "常规业务咨询",
                "tags": ["普通会员"],
                "orderId": ""
            }
            changed = True

        if user_profile:
            profile = session["customerProfile"]
            for k, v in user_profile.items():
                if v is not None and v != "" and profile.get(k) != v:
                    profile[k] = v
                    changed = True
            resolved_name = user_profile.get("name") or user_profile.get("userName")
            if resolved_name and profile.get("name") != resolved_name:
                profile["name"] = resolved_name
                session["userName"] = resolved_name
                changed = True
            resolved_vip = user_profile.get("vipLevel") or user_profile.get("tier")
            if resolved_vip and profile.get("vipLevel") != resolved_vip:
                profile["vipLevel"] = resolved_vip
                changed = True

        return changed

    def get_or_create_session(self, session_id: str, user_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        session = storage_service.get_session(session_id)
        if session:
            if self._ensure_session_defaults(session, user_profile):
                session["updatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                storage_service.save_session(session)
            return session

        # 不存在则创建并立即固化到磁盘
        up = user_profile or {}
        name = up.get("name") or up.get("userName") or "客户"
        vip = up.get("vipLevel") or up.get("tier") or "普通会员"
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        profile = {
            "name": name,
            "phone": up.get("phone", ""),
            "vipLevel": vip,
            "sentiment": up.get("sentiment", "neutral"),
            "urgency": up.get("urgency", "中"),
            "intent": up.get("intent", "售后咨询"),
            "tags": up.get("tags", [vip]),
            "orderId": up.get("orderId", f"ORD-2026-{uuid.uuid4().hex[:6].upper()}"),
        }
        # 保留前端/调用方传入的额外上下文键（如 tier、userId、recentOrder 等）
        for k, v in up.items():
            if k not in profile and v is not None:
                profile[k] = v

        new_session = {
            "id": session_id,
            "userName": name,
            "status": "AI_HANDLING",
            "assignedAgent": None,
            "assignedAgentId": None,
            "customerProfile": profile,
            "summaryMemory": f"{name}（{vip}）于今日建立咨询连接。",
            "messages": [],
            "metrics": {
                "totalTurns": 0,
                "avgLatencyMs": 350,
                "avgConfidence": 0.95,
                "escalatedAt": None
            },
            "contextSnapshot": None,
            "latestTransfer": None,
            "unreadForAgent": False,
            "createdAt": now_str,
            "updatedAt": now_str
        }
        storage_service.save_session(new_session)
        return new_session

    def _append_message_in_place(
        self,
        session: Dict[str, Any],
        role: str,
        content: str,
        confidence_score: Optional[float] = None,
        references: Optional[List[Dict[str, Any]]] = None,
        step_trace: Optional[List[Dict[str, Any]]] = None,
        queried_order: Optional[Dict[str, Any]] = None,
        refund_confirmation_pending: Optional[bool] = None,
        pending_refund_order: Optional[Dict[str, Any]] = None,
        refund_order_id: Optional[str] = None,
        refund_request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """在已加载的 session 对象上原地追加消息与摘要更新（不单独落盘）"""
        msg_id = f"m_{int(time.time() * 1000)}_{len(session.get('messages', []))}"
        msg: Dict[str, Any] = {
            "id": msg_id,
            "role": role,
            "content": content,
            "timestamp": time.strftime("%H:%M:%S"),
        }
        if confidence_score is not None:
            msg["confidenceScore"] = confidence_score
        if references:
            msg["references"] = references
        if step_trace:
            msg["stepTrace"] = step_trace
        if queried_order:
            msg["queriedOrder"] = queried_order
        if refund_confirmation_pending:
            msg["refundConfirmationPending"] = True
        if pending_refund_order:
            msg["pendingRefundOrder"] = pending_refund_order
            if "queriedOrder" not in msg:
                msg["queriedOrder"] = pending_refund_order
        if refund_order_id:
            msg["refundOrderId"] = refund_order_id
        if refund_request_id:
            msg["refundRequestId"] = refund_request_id

        session.setdefault("messages", []).append(msg)
        self._ensure_session_defaults(session)
        session["metrics"]["totalTurns"] = len(session["messages"])

        summary = session.get("summaryMemory", "")
        if role == "user":
            session["summaryMemory"] = (summary + f" 客户提问：'{content}'；")[-1000:]
        elif role in ("assistant", "human_agent"):
            prefix = "AI答复" if role == "assistant" else "人工坐席答复"
            session["summaryMemory"] = (summary + f" {prefix}：'{content[:60]}...'；")[-1000:]

        session["updatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return msg

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        confidence_score: Optional[float] = None,
        references: Optional[List[Dict[str, Any]]] = None,
        step_trace: Optional[List[Dict[str, Any]]] = None,
        queried_order: Optional[Dict[str, Any]] = None,
        refund_confirmation_pending: Optional[bool] = None,
        pending_refund_order: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        session = self.get_or_create_session(session_id)
        msg = self._append_message_in_place(
            session,
            role,
            content,
            confidence_score=confidence_score,
            references=references,
            step_trace=step_trace,
            queried_order=queried_order,
            refund_confirmation_pending=refund_confirmation_pending,
            pending_refund_order=pending_refund_order,
        )
        storage_service.save_session(session)
        return msg

    def record_user_turn(
        self,
        session_id: str,
        content: str,
        user_profile: Optional[Dict[str, Any]] = None,
        human_takeover_statuses: Tuple[str, ...] = ("HUMAN_INTERVENED", "TRANSFERRED", "TRANSFERRED_TO_HUMAN"),
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """单次读写完成：获取/创建会话 + 合并最新画像 + 写入用户消息 + 人工模式未读标记 + 落盘"""
        session = storage_service.get_session(session_id)
        if session:
            self._ensure_session_defaults(session, user_profile)
        else:
            session = self.get_or_create_session(session_id, user_profile)

        if session.get("status") in human_takeover_statuses:
            session["unreadForAgent"] = True

        user_msg = self._append_message_in_place(session, "user", content)
        storage_service.save_session(session)
        return user_msg, session

    def record_ai_turn(
        self,
        session_id: str,
        reply: str,
        *,
        intent: str,
        sentiment: str,
        latency_ms: int,
        confidence_score: float,
        handoff: bool,
        references: Optional[List[Dict[str, Any]]] = None,
        step_trace: Optional[List[Dict[str, Any]]] = None,
        queried_order: Optional[Dict[str, Any]] = None,
        refund_confirmation_pending: Optional[bool] = None,
        pending_refund_order: Optional[Dict[str, Any]] = None,
        refund_order_id: Optional[str] = None,
        refund_request_id: Optional[str] = None,
        clear_pending_refund: bool = False,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """单次读写完成：同步意图/情绪画像 + 人工升级状态 + 挂起退款上下文 + 真实指标 + AI消息落盘"""
        session = self.get_or_create_session(session_id)
        profile = session["customerProfile"]
        profile["intent"] = intent
        profile["sentiment"] = sentiment

        if refund_confirmation_pending and refund_order_id and refund_request_id:
            session["pendingRefund"] = {"orderId": refund_order_id, "requestId": refund_request_id}
        elif clear_pending_refund:
            session["pendingRefund"] = None

        metrics = session["metrics"]
        ai_count = sum(1 for m in session.get("messages", []) if m.get("role") == "assistant")
        if ai_count == 0:
            metrics["avgLatencyMs"] = latency_ms
            metrics["avgConfidence"] = round(confidence_score, 4)
        else:
            metrics["avgLatencyMs"] = int((metrics.get("avgLatencyMs", latency_ms) * ai_count + latency_ms) / (ai_count + 1))
            metrics["avgConfidence"] = round((metrics.get("avgConfidence", confidence_score) * ai_count + confidence_score) / (ai_count + 1), 4)

        if handoff:
            if session.get("status") == "AI_HANDLING":
                session["status"] = "NEEDS_INTERVENTION"
            session["unreadForAgent"] = True
            if not metrics.get("escalatedAt"):
                metrics["escalatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        assistant_msg = self._append_message_in_place(
            session,
            "assistant",
            reply,
            confidence_score=confidence_score,
            references=references,
            step_trace=step_trace,
            queried_order=queried_order,
            refund_confirmation_pending=refund_confirmation_pending,
            pending_refund_order=pending_refund_order,
            refund_order_id=refund_order_id if refund_confirmation_pending else None,
            refund_request_id=refund_request_id if refund_confirmation_pending else None,
        )
        storage_service.save_session(session)
        return assistant_msg, session

    def transfer_session(
        self,
        session_id: str,
        target_agent_id: str,
        reason: str,
        operator_note: str = "",
        trigger_type: str = "user_requested"
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        session = self.get_or_create_session(session_id)
        agents = storage_service.list_agents()
        agent = next((a for a in agents if a["id"] == target_agent_id), agents[0] if agents else {
            "id": "agent_101",
            "name": "陈浩",
            "title": "高级售后督导",
            "department": "XX商城 售后服务部",
            "currentWorkload": 1
        })

        user_questions = [m["content"] for m in session.get("messages", []) if m["role"] == "user"]
        ai_replies = [m["content"] for m in session.get("messages", []) if m["role"] == "assistant"]
        last_ai_reply = ai_replies[-1] if ai_replies else "（AI尚未回复）"

        # 打包完整的交接单上下文快照
        snapshot = {
            "snapshotId": f"TRF-{int(time.time())}-{uuid.uuid4().hex[:4].upper()}",
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "sessionId": session_id,
            "targetAgentId": agent["id"],
            "targetAgentName": agent["name"],
            "reason": reason,
            "operatorNote": operator_note,
            "triggerType": trigger_type,
            "customerProfile": session["customerProfile"],
            "summaryMemory": session["summaryMemory"],
            "userQuestions": user_questions,
            "aiResponses": ai_replies,
            "lastAiResponse": last_ai_reply,
            "dialogueRounds": len(user_questions),
            "suggestedGreeting": f"您好，{session['customerProfile']['name']}！我是售后值班专员{agent['name']}。我已全面调阅您关于【{session['customerProfile']['intent']}】的咨询快照与会员权益，接下来由我为您全权处理！"
        }

        session["status"] = "HUMAN_INTERVENED"
        session["assignedAgent"] = agent["name"]
        session["assignedAgentId"] = agent["id"]
        session["contextSnapshot"] = snapshot

        # 记录审计日志并固化
        transfer_log = {
            "id": snapshot["snapshotId"],
            "sessionId": session_id,
            "customerName": session["customerProfile"]["name"],
            "agentName": agent["name"],
            "agentId": agent["id"],
            "reason": reason,
            "triggerType": trigger_type,
            "operatorNote": operator_note,
            "dialogueRounds": len(user_questions),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        storage_service.add_transfer_log(transfer_log)
        session["latestTransfer"] = transfer_log

        # 增加坐席负载并固化
        storage_service.update_agent_workload(agent["id"], 1)

        cprint.transfer(session_id, f"{agent['name']} ({agent['id']})", reason)

        # 增加系统转接消息并保存
        self.add_message(
            session_id,
            "system",
            f"已为您无缝接入值班坐席【{agent['name']}】（工号: {agent['id']}），完整对话快照与会员权益已成功冻结移交。"
        )

        return transfer_log, session

    def intervene_session(self, session_id: str, action: str, agent_id: str = "agent_101", note: str = "") -> Dict[str, Any]:
        session = self.get_or_create_session(session_id)
        agents = storage_service.list_agents()
        if action in ["takeover", "intervene"]:
            agent = next((a for a in agents if a["id"] == agent_id), agents[0] if agents else {
                "id": "agent_101",
                "name": "陈浩"
            })
            session["status"] = "HUMAN_INTERVENED"
            session["assignedAgent"] = agent["name"]
            session["assignedAgentId"] = agent["id"]
            self.add_message(session_id, "system", f"人工坐席【{agent['name']}】（工号: {agent['id']}）已主动切入接管对话。")
        elif action == "release":
            session["status"] = "AI_HANDLING"
            session["assignedAgent"] = None
            session["assignedAgentId"] = None
            self.add_message(session_id, "system", "人工坐席已将对话交还给 AI 智能客服继续服务。")

        session["updatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        storage_service.save_session(session)
        return session

    def update_session_status(self, session_id: str, new_status: str) -> Dict[str, Any]:
        """更新并持久化会话状态（如 AI_HANDLING -> NEEDS_INTERVENTION）"""
        session = self.get_or_create_session(session_id)
        session["status"] = new_status
        session["updatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return storage_service.save_session(session)

    def list_sessions(self) -> List[Dict[str, Any]]:
        sessions_map = storage_service.list_sessions()
        for s in sessions_map.values():
            if "metrics" not in s or not isinstance(s["metrics"], dict):
                s["metrics"] = {"totalTurns": len(s.get("messages", [])), "avgLatencyMs": 350, "avgConfidence": 0.95, "escalatedAt": None}
            else:
                s["metrics"]["totalTurns"] = len(s.get("messages", []))
            if "customerProfile" not in s or not isinstance(s["customerProfile"], dict):
                s["customerProfile"] = {
                    "name": s.get("userName", "客户"),
                    "vipLevel": "普通会员",
                    "sentiment": "neutral",
                    "urgency": "中",
                    "intent": "常规业务咨询",
                    "tags": ["普通会员"],
                    "orderId": ""
                }
        return list(sessions_map.values())

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.get_or_create_session(session_id)

    def list_agents(self) -> List[Dict[str, Any]]:
        return storage_service.list_agents()

    def list_transfer_logs(self) -> List[Dict[str, Any]]:
        return storage_service.list_transfer_logs()

    def list_customers(self) -> List[Dict[str, Any]]:
        return storage_service.list_customers()

    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        return storage_service.get_customer(customer_id)

    def save_customer(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        return storage_service.save_customer(customer_data)


# 全局单例记忆服务
memory_service = MemoryService()
AVAILABLE_AGENTS = storage_service.list_agents()
