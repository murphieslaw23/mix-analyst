import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 45 * 1000,
  expect: {
    timeout: 10 * 1000,
  },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [
    ['html', { open: 'never' }],
    ['list']
  ],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    headless: true,
  },
  projects: [
    {
      // This is the only desktop browser engine in this matrix: Chromium.
      name: 'Desktop-Chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
      },
    },
    {
      // Viewport/user-agent emulation only; this does not constitute WebKit coverage.
      name: 'Chromium-iPad-viewport',
      use: {
        ...devices['iPad (gen 7)'],
        browserName: 'chromium',
        viewport: { width: 768, height: 1024 },
      },
    },
    {
      // Viewport/user-agent emulation only; this does not constitute Mobile Safari coverage.
      name: 'Chromium-iPhone-viewport',
      use: {
        ...devices['iPhone 14'],
        browserName: 'chromium',
        viewport: { width: 390, height: 844 },
      },
    },
  ],
  webServer: {
    command: 'npx vite --host 127.0.0.1 --port 3000',
    url: 'http://127.0.0.1:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 60 * 1000,
  },
});
