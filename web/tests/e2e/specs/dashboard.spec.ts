import { test, expect, type Page } from '@playwright/test';
import { assertNoHorizontalOverflow } from '../helpers';

/**
 * Dashboard start page: engine status, quick actions, recent sets, and
 * items needing attention — all deep-linked into the workflow surfaces.
 */
const MIXES = [
  { id: 'mix-a', title: 'Set A', original_filename: 'set-a.wav', duration_seconds: 1800, bpm: 150 },
  { id: 'mix-b', title: 'Set B', original_filename: 'set-b.wav', duration_seconds: 900 },
];

const FAILED_JOB = {
  id: 'job-1',
  mix_id: 'mix-a',
  job_type: 'ANALYSIS',
  status: 'FAILED',
  progress_percent: 62,
  current_stage: 'Mastering',
  error_message: 'Mastering failed: clipping above 0 dBFS',
  stage_runs: [],
};

const NOTIFS = [
  {
    id: 'notif-1',
    job_id: 'job-1',
    kind: 'job.failed',
    deep_link: '/jobs/job-1',
    status: 'unread',
    created_at: new Date().toISOString(),
    read_at: null,
  },
];

async function mockDashboardApi(page: Page): Promise<void> {
  await page.route(
    (url: URL) => url.href.includes('/api/v1'),
    async (route) => {
      const req = route.request();
      const path = new URL(req.url()).pathname.replace('/api/v1', '') || '/';
      const method = req.method();
      const json = (status: number, body: unknown) =>
        route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

      if (path === '/mixes' && method === 'GET') {
        return json(200, { items: MIXES, total: MIXES.length });
      }
      if (path === '/mixes/mix-a/jobs' && method === 'GET') return json(200, [FAILED_JOB]);
      if (path === '/mixes/mix-b/jobs' && method === 'GET') return json(200, []);
      if (path === '/notifications' && method === 'GET') return json(200, NOTIFS);
      return json(404, { detail: `unmocked ${method} ${path}` });
    },
  );
}

test.describe('Dashboard start page', () => {
  test('engine status, recent sets, and attention items link into the workflow', async ({
    page,
  }) => {
    await mockDashboardApi(page);
    await page.goto('/');

    await expect(page.getByRole('heading', { name: 'Engine status' })).toBeVisible();
    await expect(page.getByTestId('dashboard-sets-count')).toContainText('2');
    await expect(page.getByTestId('dashboard-failed-count')).toContainText('1');
    await expect(page.getByTestId('dashboard-unread-count')).toContainText('1');

    const recent = page.getByTestId('dashboard-recent').getByRole('link', { name: 'Set A' });
    await expect(recent).toHaveAttribute('href', '/library?mix=mix-a');
    await recent.click();
    await expect(page).toHaveURL(/\/library\?mix=mix-a/);
  });

  test('failed jobs surface with recovery links', async ({ page }) => {
    await mockDashboardApi(page);
    await page.goto('/');

    const row = page.getByTestId('dashboard-failed-row').first();
    await expect(row).toContainText('ANALYSIS failed');
    await expect(row.getByRole('link', { name: 'ANALYSIS failed' })).toHaveAttribute(
      'href',
      '/jobs/job-1',
    );
  });

  test('quick actions reach the workflow surfaces', async ({ page }) => {
    await mockDashboardApi(page);
    await page.goto('/');

    await page.getByRole('link', { name: 'Process audio' }).click();
    await expect(page).toHaveURL(/\/process$/);
  });

  test('empty archive shows the getting-started checklist', async ({ page }) => {
    await page.route('**/api/v1/mixes', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0 }),
      });
    });
    await page.route('**/api/v1/notifications', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');

    await expect(page.getByText('No sets in the archive yet.')).toBeVisible();
    await expect(page.getByText('Getting started')).toBeVisible();
    await expect(
      page.getByRole('link', { name: 'Go to Process audio' }),
    ).toBeVisible();
    await assertNoHorizontalOverflow(page, 390);
  });
});
