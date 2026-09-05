import { expect, test, type Page } from "@playwright/test";

const shortWav = {
  name: "short.wav",
  mimeType: "audio/wav",
  // A selection test does not need browser decoding; the server contract is mocked.
  buffer: Buffer.from("RIFF____WAVEfmt "),
};

async function stubProcessApi(page: Page) {
  await page.route("**/api/v1/", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    await route.fulfill({
      contentType: "application/json",
      json: {
        upload_id: "upload-1", upload_url: "/api/v1/upload-1", filename: "short.wav", total_size_bytes: shortWav.buffer.length,
        chunk_size: shortWav.buffer.length, offset: 0, expires_at: "2030-01-01T00:00:00Z", status: "PENDING",
      },
    });
  });
  await page.route("**/api/v1/upload-1", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ contentType: "application/json", json: { upload_id: "upload-1", filename: "short.wav", total_size_bytes: shortWav.buffer.length, bytes_received: 0, offset: 0, progress_percent: 0, status: "PENDING", expires_at: "2030-01-01T00:00:00Z", created_at: "2029-12-31T00:00:00Z", updated_at: "2029-12-31T00:00:00Z" } });
      return;
    }
    if (route.request().method() !== "PATCH") return route.fallback();
    await new Promise((resolve) => setTimeout(resolve, 120));
    await route.fulfill({ contentType: "application/json", json: { upload_id: "upload-1", bytes_received: shortWav.buffer.length, offset: shortWav.buffer.length, total_size_bytes: shortWav.buffer.length, progress_percent: 100, status: "UPLOADING" } });
  });
  await page.route("**/api/v1/upload-1/complete", async (route) => {
    await route.fulfill({ contentType: "application/json", json: { mix_id: "mix-1", media_asset_id: "asset-1", title: "short", artist: null, duration_seconds: 1, sample_rate: 44100, channels: 2, codec: "pcm_s16le", sha256_hash: "abc", status: "ready" } });
  });
  await page.route("**/api/v1/mixes/mix-1/master", async (route) => {
    await route.fulfill({ contentType: "application/json", status: 202, json: { id: "job-1", mix_id: "mix-1", job_type: "MASTERING", status: "QUEUED", progress_percent: 0, current_stage: "Queued", parameters: {}, created_at: "2030-01-01T00:00:00Z" } });
  });
}

test.describe("Process audio", () => {
  test("a valid selection shows progress then routes only after a persisted job is returned", async ({ page }) => {
    await stubProcessApi(page);
    await page.goto("/process");
    await page.getByLabel("Choose audio").setInputFiles(shortWav);
    await expect(page.getByText("Ready to process")).toBeVisible();
    await page.getByRole("button", { name: "Start mastering" }).click();
    await expect(page.getByRole("progressbar", { name: "Upload progress" })).toBeVisible();
    await expect(page).toHaveURL(/\/jobs\/job-1$/);
  });

  test("an unsupported selection is rejected before any upload starts", async ({ page }) => {
    await page.goto("/process");
    await page.getByLabel("Choose audio").setInputFiles({ name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("not audio") });
    await expect(page.getByRole("alert")).toContainText("Choose a supported audio file");
    await expect(page.getByRole("button", { name: "Start mastering" })).toHaveCount(0);
  });

  test("a failed upload keeps a truthful retry action", async ({ page }) => {
    let patches = 0;
    await stubProcessApi(page);
    await page.unroute("**/api/v1/upload-1");
    await page.route("**/api/v1/upload-1", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ contentType: "application/json", json: { upload_id: "upload-1", filename: "short.wav", total_size_bytes: shortWav.buffer.length, bytes_received: 0, offset: 0, progress_percent: 0, status: "PENDING", expires_at: "2030-01-01T00:00:00Z", created_at: "2029-12-31T00:00:00Z", updated_at: "2029-12-31T00:00:00Z" } });
        return;
      }
      if (route.request().method() !== "PATCH") return route.fallback();
      patches += 1;
      if (patches === 1) {
        await route.fulfill({ status: 503, contentType: "application/json", json: {} });
        return;
      }
      await route.fulfill({ contentType: "application/json", json: { upload_id: "upload-1", bytes_received: shortWav.buffer.length, offset: shortWav.buffer.length, total_size_bytes: shortWav.buffer.length, progress_percent: 100, status: "UPLOADING" } });
    });
    await page.goto("/process");
    await page.getByLabel("Choose audio").setInputFiles(shortWav);
    await page.getByRole("button", { name: "Start mastering" }).click();
    await expect(page.getByRole("alert")).toContainText("Upload could not continue");
    await expect(page.getByRole("button", { name: "Resume upload" })).toBeVisible();
    await page.getByRole("button", { name: "Resume upload" }).click();
    await expect(page).toHaveURL(/\/jobs\/job-1$/);
  });

  test("refuses to resume a server-completed session", async ({ page }) => {
    await stubProcessApi(page);
    await page.unroute("**/api/v1/upload-1");
    await page.route("**/api/v1/upload-1", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ contentType: "application/json", json: { upload_id: "upload-1", filename: "short.wav", total_size_bytes: shortWav.buffer.length, bytes_received: shortWav.buffer.length, offset: shortWav.buffer.length, progress_percent: 100, status: "COMPLETED", expires_at: "2030-01-01T00:00:00Z", created_at: "2029-12-31T00:00:00Z", updated_at: "2029-12-31T00:00:00Z" } });
        return;
      }
      await route.fulfill({ status: 503, contentType: "application/json", json: {} });
    });
    await page.goto("/process");
    await page.getByLabel("Choose audio").setInputFiles(shortWav);
    await page.getByRole("button", { name: "Start mastering" }).click();
    await expect(page.getByRole("alert")).toContainText("Upload could not continue");
    await page.getByRole("button", { name: "Resume upload" }).click();
    await expect(page.getByRole("alert")).toContainText("Upload session already completed");
    await expect(page.getByRole("button", { name: "Resume upload" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  });

  test("rejects a PENDING session whose server expiry has elapsed", async ({ page }) => {
    let patches = 0;
    await stubProcessApi(page);
    await page.unroute("**/api/v1/upload-1");
    await page.route("**/api/v1/upload-1", async (route) => {
      if (route.request().method() === "GET") {
        // The backend can briefly retain PENDING while its expiry cleanup runs.
        // The client must still refuse to resume based on the aware timestamp.
        await route.fulfill({ contentType: "application/json", json: { upload_id: "upload-1", filename: "short.wav", total_size_bytes: shortWav.buffer.length, bytes_received: 0, offset: 0, progress_percent: 0, status: "PENDING", expires_at: "2000-01-01T00:00:00Z", created_at: "1999-12-31T00:00:00Z", updated_at: "1999-12-31T00:00:00Z" } });
        return;
      }
      patches += 1;
      await route.fulfill({ status: 503, contentType: "application/json", json: {} });
    });
    await page.goto("/process");
    await page.getByLabel("Choose audio").setInputFiles(shortWav);
    await page.getByRole("button", { name: "Start mastering" }).click();
    await expect(page.getByRole("button", { name: "Resume upload" })).toBeVisible();
    await page.getByRole("button", { name: "Resume upload" }).click();
    await expect(page.getByRole("alert")).toContainText("Upload session expired");
    await expect(page.getByRole("button", { name: "Resume upload" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
    expect(patches).toBe(1);
  });

  test("does not resume a session with an invalid expiry timestamp", async ({ page }) => {
    await stubProcessApi(page);
    await page.unroute("**/api/v1/upload-1");
    await page.route("**/api/v1/upload-1", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ contentType: "application/json", json: { upload_id: "upload-1", filename: "short.wav", total_size_bytes: shortWav.buffer.length, bytes_received: 0, offset: 0, progress_percent: 0, status: "PENDING", expires_at: "not-a-date", created_at: "2029-12-31T00:00:00Z", updated_at: "2029-12-31T00:00:00Z" } });
        return;
      }
      await route.fulfill({ status: 503, contentType: "application/json", json: {} });
    });
    await page.goto("/process");
    await page.getByLabel("Choose audio").setInputFiles(shortWav);
    await page.getByRole("button", { name: "Start mastering" }).click();
    await page.getByRole("button", { name: "Resume upload" }).click();
    await expect(page.getByRole("alert")).toContainText("invalid expiry time");
    await expect(page.getByRole("button", { name: "Resume upload" })).toHaveCount(0);
  });

  test("clears a stale resume session after a chunk returns 410", async ({ page }) => {
    await stubProcessApi(page);
    await page.unroute("**/api/v1/upload-1");
    await page.route("**/api/v1/upload-1", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ contentType: "application/json", json: { upload_id: "upload-1", filename: "short.wav", total_size_bytes: shortWav.buffer.length, bytes_received: 0, offset: 0, progress_percent: 0, status: "PENDING", expires_at: "2030-01-01T00:00:00Z", created_at: "2029-12-31T00:00:00Z", updated_at: "2029-12-31T00:00:00Z" } });
        return;
      }
      await route.fulfill({ status: 410, contentType: "application/json", json: {} });
    });
    await page.goto("/process");
    await page.getByLabel("Choose audio").setInputFiles(shortWav);
    await page.getByRole("button", { name: "Start mastering" }).click();
    await expect(page.getByRole("alert")).toContainText("Upload session expired");
    await expect(page.getByRole("button", { name: "Resume upload" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  });

  test("clears a stale resume session after finalize returns 410", async ({ page }) => {
    await stubProcessApi(page);
    await page.unroute("**/api/v1/upload-1/complete");
    await page.route("**/api/v1/upload-1/complete", async (route) => {
      await route.fulfill({ status: 410, contentType: "application/json", json: {} });
    });
    await page.goto("/process");
    await page.getByLabel("Choose audio").setInputFiles(shortWav);
    await page.getByRole("button", { name: "Start mastering" }).click();
    await expect(page.getByRole("alert")).toContainText("Upload session expired");
    await expect(page.getByRole("button", { name: "Resume upload" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  });

  test("keeps queue creation cancellable and never navigates without its persisted job", async ({ page }) => {
    await stubProcessApi(page);
    await page.unroute("**/api/v1/mixes/mix-1/master");
    await page.route("**/api/v1/mixes/mix-1/master", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 350));
      await route.fulfill({ contentType: "application/json", status: 202, json: { id: "job-1", mix_id: "mix-1", job_type: "MASTERING", status: "QUEUED", progress_percent: 0, current_stage: "Queued", parameters: {}, created_at: "2030-01-01T00:00:00Z" } });
    });
    await page.goto("/process");
    await page.getByLabel("Choose audio").setInputFiles(shortWav);
    await page.getByRole("button", { name: "Start mastering" }).click();
    await expect(page.getByRole("button", { name: "Cancel request" })).toBeVisible();
    await page.getByRole("button", { name: "Cancel request" }).click();
    await expect(page.getByText("Mastering request cancelled. You can try again when ready.")).toBeVisible();
    await expect(page).toHaveURL(/\/process$/);
  });
});
