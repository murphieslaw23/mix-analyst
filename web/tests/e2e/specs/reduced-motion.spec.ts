import { test, expect, type Page } from '@playwright/test';
import mix30MinFixture from '../fixtures/mix_30min.json' with { type: 'json' };
import { assertNoHorizontalOverflow } from '../helpers';

/**
 * Product UI Task 6: reduced-motion regression coverage.
 *
 * The whole file runs with `reducedMotion: 'reduce'` (context option). There
 * is no `data-motion` rig surface in the app, so per the plan constraints
 * this spec asserts operability only, plus that the existing
 * `prefers-reduced-motion` CSS override collapses the animated utility
 * classes the app actually ships (`animate-pulse` skeletons,
 * `transition-all` progress fills).
 */
test.use({ reducedMotion: 'reduce' });

const MIX_ID: string = (mix30MinFixture as { id: string }).id;

const RUNNING_JOB = {
  id: 'job-a11y-run',
  mix_id: MIX_ID,
  job_type: 'ANALYSIS',
  status: 'RUNNING',
  progress_percent: 45,
  current_stage: 'Analyzing audio slice',
  error_message: null,
  stage_runs: [],
};

async function mockReducedApi(page: Page, opts: { mixesDelayMs?: number } = {}): Promise<void> {
  await page.route(
    (url: URL) => url.href.includes('/api/v1'),
    async (route: any) => {
      const req = route.request();
      const path = new URL(req.url()).pathname.replace('/api/v1', '') || '/';
      const method = req.method();
      const json = (status: number, body: unknown) =>
        route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

      if (path === '/mixes' && method === 'GET') {
        if (opts.mixesDelayMs) await new Promise((r) => setTimeout(r, opts.mixesDelayMs));
        return json(200, [mix30MinFixture]);
      }
      if (path === `/mixes/${MIX_ID}` && method === 'GET') return json(200, mix30MinFixture);
      if (path === `/mixes/${MIX_ID}/peaks` && method === 'GET') return json(200, { peaks: [] });
      if (path === `/mixes/${MIX_ID}/analysis` && method === 'GET') return json(200, {});
      if (path === `/mixes/${MIX_ID}/artifacts` && method === 'GET') return json(200, []);
      if (path === `/mixes/${MIX_ID}/mastering-report` && method === 'GET') {
        return json(404, { detail: 'No mastering job found for this mix' });
      }
      if (path === `/mixes/${MIX_ID}/jobs` && method === 'GET') return json(200, [RUNNING_JOB]);
      if (path === '/jobs/job-a11y-run' && method === 'GET') return json(200, RUNNING_JOB);
      if (path.match(/^\/jobs\/[^/]+\/events$/)) return json(404, { detail: 'no stream in tests' });
      return json(404, { detail: `unmocked ${method} ${path}` });
    },
  );
}

test.describe('Reduced motion', () => {
  test('the reduced-motion media query is active', async ({ page }) => {
    await mockReducedApi(page);
    await page.goto('/');
    const matches = await page.evaluate(
      () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    );
    expect(matches).toBe(true);
  });

  test('animated utilities collapse under reduced motion', async ({ page }) => {
    // Hold the library in its loading state so the pulse skeleton is observable.
    await mockReducedApi(page, { mixesDelayMs: 600 });
    await page.goto('/jobs');

    const skeleton = page.getByTestId('skeleton').first();
    await expect(skeleton).toBeVisible();
    const pulse = await skeleton.evaluate((el) => {
      const inner = el.querySelector('.animate-pulse') as HTMLElement;
      const cs = getComputedStyle(inner ?? el);
      return { animationDuration: cs.animationDuration };
    });
    // Tailwind's pulse ships 2s; the app-shell override collapses it near zero.
    expect(parseFloat(pulse.animationDuration)).toBeLessThan(0.01);

    // Progress fills keep their semantics with collapsed transitions.
    await mockReducedApi(page);
    await page.goto('/jobs/job-a11y-run');
    const progress = page.getByRole('progressbar', { name: 'Job progress for job-a11y-run' });
    await expect(progress).toBeVisible();
    const fill = await progress.evaluate((el) => {
      const inner = el.firstElementChild as HTMLElement;
      return getComputedStyle(inner ?? el).transitionDuration;
    });
    expect(parseFloat(fill)).toBeLessThan(0.01);
    await expect(progress).toHaveAttribute('aria-valuenow', '45');
  });

  test('core library flows work with reduced motion', async ({ page }) => {
    await mockReducedApi(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');

    // Key controls render without depending on any transition.
    await expect(page.getByRole('navigation', { name: 'Primary' })).toBeVisible();
    const slider = page.getByRole('slider', { name: /waveform position/ });
    await expect(slider).toBeVisible();
    await expect(page.getByText('Detected Tracks (8)')).toBeVisible();
    await expect(page.getByText('Harmonic Transitions (7)')).toBeVisible();

    // Select the mix, seek with the keyboard, toggle playback.
    await page.getByRole('button', { name: '30Min Live Sound-System Assault' }).click();
    await expect(page.getByText('Position: 00:00 / 30:00')).toBeVisible();

    await slider.focus();
    await page.keyboard.press('ArrowRight');
    await expect(page.getByText('Position: 00:05 / 30:00')).toBeVisible();

    await page.getByRole('button', { name: 'PLAY', exact: true }).click();
    await expect(page.getByRole('button', { name: 'PAUSE', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'PAUSE', exact: true }).click();
    await expect(page.getByRole('button', { name: 'PLAY', exact: true })).toBeVisible();

    await assertNoHorizontalOverflow(page, 390);
  });

  test('process and job surfaces render without motion dependence', async ({ page }) => {
    await mockReducedApi(page);
    await page.setViewportSize({ width: 390, height: 844 });

    await page.goto('/process');
    await expect(page.getByLabel('Choose audio')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Process audio' })).toBeVisible();
    await assertNoHorizontalOverflow(page, 390);

    await page.goto('/jobs/job-a11y-run');
    await expect(page.getByRole('progressbar')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Cancel job' })).toBeVisible();
    await assertNoHorizontalOverflow(page, 390);
  });
});
