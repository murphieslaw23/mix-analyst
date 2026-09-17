import { test, expect } from '@playwright/test';
import mix30MinFixture from '../fixtures/mix_30min.json' with { type: 'json' };

test.describe('Waveform detail: zoom and engine-region inspection', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/mixes', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([mix30MinFixture]),
      });
    });

    await page.route(`**/api/v1/mixes/${mix30MinFixture.id}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mix30MinFixture),
      });
    });

    await page.goto('/library');
  });

  test('zoom controls narrow and reset the visible window', async ({ page }) => {
    const canvas = page.getByTestId('waveform-canvas');
    await expect(canvas).toBeVisible();
    await canvas.scrollIntoViewIfNeeded();

    await expect(page.getByText('Window: 00:00 – 30:00')).toBeVisible();

    await page.getByTestId('waveform-zoom-in').click();
    await expect(page.getByText('Window: 00:00 – 30:00')).toHaveCount(0);

    await page.getByTestId('waveform-zoom-reset').click();
    await expect(page.getByText('Window: 00:00 – 30:00')).toBeVisible();
  });

  test('clicking a transition card highlights it and shows the inspector', async ({ page }) => {
    const trans2 = page.getByTestId('transition-card').nth(1);
    await expect(trans2).toBeVisible();
    await trans2.scrollIntoViewIfNeeded();
    await trans2.click();

    const inspector = page.getByTestId('region-inspector');
    await expect(inspector).toBeVisible();
    await expect(inspector).toContainText('engine blend zone');
  });

  test('waveform position is keyboard-operable', async ({ page }) => {
    const canvas = page.getByTestId('waveform-canvas');
    await expect(canvas).toBeVisible();
    await canvas.scrollIntoViewIfNeeded();
    await page.getByRole('slider', { name: /waveform position/i }).focus();
    await page.keyboard.press('ArrowRight');
    await expect(page.getByText(/Position: 00:0[1-5] \/ 30:00/)).toBeVisible();
  });
});
