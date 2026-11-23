"""
会话记忆管理服务 (Session Memory & Human Transfer Service)
维持多轮会话状态、滑动窗口长期摘要、客户画像、人工接管与转接上下文快照
通过 storage_service 统一持久化至 PostgreSQL 关系型数据库。
"""

import time
import uuid
import datetime
from typing import Dict, Any, List, Optional, Tuple
from core.logger import cprint
from config import (
    DETERMINISTIC_FLOW_CONFIDENCE,
    HUMAN_TAKEOVER_STATUSES,
    SUMMARY_USER_SNIPPET_LEN,
    SUMMARY_REPLY_SNIPPET_LEN,
    SUMMARY_MAX_SEGMENTS,
    SUMMARY_MAX_CHARS,
)
from services.storage_service import storage_service


def _now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _default_metrics(total_turns: int = 0) -> Dict[str, Any]:
    return {
        "totalTurns": total_turns,
        "avgLatencyMs": 350,
        "avgConfidence": DETERMINISTIC_FLOW_CONFIDENCE,
        "escalatedAt": None,
    }


def _default_customer_profile(user_name: str = "客户") -> Dict[str, Any]:
    return {
        "name": user_name,
        "vipLevel": "普通会员",
        "sentiment": "neutral",
        "urgency": "中",
        "intent": "常规业务咨询",
        "tags": ["普通会员"],
        "orderId": "",
    }


def _resolve_agent(agent_id: str) -> Dict[str, Any]:
    """按工号查找目标坐席，未命中时回退首位可用坐席或默认督导"""
    agents = storage_service.list_agents()
    return next(
        (a for a in agents if a["id"] == agent_id),
        agents[0]
        if agents
        else {
            "id": "agent_101",
            "name": "陈浩",
            "title": "高级售后督导",
            "department": "XX商城 售后服务部",
            "currentWorkload": 1,
        },
    )


class MemoryService:
    def _ensure_session_defaults(
        self,
        session: Dict[str, Any],
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """补齐缺损字段并将新传入的 userProfile 增量合并进会话画像，返回是否发生变更"""
        changed = False
        messages = session.get("messages")
        if not isinstance(messages, list):
            session["messages"] = []
            messages = session["messages"]
            changed = True

        if not isinstance(session.get("metrics"), dict):
            session["metrics"] = _default_metrics(len(messages))
            changed = True

        if not isinstance(session.get("customerProfile"), dict):
            session["customerProfile"] = _default_customer_profile(session.get("userName", "客户"))
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

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """只读查询会话详情（不存在时返回 None，避免 GET 详情接口产生脏会话记录）"""
        session = storage_service.get_session(session_id)
        if not session:
            return None
        self._ensure_session_defaults(session)
        return session

    def get_or_create_session(
        self,
        session_id: str,
        user_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        session = storage_service.get_session(session_id)
        if session:
            if self._ensure_session_defaults(session, user_profile):
                session["updatedAt"] = _now_str()
                storage_service.save_session(session)
            return session

        up = user_profile or {}
        name = up.get("name") or up.get("userName") or "客户"
        vip = up.get("vipLevel") or up.get("tier") or "普通会员"
        now_str = _now_str()

        profile = _default_customer_profile(name)
        profile.update({
            "phone": up.get("phone", ""),
            "vipLevel": vip,
            "sentiment": up.get("sentiment", "neutral"),
            "urgency": up.get("urgency", "中"),
            "intent": up.get("intent", "售后咨询"),
            "tags": up.get("tags", [vip]),
            "orderId": up.get("orderId", f"ORD-2026-{uuid.uuid4().hex[:6].upper()}"),
        })
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
            "metrics": _default_metrics(0),
            "contextSnapshot": None,
            "latestTransfer": None,
            "unreadForAgent": False,
            "createdAt": now_str,
            "updatedAt": now_str,
        }
        storage_service.save_session(new_session)
        return new_session

    @staticmethod
    def _update_summary_memory(current_summary: str, role: str, content: str) -> str:
        """
        按完整语义片段维护去重后的滑动窗口摘要：
        - 过滤旧版字符硬截断留下的开头残片
        - 对相邻同角色重复发言合并计数 (×N)，避免重试刷爆上下文
        - 按完整片段与最大字符上限从头部淘汰，不截断半句话
        """
        text = " ".join((content or "").split())
        if not text:
            return current_summary

        if role == "user":
            snippet = f"{text[:SUMMARY_USER_SNIPPET_LEN]}..." if len(text) > SUMMARY_USER_SNIPPET_LEN else text
            entry = f"客户提问：'{snippet}'"
        elif role in ("assistant", "human_agent"):
            prefix = "AI答复" if role == "assistant" else "人工坐席答复"
            snippet = f"{text[:SUMMARY_REPLY_SNIPPET_LEN]}..." if len(text) > SUMMARY_REPLY_SNIPPET_LEN else text
            entry = f"{prefix}：'{snippet}'"
        else:
            return current_summary

        valid_prefixes = ("客户提问：", "AI答复：", "人工坐席答复：")
        segments = []
        for raw_seg in (current_summary or "").split("；"):
            seg = raw_seg.strip()
            if not seg:
                continue
            if not segments and "建立咨询连接" not in seg and not seg.startswith(valid_prefixes):
                continue
            segments.append(seg)

        def _split_repeat(seg: str) -> Tuple[str, int]:
            idx = seg.rfind(" (×")
            if idx != -1 and seg.endswith(")"):
                num_str = seg[idx + 3:-1]
                if num_str.isdigit():
                    return seg[:idx], int(num_str)
            return seg, 1

        # 倒序查找最近一条同角色片段，若内容一致则原地合并计数 (×N)
        merged = False
        entry_prefix = entry.split("：", 1)[0] + "："
        for check_idx in range(len(segments) - 1, -1, -1):
            seg = segments[check_idx]
            if not seg.startswith(entry_prefix):
                continue
            base_seg, count = _split_repeat(seg)
            if base_seg == entry:
                segments[check_idx] = f"{entry} (×{count + 1})"
                merged = True
            break

        if not merged:
            segments.append(entry)

        if len(segments) > SUMMARY_MAX_SEGMENTS:
            segments = segments[-SUMMARY_MAX_SEGMENTS:]
        while len(segments) > 1 and len("；".join(segments) + "；") > SUMMARY_MAX_CHARS:
            segments.pop(0)

        return "；".join(segments) + "；"

    def _append_message_in_place(
        self,
        session: Dict[str, Any],
        role: str,
        content: str,
        *,
        sender_name: Optional[str] = None,
        ai_meta: Optional[Dict[str, Any]] = None,
        card: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """在已加载的 session 对象上原地追加统一结构的消息并更新摘要与指标（不单独落盘）"""
        self._ensure_session_defaults(session)
        msg_id = f"m_{int(time.time() * 1000)}_{len(session['messages'])}"
        msg: Dict[str, Any] = {
            "id": msg_id,
            "role": role,
            "content": content,
            "timestamp": time.strftime("%H:%M:%S"),
        }
        if sender_name:
            msg["senderName"] = sender_name
        if ai_meta:
            msg["aiMeta"] = ai_meta
        if card:
            msg["card"] = card

        session["messages"].append(msg)
        session["metrics"]["totalTurns"] = len(session["messages"])
        session["summaryMemory"] = self._update_summary_memory(session.get("summaryMemory", ""), role, content)
        session["updatedAt"] = _now_str()
        return msg

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        sender_name: Optional[str] = None,
        ai_meta: Optional[Dict[str, Any]] = None,
        card: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        session = self.get_or_create_session(session_id)
        msg = self._append_message_in_place(
            session,
            role,
            content,
            sender_name=sender_name,
            ai_meta=ai_meta,
            card=card,
        )
        storage_service.save_session(session)
        return msg

    def record_user_turn(
        self,
        session_id: str,
        content: str,
        user_profile: Optional[Dict[str, Any]] = None,
        human_takeover_statuses: Tuple[str, ...] = HUMAN_TAKEOVER_STATUSES,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """单次读写完成：获取/创建会话 + 合并最新画像 + 写入用户消息 + 人工模式未读标记 + 落盘"""
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
        refund_order_id: Optional[str] = None,
        out_refund_no: Optional[str] = None,
        clear_pending_refund: bool = False,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """单次读写完成：同步意图/情绪画像 + 人工升级状态 + 挂起退款上下文 + 真实指标 + 统一结构 AI 消息落盘"""
        session = self.get_or_create_session(session_id)
        profile = session["customerProfile"]
        profile["intent"] = intent
        profile["sentiment"] = sentiment

        if refund_confirmation_pending and refund_order_id and out_refund_no:
            session["pendingRefund"] = {"orderId": refund_order_id, "outRefundNo": out_refund_no}
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
                metrics["escalatedAt"] = _now_str()

        ai_meta: Dict[str, Any] = {
            "confidenceScore": confidence_score,
        }
        if references is not None:
            ai_meta["references"] = references
        if step_trace is not None:
            ai_meta["stepTrace"] = step_trace

        card: Optional[Dict[str, Any]] = None
        if refund_confirmation_pending and refund_order_id and out_refund_no:
            card = {
                "type": "refund_confirm",
                "orderId": refund_order_id,
                "outRefundNo": out_refund_no,
            }
            if queried_order and queried_order.get("paidAmount") is not None:
                card["paidAmount"] = round(float(queried_order["paidAmount"]), 2)
        elif queried_order:
            card = {
                "type": "order",
                "order": queried_order,
            }

        assistant_msg = self._append_message_in_place(
            session,
            "assistant",
            reply,
            ai_meta=ai_meta,
            card=card,
        )
        storage_service.save_session(session)
        return assistant_msg, session

    @staticmethod
    def build_session_patch(
        session: Dict[str, Any],
        *,
        include_context: bool = True,
    ) -> Dict[str, Any]:
        """提取轻量增量会话状态补丁（仅含实时对话同步所需字段）"""
        patch: Dict[str, Any] = {
            "status": session.get("status"),
            "assignedAgent": session.get("assignedAgent"),
            "assignedAgentId": session.get("assignedAgentId"),
        }
        if include_context:
            profile = session.get("customerProfile") or {}
            patch["intent"] = profile.get("intent")
            patch["sentiment"] = profile.get("sentiment")
            patch["summaryMemory"] = session.get("summaryMemory", "")
        return patch

    def transfer_session(
        self,
        session_id: str,
        target_agent_id: str,
        reason: str,
        operator_note: str = "",
        trigger_type: str = "user_requested",
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        session = self.get_or_create_session(session_id)
        agent = _resolve_agent(target_agent_id)
        profile = session["customerProfile"]

        user_questions = [m["content"] for m in session.get("messages", []) if m["role"] == "user"]
        ai_replies = [m["content"] for m in session.get("messages", []) if m["role"] == "assistant"]
        last_ai_reply = ai_replies[-1] if ai_replies else "（AI尚未回复）"

        snapshot = {
            "snapshotId": f"TRF-{int(time.time())}-{uuid.uuid4().hex[:4].upper()}",
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "sessionId": session_id,
            "targetAgentId": agent["id"],
            "targetAgentName": agent["name"],
            "reason": reason,
            "operatorNote": operator_note,
            "triggerType": trigger_type,
            "customerProfile": profile,
            "summaryMemory": session.get("summaryMemory", ""),
            "userQuestions": user_questions,
            "aiResponses": ai_replies,
            "lastAiResponse": last_ai_reply,
            "dialogueRounds": len(user_questions),
            "suggestedGreeting": (
                f"您好，{profile.get('name', '客户')}！我是售后值班专员{agent['name']}。"
                f"我已全面调阅您关于【{profile.get('intent', '售后咨询')}】的咨询快照与会员权益，接下来由我为您全权处理！"
            ),
        }

        # 对齐 TransferLogEntity / 前端期望字段，并获取持久化后的标准工单对象
        transfer_log = storage_service.add_transfer_log({
            "id": snapshot["snapshotId"],
            "sessionId": session_id,
            "customerName": profile.get("name", session.get("userName", "客户")),
            "vipLevel": profile.get("vipLevel", "普通会员"),
            "reason": reason,
            "triggerType": trigger_type,
            "assignedAgentId": agent["id"],
            "assignedAgentName": agent["name"],
            "assignedDepartment": agent.get("department", "XX商城 客户服务中心"),
            "status": "SUCCESS",
            "transferredAt": _now_str(),
            "operatorNote": operator_note,
            "dialogueRounds": len(user_questions),
            "contextSnapshot": snapshot,
        })

        previous_agent_id = session.get("assignedAgentId")
        if previous_agent_id and previous_agent_id != agent["id"]:
            storage_service.update_agent_workload(previous_agent_id, -1)
        if previous_agent_id != agent["id"]:
            storage_service.update_agent_workload(agent["id"], 1)

        session["status"] = "HUMAN_INTERVENED"
        session["assignedAgent"] = agent["name"]
        session["assignedAgentId"] = agent["id"]
        session["contextSnapshot"] = snapshot
        session["latestTransfer"] = transfer_log
        session["unreadForAgent"] = False

        cprint.transfer(session_id, f"{agent['name']} ({agent['id']})", reason)

        # 原地追加系统通知后再单次落盘，避免二次读取覆盖 status 与 contextSnapshot
        self._append_message_in_place(
            session,
            "system",
            f"已为您无缝接入值班坐席【{agent['name']}】（工号: {agent['id']}），完整对话快照与会员权益已成功冻结移交。",
        )
        saved_session = storage_service.save_session(session)
        return transfer_log, saved_session

    def intervene_session(
        self,
        session_id: str,
        action: str,
        agent_id: str = "agent_101",
        note: str = "",
    ) -> Dict[str, Any]:
        session = self.get_or_create_session(session_id)
        note_suffix = f"（备注：{note.strip()}）" if note and note.strip() else ""

        if action in ("takeover", "intervene"):
            agent = _resolve_agent(agent_id)
            previous_agent_id = session.get("assignedAgentId")
            if previous_agent_id and previous_agent_id != agent["id"]:
                storage_service.update_agent_workload(previous_agent_id, -1)
            if previous_agent_id != agent["id"]:
                storage_service.update_agent_workload(agent["id"], 1)

            session["status"] = "HUMAN_INTERVENED"
            session["assignedAgent"] = agent["name"]
            session["assignedAgentId"] = agent["id"]
            session["unreadForAgent"] = False
            self._append_message_in_place(
                session,
                "system",
                f"人工坐席【{agent['name']}】（工号: {agent['id']}）已主动切入接管对话{note_suffix}。",
            )
        elif action == "release":
            previous_agent_id = session.get("assignedAgentId")
            if previous_agent_id:
                storage_service.update_agent_workload(previous_agent_id, -1)
            session["status"] = "AI_HANDLING"
            session["assignedAgent"] = None
            session["assignedAgentId"] = None
            session["unreadForAgent"] = False
            self._append_message_in_place(
                session,
                "system",
                f"人工坐席已将对话交还给 AI 智能客服继续服务{note_suffix}。",
            )

        return storage_service.save_session(session)

    def update_session_status(self, session_id: str, new_status: str) -> Dict[str, Any]:
        """更新并持久化会话状态（如 AI_HANDLING -> NEEDS_INTERVENTION）"""
        session = self.get_or_create_session(session_id)
        session["status"] = new_status
        session["updatedAt"] = _now_str()
        return storage_service.save_session(session)

    def clear_session_messages(self, session_id: str) -> Optional[Dict[str, Any]]:
        """清空指定会话的消息历史并持久化"""
        session = self.get_session(session_id)
        if not session:
            return None
        session["messages"] = []
        session["metrics"]["totalTurns"] = 0
        session["pendingRefund"] = None
        session["updatedAt"] = _now_str()
        return storage_service.save_session(session)

    def list_sessions(self) -> List[Dict[str, Any]]:
        sessions_map = storage_service.list_sessions()
        for s in sessions_map.values():
            self._ensure_session_defaults(s)
            s["metrics"]["totalTurns"] = len(s["messages"])
        return list(sessions_map.values())


# 全局单例记忆服务
memory_service = MemoryService()
