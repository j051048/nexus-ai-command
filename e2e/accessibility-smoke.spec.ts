import { expect, test } from '@playwright/test';

test.describe('Accessibility smoke gates', () => {
  test('login page has keyboard and naming basics', async ({ page }) => {
    await page.goto('/login');

    const interactive = page.locator('button, a[href], input, textarea, select');
    await expect(interactive.first()).toBeVisible({ timeout: 10000 });

    const unnamedControls = await page
      .locator('button, a[href], input, textarea, select')
      .evaluateAll((nodes) =>
        nodes
          .map((node) => {
            const element = node as HTMLElement;
            const text = element.innerText?.trim();
            const aria = element.getAttribute('aria-label')?.trim();
            const labelledBy = element.getAttribute('aria-labelledby')?.trim();
            const title = element.getAttribute('title')?.trim();
            const placeholder = element.getAttribute('placeholder')?.trim();
            const type = element.getAttribute('type');
            const isHidden = type === 'hidden' || element.getAttribute('aria-hidden') === 'true';
            const hasName = Boolean(text || aria || labelledBy || title || placeholder);
            return isHidden || hasName ? null : element.outerHTML.slice(0, 160);
          })
          .filter(Boolean),
      );

    expect(unnamedControls).toEqual([]);

    const duplicateIds = await page.locator('[id]').evaluateAll((nodes) => {
      const seen = new Set<string>();
      const duplicates = new Set<string>();
      for (const node of nodes) {
        const id = (node as HTMLElement).id;
        if (!id) continue;
        if (seen.has(id)) duplicates.add(id);
        seen.add(id);
      }
      return [...duplicates];
    });
    expect(duplicateIds).toEqual([]);
  });
});
