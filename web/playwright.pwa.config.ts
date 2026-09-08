import { defineConfig, devices } from "@playwright/test";
import { fileURLToPath } from "node:url";

const webDirectory = fileURLToPath(new URL(".", import.meta.url));

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
    // Always exercise the bundle produced for this run. Reusing a developer's
    // preview process can leave PWA lifecycle tests pointed at stale assets.
    command: "pnpm build && node tests/support/pwa-preview-server.mjs",
    cwd: webDirectory,
    url: "http://127.0.0.1:4173",
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
