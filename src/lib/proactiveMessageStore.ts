/**
 * Proactive Message Store
 *
 * Module-level queue for AI proactive messages (scheduled tasks, event alerts, etc.)
 * Bridges useWebSocketPush → EnhancedAIChatPanel without prop drilling.
 */

export interface ProactiveMessage {
  id: string;
  organizationId: string;
  userId: string;
  sessionId: string;
  title: string;
  message: string;
  priority?: string;
  receivedAt: Date;
}

const pendingQueue: ProactiveMessage[] = [];
const consumedIds = new Set<string>();

export const PROACTIVE_MSG_EVENT = 'nexus:proactive-message';

/** Called by useWebSocketPush when a proactive_chat WS message arrives */
export function enqueueProactiveMessage(msg: ProactiveMessage): void {
  if (!msg.id || !msg.organizationId || !msg.userId) return;
  const key = `${msg.organizationId}:${msg.userId}:${msg.id}`;
  if (consumedIds.has(key)) return;
  if (pendingQueue.some(m => m.id === msg.id && m.userId === msg.userId && m.organizationId === msg.organizationId)) return;
  pendingQueue.push(msg);
  if (pendingQueue.length > 100) pendingQueue.shift();
  window.dispatchEvent(new CustomEvent(PROACTIVE_MSG_EVENT));
}

/** Called by EnhancedAIChatPanel to drain all pending messages */
export function drainProactiveMessages(organizationId: string, userId: string): ProactiveMessage[] {
  const messages = pendingQueue.filter(message => message.organizationId === organizationId && message.userId === userId);
  pendingQueue.length = 0;
  messages.forEach(m => consumedIds.add(`${m.organizationId}:${m.userId}:${m.id}`));
  while (consumedIds.size > 500) consumedIds.delete(consumedIds.values().next().value!);
  return messages;
}
