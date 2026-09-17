import { test, expect } from '@playwright/test';

/**
 * Safe offline lifecycle (PWA plan Task 2).
 *
 * Dual-mode: against `vite dev` (no worker by design) it pins no-control
 * and no cached-API impersonation; against the preview bundle (test:pwa)
 * it verifies the precached app shell renders offline while operational
 * traffic still fails instead of resolving stale data.
 */
test.describe('PWA offline safety', () => {
  test('offline shell renders without caching API traffic', async ({
    page,
    context,
  }) => {
    await page.goto('/');
    // A worker becomes controller for the open tab after a navigation.
    await page.reload();
    const controlled = await page.evaluate(
      () => navigator.serviceWorker?.controller !== null,
    );

    await context.setOffline(true);
    if (controlled) {
      await page.reload();
      await expect(page.locator('h1')).toContainText('SYSTEM CORRUPT');
      const apiResult = await page.evaluate(async () => {
        try {
          await fetch('/api/v1/mixes');
          return 'resolved';
        } catch {
          return 'network-error';
        }
      });
      expect(apiResult).toBe('network-error');
    } else {
      // page.request bypasses the context offline flag: assert the honest
      // property (no 200 payload) however the failure surfaces.
      const response = await page.request.get('/api/v1/mixes').catch(() => null);
      expect(response === null || response.status() !== 200).toBe(true);
    }

    // Back online the app recovers — nothing poisoned the cache.
    await context.setOffline(false);
    await page.reload();
    await expect(page.locator('h1')).toContainText('SYSTEM CORRUPT');
  });
});
