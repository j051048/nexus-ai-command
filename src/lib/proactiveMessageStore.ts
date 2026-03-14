/**
 * Proactive Message Store
 *
 * Module-level queue for AI proactive messages (scheduled tasks, event alerts, etc.)
 * Bridges useWebSocketPush → EnhancedAIChatPanel without prop drilling.
 */

export interface ProactiveMessage {
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
  if (consumedIds.has(msg.sessionId)) return;
  if (pendingQueue.some(m => m.sessionId === msg.sessionId)) return;
  pendingQueue.push(msg);
  window.dispatchEvent(new CustomEvent(PROACTIVE_MSG_EVENT));
}

/** Called by EnhancedAIChatPanel to drain all pending messages */
export function drainProactiveMessages(): ProactiveMessage[] {
  const messages = [...pendingQueue];
  pendingQueue.length = 0;
  messages.forEach(m => consumedIds.add(m.sessionId));
  return messages;
}
