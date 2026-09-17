import { test, expect } from '@playwright/test';

/**
 * Notification click routing (PWA plan Task 5): pushes carry only safe
 * same-origin deep links. Unknown routes fall back to the center instead
 * of opening an arbitrary URL.
 */
test.describe('Notification click routing', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/notifications', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });
  });

  test('invalid notification route falls back to notification center', async ({
    page,
  }) => {
    await page.goto('/more/notifications?fromPush=unknown');
    await expect(page.getByRole('heading', { name: 'Notifications' })).toBeVisible();
  });

  test('valid job deep link offers a safe onward link', async ({ page }) => {
    await page.goto('/more/notifications?fromPush=/jobs/job-1');
    await expect(page.getByRole('heading', { name: 'Notifications' })).toBeVisible();
    await expect(page.getByRole('link', { name: /job-1|open|view/i }).first()).toBeVisible();
  });
});
