import { test, expect } from '@playwright/test';

// 这是一个极其关键的黄金链路测试，用来检测登录与鉴权路由能否防住系统内外的攻击与白屏
test.describe('第一条生命链路：登录、鉴权与面板导航', () => {

// TODO: 根据实际系统的启动端口和环境变量调整
  const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';

  test.beforeEach(async ({ page }) => {
    // 拦截鉴权相关的 API 请求，确保即使后端没挂也能跑通逻辑
    await page.route('**/auth/v1/token*', async (route) => {
      const email = route.request().postDataJSON()?.email;
      if (email === 'test-admin@nexus-ai.com') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            access_token: 'fake-token',
            token_type: 'bearer',
            expires_in: 3600,
            refresh_token: 'fake-refresh-token',
            user: { id: 'test-user-id', email: 'test-admin@nexus-ai.com' }
          })
        });
      } else {
        await route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'invalid_grant', error_description: 'Invalid login credentials' })
        });
      }
    });

    // 拦截获取用户信息的请求
    await page.route('**/auth/v1/user', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'test-user-id', email: 'test-admin@nexus-ai.com', user_metadata: { role: 'boss' } })
      });
    });
  });

  test('如果用户未登录，访问 /dashboard 必须被重定向回 /login', async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await expect(page).toHaveURL(/.*\/login/);
  });

  test('允许测试人员输入账号密码并验证通过后正确落入大盘', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);

    await page.getByTestId('login-email-input').fill('test-admin@nexus-ai.com');
    await page.getByTestId('login-password-input').fill('TestPass123!');
    await page.getByTestId('login-submit-btn').click();

    // 等待跳转到首页或 dashboardLayout 渲染
    await expect(page).toHaveURL(new RegExp(`${BASE_URL}/?`));
    
    // 验证侧边栏或主内容渲染（App.tsx 中首页是 DashboardLayout）
    await expect(page.getByTestId('sidebar-main')).toBeVisible();
  });

  test('测试极端用例：输入错误账号密码应该被阻拦并看到红色的报错通知', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);

    await page.getByTestId('login-email-input').fill('hacker@nexus-ai.com');
    await page.getByTestId('login-password-input').fill('WrongPass123!');
    await page.getByTestId('login-submit-btn').click();

    await expect(page).toHaveURL(/.*\/login/);
    await expect(page.getByText('登录失败')).toBeVisible();
  });

  test('Token 生命周期测试：若在中途被清理，则强行被踹出回到登录页', async ({ page }) => {
    // 先模拟登录成功状态
    await page.goto(`${BASE_URL}/login`);
    await page.getByTestId('login-email-input').fill('test-admin@nexus-ai.com');
    await page.getByTestId('login-password-input').fill('TestPass123!');
    await page.getByTestId('login-submit-btn').click();
    await expect(page).not.toHaveURL(/.*\/login/);

    // 清理 token
    await page.evaluate(() => localStorage.clear());
    await page.reload();

    await expect(page).toHaveURL(/.*\/login/);
  });
});
