import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
    test.beforeEach(async ({ page }) => {
        // Disable Joyride guides to prevent overlay interception
        await page.addInitScript(() => {
            window.localStorage.setItem('nexus-joyride-seen', 'true');
        });
        await page.goto('/login');
    });

    test('should display login page correctly', async ({ page }) => {
        // Target the brand header specifically
        await expect(page.getByRole('heading', { name: 'Project Nexus', exact: true }).first()).toBeVisible();
        await expect(page.getByTestId('login-email-input')).toBeVisible();
        await expect(page.getByTestId('login-password-input')).toBeVisible();
        await expect(page.getByTestId('login-submit-btn')).toBeVisible();
    });

    test('should toggle between login and register tabs', async ({ page }) => {
        // Switch to Register (using exact text match for tabs)
        await page.getByRole('tab', { name: /注册/ }).click();
        await expect(page.getByTestId('register-name-input')).toBeVisible();
        await expect(page.getByTestId('register-email-input')).toBeVisible();
        await expect(page.getByTestId('register-password-input')).toBeVisible();

        // Switch back to Login
        await page.getByRole('tab', { name: /登录/ }).click();
        await expect(page.getByTestId('login-email-input')).toBeVisible();
    });

    test('should show error message for invalid credentials', async ({ page }) => {
        await page.getByTestId('login-email-input').fill('wrong@example.com');
        await page.getByTestId('login-password-input').fill('wrongpassword');
        await page.getByTestId('login-submit-btn').click();

        // Wait for Supabase to respond and toast to render via portal
        await expect(page.getByText('登录失败').first()).toBeVisible({ timeout: 15000 });
    });
});

test.describe('Main Application Navigation (Employee)', () => {
    test('should redirect unauthenticated users to login', async ({ page }) => {
        // Clear tokens to ensure unauthenticated state
        await page.context().clearCookies();
        await page.goto('/dashboard');
        await expect(page).toHaveURL(/.*\/login/);
    });
});
