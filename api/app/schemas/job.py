from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


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

    model_config = ConfigDict(from_attributes=True)


class JobAttemptOut(BaseModel):
    id: str
    attempt_number: int
    status: str
    worker_hostname: str | None = None
    started_at: datetime
    finished_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class JobOut(BaseModel):
    id: str
    mix_id: str
    job_type: str
    status: str
    progress_percent: float
    current_stage: str | None = None
    celery_task_id: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    stage_runs: list[StageRunOut] = []

    model_config = ConfigDict(from_attributes=True)


class JobCreateRequest(BaseModel):
    job_type: str = "ANALYSIS"
    parameters: dict[str, Any] = {}
