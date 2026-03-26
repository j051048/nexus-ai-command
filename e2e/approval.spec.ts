import { test, expect } from '@playwright/test';

test('审批流程E2E', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Nexus')).toBeVisible();
});
