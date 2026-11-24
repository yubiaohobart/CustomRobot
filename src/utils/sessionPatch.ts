import { ChatMessage, ConversationSession, SessionPatch, TransferLog, WsTransferSummary } from "../types";

/**
 * 将后端推送的轻量增量 SessionPatch 安全合并到本地完整会话对象中，
 * 避免覆盖静态客户画像字段与历史统计指标。
 */
function mergeLatestTransfer(
  prev: ConversationSession,
  incoming: WsTransferSummary | TransferLog | null | undefined,
  patch?: SessionPatch | null
): TransferLog | null | undefined {
  if (incoming === undefined) return prev.latestTransfer;
  if (incoming === null) return null;

  const fullIncoming = incoming as Partial<TransferLog>;
  const prevSameTransfer =
    prev.latestTransfer && prev.latestTransfer.id === fullIncoming.id ? prev.latestTransfer : undefined;

  return {
    ...(prevSameTransfer ?? {}),
    ...fullIncoming,
    sessionId: fullIncoming.sessionId ?? prev.id,
    customerName: fullIncoming.customerName ?? (prev.customerProfile?.name || prev.userName || "客户"),
    vipLevel: fullIncoming.vipLevel ?? (prev.customerProfile?.vipLevel || "普通会员"),
    assignedAgentId: fullIncoming.assignedAgentId ?? patch?.assignedAgentId ?? prev.assignedAgentId ?? "",
    assignedAgentName: fullIncoming.assignedAgentName ?? patch?.assignedAgent ?? prev.assignedAgent ?? "",
  } as TransferLog;
}

export function applySessionPatch(
  prev: ConversationSession,
  patch?: SessionPatch | null,
  nextMessages?: ChatMessage[],
  extras?: {
    latestTransfer?: WsTransferSummary | TransferLog | null;
    updatedAt?: string;
  }
): ConversationSession {
  const messages = nextMessages ?? prev.messages;
  const nextLatestTransfer = mergeLatestTransfer(prev, extras?.latestTransfer, patch);
  const nextUpdatedAt = extras?.updatedAt ?? prev.updatedAt;

  if (!patch) {
    if (!nextMessages && extras?.latestTransfer === undefined && !extras?.updatedAt) {
      return prev;
    }
    return {
      ...prev,
      messages,
      latestTransfer: nextLatestTransfer,
      updatedAt: nextUpdatedAt,
      metrics: {
        ...prev.metrics,
        totalTurns: messages.length,
      },
    };
  }

  const nextProfile =
    patch.intent !== undefined || patch.sentiment !== undefined
      ? {
          ...prev.customerProfile,
          ...(patch.intent !== undefined ? { intent: patch.intent } : {}),
          ...(patch.sentiment !== undefined
            ? { sentiment: patch.sentiment as ConversationSession["customerProfile"]["sentiment"] }
            : {}),
        }
      : prev.customerProfile;

  return {
    ...prev,
    status: patch.status ?? prev.status,
    assignedAgent: patch.assignedAgent !== undefined ? patch.assignedAgent : prev.assignedAgent,
    assignedAgentId: patch.assignedAgentId !== undefined ? patch.assignedAgentId : prev.assignedAgentId,
    summaryMemory: patch.summaryMemory !== undefined ? patch.summaryMemory : prev.summaryMemory,
    customerProfile: nextProfile,
    messages,
    latestTransfer: nextLatestTransfer,
    updatedAt: nextUpdatedAt,
    metrics: {
      ...prev.metrics,
      totalTurns: messages.length,
    },
  };
}
