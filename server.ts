import express from "express";
import path from "path";
import dotenv from "dotenv";
import { createServer as createViteServer } from "vite";
import { vectorStore } from "./server/vectorStore.js";
import { memoryManager, ChatMessage } from "./server/memoryManager.js";
import { runCustomerServiceGraph } from "./server/langGraphEngine.js";
import { getGenAI } from "./server/gemini.js";

dotenv.config();

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(express.json());

  // CORS middleware for separate frontend and backend deployments
  app.use((req, res, next) => {
    res.header("Access-Control-Allow-Origin", "*");
    res.header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
    res.header("Access-Control-Allow-Headers", "Origin, X-Requested-With, Content-Type, Accept, Authorization");
    if (req.method === "OPTIONS") {
      return res.sendStatus(200);
    }
    next();
  });

  // ==================== REST API ENDPOINTS ====================

  // Health check
  app.get("/api/health", (req, res) => {
    res.json({ status: "ok", timestamp: new Date().toISOString() });
  });

  // 1. Customer Chat (LangGraph Pipeline)
  app.post("/api/chat", async (req, res) => {
    try {
      const { sessionId, message } = req.body;
      if (!sessionId || !message) {
        return res.status(400).json({ error: "sessionId and message are required" });
      }

      const result = await runCustomerServiceGraph(sessionId, message);
      const session = memoryManager.getSession(sessionId);

      res.json({
        ...result,
        session,
      });
    } catch (err: any) {
      console.error("Error in /api/chat:", err);
      res.status(500).json({ error: err.message || "Failed to process chat" });
    }
  });

  // 2. Sessions List
  app.get("/api/sessions", (req, res) => {
    const sessions = memoryManager.getAllSessions();
    res.json({ sessions });
  });

  // 3. Single Session Details
  app.get("/api/sessions/:id", (req, res) => {
    const session = memoryManager.getSession(req.params.id);
    if (!session) {
      return res.status(404).json({ error: "Session not found" });
    }
    res.json({ session });
  });

  // 4. Seamless Human Intervention Transfer (无缝人工转接接口)
  // Transfers full context (user questions, assistant replies, summary memory, customer profile)
  // to specified human agent, logs transfer event, and updates session state
  app.post("/api/sessions/:id/transfer", (req, res) => {
    try {
      const sessionId = req.params.id;
      const { targetAgentId, reason, triggerType, operatorNote } = req.body;
      const result = memoryManager.transferSession(
        sessionId,
        targetAgentId,
        reason,
        triggerType,
        operatorNote
      );
      res.json(result);
    } catch (err: any) {
      console.error("Error in /api/sessions/:id/transfer:", err);
      res.status(400).json({ error: err.message || "转接失败" });
    }
  });

  // 4b. Query Transfer Logs (转接审计日志接口)
  app.get("/api/transfer-logs", (req, res) => {
    const { sessionId, triggerType } = req.query;
    const logs = memoryManager.getTransferLogs(
      sessionId as string | undefined,
      triggerType as string | undefined
    );
    res.json({ logs, totalCount: logs.length });
  });

  // 4c. Query Available Specialized Human Agents (获取可选专属坐席列表)
  app.get("/api/agents", (req, res) => {
    const agents = memoryManager.getAvailableAgents();
    res.json({ agents });
  });

  // 4d. Human Intervention (Takeover / Handback)
  app.post("/api/sessions/:id/intervene", (req, res) => {
    const { action, agentName } = req.body; // action: 'takeover' | 'release'
    const sessionId = req.params.id;
    const session = memoryManager.getSession(sessionId);
    if (!session) {
      return res.status(404).json({ error: "Session not found" });
    }

    const timestamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

    if (action === "takeover") {
      const assigned = agentName || "人工客服专员 #108";
      memoryManager.updateSessionStatus(sessionId, "HUMAN_INTERVENED", assigned);
      
      const systemMsg: ChatMessage = {
        id: `sys-${Date.now()}`,
        role: "system",
        content: `【系统提示】${assigned} 已接入会话并接管，AI引擎已暂停自动应答。`,
        timestamp,
      };
      memoryManager.addMessage(sessionId, systemMsg);
      memoryManager.addCheckpoint(sessionId, "human_takeover_started", { agent: assigned });
    } else {
      memoryManager.updateSessionStatus(sessionId, "AI_HANDLING", undefined);
      const systemMsg: ChatMessage = {
        id: `sys-${Date.now()}`,
        role: "system",
        content: `【系统提示】人工服务已结束，会话已恢复至智能客服助手（LangGraph AI）接待。`,
        timestamp,
      };
      memoryManager.addMessage(sessionId, systemMsg);
      memoryManager.addCheckpoint(sessionId, "ai_handling_resumed", {});
    }

    res.json({ success: true, session: memoryManager.getSession(sessionId) });
  });

  // 5. Send Human Agent Message
  app.post("/api/sessions/:id/human-message", (req, res) => {
    const { content, agentName } = req.body;
    const sessionId = req.params.id;
    const session = memoryManager.getSession(sessionId);
    if (!session) {
      return res.status(404).json({ error: "Session not found" });
    }

    const timestamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    const msg: ChatMessage = {
      id: `msg-human-${Date.now()}`,
      role: "human_agent",
      content,
      timestamp,
    };
    memoryManager.addMessage(sessionId, msg);

    // Update memory summary
    const updatedSummary = `${session.summaryMemory} 人工坐席（${agentName || "客服"}）发送回应：${content.slice(0, 30)}...`;
    memoryManager.updateProfileAndMemory(sessionId, updatedSummary, {});

    res.json({ success: true, message: msg, session: memoryManager.getSession(sessionId) });
  });

  // 6. Clear Session
  app.post("/api/sessions/:id/clear", (req, res) => {
    memoryManager.clearSession(req.params.id);
    res.json({ success: true, session: memoryManager.getSession(req.params.id) });
  });

  // 7. Vector Knowledge Base CRUD
  app.get("/api/knowledge", (req, res) => {
    const docs = vectorStore.getAllDocs();
    res.json({ docs });
  });

  app.post("/api/knowledge", async (req, res) => {
    try {
      const { title, category, content, tags } = req.body;
      if (!title || !content) {
        return res.status(400).json({ error: "title and content are required" });
      }
      const newDoc = await vectorStore.addDoc({
        title,
        category: category || "产品使用",
        content,
        tags: tags || [],
      });
      res.json({ success: true, doc: newDoc });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  app.delete("/api/knowledge/:id", (req, res) => {
    const ok = vectorStore.deleteDoc(req.params.id);
    res.json({ success: ok });
  });

  // 8. Vector Search Testing
  app.post("/api/knowledge/search", async (req, res) => {
    try {
      const { query, topK, minScore } = req.body;
      const start = Date.now();
      const results = await vectorStore.search(query, topK || 3, minScore !== undefined ? minScore : 0.2);
      const latencyMs = Date.now() - start;
      res.json({ results, latencyMs, query });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  // 9. Real-time Monitoring & Observability Metrics
  app.get("/api/metrics", (req, res) => {
    const sessions = memoryManager.getAllSessions();
    const totalSessions = sessions.length;
    const needsIntervention = sessions.filter(s => s.status === "NEEDS_INTERVENTION").length;
    const humanIntervened = sessions.filter(s => s.status === "HUMAN_INTERVENED").length;
    const aiHandling = sessions.filter(s => s.status === "AI_HANDLING").length;

    let totalTurns = 0;
    let totalLatency = 0;
    let confidenceSum = 0;
    let scoredCount = 0;

    const sentimentCounts = {
      positive: 0,
      neutral: 0,
      negative: 0,
      frustrated: 0,
    };

    sessions.forEach(s => {
      totalTurns += s.metrics.totalTurns;
      totalLatency += s.metrics.avgLatencyMs;
      if (s.metrics.avgConfidence) {
        confidenceSum += s.metrics.avgConfidence;
        scoredCount++;
      }
      if (s.customerProfile?.sentiment) {
        sentimentCounts[s.customerProfile.sentiment] = (sentimentCounts[s.customerProfile.sentiment] || 0) + 1;
      }
    });

    const avgLatencyMs = totalSessions > 0 ? Math.round(totalLatency / totalSessions) : 360;
    const avgConfidence = scoredCount > 0 ? Number((confidenceSum / scoredCount).toFixed(2)) : 0.91;
    const humanInterventionRate = totalSessions > 0 ? Number(((needsIntervention + humanIntervened) / totalSessions * 100).toFixed(1)) : 0;
    const aiResolutionRate = totalSessions > 0 ? Number((aiHandling / totalSessions * 100).toFixed(1)) : 0;

    res.json({
      totalSessions,
      needsIntervention,
      humanIntervened,
      aiHandling,
      totalTurns,
      avgLatencyMs,
      avgConfidence,
      humanInterventionRate,
      aiResolutionRate,
      sentimentCounts,
      kbDocCount: vectorStore.getAllDocs().length,
      timestamp: new Date().toISOString(),
    });
  });

  // 10. AI Copilot Agent Suggestion
  app.post("/api/generate-suggestion", async (req, res) => {
    try {
      const { sessionId } = req.body;
      const session = memoryManager.getSession(sessionId);
      if (!session) {
        return res.status(404).json({ error: "Session not found" });
      }

      const lastUserMsg = [...session.messages].reverse().find(m => m.role === "user");
      const query = lastUserMsg ? lastUserMsg.content : "用户咨询";
      const searchResults = await vectorStore.search(query, 2, 0.3);

      let suggestion = "";
      if (process.env.GEMINI_API_KEY) {
        try {
          const ai = getGenAI();
          const prompt = `你是一名客服主管的AI辅助驾驶副手（Copilot）。
用户问题：${query}
会话历史背景：${session.summaryMemory}
知识库依据：${searchResults.map(s => s.doc.content).join("\n")}

请为人工客服坐席生成一条高质量、可以直接一键发送或稍作编辑后发送给用户的安抚/解决方案建议回复（语气极其专业、真诚、有解决问题的具体时效与动作）：`;

          const response = await ai.models.generateContent({
            model: "gemini-3.8-flash",
            contents: prompt,
            config: {
              temperature: 0.4,
            },
          });
          suggestion = response.text?.trim() || "";
        } catch (e) {
          // fallback
        }
      }

      if (!suggestion) {
        suggestion = searchResults.length > 0
          ? `您好！我是值班客服专员，我已详细核查了您的诉求。针对您反馈的情况，${searchResults[0].doc.content.slice(0, 80)}... 我现在已为您加急登记跟进，并将处理结果在15分钟内同步给您，请您放心！`
          : `您好！我是值班客服专员，已经为您全面介入跟进此问题。请稍等，我正在后台系统为您调取该笔订单与物流节点日志，预计2分钟内为您给出明确的解决方案。`;
      }

      res.json({
        suggestion,
        references: searchResults,
      });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  // ==================== VITE MIDDLEWARE / STATIC ====================
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`[IntelliServe] Server running on http://0.0.0.0:${PORT}`);
  });
}

startServer().catch((err) => {
  console.error("Failed to start server:", err);
});
