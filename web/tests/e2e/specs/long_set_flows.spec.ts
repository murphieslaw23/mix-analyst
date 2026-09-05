import { expect, test } from "@playwright/test";

test.describe("Press Plate entry recovery", () => {
  test("unknown or legacy single-page links resolve to the real Process journey without fabricated archive content", async ({ page }) => {
    await page.goto("/legacy-visualizer");
    await expect(page).toHaveURL(/\/process$/);
    await expect(page.getByRole("heading", { name: "Process audio" })).toBeVisible();
    await expect(page.getByText("SYCO23 — Live Sound-System Transmission 23")).toHaveCount(0);
  });
});
