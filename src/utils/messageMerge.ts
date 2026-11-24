import { ChatMessage } from "../types";

// 严格基于唯一 ID 去重，绝不按文本内容误杀用户的多次发言
export function uniqueMessages(msgs: ChatMessage[]): ChatMessage[] {
  const result: ChatMessage[] = [];
  const seenIds = new Set<string>();
  for (const m of msgs) {
    if (!m || !m.id) continue;
    if (!seenIds.has(m.id)) {
      seenIds.add(m.id);
      result.push(m);
    }
  }
  return result;
}

// 核心消息保护器：当收到服务端全量/增量消息时，平滑替换 temp 乐观气泡，未落库的 temp 永不丢弃
export function mergeServerMessages(
  prevMsgs: ChatMessage[] = [],
  incomingMsgs: ChatMessage[] = [],
  isFullSync: boolean = false
): ChatMessage[] {
  if (!incomingMsgs || incomingMsgs.length === 0) return prevMsgs;

  const pendingTemps = prevMsgs.filter(m => m && m.id && m.id.startsWith("temp-"));
  const confirmedPrev = prevMsgs.filter(m => m && m.id && !m.id.startsWith("temp-"));

  const result: ChatMessage[] = [];
  const seenIds = new Set<string>();

  // 区分全量同步与增量追加
  const baseServerList = isFullSync
    ? incomingMsgs
    : [...confirmedPrev, ...incomingMsgs.filter(m => !confirmedPrev.some(p => p.id === m.id))];

  for (const sm of baseServerList) {
    if (!sm || !sm.id || seenIds.has(sm.id)) continue;
    seenIds.add(sm.id);
    result.push(sm);
  }

  // 计算各角色文本新增的确认条数
  const keyCounts = new Map<string, number>();
  for (const sm of result) {
    const k = `${sm.role}:::${sm.content.trim()}`;
    keyCounts.set(k, (keyCounts.get(k) || 0) + 1);
  }

  const prevCounts = new Map<string, number>();
  for (const pm of confirmedPrev) {
    const k = `${pm.role}:::${pm.content.trim()}`;
    prevCounts.set(k, (prevCounts.get(k) || 0) + 1);
  }

  const newConfirmations = new Map<string, number>();
  for (const [k, count] of keyCounts.entries()) {
    const prevC = prevCounts.get(k) || 0;
    if (count > prevC) {
      newConfirmations.set(k, count - prevC);
    }
  }

  // 按照先进先出匹配 temp 消息：新到落库的抵扣掉对应 temp，其余尚未被服务端收录的 temp 绝不丢失
  const consumedPerKey = new Map<string, number>();
  const remainingTemps: ChatMessage[] = [];

  for (const temp of pendingTemps) {
    const k = `${temp.role}:::${temp.content.trim()}`;
    const allowedToConsume = newConfirmations.get(k) || 0;
    const alreadyConsumed = consumedPerKey.get(k) || 0;

    if (alreadyConsumed < allowedToConsume) {
      consumedPerKey.set(k, alreadyConsumed + 1);
    } else {
      if (!seenIds.has(temp.id)) {
        seenIds.add(temp.id);
        remainingTemps.push(temp);
      }
    }
  }

  return [...result, ...remainingTemps];
}
