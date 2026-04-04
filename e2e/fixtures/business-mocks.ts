/**
 * E2E 测试 Mock 拦截器
 * 
 * 为 core 业务流程提供基础的 API 模拟，支持在无后端环境下运行。
 */

import { Page } from "@playwright/test";

export async function setupBusinessMocks(page: Page) {
  // 1. 拦截 Auth 状态 (已在 01-login-and-auth 中定义，这里作为全局复用)
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

  // 2. 拦截组织信息
  await page.route('**/rest/v1/organizations*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{ id: 'org-123', name: 'Nexus AI Test Org' }])
    });
  });

  // 3. 拦截流程列表 (Workflows)
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

  // 4. 拦截审批中心 (Approvals)
  await page.route('**/rest/v1/approvals*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { id: 'ap-1', title: '加班申请 - 张三', status: 'pending', priority: 'high' }
      ])
    });
  });

  // 5. 拦截销售目标 (Targets)
  await page.route('**/rest/v1/sales_targets*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { id: 'tg-1', target_amount: 1000000, current_amount: 450000, period: '2024-Q1' }
      ])
    });
  });

  // 6. 拦截 CRM 数据
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
 */
export async function mockLoggedInState(page: Page) {
  await page.addInitScript(() => {
    const mockSession = {
      access_token: 'fake-token-content',
      token_type: 'bearer',
      expires_in: 3600,
      refresh_token: 'fake-refresh',
      user: { id: 'test-user-id', email: 'test-admin@nexus-ai.com' }
    };
    window.localStorage.setItem('supabase.auth.token', JSON.stringify(mockSession));
    // 有些版本可能使用这个 key
    window.localStorage.setItem('sb-hztpazmuejgbtixihcgj-auth-token', JSON.stringify(mockSession));
    // Disable ProductTour Joyride overlay
    window.localStorage.setItem('hasSeenTour', 'true');
  });
}
