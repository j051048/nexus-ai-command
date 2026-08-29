import { test, expect } from '@playwright/test';
import { setupBusinessMocks, loginViaForm } from './fixtures/business-mocks';

/**
 * E2E Tests: Core Business Flows
 * 验证核心业务模块在已登录状态下的基本渲染与交互
 *
 * 认证策略：通过 form login + API 拦截实现（localStorage 注入在 Supabase JS v2 中不可靠）
 */

test.describe('Document Management Flow', () => {
  test.beforeEach(async ({ page }) => {
    await setupBusinessMocks(page);
    // Disable tour overlay
    await page.addInitScript(() => window.localStorage.setItem('hasSeenTour', 'true'));
    await loginViaForm(page);
  });

  test('should display enterprise knowledge assets for authenticated users', async ({ page }) => {
    await page.goto('/knowledge');
    await page.waitForLoadState('networkidle');
    await expect(page.getByTestId('sidebar-main')).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('heading', { name: 'AI 的企业事实库' })).toBeVisible();
  });
});

test.describe('Sales & CRM Pipeline Flow', () => {
  test.beforeEach(async ({ page }) => {
    await setupBusinessMocks(page);
    await page.addInitScript(() => window.localStorage.setItem('hasSeenTour', 'true'));
    await loginViaForm(page);
  });

  test('should render sales page with mock data', async ({ page }) => {
    await page.goto('/sales');
    await page.waitForLoadState('networkidle');
    await expect(page.getByTestId('sidebar-main')).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('heading', { name: '销售 AI 战绩中心' })).toBeVisible();
  });

  test('should render CRM page with mock data', async ({ page }) => {
    await page.goto('/crm');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: '客户管理' })).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Approval & Workflow Flow', () => {
  test.beforeEach(async ({ page }) => {
    await setupBusinessMocks(page);
    await page.addInitScript(() => window.localStorage.setItem('hasSeenTour', 'true'));
    await loginViaForm(page);
  });

  test('should show pending approvals list', async ({ page }) => {
    await page.goto('/approval');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: '审批中心' })).toBeVisible({ timeout: 10000 });
  });

  test('should keep the low-frequency workflow designer out of the focused launch profile', async ({ page }) => {
    await page.goto('/workflows');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL(/\/dashboard$/, { timeout: 10000 });
    await expect(page.getByRole('heading', { name: '今天最值得推进的业务' })).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Admin Center Flow', () => {
  test.beforeEach(async ({ page }) => {
    await setupBusinessMocks(page);
    await page.addInitScript(() => window.localStorage.setItem('hasSeenTour', 'true'));
    await loginViaForm(page);
  });

  test('should show boss dashboard', async ({ page }) => {
    await page.goto('/boss-dashboard');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('banner').getByText('总控中心')).toBeVisible({ timeout: 10000 });
  });

  test('should show org chart page', async ({ page }) => {
    await page.goto('/org-chart');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: '组织架构管理' })).toBeVisible({ timeout: 10000 });
  });
});

// 保留未登录状态下的重定向检测
test.describe('Guest Redirection', () => {
  test('should redirect unauthenticated users to login', async ({ page }) => {
    const protectedRoutes = ['/sales', '/crm', '/approval', '/finance', '/workflows'];
    for (const route of protectedRoutes) {
      await page.goto(route);
      await expect(page).toHaveURL(/.*\/login/);
    }
  });
});
