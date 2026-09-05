import { defineConfig, devices } from "@playwright/test";

/**
 * PWA lifecycle assertions must use the production bundle: Vite development
 * mode intentionally does not produce a revisioned precache.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: /pwa-(offline|update)\.spec\.ts/,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4173",
    headless: true,
    ...devices["Desktop Chrome"],
  },
  webServer: {
    command: "pnpm build && pnpm preview -- --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
