# Task 6 — immutable worker mastering stage

## Algorithms and reference source

The worker now owns a small deterministic mastering stage derived from the
existing local two-pass loudness behavior in
`/opt/freetekno-deploy/backend/mastering.py` and its loudness backend. It uses
`pyloudnorm` for integrated LUFS, applies one deterministic gain correction,
then limits using a 4x oversampled (`scipy.signal.resample_poly`) true-peak
estimate. The worker writes PCM-24 WAV output and reports the measured final
LUFS/true-peak values under algorithm version `v1`.

## Storage and key semantics

The worker accepts only a source key already stored on the owned media asset.
It requires `projects/{project_id}/...`, resolves that key through the trusted
storage service, and never receives a path from an API request. The result is
written to a worker-only staging file, hashed, and hard-linked once at
`projects/{project_id}/artifacts/mastered/v1/{sha256}`. Existing objects are
never overwritten; identical retry bytes reuse the existing immutable object.
The result report is the terminal `stage_runs.stage_output` JSON for
`master_mix`, containing the opaque artifact key, measurements, and algorithm
version. This deliberately does not introduce Task 7's generalized artifact
domain.

## API and job behavior

`POST /api/v1/mixes/{mix_id}/master` is now mounted as an authenticated,
owner-scoped command endpoint. It returns `202 QUEUED`, persists the mastering
settings on the generic durable job, and records an outbox command for
`tasks.run_master_mix` on `dsp-heavy`. It does not expose fixed measurements,
absolute paths, or a completed report. The worker performs the normal scoped
claim/event lifecycle, checks cancellation before and after DSP, persists the
stage report before terminal completion, and only then marks the job succeeded.

## Verification

Commands run:

- `PYTHONPATH=. .venv/bin/pytest tests/integration/test_authorization_scope.py tests/unit/test_master_mix_stage.py tests/integration/test_job_lifecycle.py tests/integration/test_app_boot.py -q` — 25 passed.
- `git diff --check` — passed.

The initial red run of the new stage/lifecycle tests failed as expected because
the stage module and dedicated mastering dispatch task did not exist. The
worker dependency was then installed in the local test venv after being added
to `worker/requirements.txt`.

## Commit and concerns

Commit: `feat: run mastering as immutable worker artifact stage`.

`pyloudnorm` is intentionally worker-only: the API has no DSP import and stays
light. The local virtualenv emitted existing Pydantic v2 deprecation warnings
during tests. A direct Alembic command using the default Docker PostgreSQL URL
cannot connect outside Compose; the SQLite migration/boot test passed.
