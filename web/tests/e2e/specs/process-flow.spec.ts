import { test, expect } from '@playwright/test';

/**
 * Task 3: Press Plate Process journey — reducer-first upload state machine
 * over the backend upload-session protocol (POST /uploads, PATCH 5MB chunk,
 * POST /complete), with validation, progress, and hand-off to /pipeline.
 */
async function mockProcessApi(page: any, opts: { failInit?: boolean } = {}) {
  await page.route(
    (url: URL) => url.href.includes('/api/v1'),
    async (route: any) => {
      const req = route.request();
      const path = new URL(req.url()).pathname.replace('/api/v1', '') || '/';
      const method = req.method();
      const json = (status: number, body: unknown) =>
        route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

      if (path === '/mixes' && method === 'GET') return json(200, { items: [], total: 0 });
      if (path === '/uploads' && method === 'POST') {
        if (opts.failInit) return json(500, { detail: 'engine down' });
        const body = req.postDataJSON() ?? {};
        return json(201, {
          upload_id: 'up-1',
          filename: body.filename ?? 'take.wav',
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
          title: body.title ?? 'take',
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

const wavFile = {
  name: 'take.wav',
  mimeType: 'audio/wav',
  buffer: Buffer.from(new Uint8Array(2048)),
};

test.describe('Process upload journey', () => {
  test('valid selection shows progress then navigates to Pipeline with the persisted mix', async ({
    page,
  }) => {
    await mockProcessApi(page);
    await page.goto('/process');

    await page.getByLabel('Choose audio').setInputFiles(wavFile);
    await expect(page.getByText('Ready to process', { exact: true })).toBeVisible();

    await page.getByRole('button', { name: 'Start mastering' }).click();
    await expect(page.getByRole('progressbar')).toBeVisible();
    // Hand-off lands scoped to the persisted mix, where dispatch lives.
    await expect(page).toHaveURL(/\/pipeline\?mix=mix-new/);
    await expect(page.getByRole('heading', { name: 'Analysis Jobs' })).toBeVisible();
  });

  test('unsupported file types are rejected with guidance', async ({ page }) => {
    await mockProcessApi(page);
    await page.goto('/process');

    await page.getByLabel('Choose audio').setInputFiles({
      name: 'notes.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('not audio'),
    });
    await expect(page.getByRole('alert')).toContainText('Unsupported file type');
    await expect(page.getByRole('button', { name: 'Start mastering' })).toHaveCount(0);
  });

  test('upload failure surfaces an error with recovery back to selection', async ({ page }) => {
    await mockProcessApi(page, { failInit: true });
    await page.goto('/process');

    await page.getByLabel('Choose audio').setInputFiles(wavFile);
    await page.getByRole('button', { name: 'Start mastering' }).click();
    await expect(page.getByRole('alert')).toContainText(/Upload failed/);

    await page.getByRole('button', { name: 'Try again' }).click();
    await expect(page.getByText('Ready to process', { exact: true })).toBeVisible();
  });
});
