from datetime import datetime

from pydantic import BaseModel, Field


class BatchCreateRequest(BaseModel):
    mix_ids: list[str] = Field(min_length=1, max_length=50)
    max_parallelism: int = Field(default=2, ge=1, le=8)


class BatchItemOut(BaseModel):
    job_id: str
    mix_id: str
    status: str


class BatchOut(BaseModel):
    id: str
    project_id: str
    status: str
    total_count: int
    queued_count: int
    running_count: int
    completed_count: int
    failed_count: int
    cancelled_count: int
    items: list[BatchItemOut]
    created_at: datetime
