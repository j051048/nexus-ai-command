import { expect, test } from '@playwright/test';
import { fulfillJson, loginViaForm, setupBusinessMocks } from './fixtures/business-mocks';

for (const width of [1440, 390]) {
  test(`first delivery shows real progress at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await setupBusinessMocks(page);
    await page.addInitScript(() => {
      localStorage.setItem('hasSeenTour', 'true');
      localStorage.setItem('nexus_onboarding_completed', 'true');
    });
    await page.route(/.*profile.*/, (route) => fulfillJson(route, {
      success: true, data: { user: {
        id: 'test-user-id', user_id: 'test-user-id', name: 'Test user', role: 'boss',
        email: 'test-admin@nexus-ai.com', organization_id: 'org-a',
      } },
    }));
    let unavailable = false;
    await page.route('**/api/onboarding/readiness', (route) => fulfillJson(route,
      unavailable ? { message: 'unavailable' } : { success: true, data: {
        organization_id: 'org-a', user_id: 'test-user-id', uploaded: true, searchable: false,
        facts_confirmed: false, artifact_ready: false, artifact_id: null,
      } }, unavailable ? 503 : 200));
    await loginViaForm(page);
    await page.goto('/boss-dashboard');
    const progress = page.getByRole('region', { name: '首次交付进度' });
    await expect(progress.getByText('资料整理中')).toBeVisible();
    await expect(progress.getByText('已完成', { exact: true })).toHaveCount(1);
    await expect(progress.getByRole('link', { name: '上传企业资料' })).toHaveAttribute('href', '/documents');
    await expect(progress.getByRole('link', { name: '交付首份方案' })).toHaveAttribute('href', '/growth/solutions');
    expect(await progress.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    await progress.screenshot({ path: testInfo.outputPath(`launch-${width}.png`) });
    unavailable = true;
    await progress.getByRole('button', { name: '刷新交付进度' }).click();
    await expect(progress.getByRole('alert')).toContainText('暂时无法读取进度');
    await expect(progress.getByRole('button', { name: '重试', exact: true })).toBeVisible();
  });
}
