# SYCO23 Mix Master Core and Durable Jobs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the canonical API bootable and secure, then create owned media, durable jobs, ordered events, and worker execution that survive restarts and retries.

**Architecture:** FastAPI owns validation and commands; SQLAlchemy models plus Alembic migrations own durable state; a transactional outbox bridges database commits to Celery; workers atomically claim jobs and publish persisted events. This plan introduces a small ownership model, storage abstraction, and job service boundary so API routers do not directly implement distributed-systems policy.

**Tech Stack:** Python 3, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL 16, Celery 5, Redis 7, pytest.

**Spec:** `docs/superpowers/specs/2026-09-02-syco23-mix-master-redesign-design.md`

## Global Constraints

- Use the authenticated multi-user model and scope every media, job, event, and notification command/read to an owner/project.
- `Settings` uses lowercase Python attributes and explicit environment aliases for Compose variables.
- Queueing occurs only through committed outbox records; a broker failure must not lose a queued job.
- A worker claims a queued attempt atomically, checks cancellation at stage boundaries, and never overwrites a terminal cancellation.
- Storage keys derive from owner scope, SHA-256, artifact role, and version; no endpoint accepts absolute paths.

---

### Task 1: Restore application boot and migration authority

**Files:**
- Modify: `api/app/main.py`, `api/app/config.py`, `api/app/models/__init__.py`, `api/app/models/media.py`, `api/app/models/mastering.py`, `api/app/models/stems.py`, `api/app/models/broadcast.py`, `api/Dockerfile`, `docker-compose.yml`
- Create: `api/alembic.ini`, `api/alembic/env.py`, `api/alembic/script.py.mako`, `api/alembic/versions/20260902_01_baseline.py`, `tests/integration/test_app_boot.py`

**Interfaces:**
- Produces `settings.app_name`, `settings.api_v1_prefix`, `settings.allowed_origins`, and `settings.storage_root` with environment aliases.
- Produces a migration command: `alembic -c api/alembic.ini upgrade head`.

- [ ] **Step 1: Write failing import and settings tests**

```python
def test_app_uses_declared_settings_contract():
    from api.app.main import app

    assert app.title == "Mix Analyst"
    assert app.openapi_url == "/api/v1/openapi.json"


def test_compose_storage_alias_is_applied(monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", "/storage")
    from api.app.config import Settings

    assert Settings().storage_root == "/storage"
```

- [ ] **Step 2: Run the focused tests to establish the broken baseline**

Run: `pytest tests/integration/test_app_boot.py -q`

Expected: import/settings failure caused by uppercase settings and stale model references.

- [ ] **Step 3: Align model imports, foreign-key table names, and settings**

```python
app = FastAPI(
    title=settings.app_name, openapi_url=f"{settings.api_v1_prefix}/openapi.json"
)
app.include_router(health.router, prefix=settings.api_v1_prefix, tags=["health"])


class Settings(BaseSettings):
    storage_root: str = Field("/data/storage", validation_alias="STORAGE_DIR")
```

Remove routers whose imports remain placeholders from `main.py` until their real worker contracts exist. Make media-related foreign keys reference the actual `media_assets` table. Export the single current model family from `api.app.models`.

- [ ] **Step 4: Add an Alembic baseline that creates the live model metadata**

```python
def upgrade() -> None:
    op.create_table("media_assets", ...)
    op.create_table("mixes", ...)
    op.create_table("jobs", ...)


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_table("mixes")
    op.drop_table("media_assets")
```

Keep each actual table and FK represented; do not call `Base.metadata.create_all()` at runtime.

- [ ] **Step 5: Verify boot and migration structure**

Run: `pytest tests/integration/test_app_boot.py -q && python -m compileall api/app && alembic -c api/alembic.ini heads`

Expected: all commands pass and exactly one Alembic head is reported.

- [ ] **Step 6: Commit the bootable baseline**

```bash
git add api docker-compose.yml tests/integration/test_app_boot.py
git commit -m "fix: establish bootable API and migration baseline"
```

### Task 2: Add authenticated ownership and scoped read access

**Files:**
- Create: `api/app/models/identity.py`, `api/app/services/auth.py`, `api/app/api/deps.py`, `api/app/schemas/auth.py`, `tests/integration/test_authorization_scope.py`
- Modify: `api/app/models/__init__.py`, `api/app/models/media.py`, `api/app/models/job.py`, `api/app/main.py`, `api/app/api/v1/mixes.py`, `api/app/api/v1/jobs.py`, `api/requirements.txt`, `api/alembic/versions/20260902_02_identity_scope.py`

**Interfaces:**
- Consumes `Authorization: Bearer <JWT>`.
- Produces `CurrentPrincipal(user_id: str, project_id: str)` via `get_current_principal`.
- Produces `require_owned_mix(db, principal, mix_id) -> Mix` and `require_owned_job(db, principal, job_id) -> Job`.

- [ ] **Step 1: Write ownership isolation tests**

```python
def test_user_cannot_read_another_users_mix(client, user_a_token, user_b_mix):
    response = client.get(
        f"/api/v1/mixes/{user_b_mix.id}",
        headers={"Authorization": f"Bearer {user_a_token}"},
    )
    assert response.status_code == 404


def test_unauthenticated_job_event_stream_is_rejected(client, job):
    assert client.get(f"/api/v1/jobs/{job.id}/events").status_code == 401
```

- [ ] **Step 2: Run tests and confirm the existing global-access failure**

Run: `pytest tests/integration/test_authorization_scope.py -q`

Expected: failure because current routers do not require a principal.

- [ ] **Step 3: Implement the identity schema and dependencies**

```python
class CurrentPrincipal(BaseModel):
    user_id: str
    project_id: str


def require_owned_job(db: Session, principal: CurrentPrincipal, job_id: str) -> Job:
    return (
        db.scalar(
            select(Job).where(Job.id == job_id, Job.project_id == principal.project_id)
        )
        or raise_not_found()
    )
```

Add `users`, `projects`, and `project_id`/`owner_id` columns through migration. Ensure every mix/job query applies project scope before returning data or opening SSE.

- [ ] **Step 4: Verify isolation behavior**

Run: `pytest tests/integration/test_authorization_scope.py -q`

Expected: unauthenticated reads return 401; cross-project reads return 404; owned reads pass.

- [ ] **Step 5: Commit the scoped ownership contract**

```bash
git add api tests/integration/test_authorization_scope.py
git commit -m "feat: scope media and jobs to authenticated projects"
```

### Task 3: Replace raw upload paths with bounded owned storage

**Files:**
- Modify: `api/app/api/v1/uploads.py`, `api/app/services/storage.py`, `api/app/schemas/upload.py`, `api/app/config.py`, `docker-compose.yml`
- Create: `api/app/services/upload_sessions.py`, `tests/integration/test_upload_lifecycle.py`, `api/alembic/versions/20260902_03_upload_sessions.py`

**Interfaces:**
- Produces `create_upload_session(principal, filename, byte_length, content_type) -> UploadSessionOut`.
- Produces `append_chunk(session_id, offset, chunk: BinaryIO) -> next_offset` under a row lock.
- Produces `finalize_upload(session_id) -> MediaAsset` after checksum and probe validation.

- [ ] **Step 1: Write bounded-streaming and offset-conflict tests**

```python
def test_chunk_larger_than_configured_limit_is_rejected(client, token, upload_session):
    response = client.patch(
        upload_session.url,
        headers={"Authorization": f"Bearer {token}", "Upload-Offset": "0"},
        content=b"x" * (MAX_CHUNK + 1),
    )
    assert response.status_code == 413


def test_stale_offset_returns_conflict(client, token, upload_session):
    response = client.patch(
        upload_session.url,
        headers={"Authorization": f"Bearer {token}", "Upload-Offset": "0"},
        content=b"chunk",
    )
    assert response.status_code == 409
```

- [ ] **Step 2: Run the lifecycle tests to show current unbounded behavior**

Run: `pytest tests/integration/test_upload_lifecycle.py -q`

Expected: current implementation accepts chunks without a locked authoritative offset.

- [ ] **Step 3: Implement the upload-session transaction and storage port**

```python
def derived_object_key(project_id: str, sha256: str, role: str, version: str) -> str:
    return f"projects/{project_id}/artifacts/{role}/{version}/{sha256}"


with db.begin():
    session = db.scalar(
        select(UploadSession).where(UploadSession.id == session_id).with_for_update()
    )
    assert_offset(session, requested_offset)
    write_limited_chunk(session.quarantine_key, chunk, settings.max_chunk_size_bytes)
    session.offset += bytes_written
```

Keep quarantine and final keys separate; move/promote only after a successful database transaction and validated checksum/probe.

- [ ] **Step 4: Verify upload correctness and cleanup**

Run: `pytest tests/integration/test_upload_lifecycle.py -q`

Expected: size, offset, ownership, checksum, finalization, and expiration cases pass.

- [ ] **Step 5: Commit secure upload lifecycle**

```bash
git add api docker-compose.yml tests/integration/test_upload_lifecycle.py
git commit -m "feat: add bounded owned upload lifecycle"
```

### Task 4: Introduce outbox-backed durable job commands and attempts

**Files:**
- Modify: `api/app/models/job.py`, `api/app/api/v1/jobs.py`, `api/app/schemas/job.py`, `worker/celery_app.py`, `worker/tasks.py`, `worker/Dockerfile`, `docker-compose.yml`
- Create: `api/app/models/outbox.py`, `api/app/services/job_commands.py`, `worker/outbox_dispatcher.py`, `tests/integration/test_job_lifecycle.py`, `api/alembic/versions/20260902_04_outbox_attempts.py`

**Interfaces:**
- Produces `enqueue_job(db, principal, mix, request) -> Job` and one `OutboxMessage(kind="job.dispatch")` in the same transaction.
- Produces `claim_job_attempt(db, job_id, worker_name) -> JobAttempt | None`.
- Produces Celery task routes for `analysis-cpu`, `dsp-heavy`, `metadata-network`, and `exports`.

- [ ] **Step 1: Write outbox and worker-claim tests**

```python
def test_create_job_persists_outbox_before_broker_publish(db, principal, mix):
    job = enqueue_job(db, principal, mix, JobCreateRequest(job_type="ANALYSIS"))
    assert (
        db.scalar(
            select(OutboxMessage).where(OutboxMessage.aggregate_id == job.id)
        ).kind
        == "job.dispatch"
    )


def test_only_one_worker_claims_queued_attempt(db, job):
    assert claim_job_attempt(db, job.id, "worker-a") is not None
    assert claim_job_attempt(db, job.id, "worker-b") is None
```

- [ ] **Step 2: Run tests and confirm direct broker dispatch is not durable**

Run: `pytest tests/integration/test_job_lifecycle.py -q`

Expected: failure because the router commits a job before an independent direct broker call.

- [ ] **Step 3: Implement outbox publication and idempotent claim**

```python
update(Job).where(Job.id == job_id, Job.status == JobStatus.QUEUED).values(
    status=JobStatus.RUNNING,
    started_at=utcnow(),
).returning(Job.id)
```

Configure Celery with `task_acks_late=True`, `task_reject_on_worker_lost=True`, explicit task routes, and safe retry policy. The dispatcher marks an outbox row delivered only after broker acceptance; failures keep a retryable row.

- [ ] **Step 4: Verify job dispatch and claim behavior**

Run: `pytest tests/integration/test_job_lifecycle.py -q`

Expected: one outbox row, one worker claim, explicit queue names, and retryable undelivered outbox rows.

- [ ] **Step 5: Commit durable commands**

```bash
git add api worker docker-compose.yml tests/integration/test_job_lifecycle.py
git commit -m "feat: dispatch durable jobs through transactional outbox"
```

### Task 5: Persist ordered events, cooperative cancellation, and replayable SSE

**Files:**
- Modify: `api/app/api/v1/jobs.py`, `api/app/services/job_events.py`, `api/app/models/job.py`, `worker/tasks.py`
- Create: `api/app/models/job_event.py`, `api/app/services/job_events_store.py`, `tests/integration/test_job_events.py`, `api/alembic/versions/20260902_05_job_events.py`

**Interfaces:**
- Produces `record_job_event(db, job, event_type, payload) -> JobEvent` with monotonic per-job `sequence`.
- Consumes `Last-Event-ID` and emits SSE `id: <sequence>` before every event.
- Produces `request_cancellation(db, job) -> Job` without force-terminating a running process.

- [ ] **Step 1: Write event replay and cancellation-race tests**

```python
def test_sse_replays_terminal_event_committed_before_subscription(
    client, token, job_with_succeeded_event
):
    response = client.get(
        job_with_succeeded_event.events_url,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert "id: 3" in response.text and "SUCCEEDED" in response.text


def test_cancelled_job_cannot_be_overwritten_by_late_worker(db, cancelled_job):
    assert complete_job_attempt(db, cancelled_job.id, "worker-a") is False
```

- [ ] **Step 2: Run the event tests to establish Pub/Sub-only loss behavior**

Run: `pytest tests/integration/test_job_events.py -q`

Expected: failure because current SSE has no DB snapshot, ID, or replay path.

- [ ] **Step 3: Implement event storage and cooperative terminal transitions**

```python
def complete_job_attempt(db: Session, job_id: str, worker_name: str) -> bool:
    result = db.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == JobStatus.RUNNING)
        .values(status=JobStatus.SUCCEEDED)
    )
    return result.rowcount == 1
```

At every stage boundary workers load the authoritative job state and stop cleanly when it is `CANCELLED`. SSE replays rows after `Last-Event-ID`, then tails newly committed events; Redis fan-out is an optimization only.

- [ ] **Step 4: Verify replay, cancellation, and authorization**

Run: `pytest tests/integration/test_job_events.py -q`

Expected: no missed terminal event, no duplicate after reconnect, and no late terminal overwrite.

- [ ] **Step 5: Commit event durability**

```bash
git add api worker tests/integration/test_job_events.py
git commit -m "feat: persist job events and replay SSE progress"
```

### Task 6: Port real mastering as a versioned artifact stage

**Files:**
- Create: `worker/dsp/__init__.py`, `worker/dsp/restoration.py`, `worker/dsp/mastering.py`, `worker/dsp/tagging.py`, `worker/dsp/waveforms.py`, `worker/stages/master_mix.py`, `tests/unit/test_master_mix_stage.py`
- Modify: `worker/requirements.txt`, `api/requirements.txt`, `worker/tasks.py`, `api/app/api/v1/mastering.py`, `api/app/models/job.py`, `api/app/schemas/job.py`

**Interfaces:**
- Produces `run_master_mix(source_path: Path, settings: MasterSettings) -> MasterResult` with `artifact_key`, `integrated_lufs`, `true_peak_dbtp`, and `algorithm_version`.
- Consumes an owned source artifact and writes one immutable mastered artifact/report.

- [ ] **Step 1: Move a deterministic local DSP fixture into a failing worker-stage test**

```python
def test_master_stage_writes_immutable_result_artifact(tmp_path, synthetic_audio):
    result = run_master_mix(
        synthetic_audio, MasterSettings(target_lufs=-9.0, true_peak_dbtp=-1.0)
    )
    assert result.integrated_lufs <= -8.5
    assert result.artifact_key.startswith("projects/")
```

- [ ] **Step 2: Run the focused stage test**

Run: `pytest tests/unit/test_master_mix_stage.py -q`

Expected: failure because the current API only writes fixed completed measurements.

- [ ] **Step 3: Port pure DSP behavior behind the worker-stage interface**

```python
@dataclass(frozen=True)
class MasterResult:
    artifact_key: str
    integrated_lufs: float
    true_peak_dbtp: float
    algorithm_version: str
```

Move only pure algorithms and deterministic tests from the local project. Add the required loudness dependency to the worker image; remove the synchronous placeholder completion route and replace it with a durable `MASTERING` job command.

- [ ] **Step 4: Verify stage and API command tests**

Run: `pytest tests/unit/test_master_mix_stage.py tests/integration/test_job_lifecycle.py -q`

Expected: real stage report/artifact assertions pass and no endpoint reports a completed master before worker output exists.

- [ ] **Step 5: Commit real mastering stage**

```bash
git add api worker tests/unit/test_master_mix_stage.py
git commit -m "feat: run mastering as immutable worker artifact stage"
```

### Task 7: Add metadata, naming, and waveform artifact stages

**Files:**
- Create: `worker/stages/tag_mix.py`, `worker/stages/generate_waveform.py`, `api/app/models/artifact.py`, `api/app/schemas/artifact.py`, `tests/unit/test_tag_mix_stage.py`, `tests/unit/test_waveform_stage.py`
- Modify: `worker/dsp/tagging.py`, `worker/dsp/waveforms.py`, `worker/tasks.py`, `api/app/api/v1/mixes.py`, `api/app/schemas/mix.py`, `api/app/models/__init__.py`, `api/alembic/versions/20260902_08_artifacts.py`

**Interfaces:**
- Produces `Artifact(role, key, sha256, algorithm_version, media_type, byte_length)`.
- Produces `generate_waveform(source: Path, points: int, algorithm_version: str) -> WaveformArtifact`.
- Produces a normalized display/download-name suggestion without renaming immutable storage objects.

- [ ] **Step 1: Write deterministic artifact-stage tests**

```python
def test_waveform_key_is_stable_for_source_and_algorithm(synthetic_audio):
    first = generate_waveform(synthetic_audio, points=2048, algorithm_version="1")
    second = generate_waveform(synthetic_audio, points=2048, algorithm_version="1")
    assert first.sha256 == second.sha256
    assert first.key == second.key


def test_tagger_suggests_download_name_without_mutating_source_key(tagged_mix):
    assert tagged_mix.source_artifact.key != tagged_mix.suggested_download_name
```

- [ ] **Step 2: Run the focused artifact tests**

Run: `pytest tests/unit/test_tag_mix_stage.py tests/unit/test_waveform_stage.py -q`

Expected: failure because no artifact domain or versioned stage interface exists.

- [ ] **Step 3: Implement immutable artifact persistence and pure stages**

```python
def artifact_key(source_sha256: str, role: str, algorithm_version: str) -> str:
    return f"artifacts/{role}/{algorithm_version}/{source_sha256}"
```

Port BPM/key/genre/tagging and waveform algorithms from the local project behind the new pure interfaces. Persist report data and artifact references after a stage succeeds; expose safe signed URLs and a human-facing suggested download name separately.

- [ ] **Step 4: Verify stable artifacts and API presentation**

Run: `pytest tests/unit/test_tag_mix_stage.py tests/unit/test_waveform_stage.py tests/integration/test_job_lifecycle.py -q`

Expected: repeat execution reuses the same deterministic artifact identity and mix API exposes report/artifact metadata.

- [ ] **Step 5: Commit metadata and waveform stages**

```bash
git add api worker tests
git commit -m "feat: add metadata and waveform artifact stages"
```

### Task 8: Add persistent batch parent and item aggregation

**Files:**
- Create: `api/app/models/batch.py`, `api/app/schemas/batch.py`, `api/app/api/v1/batches.py`, `api/app/services/batches.py`, `tests/integration/test_batches.py`, `api/alembic/versions/20260902_09_batches.py`
- Modify: `api/app/main.py`, `api/app/models/__init__.py`, `api/app/api/v1/jobs.py`, `worker/tasks.py`

**Interfaces:**
- Produces `POST /batches` with owned `mix_ids`, one preset, and bounded `max_parallelism`.
- Produces `BatchOut { id, status, total_count, completed_count, failed_count, cancelled_count, items }`.
- Produces `recompute_batch_status(db, batch_id) -> Batch` derived solely from persistent child jobs.

- [ ] **Step 1: Write aggregate and partial-failure tests**

```python
def test_batch_reports_partial_failure_without_losing_successes(
    client, token, owned_mix_ids
):
    batch = client.post(
        "/api/v1/batches",
        headers={"Authorization": f"Bearer {token}"},
        json={"mix_ids": owned_mix_ids, "max_parallelism": 2},
    ).json()
    mark_child_states(batch, ["SUCCEEDED", "FAILED"])
    response = client.get(
        f"/api/v1/batches/{batch['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.json()["status"] == "PARTIAL_FAILED"
```

- [ ] **Step 2: Run the batch tests**

Run: `pytest tests/integration/test_batches.py -q`

Expected: failure because current code has no batch domain or durable aggregate.

- [ ] **Step 3: Implement batch models, commands, and aggregate calculation**

```python
def recompute_batch_status(db: Session, batch_id: str) -> Batch:
    counts = db.execute(
        select(Job.status, func.count())
        .where(Job.batch_id == batch_id)
        .group_by(Job.status)
    ).all()
    return apply_counts_to_batch(db.get(Batch, batch_id), counts)
```

Create child jobs through the same outbox path as single jobs. Enforce ownership and a server-side maximum concurrency; retry operates on selected failed item jobs instead of rebuilding successful children.

- [ ] **Step 4: Verify persistence, isolation, and partial failure recovery**

Run: `pytest tests/integration/test_batches.py -q`

Expected: batch counts survive reload, cross-project access is denied, and successful child jobs remain intact during failed-item retry.

- [ ] **Step 5: Commit persistent batches**

```bash
git add api worker tests
git commit -m "feat: add durable batch job aggregation"
```

### Task 9: Add operational limits and privacy-safe observability

**Files:**
- Create: `api/app/services/metrics.py`, `api/app/api/v1/metrics.py`, `worker/services/metrics.py`, `tests/integration/test_operational_metrics.py`
- Modify: `api/app/main.py`, `api/app/api/v1/health.py`, `api/app/api/v1/uploads.py`, `api/app/services/job_commands.py`, `worker/tasks.py`, `docker-compose.yml`, `README.md`

**Interfaces:**
- Produces `record_counter(name: str, value: int = 1, tags: Mapping[str, str] = {}) -> None` with an allowlisted tag set.
- Produces authenticated/operator-only `GET /metrics` and truthful `/health/live`, `/health/ready` endpoints.
- Produces resource configuration for maximum upload, queue routing, worker CPU/memory limits, and storage free-space readiness.

- [ ] **Step 1: Write readiness and privacy tests**

```python
def test_ready_fails_when_broker_check_fails(client, monkeypatch):
    monkeypatch.setattr("api.app.api.v1.health.ping_redis", lambda: False)
    assert client.get("/api/v1/health/ready").status_code == 503


def test_metric_tags_do_not_accept_filename_or_user_content():
    with pytest.raises(ValueError):
        record_counter("job.completed", tags={"filename": "private.wav"})
```

- [ ] **Step 2: Run operational tests**

Run: `pytest tests/integration/test_operational_metrics.py -q`

Expected: failure because readiness currently asserts Redis health without checking it and no metric privacy boundary exists.

- [ ] **Step 3: Implement bounded metrics and truthful dependency checks**

```python
ALLOWED_TAGS = {"job_type", "status", "stage", "queue"}


def record_counter(name: str, value: int = 1, tags: Mapping[str, str] = {}) -> None:
    if set(tags) - ALLOWED_TAGS:
        raise ValueError("unsupported metric tag")
```

Record job stage latency/failure, outbox lag, queue depth, upload rejection, and SSE reconnect/replay count. Expose no media filename, mix metadata, user token, or storage key. Configure worker concurrency and container resource limits consistent with CPU-heavy DSP.

- [ ] **Step 4: Verify operational behavior**

Run: `pytest tests/integration/test_operational_metrics.py -q`

Expected: real dependency readiness, bounded metric tags, and no sensitive labels.

- [ ] **Step 5: Commit operational safeguards**

```bash
git add api worker docker-compose.yml README.md tests/integration/test_operational_metrics.py
git commit -m "feat: add bounded operational readiness and metrics"
```
