import { test, expect } from '@playwright/test';

/**
 * Safe offline/update lifecycle (PWA plan Task 2).
 *
 * These specs run against the dev server, where the generated worker is
 * intentionally disabled: they pin the invariants that must hold there —
 * no controlling worker, no cached API impersonation, no unsolicited
 * update UI. Full offline-shell and update-acceptance coverage requires a
 * preview/production build plus physical devices (see
 * docs/release/pwa-notification-matrix.md).
 */
test.describe('PWA offline safety (dev server)', () => {
  test('no service worker controls the page and API is never served from cache', async ({
    page,
    context,
  }) => {
    await page.goto('/');

    const controller = await page.evaluate(
      () => navigator.serviceWorker?.controller?.scriptURL ?? null,
    );
    expect(controller).toBeNull();

    // Offline: API requests must never resolve to cached mix data.
    // (page.request bypasses the context offline flag, so assert the
    // honest property: no 200 payload, whether the failure is a network
    // error or a proxy 500.)
    await context.setOffline(true);
    const response = await page.request.get('/api/v1/mixes').catch(() => null);
    expect(response === null || response.status() !== 200).toBe(true);

    // Back online the app recovers — nothing poisoned the cache.
    await context.setOffline(false);
    await page.reload();
    await expect(page.locator('h1')).toContainText('SYSTEM CORRUPT');
  });
});
