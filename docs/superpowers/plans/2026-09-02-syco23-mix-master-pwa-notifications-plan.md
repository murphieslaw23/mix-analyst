# SYCO23 Mix Master PWA and Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an HTTPS-only installable app with coherent offline/update behavior, a persistent notification center, and privacy-safe opt-in Web Push for durable job outcomes.

**Architecture:** A generated versioned service-worker precache serves static application assets, while operational requests remain network-only. PostgreSQL owns notification and delivery records; the worker writes terminal notification/outbox state transactionally; the web client renders that state before it ever asks for Push permission. Notification clicks use server-authorized routes that already exist in the product UI plan.

**Tech Stack:** Vite, Workbox-compatible PWA build, Service Worker, IndexedDB, BroadcastChannel, FastAPI, SQLAlchemy/Alembic, pywebpush, VAPID, Playwright, real browser/device tests.

**Spec:** `docs/superpowers/specs/2026-09-02-syco23-mix-master-redesign-design.md`

## Global Constraints

- Production Push and Service Worker behavior require HTTPS; HTTP is not release-capable.
- `api/**`, SSE, uploads, audio streams, downloads, subscription APIs, and preferences are always network-only.
- An OS payload holds `notification_id`, `version`, and a safe same-origin route only.
- Permission request originates from the user selecting notification settings, never from page load, app install, or a completed job.
- Notification state and delivery idempotency live in PostgreSQL; Redis is not a notification ledger.

---

### Task 1: Harden HTTPS ingress, manifest assets, and deployment checks

**Files:**
- Modify: `web/nginx.conf`, `web/Dockerfile`, `docker-compose.yml`, `web/public/manifest.webmanifest`, `web/vercel.json`, `README.md`
- Create: `infra/caddy/Caddyfile`, `web/public/icon-192.png`, `web/public/icon-512.png`, `web/public/icon-maskable-512.png`, `web/public/apple-touch-icon.png`, `web/public/pwa-screenshot-process.png`, `tests/integration/test_deployment_contract.py`

**Interfaces:**
- Produces HTTPS ingress with `/api/` proxying to API and a canonical public origin.
- Produces manifest `id: "/"` with separate standard/maskable PNG assets.

- [ ] **Step 1: Write deployment-contract tests**

```python
def test_manifest_declares_stable_identity_and_raster_maskable_icon():
    manifest = json.loads(Path("web/public/manifest.webmanifest").read_text())
    assert manifest["id"] == "/"
    assert any(
        icon["src"] == "/icon-maskable-512.png" and icon["purpose"] == "maskable"
        for icon in manifest["icons"]
    )
```

- [ ] **Step 2: Run the manifest test**

Run: `pytest tests/integration/test_deployment_contract.py -q`

Expected: failure because current manifest has no stable ID or raster maskable icon.

- [ ] **Step 3: Add HTTPS ingress and complete manifest metadata**

```caddy
{$PUBLIC_ORIGIN} {
  reverse_proxy /api/* api:8000
  root * /srv
  file_server
}
```

Expose only HTTPS publicly; retain an explicitly documented local development path. Add screenshot, shortcuts to Process/Jobs, validated PNG assets, and Apple touch icon. Do not claim successful PWA delivery for plain HTTP LAN deployment.

- [ ] **Step 4: Verify deployment contract**

Run: `pytest tests/integration/test_deployment_contract.py -q && jq . web/public/manifest.webmanifest`

Expected: valid JSON and all manifest asset tests pass.

- [ ] **Step 5: Commit install prerequisites**

```bash
git add infra web docker-compose.yml README.md tests/integration/test_deployment_contract.py
git commit -m "feat: add HTTPS PWA deployment contract"
```

### Task 2: Replace handwritten cache behavior with a versioned generated precache

**Files:**
- Modify: `web/package.json`, `web/vite.config.ts`, `web/src/main.tsx`, `web/src/App.tsx`
- Delete: `web/public/sw.js`
- Create: `web/src/pwa/registerServiceWorker.ts`, `web/src/pwa/UpdateBanner.tsx`, `web/src/pwa/offline.ts`, `web/tests/e2e/specs/pwa-offline.spec.ts`, `web/tests/e2e/specs/pwa-update.spec.ts`

**Interfaces:**
- Produces `registerServiceWorker({ onNeedRefresh, onOfflineReady })`.
- Produces a user-operated `applyUpdate(): Promise<void>` that sends `SKIP_WAITING` only after confirmation.

- [ ] **Step 1: Write offline navigation and no-API-cache tests**

```ts
test('offline navigation renders an app fallback while API requests are not served from cache', async ({ page, context }) => {
  await page.goto('/process');
  await context.setOffline(true);
  await page.reload();
  await expect(page.getByText(/offline|Process/i)).toBeVisible();
  const response = await page.request.get('/api/v1/mixes').catch(() => null);
  expect(response).toBeNull();
});
```

- [ ] **Step 2: Run PWA tests against the handwritten worker**

Run: `pnpm --dir web test:e2e -- pwa-offline.spec.ts pwa-update.spec.ts`

Expected: failure because current worker misses bundles and returns `index.html` for failed assets.

- [ ] **Step 3: Configure generated precache and explicit runtime policy**

```ts
VitePWA({
  registerType: 'prompt',
  workbox: {
    navigateFallback: '/index.html',
    navigateFallbackDenylist: [/^\/api\//, /^\/downloads\//],
    runtimeCaching: [],
  },
});
```

Use generated revisioned assets. Ensure only navigation receives app-shell fallback. Show an UpdateBanner; do not call `skipWaiting()` on install.

- [ ] **Step 4: Verify offline and update lifecycle**

Run: `pnpm --dir web build && pnpm --dir web test:e2e -- pwa-offline.spec.ts pwa-update.spec.ts`

Expected: controlled offline navigation, no cached API response, and one user-visible update decision.

- [ ] **Step 5: Commit safe service-worker behavior**

```bash
git add web
git commit -m "feat: add versioned PWA precache and update control"
```

### Task 3: Persist notification center and terminal job notifications

**Files:**
- Create: `api/app/models/notification.py`, `api/app/services/notifications.py`, `api/app/api/v1/notifications.py`, `api/app/schemas/notification.py`, `web/src/features/notifications/NotificationCenterPage.tsx`, `web/src/features/notifications/useNotifications.ts`, `web/tests/e2e/specs/notification-center.spec.ts`, `tests/integration/test_notifications.py`, `api/alembic/versions/20260902_06_notifications.py`
- Modify: `api/app/main.py`, `api/app/models/__init__.py`, `worker/tasks.py`, `api/app/api/v1/jobs.py`, `web/src/app/router.tsx`

**Interfaces:**
- Produces `create_job_notification(db, job, kind) -> Notification` with unique `dedupe_key`.
- Produces `GET /notifications`, `POST /notifications/:id/read`, and `POST /notifications/:id/dismiss` scoped to the principal.
- Produces client `useNotifications()` with BroadcastChannel invalidation and local cache only for rendering recent items.

- [ ] **Step 1: Write durable deduplication and UI persistence tests**

```python
def test_duplicate_terminal_processing_creates_one_notification(db, completed_job):
    first = create_job_notification(db, completed_job, "job.succeeded")
    second = create_job_notification(db, completed_job, "job.succeeded")
    assert first.id == second.id
```

```ts
test('notification read state survives a reload', async ({ page }) => {
  await page.goto('/more/notifications');
  await page.getByRole('button', { name: 'Mark as read' }).click();
  await page.reload();
  await expect(page.getByText('Read')).toBeVisible();
});
```

- [ ] **Step 2: Run notification tests**

Run: `pytest tests/integration/test_notifications.py -q && pnpm --dir web test:e2e -- notification-center.spec.ts`

Expected: failure because current notification is an ephemeral string in `App.tsx`.

- [ ] **Step 3: Implement transactional notification creation and center routes**

```python
def create_job_notification(db: Session, job: Job, kind: str) -> Notification:
    dedupe_key = f"{kind}:{job.id}:{job.finished_at.isoformat()}"
    return get_or_create_notification(
        db, user_id=job.owner_id, dedupe_key=dedupe_key, deep_link=f"/jobs/{job.id}"
    )
```

Create the notification inside the same transaction as terminal job state/event/outbox. Render center data from the API; foreground job events create an accessible toast that links to the center item without emitting an OS notification.

- [ ] **Step 4: Verify center state and authorization**

Run: `pytest tests/integration/test_notifications.py -q && pnpm --dir web test:e2e -- notification-center.spec.ts`

Expected: one durable item per terminal event, cross-owner isolation, read/dismiss persistence, and foreground accessibility assertions pass.

- [ ] **Step 5: Commit notification center**

```bash
git add api worker web tests
git commit -m "feat: add durable notification center"
```

### Task 4: Add explicit Push enrollment and robust delivery records

**Files:**
- Create: `api/app/models/push_subscription.py`, `api/app/services/push.py`, `api/app/api/v1/push.py`, `api/app/schemas/push.py`, `worker/push_dispatcher.py`, `web/src/features/notifications/PushSettings.tsx`, `web/src/pwa/push.ts`, `tests/integration/test_push_delivery.py`, `web/tests/e2e/specs/push-settings.spec.ts`, `api/alembic/versions/20260902_07_push.py`
- Modify: `api/requirements.txt`, `api/app/main.py`, `api/app/models/__init__.py`, `web/src/features/notifications/NotificationCenterPage.tsx`

**Interfaces:**
- Produces `POST /push/subscriptions`, `DELETE /push/subscriptions/:id`, and `POST /push/subscriptions/refresh` for the authenticated principal.
- Produces `deliver_notification(notification_id) -> DeliveryOutcome` with bounded retry/backoff and 404/410 deactivation.
- Produces `subscribeToPush(registration, vapidPublicKey): Promise<PushSubscriptionJSON>` only after click.

- [ ] **Step 1: Write permission-timing and delivery-deactivation tests**

```ts
test('notification permission is not requested until the user enables job notifications', async ({ page }) => {
  await page.goto('/more/notifications');
  await expect(page.getByText('Notify me when jobs finish')).toBeVisible();
  await page.getByRole('button', { name: 'Notify me when jobs finish' }).click();
  await expect(page.getByText(/permission/i)).toBeVisible();
});
```

```python
def test_gone_push_endpoint_is_deactivated_after_one_delivery_attempt(
    client, subscription, notification
):
    outcome = deliver_notification(notification.id)
    assert outcome.status == "deactivated"
```

- [ ] **Step 2: Run the Push test baseline**

Run: `pytest tests/integration/test_push_delivery.py -q && pnpm --dir web test:e2e -- push-settings.spec.ts`

Expected: failure because no Push endpoint, subscription model, or user-triggered settings flow exists.

- [ ] **Step 3: Implement encrypted subscription persistence and sender policy**

```python
payload = {
    "version": 1,
    "notification_id": notification.id,
    "deep_link": notification.deep_link,
}
webpush(
    subscription_info=decrypt(subscription.encrypted_payload),
    data=json.dumps(payload),
    vapid_private_key=settings.vapid_private_key,
    vapid_claims={"sub": settings.vapid_contact},
)
```

Keep VAPID private material server-only. Deduplicate deliveries by notification/subscription pair; back off 429/5xx, deactivate 404/410, and never include filename/error/credential data in payload.

- [ ] **Step 4: Verify opt-in and delivery behavior**

Run: `pytest tests/integration/test_push_delivery.py -q && pnpm --dir web test:e2e -- push-settings.spec.ts`

Expected: no automatic permission prompt, one subscription per endpoint hash, 410 deactivation, and privacy-safe payload tests pass.

- [ ] **Step 5: Commit Push delivery**

```bash
git add api worker web tests
git commit -m "feat: add opt-in privacy-safe web push"
```

### Task 5: Handle notification clicks and release verification matrix

**Files:**
- Create: `web/src/pwa/notificationServiceWorker.ts`, `web/tests/e2e/specs/notification-click.spec.ts`, `docs/release/pwa-notification-matrix.md`
- Modify: `web/vite.config.ts`, `web/src/app/router.tsx`, `README.md`

**Interfaces:**
- Produces service-worker handlers for `push`, `notificationclick`, `notificationclose`, and `pushsubscriptionchange`.
- Consumes a same-origin deep link and validates it against `/jobs/:jobId` or `/more/notifications` before opening/focusing a window.

- [ ] **Step 1: Write route-safety test**

```ts
test('invalid notification route falls back to notification center', async ({ page }) => {
  await page.goto('/more/notifications?fromPush=unknown');
  await expect(page.getByRole('heading', { name: 'Notifications' })).toBeVisible();
});
```

- [ ] **Step 2: Run the click test**

Run: `pnpm --dir web test:e2e -- notification-click.spec.ts`

Expected: failure because no service-worker Push handlers or fallback route exist.

- [ ] **Step 3: Implement safe client focus/open behavior**

```ts
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const path = isSafeNotificationPath(event.notification.data?.deep_link) ? event.notification.data.deep_link : '/more/notifications';
  event.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then(existing => existing[0]?.focus() ?? clients.openWindow(path)));
});
```

Validate authorization server-side when the route loads; deleted/unauthorized jobs present a center fallback instead of an arbitrary URL.

- [ ] **Step 4: Run automated suite and record physical evidence**

Run: `pnpm --dir web build && pnpm --dir web test:e2e -- notification-click.spec.ts`

Expected: automated route-safety tests pass. Record real Chrome/Edge, Firefox, Safari macOS, Android, and installed iOS/iPadOS evidence in `docs/release/pwa-notification-matrix.md`; label unavailable devices as pending rather than passed.

- [ ] **Step 5: Commit release matrix**

```bash
git add web docs README.md
git commit -m "test: document PWA and notification release matrix"
```
