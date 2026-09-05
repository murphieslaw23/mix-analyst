import { expect, test } from "@playwright/test";

test("an update activates only after the user chooses to apply the waiting release", async ({ page, request }) => {
  await request.post("/__pwa-test__/reset");
  await page.addInitScript(() => {
    const key = "pwa-test-page-loads";
    sessionStorage.setItem(key, String(Number(sessionStorage.getItem(key) ?? "0") + 1));
  });

  await page.goto("/process");
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload();
  await page.waitForFunction(() => navigator.serviceWorker.controller !== null);

  const updatePrompt = page.getByRole("status", { name: "Application update" });
  await expect(updatePrompt).toBeHidden();

  await request.post("/__pwa-test__/upgrade");
  await page.evaluate(async () => {
    const registration = await navigator.serviceWorker.getRegistration();
    if (!registration) throw new Error("service worker registration was not created");
    await registration.update();
  });

  // The update decision is visible only once the browser has installed a
  // waiting worker and invoked the registered onNeedRefresh callback.
  await expect(updatePrompt).toBeVisible();
  await expect.poll(async () => {
    const response = await request.get("/__pwa-test__/messages");
    return (await response.json()).skipWaitingMessages;
  }).toEqual([]);

  const reloaded = page.waitForFunction(() => Number(sessionStorage.getItem("pwa-test-page-loads")) >= 3);
  await page.getByRole("button", { name: "Update now" }).click();
  await reloaded;

  await expect.poll(async () => {
    const response = await request.get("/__pwa-test__/messages");
    return (await response.json()).skipWaitingMessages;
  }).toEqual(["SKIP_WAITING"]);
});
