import { test, expect } from '@playwright/test';
import mix30MinFixture from '../fixtures/mix_30min.json' with { type: 'json' };

const MIX_ID = mix30MinFixture.id as string;

/** In-test backend: deterministic responses for every pipeline route. */
async function mockPipelineApi(page: any) {
  const state = {
    jobs: [] as any[],
    jobCounter: 0,
    mastering: null as any,
    masteringGets: 0,
    stems: null as any,
    broadcast: { media_id: MIX_ID, status: 'not_synced' },
  };

  await page.route(
    (url: URL) => url.href.includes('/api/v1'),
    async (route: any) => {
      const req = route.request();
      const path = new URL(req.url()).pathname.replace('/api/v1', '') || '/';
      const method = req.method();
      const json = (status: number, body: unknown) =>
        route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

      if (path === '/mixes' && method === 'GET') return json(200, [mix30MinFixture]);
      if (path === `/mixes/${MIX_ID}` && method === 'GET') return json(200, mix30MinFixture);

      if (path === `/mixes/${MIX_ID}/jobs`) {
        if (method === 'GET') return json(200, state.jobs);
        state.jobCounter += 1;
        const job = {
          id: `job-${state.jobCounter}`,
          mix_id: MIX_ID,
          job_type: 'ANALYSIS',
          status: 'QUEUED',
          progress_percent: 0,
          current_stage: 'Queued',
          error_message: null,
          created_at: new Date().toISOString(),
          started_at: null,
          finished_at: null,
          stage_runs: [],
        };
        state.jobs.unshift(job);
        return json(201, job);
      }

      const jobMatch = path.match(/^\/jobs\/([^/]+)$/);
      if (jobMatch && method === 'GET') {
        const job = state.jobs.find((j) => j.id === jobMatch[1]);
        // Advance each job to RUNNING exactly once: later polls must not
        // clobber CANCELLED/QUEUED states the test asserts on.
        if (job && job.status === 'QUEUED' && !(job as any)._advanced) {
          (job as any)._advanced = true;
          job.status = 'RUNNING';
          job.progress_percent = 45;
          job.current_stage = 'Analyzing audio slice';
        }
        return job ? json(200, job) : json(404, { detail: 'Job not found' });
      }
      const cancelMatch = path.match(/^\/jobs\/([^/]+)\/cancel$/);
      if (cancelMatch && method === 'POST') {
        const job = state.jobs.find((j) => j.id === cancelMatch[1]);
        if (job) job.status = 'CANCELLED';
        return json(200, job ?? { detail: 'Job not found' });
      }
      const retryMatch = path.match(/^\/jobs\/([^/]+)\/retry$/);
      if (retryMatch && method === 'POST') {
        const job = state.jobs.find((j) => j.id === retryMatch[1]);
        if (job) {
          job.status = 'QUEUED';
          job.progress_percent = 0;
        }
        return json(200, job ?? { detail: 'Job not found' });
      }
      if (path.match(/^\/jobs\/[^/]+\/events$/)) {
        // Force the panel's polling fallback deterministically.
        return json(404, { detail: 'no stream in tests' });
      }

      if (path === `/mixes/${MIX_ID}/master` && method === 'POST') {
        state.mastering = {
          job_id: 'mj-1',
          media_id: MIX_ID,
          status: 'queued',
          preset_name: 'Club Broadcast',
          input_measurements: {},
          output_measurements: {},
          gain_adjust_db: 0,
          compliance_passed: false,
          created_at: new Date().toISOString(),
          completed_at: null,
        };
        state.masteringGets = 0;
        return json(202, state.mastering);
      }
      if (path === `/mixes/${MIX_ID}/mastering-report`) {
        if (!state.mastering) return json(404, { detail: 'No mastering job found' });
        state.masteringGets += 1;
        if (state.masteringGets >= 2) {
          state.mastering = {
            ...state.mastering,
            status: 'completed',
            output_measurements: { integrated_lufs: -14.0, true_peak_db: -1.0 },
            gain_adjust_db: 4.5,
            compliance_passed: true,
          };
        }
        return json(200, state.mastering);
      }
      if (path === `/mixes/${MIX_ID}/stems`) {
        if (method === 'POST') {
          state.stems = {
            job_id: 'stem-1',
            media_id: MIX_ID,
            status: 'completed',
            model_name: 'htdemucs',
            stems: { drums: 'd.wav', bass: 'b.wav', other: 'o.wav', vocals: 'v.wav' },
            bassline_analysis: {
              bass_fundamental_hz: 55.0,
              kick_sub_collision_score: 0.28,
              low_end_clarity: 'optimal',
              resonance_peaks: [55.0],
            },
            created_at: new Date().toISOString(),
            completed_at: new Date().toISOString(),
          };
          return json(202, { ...state.stems, status: 'queued' });
        }
        return state.stems ? json(200, state.stems) : json(404, { detail: 'No stems found' });
      }
      if (path === '/mastering/sidechain') {
        return json(409, { detail: 'Sidechain requires a completed stem separation' });
      }
      if (path === '/broadcast/render-stream') {
        state.broadcast = { media_id: MIX_ID, status: 'rendered' };
        return json(202, {
          job_id: 'job-render',
          media_id: MIX_ID,
          status: 'rendering',
          preview_url: null,
          filter_complex: 'showfreqs,showwaves',
          command_args: ['ffmpeg'],
        });
      }
      if (path === `/mixes/${MIX_ID}/broadcast-status`) return json(200, state.broadcast);
      if (path === `/mixes/${MIX_ID}/sync/azuracast`) {
        return json(200, {
          sync_id: 'sync-1',
          media_id: MIX_ID,
          station_id: 'syco23_live',
          status: 'synced',
          playlist_name: 'Underground Freetekno Sets',
          cue_markers_synced: 8,
          created_at: new Date().toISOString(),
          synced_at: new Date().toISOString(),
        });
      }

      if (path === '/uploads' && method === 'POST') {
        const body = req.postDataJSON() ?? {};
        return json(201, {
          upload_id: 'up-1',
          filename: body.filename ?? 'tiny.wav',
          total_size_bytes: body.total_size_bytes ?? 2048,
          chunk_size: body.chunk_size ?? 5242880,
          status: 'PENDING',
        });
      }
      if (path === '/uploads/up-1' && method === 'PATCH') {
        return json(200, {
          upload_id: 'up-1',
          bytes_received: 2048,
          total_size_bytes: 2048,
          progress_percent: 100,
          status: 'UPLOADING',
        });
      }
      if (path === '/uploads/up-1/complete' && method === 'POST') {
        const body = req.postDataJSON() ?? {};
        return json(200, {
          mix_id: 'mix-new',
          media_asset_id: 'asset-new',
          title: body.title ?? 'tiny',
          artist: body.artist ?? null,
          duration_seconds: 60,
          sample_rate: 44100,
          channels: 2,
          codec: 'pcm',
          sha256_hash: 'x',
          status: 'ready',
        });
      }

      return json(404, { detail: `unmocked ${method} ${path}` });
    },
  );
}

test.describe('Pipeline & Broadcast operations', () => {
  test.beforeEach(async ({ page }) => {
    await mockPipelineApi(page);
    await page.goto('/');
    await page.getByText('Pipeline & Broadcast').click();
    await expect(page.getByTestId('pipeline-panel')).toBeVisible();
  });

  test('completes a chunked mix upload', async ({ page }) => {
    await page.getByTestId('pipeline-upload-input').setInputFiles({
      name: 'tiny.wav',
      mimeType: 'audio/wav',
      buffer: Buffer.from(new Uint8Array(2048)),
    });
    await page.getByTestId('pipeline-upload-title').fill('E2E Upload');
    await page.getByTestId('pipeline-upload-start').click();

    await expect(page.getByText(/Upload complete/)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/tiny\.wav.*100%/)).toBeVisible();
  });

  test('dispatches, tracks, cancels and retries an analysis job', async ({ page }) => {
    await page.getByTestId('pipeline-dispatch-analysis').click();
    const row = page.getByTestId('pipeline-job-row').first();
    await expect(row).toBeVisible();

    // Polling fallback picks up RUNNING 45% (QUEUED is transient by design).
    await expect(row).toContainText('RUNNING', { timeout: 10000 });
    await expect(row).toContainText('45%');

    await page.getByTestId('pipeline-job-cancel-job-1').click();
    await expect(row).toContainText('CANCELLED');

    await page.getByTestId('pipeline-job-retry-job-1').click();
    await expect(row).toContainText('QUEUED');
  });

  test('runs mastering with preset and shows the verified report', async ({ page }) => {
    await page.getByTestId('pipeline-master-preset').selectOption('club_broadcast');
    await page.getByTestId('pipeline-master-trigger').click();
    await expect(page.getByTestId('pipeline-master-status')).toContainText('queued');
    await expect(page.getByTestId('pipeline-master-status')).toContainText('-14 LUFS', { timeout: 15000 });
    const download = page.locator('a:has-text("Download master WAV")');
    await expect(download).toBeVisible();
    await expect(download).toHaveAttribute('href', /.*\/mastered/);
  });

  test('separates stems and surfaces the 409 sidechain guard', async ({ page }) => {
    await page.getByTestId('pipeline-stem-trigger').click();
    await expect(page.getByTestId('pipeline-stem-status')).toContainText('55 Hz');

    await page.getByTestId('pipeline-sidechain-trigger').click();
    await expect(page.getByText('Sidechain requires a completed stem separation')).toBeVisible();
  });

  test('renders broadcast and syncs AzuraCast', async ({ page }) => {
    await page.getByTestId('pipeline-render-trigger').click();
    await expect(page.getByTestId('pipeline-broadcast-status')).toContainText('rendered', { timeout: 15000 });

    await page.getByTestId('pipeline-sync-trigger').click();
    await expect(page.getByText('AzuraCast sync recorded.')).toBeVisible();
  });

  test('persists the API key across reloads', async ({ page }) => {
    await page.getByTestId('pipeline-api-key').fill('e2e-secret');
    await page.getByTestId('pipeline-api-key-save').click();
    await page.reload();
    await page.getByText('Pipeline & Broadcast').click();
    await expect(page.getByTestId('pipeline-api-key')).toHaveValue('e2e-secret');
  });
});
