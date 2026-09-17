"""Transactional outbox delivery: DB commit first, broker second.

The API persists an OutboxMessage in the same transaction as the job;
this dispatcher publishes pending rows to Celery and marks them
delivered only after broker acceptance. Failures keep a retryable row
(delivery_attempts/last_error) so no queued job is ever lost.
"""

import json
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import bindparam, text

# sender(task_name, args, task_id, queue) -> broker task id
TaskSender = Callable[[str, list[Any], str, str], str]


def dispatch_outbox_message(db, message_id: str, sender: TaskSender) -> bool:
    """Deliver one pending outbox row. True when the broker accepted it."""
    row = db.execute(
        text("""
            SELECT id, payload, delivery_attempts FROM outbox_messages
            WHERE id = :id AND delivered_at IS NULL
        """),
        {"id": message_id},
    ).fetchone()
    if not row:
        return True
    try:
        payload = json.loads(row.payload)
    except ValueError:
        payload = {}
    try:
        broker_id = sender(
            str(payload.get("task_name", "")),
            list(payload.get("args", [])),
            str(payload.get("task_id", "")),
            str(payload.get("queue", "analysis")),
        )
    except Exception as e:  # noqa: BLE001 - any sender failure keeps the row retryable
        db.execute(
            text("""
                UPDATE outbox_messages
                SET delivery_attempts = delivery_attempts + 1, last_error = :err
                WHERE id = :id
            """),
            {"id": message_id, "err": f"{type(e).__name__}: {e}"},
        )
        db.commit()
        return False
    now = datetime.now(timezone.utc)
    db.execute(
        text("""
            UPDATE outbox_messages
            SET delivered_at = :now, last_error = NULL WHERE id = :id
        """),
        {"id": message_id, "now": now},
    )
    try:
        aggregate = db.execute(
            text("SELECT aggregate_id FROM outbox_messages WHERE id = :id"),
            {"id": message_id},
        ).fetchone()
        if aggregate:
            db.execute(
                text("UPDATE jobs SET celery_task_id = :task WHERE id = :id"),
                {"id": aggregate.aggregate_id, "task": broker_id},
            )
    except Exception:  # noqa: BLE001, S110 - delivery already recorded above
        # A missing jobs row must not fail the recorded delivery.
        pass
    db.commit()
    return True


def dispatch_pending(
    db, sender: TaskSender, *, job_ids: Sequence[str] | None = None, limit: int = 25
) -> int:
    """Deliver pending outbox rows (optionally scoped to jobs)."""
    if job_ids is not None and len(job_ids) == 0:
        return 0
    params: dict[str, Any] = {"limit": limit}
    scope = ""
    if job_ids is not None:
        scope = "AND aggregate_id IN :ids"
        params["ids"] = tuple(job_ids)
    stmt = text(f"""
            SELECT id FROM outbox_messages
            WHERE delivered_at IS NULL {scope}
            ORDER BY created_at ASC LIMIT :limit
        """)
    if job_ids is not None:
        stmt = stmt.bindparams(bindparam("ids", expanding=True))
    rows = db.execute(stmt, params).fetchall()
    delivered = 0
    for (message_id,) in rows:
        if dispatch_outbox_message(db, message_id, sender):
            delivered += 1
    return delivered
