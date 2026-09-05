import { expect, test } from "@playwright/test";

test("the generated worker waits for an explicit SKIP_WAITING message", async ({ page }) => {
  await page.goto("/process");
  const worker = await page.request.get("/service-worker.js");
  const source = await worker.text();

  expect(worker.ok()).toBeTruthy();
  expect(source).toContain("SKIP_WAITING");
  // The generated bundle has one activation call, inside the message handler;
  // it must not activate merely because a new build installed.
  expect(source.match(/skipWaiting\(\)/g)).toHaveLength(1);
});
