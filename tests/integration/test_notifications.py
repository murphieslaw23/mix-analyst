"""Notification center + Web Push backend slice tests (SQLite, no Postgres)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.app import models as models  # noqa: PLC0414  (registers base models)
from api.app.db.session import Base
from api.app.models.notification import (  # registers new tables
    Notification,
    NotificationDelivery,
    PushSubscription,
)
from api.app.services.notifications import create_job_notification, dismiss, mark_read
from api.app.services.push import (
    build_push_payload,
    record_delivery,
    subscription_endpoint_hash,
)


def make_notification_session(tmp_path):
    """Fresh SQLite DB with the full application schema (mirrors make_session)."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test_notifications.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_duplicate_terminal_processing_creates_one_notification(tmp_path):
    db = make_notification_session(tmp_path)
    first = create_job_notification(
        db,
        project_id="proj-1",
        job_id="job-1",
        kind="job.succeeded",
        deep_link="/jobs/job-1",
    )
    second = create_job_notification(
        db,
        project_id="proj-1",
        job_id="job-1",
        kind="job.succeeded",
        deep_link="/jobs/job-1",
    )
    assert first.id == second.id
    assert db.query(Notification).count() == 1
    db.close()


def test_mark_read_persists(tmp_path):
    db = make_notification_session(tmp_path)
    created = create_job_notification(
        db,
        project_id="proj-1",
        job_id="job-2",
        kind="job.succeeded",
        deep_link="/jobs/job-2",
    )
    updated = mark_read(db, created.id)
    assert updated.status == "read"
    assert updated.read_at is not None
    db.expire_all()
    reloaded = db.query(Notification).filter(Notification.id == created.id).first()
    assert reloaded is not None
    assert reloaded.status == "read"
    assert reloaded.read_at is not None
    db.close()


def test_dismiss_persists(tmp_path):
    db = make_notification_session(tmp_path)
    created = create_job_notification(
        db,
        project_id="proj-1",
        job_id="job-dismiss",
        kind="job.failed",
        deep_link="/jobs/job-dismiss",
    )
    updated = dismiss(db, created.id)
    assert updated.status == "dismissed"
    assert updated.read_at is not None
    db.close()


def test_push_payload_contains_no_filename_or_secret_fields(tmp_path):
    db = make_notification_session(tmp_path)
    notification = create_job_notification(
        db,
        project_id="proj-1",
        job_id="job-3",
        kind="job.succeeded",
        deep_link="/jobs/job-3",
    )
    payload = build_push_payload(notification)
    assert payload["version"] == 1
    assert payload["notification_id"] == notification.id
    assert payload["deep_link"] == notification.deep_link
    assert set(payload.keys()) == {"version", "notification_id", "deep_link"}
    blob = " ".join(f"{k}={v}" for k, v in payload.items()).lower()
    for forbidden in ("filename", "secret", "error", "vapid", "key", "credential"):
        assert forbidden not in blob
    db.close()


def test_endpoint_hash_is_stable():
    endpoint = "https://push.example.com/subscriptions/abc123"
    first = subscription_endpoint_hash(endpoint)
    second = subscription_endpoint_hash(endpoint)
    assert first == second
    assert len(first) == 64
    assert all(c in "0123456789abcdef" for c in first)
    assert subscription_endpoint_hash(endpoint + "-other") != first


def test_delivery_upsert_dedupes_per_pair(tmp_path):
    db = make_notification_session(tmp_path)
    notification = create_job_notification(
        db,
        project_id="proj-1",
        job_id="job-4",
        kind="job.succeeded",
        deep_link="/jobs/job-4",
    )
    subscription = PushSubscription(
        project_id="proj-1",
        endpoint_hash=subscription_endpoint_hash("https://push.example.com/sub/1"),
        encrypted_payload="encrypted-blob",
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)

    first = record_delivery(db, notification.id, subscription.id, "sent")
    second = record_delivery(db, notification.id, subscription.id, "sent")
    assert first.id == second.id
    assert (
        db.query(NotificationDelivery)
        .filter(
            NotificationDelivery.notification_id == notification.id,
            NotificationDelivery.subscription_id == subscription.id,
        )
        .count()
        == 1
    )
    db.close()


# --- Route-level coverage for the wired notification center ---

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

import api.app.main as main_mod
from api.app.db.session import get_db
from api.app.main import app


@pytest.fixture
def center_client(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    session_factory = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = session_factory()
    create_job_notification(
        db,
        project_id="default-project",
        job_id="job-1",
        kind="job.succeeded",
        deep_link="/jobs/job-1",
    )
    create_job_notification(
        db,
        project_id="project-b",
        job_id="job-9",
        kind="job.failed",
        deep_link="/jobs/job-9",
    )
    db.close()

    monkeypatch.setattr(main_mod, "init_db", lambda: None)
    app.dependency_overrides[get_db] = lambda: session_factory()
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_center_lists_only_own_project(center_client):
    res = center_client.get("/api/v1/notifications")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["job_id"] == "job-1"


def test_center_read_and_dismiss_persist(center_client):
    item_id = center_client.get("/api/v1/notifications").json()[0]["id"]
    read = center_client.post(f"/api/v1/notifications/{item_id}/read")
    assert read.status_code == 200
    assert read.json()["status"] == "read"
    # Foreign ids 404 instead of leaking existence.
    assert center_client.post("/api/v1/notifications/nope/read").status_code == 404
    dismissed = center_client.post(f"/api/v1/notifications/{item_id}/dismiss")
    assert dismissed.json()["status"] == "dismissed"


def test_push_subscription_upsert_and_delete(center_client):
    body = {
        "endpoint": "https://push.example/abc",
        "keys": {"p256dh": "k", "auth": "a"},
    }
    first = center_client.post("/api/v1/push/subscriptions", json=body)
    assert first.status_code == 201, first.text
    sub_id = first.json()["id"]
    assert len(first.json()["endpoint_hash"]) == 64
    second = center_client.post("/api/v1/push/subscriptions", json=body)
    assert second.json()["id"] == sub_id
    assert (
        center_client.delete(f"/api/v1/push/subscriptions/{sub_id}").status_code == 204
    )
    assert (
        center_client.delete(f"/api/v1/push/subscriptions/{sub_id}").status_code == 404
    )
