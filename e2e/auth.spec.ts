import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/login');
    });

    test('should display login page correctly', async ({ page }) => {
        await expect(page.locator('h1')).toContainText('Project Nexus');
        await expect(page.locator('#login-email')).toBeVisible();
        await expect(page.locator('#login-password')).toBeVisible();
        await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible();
    });

    test('should toggle between login and register tabs', async ({ page }) => {
        // Switch to Register
        await page.getByRole('tab', { name: '注册' }).click();
        await expect(page.locator('#reg-name')).toBeVisible();
        await expect(page.locator('#reg-email')).toBeVisible();
        await expect(page.locator('#reg-password')).toBeVisible();

        // Switch back to Login
        await page.getByRole('tab', { name: '登录' }).click();
        await expect(page.locator('#login-email')).toBeVisible();
    });

    test('should show error message for invalid credentials', async ({ page }) => {
        await page.locator('#login-email').fill('wrong@example.com');
        await page.locator('#login-password').fill('wrongpassword');
        await page.getByRole('button', { name: '登录', exact: true }).click();

        // Wait for Supabase to respond and toast to render via portal
        // Use longer timeout since network request + toast animation takes time
        await expect(page.getByText('登录失败').first()).toBeVisible({ timeout: 15000 });
    });
});

test.describe('Main Application Navigation (Employee)', () => {
    test('should redirect unauthenticated users to login', async ({ page }) => {
        await page.goto('/');
        await expect(page).toHaveURL(/.*\/login/);
    });
});
