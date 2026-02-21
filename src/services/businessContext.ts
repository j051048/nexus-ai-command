/**
 * Business Context Fetcher — Pre-fetch relevant business data from Supabase
 * for the enhanced direct mode (Tier 2).
 *
 * Queries are agent-aware: each agent type gets the data most relevant to it.
 * All queries use LIMIT to control context size (target: < 2000 chars total).
 */

import { supabase } from '@/integrations/supabase/client';

interface ContextResult {
  context: string;
  tables: string[];
}

/**
 * Fetch business context relevant to the given agent type.
 * Returns a formatted text summary suitable for injection into the system prompt.
 */
export async function fetchBusinessContext(
  agent: string | undefined,
  userId: string,
  userRole: string,
): Promise<string> {
  const key = resolveAgent(agent);

  try {
    const fetchers: Record<string, () => Promise<ContextResult>> = {
      approval_manager: () => fetchApprovalContext(userId, userRole),
      sales_commander: () => fetchSalesContext(),
      boss_assistant: () => fetchBossContext(userId),
      performance_coach: () => fetchPerformanceContext(),
      default_fallback: () => fetchDefaultContext(userId, userRole),
    };

    const fetcher = fetchers[key] || fetchers.default_fallback;
    const result = await fetcher();
    return result.context;
  } catch (err) {
    console.warn('Failed to fetch business context:', err);
    return '';
  }
}

function resolveAgent(agent?: string): string {
  if (!agent) return 'default_fallback';
  const map: Record<string, string> = {
    '@销售指挥官': 'sales_commander',
    'sales_commander': 'sales_commander',
    '@审批管家': 'approval_manager',
    'approval_manager': 'approval_manager',
    '@绩效教练': 'performance_coach',
    'performance_coach': 'performance_coach',
    '@总裁助理': 'boss_assistant',
    'boss_assistant': 'boss_assistant',
  };
  return map[agent] || 'default_fallback';
}

// ────────────────────────────────────────────
// Agent-specific context fetchers
// ────────────────────────────────────────────

async function fetchApprovalContext(userId: string, userRole: string): Promise<ContextResult> {
  const sections: string[] = [];

  // Pending approvals
  const { data: pending } = await supabase
    .from('approval_requests')
    .select('id, type, description, amount, status, submitted_by, created_at')
    .eq('status', 'pending')
    .order('created_at', { ascending: false })
    .limit(10);

  if (pending?.length) {
    sections.push('### 待审批事项');
    for (const r of pending) {
      const amt = r.amount ? `¥${r.amount}` : '无金额';
      sections.push(`- [${r.type}] ${r.description || '无描述'} | ${amt} | ${r.created_at?.slice(0, 10)}`);
    }
  } else {
    sections.push('### 待审批事项\n当前无待审批事项。');
  }

  // My submitted approvals (for non-boss roles)
  if (userRole !== 'boss' && userRole !== 'founder') {
    const { data: mine } = await supabase
      .from('approval_requests')
      .select('type, description, amount, status, created_at')
      .eq('submitted_by', userId)
      .order('created_at', { ascending: false })
      .limit(5);

    if (mine?.length) {
      sections.push('\n### 我的申请记录');
      for (const r of mine) {
        const statusMap: Record<string, string> = { pending: '待审批', approved: '已通过', rejected: '已驳回' };
        sections.push(`- [${r.type}] ${r.description || ''} | ${statusMap[r.status] || r.status} | ${r.created_at?.slice(0, 10)}`);
      }
    }
  }

  return { context: sections.join('\n'), tables: ['approval_requests'] };
}

async function fetchSalesContext(): Promise<ContextResult> {
  const sections: string[] = [];

  // Recent leads
  const { data: leads } = await supabase
    .from('sales_leads')
    .select('company_name, contact_name, status, score, source, created_at')
    .order('created_at', { ascending: false })
    .limit(10);

  if (leads?.length) {
    sections.push('### 近期销售线索');
    for (const l of leads) {
      sections.push(`- ${l.company_name} (${l.contact_name || '未知联系人'}) | 状态:${l.status} | 评分:${l.score} | 来源:${l.source || '未知'}`);
    }
  }

  // Sales metrics (latest)
  const { data: metrics } = await supabase
    .from('sales_metrics')
    .select('metric_date, revenue, leads_count, conversion_rate')
    .order('metric_date', { ascending: false })
    .limit(5);

  if (metrics?.length) {
    sections.push('\n### 销售指标');
    for (const m of metrics) {
      sections.push(`- ${m.metric_date}: 收入¥${m.revenue} | 线索${m.leads_count}个 | 转化率${(m.conversion_rate * 100).toFixed(1)}%`);
    }
  }

  // Current targets
  const { data: targets } = await supabase
    .from('sales_targets')
    .select('target_period, target_type, revenue_target, leads_target, win_rate_target')
    .order('created_at', { ascending: false })
    .limit(2);

  if (targets?.length) {
    sections.push('\n### 销售目标');
    for (const t of targets) {
      sections.push(`- ${t.target_period} (${t.target_type}): 收入目标¥${t.revenue_target} | 线索目标${t.leads_target}个 | 赢率目标${(t.win_rate_target * 100).toFixed(0)}%`);
    }
  }

  return { context: sections.join('\n'), tables: ['sales_leads', 'sales_metrics', 'sales_targets'] };
}

async function fetchBossContext(userId: string): Promise<ContextResult> {
  const sections: string[] = [];

  // Pending approvals count + top items
  const { data: pending } = await supabase
    .from('approval_requests')
    .select('id, type, description, amount, submitted_by, created_at')
    .eq('status', 'pending')
    .order('created_at', { ascending: false })
    .limit(5);

  sections.push(`### 待审批事项 (${pending?.length || 0}件)`);
  if (pending?.length) {
    for (const r of pending) {
      const amt = r.amount ? `¥${r.amount}` : '';
      sections.push(`- [${r.type}] ${r.description || '无描述'} ${amt}`);
    }
  }

  // Team overview
  const { data: users } = await supabase
    .from('users')
    .select('full_name, role, department, status')
    .eq('status', 'active')
    .limit(20);

  if (users?.length) {
    const deptCounts: Record<string, number> = {};
    for (const u of users) {
      const dept = u.department || '未分配';
      deptCounts[dept] = (deptCounts[dept] || 0) + 1;
    }
    sections.push(`\n### 团队概况 (${users.length}人在岗)`);
    for (const [dept, count] of Object.entries(deptCounts)) {
      sections.push(`- ${dept}: ${count}人`);
    }
  }

  // Latest sales metrics
  const { data: metrics } = await supabase
    .from('sales_metrics')
    .select('metric_date, revenue, leads_count, conversion_rate')
    .order('metric_date', { ascending: false })
    .limit(3);

  if (metrics?.length) {
    sections.push('\n### 经营指标');
    for (const m of metrics) {
      sections.push(`- ${m.metric_date}: 收入¥${m.revenue} | 线索${m.leads_count}个 | 转化${(m.conversion_rate * 100).toFixed(1)}%`);
    }
  }

  // Projects overview
  const { data: projects } = await supabase
    .from('projects')
    .select('name, status, budget')
    .limit(5);

  if (projects?.length) {
    sections.push('\n### 项目概况');
    for (const p of projects) {
      const budget = p.budget ? `预算¥${p.budget}` : '';
      sections.push(`- ${p.name} | 状态:${p.status} ${budget}`);
    }
  }

  return {
    context: sections.join('\n'),
    tables: ['approval_requests', 'users', 'sales_metrics', 'projects'],
  };
}

async function fetchPerformanceContext(): Promise<ContextResult> {
  const sections: string[] = [];

  // Team members
  const { data: users } = await supabase
    .from('users')
    .select('full_name, role, department, job_title, status')
    .eq('status', 'active')
    .limit(20);

  if (users?.length) {
    sections.push('### 团队成员');
    for (const u of users) {
      sections.push(`- ${u.full_name || '未知'} | ${u.role} | ${u.department || '未分配'} | ${u.job_title || ''}`);
    }
  }

  // Projects for context
  const { data: projects } = await supabase
    .from('projects')
    .select('name, status')
    .limit(5);

  if (projects?.length) {
    sections.push('\n### 项目状态');
    for (const p of projects) {
      sections.push(`- ${p.name}: ${p.status}`);
    }
  }

  return { context: sections.join('\n'), tables: ['users', 'projects'] };
}

async function fetchDefaultContext(userId: string, userRole: string): Promise<ContextResult> {
  const sections: string[] = [];

  // Projects
  const { data: projects } = await supabase
    .from('projects')
    .select('name, status, description, budget')
    .limit(5);

  if (projects?.length) {
    sections.push('### 项目列表');
    for (const p of projects) {
      sections.push(`- ${p.name} | ${p.status}${p.budget ? ` | 预算¥${p.budget}` : ''}`);
    }
  }

  // Pending approvals (relevant to all roles)
  const { data: pending } = await supabase
    .from('approval_requests')
    .select('type, description, amount, status')
    .eq('status', 'pending')
    .limit(5);

  if (pending?.length) {
    sections.push(`\n### 待审批事项 (${pending.length}件)`);
    for (const r of pending) {
      sections.push(`- [${r.type}] ${r.description || '无描述'}${r.amount ? ` ¥${r.amount}` : ''}`);
    }
  }

  // Unread notifications
  const { data: notifs } = await supabase
    .from('notifications')
    .select('title, message, type, created_at')
    .eq('user_id', userId)
    .eq('read', false)
    .order('created_at', { ascending: false })
    .limit(5);

  if (notifs?.length) {
    sections.push(`\n### 未读通知 (${notifs.length}条)`);
    for (const n of notifs) {
      sections.push(`- [${n.type}] ${n.title}: ${n.message?.slice(0, 50)}`);
    }
  }

  // OA tasks assigned to user
  const { data: tasks } = await supabase
    .from('oa_tasks')
    .select('title, status, priority, due_date')
    .eq('assignee_id', userId)
    .neq('status', 'completed')
    .limit(5);

  if (tasks?.length) {
    sections.push('\n### 我的待办任务');
    for (const t of tasks) {
      sections.push(`- ${t.title} | ${t.status} | 优先级:${t.priority}${t.due_date ? ` | 截止:${t.due_date}` : ''}`);
    }
  }

  return {
    context: sections.join('\n'),
    tables: ['projects', 'approval_requests', 'notifications', 'oa_tasks'],
  };
}
