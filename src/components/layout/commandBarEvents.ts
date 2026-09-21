/**
 * Command bar event bus.
 *
 * Kept in its own module so that components which only need to dispatch a chat
 * message do not pull the whole (lazy-loaded) command bar bundle, including the
 * cmdk dialog and pinyin matching tables, into the application entry chunk.
 */
export const COMMAND_BAR_CHAT_EVENT = 'nexus:command-bar-chat';
export const COMMAND_BAR_NEW_CHAT_EVENT = 'nexus:command-bar-new-chat';

export function dispatchAIChatMessage(message: string) {
  window.dispatchEvent(new CustomEvent(COMMAND_BAR_CHAT_EVENT, { detail: { message } }));
}

export function dispatchNewChat() {
  window.dispatchEvent(new CustomEvent(COMMAND_BAR_NEW_CHAT_EVENT));
}
