"""Integration contracts for opt-in, privacy-safe Web Push delivery."""

from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.app.db.session import Base
from api.app.models.identity import Project, User
from api.app.models.notification import Notification


def _database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Push models are imported inside the test so this test file can establish
    # the expected red baseline before Task 4 creates those modules.
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def test_gone_push_endpoint_is_deactivated_after_one_delivery_attempt(monkeypatch):
    from api.app.models.push_subscription import PushDelivery, PushSubscription
    from api.app.services.push import (
        PushDeliveryError,
        create_push_subscription,
        deliver_notification,
        queue_notification_deliveries,
    )

    engine, session_factory = _database()
    Base.metadata.create_all(bind=engine)
    db: Session = session_factory()
    captured_payloads: list[dict[str, object]] = []
    try:
        db.add_all(
            [
                User(id="user-a"),
                Project(id="project-a", owner_id="user-a"),
            ]
        )
        notification = Notification(
            id="notification-a",
            project_id="project-a",
            user_id="user-a",
            kind="job.succeeded",
            dedupe_key="job.succeeded:job-a",
            title="Mastering complete",
            body="Sensitive operator copy must not enter the OS payload.",
            deep_link="/jobs/job-a",
            created_at=datetime.now(timezone.utc),
        )
        db.add(notification)
        create_push_subscription(
            db,
            user_id="user-a",
            project_id="project-a",
            subscription_json={
                "endpoint": "https://push.example.invalid/gone-endpoint",
                "expirationTime": None,
                "keys": {"p256dh": "public-client-key", "auth": "client-auth-key"},
            },
        )
        queue_notification_deliveries(db, notification)
        db.commit()

        def gone_sender(*, subscription_info, payload):
            assert subscription_info["endpoint"].endswith("gone-endpoint")
            captured_payloads.append(payload)
            raise PushDeliveryError(status_code=410, message="Gone")

        outcome = deliver_notification(
            notification.id,
            db=db,
            sender=gone_sender,
        )

        assert outcome.status == "deactivated"
        subscription = db.scalar(select(PushSubscription))
        delivery = db.scalar(select(PushDelivery))
        assert subscription is not None and subscription.active is False
        assert subscription.deactivated_at is not None
        assert delivery is not None and delivery.attempt_count == 1
        assert delivery.status == "deactivated"
        assert captured_payloads == [
            {
                "version": 1,
                "notification_id": "notification-a",
                "deep_link": "/jobs/job-a",
            }
        ]
        assert "Mastering complete" not in str(captured_payloads)
        assert "Sensitive operator copy" not in str(captured_payloads)
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_subscription_payload_is_encrypted_at_rest():
    from api.app.models.push_subscription import PushSubscription
    from api.app.services.push import create_push_subscription

    engine, session_factory = _database()
    Base.metadata.create_all(bind=engine)
    db: Session = session_factory()
    try:
        db.add_all(
            [
                User(id="user-a"),
                Project(id="project-a", owner_id="user-a"),
            ]
        )
        subscription = create_push_subscription(
            db,
            user_id="user-a",
            project_id="project-a",
            subscription_json={
                "endpoint": "https://push.example.invalid/private-endpoint",
                "expirationTime": None,
                "keys": {"p256dh": "private-ish-client-key", "auth": "secret-auth-key"},
            },
        )
        db.commit()

        stored = db.get(PushSubscription, subscription.id)
        assert stored is not None
        assert "private-endpoint" not in stored.encrypted_payload
        assert "private-ish-client-key" not in stored.encrypted_payload
        assert "secret-auth-key" not in stored.encrypted_payload
        assert len(stored.endpoint_hash) == 64
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
