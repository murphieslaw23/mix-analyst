import { expect, test } from "@playwright/test";

test.describe("Push notification settings", () => {
  test("notification permission is requested only after explicit opt-in", async ({ page }) => {
    await page.addInitScript(() => {
      const notificationMock = class NotificationMock {
        static permission: NotificationPermission = "default";

        static async requestPermission(): Promise<NotificationPermission> {
          const current = Number(sessionStorage.getItem("push-permission-requests") ?? "0");
          sessionStorage.setItem("push-permission-requests", String(current + 1));
          NotificationMock.permission = "denied";
          return "denied";
        }
      };

      Object.defineProperty(window, "Notification", {
        configurable: true,
        value: notificationMock,
      });
    });

    await page.route("**/api/v1/notifications*", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ contentType: "application/json", json: { items: [], total: 0 } });
        return;
      }
      await route.fallback();
    });

    await page.goto("/more/notifications");

    await expect(page.getByRole("button", { name: "Notify me when jobs finish" })).toBeVisible();
    await expect
      .poll(() => page.evaluate(() => Number(sessionStorage.getItem("push-permission-requests") ?? "0")))
      .toBe(0);

    await page.getByRole("button", { name: "Notify me when jobs finish" }).click();

    await expect
      .poll(() => page.evaluate(() => Number(sessionStorage.getItem("push-permission-requests") ?? "0")))
      .toBe(1);
    await expect(page.getByText(/permission/i)).toBeVisible();
  });
});
