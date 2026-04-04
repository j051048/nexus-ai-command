import { test, expect } from '@playwright/test';

// 这是一个极其关键的黄金链路测试，用来检测登录与鉴权路由能否防住系统内外的攻击与白屏
test.describe('第一条生命链路：登录、鉴权与面板导航', () => {

// TODO: 根据实际系统的启动端口和环境变量调整
  const BASE_URL = process.env.BASE_URL || 'http://localhost:4173';

  test.beforeEach(async ({ page }) => {
    // Disable Joyride guides for testing
    await page.addInitScript(() => {
        window.localStorage.setItem('hasSeenTour', 'true');
    });
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
            user: { id: 'test-user-id', email: 'test-admin@nexus-ai.com', user_metadata: { role: 'boss' } }
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

    // 拦截 profile API（AuthContext.fetchUserData 调用）
    await page.route('**/api/users/profile*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 200,
          data: {
            user: {
              id: 'test-user-id',
              email: 'test-admin@nexus-ai.com',
              name: 'E2E Admin',
              role: 'boss',
              avatar_url: null
            }
          }
        })
      });
    });

    // 拦截 RPC 调用
    await page.route('**/rest/v1/rpc/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(null)
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

    // 等待跳转离开登录页
    await expect(page).not.toHaveURL(/.*\/login/, { timeout: 10000 });

    // 验证侧边栏渲染（DashboardLayout 的标志）
    await expect(page.getByTestId('sidebar-main')).toBeVisible({ timeout: 10000 });
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
    await expect(page).not.toHaveURL(/.*\/login/, { timeout: 10000 });

    // 清理 token
    await page.evaluate(() => localStorage.clear());
    await page.reload();

    await expect(page).toHaveURL(/.*\/login/);
  });
});
