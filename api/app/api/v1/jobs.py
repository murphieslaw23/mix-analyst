import base64
import binascii
import hashlib
import hmac
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ...config import settings
from ...db.session import get_db
from ...models.job import Job, JobStatus
from ...schemas.auth import CurrentPrincipal
from ...schemas.job import JobCreateRequest, JobListResponse, JobOut
from ...services.batches import recompute_batch_status
from ...services.job_commands import UnsupportedJobTypeError, enqueue_job, enqueue_retry
from ...services.job_events import event_notification, publish_event, stream_job_events
from ...services.job_events_store import request_cancellation
from ..deps import get_current_principal, require_owned_job, require_owned_mix

router = APIRouter()


def _cursor_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="The jobs cursor is invalid or has expired. Refresh the jobs list and try again.",
    )


def _encode_cursor(payload: dict[str, object]) -> str:
    """Make an opaque, signed cursor that cannot be changed across projects."""
    encoded_payload = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode()
    signature = hmac.new(
        settings.auth_jwt_secret.encode(), encoded_payload, hashlib.sha256
    ).digest()
    return f"{base64.urlsafe_b64encode(encoded_payload).rstrip(b'=').decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def _decode_cursor(value: str, project_id: str) -> dict[str, object]:
    try:
        encoded_payload, encoded_signature = value.split(".", 1)
        payload_bytes = base64.urlsafe_b64decode(
            encoded_payload + "=" * (-len(encoded_payload) % 4)
        )
        signature = base64.urlsafe_b64decode(
            encoded_signature + "=" * (-len(encoded_signature) % 4)
        )
        expected = hmac.new(
            settings.auth_jwt_secret.encode(), payload_bytes, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(payload_bytes)
        if (
            not isinstance(payload, dict)
            or payload.get("v") != 1
            or payload.get("project_id") != project_id
        ):
            raise ValueError
        for key in (
            "snapshot_created_at",
            "snapshot_id",
            "after_created_at",
            "after_id",
            "total",
        ):
            if key not in payload:
                raise ValueError
        if not all(
            isinstance(payload[key], str)
            for key in (
                "snapshot_created_at",
                "snapshot_id",
                "after_created_at",
                "after_id",
            )
        ):
            raise ValueError
        if not isinstance(payload["total"], int) or payload["total"] < 0:
            raise ValueError
        # fromisoformat is only validation here; SQLAlchemy receives the typed
        # timestamp below, never a user supplied raw cursor string.
        datetime.fromisoformat(str(payload["snapshot_created_at"]))
        datetime.fromisoformat(str(payload["after_created_at"]))
        return payload
    except (
        ValueError,
        TypeError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        binascii.Error,
    ):
        raise _cursor_error() from None


def _before_or_equal(created_at: datetime, job_id: str):
    return or_(
        Job.created_at < created_at,
        and_(Job.created_at == created_at, Job.id <= job_id),
    )


def _strictly_before(created_at: datetime, job_id: str):
    return or_(
        Job.created_at < created_at, and_(Job.created_at == created_at, Job.id < job_id)
    )


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    page: int | None = Query(None, ge=1, deprecated=True),
    cursor: str | None = Query(None, min_length=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """List durable jobs using a signed, project-bound keyset cursor.

    The cursor freezes the newest item seen on its first page, then advances by
    ``created_at, id``. New jobs cannot shift later history, and the signed
    project id prevents a cursor from disclosing another project's count.

    ``page`` remains as a deprecated offset-compatible escape hatch for older
    clients. New clients must omit it and follow ``next_cursor``.
    """
    if cursor is not None and page is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Use either page or cursor, not both.",
        )
    scoped = select(Job).where(Job.project_id == principal.project_id)

    # Compatibility is intentionally isolated from the stable cursor path.
    if page is not None:
        total = db.scalar(select(func.count()).select_from(scoped.subquery())) or 0
        jobs = list(
            db.scalars(
                scoped.order_by(Job.created_at.desc(), Job.id.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        )
        return JobListResponse(items=jobs, total=total)

    cursor_payload = _decode_cursor(cursor, principal.project_id) if cursor else None
    if cursor_payload is None:
        total = 0
        page_query = scoped
    else:
        snapshot_created_at = datetime.fromisoformat(
            str(cursor_payload["snapshot_created_at"])
        )
        after_created_at = datetime.fromisoformat(
            str(cursor_payload["after_created_at"])
        )
        total = int(cursor_payload["total"])
        page_query = scoped.where(
            _before_or_equal(snapshot_created_at, str(cursor_payload["snapshot_id"])),
            _strictly_before(after_created_at, str(cursor_payload["after_id"])),
        )

    candidates = list(
        db.scalars(
            page_query.order_by(Job.created_at.desc(), Job.id.desc()).limit(limit + 1)
        )
    )
    # Capture the count under the same upper sorting bound that goes in the
    # cursor. A later, newer job therefore cannot change a snapshot's display
    # total or make the continuation look unfinished.
    if cursor_payload is None and candidates:
        snapshot_head = candidates[0]
        total = (
            db.scalar(
                select(func.count()).select_from(
                    scoped.where(
                        _before_or_equal(snapshot_head.created_at, snapshot_head.id)
                    ).subquery()
                )
            )
            or 0
        )
    jobs = candidates[:limit]
    if len(candidates) <= limit or not jobs:
        return JobListResponse(items=jobs, total=total)

    snapshot = jobs[0] if cursor_payload is None else None
    next_cursor = _encode_cursor(
        {
            "v": 1,
            "project_id": principal.project_id,
            "snapshot_created_at": (
                snapshot.created_at
                if snapshot
                else datetime.fromisoformat(str(cursor_payload["snapshot_created_at"]))
            ).isoformat(),
            "snapshot_id": snapshot.id
            if snapshot
            else str(cursor_payload["snapshot_id"]),
            "after_created_at": jobs[-1].created_at.isoformat(),
            "after_id": jobs[-1].id,
            "total": total,
        }
    )
    return JobListResponse(items=jobs, total=total, next_cursor=next_cursor)


@router.post(
    "/mixes/{mix_id}/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED
)
def create_mix_job(
    mix_id: str,
    req: JobCreateRequest,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Dispatch an asynchronous analysis/processing job for a mix."""
    mix = require_owned_mix(db, principal, mix_id)

    try:
        job = enqueue_job(db, principal, mix, req)
    except UnsupportedJobTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Get the current status and stage runs for a job."""
    return require_owned_job(db, principal, job_id)


@router.get("/jobs/{job_id}/events")
async def get_job_events(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Subscribe to real-time Server-Sent Events (SSE) for job progress."""
    job = require_owned_job(db, principal, job_id)
    raw_last_event_id = request.headers.get("Last-Event-ID", "0")
    try:
        last_event_id = int(raw_last_event_id)
        if last_event_id < 0:
            raise ValueError
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Last-Event-ID must be a non-negative integer",
        ) from None
    return StreamingResponse(
        stream_job_events(db, job.project_id, job.id, last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Cancel an active or queued job."""
    job = require_owned_job(db, principal, job_id)
    was_cancellable = job.status in (JobStatus.QUEUED, JobStatus.RUNNING)

    job = request_cancellation(db, job)
    if job.batch_id is not None:
        # A running child occupies a durable batch slot. Cancellation releases
        # it synchronously so one waiting sibling receives a fresh outbox
        # command instead of remaining queued until unrelated work finishes.
        from ...services.batches import advance_batch_after_terminal_job

        advance_batch_after_terminal_job(db, job.id, job.project_id)
    db.commit()
    db.refresh(job)
    cancellation_event = job.events[-1] if was_cancellable and job.events else None
    if cancellation_event is not None:
        publish_event(job.project_id, job.id, event_notification(cancellation_event))
    return job


@router.post("/jobs/{job_id}/retry", response_model=JobOut)
def retry_job(
    job_id: str,
    db: Session = Depends(get_db),
    principal: CurrentPrincipal = Depends(get_current_principal),
):
    """Retry a failed or cancelled job as a new attempt."""
    job = require_owned_job(db, principal, job_id)

    if job.status not in [JobStatus.FAILED, JobStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed or cancelled jobs can be retried",
        )

    if enqueue_retry(db, job) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed or cancelled jobs can be retried",
        )
    if job.batch_id is not None:
        recompute_batch_status(db, job.batch_id)
    db.commit()
    db.refresh(job)
    return job
