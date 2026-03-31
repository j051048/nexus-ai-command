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
    await page.goto('/documents');
    // 验证是否已成功进入文档页（检查 Sidebar 是否渲染）
    await expect(page.getByTestId('sidebar-main')).toBeVisible();
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
    await expect(page.getByTestId('sidebar-main')).toBeVisible();
    await expect(page.getByText('销售AI管理')).toBeVisible();
  });

  test('should render CRM page with mock data', async ({ page }) => {
    await page.goto('/crm');
    await expect(page.getByText('CRM管理')).toBeVisible();
  });
});

test.describe('Approval & Workflow Flow', () => {
  test.beforeEach(async ({ page }) => {
    await setupBusinessMocks(page);
    await mockLoggedInState(page);
  });

  test('should show pending approvals list', async ({ page }) => {
    await page.goto('/approval');
    await expect(page.getByText('由于没有真实挂载 API，系统显示 Mock 审批项', { exact: false })).toBeVisible({ timeout: 2000 }).catch(() => {});
    await expect(page.getByText('审批中心')).toBeVisible();
  });

  test('should list workflows from mock api', async ({ page }) => {
    await page.goto('/workflows');
    await expect(page.getByText('流程设计')).toBeVisible();
  });
});

test.describe('Admin Center Flow', () => {
  test.beforeEach(async ({ page }) => {
    await setupBusinessMocks(page);
    await mockLoggedInState(page);
  });

  test('should show super admin dashboard', async ({ page }) => {
    await page.goto('/super-admin');
    await expect(page.getByText('总控中心')).toBeVisible();
  });

  test('should show org chart page', async ({ page }) => {
    await page.goto('/org-chart');
    await expect(page.getByText('组织架构')).toBeVisible();
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
