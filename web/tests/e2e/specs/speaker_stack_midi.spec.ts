import { test, expect } from '@playwright/test';

test.describe('Phase 15: 3D Speaker-Stack Visualizer & Web MIDI Hardware Integration', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to local development server
    await page.goto('/');
  });

  test('renders 3D Speaker Stack Canvas and telemetry HUD', async ({ page }) => {
    const canvas = page.locator('canvas');
    await expect(canvas).toBeVisible({ timeout: 5000 });

    const hudHeader = page.locator('text=SYCO23 // 3D STACK RIG');
    await expect(hudHeader).toBeVisible();
  });

  test('switches stack architectures without rendering failures', async ({ page }) => {
    const presetSelect = page.locator('[data-testid="rig-preset-select"]');
    await expect(presetSelect).toBeVisible();

    // Select Mechanical Totem
    await presetSelect.selectOption('mechanical_totem');
    await expect(presetSelect).toHaveValue('mechanical_totem');

    // Select Underground Rig
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

  test('opens and interacts with Web MIDI hardware configuration modal', async ({ page }) => {
    const openMidiBtn = page.locator('[data-testid="open-midi-modal-btn"]');
    await expect(openMidiBtn).toBeVisible();
    await openMidiBtn.click();

    const modalOverlay = page.locator('[data-testid="midi-modal-overlay"]');
    await expect(modalOverlay).toBeVisible();

    const title = page.locator('text=Web MIDI Hardware Configuration');
    await expect(title).toBeVisible();

    // Test clicking a hardware preset
    const pioneerPresetBtn = page.locator('button:has-text("Pioneer DDJ-400 / FLX4")');
    await expect(pioneerPresetBtn).toBeVisible();
    await pioneerPresetBtn.click();

    // Close modal
    const closeBtn = page.locator('button:has-text("DONE / SAVE")');
    await closeBtn.click();
    await expect(modalOverlay).not.toBeVisible();
  });
});
