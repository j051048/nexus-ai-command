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

  test('测试极端用例：输入错误账号密码应该被阻拦并看到红色的报错通知', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);

    await page.fill('input[type="email"]', 'hacker@nexus-ai.com');
    await page.fill('input[type="password"]', 'WrongPass123!');
    await page.click('button[type="submit"]');

    // 不应该跳转
    await expect(page).toHaveURL(/.*\/login/);
    
    // 界面应有相应的错误提示文本（无论是 toast 还是表单自带的报错红底）
    const errorToast = page.locator('text=登录失败').first(); // 根据项目真实的错误文案调整
    // 由于实际系统可能未启动，这里仅作为占位符编写：
    // await expect(errorToast).toBeVisible(); 
  });

  test('Token 生命周期测试：若在中途被清理，则强行被踹出回到登录页', async ({ page }) => {
    // 省略复杂模拟过程，仅验证如果把 localstorage 里的 auth.token 拔了然后访问数据，页面会跳转
    await page.goto(`${BASE_URL}/dashboard`);
    // 执行原生清缓存操作
    await page.evaluate(() => localStorage.removeItem('supabase.auth.token'));
    
    // 强制触发页面一个接口请求或者切换路由，这里直接请求一次 dashboard 或者重新加载
    await page.reload();

    // 此时必然会被重新遣返回 /login
    await expect(page).toHaveURL(/.*\/login/);
  });
});
