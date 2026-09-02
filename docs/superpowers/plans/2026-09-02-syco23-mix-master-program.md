# SYCO23 Mix Master Redesign Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a secure, responsive SYCO23 Mix Master that reliably processes owned audio into durable results, supports installation and intentional notifications, and follows the approved Press Plate Intake direction.

**Architecture:** Work is split into three contracts that can be reviewed independently: the canonical control plane and durable job system; the React product experience; and PWA/notification delivery. The React application consumes only documented API DTOs. PostgreSQL is the authority for jobs/events/notifications, object storage holds immutable audio artifacts, workers execute versioned DSP stages, and Redis is ephemeral transport only.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, PostgreSQL, Celery, Redis, S3-compatible storage adapter, React 18, TypeScript, Vite, React Router, Tailwind/CSS variables, Playwright, Workbox-compatible Vite PWA build, Web Push/VAPID.

**Spec:** `docs/superpowers/specs/2026-09-02-syco23-mix-master-redesign-design.md`

## Global Constraints

- Use a production-capable authenticated multi-user ownership model; a private appliance is a deployment profile, not an authorization bypass.
- Use same-origin `/api/v1` as the browser default; do not compile a remote browser to `localhost`.
- Keep source and derived object keys immutable and content-addressed; never accept client-supplied server paths.
- Do not show fake mix data, simulated playback success, or fake backend/readiness success in a production flow.
- Keep all primary controls keyboard-operable, at least 44 × 44 CSS px, contrast-safe, and compatible with reduced motion.
- Preserve the Press Plate Intake system: oil/iron/bone surfaces, rust-orange Process accent, physical vertical hierarchy, one primary action, no neon or terminal/dashboard aesthetic.
- Cache only versioned static assets and navigation fallback; `/api/**`, SSE, uploads, streams, downloads, subscriptions, and preferences are network-only.
- Request notifications only after an explicit user gesture; Push payloads expose notification IDs and safe routes, never private media metadata.

---

## Program order

1. [Canonical core and durable jobs](2026-09-02-syco23-mix-master-core-jobs-plan.md) establishes bootability, ownership, secure ingest, durable jobs/events, and real worker dispatch. It is the release gate for all later feature work.
2. [Product UI and processing flows](2026-09-02-syco23-mix-master-product-ui-plan.md) builds the Press Plate UI system, routes, Process, Jobs, Library, accessible media behavior, and real DTO adapters against the core contract.
3. [PWA and notification delivery](2026-09-02-syco23-mix-master-pwa-notifications-plan.md) adds HTTPS deployment expectations, safe updates/offline shell, durable notification center, opt-in Web Push, and device/browser acceptance tests.

No implementation task may skip a predecessor plan's acceptance suite. The optional 3D Rig, MIDI, broadcast, stems, and external cover work remain outside the primary processing critical path until the preceding contract is green.

## Program-level release evidence

- A new authenticated user can upload a valid bounded file, start a persisted job, reconnect during work, recover from a worker failure, and obtain one immutable result artifact.
- The Process → Jobs → Library journey works at 390 px, with keyboard and assistive technology, without fake data or hidden errors.
- An HTTPS deployment installs, behaves coherently after a release update, never serves API responses from cache, and provides a privacy-safe notification journey after explicit opt-in.
- Unit, API/integration, browser E2E, accessibility, PWA, and physical-browser/device evidence correspond to the requirement being claimed.
