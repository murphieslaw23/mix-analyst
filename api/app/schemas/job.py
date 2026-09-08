from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..models.job import JobType


class StageRunOut(BaseModel):
    id: str
    stage_name: str
    stage_version: str
    status: str
    progress_percent: float
    stage_output: str | None = None
    error_message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None

    class Config:
        from_attributes = True


class JobAttemptOut(BaseModel):
    id: str
    attempt_number: int
    status: str
    worker_hostname: str | None = None
    started_at: datetime
    finished_at: datetime | None = None

    class Config:
        from_attributes = True


class JobOut(BaseModel):
    id: str
    mix_id: str
    # Child jobs retain the durable parent identifier so the UI can link to
    # aggregate recovery without deriving it from transient browser state.
    batch_id: str | None = None
    job_type: str
    status: str
    progress_percent: float
    current_stage: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    celery_task_id: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    stage_runs: list[StageRunOut] = []
    attempts: list[JobAttemptOut] = []

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """A project-scoped job page with a stable cursor continuation.

    ``total`` is the count captured with the first page's snapshot boundary;
    it deliberately does not grow while a caller walks that history.
    """

    items: list[JobOut]
    total: int
    next_cursor: str | None = None


class JobCreateRequest(BaseModel):
    job_type: JobType = JobType.ANALYSIS
    parameters: dict[str, Any] = Field(default_factory=dict)
