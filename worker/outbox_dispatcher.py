"""Publish committed job commands to Celery without losing broker outages."""

import logging
import os
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.models.job import Job
from api.app.models.outbox import OutboxMessage

from .celery_app import celery_app
from .db import SessionLocal


logger = logging.getLogger(__name__)
POLL_SECONDS = float(os.getenv("OUTBOX_POLL_SECONDS", "1"))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def dispatch_pending_messages(db: Session, celery_client=celery_app, batch_size: int = 100) -> int:
    """Deliver up to ``batch_size`` committed messages.

    A row remains locked while the broker accepts it and is marked delivered in
    the same database transaction.  If publication or commit fails, the row is
    left undelivered for a later dispatcher pass.  A rare post-accept commit
    failure may redeliver a command; worker-side claims make that harmless.
    """
    delivered = 0
    for _ in range(batch_size):
        message = db.scalar(
            select(OutboxMessage)
            .where(OutboxMessage.delivered_at.is_(None))
            .order_by(OutboxMessage.created_at, OutboxMessage.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if message is None:
            break

        message_id = message.id
        try:
            payload = message.payload
            result = celery_client.send_task(
                payload["task_name"],
                args=[payload["job_id"]],
                task_id=payload["task_id"],
                queue=payload["queue"],
            )
            message.delivery_attempts += 1
            message.last_error = None
            message.delivered_at = utcnow()
            job = db.get(Job, message.aggregate_id)
            if job is not None:
                job.celery_task_id = result.id
            db.commit()
            delivered += 1
        except Exception as exc:
            db.rollback()
            # Store delivery diagnostics in a new short transaction.  This
            # preserves retryability rather than turning a broker outage into a
            # failed job command.
            failed_message = db.get(OutboxMessage, message_id)
            if failed_message is not None:
                failed_message.delivery_attempts += 1
                failed_message.last_error = str(exc)
                db.commit()
            logger.warning("Could not deliver outbox message %s: %s", message_id, exc)
            break
    return delivered


def run_dispatcher() -> None:
    """Run the independent, restart-safe outbox dispatcher process."""
    while True:
        db = SessionLocal()
        try:
            dispatch_pending_messages(db)
        except Exception:
            db.rollback()
            logger.exception("Outbox dispatcher pass failed")
        finally:
            db.close()
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    run_dispatcher()
