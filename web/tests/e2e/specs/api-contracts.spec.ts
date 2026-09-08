import { expect, test } from "@playwright/test";

const rawArtifact = {
  id: "artifact-source-1",
  role: "source",
  key: "projects/project-a/artifacts/source/v1/source-hash",
  sha256: "source-hash",
  algorithm_version: "1",
  media_type: "audio/wav",
  byte_length: 100,
  report: null,
  download_url: "/api/v1/mixes/mix-raw/artifacts/artifact-source-1/download",
  created_at: "2026-09-01T00:00:00Z",
};

const masteredArtifact = {
  id: "artifact-mastered-1",
  role: "mastered",
  key: "projects/project-a/artifacts/mastered/v1/master-hash",
  sha256: "master-hash",
  algorithm_version: "1",
  media_type: "audio/wav",
  byte_length: 100,
  report: null,
  download_url: "/api/v1/mixes/mix-mastered/artifacts/artifact-mastered-1/download",
  created_at: "2026-09-01T00:00:01Z",
};

function mix(id: string, title: string, artifacts: typeof rawArtifact[]) {
  return {
    id,
    title,
    artist: null,
    status: "ready",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    media_asset: {
      id: `media-${id}`,
      original_filename: `${title}.wav`,
      file_size_bytes: 100,
      sha256_hash: "input-hash",
      duration_seconds: 120,
      sample_rate: 48000,
      channels: 2,
      codec: "pcm_s16le",
      bit_rate: null,
      format_name: "wav",
      created_at: "2026-09-01T00:00:00Z",
    },
    analysis_result: null,
    artifacts,
    suggested_download_name: null,
  };
}

test.describe("Mix API contracts", () => {
  test("library does not treat raw paginated items as completed masters", async ({ page }) => {
    await page.route("**/api/v1/mixes", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        json: { items: [mix("mix-raw", "Analysis only mix", [rawArtifact])], total: 1 },
      });
    });

    await page.goto("/library");
    await expect(page.getByRole("heading", { name: "No completed masters yet" })).toBeVisible();
    await expect(page.getByText("Your audio is still being processed.")).toBeVisible();
    await expect(page.getByRole("list")).toHaveCount(0);
    await expect(page.getByText("Analysis only mix")).toHaveCount(0);
    await expect(page.getByText("SYCO23 — Live Sound-System Transmission 23")).toHaveCount(0);
  });

  test("library keeps a failed request visible until an explicit retry succeeds", async ({ page }) => {
    let serviceIsAvailable = false;
    let requestCount = 0;
    await page.route("**/api/v1/mixes", async (route) => {
      requestCount += 1;
      if (!serviceIsAvailable) {
        await route.fulfill({ status: 503, contentType: "application/json", json: { detail: "internal diagnostic" } });
        return;
      }
      await route.fulfill({ contentType: "application/json", json: { items: [], total: 0 } });
    });

    await page.goto("/library");
    await expect(page.getByRole("alert")).toContainText("Service temporarily unavailable");
    serviceIsAvailable = true;
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByRole("heading", { name: "No completed masters yet" })).toBeVisible();
    expect(requestCount).toBeGreaterThanOrEqual(2);
  });

  test("library renders only mixes with a server-confirmed mastered artifact", async ({ page }) => {
    await page.route("**/api/v1/mixes", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        json: {
          items: [
            mix("mix-raw", "Analysis only mix", [rawArtifact]),
            mix("mix-mastered", "Downloadable master", [rawArtifact, masteredArtifact]),
          ],
          total: 2,
        },
      });
    });

    await page.goto("/library");
    await expect(page.getByRole("list", { name: "1 completed master" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Downloadable master" })).toBeVisible();
    await expect(page.getByText("Analysis only mix")).toHaveCount(0);
    await expect(page.getByText("Mastered")).toBeVisible();
  });
});
