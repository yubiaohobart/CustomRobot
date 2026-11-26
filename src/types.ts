export type SessionStatus = "AI_HANDLING" | "NEEDS_INTERVENTION" | "HUMAN_INTERVENED" | "RESOLVED";

export type MessageRole = "user" | "assistant" | "human_agent" | "system";

export interface KnowledgeDoc {
  id: string;
  title: string;
  category: string;
  content: string;
  tags: string[];
  source?: string;
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

export interface OrderItem {
  skuId: string;
  title: string;
  category: string;
  spec: string;
  price: number;
  quantity: number;
  imageUrl?: string;
  isSpecialProduct?: boolean;
  isCustomized?: boolean;
}

export interface TrackingEvent {
  time: string;
  status: string;
  context: string;
}

export interface OrderExpress {
  company: string;
  companyCode?: string;
  trackingNumber: string;
  status: "DELIVERED" | "IN_TRANSIT" | "WAREHOUSE_RECEIVED" | "PENDING_PICKUP";
  statusDescription: string;
  timeline: TrackingEvent[];
}

export interface OrderAfterSales {
  canReturn7Days: boolean;
  returnDaysRemaining: number;
  signedDays: number;
  returnPolicy: string;
  shippingSubsidy: string;
  warrantyStatus: string;
  warrantyExpiredDate: string;
  warrantyPolicy: string;
  refundStatus?: "NONE" | "AUTO_REFUNDED" | "PENDING_HUMAN_AUDIT" | "AUDIT_APPROVED" | "AUDIT_REJECTED";
  refundAmount?: number;
  refundReason?: string;
  requiresHumanAudit?: boolean;
  auditOperator?: string;
  auditTime?: string;
  auditNote?: string;
}

export interface OrderData {
  orderId: string;
  orderSn: string;
  userId: string;
  userName: string;
  userPhone: string;
  vipLevel: string;
  status: "DELIVERED" | "IN_TRANSIT" | "RETURNING_INSPECTION" | "COMPLETED" | "PENDING_PAYMENT" | "REFUND_PENDING_AUDIT" | "REFUNDED" | string;
  statusText: string;
  statusCode?: number;
  createTime: string;
  payTime?: string;
  shipTime?: string;
  deliveryTime?: string | null;
  items: OrderItem[];
  totalAmount: number;
  paidAmount: number;
  shippingFee: number;
  express: OrderExpress;
  receiver: {
    name: string;
    phone: string;
    address: string;
  };
  afterSales: OrderAfterSales;
}

export interface MessageAiMeta {
  confidenceScore?: number;
  references?: Array<{
    id: string;
    title: string;
    score: number;
    snippet: string;
  }>;
  stepTrace?: StepTraceItem[];
}

export type MessageCard =
  | {
      type: "order";
      order: OrderData;
    }
  | {
      type: "refund_confirm";
      orderId: string;
      outRefundNo: string;
      paidAmount?: number;
    };

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  senderName?: string;
  aiMeta?: MessageAiMeta;
  card?: MessageCard;
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

export interface CustomerRecord {
  id: string;
  name: string;
  phone?: string;
  vipLevel: "普通会员" | "黄金会员" | "钻石会员";
  sentiment: "positive" | "neutral" | "negative" | "frustrated";
  urgency: string;
  intent: string;
  tags: string[];
  orderId?: string;
  avatar?: string;
  registeredDate?: string;
  totalOrdersCount?: number;
  totalSpent?: number;
  shippingAddress?: string;
  updatedAt?: string;
}

export interface StorageTableInfo {
  tableName: string;
  count: number;
  primaryKey: string;
  model?: string;
}

export interface StorageStatus {
  storageType: string;
  orm?: string;
  databaseUrlTarget?: string;
  databaseDialect?: string;
  poolConfig?: {
    poolSize: number;
    maxOverflow: number;
    prePing: boolean;
  };
  tables?: {
    orders: StorageTableInfo;
    customers: StorageTableInfo;
    agents: StorageTableInfo;
    sessions: StorageTableInfo;
    transferLogs: StorageTableInfo;
  };
  lastQueryAt?: string;
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
  contextSnapshot?: TransferContextSnapshot;
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
  assignedAgent?: string | null;
  assignedAgentId?: string | null;
  latestTransfer?: TransferLog | null;
  messages: ChatMessage[];
  summaryMemory: string;
  customerProfile: CustomerProfile;
  metrics: {
    totalTurns: number;
    avgLatencyMs: number;
    avgConfidence: number;
    escalatedAt?: string | null;
  };
  createdAt: string;
  updatedAt: string;
}

export interface SessionPatch {
  status: SessionStatus;
  assignedAgent?: string | null;
  assignedAgentId?: string | null;
  intent?: string;
  sentiment?: CustomerProfile["sentiment"] | string;
  summaryMemory?: string;
}

export type WsRole = "customer" | "agent" | "dual_observer" | "supervisor";

export interface WsEnvelope<TType extends string, TData> {
  type: TType;
  sessionId?: string;
  timestamp: string;
  data: TData;
}

export type SessionUpdateAction = "message" | "transfer" | "takeover" | "release" | "clear" | string;
export type OrderUpdateAction = "refund" | "audit" | "reset" | "status" | "chat_refund" | string;

export interface WsTransferSummary {
  id: string;
  triggerType: TransferTriggerType;
  reason: string;
  assignedDepartment: string;
  status: TransferLog["status"];
  transferredAt: string;
  operatorNote?: string;
}

export interface SessionUpdateData {
  action: SessionUpdateAction;
  sessionPatch: SessionPatch | null;
  message?: ChatMessage;
  latestTransfer?: WsTransferSummary | null;
}

export interface OrderUpdateData {
  orderId: string;
  action: OrderUpdateAction;
  order: OrderData;
}

export type WsClientEvent =
  | {
      type: "join";
      sessionId: string;
      data: {
        role: WsRole;
        name?: string;
      };
    }
  | {
      type: "typing";
      sessionId?: string;
      data: {
        isTyping: boolean;
        role?: "customer" | "agent";
        name?: string;
      };
    }
  | {
      type: "ping";
      data?: Record<string, never>;
    };

export type WsServerEvent =
  | WsEnvelope<"joined", { role: WsRole; name: string }>
  | WsEnvelope<"pong", Record<string, never>>
  | WsEnvelope<"typing", { role: "customer" | "agent" | string; name?: string; isTyping: boolean }>
  | WsEnvelope<"session:update", SessionUpdateData>
  | WsEnvelope<"order:update", OrderUpdateData>;

export interface MetricsData {
  totalSessions: number;
  needsIntervention: number;
  humanIntervened: number;
  aiHandling: number;
  totalTurns: number;
  totalMessages?: number;
  avgLatencyMs: number;
  avgConfidence: number;
  humanInterventionRate: number;
  aiResolutionRate: number;
  aiResolvedRate?: string;
  sentimentCounts: {
    positive: number;
    neutral: number;
    negative: number;
    frustrated: number;
  };
  kbDocCount: number;
  timestamp: string;
  llmModel?: string;
  embeddingModel?: string;
  vectorDatabase?: string;
}
