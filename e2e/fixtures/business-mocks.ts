/**
 * E2E 测试 Mock 拦截器
 *
 * 为 core 业务流程提供基础的 API 模拟，支持在无后端环境下运行。
 */

import { Page, expect } from "@playwright/test";

export async function setupBusinessMocks(page: Page) {
  // 1. 拦截 Auth token 请求（login + refresh）
  await page.route('**/auth/v1/token*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'fake-token-content',
        token_type: 'bearer',
        expires_in: 3600,
        refresh_token: 'fake-refresh',
        user: {
          id: 'test-user-id',
          email: 'test-admin@nexus-ai.com',
          user_metadata: { role: 'boss', name: 'E2E Admin' },
          app_metadata: { provider: 'email' }
        }
      })
    });
  });

  // 2. 拦截 Auth user 信息
  await page.route('**/auth/v1/user*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'test-user-id',
        email: 'test-admin@nexus-ai.com',
        user_metadata: { role: 'boss', name: 'E2E Admin' },
        app_metadata: { provider: 'email' }
      })
    });
  });

  // 3. 拦截用户 profile API
  await page.route('**/api/users/profile*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 200,
        data: {
          user: {
            id: 'test-user-id',
            email: 'test-admin@nexus-ai.com',
            name: 'E2E Admin',
            role: 'boss',
            avatar_url: null
          }
        }
      })
    });
  });

  // 4. 拦截 RPC 调用 (get_user_role, is_super_admin)
  await page.route('**/rest/v1/rpc/get_user_role*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ role: 'boss' })
    });
  });

  await page.route('**/rest/v1/rpc/is_super_admin*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(false)
    });
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
}

/**
 * 快速注入登录状态至 localStorage
 * Supabase JS v2 使用 sb-{project-ref}-auth-token 作为 storage key
 * access_token 必须是可解码的 JWT 格式，否则 Supabase 会认为 session 无效
 */
export async function mockLoggedInState(page: Page, _role?: string) {
  await page.addInitScript(() => {
    // 构造一个可解码的 fake JWT（Supabase JS v2 会 base64 decode 来检查 exp）
    const now = Math.floor(Date.now() / 1000);
    const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
      .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    const payload = btoa(JSON.stringify({
      sub: 'test-user-id',
      email: 'test-admin@nexus-ai.com',
      role: 'authenticated',
      aud: 'authenticated',
      exp: now + 3600,
      iat: now
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
        email: 'test-admin@nexus-ai.com',
        role: 'authenticated',
        user_metadata: { role: 'boss', name: 'E2E Admin' },
        app_metadata: { provider: 'email' }
      }
    };
    // Supabase JS v2 storage key format
    window.localStorage.setItem(
      'sb-hztpazmuejgbtixihcgj-auth-token',
      JSON.stringify(mockSession)
    );
    // Disable ProductTour Joyride overlay
    window.localStorage.setItem('hasSeenTour', 'true');
  });
}

/**
 * 通过表单登录获取真实的 Supabase session（配合 setupBusinessMocks 的 API 拦截）
 * 这比 localStorage 注入更可靠，因为 Supabase JS v2 会通过内部流程正确存储 session
 */
export async function loginViaForm(page: Page) {
  await page.goto('/login');
  await page.getByTestId('login-email-input').fill('test-admin@nexus-ai.com');
  await page.getByTestId('login-password-input').fill('TestPass123!');
  await page.getByTestId('login-submit-btn').click();
  // 等待离开登录页
  await expect(page).not.toHaveURL(/.*\/login/, { timeout: 10000 });
}
