export type AuthRole = 'boss' | 'manager' | 'admin' | 'ai_assistant' | 'employee' | 'pending_boss';

/** Normalize server-issued roles only; unknown and pending roles never gain privileges. */
export function normalizeAuthRole(value: unknown): Exclude<AuthRole, 'pending_boss'> {
  switch (value) {
    case 'founder':
    case 'boss': return 'boss';
    case 'manager': return 'manager';
    case 'admin': return 'admin';
    case 'ai_assistant': return 'ai_assistant';
    default: return 'employee';
  }
}
