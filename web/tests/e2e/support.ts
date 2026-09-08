import { expect, type Page } from "@playwright/test";

/**
 * Checks reflow at a concrete viewport rather than inferring device-engine
 * coverage from a mobile user agent. The configured mobile projects remain
 * Chromium viewport emulation; they are not presented as Safari coverage.
 */
export async function assertNoHorizontalOverflow(page: Page, width: number) {
  await page.setViewportSize({ width, height: 844 });
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth), {
      message: `document should not overflow a ${width}px viewport`,
    })
    .toBeLessThanOrEqual(width);
}

export const sourceArtifact = {
  id: "artifact-source-1", role: "source", key: "projects/project-a/artifacts/source/v1/source-hash", sha256: "source-hash",
  algorithm_version: "1", media_type: "audio/wav", byte_length: 100, report: null,
  download_url: "/api/v1/mixes/mix-1/artifacts/artifact-source-1/download", created_at: "2026-09-01T00:00:00Z",
};

export const masteredArtifact = {
  id: "artifact-mastered-1", role: "mastered", key: "projects/project-a/artifacts/mastered/v1/master-hash", sha256: "master-hash",
  algorithm_version: "1", media_type: "audio/wav", byte_length: 100, report: null,
  download_url: "/api/v1/mixes/mix-1/artifacts/artifact-mastered-1/download", created_at: "2026-09-01T00:00:01Z",
};

export function completedMix() {
  return {
    id: "mix-1", title: "Sound-system transmission", artist: "SYCO23", status: "mastered",
    created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:01Z",
    media_asset: {
      id: "media-1", original_filename: "transmission.wav", file_size_bytes: 48000, sha256_hash: "input-hash",
      duration_seconds: 120, sample_rate: 48000, channels: 2, codec: "pcm_s16le", bit_rate: null, format_name: "wav", created_at: "2026-09-01T00:00:00Z",
    },
    analysis_result: null,
    artifacts: [sourceArtifact, masteredArtifact],
    suggested_download_name: "sound-system-master.wav",
  };
}

export async function mockCompletedMix(page: Page) {
  await page.route("**/api/v1/mixes/mix-1", (route) => route.fulfill({ contentType: "application/json", json: completedMix() }));
}

export async function mockEmptyJobs(page: Page) {
  await page.route("**/api/v1/jobs?*", (route) => route.fulfill({ contentType: "application/json", json: { items: [], total: 0, next_cursor: null } }));
}

export async function mockEmptyLibrary(page: Page) {
  await page.route("**/api/v1/mixes", (route) => route.fulfill({ contentType: "application/json", json: { items: [], total: 0 } }));
}
