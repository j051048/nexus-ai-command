import { test, expect } from '@playwright/test';
import { setupBusinessMocks, mockLoggedInState } from './fixtures/business-mocks';

/**
 * P2: 模拟真实的 SaaS 业务全路径闭环。
 * 流程：创建销售线索 -> 触发 AI 转化 -> 进入审批中心 -> 财务核对。
 *
 * NOTE: 该功能尚未实现（/sales/leads 路由、新建线索按钮、AI转化等均不存在），
 * 暂时 skip，等对应功能上线后再启用。
 */
test.describe('Nexus AI 业务闭环 E2E (销售至审批)', () => {

  test.beforeEach(async ({ page }) => {
    await setupBusinessMocks(page);
    await mockLoggedInState(page);
  });

  test.skip('全流程：销售线索一键转化为审批草案并提交', async ({ page }) => {
    // 1. 登录并进入线索模块 (模拟测试环境登录状态)
    await page.goto('/sales/leads');

    // 2. 交互式创建线索
    await page.getByRole('button', { name: /新建线索/i }).click();
    await page.fill('input[name="customer_name"]', '大厂专供自动化测试客户');
    await page.click('button:has-text("保存")');

    // 3. AI 驱动的业务操作 (一键转化)
    await page.click('text=大厂专供自动化测试客户');
    const aiBtn = page.locator('text=AI转化为合同并报审');
    await aiBtn.click();

    // 等待跳转或成功提示
    await expect(page.locator('text=审批单已提交')).toBeVisible();

    // 4. 跳转至审批中心验证
    await page.goto('/approval/center');
    await expect(page.locator('table')).toContainText('大厂专供自动化测试客户');

    // 5. 状态验证
    const statusBadge = page.locator('tr:has-text("大厂专供自动化测试客户") .badge');
    await expect(statusBadge).toContainText('待审批');

    // 6. 验证是否生成了关联审计日志
    await page.goto('/system/audit-logs');
    await expect(page.locator('tbody tr').first()).toContainText('线索转合同审批申请已触发');
  });
});
