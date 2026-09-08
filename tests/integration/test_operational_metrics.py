"""Operational behavior that remains meaningful without host Redis/PostgreSQL."""

import base64
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.db.session import Base, get_db
from api.app.main import app
from api.app.models.identity import Project, User
from api.app.services import metrics as metrics_service
from api.app.services.metrics import record_counter


def _token(user_id: str, project_id: str = "project-a") -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=")
    payload = base64.urlsafe_b64encode(
        json.dumps(
            {"sub": user_id, "project_id": project_id}, separators=(",", ":")
        ).encode()
    ).rstrip(b"=")
    signature = hmac.new(
        b"development-only-secret-change-me-32", header + b"." + payload, hashlib.sha256
    ).digest()
    return b".".join(
        (header, payload, base64.urlsafe_b64encode(signature).rstrip(b"="))
    ).decode()


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(engine)
    session = factory()
    session.add_all([User(id="operator"), Project(id="project-a", owner_id="operator")])
    session.commit()
    session.close()

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setenv("OPERATOR_USER_IDS", "operator")
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_ready_fails_when_broker_check_fails(client, monkeypatch):
    monkeypatch.setattr("api.app.api.v1.health.ping_redis", lambda: False)
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["redis"] == "error"


def test_storage_readiness_uses_and_removes_a_unique_probe_file(tmp_path, monkeypatch):
    from api.app.api.v1 import health

    monkeypatch.setattr(health.settings, "storage_root", str(tmp_path))
    monkeypatch.setattr(health.settings, "min_storage_free_bytes", 0)
    assert health.storage_is_ready() is True
    assert list(tmp_path.glob(".healthcheck-*")) == []


def test_metric_tags_do_not_accept_filename_or_user_content():
    with pytest.raises(ValueError):
        record_counter("job.enqueued", tags={"filename": "private.wav"})
    with pytest.raises(ValueError):
        record_counter("job.enqueued", tags={"stage": "private.wav"})


def test_metrics_requires_explicit_operator_and_never_renders_sensitive_labels(
    client, monkeypatch
):
    monkeypatch.setattr(
        "api.app.api.v1.metrics._queue_depths", lambda: [("analysis-cpu", 0)]
    )
    record_counter("upload.rejected", tags={"stage": "upload", "status": "rejected"})

    denied = client.get(
        "/api/v1/metrics",
        headers={"Authorization": f"Bearer {_token('not-an-operator')}"},
    )
    assert denied.status_code == 401

    response = client.get(
        "/api/v1/metrics", headers={"Authorization": f"Bearer {_token('operator')}"}
    )
    assert response.status_code == 200
    assert "filename" not in response.text
    assert "project-a" not in response.text
    assert "upload_rejected" in response.text


def test_worker_metric_is_visible_from_operator_api_scrape(client, monkeypatch):
    """A worker process writes shared counters; an API process reads that hash."""
    from worker.services import metrics as worker_metrics

    class SharedMetricsRedis:
        def __init__(self):
            self.values = {}

        def hincrby(self, key, field, value):
            self.values[(key, field)] = self.values.get((key, field), 0) + value

        def hgetall(self, key):
            return {
                field: value
                for (stored_key, field), value in self.values.items()
                if stored_key == key
            }

        def close(self):
            pass

    shared = SharedMetricsRedis()
    monkeypatch.setattr(metrics_service, "_metrics_redis_client", lambda: shared)
    monkeypatch.setattr(
        "api.app.api.v1.metrics._queue_depths", lambda: [("analysis-cpu", 0)]
    )

    worker_metrics.record_job_finished(
        "MASTERING", start_time=worker_metrics.time.monotonic() - 1, status="failed"
    )
    metrics_service._counters.clear()  # Model an independent API process with no worker memory.

    response = client.get(
        "/api/v1/metrics", headers={"Authorization": f"Bearer {_token('operator')}"}
    )
    assert response.status_code == 200
    assert (
        'mix_analyst_job_stage_duration_ms{job_type="MASTERING",stage="mastering",status="failed"}'
        in response.text
    )
    assert (
        'mix_analyst_job_failed{job_type="MASTERING",stage="mastering",status="failed"}'
        in response.text
    )
    assert "mix_analyst_counter_backend_available 1" in response.text


def test_local_metric_fallback_flushes_when_redis_recovers(monkeypatch):
    """A transient telemetry outage may delay, but must not drop, a counter."""

    class RecoveringRedis:
        def __init__(self):
            self.available = False
            self.values = {}

        def hincrby(self, key, field, value):
            if not self.available:
                raise OSError("redis temporarily unavailable")
            self.values[(key, field)] = self.values.get((key, field), 0) + value

        def hgetall(self, key):
            if not self.available:
                raise OSError("redis temporarily unavailable")
            return {
                field: value
                for (stored_key, field), value in self.values.items()
                if stored_key == key
            }

        def close(self):
            pass

    shared = RecoveringRedis()
    monkeypatch.setattr(metrics_service, "_metrics_redis_client", lambda: shared)
    metrics_service._counters.clear()
    record_counter("upload.rejected", 3, tags={"stage": "upload", "status": "rejected"})
    assert metrics_service.counter_samples()[0][1] == 3

    shared.available = True
    samples, shared_available = metrics_service.shared_counter_samples()
    assert shared_available is True
    assert ("upload.rejected", 3, {"stage": "upload", "status": "rejected"}) in samples
    assert metrics_service.counter_samples() == []
