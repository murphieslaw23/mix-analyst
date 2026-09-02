# SYCO23 Mix Master — Canonical Redesign Design

**Status:** Approved design; awaiting plan review  
**Foundation:** `murphieslaw23/mix-analyst` on `codex/full-app-redesign`  
**Selected visual direction:** Press Plate Intake (mobile Process screen)

## 1. Purpose and decisions

SYCO23 Mix Master will become a reliable, mobile-first audio processing application for DJs and producers. It must take a user from choosing source audio to a durable job, a trustworthy result, A/B listening, and download without pretending that network, processing, or playback succeeded when it did not.

The canonical `mix-analyst` repository is the product foundation. The local `freetekno-deploy` application is an algorithm and interaction reference only: its restoration, mastering, tagging, naming, waveform, and batch behavior will be migrated behind new durable boundaries; its process-local jobs, direct file paths, fake readiness claims, desktop table, and rapid polling will not be migrated.

The selected visual direction is **Press Plate Intake**: a vertical, bolted speaker-totem composition with a single strong action. It implements the active SYSTEM CORRUPT / SYCO23 brand rather than the current purple/neon analyzer aesthetic. The system is not a terminal, a generic dashboard, a streaming service, or a neon rave interface.

## 2. Product scope and non-goals

### In scope

- Secure, owned audio ingest for individual and bounded batch work.
- Durable analysis, restoration, mastering, metadata, waveform, export, and batch jobs.
- A responsive application with Process, Jobs, Library, and More destinations.
- Honest live progress, failure, cancellation, retry, result inspection, A/B playback, and downloads.
- Installability, carefully scoped offline behavior, a notification center, and opt-in Web Push.
- Keyboard, screen-reader, reduced-motion, touch, privacy, and deployment hardening.

### Explicitly deferred

- Broadcast, stems, and cover-enrichment workflows remain hidden until backed by real workers and their own contracts.
- The 3D speaker rig and MIDI capabilities remain optional Mix Detail enhancements; they do not occupy the primary processing flow.
- Full offline audio processing is not promised. The PWA caches the application shell and selected safe presentation data, while uploads, API requests, streams, and downloads remain network-only.
- A public multi-tenant model is not assumed silently. Before release, deployment must select either authenticated multi-user ownership or a private single-administrator appliance model.

## 3. Experience architecture

### Primary destinations

| Destination | User outcome | Mobile treatment | Desktop treatment |
| --- | --- | --- | --- |
| **Process** | Select audio, validate it, choose a preset, start work. | Default screen and bottom-nav primary action. | First rail item; intake stack is anchored beside the form. |
| **Jobs** | See active, historical, failed, cancelled, and batch work; recover safely. | Progress-first list; a job opens a focused detail route. | Filterable list with job detail pane or route. |
| **Library** | Find completed outputs; compare, play, download, and inspect analysis. | Search then compact result rows; player remains sticky when active. | List/detail layout with a lazy optional Rig panel. |
| **More** | Installation, notification preferences, MIDI, accessibility, support, privacy, and legal. | Bottom-sheet or route, never a crowded primary header. | Secondary navigation or account menu. |

Routes are real and deep-linkable: `/process`, `/jobs`, `/jobs/:jobId`, `/library`, `/library/:mixId`, and `/more/*`. Route state replaces the current in-memory `activeTab`, making back/forward, reload, notification clicks, and shared support links coherent.

### Core user journeys

1. **Single item:** choose/drop a file → type and size validation → optional metadata and mastering preset → confirmation → persisted job → live stage progress → result → A/B listen → download.
2. **Failure:** an actionable stage-level failure preserves the chosen settings and source record, then offers retry, diagnostics, or safe cancellation. Empty or fake data is never substituted for a failed request.
3. **Batch:** select owned uploaded assets → review item settings and filename conflicts → create a persistent parent batch → follow child status and aggregate result → resolve only failed items or download complete outputs.
4. **Return later:** reopening a route hydrates the authoritative job or library resource. The client may retain recent IDs for convenience but never treats local state as truth.
5. **Notification:** an explicit user action enables notifications. A completed/failed job creates one durable in-app item; a matching Push payload holds only a notification ID and authorized same-origin deep link.

## 4. Visual and responsive system

### Direction rules

- **Form:** vertical slabs, steel plates, rails, bolts, speaker-driver circles, and a tall central totem. Texture is subdued background material, not a legibility layer.
- **Color:** oil/ash page base, charcoal/iron surfaces, bone primary text, fog secondary text, and rust orange as the Process action/status accent. A single asset uses one key color; later result screens may use one approved alternate, never several accents together.
- **Type:** condensed industrial display type for headlines and high-signal state; clean sans-serif for instructions; mono only for durations, formats, LUFS, and IDs.
- **Controls:** one clear primary action per screen; buttons and inputs have at least 44 × 44 CSS pixels; body copy targets 14–16 px; color is never the sole status signal.
- **Motion:** subtle, opt-in material/signal movement. `prefers-reduced-motion` disables nonessential orbit, animation, and strobe. Strobe is off by default and cannot flash at unsafe rates.

### Layout behavior

At 390 px, the Process screen orders identity, a dimmed speaker/totem visual, processing state, one primary action, and only essential helper copy. It avoids a desktop-width table or an oversized fixed canvas. At tablet widths, the visual and operational stack may sit side by side. At desktop widths, the totem anchors one side while operations form a vertically weighted column on the other; equal-weight dashboard grids are prohibited.

The generated Press Plate reference is a direction for composition, material, contrast, hierarchy, and interaction emphasis—not a literal bitmap to stretch into every view. The production UI uses accessible HTML controls and a tokenized visual system rather than embedding generated UI imagery as an interface.

## 5. Frontend structure and contracts

### Application layers

- `app/`: router, `AppShell`, session/ownership context, theme, install/update coordination, and one shell-level player provider.
- `api/`: same-origin client (`/api/v1` by default), generated or explicit DTO contracts, normalized problem errors, request cancellation, and resource adapters.
- `features/process/`: selected-file and resumable-upload state machine; preset/settings form; confirmation.
- `features/jobs/`: jobs list/detail, SSE with polling fallback, cancellation/retry, stage progress, batch summary, and error recovery.
- `features/library/`: mix list/detail adapters, result playback, A/B comparison, waveform and download artifacts.
- `features/notifications/`: durable center, unread/read/dismiss state, Push enrollment, preference UI, and cross-tab synchronization.
- `components/ui/`: semantic Button, FormField, StatusBadge, Progress, EmptyState, ErrorState, Skeleton, Toast live region, and Dialog primitives.
- `features/rig/`: lazy-loaded visualizer and MIDI UI, isolated from primary job completion and playback.

No UI view model is reused as a transport contract. Mix list pagination, detail metadata, tracks, transitions, analysis, mastering report, audio URLs, and exports are fetched/adapted as distinct resources. The current live API mismatch—an expected array versus `{items,total}`—must be corrected with contract tests before screen work is treated as complete.

### Client state machines

The single-file upload flow is `idle → selected → initializing → uploading → finalizing → ready | error | aborted`. The job flow is derived from server state, not animation: `QUEUED → RUNNING → SUCCEEDED | FAILED | CANCELLED`, with explicit retry attempt metadata. Batch status is an aggregate of persisted child state. Every loading, empty, error, and retry state is rendered explicitly.

## 6. Backend and worker design

### Authority boundaries

- **API/control plane:** authentication, tenant-scoped authorization, request validation, upload coordination, job/batch commands, read models, and signed artifact URLs. It imports no heavy DSP package.
- **PostgreSQL:** authoritative users/organizations/projects, media assets, mixes, jobs, attempts, stage runs, artifacts, batches, events, notifications, push subscriptions, deliveries, and transactional outbox rows.
- **Object storage port:** immutable content-addressed source and derived keys, checksums, quarantine namespace, lifecycle cleanup, and separate local-filesystem/S3-compatible adapters. Clients never provide server paths.
- **Workers:** thin Celery entry points dispatch versioned, pure stages over explicit queues: `analysis-cpu`, `dsp-heavy`, `metadata-network`, and `exports`.
- **Redis:** broker and transient fan-out only. It is never the system of record and must not use an eviction policy that can drop queued work.

### Required foundational corrections

The first implementation slice repairs current boot and contract failures: stale model imports, mismatched settings names, invalid foreign keys, absent migration baseline, queue routing, storage volume paths, same-origin browser API defaults, and missing dependencies. It also establishes the selected ownership model before private media or Push subscriptions are exposed.

Secure ingest uses authenticated streaming multipart upload, server-derived quotas, chunk and total limits, locked offsets, media/checksum validation, expiry cleanup, and atomic object finalization. A database transaction records the completed asset before it becomes usable.

Durable jobs use an outbox written in the same transaction as a queued command, an atomic queued-to-running claim, idempotency keys for stage/version/parameters, `acks_late`, worker-loss recovery, cooperative cancellation, retry policy, deterministic artifact keys, and DB-first event persistence. Workers may publish fast notifications only after the authoritative commit.

### Migrated capabilities

The local project supplies pure, testable domain behavior: restoration, genre-aware mastering, tag/key/BPM analysis, naming suggestions, waveform generation, and batch aggregation. They move as versioned stages behind ports/adapters. Real mastering replaces the current placeholder endpoint; it produces immutable audio and a report artifact asynchronously. Physical rename behavior remains confined to a trusted local-filesystem adapter; canonical object keys remain immutable.

## 7. PWA, notification, and privacy design

The application is installable only from HTTPS in production. The manifest has a stable ID, SVG plus validated PNG/maskable icons, Apple touch asset, screenshots, and optional safe shortcuts. Install UX detects installed mode, supports Chromium prompt lifecycle, and provides manual iOS/Safari guidance without repeatedly offering an unavailable prompt.

The service worker uses a versioned generated precache for hashed application assets. Navigation is network-first with an app-shell/offline fallback; APIs, SSE, uploads, streams, downloads, subscriptions, and preferences are network-only. Runtime image/font caching is bounded and deliberate. Updates remain coherent until a user accepts an update-ready action; only then does the page request activation and reload on `controllerchange`.

Before Web Push, the product ships a durable notification center. `job_events` provides ordered sequence IDs and replay; `notifications` holds read/dismissed history; `push_subscriptions` encrypts device subscription material at rest; and `notification_deliveries` provides deduplicated, bounded retry state. Foreground events update an accessible `aria-live` status and the center without duplicating an operating-system notification.

Permission is requested only after the user selects “Notify me when jobs finish.” OS payloads contain no filename, error stack, URL token, or device material—only a version, notification ID, and safe deep link. Click handling validates the route, focuses an existing client where possible, and falls back to `/notifications` for missing or unauthorized targets. Unsubscribe, logout, account deletion, 404/410 deactivation, retention, and quiet preferences are explicit.

## 8. Accessibility and safety contract

- Every operation has a semantic button, label, focus order, visible focus indicator, and keyboard equivalent.
- Progress exposes `role=progressbar`, value semantics, stage text, and a polite live update cadence.
- Dialogs trap and restore focus, close with Escape, declare `role=dialog`/`aria-modal`, and make the background inert.
- Waveform seeking uses a keyboard-operable range/timeline with text equivalents. Canvas and 3D views have meaningful text alternatives.
- Content does not depend on hover, mouse dragging, color, sound, or motion alone.
- Toasts use a suitable live region; errors stay visible until dismissed or resolved.
- The visualizer and MIDI remain optional enhancements, respect reduced motion, and never claim physical hardware success without an observed result.

## 9. Delivery sequence

This is one program with reviewable, independently releasable slices; feature surfaces are not built over a knowingly non-bootable control plane.

1. **Canonical core:** bootable API, migrations, settings, ownership, storage, queues, readiness, DTO alignment, and baseline security tests.
2. **Secure ingest and durable jobs:** upload lifecycle, outbox, attempts/stages/artifacts, DB-backed SSE, cancellation/retry, and job API tests.
3. **Process and Jobs experience:** selected visual direction/tokens, real router and responsive shell, Process flow, Jobs detail, explicit states, and accessibility primitives.
4. **Real DSP and Library:** port pure restoration/mastering/tagging/waveform capabilities; immutable result artifacts; A/B player, downloads, library detail, and contract tests.
5. **Batch operations:** persisted aggregate/child jobs, bounded concurrency, partial-failure recovery, and mobile review UX.
6. **PWA and notification center:** TLS deployment contract, precache/update behavior, durable center, preferences, Push, deep links, and real device/browser test matrix.
7. **Deferred integrations and enhancement:** hardened cover enrichment, AzuraCast/broadcast, Rig/MIDI polish, performance, observability, and final release audit.

## 10. Definition of done and verification

The redesign is not complete because a static screen exists. Each delivery slice must demonstrate the relevant contract with automated tests and manual evidence.

- API boot, migration, authentication/ownership, upload bounds, queue routing, storage sharing, job claim/retry/cancel, and worker-loss behavior are integration tested.
- Client API tests prove actual DTO parsing; E2E tests cover Process→Jobs→Library with loading, network failure, retry, history hydration, and an explicit demo-free empty state.
- Keyboard, focus, dialog, screen-reader/live-region, color contrast, zoom, touch target, 390 px reflow, and reduced-motion tests cover primary flows.
- PWA tests validate manifest/icon assets, HTTPS service-worker registration, first-load offline behavior, no API cache poisoning, coherent update activation, and real browser/device install coverage.
- Notification tests prove event replay without gaps/duplicates, center persistence and cross-tab state, deliberate permission timing, Push retry/deactivation, deep-link authorization, and payload privacy.
- Performance and observability track stage latency, failures, outbox lag, queue depth, upload rejection, SSE reconnect/replay, service-worker version, and notification delivery outcomes without storing sensitive audio metadata in telemetry.

## 11. Risks and decisions needing implementation-time confirmation

- Select and document the ownership model before exposing a public deployment.
- Select an S3-compatible object-storage provider or validate mounted storage only for a private appliance; both must meet the immutable-artifact contract.
- Preserve existing DSP test fixtures while validating production dependencies and CPU/memory limits with real audio samples.
- Push and install acceptance requires HTTPS plus physical/browser-engine verification; viewport emulation does not prove Safari/iOS capability.
- The selected visual direction is intentionally expressive. Contrast, typography scale, texture opacity, and motion must be checked against real controls and content before release.

