import { test, expect, type Page } from '@playwright/test';

/**
 * Tokenized shell + history-API routing.
 * - Mobile (390px) primary nav reaches every route without horizontal overflow.
 * - Direct goto of each route renders its surface (vite + nginx fall back to index.html).
 */
const ROUTES = [
  { path: '/', navName: 'Dashboard', urlPattern: /\/$/, marker: 'Engine status' },
  { path: '/library', navName: 'Library', urlPattern: /\/library$/, marker: 'Mix Archive' },
  { path: '/pipeline', navName: 'Pipeline', urlPattern: /\/pipeline$/, marker: 'Pipeline & Broadcast' },
  { path: '/more', navName: 'More', urlPattern: /\/more$/, marker: 'Impressum (Legal Notice)' },
] as const;

async function mockEmptyLibrary(page: Page): Promise<void> {
  await page.route('**/api/v1/mixes', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0 }),
    });
  });
}

async function assertNoOverflow(page: Page, width: number): Promise<void> {
  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(scrollWidth).toBeLessThanOrEqual(width);
}

test.describe('App shell primary navigation', () => {
  test.beforeEach(async ({ page }) => {
    await mockEmptyLibrary(page);
  });

  test('mobile navigation reaches each primary destination without horizontal overflow', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');

    for (const route of ROUTES) {
      const link = page.getByRole('link', { name: route.navName, exact: true });
      await expect(link).toBeVisible();
      await link.click();
      await expect(page).toHaveURL(route.urlPattern);
      await expect(link).toHaveAttribute('aria-current', 'page');
      await expect(page.getByText(route.marker).first()).toBeVisible();
      await assertNoOverflow(page, 390);
    }
  });

  test('direct goto of each route renders its surface', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });

    for (const route of ROUTES) {
      await page.goto(route.path);
      await expect(page.locator('h1')).toContainText('SYSTEM CORRUPT');
      await expect(page.getByText(route.marker).first()).toBeVisible();
      await assertNoOverflow(page, 390);
    }
  });
});
