"""Restart-safe dispatcher for committed Web Push delivery rows."""

import logging
import os
import time
from datetime import datetime, timezone

from sqlalchemy import or_, select

from api.app.models.push_subscription import PushDelivery
from api.app.services.push import deliver_notification

from .db import SessionLocal

logger = logging.getLogger(__name__)
POLL_SECONDS = float(os.getenv("PUSH_POLL_SECONDS", "2"))
BATCH_SIZE = int(os.getenv("PUSH_BATCH_SIZE", "50"))


def dispatch_due_notifications() -> int:
    db = SessionLocal()
    processed = 0
    try:
        now = datetime.now(timezone.utc)
        notification_ids = list(
            db.scalars(
                select(PushDelivery.notification_id)
                .where(
                    PushDelivery.status.in_(("pending", "retry")),
                    or_(
                        PushDelivery.next_attempt_at.is_(None),
                        PushDelivery.next_attempt_at <= now,
                    ),
                )
                .distinct()
                .limit(BATCH_SIZE)
            )
        )
        for notification_id in notification_ids:
            outcome = deliver_notification(notification_id, db=db)
            if outcome.status == "not_configured":
                db.rollback()
                break
            db.commit()
            processed += outcome.attempted
        return processed
    except Exception:
        db.rollback()
        logger.exception("Push dispatcher pass failed")
        return processed
    finally:
        db.close()


def run_dispatcher() -> None:
    while True:
        dispatch_due_notifications()
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    run_dispatcher()
