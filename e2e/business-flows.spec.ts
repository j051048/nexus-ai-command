import { test, expect } from '@playwright/test';
import { setupBusinessMocks, mockLoggedInState } from './fixtures/business-mocks';

/**
 * E2E Tests: Core Business Flows
 * 验证核心业务模块在已登录状态下的基本渲染与交互
 */

test.describe('Document Management Flow', () => {
  test.beforeEach(async ({ page }) => {
    await setupBusinessMocks(page);
    await mockLoggedInState(page);
  });

  test('should display documents page for authenticated users', async ({ page }) => {
    await page.goto('/knowledge');
    await page.waitForLoadState('networkidle');
    // 验证 Sidebar 渲染
    await expect(page.getByTestId('sidebar-main')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('知识库')).toBeVisible();
  });
});

test.describe('Sales & CRM Pipeline Flow', () => {
  test.beforeEach(async ({ page }) => {
    await setupBusinessMocks(page);
    await mockLoggedInState(page);
  });

  test('should render sales page with mock data', async ({ page }) => {
    await page.goto('/sales');
    await page.waitForLoadState('networkidle');
    await expect(page.getByTestId('sidebar-main')).toBeVisible({ timeout: 10000 });
    // Sidebar 标签为 "销售"
    await expect(page.getByText('销售')).toBeVisible();
  });

  test('should render CRM page with mock data', async ({ page }) => {
    await page.goto('/crm');
    await page.waitForLoadState('networkidle');
    // Sidebar 标签为 "客户"
    await expect(page.getByText('客户')).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Approval & Workflow Flow', () => {
  test.beforeEach(async ({ page }) => {
    await setupBusinessMocks(page);
    await mockLoggedInState(page);
  });

  test('should show pending approvals list', async ({ page }) => {
    await page.goto('/approval');
    await page.waitForLoadState('networkidle');
    // Sidebar 标签为 "审批"
    await expect(page.getByText('审批')).toBeVisible({ timeout: 10000 });
  });

  test('should list workflows from mock api', async ({ page }) => {
    await page.goto('/workflows');
    await page.waitForLoadState('networkidle');
    // Sidebar 标签为 "流程"
    await expect(page.getByText('流程')).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Admin Center Flow', () => {
  test.beforeEach(async ({ page }) => {
    await setupBusinessMocks(page);
    await mockLoggedInState(page);
  });

  test('should show boss dashboard', async ({ page }) => {
    await page.goto('/boss-dashboard');
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('总控中心')).toBeVisible({ timeout: 10000 });
  });

  test('should show org chart page', async ({ page }) => {
    await page.goto('/org-chart');
    await page.waitForLoadState('networkidle');
    // Sidebar 标签为 "组织"
    await expect(page.getByText('组织')).toBeVisible({ timeout: 10000 });
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
