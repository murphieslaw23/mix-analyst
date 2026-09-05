import { expect, test, type Page } from "@playwright/test";

type JobState = "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "CANCELLED";

function job(status: JobState, overrides: Record<string, unknown> = {}) {
  const failed = status === "FAILED";
  return {
    id: "job-1",
    mix_id: "mix-1",
    job_type: "MASTERING",
    status,
    progress_percent: failed ? 68 : status === "RUNNING" ? 42 : status === "SUCCEEDED" ? 100 : 0,
    current_stage: failed ? "Limiter" : status === "RUNNING" ? "Dynamics" : status === "QUEUED" ? "Queued" : null,
    parameters: {},
    celery_task_id: null,
    error_message: failed ? "The limiter could not create a safe output. No master was published." : null,
    created_at: "2030-01-01T00:00:00Z",
    started_at: "2030-01-01T00:00:02Z",
    finished_at: failed || status === "CANCELLED" || status === "SUCCEEDED" ? "2030-01-01T00:01:00Z" : null,
    stage_runs: [{
      id: "stage-1", stage_name: "Limiter", stage_version: "v1", status: failed ? "FAILED" : status === "SUCCEEDED" ? "COMPLETED" : "RUNNING",
      progress_percent: failed ? 68 : status === "SUCCEEDED" ? 100 : 42,
      stage_output: null, error_message: failed ? "Ceiling could not be held without audible distortion." : null,
      started_at: "2030-01-01T00:00:03Z", finished_at: failed ? "2030-01-01T00:01:00Z" : null,
    }],
    attempts: [{ id: "attempt-1", attempt_number: 1, status, worker_hostname: null, started_at: "2030-01-01T00:00:02Z", finished_at: null }],
    ...overrides,
  };
}

async function stubJobDetail(page: Page, getJob: () => unknown, onCommand?: (command: "cancel" | "retry") => unknown) {
  await page.route(/\/api\/v1\/jobs\/job-1$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ contentType: "application/json", json: getJob() });
      return;
    }
    const command = route.request().url().endsWith("/retry") ? "retry" : "cancel";
    await route.fulfill({ contentType: "application/json", json: onCommand?.(command) ?? getJob() });
  });
  await page.route(/\/api\/v1\/jobs\/job-1\/(cancel|retry)$/, async (route) => {
    const command = route.request().url().endsWith("/retry") ? "retry" : "cancel";
    await route.fulfill({ contentType: "application/json", json: onCommand?.(command) ?? getJob() });
  });
  // Force the supported fallback path. The detail state is still read from GET.
  await page.route(/\/api\/v1\/jobs\/job-1\/events$/, async (route) => {
    await route.fulfill({ status: 503, contentType: "application/json", json: {} });
  });
}

test.describe("Jobs progress and recovery", () => {
  test("a failed job retains stage recovery information and retries from a server response", async ({ page }) => {
    let current = job("FAILED");
    await stubJobDetail(page, () => current, (command) => {
      if (command === "retry") current = job("QUEUED", { attempts: [{ id: "attempt-2", attempt_number: 2, status: "QUEUED", worker_hostname: null, started_at: "2030-01-01T00:02:00Z", finished_at: null }] });
      return current;
    });
    await page.goto("/jobs/job-1");
    await expect(page.getByRole("heading", { name: "Mastering failed" })).toBeVisible();
    await expect(page.getByRole("alert")).toContainText("No master was published");
    await expect(page.getByText("Ceiling could not be held without audible distortion.")).toBeVisible();
    await page.getByRole("button", { name: "Retry job" }).click();
    await expect(page.getByRole("heading", { name: "Mastering job" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Cancel job" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Retry job" })).toHaveCount(0);
  });

  test("cancelling a running job waits for the server terminal state", async ({ page }) => {
    let current = job("RUNNING");
    await stubJobDetail(page, () => current, (command) => {
      if (command === "cancel") current = job("CANCELLED");
      return current;
    });
    await page.goto("/jobs/job-1");
    await expect(page.getByRole("button", { name: "Cancel job" })).toBeVisible();
    await page.getByRole("button", { name: "Cancel job" }).click();
    await expect(page.getByRole("heading", { name: "Mastering cancelled" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Cancel job" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Retry job" })).toBeVisible();
  });

  test("an unavailable event stream uses server polling instead of inventing progress", async ({ page }) => {
    let requests = 0;
    await stubJobDetail(page, () => {
      requests += 1;
      // The hook performs two authoritative reads before opening the stream:
      // initial load and reconnect reconciliation. Polling is the third read.
      return job("RUNNING", { progress_percent: requests > 2 ? 64 : 42 });
    });
    await page.goto("/jobs/job-1");
    await expect(page.getByText("Live progress is unavailable. Checking the server every few seconds.")).toBeVisible();
    await expect(page.getByRole("progressbar", { name: "Mastering progress" })).toHaveAttribute("value", "42");
    await expect(page.getByRole("progressbar", { name: "Mastering progress" })).toHaveAttribute("value", "64", { timeout: 9_000 });
    expect(requests).toBeGreaterThanOrEqual(2);
  });

  test("a live stream that stops yielding is recovered through server polling", async ({ page }) => {
    let requests = 0;
    await page.route(/\/api\/v1\/jobs\/job-1$/, async (route) => {
      requests += 1;
      await route.fulfill({ contentType: "application/json", json: job("RUNNING", { progress_percent: requests > 1 ? 64 : 42 }) });
    });
    // Playwright routes cannot hold an SSE response body open, so model the
    // browser transport directly: headers arrive, then the body never emits a
    // chunk until the hook's own AbortSignal closes it.
    await page.addInitScript(() => {
      const browserFetch = window.fetch.bind(window);
      window.fetch = async (input, init) => {
        const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
        if (url.includes("/api/v1/jobs/job-1/events")) {
          const body = new ReadableStream<Uint8Array>({
            start(controller) {
              init?.signal?.addEventListener("abort", () => controller.error(new DOMException("Aborted", "AbortError")), { once: true });
            },
          });
          return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
        }
        return browserFetch(input, init);
      };
    });
    await page.goto("/jobs/job-1");
    await expect(page.getByText("Live progress connected.")).toBeVisible();
    await expect(page.getByText("Live progress is unavailable. Checking the server every few seconds.")).toBeVisible({ timeout: 16_000 });
    await expect(page.getByRole("progressbar", { name: "Mastering progress" })).toHaveAttribute("value", "64", { timeout: 24_000 });
    expect(requests).toBeGreaterThanOrEqual(2);
  });

  test("a reconnect sends the server-supported Last-Event-ID cursor", async ({ page }) => {
    let eventRequests = 0;
    let replayCursor: string | undefined;
    await page.route(/\/api\/v1\/jobs\/job-1$/, async (route) => {
      await route.fulfill({ contentType: "application/json", json: job("RUNNING") });
    });
    await page.route(/\/api\/v1\/jobs\/job-1\/events$/, async (route) => {
      eventRequests += 1;
      if (eventRequests === 1) {
        await route.fulfill({ contentType: "text/event-stream", body: "id: 9\nevent: update\ndata: {\"status\":\"RUNNING\"}\n\n" });
        return;
      }
      replayCursor = route.request().headers()["last-event-id"];
      await route.fulfill({ status: 503, contentType: "application/json", json: {} });
    });
    await page.goto("/jobs/job-1");
    await expect.poll(() => replayCursor, { timeout: 9_000 }).toBe("9");
  });

  test("the jobs list consumes the authenticated paginated envelope", async ({ page }) => {
    await page.route("**/api/v1/jobs?page=1&limit=20", async (route) => {
      await route.fulfill({ contentType: "application/json", json: { items: [job("RUNNING")], total: 1 } });
    });
    await page.goto("/jobs");
    await expect(page.getByRole("list", { name: "1 job" })).toBeVisible();
    await expect(page.getByRole("link", { name: "View job" })).toHaveAttribute("href", "/jobs/job-1");
  });

  test("the jobs list loads the next authenticated page without hiding later jobs", async ({ page }) => {
    const firstPage = Array.from({ length: 20 }, (_, index) => job("RUNNING", { id: `job-${index + 1}` }));
    await page.route("**/api/v1/jobs?page=1&limit=20", async (route) => {
      await route.fulfill({ contentType: "application/json", json: { items: firstPage, total: 21 } });
    });
    await page.route("**/api/v1/jobs?page=2&limit=20", async (route) => {
      await route.fulfill({ contentType: "application/json", json: { items: [job("FAILED", { id: "job-21" })], total: 21 } });
    });
    await page.goto("/jobs");
    await expect(page.getByText("Showing 20 of 21 jobs.")).toBeVisible();
    await page.getByRole("button", { name: "Load more jobs" }).click();
    await expect(page.getByText("Showing 21 of 21 jobs.")).toBeVisible();
    await expect(page.getByRole("link", { name: "View job" })).toHaveCount(21);
    await expect(page.getByRole("link", { name: "View job" }).nth(20)).toHaveAttribute("href", "/jobs/job-21");
  });

  test("job detail reflows at a 390 pixel viewport", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await stubJobDetail(page, () => job("FAILED"));
    await page.goto("/jobs/job-1");
    await expect(page.getByRole("heading", { name: "Mastering failed" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  });
});
