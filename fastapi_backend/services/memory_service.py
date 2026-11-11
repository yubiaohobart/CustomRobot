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

    def get_or_create_session(self, session_id: str, user_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        session = storage_service.get_session(session_id)
        if session:
            # 补齐缺损字段兼容旧数据
            if "metrics" not in session or not isinstance(session["metrics"], dict):
                session["metrics"] = {"totalTurns": len(session.get("messages", [])), "avgLatencyMs": 350, "avgConfidence": 0.95, "escalatedAt": None}
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
            return session

        # 不存在则创建并立即固化到磁盘
        name = (user_profile or {}).get("name", "客户")
        vip = (user_profile or {}).get("vipLevel", "普通会员")
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        new_session = {
            "id": session_id,
            "userName": name,
            "status": "AI_HANDLING",
            "assignedAgent": None,
            "assignedAgentId": None,
            "customerProfile": {
                "name": name,
                "phone": (user_profile or {}).get("phone", ""),
                "vipLevel": vip,
                "sentiment": (user_profile or {}).get("sentiment", "neutral"),
                "urgency": (user_profile or {}).get("urgency", "中"),
                "intent": (user_profile or {}).get("intent", "售后咨询"),
                "tags": (user_profile or {}).get("tags", [vip]),
                "orderId": (user_profile or {}).get("orderId", f"ORD-2026-{uuid.uuid4().hex[:6].upper()}")
            },
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

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        confidence_score: Optional[float] = None,
        references: Optional[List[Dict[str, Any]]] = None,
        step_trace: Optional[List[Dict[str, Any]]] = None,
        queried_order: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        session = self.get_or_create_session(session_id)
        msg_id = f"m_{int(time.time() * 1000)}_{len(session.get('messages', []))}"
        now_time = time.strftime("%H:%M:%S")

        msg = {
            "id": msg_id,
            "role": role,
            "content": content,
            "timestamp": now_time
        }
        if confidence_score is not None:
            msg["confidenceScore"] = confidence_score
        if references:
            msg["references"] = references
        if step_trace:
            msg["stepTrace"] = step_trace
        if queried_order:
            msg["queriedOrder"] = queried_order

        session.setdefault("messages", []).append(msg)
        if "metrics" not in session or not isinstance(session["metrics"], dict):
            session["metrics"] = {"totalTurns": len(session["messages"]), "avgLatencyMs": 350, "avgConfidence": 0.95, "escalatedAt": None}
        else:
            session["metrics"]["totalTurns"] = len(session["messages"])

        # 增量更新摘要
        summary = session.get("summaryMemory", "")
        if role == "user":
            session["summaryMemory"] = (summary + f" 客户提问：'{content}'；")[-1000:]
        elif role in ("assistant", "human_agent"):
            prefix = "AI答复" if role == "assistant" else "人工坐席答复"
            session["summaryMemory"] = (summary + f" {prefix}：'{content[:60]}...'；")[-1000:]

        session["updatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 立即固化存储至磁盘 sessions.json
        storage_service.save_session(session)
        return msg

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
