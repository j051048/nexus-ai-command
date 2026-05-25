/**
 * E2E 测试 Mock 拦截器
 *
 * 为 core 业务流程提供基础的 API 模拟，支持在无后端环境下运行。
 */

import { Page, Route, expect } from "@playwright/test";

const corsHeaders = {
  'access-control-allow-origin': 'http://localhost:4173',
  'access-control-allow-credentials': 'true',
  'access-control-allow-methods': 'GET,POST,PUT,PATCH,DELETE,OPTIONS',
  'access-control-allow-headers': 'authorization,content-type,x-client-info,apikey,x-requested-with,x-org-id,x-csrf-token,x-idempotency-key',
};

export async function fulfillJson(route: Route, body: unknown, status = 200) {
  if (route.request().method() === 'OPTIONS') {
    await route.fulfill({ status: 204, headers: corsHeaders, body: '' });
    return;
  }
  await route.fulfill({
    status,
    headers: {
      ...corsHeaders,
      'content-type': 'application/json',
    },
    body: JSON.stringify(body),
  });
}

function createFakeJwt(role = 'boss') {
  const now = Math.floor(Date.now() / 1000);
  const encode = (value: unknown) =>
    Buffer.from(JSON.stringify(value)).toString('base64url');
  return [
    encode({ alg: 'HS256', typ: 'JWT' }),
    encode({
      sub: 'test-user-id',
      email: 'test-admin@nexus-ai.com',
      role: 'authenticated',
      app_metadata: { provider: 'email', role },
      user_metadata: { role, name: 'E2E Admin' },
      aud: 'authenticated',
      exp: now + 3600,
      iat: now,
    }),
    'fake-signature',
  ].join('.');
}

function getSupabaseAuthStorageKeys(): string[] {
  const keys = new Set<string>(['sb-hztpazmuejgbtixihcgj-auth-token']);
  const url = process.env.VITE_SUPABASE_URL || process.env.SUPABASE_URL;
  if (url) {
    try {
      const projectRef = new URL(url).hostname.split('.')[0];
      if (projectRef) keys.add(`sb-${projectRef}-auth-token`);
    } catch {
      // Keep the stable fallback key above.
    }
  }
  return [...keys];
}

export async function setupBusinessMocks(page: Page) {
  // 1. 拦截 Auth token 请求（login + refresh）
  await page.route('**/auth/v1/token*', async (route) => {
    await fulfillJson(route, {
        access_token: createFakeJwt('boss'),
        token_type: 'bearer',
        expires_in: 3600,
        refresh_token: 'fake-refresh',
        user: {
          id: 'test-user-id',
          email: 'test-admin@nexus-ai.com',
          user_metadata: { role: 'boss', name: 'E2E Admin' },
          app_metadata: { provider: 'email', role: 'boss' }
        }
      });
  });

  // 2. 拦截 Auth user 信息
  await page.route('**/auth/v1/user*', async (route) => {
    await fulfillJson(route, {
        id: 'test-user-id',
        email: 'test-admin@nexus-ai.com',
        user_metadata: { role: 'boss', name: 'E2E Admin' },
        app_metadata: { provider: 'email', role: 'boss' }
      });
  });

  // 3. 拦截用户 profile API
  await page.route(/.*profile.*/, async (route) => {
    await fulfillJson(route, {
        code: 200,
        data: {
          id: 'test-user-id',
          email: 'test-admin@nexus-ai.com',
          name: 'E2E Admin',
          role: 'boss',
          avatar_url: null,
          user: {
            id: 'test-user-id',
            email: 'test-admin@nexus-ai.com',
            name: 'E2E Admin',
            role: 'boss',
            avatar_url: null
          }
        }
      });
  });

  // 4. 拦截 RPC 调用 (get_user_role, is_super_admin)
  await page.route('**/rest/v1/rpc/get_user_role*', async (route) => {
    await fulfillJson(route, 'boss');
  });

  await page.route('**/rest/v1/rpc/is_super_admin*', async (route) => {
    await fulfillJson(route, false);
  });

  // 5. 拦截组织信息
  await page.route('**/rest/v1/organizations*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{ id: 'org-123', name: 'Nexus AI Test Org' }])
    });
  });

  // 6. 拦截流程列表 (Workflows)
  await page.route('**/rest/v1/workflows*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { id: 'wf-1', name: '入职审批流程', status: 'active', created_at: new Date().toISOString() },
        { id: 'wf-2', name: '报销自动处理', status: 'draft', created_at: new Date().toISOString() }
      ])
    });
  });

  // 7. 拦截审批中心 (Approvals)
  await page.route('**/rest/v1/approvals*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { id: 'ap-1', title: '加班申请 - 张三', status: 'pending', priority: 'high' }
      ])
    });
  });

  // 8. 拦截销售目标 (Targets)
  await page.route('**/rest/v1/sales_targets*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { id: 'tg-1', target_amount: 1000000, current_amount: 450000, period: '2024-Q1' }
      ])
    });
  });

  // 9. 拦截 CRM 数据
  await page.route('**/rest/v1/customers*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { id: 'c-1', name: 'Google Cloud', industry: 'Tech', status: 'active' }
      ])
    });
  });

  await page.route('**/api/inbox/analytics**', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        window_days: 30,
        summary: {
          total_events: 7,
          accepted: 3,
          completed: 2,
          ignored: 1,
          snoozed: 1,
          completion_rate: 0.29,
          acceptance_rate: 0.43,
          ignored_rate: 0.14,
          open_high_risk: 1,
          unique_actors: 2,
        },
        by_source: {
          approval: {
            total: 3,
            accepted: 1,
            completed: 1,
            ignored: 0,
            snoozed: 1,
            command_executed: 1,
          },
          crm: {
            total: 4,
            accepted: 2,
            completed: 1,
            ignored: 1,
            snoozed: 0,
            command_executed: 0,
          },
        },
        stale_open_actions: [
          {
            id: 'crm-risk:c-1',
            source: 'crm',
            source_id: 'c-1',
            type: 'customer_followup_risk',
            title: 'Google Cloud 需要跟进',
            description: '客户长时间没有新的跟进记录',
            reason: 'AI 规则：机会客户 30 天无更新',
            priority: 'high',
            status: 'open',
            created_at: new Date().toISOString(),
            action_url: '/crm?customer=c-1',
            actions: [],
            metadata: {},
          },
        ],
        recent_events: [
          {
            id: 'evt-1',
            action_id: 'approval:ap-1',
            source: 'approval',
            event_type: 'accepted',
            created_at: new Date().toISOString(),
            metadata: {},
          },
        ],
      },
    });
  });

  await page.route('**/api/inbox/actions**', async (route) => {
    if (route.request().url().includes('/events')) {
      await fulfillJson(route, {
        success: true,
        data: {
          recorded: true,
          event: {
            id: 'evt-1',
            created_at: new Date().toISOString(),
          },
        },
      });
      return;
    }

    await fulfillJson(route, {
      success: true,
      data: {
        items: [
          {
            id: 'approval:ap-1',
            source: 'approval',
            source_id: 'ap-1',
            type: 'expense',
            title: 'E2E Admin 的报销审批',
            description: '测试环境待处理审批',
            reason: '等待你处理的审批事项',
            priority: 'high',
            status: 'open',
            created_at: new Date().toISOString(),
            action_url: '/approval',
            actions: [
              {
                id: 'view',
                label: '查看',
                kind: 'navigate',
                variant: 'primary',
                navigate_to: '/approval',
              },
            ],
            metadata: {
              risk_score: 65,
              risk_flags: ['测试审批待处理'],
              evidence: [
                { label: '提交人', value: 'E2E Admin' },
                { label: '审批类型', value: 'expense' },
              ],
            },
          },
        ],
        summary: {
          total: 1,
          urgent: 0,
          high: 1,
          by_source: {
            approval: 1,
            notification: 0,
            crm: 0,
            system: 0,
          },
        },
      },
    });
  });

  await page.route('**/api/ai-operating-system/overview**', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        window_days: 30,
        agent: {
          total_runs: 18,
          completed: 15,
          failed: 2,
          failure_rate: 0.11,
          success_rate: 0.83,
          tool_failure_signals: 1,
          total_cost_usd: 1.23,
          total_tokens: 42000,
        },
        actions: {
          total_events: 9,
          accepted: 4,
          completed: 3,
          ignored: 1,
          completion_rate: 0.33,
          acceptance_rate: 0.44,
        },
        graph: {
          nodes: [
            { id: 'customer:c-1', type: 'customer', label: 'Google Cloud', status: 'lead' },
            { id: 'project:p-1', type: 'project', label: 'Pilot Rollout', status: 'planning' },
            { id: 'action_event:e-1', type: 'action_event', label: 'crm-risk:c-1', status: 'accepted' },
          ],
          edges: [
            { source: 'customer:c-1', target: 'project:p-1', label: '客户项目', strength: 0.86 },
            { source: 'customer:c-1', target: 'action_event:e-1', label: '客户行动', strength: 0.68 },
          ],
          summary: {
            node_count: 3,
            edge_count: 2,
            density: 0.67,
            entity_counts: { customer: 1, project: 1, action_event: 1 },
          },
          prompt_context: '[业务知识图谱]\\n- customer: Google Cloud',
        },
        recent_runs: [
          {
            id: 'run-1',
            run_id: 'run-1',
            status: 'completed',
            input_summary: '查询高价值客户跟进风险',
            updated_at: new Date().toISOString(),
          },
        ],
          operating_metrics: {
            agent_success_rate: 0.83,
            action_completion_rate: 0.33,
            context_graph_nodes: 3,
            context_graph_edges: 2,
          },
          value: {
            saved_minutes: 86,
            saved_hours: 1.4,
            automated_followups: 2,
            risk_reviews: 3,
            estimated_value_cny: 1392,
            roi_story: '近 30 天 AI 约节省 1.4 小时，自动推进 2 个跟进动作，识别/复核 3 个风险信号，折算业务价值约 ¥1392。',
          },
          trust: {
            confidence_score: 75,
            confidence_level: '中',
            human_review_rate: 0.56,
            tool_failure_rate: 0.06,
            audit_summary: 'Agent 成功率 83%，行动完成率 33%，工具失败信号 1 次。',
          },
        },
      });
    });

  await page.route('**/api/ai-operating-system/prompt-registry**', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        manifests: [
          {
            agent_code: 'director_agent',
            prompt_version: 'director_agent@2026-05-25.1',
            owner: 'agent-platform',
            scenario: 'scientific instrument sales operations',
            risk_tier: 'high',
            status: 'active',
            eval_gates: ['agent_ci', 'redteam', 'human_approval'],
            blocks: [{ name: 'operating_policy', purpose: 'governed action', risk: 'medium', required: true }],
          },
        ],
      },
    });
  });

  await page.route('**/api/ai-operating-system/agent-ci**', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        passed: true,
        score: 0.91,
        case_count: 2,
        recommendation: 'ready_for_gray_release',
        cases: [
          {
            id: 'eval-crm-risk-followup',
            message: 'Find stale customers',
            passed: true,
            score: 0.94,
            behavior_diff: {
              expected_tools: ['search_customers', 'draft_followup'],
              actual_tools: ['search_customers', 'draft_followup'],
              missing_tools: [],
              forbidden_hits: [],
            },
          },
        ],
      },
    });
  });

  await page.route('**/api/ai-operating-system/improvement-proposals**', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        proposals: [
          {
            id: 'proposal-crm-nba',
            category: 'context_policy',
            title: 'Require evidence pack for CRM next best action',
            rationale: 'Low-quality runs show missing evidence links.',
            proposed_patch: { context: 'evidence_pack_required' },
            risk_level: 'medium',
            approval_required: true,
            status: 'proposed',
          },
        ],
        agent_ci: {
          passed: true,
          score: 0.91,
          case_count: 2,
          recommendation: 'ready_for_gray_release',
          cases: [],
        },
        governance: {
          self_mutation_allowed: false,
          required_flow: ['proposal', 'agent_ci', 'human_approval', 'gray_release', 'rollback'],
        },
      },
    });
  });

  await page.route('**/api/ai-operating-system/memory-hygiene**', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        sample_size: 20,
        hygiene_score: 87,
        stale_memories: 2,
        expired_memories: 1,
        compressed_memories: 3,
        conflict_candidates: 1,
        golden_examples: 6,
        recommendations: ['Promote high-quality solved runs to golden examples.'],
        policy: { max_age_days: 120, golden_example_target: 50 },
      },
    });
  });

  await page.route('**/api/ai-operating-system/evolution-ops**', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        generated_at: new Date().toISOString(),
        persistence: {
          migration: '20260525_agent_evolution_ops.sql',
          tables: ['agent_prompt_versions', 'agent_improvement_proposals', 'agent_eval_cases', 'agent_redteam_findings'],
          persisted_counts: { agent_prompt_versions: 1, agent_improvement_proposals: 1 },
          mode: 'database_backed_with_safe_fallback',
        },
        proposal_flow: {
          states: ['proposed', 'approved', 'gray_release', 'published', 'rolled_back', 'rejected'],
          requires_human_approval: true,
          records: [
            {
              id: 'proposal-crm-nba',
              title: 'Require evidence pack for CRM next best action',
              status: 'proposed',
              approval_required: true,
              gray_percentage: 0,
              rollback_plan: 'restore previous prompt_version',
              allowed_actions: ['approve', 'reject', 'gray_release', 'rollback'],
            },
          ],
        },
        diffs: {
          prompt_diff: { baseline_version: 'director_agent@2026-05-25.1', candidate_version: 'candidate' },
          context_diff: { candidate_policy: 'require evidence_pack' },
          tool_diff: { candidate_mode: 'low-risk autonomous action with HITL' },
        },
        low_quality_queue: [
          {
            id: 'run-low-1',
            reason: 'tool failed',
            priority: 'high',
            suggested_action: 'convert_to_eval_case',
            source: 'agent_runs',
          },
        ],
        eval_dataset: {
          case_count: 3,
          from_real_runs: 1,
          coverage_dimensions: ['sales_followup', 'scientific_instrument_tender'],
          cases: [],
        },
        reward_model: {
          name: 'business_reward_model_v1',
          score: 0.76,
          signals: [{ name: 'task_completed', weight: 1 }],
          business_outcomes: ['saved_minutes', 'risk_prevented'],
        },
        skill_marketplace: [
          {
            id: 'scientific_tender_copilot',
            name: 'Scientific Tender Copilot',
            scenario: 'scientific_instrument_tender',
            agent_roles: ['tender_agent'],
            tools: ['parse_tender_document'],
            install_state: 'recommended',
            quality_gate: 'agent_ci_score >= 0.85',
          },
        ],
        multi_agent_protocol: {
          name: 'Nexus Agent Collaboration Protocol',
          version: '2026-05-25.1',
          handoff_contract: ['Every handoff includes evidence_ids.'],
          flows: [{ id: 'tender_to_approval', steps: [{ agent: 'sales_agent', responsibility: 'capture context' }] }],
        },
        redteam_center: {
          scenario_count: 5,
          open_high: 0,
          scenarios: [],
          latest_findings: [],
          required_release_gate: 'no critical open finding',
        },
        trust_center: {
          customer_visible: true,
          confidence_score: 88,
          confidence_level: 'high',
          audit_story: '1 proposals reviewed, CI score 0.91, reward score 0.76.',
          controls: ['versioned_prompt_registry', 'human_approval_required', 'gray_release_and_rollback'],
        },
      },
    });
  });

  await page.route('**/api/ai-operating-system/proposals/*/decision**', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        proposal_key: 'proposal-crm-nba',
        action: 'gray_release',
        status: 'gray_release',
        persistence: 'saved',
      },
    });
  });

  await page.route('**/api/ai-operating-system/simulate**', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        cases: [
          {
            id: 'case-1',
            message: '30天未跟进客户自动生成拜访提醒和邮件草稿',
            detected_intent: 'crm_followup',
            suggested_tools: ['search_customers', 'draft_followup'],
            baseline: { mode: 'recommend_only', expected_outcome: '生成建议，等待人工点击执行' },
            candidate: { mode: 'auto', policy: '低风险自动执行', expected_outcome: '自动执行低风险步骤' },
            risk_score: 20,
            risk_flags: ['低风险信息处理或草稿生成，可自动执行'],
          },
        ],
        summary: {
          case_count: 1,
          automation_rate: 1,
          hitl_rate: 0,
          avg_risk_score: 20,
          recommendation: '可上线灰度',
        },
        context_graph_summary: {
          node_count: 3,
          edge_count: 2,
          density: 0.67,
          entity_counts: { customer: 1, project: 1, action_event: 1 },
        },
        baseline_policy: '全部建议人工点击执行',
        candidate_policy: '低风险自动执行',
      },
      });
    });

  await page.route('**/api/ai-operating-system/define-agent**', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        scenario: '科学仪器客户跟进 Agent',
        autonomy_level: 'guarded_auto',
        intent_rules: [
          {
            name: '科学仪器客户跟进 Agent 规则 1',
            trigger: '当科学仪器客户 30 天没有跟进记录时，Agent 需要查询客户阶段、最近拜访、项目预算和历史沟通。',
            tools: ['search_customers', 'draft_followup'],
            autonomy: 'guarded_auto',
          },
        ],
        operating_procedure: [
          {
            step: 1,
            name: '步骤 1',
            instruction: '查询客户阶段、最近拜访、项目预算和历史沟通。',
            expected_evidence: '客户/项目/合同/文档/行动事件',
          },
        ],
        tools: ['search_customers', 'draft_followup', 'create_visit_note'],
        guardrails: [
          '所有付款、删除、批量外发、审批结论和合同金额变更必须进入人工确认。',
          '回答必须引用客户、项目、合同、审批或文档证据；证据不足时只生成待确认草稿。',
        ],
        test_cases: ['用户说：30 天未跟进客户。验证 Agent 是否输出证据链。'],
        confidence: 0.82,
        next_steps: ['放入 Agent 仿真沙盒跑历史消息回放。'],
        definition_markdown: '# 科学仪器客户跟进 Agent Operating Procedure',
      },
    });
  });
  }

/**
 * 快速注入登录状态至 localStorage
 * Supabase JS v2 使用 sb-{project-ref}-auth-token 作为 storage key
 * access_token 必须是可解码的 JWT 格式，否则 Supabase 会认为 session 无效
 */
export async function mockLoggedInState(page: Page, role = 'boss') {
  const storageKeys = getSupabaseAuthStorageKeys();
  await page.addInitScript(({ sessionRole, keys }) => {
    // 构造一个可解码的 fake JWT（Supabase JS v2 会 base64 decode 来检查 exp）
    const now = Math.floor(Date.now() / 1000);
    const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
      .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    const payload = btoa(JSON.stringify({
      sub: 'test-user-id',
      email: `${sessionRole}@nexus-ai.com`,
      role: 'authenticated',
      aud: 'authenticated',
      exp: now + 3600,
      iat: now,
      app_metadata: { provider: 'email', role: sessionRole },
      user_metadata: { role: sessionRole, name: `E2E ${sessionRole}` },
    })).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    const fakeJwt = `${header}.${payload}.fake-signature`;

    const mockSession = {
      access_token: fakeJwt,
      token_type: 'bearer',
      expires_in: 3600,
      expires_at: now + 3600,
      refresh_token: 'fake-refresh',
      user: {
        id: 'test-user-id',
        aud: 'authenticated',
        email: `${sessionRole}@nexus-ai.com`,
        role: 'authenticated',
        user_metadata: { role: sessionRole, name: `E2E ${sessionRole}` },
        app_metadata: { provider: 'email', role: sessionRole }
      }
    };
    // Supabase JS v2 storage key format
    const serialized = JSON.stringify(mockSession);
    keys.forEach((key) => window.localStorage.setItem(key, serialized));
    // Disable ProductTour Joyride overlay
    window.localStorage.setItem('hasSeenTour', 'true');
  }, { sessionRole: role, keys: storageKeys });
}

async function dismissProductTourIfVisible(page: Page) {
  const skipTour = page.getByRole('button', { name: '跳过引导' });
  if (await skipTour.isVisible({ timeout: 1500 }).catch(() => false)) {
    await skipTour.click();
  }
}

/**
 * 通过表单登录获取真实的 Supabase session（配合 setupBusinessMocks 的 API 拦截）
 * 这比 localStorage 注入更可靠，因为 Supabase JS v2 会通过内部流程正确存储 session
 */
export async function loginViaForm(page: Page, role = 'boss') {
  await page.addInitScript(() => window.localStorage.setItem('hasSeenTour', 'true'));
  await page.goto('/login');
  const emailInput = page.getByTestId('login-email-input');
  if (!(await emailInput.isVisible({ timeout: 2000 }).catch(() => false))) {
    await expect(page.getByTestId('sidebar-main')).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId('sidebar-main').getByText(role, { exact: true })).toBeVisible({ timeout: 10000 });
    await dismissProductTourIfVisible(page);
    return;
  }
  const roleButton = page.getByTestId(`role-${role}-btn`);
  if (await roleButton.isVisible().catch(() => false)) {
    await roleButton.click();
  }
  const email = role === 'boss' ? 'test-admin@nexus-ai.com' : `${role}@nexus-ai.com`;
  await emailInput.fill(email);
  await page.getByTestId('login-password-input').fill('TestPass123!');
  await page.getByTestId('login-submit-btn').click();
  // 等待离开登录页
  await expect(page).not.toHaveURL(/.*\/login/, { timeout: 10000 });
  await expect(page.getByTestId('sidebar-main')).toBeVisible({ timeout: 10000 });
  await expect(page.getByTestId('sidebar-main').getByText(role, { exact: true })).toBeVisible({ timeout: 10000 });
  await dismissProductTourIfVisible(page);
}
