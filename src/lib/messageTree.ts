/**
 * Message Tree Utilities
 * Supports branching conversations: edit user messages, switch between sibling branches.
 *
 * The message tree is stored as a flat AIMessage[] where each message can have:
 * - parentId: links to parent message (null for root)
 * - children: array of child message IDs
 * - activeBranchIndex: which child branch is currently active (0-based)
 * - isEdited: whether this message was edited
 */

import { AIMessage } from '@/types/nexus';

/** Build a lookup map from message ID to message */
export function buildMessageMap(messages: AIMessage[]): Map<string, AIMessage> {
  const map = new Map<string, AIMessage>();
  for (const m of messages) {
    map.set(m.id, m);
  }
  return map;
}

/**
 * Get the active path from root to the current leaf.
 * Walks the tree following activeBranchIndex at each node.
 */
export function getActivePath(messages: AIMessage[]): AIMessage[] {
  if (messages.length === 0) return [];

  const map = buildMessageMap(messages);

  // Find root messages (parentId === null or undefined)
  const roots = messages.filter(m => m.parentId === null || m.parentId === undefined);
  if (roots.length === 0) {
    // No tree structure — treat as flat list (backward compat)
    return messages;
  }

  const path: AIMessage[] = [];

  // Walk from first root following active branches
  let current: AIMessage | undefined = roots[0];
  while (current) {
    path.push(current);
    if (!current.children || current.children.length === 0) break;
    const branchIdx = current.activeBranchIndex ?? 0;
    const childId = current.children[Math.min(branchIdx, current.children.length - 1)];
    current = map.get(childId);
  }

  return path;
}

/**
 * Edit a user message: creates a new sibling branch with the edited content.
 * Returns the updated messages array.
 */
export function handleEditMessage(
  messages: AIMessage[],
  messageId: string,
  newContent: string
): AIMessage[] {
  const map = buildMessageMap(messages);
  const target = map.get(messageId);
  if (!target || target.role !== 'user') return messages;

  const parentId = target.parentId ?? null;
  const parent = parentId ? map.get(parentId) : undefined;

  // Create new edited message
  const newId = `edit-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  const editedMsg: AIMessage = {
    ...target,
    id: newId,
    content: newContent,
    isEdited: true,
    parentId,
    children: [], // Will be populated when AI responds
    activeBranchIndex: 0,
  };

  // Update parent to include new child and point to it
  let updated = messages.map(m => {
    if (m.id === messageId) {
      // Keep the original but clear its children (it becomes a dead branch)
      return { ...m, children: [] };
    }
    return m;
  });

  if (parent) {
    updated = updated.map(m => {
      if (m.id === parent.id) {
        const children = [...(m.children || []), newId];
        const activeBranchIndex = children.length - 1; // Switch to new branch
        return { ...m, children, activeBranchIndex };
      }
      return m;
    });
  } else {
    // No parent — this is a root-level message
    // We need to handle root-level branching
    // Find all root messages and add the new one
    const roots = updated.filter(m => m.parentId === null || m.parentId === undefined);
    // The edited message becomes a new root sibling
    // For simplicity at root level, we just add it and mark it active
    editedMsg.parentId = null;
  }

  // Add the new edited message
  updated = [...updated, editedMsg];

  return updated;
}

/**
 * Switch to a different sibling branch.
 * Returns the updated messages array.
 */
export function handleSwitchBranch(
  messages: AIMessage[],
  parentMessageId: string,
  branchIndex: number
): AIMessage[] {
  return messages.map(m => {
    if (m.id === parentMessageId && m.children && branchIndex < m.children.length) {
      return { ...m, activeBranchIndex: branchIndex };
    }
    return m;
  });
}

/**
 * Get branch info for a message (number of siblings, current index).
 * Returns null if the message has no siblings (no branching).
 */
export function getBranchInfo(
  messages: AIMessage[],
  messageId: string
): { total: number; current: number } | null {
  const map = buildMessageMap(messages);
  const target = map.get(messageId);
  if (!target) return null;

  const parentId = target.parentId;
  if (!parentId) {
    // Root level — check if there are other roots
    const roots = messages.filter(m => m.parentId === null || m.parentId === undefined);
    if (roots.length <= 1) return null;
    const idx = roots.findIndex(m => m.id === messageId);
    return { total: roots.length, current: idx };
  }

  const parent = map.get(parentId);
  if (!parent || !parent.children || parent.children.length <= 1) return null;

  const idx = parent.children.indexOf(messageId);
  return { total: parent.children.length, current: idx };
}

/**
 * Convert a flat message array to tree structure by linking parent-child relationships.
 * This is used for backward compatibility — when messages come from the backend
 * without tree fields, we link them sequentially.
 */
export function linkMessagesSequentially(messages: AIMessage[]): AIMessage[] {
  if (messages.length === 0) return messages;

  // Check if already has tree structure
  const hasTree = messages.some(m => m.parentId !== undefined || m.children !== undefined);
  if (hasTree) return messages;

  return messages.map((m, i) => ({
    ...m,
    parentId: i === 0 ? null : messages[i - 1].id,
    children: i < messages.length - 1 ? [messages[i + 1].id] : [],
    activeBranchIndex: 0,
  }));
}
