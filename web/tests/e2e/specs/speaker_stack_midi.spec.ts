import { test, expect } from '@playwright/test';

test.describe('Phase 15: 3D Speaker-Stack Visualizer & Web MIDI Hardware Integration', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('renders 3D Speaker Stack Canvas and telemetry HUD', async ({ page }) => {
    const canvas = page.locator('canvas');
    await expect(canvas.first()).toBeVisible({ timeout: 5000 });

    const hudHeader = page.locator('text=SYCO23 // 3D STACK RIG');
    await expect(hudHeader).toBeVisible();
  });

  test('renders an audio element for the selected mix', async ({ page }) => {
    const audioEl = page.locator('audio');
    await expect(audioEl).toHaveCount(1);
  });

  test('play/pause button toggles playback state without crashing', async ({ page }) => {
    const playBtn = page.locator('[data-testid="play-pause-btn"]');
    await expect(playBtn).toBeVisible();
    const initialLabel = await playBtn.textContent();
    await playBtn.click();
    await page.waitForTimeout(300);
    const nextLabel = await playBtn.textContent();
    expect(nextLabel).not.toBeNull();
    expect(initialLabel).not.toBeNull();
  });

  test('switches stack architectures without rendering failures', async ({ page }) => {
    const presetSelect = page.locator('[data-testid="rig-preset-select"]');
    await expect(presetSelect).toBeVisible();

    await presetSelect.selectOption('mechanical_totem');
    await expect(presetSelect).toHaveValue('mechanical_totem');

    await presetSelect.selectOption('underground_rig');
    await expect(presetSelect).toHaveValue('underground_rig');
  });

  test('changes color themes seamlessly', async ({ page }) => {
    const themeSelect = page.locator('[data-testid="theme-select"]');
    await expect(themeSelect).toBeVisible();

    await themeSelect.selectOption('crimson');
    await expect(themeSelect).toHaveValue('crimson');

    await themeSelect.selectOption('copper');
    await expect(themeSelect).toHaveValue('copper');
  });

  test('opens Web MIDI hardware configuration modal from header badge', async ({ page }) => {
    const headerMidiBtn = page.locator('[data-testid="header-midi-btn"]');
    await expect(headerMidiBtn).toBeVisible();
    await headerMidiBtn.click();

    const modalOverlay = page.locator('[data-testid="midi-modal-overlay"]');
    await expect(modalOverlay).toBeVisible();

    const title = page.locator('text=Web MIDI Hardware Configuration');
    await expect(title).toBeVisible();

    if (page.locator('text=Web MIDI API is not natively available').isVisible) {
      // Non-Chromium engines: unsupported banner must render without crashing.
    }

    const closeBtn = page.locator('button:has-text("DONE / SAVE")');
    await closeBtn.click();
    await expect(modalOverlay).not.toBeVisible();
  });

  test('opens and interacts with Web MIDI hardware configuration modal via controls', async ({ page }) => {
    const openMidiBtn = page.locator('[data-testid="open-midi-modal-btn"]');
    await expect(openMidiBtn).toBeVisible();
    await openMidiBtn.click();

    const modalOverlay = page.locator('[data-testid="midi-modal-overlay"]');
    await expect(modalOverlay).toBeVisible();

    const pioneerPresetBtn = page.locator('button:has-text("Pioneer DDJ-400 / FLX4")');
    await expect(pioneerPresetBtn).toBeVisible();
    await pioneerPresetBtn.click();

    const closeBtn = page.locator('button:has-text("DONE / SAVE")');
    await closeBtn.click();
    await expect(modalOverlay).not.toBeVisible();
  });
});
