/**
 * Business Context Fetcher — Calls backend aggregated API
 * to get pre-formatted business context for AI prompts.
 */

import { httpClient } from '@/lib/httpClient';

/**
 * Fetch business context relevant to the given agent type.
 * Returns a formatted text summary suitable for injection into the system prompt.
 */
export async function fetchBusinessContext(
  agent: string | undefined,
  userId: string,
  userRole: string,
): Promise<string> {
  const scene = resolveScene(agent, userRole);

  try {
    const response = await httpClient.get('/api/context/business', {
      params: { scene },
    });
    return response.data?.data || '';
  } catch (err) {
    console.warn('Failed to fetch business context:', err);
    return '';
  }
}

/**
 * Convenience wrapper matching the new simplified signature.
 */
export async function getBusinessContext(userId: string, role: string, scene?: string): Promise<string> {
  try {
    const response = await httpClient.get('/api/context/business', {
      params: { scene: scene || (role === 'boss' ? 'boss' : 'default') },
    });
    return response.data?.data || '';
  } catch (err) {
    console.warn('Failed to fetch business context:', err);
    return '';
  }
}

function resolveScene(agent?: string, userRole?: string): string {
  if (!agent) return userRole === 'boss' ? 'boss' : 'default';
  const map: Record<string, string> = {
    '@销售助手': 'sales',
    '@销售指挥官': 'sales',
    'sales_commander': 'sales',
    '@流程助手': 'approval',
    '@审批管家': 'approval',
    'approval_manager': 'approval',
    '@绩效助手': 'performance',
    '@绩效教练': 'performance',
    'performance_coach': 'performance',
    '@总裁助理': 'boss',
    'boss_assistant': 'boss',
  };
  return map[agent] || 'default';
}
