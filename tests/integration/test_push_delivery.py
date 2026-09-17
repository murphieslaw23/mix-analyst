"""Web Push delivery tests (SQLite, monkeypatched pywebpush)."""

import json
from types import SimpleNamespace

import pytest
from pywebpush import WebPushException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.app import models as models  # noqa: PLC0414  (registers base models)
from api.app.db.session import Base
from api.app.models.notification import (
    Notification,
    NotificationDelivery,
    PushSubscription,
)
from api.app.services.push import subscription_endpoint_hash
from worker import push_dispatcher
from worker.push_dispatcher import deliver_notification


def make_push_factory(tmp_path, name="test_push_delivery.db"):
    """Fresh SQLite DB with the full application schema (mirrors make_session)."""
    engine = create_engine(f"sqlite:///{tmp_path / name}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def seed_notification(db, project_id="proj-1", job_id="job-1", suffix="a"):
    """Insert a Notification row directly (no FK coupling)."""
    row = Notification(
        project_id=project_id,
        job_id=job_id,
        kind="job.succeeded",
        dedupe_key=f"job.succeeded:{job_id}:{suffix}",
        deep_link=f"/jobs/{job_id}",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def seed_subscription(
    db, project_id="proj-1", endpoint="https://push.example.com/sub/1"
):
    """Insert a PushSubscription row directly (no FK coupling)."""
    row = PushSubscription(
        project_id=project_id,
        endpoint_hash=subscription_endpoint_hash(endpoint),
        encrypted_payload=json.dumps(
            {
                "endpoint": endpoint,
                "keys": {"p256dh": "p256dh-key", "auth": "auth-key"},
            }
        ),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture
def vapid_env(monkeypatch):
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "test-vapid-private-key")
    monkeypatch.setenv("VAPID_CONTACT", "mailto:push-tests@example.com")


def get_delivery(db, notification_id, subscription_id):
    return (
        db.query(NotificationDelivery)
        .filter(
            NotificationDelivery.notification_id == notification_id,
            NotificationDelivery.subscription_id == subscription_id,
        )
        .one()
    )


def get_subscription(db, subscription_id):
    return (
        db.query(PushSubscription).filter(PushSubscription.id == subscription_id).one()
    )


def gone_sender(**kwargs):
    raise WebPushException("endpoint gone", response=SimpleNamespace(status_code=410))


def test_gone_endpoint_is_deactivated(tmp_path, monkeypatch, vapid_env):
    factory = make_push_factory(tmp_path)
    db = factory()
    notification = seed_notification(db)
    subscription = seed_subscription(db)
    notification_id, subscription_id = notification.id, subscription.id
    db.close()
    monkeypatch.setattr(push_dispatcher, "webpush", gone_sender)

    outcome = deliver_notification(factory, notification_id)

    assert outcome["status"] == "deactivated"
    assert outcome["attempted"] == 1
    assert outcome["delivered"] == 0
    db = factory()
    assert get_delivery(db, notification_id, subscription_id).status == "deactivated"
    assert get_subscription(db, subscription_id).deactivated_at is not None
    db.close()


def test_transient_503_retries_then_gives_up(tmp_path, monkeypatch, vapid_env):
    factory = make_push_factory(tmp_path)
    db = factory()
    notification = seed_notification(db)
    subscription = seed_subscription(db)
    notification_id, subscription_id = notification.id, subscription.id
    db.close()

    def flaky_sender(**kwargs):
        raise WebPushException(
            "temporarily unavailable",
            response=SimpleNamespace(status_code=503),
        )

    monkeypatch.setattr(push_dispatcher, "webpush", flaky_sender)

    for attempt in range(1, 5):
        outcome = deliver_notification(factory, notification_id)
        assert outcome["status"] == "retryable"
        assert outcome["attempted"] == 1
        assert outcome["delivered"] == 0
        db = factory()
        delivery = get_delivery(db, notification_id, subscription_id)
        assert delivery.status == "retryable"
        assert delivery.attempts == attempt
        assert delivery.last_error
        assert get_subscription(db, subscription_id).deactivated_at is None
        db.close()

    outcome = deliver_notification(factory, notification_id)
    assert outcome["status"] == "deactivated"
    assert outcome["attempted"] == 1
    assert outcome["delivered"] == 0
    db = factory()
    final = get_delivery(db, notification_id, subscription_id)
    assert final.status == "deactivated"
    assert final.attempts == 5
    db.close()


def test_successful_send_is_delivered(tmp_path, monkeypatch, vapid_env):
    factory = make_push_factory(tmp_path)
    db = factory()
    notification = seed_notification(db)
    subscription = seed_subscription(db)
    notification_id, subscription_id = notification.id, subscription.id
    db.close()
    calls = []

    def ok_sender(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(status_code=201)

    monkeypatch.setattr(push_dispatcher, "webpush", ok_sender)

    outcome = deliver_notification(factory, notification_id)

    assert outcome == {"status": "delivered", "attempted": 1, "delivered": 1}
    assert len(calls) == 1
    db = factory()
    delivery = get_delivery(db, notification_id, subscription_id)
    assert delivery.status == "delivered"
    assert delivery.attempts == 1
    assert get_subscription(db, subscription_id).deactivated_at is None
    db.close()


def test_sent_payload_contains_only_routing_fields(tmp_path, monkeypatch, vapid_env):
    factory = make_push_factory(tmp_path)
    db = factory()
    notification = seed_notification(db)
    seed_subscription(db)
    notification_id = notification.id
    db.close()
    calls = []

    def ok_sender(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(status_code=201)

    monkeypatch.setattr(push_dispatcher, "webpush", ok_sender)

    outcome = deliver_notification(factory, notification_id)

    assert outcome["status"] == "delivered"
    assert len(calls) == 1
    payload = json.loads(calls[0]["data"])
    assert set(payload.keys()) == {"version", "notification_id", "deep_link"}
    assert payload["version"] == 1
    assert payload["notification_id"] == notification_id
    assert payload["deep_link"] == "/jobs/job-1"
    assert calls[0]["vapid_claims"] == {"sub": "mailto:push-tests@example.com"}
    assert calls[0]["vapid_private_key"] == "test-vapid-private-key"


def test_missing_vapid_private_key_is_misconfigured(tmp_path, monkeypatch):
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    factory = make_push_factory(tmp_path)
    db = factory()
    notification = seed_notification(db)
    seed_subscription(db)
    notification_id = notification.id
    db.close()
    sent = []

    def ok_sender(**kwargs):
        sent.append(kwargs)
        return SimpleNamespace(status_code=201)

    monkeypatch.setattr(push_dispatcher, "webpush", ok_sender)

    outcome = deliver_notification(factory, notification_id)

    assert outcome["status"] == "misconfigured"
    assert outcome["attempted"] == 0
    assert outcome["delivered"] == 0
    assert sent == []
    db = factory()
    assert db.query(NotificationDelivery).count() == 0
    db.close()


def test_no_active_subscriptions_reports_no_subscriptions(
    tmp_path, monkeypatch, vapid_env
):
    factory = make_push_factory(tmp_path)
    db = factory()
    notification = seed_notification(db)
    notification_id = notification.id
    db.close()

    def exploding_sender(**kwargs):  # pragma: no cover - must not be called
        raise AssertionError("webpush must not be called without subscriptions")

    monkeypatch.setattr(push_dispatcher, "webpush", exploding_sender)

    outcome = deliver_notification(factory, notification_id)

    assert outcome == {"status": "no_subscriptions", "attempted": 0, "delivered": 0}


def test_one_failure_does_not_abort_siblings(tmp_path, monkeypatch, vapid_env):
    factory = make_push_factory(tmp_path)
    db = factory()
    notification = seed_notification(db)
    gone = seed_subscription(db, endpoint="https://push.example.com/gone")
    healthy = seed_subscription(db, endpoint="https://push.example.com/healthy")
    notification_id = notification.id
    gone_id, healthy_id = gone.id, healthy.id
    db.close()

    def mixed_sender(**kwargs):
        if "gone" in kwargs["subscription_info"]["endpoint"]:
            raise WebPushException(
                "endpoint gone", response=SimpleNamespace(status_code=410)
            )
        return SimpleNamespace(status_code=201)

    monkeypatch.setattr(push_dispatcher, "webpush", mixed_sender)

    outcome = deliver_notification(factory, notification_id)

    assert outcome == {"status": "delivered", "attempted": 2, "delivered": 1}
    db = factory()
    assert get_delivery(db, notification_id, gone_id).status == "deactivated"
    assert get_subscription(db, gone_id).deactivated_at is not None
    assert get_delivery(db, notification_id, healthy_id).status == "delivered"
    assert get_subscription(db, healthy_id).deactivated_at is None
    db.close()
