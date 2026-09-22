"""
会话记忆管理服务 (Session Memory & Human Transfer Service)
维持多轮会话状态、长期记忆、客户画像、转接上下文快照打包与审计日志
"""

import time
import uuid
from typing import Dict, Any, List, Optional, Tuple

AVAILABLE_AGENTS = [
    {
        "id": "agent_101",
        "name": "陈浩",
        "title": "高级售后督导",
        "department": "XX商城 售后服务与仲裁部",
        "status": "IDLE",
        "currentWorkload": 1,
        "rating": 4.98,
        "specialties": ["7天无理由退货", "黄金会员运费补贴", "破损质量先行赔付", "退款异常加急"],
        "recommendedFor": ["7天无理由退货政策", "特殊不可退换商品范围"]
    },
    {
        "id": "agent_102",
        "name": "林婉儿",
        "title": "资深退款财务专员",
        "department": "财务核算与退款中心",
        "status": "IDLE",
        "currentWorkload": 2,
        "rating": 4.96,
        "specialties": ["48小时质检入库", "银行卡到账跟踪", "原路退回冲正", "信用卡退费流水"],
        "recommendedFor": ["退款质检与到账时效"]
    },
    {
        "id": "agent_103",
        "name": "周建国",
        "title": "硬件技术工程师",
        "department": "全国联保与检测中心",
        "status": "BUSY",
        "currentWorkload": 3,
        "rating": 4.92,
        "specialties": ["1年全国联保", "15天免费换新机", "非人为硬件故障鉴定", "配件成本费核算"],
        "recommendedFor": ["1年联保与硬件保修条款"]
    },
    {
        "id": "agent_104",
        "name": "苏晓晓",
        "title": "大客户会员顾问",
        "department": "高净值会员服务部",
        "status": "IDLE",
        "currentWorkload": 0,
        "rating": 5.00,
        "specialties": ["黄金会员免运费权益", "钻石VIP快速通道", "专属1对1客服", "大件物流上门"],
        "recommendedFor": ["退换货运费承担与会员权益"]
    }
]

class MemoryService:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.transfer_logs: List[Dict[str, Any]] = []
        self._init_demo_sessions()

    def _init_demo_sessions(self):
        """预置符合 XX商城 2026 售后新规的演示会话"""
        self.sessions["session_user_001"] = {
            "id": "session_user_001",
            "userName": "王女士",
            "status": "AI_HANDLING",
            "assignedAgent": None,
            "assignedAgentId": None,
            "customerProfile": {
                "name": "王女士",
                "phone": "138****6699",
                "vipLevel": "黄金会员",
                "sentiment": "frustrated",
                "urgency": "高",
                "intent": "7天无理由退货运费与到账时间",
                "tags": ["黄金会员", "免运费特权", "急躁", "签收第3天"],
                "orderId": "ORD-2026-88992"
            },
            "summaryMemory": "客户王女士（黄金会员，订单 ORD-2026-88992）签收扫地机器人3天，因尺寸不合适想申请7天无理由退货，咨询退货运费是否需要自己出以及退款多久到账。系统已确认黄金会员享免运费补贴。",
            "messages": [
                {
                    "id": "m1",
                    "role": "user",
                    "content": "我3天前买的扫地机器人，包装完好没拆过封，想退货的话运费谁承担？",
                    "timestamp": "10:14:20"
                },
                {
                    "id": "m2",
                    "role": "assistant",
                    "content": "王女士您好！根据XX商城政策：签收7天内商品完好支持7天无理由退换。虽然个人原因退换通常由买家承担运费，但检测到您是【黄金会员】，享有平台全额补贴的『退货免运费』专属权益，您无需承担任何寄回运费！",
                    "confidenceScore": 0.96,
                    "timestamp": "10:14:24"
                },
                {
                    "id": "m3",
                    "role": "user",
                    "content": "那我退回去之后，钱大概几天能退回我的支付宝？",
                    "timestamp": "10:15:02"
                }
            ],
            "contextSnapshot": None
        }

        self.sessions["session_user_002"] = {
            "id": "session_user_002",
            "userName": "李先生",
            "status": "AI_HANDLING",
            "assignedAgent": None,
            "assignedAgentId": None,
            "customerProfile": {
                "name": "李先生",
                "phone": "139****1122",
                "vipLevel": "普通会员",
                "sentiment": "neutral",
                "urgency": "中",
                "intent": "特殊商品退换咨询",
                "tags": ["定制工艺品", "普通会员"],
                "orderId": "ORD-2026-77312"
            },
            "summaryMemory": "李先生咨询刻字银杯能否申请7天无理由退款，已告知个人定制类商品非质量问题不予退换。",
            "messages": [
                {
                    "id": "m201",
                    "role": "user",
                    "content": "我定制刻字的银杯送朋友没送成，能七天无理由退吗？",
                    "timestamp": "09:30:11"
                }
            ],
            "contextSnapshot": None
        }

    def get_or_create_session(self, session_id: str, user_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if session_id not in self.sessions:
            name = (user_profile or {}).get("name", "客户")
            vip = (user_profile or {}).get("vipLevel", "普通会员")
            self.sessions[session_id] = {
                "id": session_id,
                "userName": name,
                "status": "AI_HANDLING",
                "assignedAgent": None,
                "assignedAgentId": None,
                "customerProfile": {
                    "name": name,
                    "vipLevel": vip,
                    "sentiment": "neutral",
                    "urgency": "中",
                    "intent": "售后咨询",
                    "tags": [vip],
                    "orderId": (user_profile or {}).get("orderId", f"ORD-2026-{uuid.uuid4().hex[:6].upper()}")
                },
                "summaryMemory": f"{name}（{vip}）于今日建立咨询连接。",
                "messages": [],
                "contextSnapshot": None
            }
        return self.sessions[session_id]

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        confidence_score: Optional[float] = None,
        references: Optional[List[Dict[str, Any]]] = None,
        step_trace: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        session = self.get_or_create_session(session_id)
        msg_id = f"m_{int(time.time() * 1000)}_{len(session['messages'])}"
        now_str = time.strftime("%H:%M:%S")

        msg = {
            "id": msg_id,
            "role": role,
            "content": content,
            "timestamp": now_str
        }
        if confidence_score is not None:
            msg["confidenceScore"] = confidence_score
        if references:
            msg["references"] = references
        if step_trace:
            msg["stepTrace"] = step_trace

        session["messages"].append(msg)

        # 简单增量更新长期摘要
        if role == "user":
            session["summaryMemory"] += f" 客户提问：'{content}'；"
        elif role == "assistant":
            session["summaryMemory"] += f" AI答复：'{content[:60]}...'；"

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
        agent = next((a for a in AVAILABLE_AGENTS if a["id"] == target_agent_id), AVAILABLE_AGENTS[0])

        user_questions = [m["content"] for m in session["messages"] if m["role"] == "user"]
        ai_replies = [m["content"] for m in session["messages"] if m["role"] == "assistant"]
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

        # 记录审计日志
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
        self.transfer_logs.insert(0, transfer_log)

        # 增加坐席负载
        agent["currentWorkload"] += 1

        # 增加系统转接消息
        self.add_message(
            session_id,
            "system",
            f"已为您无缝接入值班坐席【{agent['name']}】（工号: {agent['id']}），完整对话快照与会员权益已成功冻结移交。"
        )

        return transfer_log, session

    def intervene_session(self, session_id: str, action: str, agent_id: str = "agent_101", note: str = "") -> Dict[str, Any]:
        session = self.get_or_create_session(session_id)
        if action == "takeover":
            agent = next((a for a in AVAILABLE_AGENTS if a["id"] == agent_id), AVAILABLE_AGENTS[0])
            session["status"] = "HUMAN_INTERVENED"
            session["assignedAgent"] = agent["name"]
            session["assignedAgentId"] = agent["id"]
            self.add_message(session_id, "system", f"人工坐席【{agent['name']}】已主动切入接管对话。")
        elif action == "release":
            session["status"] = "AI_HANDLING"
            self.add_message(session_id, "system", "人工坐席已将对话交还给 AI 智能客服继续服务。")
        return session

    def list_sessions(self) -> List[Dict[str, Any]]:
        return list(self.sessions.values())

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.sessions.get(session_id)

    def list_agents(self) -> List[Dict[str, Any]]:
        return AVAILABLE_AGENTS

    def list_transfer_logs(self) -> List[Dict[str, Any]]:
        return self.transfer_logs

# 全局单例记忆服务
memory_service = MemoryService()
