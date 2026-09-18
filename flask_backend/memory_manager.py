"""
会话记忆管理模块 (Session Memory Manager)
支持滑动窗口消息历史、长期记忆生成、完整上下文快照打包与人工转接流水审计
"""

import time
import uuid
from typing import Dict, Any, List, Optional, Tuple

AVAILABLE_AGENTS = [
    {
        "id": "agent_101",
        "name": "陈浩",
        "title": "高级客服主管",
        "department": "售后与客诉仲裁组",
        "status": "IDLE",
        "currentWorkload": 1,
        "rating": 4.98,
        "specialties": ["极速退款", "争议仲裁", "钻石VIP专席", "物流丢件先行赔付"],
        "recommendedFor": ["售后退换货政策", "疑难客诉争议"]
    },
    {
        "id": "agent_102",
        "name": "林婉儿",
        "title": "财务高级专员",
        "department": "发票与结算中心",
        "status": "IDLE",
        "currentWorkload": 2,
        "rating": 4.95,
        "specialties": ["增值税专票开具", "对公账单核对", "跨期发票重开", "退税指引"],
        "recommendedFor": ["账单与发票申请"]
    },
    {
        "id": "agent_103",
        "name": "周建国",
        "title": "物流调度督导",
        "department": "全国物流保障中心",
        "status": "BUSY",
        "currentWorkload": 4,
        "rating": 4.91,
        "specialties": ["顺丰加急拦截", "生鲜冷链破损", "偏远地区专配", "时效延误赔付"],
        "recommendedFor": ["物流时效与发货"]
    },
    {
        "id": "agent_104",
        "name": "苏晓晓",
        "title": "VIP客户经理",
        "department": "高净值会员服务部",
        "status": "IDLE",
        "currentWorkload": 0,
        "rating": 5.00,
        "specialties": ["大宗团购采购", "白金钻石特权", "定制礼遇", "一对一顾问"],
        "recommendedFor": ["会员权益与特权"]
    }
]

class PythonMemoryManager:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.transfer_logs: List[Dict[str, Any]] = []
        self._init_demo_sessions()

    def _init_demo_sessions(self):
        """预置演示会话"""
        self.sessions["session_user_001"] = {
            "id": "session_user_001",
            "userName": "王女士",
            "status": "AI_HANDLING",
            "assignedAgent": None,
            "assignedAgentId": None,
            "customerProfile": {
                "name": "王女士",
                "phone": "138****6699",
                "vipLevel": "钻石VIP",
                "sentiment": "frustrated",
                "urgency": "高",
                "intent": "售后加急退款与物流破损争议",
                "tags": ["高客单价", "顺丰包邮", "钻石VIP", "急躁/投诉倾向"],
                "orderId": "ORD-2026-88992"
            },
            "summaryMemory": "客户反映购买的定制高奢瓷器（订单 ORD-2026-88992）签收时发现包装微损且顺丰延迟派送。作为钻石VIP，希望尽快免检退货退款，并要求值班主管加急原路退回。",
            "messages": [
                {
                    "id": "m1",
                    "role": "user",
                    "content": "我昨天买的瓷器包裹到了，但是顺丰纸箱角有点瘪，我着急出差，能退货吗？",
                    "timestamp": "10:14:20"
                },
                {
                    "id": "m2",
                    "role": "assistant",
                    "content": "王女士您好！非常理解您的急切心情。您作为平台钻石VIP，享有签收7日内免检极速退换特权。请问内物瓷器是否有破损？若需退货，可直接安排顺丰专人上门取件。",
                    "confidenceScore": 0.94,
                    "timestamp": "10:14:24"
                },
                {
                    "id": "m3",
                    "role": "user",
                    "content": "顺丰取件太慢了，我现在就要退款到账，你们这处理效率太差了吧，再不解决我就找消协！",
                    "timestamp": "10:15:02"
                }
            ],
            "checkpoints": [],
            "metrics": {
                "totalTurns": 3,
                "avgLatencyMs": 320,
                "avgConfidence": 0.92
            },
            "createdAt": "10:14:00",
            "updatedAt": "10:15:02"
        }

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        return list(self.sessions.values())

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.sessions.get(session_id)

    def get_or_create_session(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "id": session_id,
                "userName": "新访客",
                "status": "AI_HANDLING",
                "customerProfile": {
                    "name": "新访客",
                    "vipLevel": "普通会员",
                    "sentiment": "neutral",
                    "urgency": "中",
                    "intent": "常规业务咨询",
                    "tags": ["新访客"]
                },
                "summaryMemory": "新建立会话，正在通过 LangGraph 实时积累记忆。",
                "messages": [],
                "checkpoints": [],
                "metrics": {"totalTurns": 0, "avgLatencyMs": 280, "avgConfidence": 0.9},
                "createdAt": time.strftime("%H:%M:%S"),
                "updatedAt": time.strftime("%H:%M:%S")
            }
        return self.sessions[session_id]

    def add_message(self, session_id: str, role: str, content: str, **kwargs) -> Dict[str, Any]:
        session = self.get_or_create_session(session_id)
        msg = {
            "id": f"msg_{uuid.uuid4().hex[:8]}",
            "role": role,
            "content": content,
            "timestamp": time.strftime("%H:%M:%S"),
            **kwargs
        }
        session["messages"].append(msg)
        session["metrics"]["totalTurns"] += 1
        session["updatedAt"] = msg["timestamp"]

        # 更新意图与情绪
        if role == "user":
            if any(w in content for w in ["差评", "太慢", "生气", "消协", "骗子", "投诉"]):
                session["customerProfile"]["sentiment"] = "frustrated"
                session["customerProfile"]["urgency"] = "紧急"
            elif any(w in content for w in ["谢谢", "感谢", "点赞"]):
                session["customerProfile"]["sentiment"] = "positive"
                
        return session

    def update_status(self, session_id: str, status: str, reason: str = ""):
        session = self.get_session(session_id)
        if session:
            session["status"] = status
            if status == "NEEDS_INTERVENTION":
                session["metrics"]["escalatedAt"] = time.strftime("%H:%M:%S")

    def record_checkpoint(self, session_id: str, node: str, state_data: Dict[str, Any]):
        session = self.get_session(session_id)
        if session:
            session["checkpoints"].append({
                "id": f"cp_{uuid.uuid4().hex[:6]}",
                "timestamp": time.strftime("%H:%M:%S"),
                "node": node,
                "stateData": state_data
            })
            if len(session["checkpoints"]) > 8:
                session["checkpoints"] = session["checkpoints"][-8:]

    def get_available_agents(self) -> List[Dict[str, Any]]:
        return AVAILABLE_AGENTS

    def get_transfer_logs(self) -> List[Dict[str, Any]]:
        return self.transfer_logs

    def transfer_session(
        self,
        session_id: str,
        target_agent_id: str,
        reason: str,
        operator_note: str = "",
        trigger_type: str = "user_requested"
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """打包完整上下文交接单并更新会话状态"""
        session = self.get_session(session_id)
        if not session:
            return None, None

        agent = next((a for a in AVAILABLE_AGENTS if a["id"] == target_agent_id), AVAILABLE_AGENTS[0])

        # 提取用户所有提问与客服所有答复
        user_questions = [m["content"] for m in session["messages"] if m["role"] == "user"]
        ai_answers = [m["content"] for m in session["messages"] if m["role"] in ["assistant", "system"]]
        last_user_q = user_questions[-1] if user_questions else ""
        last_ai_ans = ai_answers[-1] if ai_answers else ""

        # 打包完整上下文快照 (TransferContextSnapshot)
        context_snapshot = {
            "sessionId": session_id,
            "customerName": session["userName"],
            "vipLevel": session["customerProfile"].get("vipLevel", "普通会员"),
            "userMessagesCount": len(user_questions),
            "aiMessagesCount": len(ai_answers),
            "totalTurns": session["metrics"]["totalTurns"],
            "userQuestions": user_questions,
            "lastUserQuestion": last_user_q,
            "lastAiResponse": last_ai_ans,
            "summaryMemory": session.get("summaryMemory", ""),
            "sentiment": session["customerProfile"].get("sentiment", "neutral"),
            "intent": session["customerProfile"].get("intent", "常规业务咨询"),
            "urgency": session["customerProfile"].get("urgency", "高"),
            "orderId": session["customerProfile"].get("orderId"),
            "fullConversationSnapshot": [
                {
                    "id": m["id"],
                    "role": m["role"],
                    "content": m["content"],
                    "timestamp": m["timestamp"]
                }
                for m in session["messages"]
            ]
        }

        transfer_log = {
            "id": f"TRF-{int(time.time()*1000)}",
            "sessionId": session_id,
            "triggerType": trigger_type,
            "reason": reason,
            "assignedAgentId": agent["id"],
            "assignedAgentName": agent["name"],
            "assignedDepartment": agent["department"],
            "customerName": session["userName"],
            "vipLevel": session["customerProfile"].get("vipLevel", "普通会员"),
            "status": "SUCCESS",
            "transferredAt": time.strftime("%H:%M:%S"),
            "contextSnapshot": context_snapshot,
            "operatorNote": operator_note
        }

        self.transfer_logs.insert(0, transfer_log)

        # 更新会话状态为人工服务中
        session["status"] = "HUMAN_INTERVENED"
        session["assignedAgent"] = f"{agent['name']} ({agent['department']})"
        session["assignedAgentId"] = agent["id"]
        session["latestTransfer"] = transfer_log

        # 插入系统级无缝转接提示
        notice = f"【系统已无缝转接】会话及完整历史记录已移交人工客服：{agent['name']}（{agent['department']}）。"
        if operator_note:
            notice += f" 附言：{operator_note}"
        self.add_message(session_id, "system", notice)

        return transfer_log, session

    def handle_intervention(self, session_id: str, action: str, agent_name: str) -> Optional[Dict[str, Any]]:
        session = self.get_session(session_id)
        if not session:
            return None

        if action == "takeover":
            session["status"] = "HUMAN_INTERVENED"
            session["assignedAgent"] = agent_name
            self.add_message(session_id, "system", f"【人工客服介入】客服坐席 {agent_name} 已接管本会话。")
        else:
            session["status"] = "AI_HANDLING"
            session["assignedAgent"] = None
            self.add_message(session_id, "system", "【会话已转回】人工服务已结束，已无缝切换回智能客服继续为您服务。")

        return session

    def get_metrics(self) -> Dict[str, Any]:
        total = len(self.sessions)
        needs = sum(1 for s in self.sessions.values() if s["status"] == "NEEDS_INTERVENTION")
        human = sum(1 for s in self.sessions.values() if s["status"] == "HUMAN_INTERVENED")
        ai = sum(1 for s in self.sessions.values() if s["status"] == "AI_HANDLING")

        return {
            "totalSessions": total,
            "needsIntervention": needs,
            "humanIntervened": human,
            "aiHandling": ai,
            "totalTurns": sum(s["metrics"]["totalTurns"] for s in self.sessions.values()),
            "avgLatencyMs": 330,
            "avgConfidence": 0.92,
            "kbDocCount": 5,
            "transferLogsCount": len(self.transfer_logs),
            "sentimentCounts": {
                "positive": sum(1 for s in self.sessions.values() if s["customerProfile"]["sentiment"] == "positive"),
                "neutral": sum(1 for s in self.sessions.values() if s["customerProfile"]["sentiment"] == "neutral"),
                "frustrated": sum(1 for s in self.sessions.values() if s["customerProfile"]["sentiment"] == "frustrated"),
                "negative": 0
            }
        }
