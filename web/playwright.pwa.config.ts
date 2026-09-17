import { defineConfig, devices } from '@playwright/test';

/**
 * Production PWA lifecycle assertions run against the built bundle:
 * Vite development mode intentionally produces no revisioned precache,
 * so offline-shell and update behavior can only be verified on preview.
 */
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: /pwa-(offline|update)\.spec\.ts/,
  timeout: 45 * 1000,
  expect: {
    timeout: 10 * 1000,
  },
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    headless: true,
    ...devices['Desktop Chrome'],
  },
  webServer: {
    command: 'pnpm build && pnpm preview --port 4173 --strictPort --host 127.0.0.1',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: false,
    timeout: 180 * 1000,
  },
});
