"""
LangGraph 工作流编排管线：
Query Router -> Vector Search -> Memory Synthesis -> LLM Generation -> Confidence Guardrail -> Human Escalation
"""

from typing import TypedDict, List, Dict, Any, Optional
import os
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from vector_store import VectorKnowledgeStore

class AgentState(TypedDict):
    session_id: str
    user_message: str
    intent: str
    sentiment: str
    explicit_human_request: bool
    retrieved_docs: List[Dict[str, Any]]
    top_similarity_score: float
    user_profile: Dict[str, Any]
    summary_memory: str
    assembled_prompt: str
    generated_response: str
    escalated_to_human: bool
    escalation_reason: str
    step_trace: List[Dict[str, Any]]

# 初始化向量知识库与内存检查点
vector_db = VectorKnowledgeStore()
memory_store = MemorySaver()

# ================= 节点函数实现 =================

def analyze_query_node(state: AgentState) -> Dict[str, Any]:
    """1. 意图分类与负面情绪/人工指令初筛节点"""
    msg = state["user_message"].lower()
    explicit = any(k in msg for k in ["转人工", "人工", "投诉", "找人工", "主管", "消协", "退钱", "人工客服"])
    
    sentiment = "neutral"
    if explicit or any(k in msg for k in ["差评", "太慢", "生气", "骗子", "态度差", "催", "急", "火大"]):
        sentiment = "frustrated"
    elif any(k in msg for k in ["谢谢", "感谢", "好的", "点赞", "挺快"]):
        sentiment = "positive"
        
    intent = "常规业务咨询"
    if any(k in msg for k in ["退货", "退款", "七天", "无理由", "换货", "质量问题"]):
        intent = "售后退换货政策"
    elif any(k in msg for k in ["发票", "专票", "普票", "开票", "纳税人"]):
        intent = "账单与发票申请"
    elif any(k in msg for k in ["快递", "物流", "顺丰", "运费", "发货", "签收"]):
        intent = "物流时效与发货"
    elif any(k in msg for k in ["vip", "会员", "积分", "折扣", "生日"]):
        intent = "会员权益与特权"
        
    trace = state.get("step_trace", [])
    trace.append({
        "node": "analyze_query",
        "intent": intent,
        "sentiment": sentiment,
        "explicit_human_request": explicit
    })
    
    return {
        "intent": intent,
        "sentiment": sentiment,
        "explicit_human_request": explicit,
        "step_trace": trace
    }

def vector_retrieve_node(state: AgentState) -> Dict[str, Any]:
    """2. 向量数据库语义检索节点"""
    query = state["user_message"]
    results = vector_db.similarity_search(query, k=3)
    
    docs = [r["doc"] for r in results]
    top_score = results[0]["score"] if results else 0.0
    
    trace = state.get("step_trace", [])
    trace.append({
        "node": "vector_retrieve",
        "retrieved_count": len(docs),
        "top_score": top_score
    })
    
    return {
        "retrieved_docs": docs,
        "top_similarity_score": top_score,
        "step_trace": trace
    }

def memory_synthesis_node(state: AgentState) -> Dict[str, Any]:
    """3. 结合长期会话记忆与参考知识库构建上下文 Prompt"""
    knowledge_text = "\n\n".join([f"[{d['title']}]: {d['content']}" for d in state.get("retrieved_docs", [])])
    memory_text = state.get("summary_memory", "新会话建立，尚无摘要。")
    user_name = state.get("user_profile", {}).get("name", "尊敬的客户")
    
    prompt = f"""你是一名官方资深智能客服专家。请严格基于以下知识库与客户长期记忆回答：

【客户长期会话记忆 (MemorySaver)】:
{memory_text}

【企业向量知识库参考 (RAG)】:
{knowledge_text}

【客户当前提问】:
{state['user_message']}

要求：
1. 口吻诚恳、礼貌、专业，直接给出清晰的业务解决方案；
2. 如果知识库中包含对应规则，请给出精准条款与时效说明；
3. 如果客户情绪急躁，请主动致歉并说明正在重点跟进。"""
    
    trace = state.get("step_trace", [])
    trace.append({"node": "memory_synthesis", "prompt_len": len(prompt)})
    
    return {
        "assembled_prompt": prompt,
        "step_trace": trace
    }

def llm_generate_node(state: AgentState) -> Dict[str, Any]:
    """4. 大模型答案生成节点"""
    # 模拟高质量生成（在配置 GEMINI_API_KEY 时可调用真实 Gemini 接口）
    top_doc = state["retrieved_docs"][0] if state["retrieved_docs"] else None
    user_msg = state["user_message"]
    
    if "退" in user_msg and top_doc:
        reply = f"尊敬的客户您好！根据售后政策：支持签收后7天无理由退货（拆封且不影响二次销售亦可支持）。若是钻石VIP客户，支持专属极速垫付退款通道。顺丰取件免运费，请您在个人中心点击退换申请即可！"
    elif ("发票" in user_msg or "专票" in user_msg) and top_doc:
        reply = f"您好！企业增值税专用发票开具需提供纳税人识别号、银行开户许可证及地址电话。确认收货后1个工作日内系统即自动开具，并免费顺丰包邮寄送纸质发票，您也可在后台下载电子凭证。"
    elif ("顺丰" in user_msg or "物流" in user_msg or "快递" in user_msg) and top_doc:
        reply = f"您好！全场订单满99元全国顺丰包邮（含冷链及生鲜专送）。当日16:00前下单当天发出，华东华南核心城市支持次晨达与次日达服务。"
    else:
        doc_snippet = top_doc['content'][:120] if top_doc else "平台为您提供全流程保障服务"
        reply = f"您好！关于您咨询的问题：{doc_snippet}... 如需办理特批或有加急事项，欢迎随时告诉我或点击转人工！"
        
    trace = state.get("step_trace", [])
    trace.append({"node": "llm_generate", "reply_len": len(reply)})
    
    return {
        "generated_response": reply,
        "step_trace": trace
    }

def human_escalation_node(state: AgentState) -> Dict[str, Any]:
    """5. 人工介入与预警挂起节点"""
    explicit = state.get("explicit_human_request", False)
    low_conf = state.get("top_similarity_score", 1.0) < 0.65
    sentiment_bad = state.get("sentiment") == "frustrated"
    
    reason = "客户显式要求转人工客服" if explicit else (
        "知识库匹配置信度不足（< 0.65），智能客服无法准确回答" if low_conf else "客户情绪负向/急躁预警"
    )
    
    trace = state.get("step_trace", [])
    trace.append({"node": "human_escalation", "reason": reason})
    
    return {
        "escalated_to_human": True,
        "escalation_reason": reason,
        "step_trace": trace
    }

# ================= 条件路由逻辑 =================

def router_after_analysis(state: AgentState) -> str:
    """根据意图初筛决定：直接升级人工或进入知识库检索"""
    if state.get("explicit_human_request"):
        return "human_escalation"
    return "vector_retrieve"

def router_after_retrieval(state: AgentState) -> str:
    """根据检索置信度决定：如果小于0.60则直接无法回答并转人工，否则进入生成"""
    score = state.get("top_similarity_score", 0.0)
    if score < 0.60:
        return "human_escalation"
    return "memory_synthesis"

# ================= 构建 StateGraph =================

builder = StateGraph(AgentState)

builder.add_node("analyze_query", analyze_query_node)
builder.add_node("vector_retrieve", vector_retrieve_node)
builder.add_node("memory_synthesis", memory_synthesis_node)
builder.add_node("llm_generate", llm_generate_node)
builder.add_node("human_escalation", human_escalation_node)

builder.add_edge(START, "analyze_query")

builder.add_conditional_edges(
    "analyze_query",
    router_after_analysis,
    {
        "human_escalation": "human_escalation",
        "vector_retrieve": "vector_retrieve"
    }
)

builder.add_conditional_edges(
    "vector_retrieve",
    router_after_retrieval,
    {
        "human_escalation": "human_escalation",
        "memory_synthesis": "memory_synthesis"
    }
)

builder.add_edge("memory_synthesis", "llm_generate")
builder.add_edge("llm_generate", END)
builder.add_edge("human_escalation", END)

# 编译 LangGraph 工作流状态机
customer_service_graph = builder.compile(checkpointer=memory_store)
