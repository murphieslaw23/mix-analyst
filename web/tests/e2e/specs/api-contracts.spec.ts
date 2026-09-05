import { expect, test } from "@playwright/test";

test.describe("Mix API contracts", () => {
  test("library reads a paginated response and never renders a fabricated mix", async ({ page }) => {
    await page.route("**/api/v1/mixes", async (route) => {
      await route.fulfill({ contentType: "application/json", json: { items: [], total: 0 } });
    });

    await page.goto("/library");
    await expect(page.getByRole("heading", { name: "No completed masters yet" })).toBeVisible();
    await expect(page.getByText("SYCO23 — Live Sound-System Transmission 23")).toHaveCount(0);
  });

  test("library keeps a failed request visible until an explicit retry succeeds", async ({ page }) => {
    let serviceIsAvailable = false;
    await page.route("**/api/v1/mixes", async (route) => {
      if (!serviceIsAvailable) {
        await route.fulfill({ status: 503, contentType: "application/json", json: { detail: "internal diagnostic" } });
        return;
      }
      await route.fulfill({ contentType: "application/json", json: { items: [], total: 0 } });
    });

    await page.goto("/library");
    await expect(page.getByRole("alert")).toContainText("Service temporarily unavailable");
    serviceIsAvailable = true;
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByRole("heading", { name: "No completed masters yet" })).toBeVisible();
  });
});
