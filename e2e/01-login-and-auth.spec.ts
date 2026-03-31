import { test, expect } from '@playwright/test';

// 这是一个极其关键的黄金链路测试，用来检测登录与鉴权路由能否防住系统内外的攻击与白屏
test.describe('第一条生命链路：登录、鉴权与面板导航', () => {

// TODO: 根据实际系统的启动端口和环境变量调整
  const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';

  test('如果用户未登录，访问 /dashboard 必须被重定向回 /login', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    // 无论框架有多高大上，这里没 token 必须被拦截回去
    await expect(page).toHaveURL(/.*\/login/);
  });

  test('允许测试人员输入账号密码并验证通过后正确落入大盘', async ({ page }) => {
    // 1. 到达登录页
    await page.goto(`${BASE_URL}/login`);

    // 假设你有通用的 input placeholder
    await page.fill('input[type="email"]', 'test-admin@nexus-ai.com');
    await page.fill('input[type="password"]', 'TestPass123!');

    // 2. 点击登录按钮
    await page.click('button[type="submit"]');

    // 3. 拦截 API 如果是纯离线也可以通过 playwright route mock 掉，
    // 这里我们假设后端能正常吐出 200 或者我们 mock 登录成功
    
    // 4. 等待跳转
    await page.waitForURL(/.*\/dashboard/);

    // 5. 验证是不是真大盘：可以找侧边栏、或者是特定的图表容器
    const heading = await page.locator('h1', { hasText: /Dashboard/i }).first();
    await expect(heading).toBeVisible();
  });
});
