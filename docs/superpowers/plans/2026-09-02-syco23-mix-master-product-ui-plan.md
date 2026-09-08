# SYCO23 Mix Master Product UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the analyzer-first single-page interface with an accessible, mobile-first Press Plate Intake product flow for Process, Jobs, Library, and More.

**Architecture:** React Router provides deep-linkable workflow routes. A typed same-origin API client converts backend DTOs into feature view models; feature-local hooks own resource state while an app-level player survives navigation. The current visualizer and MIDI code moves behind a lazy Library Detail Rig boundary, so no optional visualization can block processing or result recovery.

**Tech Stack:** React 18, TypeScript, Vite, React Router, Tailwind CSS, lucide-react, native audio, Playwright, axe-compatible accessibility assertions.

**Spec:** `docs/superpowers/specs/2026-09-02-syco23-mix-master-redesign-design.md`

## Global Constraints

- Browser API default is `/api/v1`; tests use real paginated DTO shapes rather than array-shaped mocks.
- Press Plate visual tokens use oil, iron, bone, fog, and rust orange; no purple/neon/cyberpunk/terminal treatment.
- Process has one primary action and shows no fake connectivity/data/playback success.
- Every primary flow renders loading, empty, error, retry, and success states.
- Keyboard, live-region, dialog, reduced-motion, and 390 px reflow requirements apply to every task.

---

### Task 1: Establish tokenized shell, router, and responsive primary navigation

**Files:**
- Create: `web/src/app/AppShell.tsx`, `web/src/app/router.tsx`, `web/src/app/routes.ts`, `web/src/styles/tokens.css`, `web/src/components/ui/Button.tsx`, `web/src/components/ui/LiveRegion.tsx`, `web/tests/e2e/specs/app-shell.spec.ts`
- Modify: `web/src/main.tsx`, `web/src/index.css`, `web/tailwind.config.js`, `web/package.json`, `web/src/App.tsx`

**Interfaces:**
- Produces route constants `PROCESS_ROUTE`, `JOBS_ROUTE`, `LIBRARY_ROUTE`, and `MORE_ROUTE`.
- Produces `<AppShell><Outlet /></AppShell>` with mobile bottom navigation and desktop rail.
- Produces semantic design tokens such as `--surface-oil`, `--surface-iron`, `--text-bone`, and `--accent-rust`.

- [ ] **Step 1: Write failing route and 390 px navigation tests**

```ts
test('mobile navigation reaches each primary destination without horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/process');
  await page.getByRole('link', { name: 'Jobs' }).click();
  await expect(page).toHaveURL(/\/jobs$/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
```

- [ ] **Step 2: Run the shell test against the one-tab app**

Run: `pnpm --dir web test:e2e -- app-shell.spec.ts`

Expected: failure because `/process` and semantic primary links do not exist.

- [ ] **Step 3: Install and wire route dependencies**

```tsx
export const router = createBrowserRouter([
  { element: <AppShell />, children: [
    { path: '/process', element: <ProcessPage /> },
    { path: '/jobs', element: <JobsPage /> },
    { path: '/library', element: <LibraryPage /> },
  ]},
  { path: '*', element: <Navigate to="/process" replace /> },
]);
```

Use a mobile bottom bar with text labels and `aria-current`, then switch to a desktop side rail via CSS. Replace hardcoded theme colors with semantic tokens. Keep the application dark by default; only retain a light mode if every tokenized surface supports it.

- [ ] **Step 4: Verify routes, type-check, and reflow**

Run: `pnpm --dir web build && pnpm --dir web test:e2e -- app-shell.spec.ts`

Expected: build succeeds; tested routes have no overflow at 390 px.

- [ ] **Step 5: Commit shell and tokens**

```bash
git add web
git commit -m "feat: add responsive Press Plate application shell"
```

### Task 2: Add a typed same-origin API client and honest resource states

**Files:**
- Create: `web/src/api/client.ts`, `web/src/api/contracts.ts`, `web/src/api/mixAdapters.ts`, `web/src/components/ui/EmptyState.tsx`, `web/src/components/ui/ErrorState.tsx`, `web/src/components/ui/Skeleton.tsx`, `web/tests/e2e/specs/api-contracts.spec.ts`
- Modify: `web/src/App.tsx`, `web/tests/e2e/specs/long_set_flows.spec.ts`

**Interfaces:**
- Produces `apiClient<T>(path, init?) -> Promise<T>` using `/api/v1` by default.
- Consumes `MixListResponse { items: MixOut[]; total: number }` and produces `LibraryMixSummary`.
- Produces `ApiProblem { status: number; title: string; detail: string; retryable: boolean }`.

- [ ] **Step 1: Write the real list DTO test**

```ts
test('library reads the paginated backend response and never renders a fabricated mix', async ({ page }) => {
  await page.route('**/api/v1/mixes', route => route.fulfill({ json: { items: [], total: 0 } }));
  await page.goto('/library');
  await expect(page.getByText('No completed masters yet')).toBeVisible();
  await expect(page.getByText('SYCO23 — Live Sound-System Transmission 23')).toHaveCount(0);
});
```

- [ ] **Step 2: Run the focused contract test**

Run: `pnpm --dir web test:e2e -- api-contracts.spec.ts`

Expected: failure because the current app calls `mixes.map` on the DTO object and falls back to demo content.

- [ ] **Step 3: Implement transport and adapter boundaries**

```ts
const apiBase = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

export async function apiClient<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, { ...init, credentials: 'include' });
  if (!response.ok) throw await toApiProblem(response);
  return response.json() as Promise<T>;
}
```

Adapt list, mix detail, analysis, tracks, transitions, mastering report, and artifacts separately. Render explicit `<Skeleton>`, `<EmptyState>`, `<ErrorState onRetry>`, and content states; delete demo fallback and simulated playback state.

- [ ] **Step 4: Verify DTO and error behavior**

Run: `pnpm --dir web build && pnpm --dir web test:e2e -- api-contracts.spec.ts`

Expected: empty/error/real paginated contract tests pass.

- [ ] **Step 5: Commit the API boundary**

```bash
git add web
git commit -m "feat: consume mix API through typed same-origin client"
```

### Task 3: Build the Press Plate Process journey and resumable upload UI

**Files:**
- Create: `web/src/features/process/ProcessPage.tsx`, `web/src/features/process/useUpload.ts`, `web/src/features/process/ProcessForm.tsx`, `web/src/features/process/processReducer.ts`, `web/src/features/process/types.ts`, `web/tests/e2e/specs/process-flow.spec.ts`
- Modify: `web/src/app/router.tsx`, `web/src/components/ui/LiveRegion.tsx`

**Interfaces:**
- Produces `UploadState = 'idle' | 'selected' | 'initializing' | 'uploading' | 'finalizing' | 'ready' | 'error' | 'aborted'`.
- Produces `startUpload(file: File, input: ProcessSettings): Promise<{ mixId: string }>`.
- Navigates to `/jobs/:jobId` only after the server returns a persisted job.

- [ ] **Step 1: Write a user-visible upload-state test**

```ts
test('a valid selection shows progress then navigates only after a job is created', async ({ page }) => {
  await page.goto('/process');
  await page.getByLabel('Choose audio').setInputFiles('tests/fixtures/short.wav');
  await expect(page.getByText('Ready to process')).toBeVisible();
  await page.getByRole('button', { name: 'Start mastering' }).click();
  await expect(page.getByRole('progressbar')).toBeVisible();
  await expect(page).toHaveURL(/\/jobs\//);
});
```

- [ ] **Step 2: Run the Process test**

Run: `pnpm --dir web test:e2e -- process-flow.spec.ts`

Expected: failure because the Process route and upload state machine do not exist.

- [ ] **Step 3: Implement reducer-first Process UI**

```ts
type UploadEvent =
  | { type: 'SELECT'; file: File }
  | { type: 'UPLOAD_PROGRESS'; percent: number }
  | { type: 'READY'; mixId: string }
  | { type: 'FAIL'; problem: ApiProblem };
```

Use the backend upload-session protocol from the core plan. Keep one primary choice action until a valid file is selected, then one “Start mastering” action after accessible preset controls. Announce only meaningful state transitions through the live region.

- [ ] **Step 4: Verify keyboard, validation, and recovery states**

Run: `pnpm --dir web test:e2e -- process-flow.spec.ts`

Expected: valid/invalid selection, upload failure/retry, progress semantics, and post-create routing pass.

- [ ] **Step 5: Commit the Process flow**

```bash
git add web
git commit -m "feat: add mobile-first audio Process flow"
```

### Task 4: Build Jobs list/detail with replay-aware progress, retry, and cancellation

**Files:**
- Create: `web/src/features/jobs/JobsPage.tsx`, `web/src/features/jobs/JobDetailPage.tsx`, `web/src/features/jobs/useJobEvents.ts`, `web/src/features/jobs/jobAdapters.ts`, `web/src/components/ui/Progress.tsx`, `web/src/components/ui/StatusBadge.tsx`, `web/tests/e2e/specs/jobs-flow.spec.ts`
- Modify: `web/src/app/router.tsx`, `web/src/api/contracts.ts`

**Interfaces:**
- Consumes `GET /jobs/:jobId` and `GET /jobs/:jobId/events` with `Last-Event-ID`.
- Produces `useJobEvents(jobId): { job: JobViewModel; reconnecting: boolean; cancel(): Promise<void>; retry(): Promise<void> }`.

- [ ] **Step 1: Write SSE reconnect and recovery tests**

```ts
test('a failed job retains the stage error and exposes retry', async ({ page }) => {
  await page.goto('/jobs/job-failed');
  await expect(page.getByText('Mastering failed')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Retry job' })).toBeVisible();
});
```

- [ ] **Step 2: Run the Jobs test**

Run: `pnpm --dir web test:e2e -- jobs-flow.spec.ts`

Expected: failure because no Jobs route or durable event client exists.

- [ ] **Step 3: Implement SSE-first with polling fallback**

```ts
const eventSource = new EventSource(`${apiBase}/jobs/${jobId}/events`, { withCredentials: true });
eventSource.addEventListener('job', event => applyEvent(JSON.parse(event.data), event.lastEventId));
```

Persist the latest event ID per job only as a reconnect cursor; refresh authoritative job state on reconnect and fall back to timed GET polling when SSE is unavailable. Cancel/retry controls are semantic buttons and terminal states are non-destructive.

- [ ] **Step 4: Verify progress semantics and failure recovery**

Run: `pnpm --dir web test:e2e -- jobs-flow.spec.ts`

Expected: accessible stage/progress updates, error persistence, retry, and cancel state tests pass.

- [ ] **Step 5: Commit Jobs experience**

```bash
git add web
git commit -m "feat: add durable jobs progress and recovery UI"
```

### Task 5: Build Library detail with genuine playback and optional Rig boundary

**Files:**
- Create: `web/src/features/library/LibraryPage.tsx`, `web/src/features/library/MixDetailPage.tsx`, `web/src/features/library/ABPlayer.tsx`, `web/src/features/library/usePlayer.ts`, `web/src/features/rig/RigPanel.tsx`, `web/tests/e2e/specs/library-flow.spec.ts`
- Modify: `web/src/app/router.tsx`, `web/src/App.tsx`, `web/src/visualizer/SpeakerStackVisualizer.tsx`, `web/src/components/MidiControllerModal.tsx`

**Interfaces:**
- Produces `playArtifact(url: string): Promise<void>` that sets playing state only after `HTMLAudioElement.play()` resolves.
- Produces `ABPlayer` with explicit original/mastered selection and an accessible transport control.
- Produces a lazy `<RigPanel mixId={mixId} />` that is not loaded by default.

- [ ] **Step 1: Write playback and reduced-motion tests**

```ts
test('library does not report playing when the browser rejects audio playback', async ({ page }) => {
  await page.addInitScript(() => HTMLMediaElement.prototype.play = () => Promise.reject(new DOMException('blocked')));
  await page.goto('/library/mix-1');
  await page.getByRole('button', { name: 'Play mastered audio' }).click();
  await expect(page.getByText('Playback needs a browser gesture or supported audio')).toBeVisible();
});
```

- [ ] **Step 2: Run the Library test**

Run: `pnpm --dir web test:e2e -- library-flow.spec.ts`

Expected: failure because the current app simulates success without an audio source.

- [ ] **Step 3: Implement result library and A/B transport**

```tsx
<button aria-pressed={activeArtifact === 'mastered'} onClick={() => setActiveArtifact('mastered')}>
  Mastered
</button>
<button onClick={() => void playArtifact(activeUrl)}>Play mastered audio</button>
```

Display result metadata, loudness, artifact download, and truthful playback errors. Move visualizer/MIDI to `React.lazy`; add keyboard alternatives, dialog semantics, focus handling, and reduced-motion/strobe-safe defaults before exposing the Rig control.

- [ ] **Step 4: Verify Library flow and accessibility controls**

Run: `pnpm --dir web build && pnpm --dir web test:e2e -- library-flow.spec.ts`

Expected: A/B selection, playback failure, download, lazy Rig, and keyboard control tests pass.

- [ ] **Step 5: Commit Library and optional Rig separation**

```bash
git add web
git commit -m "feat: add results library and honest A/B playback"
```

### Task 6: Add automated accessibility and responsive regression coverage

**Files:**
- Create: `web/tests/e2e/specs/accessibility.spec.ts`, `web/tests/e2e/specs/reduced-motion.spec.ts`
- Modify: `web/playwright.config.ts`, `web/tests/e2e/specs/long_set_flows.spec.ts`, `web/tests/e2e/specs/speaker_stack_midi.spec.ts`

**Interfaces:**
- Produces shared test helper `assertNoHorizontalOverflow(page, width)`.
- Produces a browser matrix that distinguishes viewport emulation from real engine coverage.

- [ ] **Step 1: Write core semantics assertions**

```ts
test('Process has one visible primary action and a named file input', async ({ page }) => {
  await page.goto('/process');
  await expect(page.getByLabel('Choose audio')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Choose audio' })).toHaveCount(1);
});
```

- [ ] **Step 2: Run the regression suite**

Run: `pnpm --dir web test:e2e -- accessibility.spec.ts reduced-motion.spec.ts`

Expected: failures reveal current canvas-only/invalid dialog/motion behavior.

- [ ] **Step 3: Add semantic assertions and repair stale tests**

```ts
await page.emulateMedia({ reducedMotion: 'reduce' });
await expect(page.locator('[data-motion="rig"]')).toHaveAttribute('data-motion', 'reduced');
```

Replace selectors for nonexistent controls and first-canvas assumptions with role/test IDs tied to the actual primary control. Keep engine coverage claims truthful.

- [ ] **Step 4: Run build and all E2E tests**

Run: `pnpm --dir web build && pnpm --dir web test:e2e`

Expected: no stale selector, overflow, semantic, or reduced-motion regression.

- [ ] **Step 5: Commit UI verification suite**

```bash
git add web
git commit -m "test: cover responsive accessible processing workflows"
```

### Task 7: Add mobile batch review and partial-failure recovery UI

**Files:**
- Create: `web/src/features/batches/BatchReviewPage.tsx`, `web/src/features/batches/BatchDetailPage.tsx`, `web/src/features/batches/useBatch.ts`, `web/src/features/batches/batchAdapters.ts`, `web/tests/e2e/specs/batch-flow.spec.ts`
- Modify: `web/src/app/router.tsx`, `web/src/features/process/ProcessPage.tsx`, `web/src/features/jobs/JobsPage.tsx`, `web/src/api/contracts.ts`

**Interfaces:**
- Consumes `POST /batches`, `GET /batches/:batchId`, and failed-item retry commands from the core plan.
- Produces `BatchReviewState { selectedMixIds: Set<string>; preset: ProcessSettings; maxParallelism: number }`.
- Produces `/batches/:batchId` detail route linked from Jobs.

- [ ] **Step 1: Write a mobile batch selection and partial-failure test**

```ts
test('batch review processes only selected items and exposes retry for failed children', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/process?mode=batch');
  await page.getByRole('checkbox', { name: 'set-b.wav' }).check();
  await page.getByRole('button', { name: 'Create batch' }).click();
  await expect(page).toHaveURL(/\/batches\//);
  await expect(page.getByRole('button', { name: 'Retry failed items' })).toBeVisible();
});
```

- [ ] **Step 2: Run the batch UI test**

Run: `pnpm --dir web test:e2e -- batch-flow.spec.ts`

Expected: failure because the current UI has no batch route and no selection-controlled processing.

- [ ] **Step 3: Implement review and aggregate-detail states**

```tsx
<input type="checkbox" aria-label={item.filename} checked={selectedMixIds.has(item.id)} onChange={() => toggle(item.id)} />
<button disabled={selectedMixIds.size === 0} onClick={() => void createBatch()}>Create batch</button>
```

Use a stacked mobile list, never a fixed-width desktop table. Make selected count, bounds, preset, aggregate progress, completed items, failed items, and retry scope visible. The detail page consumes only authoritative batch counts and child statuses.

- [ ] **Step 4: Verify mobile reflow and recovery behavior**

Run: `pnpm --dir web test:e2e -- batch-flow.spec.ts`

Expected: selection determines submitted IDs, no horizontal overflow at 390 px, and retry does not re-submit successful items.

- [ ] **Step 5: Commit batch UI**

```bash
git add web
git commit -m "feat: add mobile batch review and recovery"
```
