import { ChatMessage, ConversationSession, SessionPatch } from "../types";

/**
 * 将后端推送的轻量增量 SessionPatch 安全合并到本地完整会话对象中，
 * 避免覆盖静态客户画像字段与历史统计指标。
 */
export function applySessionPatch(
  prev: ConversationSession,
  patch?: SessionPatch | null,
  nextMessages?: ChatMessage[]
): ConversationSession {
  const messages = nextMessages ?? prev.messages;
  if (!patch) {
    return nextMessages
      ? {
          ...prev,
          messages,
          metrics: {
            ...prev.metrics,
            totalTurns: messages.length,
          },
        }
      : prev;
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
    metrics: {
      ...prev.metrics,
      totalTurns: messages.length,
    },
  };
}
