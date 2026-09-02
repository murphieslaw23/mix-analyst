# Task 7 report: metadata and waveform artifacts

## Deterministic identity and key contract

Pure stages derive the relative identity `artifacts/{role}/{algorithm_version}/{source_sha256}`. The trusted worker alone prefixes that identity as `projects/{project_id}/...`, writes a canonical JSON payload with an atomic link, and rejects different bytes at an existing immutable key. Retries therefore reuse the same object and database identity. Waveform point count is a stage configuration covered by its algorithm version; changing it requires a version bump.

## Data and migration shape

`artifacts` stores owner project, mix, role, opaque key, SHA-256, algorithm version, media type, byte length, optional immutable report data, and timestamp. It has a project/key uniqueness constraint and owner/mix/role lookup index. Migration `20260902_08_artifacts` revises `20260902_06_mastering_job_parameters`, the actual preceding head, leaving exactly one head.

## API presentation and security

Mix responses include artifact metadata, protected download routes, and the metadata-stage suggested download name. Presentation names do not rename source objects. Downloads re-authorize both mix and artifact in the principal's project, validate the owner-prefixed key, and stream through the API; responses never expose raw filesystem paths or public object URLs.

## Tests

- `PYTHONPATH=. .venv/bin/pytest tests/unit/test_tag_mix_stage.py tests/unit/test_waveform_stage.py tests/integration/test_job_lifecycle.py tests/integration/test_authorization_scope.py tests/integration/test_app_boot.py -q` — 28 passed.
- `PYTHONPATH=. .venv/bin/python -m alembic -c api/alembic.ini heads` — one head: `20260902_08_artifacts`.
- `git diff --check` — clean.

## Commit

`feat: add metadata and waveform artifact stages`

## Concerns

No blocking concerns. A future remote object-storage adapter should mint an equivalently project-scoped, server-authorized download capability; the current local adapter intentionally serves the protected API route instead of a public storage URL.
