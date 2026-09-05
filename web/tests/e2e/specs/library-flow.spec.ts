import { expect, test } from "@playwright/test";

const sourceArtifact = {
  id: "artifact-source-1", role: "source", key: "projects/project-a/artifacts/source/v1/source-hash", sha256: "source-hash",
  algorithm_version: "1", media_type: "audio/wav", byte_length: 100, report: null,
  download_url: "/api/v1/mixes/mix-1/artifacts/artifact-source-1/download", created_at: "2026-09-01T00:00:00Z",
};
const masteredArtifact = {
  id: "artifact-mastered-1", role: "mastered", key: "projects/project-a/artifacts/mastered/v1/master-hash", sha256: "master-hash",
  algorithm_version: "1", media_type: "audio/wav", byte_length: 100, report: null,
  download_url: "/api/v1/mixes/mix-1/artifacts/artifact-mastered-1/download", created_at: "2026-09-01T00:00:01Z",
};

function mixDetail() {
  return {
    id: "mix-1", title: "Sound-system transmission", artist: "SYCO23", status: "mastered",
    created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:01Z",
    media_asset: {
      id: "media-1", original_filename: "transmission.wav", file_size_bytes: 48000, sha256_hash: "input-hash",
      duration_seconds: 120, sample_rate: 48000, channels: 2, codec: "pcm_s16le", bit_rate: null, format_name: "wav", created_at: "2026-09-01T00:00:00Z",
    },
    analysis_result: {
      id: "analysis-1", mix_id: "mix-1", media_asset_id: "media-1", primary_bpm: 140, bpm_confidence: 0.9,
      detected_key: "F minor", camelot_code: "4A", key_confidence: 0.8, integrated_lufs: -9.2, loudness_range_lra: 5.1,
      true_peak_db: -1, created_at: "2026-09-01T00:00:00Z",
    },
    artifacts: [sourceArtifact, masteredArtifact], suggested_download_name: "sound-system-master.wav",
  };
}

async function mockMix(page: import("@playwright/test").Page) {
  await page.route("**/api/v1/mixes/mix-1", async (route) => {
    await route.fulfill({ contentType: "application/json", json: mixDetail() });
  });
}

test.describe("Library detail", () => {
  test("uses server artifacts for explicit A/B playback and download", async ({ page }) => {
    await mockMix(page);
    await page.addInitScript(() => {
      HTMLMediaElement.prototype.play = () => Promise.resolve();
    });
    await page.goto("/library/mix-1");

    await expect(page.getByRole("heading", { name: "Sound-system transmission" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Mastered", exact: true })).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "Play mastered audio" }).click();
    await expect(page.getByRole("button", { name: "Pause mastered audio" })).toBeVisible();
    await page.getByRole("button", { name: "Original", exact: true }).click();
    await expect(page.getByRole("button", { name: "Original", exact: true })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("button", { name: "Play original audio" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Download original audio" })).toHaveAttribute("href", sourceArtifact.download_url);
    await expect(page.getByRole("link", { name: "Download original audio" })).toHaveAttribute("download", "transmission.wav");
  });

  test("does not report playback when the browser denies it", async ({ page }) => {
    await mockMix(page);
    await page.addInitScript(() => {
      HTMLMediaElement.prototype.play = () => Promise.reject(new DOMException("blocked", "NotAllowedError"));
    });
    await page.goto("/library/mix-1");
    await page.getByRole("button", { name: "Play mastered audio" }).click();
    await expect(page.getByRole("alert")).toContainText("Playback needs a browser gesture or supported audio");
    await expect(page.getByRole("button", { name: "Play mastered audio" })).toBeVisible();
  });

  test("loads the optional Rig only on request and supports keyboard dismissal", async ({ page }) => {
    await mockMix(page);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/library/mix-1");
    await expect(page.getByTestId("rig-panel")).toHaveCount(0);
    await page.getByRole("button", { name: "Open listening rig" }).click();
    await expect(page.getByRole("dialog", { name: "Listening rig" })).toBeVisible();
    await expect(page.getByTestId("rig-panel")).toHaveAttribute("data-motion", "reduced");
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: "Listening rig" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Open listening rig" })).toBeFocused();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  });
});
