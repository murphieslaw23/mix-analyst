import { expect, test, type Page } from "@playwright/test";

function mix(id: string, filename: string) {
  return {
    id, title: filename.replace(/\.[^.]+$/, ""), artist: null, status: "ready",
    created_at: "2030-01-01T00:00:00Z", updated_at: "2030-01-01T00:00:00Z",
    media_asset: { id: `asset-${id}`, original_filename: filename, file_size_bytes: 100, sha256_hash: "source-hash", duration_seconds: 120, sample_rate: 48000, channels: 2, codec: "pcm_s16le", bit_rate: null, format_name: "wav", created_at: "2030-01-01T00:00:00Z" },
    analysis_result: null, artifacts: [], suggested_download_name: null,
  };
}

function job(id: string, mixId: string, status: "SUCCEEDED" | "FAILED" | "QUEUED") {
  const failed = status === "FAILED";
  return {
    id, mix_id: mixId, batch_id: "batch-1", job_type: "MASTERING", status,
    progress_percent: status === "SUCCEEDED" ? 100 : failed ? 64 : 0,
    current_stage: failed ? "Limiter" : status === "SUCCEEDED" ? "Published" : "Queued",
    parameters: {}, celery_task_id: null,
    error_message: failed ? "The limiter could not create a safe output." : null,
    created_at: "2030-01-01T00:00:00Z", started_at: null,
    finished_at: status === "QUEUED" ? null : "2030-01-01T00:01:00Z",
    stage_runs: [], attempts: [],
  };
}

function batch(items = [job("job-success", "mix-a", "SUCCEEDED"), job("job-failed", "mix-b", "FAILED")]) {
  const failed = items.filter((item) => item.status === "FAILED").length;
  const complete = items.filter((item) => item.status === "SUCCEEDED").length;
  return {
    id: "batch-1", status: failed ? "PARTIAL_FAILED" : "RUNNING", total_count: items.length,
    completed_count: complete, failed_count: failed, cancelled_count: 0, items,
    preset: { preset_id: "sound_system_heavy", preset_name: "Sound System Heavy", target_lufs: -11, true_peak_dbtp: -0.8 },
    max_parallelism: 2, created_at: "2030-01-01T00:00:00Z", updated_at: "2030-01-01T00:01:00Z",
  };
}

test("mobile batch review submits only checked mixes and retries only failed children", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  let createBody: unknown;
  let retryBody: unknown;
  let currentBatch = batch();
  await page.route("**/api/v1/mixes", async (route) => route.fulfill({ contentType: "application/json", json: { items: [mix("mix-a", "set-a.wav"), mix("mix-b", "set-b.wav")], total: 2 } }));
  await page.route("**/api/v1/batches", async (route) => {
    createBody = route.request().postDataJSON();
    await route.fulfill({ status: 201, contentType: "application/json", json: currentBatch });
  });
  await page.route(/\/api\/v1\/batches\/batch-1(?:\/retry)?$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ contentType: "application/json", json: currentBatch });
      return;
    }
    retryBody = route.request().postDataJSON();
    currentBatch = batch([job("job-success", "mix-a", "SUCCEEDED"), job("job-failed", "mix-b", "QUEUED")]);
    await route.fulfill({ contentType: "application/json", json: currentBatch });
  });

  await page.goto("/process?mode=batch");
  await expect(page.getByText("0 selected of 2 available audio items.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Create batch" })).toBeDisabled();
  await page.getByRole("checkbox", { name: "set-b.wav" }).check();
  await page.getByLabel("Concurrent jobs").selectOption("2");
  await expect(page.getByText("1 selected of 2 available audio items.")).toBeVisible();
  await page.getByRole("button", { name: "Create batch" }).click();
  await expect(page).toHaveURL(/\/batches\/batch-1$/);
  expect(createBody).toEqual({ mix_ids: ["mix-b"], preset: { preset_id: "sound_system_heavy" }, max_parallelism: 2 });
  await expect(page.getByText("Retry scope: 1 failed item only.")).toBeVisible();
  await page.getByRole("button", { name: "Retry failed items" }).click();
  expect(retryBody).toEqual({ job_ids: ["job-failed"] });
  await expect(page.getByRole("heading", { name: "Failed items (1)" })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test("Jobs exposes the durable batch recovery link only for batch children", async ({ page }) => {
  await page.route("**/api/v1/jobs?limit=20", async (route) => route.fulfill({ contentType: "application/json", json: { items: [job("job-batch", "mix-a", "FAILED")], total: 1, next_cursor: null } }));
  await page.route("**/api/v1/batches/batch-1", async (route) => route.fulfill({ contentType: "application/json", json: batch([job("job-batch", "mix-a", "FAILED")]) }));
  await page.goto("/jobs");
  await page.getByRole("link", { name: "View batch recovery" }).click();
  await expect(page).toHaveURL(/\/batches\/batch-1$/);
  await expect(page.getByRole("heading", { name: "Batch review" })).toBeVisible();
});
