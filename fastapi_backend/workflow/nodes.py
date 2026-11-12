"""
LangGraph 状态图执行节点实现 (Workflow Nodes - 工业级加固优化版)
修复与优化清单：
1. [P0-1] 接住 interrupt 返回值，支持原生 LangGraph resume 交互唤醒，彻底根治死循环
2. [P0-2] 严格只认 intent == "退款申请与审批"，彻底移除模糊关键字匹配，杜绝时效查询误弹卡片
3. [P1-1] cards 按 type 覆盖去重，杜绝多轮交互重复追加堆叠
4. [P1-2] snippet 保留完整 FAQ 切片文本，杜绝暴力截断导致信用卡/跨行到账时效丢失
5. [P1-3] 剔除无用的 memory_synthesis 空转节点，直连 deepseek_generate
"""

from typing import Dict, Any, List, Optional
import time

try:
    from langgraph.types import interrupt
except ImportError:
    try:
        from langgraph.checkpoint.base import interrupt
    except ImportError:
        def interrupt(value: Any) -> Any:
            """LangGraph 人在环路 (Human-in-the-Loop) 中断信号机制"""
            return value

from .state import AgentState, Hit, RefundDraft, Intent
from core.qdrant_store import qdrant_store
from core.llm import deepseek_client
from services.order_service import order_service
from config import settings
from core.logger import cprint, LogColor

def analyze_query_node(state: AgentState) -> Dict[str, Any]:
    """1. 意图分类、情绪识别与人工呼叫检测节点"""
    t0 = time.time()
    msg = state.get("user_message", "").lower()
    
    # 显式人工请求判定
    explicit = any(k in msg for k in ["转人工", "人工", "投诉", "找人工", "人工客服", "主管", "消协", "找领导"])
    
    # 情绪识别 (映射为: calm, neutral, frustrated, angry)
    sentiment = "neutral"
    if any(k in msg for k in ["骗子", "投诉", "消协", "火大", "气死", "态度差", "打死"]):
        sentiment = "angry"
    elif explicit or any(k in msg for k in ["差评", "太慢", "生气", "催", "急", "不要机器人"]):
        sentiment = "frustrated"
    elif any(k in msg for k in ["谢谢", "感谢", "好的", "明白了", "点赞", "挺快"]):
        sentiment = "calm"

    # 意图识别 (精准映射为标准枚举，无死代码)
    intent: Intent = "常规售后咨询"
    if explicit:
        intent = "handoff"
    elif any(k in msg for k in ["订单", "查订单", "物流", "快递", "运单", "发货", "到哪了", "什么时候到", "送达", "签收", "收件地址", "ord-", "88992", "90412", "77310"]):
        intent = "订单查询与物流追踪"
    elif any(k in msg for k in ["运费", "谁出", "谁付", "包邮", "免运费"]):
        intent = "退换货运费承担与会员权益"
    elif any(k in msg for k in ["7天", "七天", "无理由", "退货", "退换"]):
        intent = "7天无理由退货政策"
    elif any(k in msg for k in ["特殊商品", "不能退", "不给退", "定制", "生鲜", "内裤", "母婴", "拆封"]):
        intent = "特殊不可退换商品范围"
    elif any(k in msg for k in ["到账", "几天能收到", "几天到", "多久到账", "打款时间", "退款多久", "时效"]):
        # 严格分离：退款到账时效查询，绝非退款申请！
        intent = "退款到账时效查询"
    elif any(k in msg for k in ["申请退款", "我要退款", "办理退款", "退钱给我", "我要退货退款", "提交退款"]):
        intent = "退款申请与审批"
    elif any(k in msg for k in ["保修", "维修", "坏了", "换新", "质保", "联保", "进水", "摔坏"]):
        intent = "1年联保与硬件保修条款"

    duration = int((time.time() - t0) * 1000)
    cprint.node(
        "analyze_query",
        f"意图: {LogColor.BRIGHT_WHITE}{intent}{LogColor.RESET} | 情绪: {sentiment}",
        f"显式人工请求: {explicit} (耗时 {duration}ms)"
    )

    return {
        "intent": intent,
        "sentiment": sentiment,
        "explicit_human_request": explicit,
        "trace": [f"analyze_query: 意图={intent}, 情绪={sentiment}, 显式人工={explicit} ({duration}ms)"]
    }

def order_query_node(state: AgentState) -> Dict[str, Any]:
    """2. 订单与物流中台实时检索节点 (按 type 覆盖去重 cards)"""
    t0 = time.time()
    user_msg = state.get("user_message", "")
    profile = state.get("user_profile", {})

    order = order_service.detect_and_query_order(user_msg, profile)
    order_id = order["orderId"] if order else None

    duration = int((time.time() - t0) * 1000)
    # [P1-1] cards 按 type 去重覆盖，避免反复 append order_card
    cards: List[Dict[str, Any]] = [c for c in (state.get("cards") or []) if c.get("type") != "order_card"]
    if order:
        cards.append({
            "type": "order_card",
            "order_id": order_id,
            "order": order
        })

    return {
        "order_id": order_id,
        "cards": cards,
        "trace": [f"order_query: 命中订单 [{order_id or '无'}] ({duration}ms)"]
    }

def order_refund_node(state: AgentState) -> Dict[str, Any]:
    """3. 订单退款与人工干涉控制节点 (接住 interrupt 返回值，严格意图触发)"""
    t0 = time.time()
    action = state.get("confirm_action")
    order_id = state.get("order_id")

    escalate_human = False
    escalation_reason = ""
    override_response = None
    order = None
    refund_draft: Optional[RefundDraft] = None
    # [P1-1] cards 按 type 去重，避免重复积累 refund_gate 卡片
    cards: List[Dict[str, Any]] = [c for c in (state.get("cards") or []) if c.get("type") != "refund_gate"]

    try:
        # 1. 严格校验订单归属与持久化状态
        if order_id:
            persisted_order = order_service.get_order_by_id(order_id)
            if persisted_order:
                user_profile = state.get("user_profile", {})
                profile_name = user_profile.get("name", "")
                if not profile_name or profile_name in persisted_order.get("userName", ""):
                    order = persisted_order

        if not order:
            override_response = "未检测到您关联的有效订单信息，请提供正确的订单编号，我来为您核验办理。"
            return {
                "order_id": None,
                "refund": None,
                "reply": override_response,
                "cards": cards,
                "trace": ["order_refund: 未命中有效归属订单，流程终止"]
            }

        current_status = order.get("status", "")
        amount = round(float(order.get("paidAmount", 0.0)), 2)
        amount_cents = int(round(amount * 100))  # 整数"分"，严防浮点精度失真
        request_id = f"ref_{order['orderId']}_{int(time.time() * 1000)}"

        # 2. 常规退款意图识别：如果用户没有传入确认动作，且明确是退款申请意图，触发确认门槛挂起
        # [P0-2] 严格只认 intent == "退款申请与审批"，彻底移除关键字模糊匹配
        intent = state.get("intent", "")
        is_refund_apply_intent = (intent == "退款申请与审批")
        was_pending = (state.get("refund") or {}).get("status") == "PENDING_CONFIRM"

        if not action and is_refund_apply_intent:
            rule_text = "金额 < 3.00 元，确认后将由智能客服直接秒退" if amount_cents < 300 else "金额 >= 3.00 元，确认后将提交人工干涉与资金安全审核"

            if current_status not in ["REFUNDED", "REFUND_PENDING_AUDIT"]:
                override_response = (
                    f"收到您针对订单【{order['orderId']}】（实付 ¥{amount:.2f} 元）的退款申请。\n"
                    f"根据商城退款规则（{rule_text}），在正式提交前，请您确认以下权益调整：\n"
                    f"• 订单对应的黄金/钻石会员积分及运费补贴将同步收回；\n"
                    f"• 退款将通过原支付渠道（支付宝/微信/银行卡）解冻退回。\n\n"
                    f"请在下方卡片中点击【确认提交退款】或【取消 / 我再想想】："
                )
            elif current_status == "REFUND_PENDING_AUDIT":
                override_response = (
                    f"收到您针对订单【{order['orderId']}】（实付 ¥{amount:.2f} 元）的退款申请。\n"
                    f"该订单当前正处于【退款待人工审核】状态（因金额 >= 3.00 元触发资金安全人工干涉）。\n"
                    f"如需重新提交确认或变更诉求，请在下方卡片中点击【确认提交退款】或【取消 / 我再想想】："
                )
            else:
                override_response = (
                    f"收到您针对订单【{order['orderId']}】（实付 ¥{amount:.2f} 元）的退款申请。\n"
                    f"该订单此前已完成退款解冻。如需重新提交申请测试，请在下方卡片中点击【确认提交退款】或【取消 / 我再想想】："
                )

            cards.append({
                "type": "refund_gate",
                "order_id": order["orderId"],
                "amount_cents": amount_cents,
                "amount": amount,
                "rule_text": rule_text,
                "status": "PENDING_CONFIRM"
            })

            # [P0-1 核心修复]：接住 interrupt 返回值，支持 LangGraph resume 传入唤醒动作！
            cprint.node("order_refund", f"[触发 LangGraph interrupt 挂起] 订单 {order['orderId']}", "等待用户确认")
            resume_data = interrupt({
                "type": "refund_confirmation_gate",
                "order_id": order["orderId"],
                "amount_cents": amount_cents,
                "amount": amount,
                "rule_text": rule_text,
                "prompt": "退款前风险与权益确认挂起"
            })

            # 若通过 LangGraph resume(value) 唤醒继续执行
            if isinstance(resume_data, dict):
                action = resume_data.get("action") or resume_data.get("confirm_action") or action
            elif isinstance(resume_data, str) and resume_data in ("confirm", "cancel"):
                action = resume_data

            if not action:
                refund_draft = {
                    "order_id": order["orderId"],
                    "amount_cents": amount_cents,
                    "request_id": request_id,
                    "status": "PENDING_CONFIRM"
                }

        # 3. 处理退款二次确认动作 ('confirm' 或 'cancel')
        if action == "confirm":
            if current_status == "REFUNDED":
                override_response = f"【温馨提示】订单【{order['orderId']}】此前已完成退款，款项已原路退回解冻，请您查收账户通知！"
                refund_draft = {
                    "order_id": order["orderId"],
                    "amount_cents": amount_cents,
                    "request_id": request_id,
                    "status": "SUBMITTED"
                }
            elif current_status == "REFUND_PENDING_AUDIT":
                override_response = f"【温馨提示】订单【{order['orderId']}】的退款审核工单已在处理中，无需重复提交，专员正在加急核验！"
                refund_draft = {
                    "order_id": order["orderId"],
                    "amount_cents": amount_cents,
                    "request_id": request_id,
                    "status": "PENDING_AUDIT"
                }
            else:
                if amount_cents < 300:  # < 3.00 元智能秒退
                    order = order_service.process_refund_request(order["orderId"], reason="用户二次确认提交退款(自动秒退)", refund_amount=amount)
                    override_response = f"【智能客服秒退成功】您已二次确认！订单【{order['orderId']}】实付金额为 ¥{amount:.2f} 元 (< 3.00 元)，智能客服已为您直接原路退回解冻，请查收！"
                    refund_draft = {
                        "order_id": order["orderId"],
                        "amount_cents": amount_cents,
                        "request_id": request_id,
                        "status": "SUBMITTED"
                    }
                    cprint.node("order_refund", f"[幂等秒退成功] 订单 {order['orderId']} 金额 {amount_cents}分", "秒退完成")
                else:  # >= 3.00 元提交人工干涉审核队列
                    order = order_service.process_refund_request(order["orderId"], reason="用户二次确认提交退款(人工审核)", refund_amount=amount)
                    escalate_human = True
                    escalation_reason = f"订单 {order['orderId']} 申请退款金额 ¥{amount:.2f} 元 (>= 3.00 元)，涉及资金安全，已通过二次确认提交至人工干涉与审核队列"
                    override_response = f"【退款审核工单已提交】您已二次确认！订单【{order['orderId']}】实付金额为 ¥{amount:.2f} 元 (>= 3.00 元)，涉及商城资金安全，已自动为您无缝对接人工客服加急干涉与核验！"
                    refund_draft = {
                        "order_id": order["orderId"],
                        "amount_cents": amount_cents,
                        "request_id": request_id,
                        "status": "PENDING_AUDIT"
                    }
                    cprint.node("order_refund", f"[转人工干涉队列] 订单 {order['orderId']} 金额 {amount_cents}分", "转人工核验")

        elif action == "cancel":
            override_response = f"已为您取消退款申请，订单【{order['orderId']}】将保持正常签收状态。如需其他帮助，随时联系我！"
            refund_draft = {
                "order_id": order["orderId"],
                "amount_cents": amount_cents,
                "request_id": request_id,
                "status": "CANCELED"
            }
            cprint.node("order_refund", "用户点击取消退款申请", "恢复正常状态")

        elif was_pending and not override_response:
            override_response = (
                f"温馨提示：您的订单【{order['orderId']}】退款申请尚处于【待交互确认】状态，系统尚未正式提交。\n"
                f"请您在下方卡片中点击【确认提交退款】（如需退款）或【取消 / 我再想想】（放弃退款），完成确认后系统将立即处理！"
            )
            refund_draft = {
                "order_id": order["orderId"],
                "amount_cents": amount_cents,
                "request_id": request_id,
                "status": "PENDING_CONFIRM"
            }

    except Exception as e:
        cprint.error(f"[order_refund_node 异常兜底]: {e}")
        override_response = "系统在处理您的退款申请时遇到临时校验异常，已为您转接人工客服专员为您紧急处理，请稍候..."
        escalate_human = True
        escalation_reason = f"退款处理节点异常兜底: {str(e)}"

    duration = int((time.time() - t0) * 1000)
    trace_desc = f"order_refund: action={action}, status={refund_draft['status'] if refund_draft else 'none'} ({duration}ms)"

    res: Dict[str, Any] = {
        "order_id": order.get("orderId") if order else None,
        "refund": refund_draft,
        "cards": cards,
        "trace": [trace_desc]
    }

    if override_response:
        res["reply"] = override_response

    if escalate_human:
        res["handoff"] = True
        res["escalation_reason"] = escalation_reason

    return res

def qdrant_retrieve_node(state: AgentState) -> Dict[str, Any]:
    """4. 基于 BGE-M3 向量嵌入检索 FAQ 条款 (保留完整 snippet，防到账时效丢失)"""
    t0 = time.time()
    query = state.get("user_message", "")
    
    hits = qdrant_store.similarity_search(query, k=settings.TOP_K_RETRIEVAL)
    top_score = hits[0]["score"] if hits else 0.0
    top_title = hits[0]["doc"].get("title", "无直接匹配") if hits else "无"

    # 仅保留达到相似度阈值的文档
    valid_hits = [h for h in hits if h.get("score", 0.0) >= settings.SIMILARITY_THRESHOLD]

    # [P1-2 修复]：保留完整 snippet 文本，不进行 [:150] 截断，防止信用卡与各渠道到账时效缺失
    formatted_hits: List[Hit] = [
        {
            "id": str(h.get("id") or h["doc"].get("id", f"hit_{i}")),
            "title": h["doc"].get("title", ""),
            "score": round(float(h.get("score", 0.0)), 4),
            "snippet": h["doc"].get("content", "")
        }
        for i, h in enumerate(valid_hits)
    ]

    duration = int((time.time() - t0) * 1000)
    cprint.rag(query, len(formatted_hits), top_score, top_title)

    return {
        "hits": formatted_hits,
        "trace": [f"qdrant_retrieve: hits={len(formatted_hits)}, top_score={top_score:.2f} ({duration}ms)"]
    }

async def deepseek_generate_node(state: AgentState) -> Dict[str, Any]:
    """5. 调用 DeepSeek 大模型生成严谨回答 (直连检索与业务事实，去掉空转中间节点)"""
    t0 = time.time()
    user_msg = state.get("user_message", "")
    existing_reply = state.get("reply")
    cards = list(state.get("cards") or [])

    # 若前置节点已生成明确文案（如秒退或待确认门槛），优先保留
    if existing_reply:
        return {
            "reply": existing_reply,
            "cards": cards,
            "handoff": state.get("handoff", False),
            "trace": ["deepseek_generate: 保留前置确定性回复文案"]
        }

    hits = state.get("hits", [])
    memory = state.get("memory_summary", "")
    profile = state.get("user_profile", {})
    order_id = state.get("order_id")

    reply = await deepseek_client.generate_response(
        user_message=user_msg,
        hits=hits,
        memory_summary=memory,
        user_profile=profile,
        order_id=order_id
    )

    duration = int((time.time() - t0) * 1000)
    cprint.node(
        "deepseek_generate",
        f"DeepSeek 推理完成，生成回复: {LogColor.BRIGHT_GREEN}{len(reply)} 字{LogColor.RESET}",
        f"耗时: {duration}ms"
    )

    return {
        "reply": reply,
        "cards": cards,
        "handoff": False,
        "trace": [f"deepseek_generate: 生成答复 ({len(reply)} 字) ({duration}ms)"]
    }

def human_escalation_node(state: AgentState) -> Dict[str, Any]:
    """6. 人工接入触发节点 (主动要求或低置信度兜底)"""
    t0 = time.time()
    explicit = state.get("explicit_human_request", False) or state.get("intent") == "handoff"
    hits = state.get("hits", [])
    top_score = hits[0]["score"] if hits else 0.0
    low_conf = len(hits) == 0 or top_score < settings.SIMILARITY_THRESHOLD

    if explicit:
        reason = "客户主动要求转人工客服服务"
    elif low_conf:
        reason = f"Qdrant 向量匹配得分较低 (< {settings.SIMILARITY_THRESHOLD})，转人工以防误答"
    elif state.get("sentiment") in ["frustrated", "angry"]:
        reason = "客户情绪预警，启动人工跟进"
    else:
        reason = "知识库无可用依据，转人工兜底处理"

    session_id = state.get("session_id", "当前会话")
    cprint.transfer(session_id, "值班客服专员", reason)

    reply = "【智能管家温馨提示】收到您的需求，正在为您无缝转接 XX商城 官方售后值班专员。我们将保留您的完整对话快照与政策咨询记录，请稍候片刻..."
    cards = list(state.get("cards") or [])
    duration = int((time.time() - t0) * 1000)

    return {
        "reply": reply,
        "handoff": True,
        "escalation_reason": reason,
        "cards": cards,
        "trace": [f"human_escalation: 触发转人工 (原因: {reason}) ({duration}ms)"]
    }

# ================= 智能条件路由 =================

def router_after_analysis(state: AgentState) -> str:
    """第一级路由：若显式要求人工或意图为 handoff，直接转人工；若涉及订单，进入 order_query 节点"""
    if state.get("explicit_human_request") or state.get("intent") == "handoff":
        return "human_escalation"
    
    intent = state.get("intent", "")
    if intent in [
        "订单查询与物流追踪",
        "退款申请与审批",
        "退款到账时效查询",
        "7天无理由退货政策"
    ]:
        return "order_query"
        
    return "qdrant_retrieve"

def router_after_order_query(state: AgentState) -> str:
    """订单查询后的条件路由：仅当明确为退款申请意图、存在确认动作或处于待确认挂起状态时才进入退款节点"""
    action = state.get("confirm_action")
    intent = state.get("intent", "")
    was_pending = (state.get("refund") or {}).get("status") == "PENDING_CONFIRM"

    # [P0-2 修复]：彻底去掉关键字模糊匹配，"退款到账时效查询" 将平滑直达 qdrant_retrieve 回答用户问题
    if action in ["confirm", "cancel"] or intent == "退款申请与审批" or was_pending:
        return "order_refund"
    return "qdrant_retrieve"

def router_after_retrieval(state: AgentState) -> str:
    """第二级路由：检索置信度低于阈值且用户情绪烦躁时升级人工，否则直达 DeepSeek 生成"""
    hits = state.get("hits", [])
    top_score = hits[0]["score"] if hits else 0.0
    sentiment = state.get("sentiment", "neutral")
    if top_score < settings.SIMILARITY_THRESHOLD and sentiment in ["frustrated", "angry"]:
        return "human_escalation"
    # [P1-3 修复]：直接进入 deepseek_generate，剔除 memory_synthesis 空转
    return "deepseek_generate"
