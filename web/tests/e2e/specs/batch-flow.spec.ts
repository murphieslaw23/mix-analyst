import { test, expect } from '@playwright/test';

/**
 * Task 7: mobile batch review and partial-failure recovery. Selection alone
 * determines the submitted mix ids; failed-item retry re-queues only FAILED
 * children and leaves successful ones untouched.
 */
const MIXES = [
  { id: 'mix-a', title: 'Set A', original_filename: 'set-a.wav' },
  { id: 'mix-b', title: 'Set B', original_filename: 'set-b.wav' },
];

function batchAggregate(status: string, failed: boolean) {
  return {
    id: 'batch-1',
    project_id: 'project-1',
    status,
    total_count: 1,
    queued_count: failed ? 0 : 1,
    running_count: 0,
    completed_count: 0,
    failed_count: failed ? 1 : 0,
    cancelled_count: 0,
    items: [{ job_id: 'job-9', mix_id: 'mix-b', status: failed ? 'FAILED' : 'QUEUED' }],
    created_at: new Date().toISOString(),
  };
}

async function mockBatchApi(page: any, submitted: { body: any }) {
  const state = { retried: false };
  await page.route(
    (url: URL) => url.href.includes('/api/v1'),
    async (route: any) => {
      const req = route.request();
      const path = new URL(req.url()).pathname.replace('/api/v1', '') || '/';
      const method = req.method();
      const json = (status: number, body: unknown) =>
        route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

      if (path === '/mixes' && method === 'GET') {
        return json(200, { items: MIXES, total: MIXES.length });
      }
      if (path === '/batches' && method === 'POST') {
        submitted.body = req.postDataJSON() ?? null;
        return json(201, batchAggregate('QUEUED', false));
      }
      if (path === '/batches/batch-1' && method === 'GET') {
        return json(200, batchAggregate(state.retried ? 'QUEUED' : 'PARTIAL_FAILED', !state.retried));
      }
      if (path === '/jobs/job-9/retry' && method === 'POST') {
        state.retried = true;
        return json(200, { id: 'job-9', mix_id: 'mix-b', job_type: 'ANALYSIS', status: 'QUEUED' });
      }
      if (path.match(/^\/jobs\/[^/]+\/events$/)) {
        return json(404, { detail: 'no stream in tests' });
      }
      if (path === '/jobs/job-9' && method === 'GET') {
        return json(200, {
          id: 'job-9',
          mix_id: 'mix-b',
          job_type: 'ANALYSIS',
          status: state.retried ? 'QUEUED' : 'FAILED',
          progress_percent: 0,
          current_stage: 'Re-queued',
          error_message: null,
          stage_runs: [],
        });
      }
      return json(404, { detail: `unmocked ${method} ${path}` });
    },
  );
}

test.describe('Batch review and recovery', () => {
  test('batch selection determines submitted ids and exposes retry for failed children', async ({
    page,
  }) => {
    const submitted: { body: any } = { body: null };
    await mockBatchApi(page, submitted);
    await page.goto('/batches');

    await page.getByRole('checkbox', { name: 'Set B' }).check();
    await expect(page.getByTestId('batch-selection-count')).toContainText('Selected 1 of 2');

    await page.getByLabel('Max parallelism').fill('3');
    await page.getByRole('button', { name: 'Create batch' }).click();

    await expect(page).toHaveURL(/\/batches\/batch-1$/);
    expect(submitted.body).toEqual({ mix_ids: ['mix-b'], max_parallelism: 3 });

    const retry = page.getByRole('button', { name: 'Retry failed items' });
    await expect(retry).toBeVisible();
    await retry.click();
    await expect(page.getByText('Re-queued 1 failed item')).toBeVisible();
    await expect(page.getByTestId('batch-counts')).toContainText('0 failed');
  });

  test('batch review stays usable at 390px without horizontal overflow', async ({ page }) => {
    const submitted: { body: any } = { body: null };
    await mockBatchApi(page, submitted);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/batches');

    await expect(page.getByRole('checkbox', { name: 'Set A' })).toBeVisible();
    await expect(page.getByRole('checkbox', { name: 'Set B' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Create batch' })).toBeVisible();
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(scrollWidth).toBeLessThanOrEqual(390);
  });
});
