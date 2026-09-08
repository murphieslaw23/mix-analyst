import { expect, test } from "@playwright/test";

test("offline navigation uses the precached app shell without caching API traffic", async ({ page, context }) => {
  await page.goto("/process");
  await page.evaluate(() => navigator.serviceWorker.ready);

  // A worker becomes controller for this open tab after its next navigation.
  await page.reload();
  await page.waitForFunction(() => navigator.serviceWorker.controller !== null);

  await context.setOffline(true);
  await page.reload();

  await expect(page.getByRole("heading", { name: "Process" })).toBeVisible();
  await expect(page.getByText(/You’re offline/i)).toBeVisible();
  await expect(page.evaluate(async () => {
    try {
      await fetch("/api/v1/mixes");
      return "resolved";
    } catch {
      return "network-error";
    }
  })).resolves.toBe("network-error");
});
