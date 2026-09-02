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
from api.app.services.metrics import record_counter


def _token(user_id: str, project_id: str = "project-a") -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": user_id, "project_id": project_id}, separators=(",", ":")).encode()
    ).rstrip(b"=")
    signature = hmac.new(
        b"development-only-secret-change-me-32", header + b"." + payload, hashlib.sha256
    ).digest()
    return b".".join((header, payload, base64.urlsafe_b64encode(signature).rstrip(b"="))).decode()


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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


def test_metric_tags_do_not_accept_filename_or_user_content():
    with pytest.raises(ValueError):
        record_counter("job.enqueued", tags={"filename": "private.wav"})
    with pytest.raises(ValueError):
        record_counter("job.enqueued", tags={"stage": "private.wav"})


def test_metrics_requires_explicit_operator_and_never_renders_sensitive_labels(client, monkeypatch):
    monkeypatch.setattr("api.app.api.v1.metrics._queue_depths", lambda: [("analysis-cpu", 0)])
    record_counter("upload.rejected", tags={"stage": "upload", "status": "rejected"})

    denied = client.get("/api/v1/metrics", headers={"Authorization": f"Bearer {_token('not-an-operator')}"})
    assert denied.status_code == 403

    response = client.get("/api/v1/metrics", headers={"Authorization": f"Bearer {_token('operator')}"})
    assert response.status_code == 200
    assert "filename" not in response.text
    assert "project-a" not in response.text
    assert "upload_rejected" in response.text
