import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
    testDir: './e2e',
    fullyParallel: false, // Run sequentially for auth flow
    forbidOnly: !!process.env.CI,
    retries: 1,
    workers: 1,
    reporter: 'list',
    use: {
        baseURL: process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:4173',
        trace: 'on-first-retry',
        viewport: { width: 1280, height: 720 },
        serviceWorkers: 'block',
    },
    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
    ],
    webServer: {
        command: 'npm run preview',
        port: 4173,
        reuseExistingServer: true,
        timeout: 60 * 1000,
    },
});
