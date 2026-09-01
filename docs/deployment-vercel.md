# Vercel Deployment Architecture & Production Plan

**Project:** SYSTEM CORRUPT | MIX ANALYST (`mix-analyzer`)  
**Vercel Team:** SYCO23 (`system-corrupt`, `team_NgD523QOHDHfux9i6bXTZTUr`)  
**Project ID:** `prj_7eKfQ52YGBd2YC6zwgXcgwMBxYb1`  
**Framework:** Vite (React + TypeScript + Tailwind CSS)  
**Production URL:** `https://mix-analyzer-system-corrupt.vercel.app`  
**Git Link:** `murphieslaw23/mix-analyst` on branch `main` (Automatic CI/CD)

---

## 🏛️ Topology & Separation of Concerns

```
                               ┌───────────────────────────────────────────────────────────┐
                               │                    Vercel Edge Network                    │
                               │  https://mix-analyzer-system-corrupt.vercel.app           │
                               └─────────────────────────────┬─────────────────────────────┘
                                                             │
                                   ┌─────────────────────────┴─────────────────────────┐
                                   ▼                                                   ▼
                    ┌─────────────────────────────┐                     ┌─────────────────────────────┐
                    │      Static PWA Assets      │                     │   Interactive DSP UI        │
                    │ • Wasm & 3D Canvas Canvas   │                     │ • Waveform Player           │
                    │ • Web MIDI Hardware Engine  │                     │ • 3D Speaker Stack Rig      │
                    │ • Service Worker Offline    │                     │ • Realtime MIDI CC Monitor  │
                    └─────────────────────────────┘                     └──────────────┬──────────────┘
                                                                                       │
                                                                                       │ REST / SSE
                                                                                       ▼
                                                                        ┌─────────────────────────────┐
                                                                        │  FastAPI + Celery Backend   │
                                                                        │ (Docker / VPS / Dedicated)  │
                                                                        │ • Demucs 4-Stem Separation  │
                                                                        │ • EBU R128 Loudness Engine  │
                                                                        │ • FFmpeg 1080p Compositor   │
                                                                        │ • AzuraCast Webhook Sync    │
                                                                        └─────────────────────────────┘
```

---

## ⚙️ Vercel Project Configuration

| Parameter | Setting | Notes |
| :--- | :--- | :--- |
| **Framework Preset** | `Vite` | Auto-configured output directory `dist` |
| **Root Directory** | `web` | Contains `package.json`, `vite.config.ts`, `src/` |
| **Build Command** | `npm run build` (`tsc && vite build`) | Typechecked and minified asset compilation |
| **Output Directory** | `dist` | Edge-optimized static files |
| **Node.js Version** | `20.x` / `24.x` | Modern ESM & TypeScript support |

---

## 🔐 Environment Variables

| Variable | Target | Description | Example Value |
| :--- | :--- | :--- | :--- |
| `VITE_API_BASE_URL` | Production & Preview | URL of the standalone FastAPI gateway | `https://api.mix.syco23.org/api/v1` |

---

## 🚀 Deployment Workflow

1. **Continuous Deployment via GitHub:** Every commit pushed to `main` on `murphieslaw23/mix-analyst` triggers an automatic build on Vercel.
2. **Preview Deployments:** Pull requests receive unique preview deployment URLs for testing visualizer changes and MIDI bindings.
3. **PWA & SPA Routing:** `web/vercel.json` provides rewrite rules ensuring client-side routes fallback to `index.html` while serving Service Worker and webmanifest headers correctly.
