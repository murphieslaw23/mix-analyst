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
      await route.fulfill({ contentType: "application/json", json: { upload_id: "upload-1", upload_url: "/api/v1/upload-1", filename: "short.wav", total_size_bytes: shortWav.buffer.length, chunk_size: shortWav.buffer.length, offset: 0, expires_at: "2030-01-01T00:00:00Z", status: "PENDING" } });
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
        await route.fulfill({ contentType: "application/json", json: { upload_id: "upload-1", upload_url: "/api/v1/upload-1", filename: "short.wav", total_size_bytes: shortWav.buffer.length, chunk_size: shortWav.buffer.length, offset: 0, expires_at: "2030-01-01T00:00:00Z", status: "PENDING" } });
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
});
