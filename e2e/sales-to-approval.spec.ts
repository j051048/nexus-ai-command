import { test, expect } from '@playwright/test';
import { setupBusinessMocks, mockLoggedInState } from './fixtures/business-mocks';

/**
 * P2: 模拟真实的 SaaS 业务全路径闭环。
 * 流程：创建销售线索 -> 触发 AI 转化 -> 进入审批中心 -> 财务核对。
 * 此测试直接在 Chromium 浏览器中运行，验证 UI 与 API 的联调。
 */
test.describe('Nexus AI 业务闭环 E2E (销售至审批)', () => {

  test.beforeEach(async ({ page }) => {
    await setupBusinessMocks(page);
    await mockLoggedInState(page);
  });

  test('全流程：销售线索一键转化为审批草案并提交', async ({ page }) => {
    // 1. 登录并进入线索模块 (模拟测试环境登录状态)
    await page.goto('/sales/leads');
    
    // 2. 交互式创建线索
    // 期待：Button aria-label="新建线索"
    await page.getByRole('button', { name: /新建线索/i }).click();
    await page.fill('input[name="customer_name"]', '大厂专供自动化测试客户');
    await page.click('button:has-text("保存")');
    
    // 3. AI 驱动的业务操作 (一键转化)
    // 根据业务逻辑，AI 节点会分析该线索，并提交一份“潜客转合同审批申请”
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
    
    // 6. 验证是否生成了关联审计日志 (P2 深度检查)
    await page.goto('/system/audit-logs');
    await expect(page.locator('tbody tr').first()).toContainText('线索转合同审批申请已触发');
  });
});
