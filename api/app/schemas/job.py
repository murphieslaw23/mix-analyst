from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any

from ..models.job import JobType


class StageRunOut(BaseModel):
    id: str
    stage_name: str
    stage_version: str
    status: str
    progress_percent: float
    stage_output: Optional[str] = None
    error_message: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobAttemptOut(BaseModel):
    id: str
    attempt_number: int
    status: str
    worker_hostname: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobOut(BaseModel):
    id: str
    mix_id: str
    job_type: str
    status: str
    progress_percent: float
    current_stage: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    celery_task_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    stage_runs: List[StageRunOut] = []
    attempts: List[JobAttemptOut] = []

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """Stable, project-scoped page of durable jobs."""

    items: List[JobOut]
    total: int


class JobCreateRequest(BaseModel):
    job_type: JobType = JobType.ANALYSIS
    parameters: Dict[str, Any] = Field(default_factory=dict)
