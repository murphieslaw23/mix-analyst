import { test, expect, type Page } from '@playwright/test';

/**
 * Product UI Task 5: results library + honest A/B playback.
 * - A/B switch toggles aria-pressed and the real <audio> source.
 * - Rejected play() surfaces an honest error, never fake playing state.
 * - Artifact download links point at the mastered download.
 * - Missing master renders an honest empty state.
 */
const MIX = {
  id: 'mix-1',
  title: 'Set A',
  original_filename: 'set-a.wav',
  duration_seconds: 180,
  bpm: 140,
  audio_url: '/audio/original.wav',
  tracks: [],
  transitions: [],
};

const ARTIFACTS = [
  {
    id: 'art-1',
    role: 'master',
    key: 'masters/mix-1.wav',
    sha256: 'abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789',
    algorithm_version: 'v1',
    media_type: 'audio/wav',
    byte_length: 123456,
    created_at: new Date().toISOString(),
  },
];

const REPORT = {
  job_id: 'mj-1',
  media_id: MIX.id,
  status: 'completed',
  preset_name: 'Club Broadcast',
  input_measurements: { integrated_lufs: -18.5, true_peak_db: -0.5 },
  output_measurements: { integrated_lufs: -14.0, true_peak_db: -1.0 },
  gain_adjust_db: 4.5,
  compliance_passed: true,
  created_at: new Date().toISOString(),
  completed_at: new Date().toISOString(),
};

async function mockLibraryApi(page: Page, opts: { withMaster: boolean }): Promise<void> {
  await page.route(
    (url: URL) => url.href.includes('/api/v1'),
    async (route) => {
      const req = route.request();
      const path = new URL(req.url()).pathname.replace('/api/v1', '') || '/';
      const method = req.method();
      const json = (status: number, body: unknown) =>
        route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

      if (path === '/mixes' && method === 'GET') {
        return json(200, { items: [MIX], total: 1 });
      }
      if (path === `/mixes/${MIX.id}` && method === 'GET') return json(200, MIX);
      if (path === `/mixes/${MIX.id}/peaks` && method === 'GET') return json(200, { peaks: [] });
      if (path === `/mixes/${MIX.id}/analysis` && method === 'GET') return json(200, {});
      if (path === `/mixes/${MIX.id}/artifacts` && method === 'GET') {
        return json(200, opts.withMaster ? ARTIFACTS : []);
      }
      if (path === `/mixes/${MIX.id}/mastering-report` && method === 'GET') {
        if (opts.withMaster) return json(200, REPORT);
        return json(404, { detail: 'No mastering job found for this mix' });
      }
      return json(404, { detail: `unmocked ${method} ${path}` });
    },
  );
}

test.describe('Results library and honest A/B playback', () => {
  test('A/B switch toggles the active source on the real audio element', async ({ page }) => {
    await mockLibraryApi(page, { withMaster: true });
    await page.goto('/');

    const panel = page.getByTestId('mix-result-panel');
    await expect(panel).toBeVisible();
    const player = page.getByTestId('ab-player');
    await expect(player).toBeVisible();

    const originalBtn = page.getByRole('button', { name: 'Original', exact: true });
    const masteredBtn = page.getByRole('button', { name: 'Mastered', exact: true });
    await expect(originalBtn).toBeVisible();
    await expect(masteredBtn).toBeVisible();

    await masteredBtn.click();
    await expect(masteredBtn).toHaveAttribute('aria-pressed', 'true');
    await expect(originalBtn).toHaveAttribute('aria-pressed', 'false');
    await expect(page.getByTestId('ab-audio')).toHaveAttribute('src', /mastered/);
    await expect(page.getByTestId('ab-current')).toContainText('Mastered');

    await originalBtn.click();
    await expect(originalBtn).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByTestId('ab-audio')).toHaveAttribute('src', /original/);

    // Keyboard-operable: focus and activate via keyboard.
    await masteredBtn.focus();
    await page.keyboard.press('Enter');
    await expect(masteredBtn).toHaveAttribute('aria-pressed', 'true');
  });

  test('rejected playback surfaces an honest error and never fakes playing', async ({
    page,
  }) => {
    await page.addInitScript(() => {
      // @ts-expect-error stub for deterministic rejection
      HTMLMediaElement.prototype.play = () =>
        Promise.reject(new DOMException('blocked', 'NotAllowedError'));
    });
    await mockLibraryApi(page, { withMaster: true });
    await page.goto('/');

    await expect(page.getByTestId('ab-player')).toBeVisible();
    await page.getByRole('button', { name: 'Mastered', exact: true }).click();
    await page.getByRole('button', { name: 'Play mastered audio' }).click();

    await expect(
      page.getByText('Playback needs a browser gesture or supported audio'),
    ).toBeVisible();
    // Honest state stays paused — no fake Playing indicator.
    await expect(page.getByTestId('ab-state')).toContainText('Paused');
  });

  test('artifact list exposes a mastered download link and loudness', async ({ page }) => {
    await mockLibraryApi(page, { withMaster: true });
    await page.goto('/');

    await expect(page.getByTestId('mix-result-panel')).toBeVisible();
    await expect(page.getByTestId('artifact-list')).toBeVisible();
    await expect(page.getByTestId('artifact-row')).toHaveCount(1);

    const download = page.getByRole('link', { name: 'Download mastered audio' });
    await expect(download).toBeVisible();
    await expect(download).toHaveAttribute('href', /\/mixes\/mix-1\/mastered/);

    await expect(page.getByTestId('loudness-summary')).toContainText('-14.0 LUFS');
  });

  test('missing master renders an honest empty state without fake success', async ({
    page,
  }) => {
    await mockLibraryApi(page, { withMaster: false });
    await page.goto('/');

    await expect(page.getByTestId('mix-result-panel')).toBeVisible();
    await expect(page.getByText('No mastered audio yet')).toBeVisible();
    await expect(page.getByTestId('master-empty-hint')).toContainText(
      'No completed master found for this mix',
    );
    await expect(page.getByText('No derived artifacts yet.')).toBeVisible();
    await expect(page.getByTestId('loudness-summary')).toContainText(
      'Loudness not measured yet.',
    );
    // No fake download when there is no master.
    await expect(page.getByRole('link', { name: 'Download mastered audio' })).toHaveCount(0);
  });
});
