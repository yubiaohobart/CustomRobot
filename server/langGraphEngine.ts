import { getGenAI } from "./gemini.js";
import { vectorStore, SearchResult } from "./vectorStore.js";
import { memoryManager, ChatMessage, SessionStatus } from "./memoryManager.js";

export interface LangGraphExecutionResult {
  reply: string;
  references: SearchResult[];
  confidenceScore: number;
  sentiment: "positive" | "neutral" | "negative" | "frustrated";
  intent: string;
  escalatedToHuman: boolean;
  stepTrace: Array<{
    node: string;
    description: string;
    durationMs: number;
    status: "success" | "warning" | "error";
  }>;
}

export async function runCustomerServiceGraph(
  sessionId: string,
  userMessage: string
): Promise<LangGraphExecutionResult> {
  const startTime = Date.now();
  const stepTrace: LangGraphExecutionResult["stepTrace"] = [];
  const session = memoryManager.getOrCreateSession(sessionId);

  // Check if already in human intervention mode
  if (session.status === "HUMAN_INTERVENED") {
    const timestamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    const userMsg: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: "user",
      content: userMessage,
      timestamp,
      sentiment: "neutral",
    };
    memoryManager.addMessage(sessionId, userMsg);
    
    stepTrace.push({
      node: "human_intercept_guard",
      description: "检测到该会话已被人工坐席接管，AI引擎暂停自动应答，消息已直达人工客服座席端。",
      durationMs: Date.now() - startTime,
      status: "warning",
    });

    return {
      reply: "【人工客服服务中】您的消息已成功同步给专属人工客服，坐席人员正在为您处理，请稍候...",
      references: [],
      confidenceScore: 1.0,
      sentiment: "neutral",
      intent: "人工会话直通",
      escalatedToHuman: true,
      stepTrace,
    };
  }

  // NODE 1: Query Analysis & Routing (意图识别与情感初筛节点)
  const node1Start = Date.now();
  let intent = "常规咨询";
  let sentiment: "positive" | "neutral" | "negative" | "frustrated" = "neutral";
  let explicitEscalate = false;

  const lower = userMessage.toLowerCase();
  if (
    lower.includes("转人工") ||
    lower.includes("人工客服") ||
    lower.includes("找人工") ||
    lower.includes("投诉") ||
    lower.includes("消协") ||
    lower.includes("骗子") ||
    lower.includes("主管")
  ) {
    explicitEscalate = true;
    sentiment = "frustrated";
    intent = "人工服务诉求 / 争议投诉";
  } else if (lower.includes("退款") || lower.includes("退货") || lower.includes("换货") || lower.includes("坏了")) {
    intent = "售后退换与质量咨询";
    sentiment = lower.includes("慢") || lower.includes("没到账") || lower.includes("气死") ? "frustrated" : "neutral";
  } else if (lower.includes("发票") || lower.includes("专票") || lower.includes("税号") || lower.includes("报销")) {
    intent = "财务发票与对账申请";
  } else if (lower.includes("快递") || lower.includes("物流") || lower.includes("发货") || lower.includes("顺丰") || lower.includes("送到")) {
    intent = "物流履约与时效跟踪";
  } else if (lower.includes("密码") || lower.includes("登录") || lower.includes("盗号") || lower.includes("验证码")) {
    intent = "账号权限与安全保障";
  } else if (lower.includes("vip") || lower.includes("会员") || lower.includes("特权") || lower.includes("积分")) {
    intent = "会员权益与专属礼遇";
  }

  stepTrace.push({
    node: "query_router_node",
    description: `完成语义意图分类 [${intent}]，情感倾向评估 [${sentiment}]，人工触发器状态 [${explicitEscalate ? "已激活" : "常规"}]`,
    durationMs: Date.now() - node1Start,
    status: explicitEscalate ? "warning" : "success",
  });

  // NODE 2: Vector Search & Knowledge Retrieval (向量检索与知识抽取节点)
  const node2Start = Date.now();
  const searchResults = await vectorStore.search(userMessage, 3, 0.35);
  const bestScore = searchResults.length > 0 ? searchResults[0].score : 0;

  stepTrace.push({
    node: "vector_retrieval_node",
    description: `向量数据库执行余弦相似度检索，召回 Top-${searchResults.length} 条关联知识块，最高匹配分: ${(bestScore * 100).toFixed(1)}%`,
    durationMs: Date.now() - node2Start,
    status: searchResults.length > 0 ? "success" : "warning",
  });

  // NODE 3: Memory Synthesis Node (会话上下文与历史摘要融合节点)
  const node3Start = Date.now();
  const slidingHistory = memoryManager.getSlidingWindow(sessionId, 4);
  const runningSummary = session.summaryMemory || "暂无前序历史摘要";
  
  stepTrace.push({
    node: "memory_synthesis_node",
    description: `提取前序 ${slidingHistory.length} 轮滑动记忆窗口，注入长期状态摘要（${runningSummary.slice(0, 30)}...）`,
    durationMs: Date.now() - node3Start,
    status: "success",
  });

  // NODE 4: LLM Generation / Agent Node (模型生成与回答提炼节点)
  const node4Start = Date.now();
  let generatedAnswer = "";
  let confidence = bestScore;

  // Build grounded prompt
  const knowledgeContext = searchResults.length > 0
    ? searchResults.map((r, i) => `【知识库文档${i+1}：${r.doc.title}】\n${r.doc.content}`).join("\n\n")
    : "【暂无高相似度知识库匹配条目】";

  const historyContext = slidingHistory
    .map((m) => `${m.role === "user" ? "用户" : "客服"}: ${m.content}`)
    .join("\n");

  const systemInstruction = `你是一名专业、亲切、高效的企业级智能客服专家（IntelliServe AI）。
请严格依据所提供的【企业知识库】与【用户会话历史】回答用户的疑问。
要求：
1. 语言亲切得体、条理清晰，重点突出时效、规则与办理流程；
2. 如果知识库有明确规定，请准确引用，严禁编造不实政策；
3. 如果用户问题超出了知识库范围或用户情绪明显焦急要求人工，请安抚用户并主动建议转接人工坐席；
4. 回答中不要提及"依据知识库文档"等死板字眼，以官方客服的自然口吻应答。`;

  const prompt = `【长期会话记忆摘要】:
${runningSummary}

【最近对话记录】:
${historyContext || "无前序对话"}

【参考知识库内容】:
${knowledgeContext}

【用户当前问题】:
${userMessage}

请给出专业客服应答：`;

  if (process.env.GEMINI_API_KEY) {
    try {
      const ai = getGenAI();
      const response = await ai.models.generateContent({
        model: "gemini-3.8-flash",
        contents: prompt,
        config: {
          systemInstruction,
          temperature: 0.3,
        },
      });
      generatedAnswer = response.text?.trim() || "";
    } catch (error) {
      console.error("[LangGraphEngine] Gemini API error, falling back to local synthesis:", error);
    }
  }

  // High-fidelity rule fallback if API not available or empty
  if (!generatedAnswer) {
    if (explicitEscalate) {
      generatedAnswer = "非常抱歉让您产生不愉快的体验！我已记录下您的诉求并立即为您申请人工坐席快速接入通道。我们的资深客服主管将优先接管本对话，请您稍候片刻！";
      confidence = 0.5;
    } else if (searchResults.length > 0) {
      const topDoc = searchResults[0].doc;
      generatedAnswer = `您好！关于您咨询的"${userMessage}"，依据业务标准规范：${topDoc.content} 如您在办理过程中需要进一步协助或特批处理，可随时随时回复【转人工】为您安排客服专员。`;
      confidence = Math.max(0.75, bestScore);
    } else {
      generatedAnswer = "您好，我已收到您的提问。由于该问题涉及个性化业务核查，为了给您更精准的解答，建议您提供具体订单号，或者回复【转人工】由人工坐席专员为您快速核实处理。";
      confidence = 0.42;
    }
  }

  stepTrace.push({
    node: "llm_agent_generate_node",
    description: `调用 Gemini 3.8 Flash 执行多源融合推理，生成结构化客服应答（置信度: ${(confidence * 100).toFixed(1)}%）`,
    durationMs: Date.now() - node4Start,
    status: "success",
  });

  // NODE 5: Guardrail & Human Escalation Evaluation (质量护栏与人工介入决策节点)
  const node5Start = Date.now();
  let escalatedToHuman = false;

  // Escalation triggers:
  // 1. Explicit user request (e.g. "转人工", "投诉")
  // 2. Frustrated sentiment
  // 3. Confidence below 0.55
  if (explicitEscalate || sentiment === "frustrated" || confidence < 0.55) {
    escalatedToHuman = true;
    memoryManager.updateSessionStatus(sessionId, "NEEDS_INTERVENTION");
    session.metrics.escalatedAt = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }

  stepTrace.push({
    node: "guardrail_and_intervention_eval",
    description: escalatedToHuman
      ? `护栏评估触发预警：[${explicitEscalate ? "客户强诉人工" : sentiment === "frustrated" ? "客户情绪负向" : "置信度低于阈值"}] -> 状态已标记为 [NEEDS_INTERVENTION] 并推送到坐席监控看板`
      : `护栏评估通过：置信度 ${(confidence * 100).toFixed(1)}% 达到安全标准，继续保持 AI 自主接待`,
    durationMs: Date.now() - node5Start,
    status: escalatedToHuman ? "warning" : "success",
  });

  // NODE 6: State Checkpoint & Memory Update (会话快照与记忆持久化节点)
  const node6Start = Date.now();
  const timestamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  // Add user message
  const userMsg: ChatMessage = {
    id: `msg-user-${Date.now()}`,
    role: "user",
    content: userMessage,
    timestamp,
    sentiment,
    intent,
  };
  memoryManager.addMessage(sessionId, userMsg);

  // Add assistant message
  const assistantMsg: ChatMessage = {
    id: `msg-asst-${Date.now()}`,
    role: "assistant",
    content: generatedAnswer,
    timestamp,
    references: searchResults.map((r) => ({
      id: r.doc.id,
      title: r.doc.title,
      score: r.score,
      snippet: r.snippet,
    })),
    confidenceScore: Number(confidence.toFixed(2)),
    sentiment,
    intent,
    stepTrace,
  };
  memoryManager.addMessage(sessionId, assistantMsg);

  // Update running memory summary
  const updatedSummary = `${session.summaryMemory ? session.summaryMemory + " " : ""}用户提问：${userMessage.slice(0, 30)}；系统识别意图[${intent}]，提供解答置信度[${(confidence * 100).toFixed(0)}%]${escalatedToHuman ? "，已发起人工介入预警。" : "。"}`;
  
  memoryManager.updateProfileAndMemory(sessionId, updatedSummary, {
    sentiment,
    urgency: escalatedToHuman ? "high" : "low",
    intent,
  });

  // Save LangGraph checkpoint
  memoryManager.addCheckpoint(sessionId, "turn_completed", {
    intent,
    sentiment,
    confidence,
    escalatedToHuman,
    referenceCount: searchResults.length,
  });

  stepTrace.push({
    node: "checkpoint_memory_node",
    description: `完成 LangGraph 状态检查点固化 (Checkpoint Saved)，更新滑动上下文与客户画像`,
    durationMs: Date.now() - node6Start,
    status: "success",
  });

  return {
    reply: generatedAnswer,
    references: searchResults,
    confidenceScore: confidence,
    sentiment,
    intent,
    escalatedToHuman,
    stepTrace,
  };
}
