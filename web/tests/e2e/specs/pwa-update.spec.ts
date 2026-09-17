import { test, expect } from '@playwright/test';

/**
 * Update control (PWA plan Task 2): a new version never activates itself.
 * On a fresh load with no waiting worker there is no update banner; the
 * banner only appears off a worker waiting event after user-visible builds.
 */
test.describe('PWA update control', () => {
  test('fresh load shows no unsolicited update prompt', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('h1')).toContainText('SYSTEM CORRUPT');
    await expect(page.getByText('A new version is ready')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Apply update' })).toHaveCount(0);
  });
});
