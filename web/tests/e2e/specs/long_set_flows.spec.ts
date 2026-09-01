import { test, expect } from '@playwright/test';
import mix30MinFixture from './fixtures/mix_30min.json';

test.describe('Mix Analyst Frontend E2E - 30-Minute Long Set Flows', () => {
  test.beforeEach(async ({ page }) => {
    // Intercept backend API routes with the realistic 30-minute test fixture
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

    await page.route(`**/api/v1/mixes/${mix30MinFixture.id}/export/youtube`, async (route) => {
      const timestamps = [
        '00:00 - System Corrupt - Resonance Generator (Intro)',
        '03:45 - Curley Korrupt - Subwoofer Pressure Tribe',
        '07:30 - Murphies Law - Tekno Totem Assault',
        '11:15 - Turbulence 23 - Acid Wall Destroyer',
        '15:00 - Underground Tribe - Oxidized Copper Coil',
        '19:20 - Tekno Core 23 - Speaker Stack Distortion',
        '24:10 - System Corrupt - Hardtek Ritual Anthem',
        '28:00 - SYCO23 - Outro Sub Frequency Fade',
      ].join('\n');
      await route.fulfill({
        status: 200,
        contentType: 'text/plain',
        body: timestamps,
      });
    });

    // Grant clipboard permissions
    await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);

    await page.goto('/');
  });

  test('User Flow 1: 30-Minute Mix Ingestion & Archive Selection', async ({ page }) => {
    // Verify Brand Header
    await expect(page.locator('h1')).toContainText('SYSTEM CORRUPT');
    await expect(page.getByText('MIX ANALYST')).toBeVisible();

    // Verify 30-min mix appears in archive sidebar
    const archiveItem = page.locator(`button:has-text("${mix30MinFixture.title}")`);
    await expect(archiveItem).toBeVisible();
    await expect(archiveItem).toContainText('30:00');
    await expect(archiveItem).toContainText('152.0 BPM');

    // Click mix to select
    await archiveItem.click();

    // Verify Title & Initial Time Display (00:00 / 30:00)
    await expect(page.locator('h3')).toContainText(mix30MinFixture.title);
    await expect(page.getByText('Position: 00:00 / 30:00')).toBeVisible();
  });

  test('User Flow 2: Long-Set Waveform Timeline Interaction & Scrubbing', async ({ page }) => {
    const canvas = page.locator('canvas');
    await expect(canvas).toBeVisible();

    // Measure bounding box to simulate scrub clicks across 30 minutes
    const box = await canvas.boundingBox();
    expect(box).not.toBeNull();
    if (!box) return;

    // Click at 50% width (should seek to ~15:00 = 900s)
    await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.5);
    await expect(page.getByText(/Position: (14:5[8-9]|15:0[0-2]) \/ 30:00/)).toBeVisible();

    // Click at 90% width (should seek to ~27:00 = 1620s near set climax)
    await page.mouse.click(box.x + box.width * 0.9, box.y + box.height * 0.5);
    await expect(page.getByText(/Position: (26:5[8-9]|27:0[0-2]) \/ 30:00/)).toBeVisible();
  });

  test('User Flow 3: Transport Controls (Play/Pause & Restart)', async ({ page }) => {
    const playBtn = page.locator('button:has-text("PLAY")');
    await expect(playBtn).toBeVisible();

    // Toggle Play -> Pause
    await playBtn.click();
    await expect(page.locator('button:has-text("PAUSE")')).toBeVisible();

    // Toggle Pause -> Play
    await page.locator('button:has-text("PAUSE")').click();
    await expect(page.locator('button:has-text("PLAY")')).toBeVisible();

    // Scrub forward and test Restart button
    const canvas = page.locator('canvas');
    const box = await canvas.boundingBox();
    if (box) {
      await page.mouse.click(box.x + box.width * 0.4, box.y + box.height * 0.5);
      await expect(page.getByText('Position: 00:00 / 30:00')).not.toBeVisible();

      // Click RESTART
      await page.locator('button:has-text("RESTART")').click();
      await expect(page.getByText('Position: 00:00 / 30:00')).toBeVisible();
    }
  });

  test('User Flow 4: Interactive Tracklist Cue Jumping Across Long Durations', async ({ page }) => {
    // Verify 8 tracks detected
    await expect(page.getByText('Detected Tracks (8)')).toBeVisible();

    // Click Track #4 (Acid Wall Destroyer at 11:15 = 675s)
    const track4 = page.locator('div:has-text("4. Acid Wall Destroyer")').last();
    await expect(track4).toBeVisible();
    await track4.click();

    // Verify time jumped to 11:15
    await expect(page.getByText('Position: 11:15 / 30:00')).toBeVisible();

    // Click Track #7 (Hardtek Ritual Anthem at 24:10 = 1450s)
    const track7 = page.locator('div:has-text("7. Hardtek Ritual Anthem")').last();
    await expect(track7).toBeVisible();
    await track7.click();

    // Verify time jumped to 24:10
    await expect(page.getByText('Position: 24:10 / 30:00')).toBeVisible();
  });

  test('User Flow 5: Harmonic Transition Zone Breakdown & Key Shift Inspection', async ({ page }) => {
    // Verify 7 transitions listed
    await expect(page.getByText('Harmonic Transitions (7)')).toBeVisible();

    // Inspect Transition #2 (Energy Boost Drop at 07:00 = 420s)
    const trans2 = page.locator('div:has-text("ENERGY_BOOST_DROP")').first();
    await expect(trans2).toBeVisible();
    await expect(trans2).toContainText('9A → 9B');
    await expect(trans2).toContainText('Relative Major');

    // Click Transition #2 and verify position jumps to 07:00
    await trans2.click();
    await expect(page.getByText('Position: 07:00 / 30:00')).toBeVisible();
  });

  test('User Flow 6: Export Actions & YouTube Timestamps Toast Notification', async ({ page }) => {
    // Verify DJ Software export buttons exist with proper download endpoints
    const cueBtn = page.locator('a:has-text("Export .CUE")');
    await expect(cueBtn).toBeVisible();
    await expect(cueBtn).toHaveAttribute('href', /.*\/export\/cue/);

    const rekordboxBtn = page.locator('a:has-text("Rekordbox XML")');
    await expect(rekordboxBtn).toBeVisible();
    await expect(rekordboxBtn).toHaveAttribute('href', /.*\/export\/rekordbox/);

    const traktorBtn = page.locator('a:has-text("Traktor NML")');
    await expect(traktorBtn).toBeVisible();
    await expect(traktorBtn).toHaveAttribute('href', /.*\/export\/traktor/);

    // Click YouTube Timestamps copy button
    const ytBtn = page.locator('button:has-text("Copy YouTube Timestamps")');
    await expect(ytBtn).toBeVisible();
    await ytBtn.click();

    // Verify UI Toast notification appears
    const toast = page.getByText('YouTube timestamps copied to clipboard!');
    await expect(toast).toBeVisible();
  });

  test('User Flow 7: Responsive Layouts (Desktop / Tablet / Mobile)', async ({ page }) => {
    // Verify all primary cards are rendered and accessible
    await expect(page.getByText('Mix Archive')).toBeVisible();
    await expect(page.locator('canvas')).toBeVisible();
    await expect(page.getByText('Detected Tracks (8)')).toBeVisible();
    await expect(page.getByText('Harmonic Transitions (7)')).toBeVisible();

    // Test responsive canvas interaction on any viewport
    const canvas = page.locator('canvas');
    await canvas.click({ position: { x: 50, y: 50 } });
    await expect(page.getByText(/Position:/)).toBeVisible();
  });
});
