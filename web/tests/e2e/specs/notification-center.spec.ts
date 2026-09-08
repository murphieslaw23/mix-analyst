import { expect, test } from "@playwright/test";

type NotificationFixture = {
  id: string;
  job_id: string | null;
  kind: string;
  title: string;
  body: string | null;
  deep_link: string;
  read_at: string | null;
  dismissed_at: string | null;
  created_at: string;
};

function unreadNotification(): NotificationFixture {
  return {
    id: "notification-1",
    job_id: "job-1",
    kind: "job.succeeded",
    title: "Mastering complete",
    body: "Your finished audio is ready in the Library.",
    deep_link: "/jobs/job-1",
    read_at: null,
    dismissed_at: null,
    created_at: "2030-01-01T00:00:00Z",
  };
}

async function mockNotificationList(
  page: import("@playwright/test").Page,
  getNotification: () => NotificationFixture | null,
) {
  await page.route("**/api/v1/notifications*", async (route) => {
    if (route.request().method() !== "GET") {
      await route.fallback();
      return;
    }
    const notification = getNotification();
    await route.fulfill({
      contentType: "application/json",
      json: { items: notification ? [notification] : [], total: notification ? 1 : 0 },
    });
  });
}

test.describe("Notification center", () => {
  test("notification read state survives a reload", async ({ page }) => {
    let notification = unreadNotification();
    await mockNotificationList(page, () => notification);
    await page.route("**/api/v1/notifications/notification-1/read", async (route) => {
      notification = { ...notification, read_at: "2030-01-01T00:01:00Z" };
      await route.fulfill({ contentType: "application/json", json: notification });
    });

    await page.goto("/more/notifications");
    await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
    await expect(page.getByText("Unread", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Mark as read" }).click();
    await expect(page.getByText("Read", { exact: true })).toBeVisible();

    await page.reload();
    await expect(page.getByText("Read", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Mark as read" })).toHaveCount(0);
  });

  test("dismissed notifications leave the active center", async ({ page }) => {
    let notification: NotificationFixture | null = unreadNotification();
    await mockNotificationList(page, () => notification);
    await page.route("**/api/v1/notifications/notification-1/dismiss", async (route) => {
      const dismissed = { ...notification!, dismissed_at: "2030-01-01T00:02:00Z" };
      notification = null;
      await route.fulfill({ contentType: "application/json", json: dismissed });
    });

    await page.goto("/more/notifications");
    await expect(page.getByText("Mastering complete")).toBeVisible();
    await page.getByRole("button", { name: "Dismiss" }).click();
    await expect(page.getByText("Mastering complete")).toHaveCount(0);
    await expect(page.getByText("No notifications yet", { exact: true })).toBeVisible();
  });
});
