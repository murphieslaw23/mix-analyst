import { test, expect } from '@playwright/test';

/**
 * Task 2: the library consumes the paginated backend DTO ({ items, total })
 * through the typed contract — never a fabricated mix — with honest
 * loading/empty/error states.
 */
test.describe('Library API contracts', () => {
  test('paginated empty response renders the library empty state with zero fabricated mixes', async ({ page }) => {
    await page.route('**/api/v1/mixes', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0 }),
      });
    });

    await page.goto('/library');
    await expect(page.getByText('Mix Archive')).toBeVisible();
    await expect(page.getByText('No mixes yet.')).toBeVisible();
    await expect(page.getByTestId('track-card')).toHaveCount(0);
    await expect(page.getByTestId('transition-card')).toHaveCount(0);
  });

  test('legacy array response still renders the empty state', async ({ page }) => {
    await page.route('**/api/v1/mixes', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.goto('/library');
    await expect(page.getByText('No mixes yet.')).toBeVisible();
    await expect(page.getByTestId('track-card')).toHaveCount(0);
  });

  test('backend failure surfaces an error with retry', async ({ page }) => {
    await page.route('**/api/v1/mixes', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'engine down' }),
      });
    });

    await page.goto('/library');
    await expect(page.getByText('Could not load mixes')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible();
  });
});
