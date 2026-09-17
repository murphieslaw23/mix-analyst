import { test, expect, type Page } from '@playwright/test';

/**
 * PWA plan Task 3 (frontend): durable notification center.
 * Read/dismiss persist across reloads via the API ledger.
 */
interface MockItem {
  id: string;
  job_id: string | null;
  kind: string;
  deep_link: string;
  status: string;
  created_at: string;
  read_at: string | null;
}

function seedItems(): MockItem[] {
  const now = new Date().toISOString();
  return [
    {
      id: 'notif-1',
      job_id: 'job-9',
      kind: 'job.succeeded',
      deep_link: '/jobs/job-9',
      status: 'unread',
      created_at: now,
      read_at: null,
    },
    {
      id: 'notif-2',
      job_id: 'job-8',
      kind: 'job.failed',
      deep_link: '/jobs/job-8',
      status: 'unread',
      created_at: now,
      read_at: null,
    },
  ];
}

async function mockNotificationApi(page: Page, state: { items: MockItem[] }): Promise<void> {
  await page.route(
    (url: URL) => url.href.includes('/api/v1'),
    async (route) => {
      const req = route.request();
      const path = new URL(req.url()).pathname.replace('/api/v1', '') || '/';
      const method = req.method();
      const json = (status: number, body: unknown) =>
        route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

      if (path === '/mixes' && method === 'GET') return json(200, { items: [], total: 0 });
      if (path === '/notifications' && method === 'GET') return json(200, state.items);

      const readMatch = path.match(/^\/notifications\/([^/]+)\/read$/);
      if (readMatch && method === 'POST') {
        const item = state.items.find((n) => n.id === readMatch[1]);
        if (!item) return json(404, { detail: 'Notification not found' });
        item.status = 'read';
        item.read_at = new Date().toISOString();
        return json(200, item);
      }
      const dismissMatch = path.match(/^\/notifications\/([^/]+)\/dismiss$/);
      if (dismissMatch && method === 'POST') {
        const item = state.items.find((n) => n.id === dismissMatch[1]);
        if (!item) return json(404, { detail: 'Notification not found' });
        item.status = 'dismissed';
        item.read_at = new Date().toISOString();
        return json(200, item);
      }
      return json(404, { detail: `unmocked ${method} ${path}` });
    },
  );
}

test.describe('Notification center durability', () => {
  test('notification read state survives a reload', async ({ page }) => {
    const state = { items: seedItems() };
    await mockNotificationApi(page, state);
    await page.goto('/more/notifications');

    await expect(page.getByRole('heading', { name: 'Notifications', exact: true })).toBeVisible();
    await expect(page.getByTestId('notifications-list')).toBeVisible();
    await expect(page.getByTestId('notifications-unread-count')).toContainText('2 unread');

    const first = page.getByTestId('notification-item').first();
    await expect(first).toContainText('Unread');
    await first.getByRole('button', { name: 'Mark as read' }).click();
    await expect(first).toContainText('Read');
    await expect(page.getByTestId('notifications-unread-count')).toContainText('1 unread');

    await page.reload();
    await expect(page.getByRole('heading', { name: 'Notifications', exact: true })).toBeVisible();
    const reloadedFirst = page.getByTestId('notification-item').first();
    await expect(reloadedFirst).toContainText('Read');
    await expect(page.getByTestId('notifications-unread-count')).toContainText('1 unread');

    // Foreground toast links to the remaining unread item accessibly.
    await expect(page.getByTestId('notification-toast')).toBeVisible();
    await expect(
      page.getByTestId('notifications-view').getByTestId('live-region'),
    ).toContainText('Notifications view loaded');
  });

  test('dismissed notifications stay dismissed across reload', async ({ page }) => {
    const state = { items: seedItems() };
    await mockNotificationApi(page, state);
    await page.goto('/more/notifications');

    await expect(page.getByTestId('notification-item')).toHaveCount(2);
    const first = page.getByTestId('notification-item').first();
    await first.getByRole('button', { name: 'Dismiss' }).click();
    await expect(first).toContainText('Dismissed');

    await page.reload();
    await expect(page.getByTestId('notification-item')).toHaveCount(2);
    await expect(page.getByTestId('notification-item').first()).toContainText('Dismissed');
  });
});
