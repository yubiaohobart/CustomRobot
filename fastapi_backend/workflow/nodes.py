"""
LangGraph 状态图执行节点实现 (Workflow Nodes)
涵盖：
1. 意图与情绪分析 (analyze_query)
2. Qdrant + BGE-M3 向量检索 (qdrant_retrieve)
3. 记忆与上下文合成 (memory_synthesis)
4. DeepSeek 大模型回复生成 (deepseek_generate)
5. 人工坐席升级判定 (human_escalation)
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

from models.state import AgentState
from core.qdrant_store import qdrant_store
from core.llm import deepseek_client
from services.order_service import order_service
from config import settings
from core.logger import cprint, LogColor

def analyze_query_node(state: AgentState) -> Dict[str, Any]:
    """1. 意图分类、情绪识别与人工呼叫检测节点"""
    t0 = time.time()
    msg = state["user_message"].lower()
    
    # 检测是否显式要求人工
    explicit = any(k in msg for k in ["转人工", "人工", "投诉", "找人工", "人工客服", "主管", "消协", "找领导"])
    
    # 情绪识别
    sentiment = "neutral"
    if explicit or any(k in msg for k in ["差评", "太慢", "生气", "骗子", "态度差", "催", "急", "火大", "不要机器人"]):
        sentiment = "frustrated"
    elif any(k in msg for k in ["谢谢", "感谢", "好的", "明白了", "点赞", "挺快"]):
        sentiment = "positive"

    # XX商城 2026 售后核心意图分类
    intent = "常规售后咨询"
    if any(k in msg for k in ["订单", "查订单", "物流", "快递", "运单", "发货", "到哪了", "什么时候到", "送达", "签收", "收件地址", "ord-", "88992", "90412", "77310"]):
        intent = "订单查询与物流追踪"
    elif any(k in msg for k in ["运费", "谁出", "谁付", "包邮", "免运费"]):
        intent = "退换货运费承担与会员权益"
    elif any(k in msg for k in ["7天", "七天", "无理由", "退货", "退换"]):
        intent = "7天无理由退货政策"
    elif any(k in msg for k in ["特殊商品", "不能退", "不给退", "定制", "生鲜", "内裤", "母婴", "拆封"]):
        intent = "特殊不可退换商品范围"
    elif any(k in msg for k in ["到账", "多久", "几天", "退款", "打款", "银行卡", "微信", "支付宝"]):
        intent = "退款质检与到账时效"
    elif any(k in msg for k in ["保修", "维修", "坏了", "换新", "质保", "联保", "进水", "摔坏"]):
        intent = "1年联保与硬件保修条款"

    duration = int((time.time() - t0) * 1000)
    cprint.node(
        "analyze_query",
        f"意图: {LogColor.BRIGHT_WHITE}{intent}{LogColor.RESET} | 情绪: {sentiment}",
        f"显式人工请求: {explicit} (耗时 {duration}ms)"
    )

    trace = state.get("step_trace", [])
    trace.append({
        "node": "analyze_query",
        "description": f"意图识别: {intent} | 情绪: {sentiment} | 显式人工请求: {explicit}",
        "durationMs": duration,
        "status": "success"
    })

    return {
        "intent": intent,
        "sentiment": sentiment,
        "explicit_human_request": explicit,
        "step_trace": trace
    }

def order_query_node(state: AgentState) -> Dict[str, Any]:
    """2. 订单与物流中台实时检索节点 (Order Query Node)"""
    t0 = time.time()
    user_msg = state["user_message"]
    profile = state.get("user_profile", {})

    order = order_service.detect_and_query_order(user_msg, profile)
    order_summary = ""
    if order:
        order_summary = order_service.format_order_summary_text(order)

    duration = int((time.time() - t0) * 1000)
    trace = state.get("step_trace", [])
    trace.append({
        "node": "order_query",
        "description": f"检索关联订单 [{order['orderId'] if order else '无关联订单'}]",
        "durationMs": duration,
        "status": "success" if order else "warning"
    })

    return {
        "queried_order": order,
        "order_query_info": order_summary,
        "business_facts_text": order_summary,
        "business_facts_list": [order] if order else [],
        "step_trace": trace
    }

def order_refund_node(state: AgentState) -> Dict[str, Any]:
    """3. 订单退款与人工干涉控制节点 (Order Refund Node)"""
    t0 = time.time()
    user_msg = state["user_message"]
    action = state.get("refund_confirmation_action")
    order = state.get("queried_order")

    escalate_human = False
    escalation_reason = ""
    refund_pending = False
    pending_order = None
    override_response = None

    # 1. 处理退款二次确认恢复动作 ('confirm' 或 'cancel')
    if action == "confirm":
        if order:
            amount = float(order.get("paidAmount", 0.0))
            if amount < 3.00:
                order = order_service.process_refund_request(order["orderId"], reason="用户二次确认提交退款", refund_amount=amount)
                override_response = f"【智能客服秒退成功】您已二次确认！订单【{order['orderId']}】实付金额为 ¥{amount:.2f} 元 (< 3.00 元)，智能客服已为您直接原路退回解冻，请查收！"
                cprint.node("order_refund", f"[二次确认通过-秒退] 订单 {order['orderId']} 金额 ¥{amount:.2f} < 3元", "秒退成功")
            else:
                order = order_service.process_refund_request(order["orderId"], reason="用户二次确认提交退款", refund_amount=amount)
                escalate_human = True
                escalation_reason = f"订单 {order['orderId']} 申请退款金额 ¥{amount:.2f} 元 (>= 3.00 元)，涉及资金安全，已通过二次确认提交至人工干涉与审核队列"
                override_response = f"【退款审核工单已提交】您已二次确认！订单【{order['orderId']}】实付金额为 ¥{amount:.2f} 元 (>= 3.00 元)，涉及商城资金安全，已自动为您无缝对接人工客服加急干涉与核验！"
                cprint.node("order_refund", f"[二次确认通过-转人工干涉] 订单 {order['orderId']} 金额 ¥{amount:.2f} >= 3元", "转人工核验")
            pending_order = order

    elif action == "cancel":
        override_response = f"已为您取消退款申请，订单【{order['orderId'] if order else ''}】将保持正常签收状态。如需其他帮助，随时联系我！"
        cprint.node("order_refund", "用户点击取消退款申请", "恢复正常状态")

    else:
        # 2. 常规检测退款意图：触发二次确认中断卡片 (Customer Confirmation Gate)
        if order:
            is_refund_intent = any(k in user_msg for k in ["退款", "退货", "申请退款", "要退", "退钱", "退回"])
            was_pending = state.get("refund_confirmation_pending", False)
            current_status = order.get("status", "")

            if is_refund_intent and current_status not in ["REFUNDED", "REFUND_PENDING_AUDIT"]:
                amount = float(order.get("paidAmount", 0.0))
                refund_pending = True
                pending_order = order
                rule_text = "金额 < 3.00 元，确认后将由智能客服直接秒退" if amount < 3.00 else "金额 >= 3.00 元，确认后将提交人工干涉与资金安全审核"
                override_response = (
                    f"收到您针对订单【{order['orderId']}】（实付 ¥{amount:.2f} 元）的退款申请。\n"
                    f"根据商城退款规则（{rule_text}），在正式提交前，请您确认以下权益调整：\n"
                    f"• 订单对应的黄金/钻石会员积分及运费补贴将同步收回；\n"
                    f"• 退款将通过原支付渠道（支付宝/微信/银行卡）解冻退回。\n\n"
                    f"请在下方卡片中点击【确认提交退款】或【取消 / 我再想想】："
                )
                try:
                    interrupt({
                        "type": "refund_confirmation_gate",
                        "order_id": order['orderId'],
                        "amount": amount,
                        "rule_text": rule_text,
                        "prompt": "退款前风险与权益确认挂起"
                    })
                except Exception:
                    pass

                cprint.node("order_refund", f"[触发 LangGraph interrupt 退款二次确认中断] 订单 {order['orderId']} 金额 ¥{amount:.2f}", "等待用户点击二次确认")
            elif was_pending and any(k in user_msg for k in ["进度", "好了吗", "退了吗", "审核过了吗", "处理了吗"]):
                refund_pending = True
                pending_order = order
                override_response = (
                    f"温馨提示：您的订单【{order['orderId']}】退款申请尚处于【待交互确认】状态，系统尚未正式提交。\n"
                    f"请您在上方卡片中点击【确认提交退款】（如需退款）或【取消 / 我再想想】（放弃退款），完成确认后系统将立即处理！"
                )
                cprint.node("order_refund", f"[追问未确认的退款] 订单 {order['orderId']}", "提醒用户先点击卡片确认")
            elif is_refund_intent and current_status == "REFUND_PENDING_AUDIT":
                pending_order = order
                override_response = (
                    f"您针对订单【{order['orderId']}】（实付 ¥{float(order.get('paidAmount', 0.0)):.2f} 元）的退款申请已处于【退款待人工审核】状态。\n"
                    f"工单已自动接入专属坐席加急干涉，请您耐心等待核验结果！"
                )
                cprint.node("order_refund", f"[重复发起已在审核中的退款] 订单 {order['orderId']}", "提示审核处理中")
            elif is_refund_intent and current_status == "REFUNDED":
                pending_order = order
                override_response = (
                    f"订单【{order['orderId']}】（实付 ¥{float(order.get('paidAmount', 0.0)):.2f} 元）此前已完成退款解冻，款项已原路退回您的支付账户。"
                )
                cprint.node("order_refund", f"[重复发起已退款订单] 订单 {order['orderId']}", "提示已完成退款")

    duration = int((time.time() - t0) * 1000)
    trace = state.get("step_trace", [])
    trace.append({
        "node": "order_refund",
        "description": f"处理退款动作与二次确认门槛，挂起状态: {refund_pending}",
        "durationMs": duration,
        "status": "success"
    })

    res: Dict[str, Any] = {
        "queried_order": order,
        "refund_confirmation_pending": refund_pending,
        "pending_refund_order": pending_order,
        "step_trace": trace
    }

    if override_response:
        res["generated_response"] = override_response

    if escalate_human:
        res["escalated_to_human"] = True
        res["escalation_reason"] = escalation_reason

    return res

def qdrant_retrieve_node(state: AgentState) -> Dict[str, Any]:
    """2. 基于 BGE-M3 向量嵌入在 Qdrant 数据库中检索相关 FAQ 条款"""
    t0 = time.time()
    query = state["user_message"]
    
    # 调用 Qdrant 检索
    hits = qdrant_store.similarity_search(query, k=settings.TOP_K_RETRIEVAL)
    
    top_score = hits[0]["score"] if hits else 0.0
    top_title = hits[0]["doc"].get("title", "无直接匹配") if hits else "无"

    # 工业级 RAG 阈值门禁：仅保留达到相似度阈值的文档，过滤低相关度噪声，防止污染 Prompt 上下文
    valid_hits = [h for h in hits if h.get("score", 0.0) >= settings.SIMILARITY_THRESHOLD]
    docs = [h["doc"] for h in valid_hits]

    duration = int((time.time() - t0) * 1000)
    cprint.rag(query, len(docs), top_score, top_title)

    trace = state.get("step_trace", [])
    if docs:
        trace_desc = f"Qdrant (BGE-M3 1024维) 命中 {len(docs)} 条强相关条款 (最高分: {top_score:.2f} >= 阈值 {settings.SIMILARITY_THRESHOLD})"
        trace_status = "success"
    else:
        trace_desc = f"Qdrant 检索最高相似度 {top_score:.2f} 低于阈值 {settings.SIMILARITY_THRESHOLD}，判定无相关政策，未注入条款"
        trace_status = "warning"

    trace.append({
        "node": "qdrant_retrieve",
        "description": trace_desc,
        "durationMs": duration,
        "status": trace_status
    })

    return {
        "retrieved_docs": docs,
        "top_similarity_score": top_score,
        "retrieval_ran": True,
        "step_trace": trace
    }

def memory_synthesis_node(state: AgentState) -> Dict[str, Any]:
    """3. 结合长期会话记忆、用户画像与 Qdrant 检索结果构建提示上下文 (方案1: 业务实体事实抽象)"""
    t0 = time.time()
    docs = state.get("retrieved_docs", [])
    doc_titles = [d.get("title", "") for d in docs]
    
    # 汇总通用业务事实（订单、物流、发票等中台数据统一汇聚）
    facts_text = (state.get("business_facts_text") or state.get("order_query_info") or "").strip()
    order = state.get("queried_order")
    if not facts_text and order:
        facts_text = order_service.format_order_summary_text(order)

    facts_summary = f"注入业务实体事实 ({len(facts_text)}字)，" if facts_text else "无特定业务实体数据，"
    duration = int((time.time() - t0) * 1000)

    cprint.node(
        "memory_synthesis",
        f"通用事实与画像装配完成 ({facts_summary}关联政策: {len(doc_titles)} 条)",
        f"耗时: {duration}ms"
    )

    trace = state.get("step_trace", [])
    trace.append({
        "node": "memory_synthesis",
        "description": f"合成上下文：{facts_summary}关联政策 [{', '.join(doc_titles)}]，注入长期记忆与VIP画像",
        "durationMs": duration,
        "status": "success"
    })

    return {
        "business_facts_text": facts_text,
        "step_trace": trace
    }

async def deepseek_generate_node(state: AgentState) -> Dict[str, Any]:
    """4. 调用 DeepSeek 大模型生成温暖、严谨且符合政策的专业回答 (方案1: 接入通用业务事实槽位)"""
    t0 = time.time()
    user_msg = state["user_message"]
    existing_reply = state.get("generated_response")

    # 若前置节点（如 order_refund_node）已设置明确的交互确认/秒退文案，优先保留
    if existing_reply:
        trace = state.get("step_trace", [])
        trace.append({
            "node": "deepseek_generate",
            "description": "前置节点已生成确切交互文案，保留既定回复",
            "durationMs": int((time.time() - t0) * 1000),
            "status": "success"
        })
        return {
            "generated_response": existing_reply,
            "step_trace": trace
        }

    docs = state.get("retrieved_docs", [])
    memory = state.get("summary_memory", "")
    profile = state.get("user_profile", {})
    order = state.get("queried_order")
    order_summary = state.get("order_query_info", "")
    business_facts = state.get("business_facts_text", "") or order_summary

    reply = await deepseek_client.generate_response(
        user_message=user_msg,
        retrieved_docs=docs,
        summary_memory=memory,
        user_profile=profile,
        business_facts=business_facts,
        order_info=order,
        order_summary=order_summary
    )

    duration = int((time.time() - t0) * 1000)
    cprint.node(
        "deepseek_generate",
        f"DeepSeek 推理完成，生成回复: {LogColor.BRIGHT_GREEN}{len(reply)} 字{LogColor.RESET}",
        f"耗时: {duration}ms"
    )

    trace = state.get("step_trace", [])
    trace.append({
        "node": "deepseek_generate",
        "description": f"DeepSeek ({settings.DEEPSEEK_MODEL}) 完成针对性答复生成 (共 {len(reply)} 字)",
        "durationMs": duration,
        "status": "success"
    })

    return {
        "generated_response": reply,
        "step_trace": trace
    }

def human_escalation_node(state: AgentState) -> Dict[str, Any]:
    """5. 人工接入触发节点（置信度不足或主动呼叫转人工）"""
    t0 = time.time()
    explicit = state.get("explicit_human_request", False)
    retrieval_ran = state.get("retrieval_ran", False)
    # 仅在检索真实执行过时，相似度才有解释力；否则 0.0 只是初始值，不能当低置信度
    low_conf = retrieval_ran and state.get("top_similarity_score", 0.0) < settings.SIMILARITY_THRESHOLD

    if explicit:
        reason = "客户主动要求转人工客服服务"
    elif low_conf:
        reason = f"Qdrant 向量匹配得分较低 (< {settings.SIMILARITY_THRESHOLD})，转人工以防误答"
    elif state.get("sentiment") == "frustrated":
        reason = "客户负向情绪预警，启动人工跟进"
    else:
        reason = "知识库无可用依据，转人工兜底处理"

    session_id = state.get("session_id", "当前会话")
    cprint.transfer(session_id, "值班客服专员", reason)

    reply = "【智能管家温馨提示】收到您的需求，正在为您无缝转接 XX商城 官方售后值班专员。我们将保留您的完整对话快照与政策咨询记录，请稍候片刻..."

    trace = state.get("step_trace", [])
    trace.append({
        "node": "human_escalation",
        "description": f"触发人工介入判定：{reason}",
        "durationMs": int((time.time() - t0) * 1000),
        "status": "warning"
    })

    return {
        "generated_response": reply,
        "escalated_to_human": True,
        "escalation_reason": reason,
        "step_trace": trace
    }

# ================= 路由条件分支 =================

def router_after_analysis(state: AgentState) -> str:
    """第一级路由：若用户强指令要求人工，则直接路由至人工升级；若涉及订单/物流查询，则路由到订单查询节点"""
    if state.get("explicit_human_request"):
        return "human_escalation"
    if state.get("intent") in ["订单查询与物流追踪", "退款质检与到账时效", "7天无理由退货政策"]:
        return "order_query"
    return "qdrant_retrieve"

def router_after_order_query(state: AgentState) -> str:
    """订单查询后的条件路由：若有退款意图或交互动作，进入退款节点；否则跳过退款节点直接进行知识检索与大模型答复"""
    user_msg = state.get("user_message", "").lower()
    action = state.get("refund_confirmation_action")
    is_refund = any(k in user_msg for k in ["退款", "退货", "申请退款", "要退", "退钱", "退回"])
    was_pending = state.get("refund_confirmation_pending", False)

    if action in ["confirm", "cancel"] or is_refund or was_pending:
        return "order_refund"
    return "qdrant_retrieve"

def router_after_retrieval(state: AgentState) -> str:
    """第二级路由：检索置信度低于统一阈值且用户情绪烦躁时升级人工，否则进入 DeepSeek 生成

    阈值复用 settings.SIMILARITY_THRESHOLD，与 qdrant_retrieve_node 的文档过滤保持一致，
    避免出现「文档已被过滤为空、却仍去生成回答」的无依据回答。
    """
    score = state.get("top_similarity_score", 0.0)
    sentiment = state.get("sentiment", "neutral")
    if score < settings.SIMILARITY_THRESHOLD and sentiment == "frustrated":
        return "human_escalation"
    return "memory_synthesis"
