import { expect, test } from "@playwright/test";

test.describe("Press Plate audio entry", () => {
  test("opens the Process journey without pretending an archived mix is selected", async ({ page }) => {
    await page.goto("/");

    await expect(page).toHaveURL(/\/process$/);
    await expect(page.getByRole("heading", { name: "Process audio" })).toBeVisible();
    await expect(page.getByText("SYCO23 — Live Sound-System Transmission 23")).toHaveCount(0);
  });
});
