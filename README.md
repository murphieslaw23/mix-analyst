# SYSTEM CORRUPT | MIX ANALYST 🎚️

**Underground Mix Analysis, Cue Detection, Transition Mapping & Mastering Engine**

Built for continuous Freetekno, Hardtek, Tribe, Jungle, and electronic sound-system sets.

---

## Architecture Overview

```
                          ┌────────────────────────┐
                          │   FastAPI Gateway      │
                          │   /api/v1 (REST / SSE) │
                          └───────────┬────────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            │                         │                         │
  ┌─────────▼──────────┐    ┌─────────▼──────────┐    ┌─────────▼──────────┐
  │ Ingestion & Upload │    │  Export & CUE Gen  │    │ Two-Pass Mastering │
  │ (Chunked / ffprobe)│    │ (CUE/Rekordbox/NML)│    │ (LUFS/EQ/Limiter)  │
  └─────────┬──────────┘    └────────────────────┘    └────────────────────┘
            │
  ┌─────────▼──────────┐
  │ PostgreSQL / Redis │
  └─────────┬──────────┘
            │
  ┌─────────▼──────────────────────────────────────────────────┐
  │ Celery Worker Engine (Bounded-Memory Analysis)              │
  │ • Windowed BPM Detection & Tempo Variance                  │
  │ • Chroma / Camelot Harmonic Key Analysis                   │
  │ • Segment Partitioning & Acoustic Fingerprinting           │
  │ • Energy Delta & Transition / Cue Point Detection          │
  │ • Two-Pass EBU R128 Mastering & Report Engine               │
  └────────────────────────────────────────────────────────────┘
```

---

## Features & Implemented Phases

- **Phase 1: Ingestion & Storage:** Streamed chunked uploads, ffprobe technical validation, persistent Media models.
- **Phase 2: Job Platform:** Asynchronous Celery tasks, persistent `StageRun` tracking, and real-time Server-Sent Events (SSE).
- **Phase 3: Bounded Audio Analysis:** Windowed analysis maintaining bounded RAM for multi-hour recordings, BPM detection, and EBU R128 loudness.
- **Phase 4: Track Identification:** Segment partitioning and AcoustID fingerprinting.
- **Phase 5: Transition Detection:** Energy delta tracking, Camelot wheel harmonic compatibility classification, and cue point generation.
- **Phase 6: DJ Exports & Dashboard:** Standard CDRWIN `.cue` sheets (75 fps), Pioneer Rekordbox `DJ_PLAYLISTS` XML, Traktor NML, YouTube timestamps, synthetic test fixtures, and interactive Waveform canvas player.
- **Phase 7: Two-Pass Mastering:** Pass-1 input measurement, 5-band parametric EQ, dynamic compression, true-peak limiting, Pass-2 output verification, and before/after mastering reports.

---

## API Endpoints

### Uploads & Mixes
- `POST /api/v1/uploads/chunk` — Streamed chunk upload session.
- `GET /api/v1/mixes` — List analyzed mixes.
- `GET /api/v1/mixes/{id}` — Full mix metadata, detected tracks, and transitions.

### DJ Exports
- `GET /api/v1/mixes/{id}/export/cue` — Standard CDRWIN `.cue` file.
- `GET /api/v1/mixes/{id}/export/rekordbox` — Pioneer Rekordbox XML with memory and hot cues.
- `GET /api/v1/mixes/{id}/export/traktor` — Native Instruments Traktor NML collection file.
- `GET /api/v1/mixes/{id}/export/youtube` — Formatted YouTube timestamps with BPM and Camelot keys.

### Mastering & Reports
- `POST /api/v1/mixes/{id}/master` — Trigger two-pass mastering pipeline.
- `GET /api/v1/mixes/{id}/mastering-report` — Retrieve mastering measurements and before/after comparison.
- `GET /api/v1/mastering/presets` — List built-in mastering presets.

---

## Running Tests & Benchmarks

```bash
# Run full unit and integration test suite
pytest

# Run throughput and latency benchmarks
python -m tests.benchmarks.benchmark_pipeline
```
