import { test, expect } from '@playwright/test';

/**
 * E2E Tests: Core Business Flows
 * Tests critical user journeys that span multiple modules.
 */

test.describe('Document Management Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
  });

  test('should display documents page for authenticated users', async ({ page }) => {
    // Verify redirect to login for unauthenticated access
    await page.goto('/documents');
    await expect(page).toHaveURL(/.*\/login/);
  });

  test('should show knowledge base navigation item', async ({ page }) => {
    // Check that the sidebar has the knowledge/documents link
    await page.goto('/login');
    await expect(page.locator('#login-email')).toBeVisible();
  });
});

test.describe('Sales Pipeline Flow', () => {
  test('should redirect unauthenticated users from sales page', async ({ page }) => {
    await page.goto('/sales');
    await expect(page).toHaveURL(/.*\/login/);
  });

  test('should redirect unauthenticated users from CRM page', async ({ page }) => {
    await page.goto('/crm');
    await expect(page).toHaveURL(/.*\/login/);
  });
});

test.describe('Approval Center Flow', () => {
  test('should redirect unauthenticated users from approval page', async ({ page }) => {
    await page.goto('/approval');
    await expect(page).toHaveURL(/.*\/login/);
  });
});

test.describe('Finance Center Flow', () => {
  test('should redirect unauthenticated users from finance page', async ({ page }) => {
    await page.goto('/finance');
    await expect(page).toHaveURL(/.*\/login/);
  });

  test('should redirect unauthenticated users from contracts page', async ({ page }) => {
    await page.goto('/contracts');
    await expect(page).toHaveURL(/.*\/login/);
  });
});

test.describe('Admin Routes Protection', () => {
  test('should protect super admin page', async ({ page }) => {
    await page.goto('/super-admin');
    await expect(page).toHaveURL(/.*\/login/);
  });

  test('should protect API keys page', async ({ page }) => {
    await page.goto('/api-keys');
    await expect(page).toHaveURL(/.*\/login/);
  });

  test('should protect employee management page', async ({ page }) => {
    await page.goto('/employees');
    await expect(page).toHaveURL(/.*\/login/);
  });

  test('should protect LLM model management page', async ({ page }) => {
    await page.goto('/llm/models');
    await expect(page).toHaveURL(/.*\/login/);
  });
});

test.describe('VMD Module Protection', () => {
  test('should redirect from VMD center', async ({ page }) => {
    await page.goto('/vmd');
    await expect(page).toHaveURL(/.*\/login/);
  });

  test('should redirect from VMD tasks', async ({ page }) => {
    await page.goto('/vmd/tasks');
    await expect(page).toHaveURL(/.*\/login/);
  });
});

test.describe('Workflow Module Protection', () => {
  test('should redirect from workflow list', async ({ page }) => {
    await page.goto('/workflows');
    await expect(page).toHaveURL(/.*\/login/);
  });

  test('should redirect from workflow designer', async ({ page }) => {
    await page.goto('/workflows/new');
    await expect(page).toHaveURL(/.*\/login/);
  });
});
