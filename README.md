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

## 📱 PWA and HTTPS requirement

Production installation, Service Workers, and Push require a valid HTTPS
origin. The Compose stack uses Caddy as the only public ingress: it obtains
and renews TLS certificates, redirects clear-text HTTP for ACME/HTTPS upgrade,
and serves both the app and the same-origin `/api` route from the canonical
`PUBLIC_ORIGIN`. The app is **not** release-installable from a plain HTTP LAN
address.

The manifest already provides stable identity, PNG and maskable app icons,
Apple touch artwork, a Process screenshot, and safe Process/Jobs shortcuts.
The generated service-worker/update lifecycle is delivered separately; do not
take the presence of a manifest alone as evidence that an HTTP deployment is
installable.

---

## 🌓 Light & Dark Industrial Theme Tokens

Designed in accordance with the **SYSTEM CORRUPT Brand Book**:

- **Dark Mode (Default)**: Deep obsidian plate (`#0d0e12`), charcoal cards (`#15171e`), Rust Orange accents (`#ea580c`), Oxidized Copper indicators (`#0f766e`).
- **Light Mode**: Weathered concrete slate (`#f3f4f6`), high-contrast industrial cards (`#ffffff`), burnt ochre highlights (`#c2410c`).

---

## 🧪 Comprehensive E2E Testing with Playwright

End-to-end tests simulate realistic **30-minute long-format DJ sets** (`1800.0s`) across multiple device viewports:

```bash
cd web

# Install test dependencies & Playwright browsers
npm install
npx playwright install --with-deps

# Run full test suite
npm run test:e2e

# Interactive UI runner
npm run test:e2e:ui
```

### Supported Viewports:
- **Desktop**: Chromium, Firefox, WebKit (1440 × 900)
- **Tablet**: Apple iPad Gen 7 (768 × 1024)
- **Mobile**: Apple iPhone 14 (390 × 844)

---

## 🚀 Docker Compose Quickstart

```bash
# Clone and configure the production origin
git clone https://github.com/murphieslaw23/mix-analyst.git
cd mix-analyst

cp .env.example .env
# Set PUBLIC_ORIGIN to a DNS hostname that points here, and set a unique
# 32+ character AUTH_JWT_SECRET. Allow inbound TCP 80 and 443 for Caddy.
docker compose up --build -d
```

- **App and API**: `https://${PUBLIC_ORIGIN}` and
  `https://${PUBLIC_ORIGIN}/api/v1/docs`
- **Public ingress**: Caddy only (ports 80 and 443; port 80 is redirect/ACME,
  never a release application origin)
- **Private services**: API, PostgreSQL, Redis, workers, and the web runtime
  stay on the Compose network

### Local development (not an install acceptance path)

Use the explicit development overlay to bind the API to loopback, then let
Vite proxy browser `/api` calls. This HTTP workflow is for iteration only; use
the HTTPS deployment above for install, Service Worker, and Push testing.

```bash
# terminal 1
docker compose -f docker-compose.yml -f docker-compose.dev.yml up api postgres redis

# terminal 2
VITE_API_PROXY_TARGET=http://localhost:8000 pnpm --dir web dev
```

## Operations

- `GET /api/v1/health/live` proves the API process can respond. It deliberately
  does not depend on PostgreSQL, Redis, or storage so an orchestrator can
  restart a stuck process without amplifying a dependency outage.
- `GET /api/v1/health/ready` returns `503` unless PostgreSQL accepts a query,
  Redis answers `PING`, and the mounted storage is writable with at least
  `MIN_STORAGE_FREE_BYTES` available (5 GiB by default). Docker Compose uses
  this readiness probe for the API service.
- `GET /api/v1/metrics` is Prometheus text and requires a valid bearer token
  whose subject appears in the server-side comma-separated `OPERATOR_USER_IDS`
  allowlist. Leaving that setting unset denies all metrics requests.
- Metrics are aggregate-only. Their only labels are fixed `job_type`, `status`,
  `stage`, and `queue` values; filenames, media metadata, project IDs, tokens,
  storage keys, and request-provided label values are rejected by the metrics
  boundary. API and worker counters are atomically aggregated in a fixed Redis
  hash so an operator scrape sees all processes. If that shared backend is
  unavailable, `mix_analyst_counter_backend_available 0` marks the scrape as
  incomplete rather than presenting a process-local total as fleet-wide.

The Compose worker is limited to one Celery process (`WORKER_CONCURRENCY=1`),
2 CPUs, and 6 GiB memory because DSP work is CPU/memory intensive. Scale worker
containers for throughput rather than raising concurrency in one constrained
process. Upload admission remains bounded to `MAX_UPLOAD_SIZE_BYTES` (4 GiB by
default) and 8 MiB chunks. Host-run tests mock dependency failures; they do not
prove the Compose PostgreSQL/Redis/storage readiness path, which should be
checked with `docker compose up` in a deployment-capable environment.
