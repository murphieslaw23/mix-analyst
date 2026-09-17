import { test, expect } from '@playwright/test';

/**
 * Task 4: Jobs list/detail with replay-aware progress, retry, cancellation.
 * SSE is forced into its polling fallback (events -> 404) for determinism;
 * the UI converges on authoritative GET state either way.
 */
const MIX = { id: 'mix-1', title: 'Set A', original_filename: 'set-a.wav' };

function runningJob() {
  return {
    id: 'job-9',
    mix_id: MIX.id,
    job_type: 'ANALYSIS',
    status: 'RUNNING',
    progress_percent: 45,
    current_stage: 'Analyzing audio slice',
    error_message: null,
    stage_runs: [],
  };
}

async function mockJobsApi(page: any) {
  const state = { failedStatus: 'FAILED' };
  await page.route(
    (url: URL) => url.href.includes('/api/v1'),
    async (route: any) => {
      const req = route.request();
      const path = new URL(req.url()).pathname.replace('/api/v1', '') || '/';
      const method = req.method();
      const json = (status: number, body: unknown) =>
        route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

      if (path === '/mixes' && method === 'GET') {
        return json(200, { items: [MIX], total: 1 });
      }
      if (path === `/mixes/${MIX.id}` && method === 'GET') return json(200, MIX);
      if (path === `/mixes/${MIX.id}/jobs` && method === 'GET') return json(200, [runningJob()]);
      if (path === '/jobs/job-9' && method === 'GET') return json(200, runningJob());
      if (path === '/jobs/job-9/cancel' && method === 'POST') {
        return json(200, { ...runningJob(), status: 'CANCELLED', error_message: 'Cancelled by user request' });
      }
      if (path === '/jobs/job-failed' && method === 'GET') {
        return json(200, {
          id: 'job-failed',
          mix_id: MIX.id,
          job_type: 'ANALYSIS',
          status: state.failedStatus,
          progress_percent: state.failedStatus === 'FAILED' ? 62 : 0,
          current_stage: state.failedStatus === 'FAILED' ? 'Mastering' : 'Re-queued',
          error_message:
            state.failedStatus === 'FAILED' ? 'Mastering failed: clipping above 0 dBFS' : null,
          stage_runs: [],
        });
      }
      if (path === '/jobs/job-failed/retry' && method === 'POST') {
        state.failedStatus = 'QUEUED';
        return json(200, {
          id: 'job-failed',
          mix_id: MIX.id,
          job_type: 'ANALYSIS',
          status: 'QUEUED',
          progress_percent: 0,
          current_stage: 'Re-queued',
          error_message: null,
          stage_runs: [],
        });
      }
      if (path.match(/^\/jobs\/[^/]+\/events$/)) {
        return json(404, { detail: 'no stream in tests' });
      }
      return json(404, { detail: `unmocked ${method} ${path}` });
    },
  );
}

test.describe('Jobs progress and recovery', () => {
  test('jobs list for a mix shows stage progress with links into detail', async ({ page }) => {
    await mockJobsApi(page);
    await page.goto('/jobs?mix=mix-1');

    const row = page.getByTestId('job-row').first();
    await expect(row).toContainText('ANALYSIS');
    await expect(row.getByRole('progressbar')).toBeVisible();
    const detailLink = row.getByRole('link', { name: 'ANALYSIS' });
    await expect(detailLink).toHaveAttribute('href', '/jobs/job-9');

    await detailLink.click();
    await expect(page).toHaveURL(/\/jobs\/job-9$/);
    await expect(page.getByRole('button', { name: 'Cancel job' })).toBeVisible();
  });

  test('cancelling a running job settles it without destroying state', async ({ page }) => {
    await mockJobsApi(page);
    await page.goto('/jobs/job-9');

    await expect(page.getByRole('progressbar')).toBeVisible();
    await page.getByRole('button', { name: 'Cancel job' }).click();
    await expect(page.getByTestId('status-badge')).toContainText('CANCELLED');
    await expect(page.getByRole('button', { name: 'Retry job' })).toBeVisible();
  });

  test('a failed job retains the stage error and exposes retry', async ({ page }) => {
    await mockJobsApi(page);
    await page.goto('/jobs/job-failed');

    await expect(page.getByTestId('job-detail-error')).toContainText('Mastering failed');
    await expect(page.getByRole('button', { name: 'Retry job' })).toBeVisible();

    await page.getByRole('button', { name: 'Retry job' }).click();
    await expect(page.getByTestId('status-badge')).toContainText('QUEUED');
  });

  test('without a mix context the picker lists owned mixes', async ({ page }) => {
    await mockJobsApi(page);
    await page.goto('/jobs');

    const picker = page.getByRole('link', { name: 'Open jobs for Set A' });
    await expect(picker).toBeVisible();
    await picker.click();
    await expect(page).toHaveURL(/\/jobs\?mix=mix-1$/);
  });
});
