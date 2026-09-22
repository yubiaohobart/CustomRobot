export type SessionStatus = "AI_HANDLING" | "NEEDS_INTERVENTION" | "HUMAN_INTERVENED" | "RESOLVED";

export type MessageRole = "user" | "assistant" | "human_agent" | "system";

export interface KnowledgeDoc {
  id: string;
  title: string;
  category: "售后政策" | "账单发票" | "配送物流" | "账户安全" | "产品使用" | "VIP服务";
  content: string;
  tags: string[];
  updatedAt: string;
}

export interface SearchResult {
  doc: KnowledgeDoc;
  score: number;
  snippet: string;
}

export interface StepTraceItem {
  node: string;
  description: string;
  durationMs: number;
  status: "success" | "warning" | "error";
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
  stepTrace?: StepTraceItem[];
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

export interface CheckpointItem {
  id: string;
  timestamp: string;
  node: string;
  stateData: Record<string, any>;
}

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
  checkpoints: CheckpointItem[];
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

export interface MetricsData {
  totalSessions: number;
  needsIntervention: number;
  humanIntervened: number;
  aiHandling: number;
  totalTurns: number;
  avgLatencyMs: number;
  avgConfidence: number;
  humanInterventionRate: number;
  aiResolutionRate: number;
  sentimentCounts: {
    positive: number;
    neutral: number;
    negative: number;
    frustrated: number;
  };
  kbDocCount: number;
  timestamp: string;
}
