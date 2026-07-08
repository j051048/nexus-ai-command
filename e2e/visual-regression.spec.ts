import { expect, test, type Page } from '@playwright/test';
import { mockLoggedInState, setupBusinessMocks } from './fixtures/business-mocks';

const CORE_VISUAL_ROUTES = [
  { name: 'dashboard', path: '/dashboard' },
  { name: 'crm', path: '/crm' },
  { name: 'approval', path: '/approval' },
  { name: 'contracts', path: '/contracts' },
  { name: 'ai-operating-system', path: '/ai-operating-system' },
];

async function prepareVisualPage(page: Page) {
  await setupBusinessMocks(page);
  await page.addInitScript(() => {
    window.localStorage.setItem('hasSeenTour', 'true');
    window.localStorage.setItem('nexus-sidebar-collapsed', 'false');
  });
  await mockLoggedInState(page, 'boss');
}

test.describe('core page visual regression snapshots', () => {
  test.skip(
    process.env.RUN_VISUAL_REGRESSION !== '1',
    'Set RUN_VISUAL_REGRESSION=1 after approving/updating snapshots.'
  );

  for (const route of CORE_VISUAL_ROUTES) {
    test(`${route.name} stays visually stable`, async ({ page }) => {
      await prepareVisualPage(page);
      await page.goto(route.path);
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toContainText('Application error');
      await expect(page.locator('body')).not.toContainText('Something went wrong');
      await expect(page).toHaveScreenshot(`${route.name}.png`, {
        fullPage: true,
        animations: 'disabled',
        maxDiffPixelRatio: 0.015,
      });
    });
  }
});
