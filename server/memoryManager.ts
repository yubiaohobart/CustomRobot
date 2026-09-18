export type SessionStatus = "AI_HANDLING" | "NEEDS_INTERVENTION" | "HUMAN_INTERVENED" | "RESOLVED";

export type MessageRole = "user" | "assistant" | "human_agent" | "system";

export type TransferTriggerType = 
  | "ai_fallback"        // 智能客服无法回答 / 置信度不足
  | "user_requested"      // 用户主动要求转人工
  | "sentiment_alert"    // 情绪负向/急躁预警
  | "manual_dispatch";   // 坐席主动调度/改派

export interface TransferContextSnapshot {
  sessionId: string;
  customerName: string;
  vipLevel: string;
  userMessagesCount: number;
  aiMessagesCount: number;
  totalTurns: number;
  userQuestions: string[];
  lastUserQuestion: string;
  lastAiResponse?: string;
  summaryMemory: string;
  sentiment: string;
  intent: string;
  urgency: string;
  orderId?: string;
  confidenceScore?: number;
  topReferences?: Array<{ id: string; title: string; score: number; snippet: string }>;
  fullConversationSnapshot: Array<{
    id: string;
    role: MessageRole;
    content: string;
    timestamp: string;
  }>;
}

export interface TransferLog {
  id: string;
  sessionId: string;
  triggerType: TransferTriggerType;
  reason: string;
  assignedAgentId: string;
  assignedAgentName: string;
  assignedDepartment: string;
  customerName: string;
  vipLevel: string;
  status: "SUCCESS" | "TRANSFERRED" | "CANCELLED";
  transferredAt: string;
  contextSnapshot: TransferContextSnapshot;
  operatorNote?: string;
}

export interface AvailableAgent {
  id: string;
  name: string;
  department: string;
  title: string;
  avatar?: string;
  status: "IDLE" | "BUSY" | "OFFLINE";
  currentWorkload: number;
  rating: number;
  specialties: string[];
  recommendedFor?: string[];
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  references?: Array<{
    id: string;
    title: string;
    score: number;
    snippet: string;
  }>;
  confidenceScore?: number;
  sentiment?: "positive" | "neutral" | "negative" | "frustrated";
  intent?: string;
  stepTrace?: Array<{
    node: string;
    description: string;
    durationMs: number;
    status: "success" | "warning" | "error";
  }>;
}

export interface CustomerProfile {
  name: string;
  phone?: string;
  vipLevel: "普通会员" | "黄金会员" | "钻石会员";
  sentiment: "positive" | "neutral" | "negative" | "frustrated";
  urgency: "low" | "medium" | "high";
  intent: string;
  tags: string[];
  orderId?: string;
}

export interface ConversationSession {
  id: string;
  userName: string;
  status: SessionStatus;
  assignedAgent?: string;
  assignedAgentId?: string;
  transferLogs?: TransferLog[];
  latestTransfer?: TransferLog;
  messages: ChatMessage[];
  summaryMemory: string;
  customerProfile: CustomerProfile;
  checkpoints: Array<{
    id: string;
    timestamp: string;
    node: string;
    stateData: Record<string, any>;
  }>;
  metrics: {
    totalTurns: number;
    avgLatencyMs: number;
    avgConfidence: number;
    escalatedAt?: string;
  };
  unreadForAgent: boolean;
  createdAt: string;
  updatedAt: string;
}

class MemoryManager {
  private sessions: Map<string, ConversationSession> = new Map();
  private transferLogs: TransferLog[] = [];
  private availableAgents: AvailableAgent[] = [
    {
      id: "agent_108",
      name: "陈主管",
      title: "资深客户体验经理",
      department: "VIP及疑难客诉部",
      status: "IDLE",
      currentWorkload: 1,
      rating: 4.98,
      specialties: ["钻石VIP专属关怀", "退款及赔付特批", "危机争议化解", "高急迫工单"],
      recommendedFor: ["售后退款", "投诉", "钻石会员"],
    },
    {
      id: "agent_102",
      name: "李雪",
      title: "高级售后专员",
      department: "售后履约服务部",
      status: "IDLE",
      currentWorkload: 0,
      rating: 4.92,
      specialties: ["7天无理由退货", "仓库质检争议", "顺丰物流赔偿", "退运费险核销"],
      recommendedFor: ["退货质检", "换货进度", "物流异常"],
    },
    {
      id: "agent_105",
      name: "赵林",
      title: "财务与账单专家",
      department: "财务支持部",
      status: "BUSY",
      currentWorkload: 2,
      rating: 4.88,
      specialties: ["增值税专票重开", "退款原路对账", "企业报销核算", "合同款项冲抵"],
      recommendedFor: ["发票申请", "专票核验", "对账单"],
    },
    {
      id: "agent_110",
      name: "孙浩",
      title: "安全与技术顾问",
      department: "平台安全运营部",
      status: "IDLE",
      currentWorkload: 0,
      rating: 4.95,
      specialties: ["账号密码紧急找回", "异地风控解冻", "手机解绑核验", "企业子账号授权"],
      recommendedFor: ["密码找回", "账号安全", "登录异常"],
    },
  ];

  constructor() {
    this.seedDefaultSessions();
  }

  private seedDefaultSessions() {
    const now = new Date();
    const timeStr = (minsAgo: number) => {
      const d = new Date(now.getTime() - minsAgo * 60 * 1000);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    };

    // Pre-seed Session 1: Needs intervention due to customer frustration over refund
    const s1: ConversationSession = {
      id: "session_user_001",
      userName: "王女士 (钻石VIP)",
      status: "NEEDS_INTERVENTION",
      messages: [
        {
          id: "m1_1",
          role: "user",
          content: "你好，我的订单 20260912-7890 申请退货已经过去4天了，为什么款项还没到账？",
          timestamp: timeStr(18),
          sentiment: "neutral",
          intent: "退款进度咨询",
        },
        {
          id: "m1_2",
          role: "assistant",
          content: "您好王女士！根据售后政策，商品仓库收件质检无误后48小时内原路退款至原支付渠道。请问您的退货包裹物流是否显示已签收呢？",
          timestamp: timeStr(17),
          confidenceScore: 0.92,
          references: [{ id: "kb-001", title: "7天无理由退货与退款办理细则", score: 0.94, snippet: "自用户签收商品之日起7日内..." }],
        },
        {
          id: "m1_3",
          role: "user",
          content: "顺丰早就签收两天了！你们仓库质检怎么这么慢？我今天必须拿到退款，不然找消费者协会投诉了！麻烦立即给我转人工！",
          timestamp: timeStr(3),
          sentiment: "frustrated",
          intent: "催款投诉 / 强转人工",
        },
        {
          id: "m1_4",
          role: "assistant",
          content: "非常理解您的焦急心情，给您带来不便深表歉意！检测到您是尊贵的钻石VIP会员且遇到退款阻滞，系统已为您触发最高优先级人工坐席通道，正在接驳专属客户经理...",
          timestamp: timeStr(3),
          confidenceScore: 0.48,
        }
      ],
      summaryMemory: "用户为钻石VIP王女士，咨询订单20260912-7890退款时效。顺丰物流显示已妥投仓库2天但款项未到账。用户情绪较激动，有投诉意向并明确要求转人工，已挂起转接队列等待接管。",
      customerProfile: {
        name: "王女士",
        phone: "138****6688",
        vipLevel: "钻石会员",
        sentiment: "frustrated",
        urgency: "high",
        intent: "售后退款延迟催办 / 转人工",
        tags: ["钻石VIP", "订单退货", "高危机预警", "质检延迟"],
        orderId: "20260912-7890",
      },
      checkpoints: [
        { id: "cp-001", timestamp: timeStr(3), node: "guardrail_eval", stateData: { escalationTriggered: true, reason: "Customer angry sentiment + keyword '转人工'" } }
      ],
      metrics: {
        totalTurns: 2,
        avgLatencyMs: 380,
        avgConfidence: 0.70,
        escalatedAt: timeStr(3),
      },
      unreadForAgent: true,
      createdAt: timeStr(20),
      updatedAt: timeStr(3),
    };

    // Pre-seed Session 2: Active AI handling on invoice question
    const s2: ConversationSession = {
      id: "session_user_002",
      userName: "张先生 (普通会员)",
      status: "AI_HANDLING",
      messages: [
        {
          id: "m2_1",
          role: "user",
          content: "公司采购需要开具增值税专用发票，请问需要提供哪些材料？大概几天能收到？",
          timestamp: timeStr(8),
          sentiment: "neutral",
          intent: "增值税发票办理",
        },
        {
          id: "m2_2",
          role: "assistant",
          content: "您好！企业增值税专用发票开具指南如下：确认收货后在【我的订单】-【申请开票】提交公司全称、纳税人识别号、开户行名称及账号、注册地址和电话。审核通过后3个工作日内由顺丰免费寄出专票。如只需普通电子发票，提交后1-2小时内直发您的邮箱。",
          timestamp: timeStr(8),
          confidenceScore: 0.96,
          references: [{ id: "kb-002", title: "电子发票与增值税专用发票申请指南", score: 0.95, snippet: "订单确认收货后，可在【我的订单】-【申请开票】中选择..." }],
        }
      ],
      summaryMemory: "张先生咨询企业增值税专用发票开具所需资质信息及寄送时效。AI已依据知识库精确回复专票3个工作日寄出及所需材料。",
      customerProfile: {
        name: "张先生",
        phone: "186****1234",
        vipLevel: "普通会员",
        sentiment: "positive",
        urgency: "low",
        intent: "增值税专票申请",
        tags: ["企业采购", "开票报销", "解答满意"],
      },
      checkpoints: [
        { id: "cp-002", timestamp: timeStr(8), node: "agent_generate", stateData: { ragSuccess: true } }
      ],
      metrics: {
        totalTurns: 1,
        avgLatencyMs: 420,
        avgConfidence: 0.96,
      },
      unreadForAgent: false,
      createdAt: timeStr(10),
      updatedAt: timeStr(8),
    };

    // Pre-seed Session 3: Human already intervened and serving
    const s3: ConversationSession = {
      id: "session_user_003",
      userName: "刘总 (黄金会员)",
      status: "HUMAN_INTERVENED",
      assignedAgent: "坐席 #105 - 赵主管",
      messages: [
        {
          id: "m3_1",
          role: "user",
          content: "我们定制的服务器机箱配件物流卡在转运中心2天了，工程下周一就要上线，能协调加急吗？",
          timestamp: timeStr(35),
          sentiment: "neutral",
          intent: "关键物流加急",
        },
        {
          id: "m3_2",
          role: "assistant",
          content: "已为您查询物流信息。检测到该批次包含大宗工程定制件，正在为您接通物流大客户专项座席。",
          timestamp: timeStr(34),
          confidenceScore: 0.82,
        },
        {
          id: "m3_3",
          role: "human_agent",
          content: "刘总您好，我是专属大客户值班主管赵经理。我已经直接联系了顺丰区域转运主管，为您开辟了红标特快通道，预计今晚21:00前完成清点并直接派送专车配送，保证不耽误周一上线！",
          timestamp: timeStr(25),
        },
        {
          id: "m3_4",
          role: "user",
          content: "太感谢了！专车单号发我一下，我让库管准备接货。",
          timestamp: timeStr(15),
          sentiment: "positive",
        }
      ],
      summaryMemory: "黄金会员刘总因定制工程机箱物流转运滞留紧急求助。人工坐席赵主管介入，协调顺丰特快专车加急派送，用户高度满意。",
      customerProfile: {
        name: "刘总",
        phone: "159****9988",
        vipLevel: "黄金会员",
        sentiment: "positive",
        urgency: "high",
        intent: "大宗物流专车加急",
        tags: ["大客户", "加急专配", "人工跟进中"],
        orderId: "ENG-2026-9081",
      },
      checkpoints: [
        { id: "cp-003", timestamp: timeStr(25), node: "human_takeover", stateData: { agent: "坐席 #105 - 赵主管" } }
      ],
      metrics: {
        totalTurns: 3,
        avgLatencyMs: 310,
        avgConfidence: 0.88,
        escalatedAt: timeStr(34),
      },
      unreadForAgent: false,
      createdAt: timeStr(40),
      updatedAt: timeStr(15),
    };

    // Seed historical transfer log for s3
    const seedLog: TransferLog = {
      id: `TRF-${Date.now().toString().slice(-6)}-101`,
      sessionId: s3.id,
      triggerType: "user_requested",
      reason: "客户咨询大宗订单专车配送并明确要求人工主管特批",
      assignedAgentId: "agent_105",
      assignedAgentName: "赵林",
      assignedDepartment: "财务与高端客户专席",
      customerName: s3.userName,
      vipLevel: s3.customerProfile.vipLevel,
      status: "SUCCESS",
      transferredAt: timeStr(25),
      operatorNote: "客户有50台服务器加急需求，已协调专车调运。",
      contextSnapshot: {
        sessionId: s3.id,
        customerName: s3.userName,
        vipLevel: s3.customerProfile.vipLevel,
        userMessagesCount: 2,
        aiMessagesCount: 1,
        totalTurns: 3,
        userQuestions: [
          "我们公司订购了50台高性能服务器，要求本周五前通过专属冷链专车送达深圳机房，目前订单显示普快，请帮我特批专线！",
        ],
        lastUserQuestion: "我们公司订购了50台高性能服务器，要求本周五前通过专属冷链专车送达深圳机房，目前订单显示普快，请帮我特批专线！",
        lastAiResponse: "大宗企业客户专享冷链及专车调度需经由专属客户经理发起仓储特批工单...",
        summaryMemory: s3.summaryMemory,
        sentiment: s3.customerProfile.sentiment,
        intent: s3.customerProfile.intent,
        urgency: s3.customerProfile.urgency,
        orderId: s3.customerProfile.orderId,
        confidenceScore: 0.88,
        fullConversationSnapshot: s3.messages.map(m => ({
          id: m.id,
          role: m.role,
          content: m.content,
          timestamp: m.timestamp,
        })),
      },
    };
    s3.latestTransfer = seedLog;
    s3.transferLogs = [seedLog];
    this.transferLogs.push(seedLog);

    this.sessions.set(s1.id, s1);
    this.sessions.set(s2.id, s2);
    this.sessions.set(s3.id, s3);
  }

  public getSession(id: string): ConversationSession | undefined {
    return this.sessions.get(id);
  }

  public getAllSessions(): ConversationSession[] {
    return Array.from(this.sessions.values()).sort((a, b) => {
      // Prioritize NEEDS_INTERVENTION
      if (a.status === "NEEDS_INTERVENTION" && b.status !== "NEEDS_INTERVENTION") return -1;
      if (b.status === "NEEDS_INTERVENTION" && a.status !== "NEEDS_INTERVENTION") return 1;
      return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
    });
  }

  public getOrCreateSession(id: string, userName: string = "访客客户"): ConversationSession {
    let session = this.sessions.get(id);
    if (!session) {
      const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      session = {
        id,
        userName,
        status: "AI_HANDLING",
        messages: [],
        summaryMemory: "新会话建立，等待客户首句提问。",
        customerProfile: {
          name: userName,
          vipLevel: "普通会员",
          sentiment: "neutral",
          urgency: "low",
          intent: "初次咨询",
          tags: ["新访客", "智能解答中"],
        },
        checkpoints: [],
        metrics: {
          totalTurns: 0,
          avgLatencyMs: 0,
          avgConfidence: 1.0,
        },
        unreadForAgent: false,
        createdAt: now,
        updatedAt: now,
      };
      this.sessions.set(id, session);
    }
    return session;
  }

  public addMessage(sessionId: string, message: ChatMessage): ConversationSession {
    const session = this.getOrCreateSession(sessionId);
    session.messages.push(message);
    session.updatedAt = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    
    if (message.role === "user") {
      session.metrics.totalTurns += 1;
      if (session.status === "NEEDS_INTERVENTION" || session.status === "HUMAN_INTERVENED") {
        session.unreadForAgent = true;
      }
    }
    return session;
  }

  public updateSessionStatus(sessionId: string, status: SessionStatus, assignedAgent?: string): ConversationSession | undefined {
    const session = this.sessions.get(sessionId);
    if (!session) return undefined;
    session.status = status;
    if (assignedAgent !== undefined) {
      session.assignedAgent = assignedAgent;
    }
    if (status === "HUMAN_INTERVENED") {
      session.unreadForAgent = false;
    }
    session.updatedAt = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    return session;
  }

  public updateProfileAndMemory(sessionId: string, summary: string, profilePartial: Partial<CustomerProfile>) {
    const session = this.sessions.get(sessionId);
    if (!session) return;
    if (summary) session.summaryMemory = summary;
    if (profilePartial) {
      session.customerProfile = {
        ...session.customerProfile,
        ...profilePartial,
      };
    }
  }

  public addCheckpoint(sessionId: string, node: string, stateData: Record<string, any>) {
    const session = this.sessions.get(sessionId);
    if (!session) return;
    const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    session.checkpoints.push({
      id: `cp-${Date.now()}`,
      timestamp: now,
      node,
      stateData,
    });
  }

  public getSlidingWindow(sessionId: string, windowSize: number = 6): ChatMessage[] {
    const session = this.sessions.get(sessionId);
    if (!session) return [];
    return session.messages.slice(-windowSize);
  }

  public getAvailableAgents(): AvailableAgent[] {
    return this.availableAgents;
  }

  public getTransferLogs(sessionId?: string, triggerType?: string): TransferLog[] {
    return this.transferLogs.filter((log) => {
      if (sessionId && log.sessionId !== sessionId) return false;
      if (triggerType && log.triggerType !== triggerType) return false;
      return true;
    });
  }

  /**
   * Seamless Human Transfer Method (无缝人工介入接口)
   * Packages full context: user questions, assistant responses, summary memory, customer profile
   * Assigns to designated human agent, creates audit log, and notifies chat stream
   */
  public transferSession(
    sessionId: string,
    targetAgentId?: string,
    reason?: string,
    triggerType: TransferTriggerType = "user_requested",
    operatorNote?: string
  ): { success: boolean; transferLog: TransferLog; session: ConversationSession } {
    const session = this.getSession(sessionId);
    if (!session) {
      throw new Error(`会话 [${sessionId}] 不存在，无法执行人工转接`);
    }

    // Match designated agent or fallback
    const agent = this.availableAgents.find(a => a.id === targetAgentId) || this.availableAgents[0];
    const timestamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

    // Assemble complete conversation context package
    const userQuestions = session.messages.filter(m => m.role === "user").map(m => m.content);
    const lastUserMsg = [...session.messages].reverse().find(m => m.role === "user");
    const lastAiMsg = [...session.messages].reverse().find(m => m.role === "assistant");
    const fallbackReason = reason || (triggerType === "ai_fallback" ? "智能客服检索置信度不足，无法准确回答" : "客户主动申请转接专属人工客服");

    const contextSnapshot: TransferContextSnapshot = {
      sessionId: session.id,
      customerName: session.userName,
      vipLevel: session.customerProfile.vipLevel,
      userMessagesCount: userQuestions.length,
      aiMessagesCount: session.messages.filter(m => m.role === "assistant").length,
      totalTurns: session.metrics.totalTurns,
      userQuestions,
      lastUserQuestion: lastUserMsg ? lastUserMsg.content : "无历史提问",
      lastAiResponse: lastAiMsg ? lastAiMsg.content : undefined,
      summaryMemory: session.summaryMemory || "暂无前序长期记忆",
      sentiment: session.customerProfile.sentiment,
      intent: session.customerProfile.intent,
      urgency: session.customerProfile.urgency,
      orderId: session.customerProfile.orderId,
      confidenceScore: lastAiMsg?.confidenceScore,
      topReferences: lastAiMsg?.references,
      fullConversationSnapshot: session.messages.map(m => ({
        id: m.id,
        role: m.role,
        content: m.content,
        timestamp: m.timestamp,
      })),
    };

    const transferLogId = `TRF-${Date.now().toString().slice(-6)}-${Math.floor(Math.random() * 899 + 100)}`;
    const transferLog: TransferLog = {
      id: transferLogId,
      sessionId: session.id,
      triggerType,
      reason: fallbackReason,
      assignedAgentId: agent.id,
      assignedAgentName: agent.name,
      assignedDepartment: agent.department,
      customerName: session.userName,
      vipLevel: session.customerProfile.vipLevel,
      status: "SUCCESS",
      transferredAt: timestamp,
      contextSnapshot,
      operatorNote,
    };

    // Update session state
    session.status = "HUMAN_INTERVENED";
    session.assignedAgent = `${agent.department} · ${agent.name} (${agent.title})`;
    session.assignedAgentId = agent.id;
    session.latestTransfer = transferLog;
    if (!session.transferLogs) session.transferLogs = [];
    session.transferLogs.unshift(transferLog);
    this.transferLogs.unshift(transferLog);

    // Inject system transfer announcement in customer stream
    const systemNotice: ChatMessage = {
      id: `sys-transfer-${Date.now()}`,
      role: "system",
      content: `【无缝人工转接成功】会话已分配至人工客服【${agent.department} · ${agent.name}】。已完整同步历史对话(${userQuestions.length}轮提问)及会话长期记忆，客服人员正在查阅历史背景，无需重复描述！`,
      timestamp,
    };
    session.messages.push(systemNotice);
    session.unreadForAgent = true;
    session.updatedAt = timestamp;

    // Checkpoint
    this.addCheckpoint(sessionId, "seamless_human_transfer_node", {
      transferLogId,
      assignedAgent: agent.name,
      assignedDepartment: agent.department,
      triggerType,
      reason: fallbackReason,
      contextTurnCount: userQuestions.length,
      snapshotUserQuestions: userQuestions.slice(-3),
    });

    return {
      success: true,
      transferLog,
      session,
    };
  }

  public clearSession(sessionId: string) {
    const session = this.sessions.get(sessionId);
    if (session) {
      session.messages = [];
      session.summaryMemory = "会话已重置清空。";
      session.status = "AI_HANDLING";
      session.assignedAgent = undefined;
      session.checkpoints = [];
      session.unreadForAgent = false;
    }
  }
}

export const memoryManager = new MemoryManager();
