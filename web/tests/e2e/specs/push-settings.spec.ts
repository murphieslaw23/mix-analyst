import { test, expect, type Page } from '@playwright/test';

/**
 * PWA plan Task 4 (frontend): explicit Push opt-in + safe deep links.
 * - Notification.requestPermission is NEVER called before the explicit
 *   opt-in click (permission stays 'default' until then).
 * - Invalid deep links fall back to the notification center.
 */
const VAPID_KEY = 'dGVzdC12YXBpZC1rZXktZm9yLXRlc3RpbmctMTIzNDU2Nzg5MDEyMw==';

async function mockPushApi(page: Page): Promise<void> {
  await page.route(
    (url: URL) => url.href.includes('/api/v1'),
    async (route) => {
      const req = route.request();
      const path = new URL(req.url()).pathname.replace('/api/v1', '') || '/';
      const method = req.method();
      const json = (status: number, body: unknown) =>
        route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

      if (path === '/mixes' && method === 'GET') return json(200, { items: [], total: 0 });
      if (path === '/notifications' && method === 'GET') return json(200, []);
      if (path === '/push/subscriptions' && method === 'POST') {
        return route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 'sub-1',
            endpoint_hash: 'hash-1',
            created_at: new Date().toISOString(),
          }),
        });
      }
      if (path === '/push/subscriptions/sub-1' && method === 'DELETE') {
        return route.fulfill({ status: 204, body: '' });
      }
      return json(404, { detail: `unmocked ${method} ${path}` });
    },
  );
}

async function stubPushBrowser(page: Page): Promise<void> {
  await page.addInitScript(() => {
    (window as unknown as { __permCalls?: number }).__permCalls = 0;
    try {
      // Pin permission to 'default' so the no-prompt assertion is deterministic
      // in headless Chromium (which otherwise reports 'denied').
      Object.defineProperty(Notification, 'permission', {
        value: 'default',
        configurable: true,
      });
      Notification.requestPermission = function () {
        (window as unknown as { __permCalls: number }).__permCalls += 1;
        return Promise.resolve('granted' as NotificationPermission);
      };
    } catch {
      // If Notification is unavailable the component shows unsupported honestly.
    }
    try {
      if (!('PushManager' in window)) {
        (window as unknown as { PushManager: unknown }).PushManager = class {};
      }
      const fakeRegistration = {
        pushManager: {
          subscribe: () =>
            Promise.resolve({
              toJSON: () => ({
                endpoint: 'https://push.example.test/endpoint-1',
                keys: { p256dh: 'test-p256dh', auth: 'test-auth' },
              }),
            }),
          getSubscription: () => Promise.resolve(null),
        },
      };
      Object.defineProperty(navigator, 'serviceWorker', {
        value: { ready: Promise.resolve(fakeRegistration) },
        configurable: true,
      });
    } catch {
      // Push stub is best-effort; permission-timing assertions still hold.
    }
  });
}

async function permCalls(page: Page): Promise<number> {
  return page.evaluate(() => (window as unknown as { __permCalls?: number }).__permCalls ?? 0);
}

test.describe('Push enrollment and safe notification routes', () => {
  test('notification permission is not requested until the user enables job notifications', async ({
    page,
  }) => {
    await stubPushBrowser(page);
    await mockPushApi(page);
    await page.goto('/more/notifications');

    await expect(
      page.getByRole('button', { name: 'Notify me when jobs finish' }),
    ).toBeVisible();
    await expect(page.getByTestId('push-vapid-key')).toBeVisible();

    // No permission prompt on page load: count stays zero and state is default.
    expect(await permCalls(page)).toBe(0);
    expect(await page.evaluate(() => Notification.permission)).toBe('default');
    await expect(page.getByTestId('push-permission')).toContainText('default');

    await page.getByTestId('push-vapid-key').fill(VAPID_KEY);
    expect(await permCalls(page)).toBe(0);

    await page.getByRole('button', { name: 'Notify me when jobs finish' }).click();

    // Exactly one explicit request after the click, then enrollment succeeds.
    await expect.poll(() => permCalls(page)).toBe(1);
    await expect(page.getByText('Job notifications enabled for this device.')).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Unsubscribe from job notifications' }),
    ).toBeVisible();
  });

  test('invalid notification route falls back to notification center', async ({ page }) => {
    await mockPushApi(page);
    await page.goto('/more/notifications?fromPush=/evil/phish');

    await expect(page.getByRole('heading', { name: 'Notifications', exact: true })).toBeVisible();
    await expect(page.getByTestId('notifications-view')).toBeVisible();
    await expect(page.getByText('No notifications yet.')).toBeVisible();
  });
});
