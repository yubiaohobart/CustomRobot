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
        item_title = order["items"][0]["title"] if order.get("items") else "未知商品"
        cprint.node(
            "order_query",
            f"成功调取订单: {LogColor.BRIGHT_CYAN}{order['orderId']}{LogColor.RESET} ({order['statusText']})",
            f"商品: {item_title}"
        )
        desc = f"中台检索到关联订单 [{order['orderId']}]，状态: {order['statusText']}，物流: {order.get('express', {}).get('company')} ({order.get('express', {}).get('trackingNumber')})"
    else:
        cprint.node("order_query", "未匹配到指定订单", "按常规售后知识库策略流转")
        desc = "未提供或未匹配到具体订单编号，继续进行政策库检索"

    duration = int((time.time() - t0) * 1000)
    trace = state.get("step_trace", [])
    trace.append({
        "node": "order_query",
        "description": desc,
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

def qdrant_retrieve_node(state: AgentState) -> Dict[str, Any]:
    """2. 基于 BGE-M3 向量嵌入在 Qdrant 数据库中检索相关 FAQ 条款"""
    t0 = time.time()
    query = state["user_message"]
    
    # 调用 Qdrant 检索
    hits = qdrant_store.similarity_search(query, k=settings.TOP_K_RETRIEVAL)
    
    docs = [h["doc"] for h in hits]
    top_score = hits[0]["score"] if hits else 0.0
    top_title = docs[0].get("title", "无直接匹配") if docs else "无"

    duration = int((time.time() - t0) * 1000)
    cprint.rag(query, len(docs), top_score, top_title)

    trace = state.get("step_trace", [])
    trace.append({
        "node": "qdrant_retrieve",
        "description": f"Qdrant (BGE-M3 1024维) 检索召回 {len(docs)} 条条款，最高相似度: {top_score}",
        "durationMs": duration,
        "status": "success" if top_score >= settings.SIMILARITY_THRESHOLD else "warning"
    })

    return {
        "retrieved_docs": docs,
        "top_similarity_score": top_score,
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
    low_conf = state.get("top_similarity_score", 1.0) < settings.SIMILARITY_THRESHOLD
    
    if explicit:
        reason = "客户主动要求转人工客服服务"
    elif low_conf:
        reason = f"Qdrant 向量匹配得分较低 (< {settings.SIMILARITY_THRESHOLD})，转人工以防误答"
    else:
        reason = "客户负向情绪预警，启动人工跟进"

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
    if state.get("intent") == "订单查询与物流追踪":
        return "order_query"
    return "qdrant_retrieve"

def router_after_retrieval(state: AgentState) -> str:
    """第二级路由：若 Qdrant 检索置信度极低 (<0.45) 且带有情绪，可升级人工，否则进入 DeepSeek 生成"""
    score = state.get("top_similarity_score", 0.0)
    sentiment = state.get("sentiment", "neutral")
    if score < 0.45 and sentiment == "frustrated":
        return "human_escalation"
    return "memory_synthesis"
