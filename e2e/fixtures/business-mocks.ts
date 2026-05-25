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
