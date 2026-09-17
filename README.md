# SYSTEM CORRUPT | MIX ANALYST 🔊

![PWA Ready](https://img.shields.io/badge/PWA-Installable-ea580c.svg)
![CI Status](https://img.shields.io/badge/CI-Passing-10b981.svg)
![DSP Engine](https://img.shields.io/badge/Audio-EBU_R128_%2B_Demucs-0f766e.svg)

> **Continuous DJ Mix Intelligence, Transition & Cue Engine with Stem Separation & Broadcast Synchronization** for underground sound-system culture (freetekno, hardtek, acidcore, jungle).

---

## 🏛️ System Architecture

```
                                  ┌────────────────────────┐
                                  │   Continuous DJ Mix    │
                                  │ (WAV / FLAC / MP3 4h)  │
                                  └───────────┬────────────┘
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
         ┌─────────────────────────┐                     ┌─────────────────────────┐
         │   FastAPI Core Engine   │                     │  Demucs 4-Stem Worker   │
         │ (EBU R128 LUFS / Peak)  │                     │ (Drums, Bass, Vocal)    │
         └────────────┬────────────┘                     └────────────┬────────────┘
                      │                                               │
                      ├───────────────────────┬───────────────────────┘
                      ▼                       ▼
         ┌─────────────────────────┐  ┌─────────────────────────┐
         │  Harmonic Transitions   │  │   AzuraCast Web Radio   │
         │ (Camelot Key & Cues)    │  │ (Live Metadata Sync)   │
         └────────────┬────────────┘  └─────────────────────────┘
                      │
                      ▼
         ┌─────────────────────────┐
         │  Progressive Web App    │
         │ (Mobile, Tablet, Web)   │
         └─────────────────────────┘
```

---

## 📱 Full PWA Installation

The web interface is fully installable as a standalone Progressive Web Application across all devices:

- **Desktop (Chrome / Edge / Safari macOS)**: Click the **Install App** button in the top navigation or use browser address bar install prompt.
- **Mobile (iOS Safari)**: Tap `Share` → `Add to Home Screen`.
- **Mobile (Android Chrome)**: Tap `Install App` banner or `Add to Home screen`.

---

## 🌓 Light & Dark Industrial Theme Tokens

Designed in accordance with the **SYSTEM CORRUPT Brand Book**:

- **Dark Mode (Default)**: Deep obsidian plate (`#0d0e12`), charcoal cards (`#15171e`), Rust Orange accents (`#ea580c`), Oxidized Copper indicators (`#0f766e`).
- **Light Mode**: Weathered concrete slate (`#f3f4f6`), high-contrast industrial cards (`#ffffff`), burnt ochre highlights (`#c2410c`).

---

## 🧭 App Routes

Deep-linkable destinations (mobile bottom nav, desktop rail):

- `/` — Mix library & waveform detail (zoomable engine-region timeline)
- `/process` — Upload journey with resumable sessions
- `/pipeline` — Pipeline & broadcast operations
- `/jobs`, `/jobs/:jobId` — Durable job progress, cancel/retry, recovery
- `/batches`, `/batches/:batchId` — Batch review with partial-failure recovery
- `/more/notifications` — Notification center + opt-in Web Push settings

---

## 🧪 Comprehensive E2E Testing with Playwright

End-to-end tests simulate realistic **30-minute long-format DJ sets** (`1800.0s`) across multiple device viewports:

```bash
cd web

# Install dependencies & Playwright browsers (pnpm)
pnpm install
pnpm exec playwright install --with-deps chromium

# Run full test suite (dev server)
pnpm run test:e2e

# Production PWA lifecycle (versioned precache, offline shell, updates)
pnpm run test:pwa

# Interactive UI runner
pnpm run test:e2e:ui
```

### Supported Viewports:
- **Desktop**: Chromium, Firefox, WebKit (1440 × 900)
- **Tablet**: Apple iPad Gen 7 (768 × 1024)
- **Mobile**: Apple iPhone 14 (390 × 844)

---

## 🚀 Docker Compose Quickstart

```bash
# Clone and spin up full multi-stage stack
git clone https://github.com/murphieslaw23/mix-analyst.git
cd mix-analyst

cp .env.example .env
docker compose up --build -d
```

- **Frontend PWA**: `http://localhost`
- **FastAPI Backend**: `http://localhost:8000/docs`
- **PostgreSQL**: `localhost:5432`
- **Redis Queue**: `localhost:6379`

---

## 🔧 Pipeline Operations (PWA "Pipeline & Broadcast" Tab)

- **Ingestion**: chunked upload with ffprobe validation and optional client SHA-256 check; chunks bounded per request, offsets authoritative; stale unfinished sessions auto-purge after `UPLOAD_EXPIRY_HOURS`.
- **Jobs**: dispatch analysis, watch live SSE progress (durable replay with `Last-Event-ID`), cancel/retry. Dispatch is outbox-backed: a down broker leaves jobs `QUEUED` and retryable, never lost. Queues: `analysis`, `mastering`, `stems`, `exports`.
- **Batches**: `POST /batches` processes owned mixes with bounded parallelism and `PARTIAL_FAILED` aggregation; only failed items retry.
- **DSP**: two-pass loudness mastering (preset targets, downloadable master WAV, immutable artifact records), Demucs 4-stem separation **(optional worker extra: `torch` + `demucs`, excluded by default)**, kick/sub sidechain ducking (requires completed stems), 1080p FFmpeg broadcast render, AzuraCast sync. Pure versioned stages live in `worker/dsp/` + `worker/stages/`.
- **Auth & ownership**: Bearer JWT project ownership with DB membership checks; open appliance mode serves the default project. Reads are open; uploads, dispatches, triggers, sync and mix edits require `X-API-Key` when `API_KEYS` is set (empty = open single-user mode). `AUTH_ENFORCED=true` requires a token for every request.
- **Notifications**: terminal job outcomes land in a durable center (`GET /notifications`); opt-in Web Push carries only notification id + safe deep link, with bounded retry and 410 deactivation. Schema is migration-managed (`api/alembic/versions/`); the API upgrades to head on startup.
