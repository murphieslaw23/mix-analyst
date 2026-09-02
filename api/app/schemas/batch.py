"""Batch command and read-model schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .job import JobOut


MAX_BATCH_PARALLELISM = 4


class BatchCreateRequest(BaseModel):
    mix_ids: list[str] = Field(min_length=1)
    preset: dict[str, Any] = Field(default_factory=dict)
    max_parallelism: int = Field(default=1, ge=1, le=MAX_BATCH_PARALLELISM)


class BatchRetryRequest(BaseModel):
    job_ids: list[str] = Field(min_length=1)


class BatchOut(BaseModel):
    id: str
    status: str
    total_count: int
    completed_count: int
    failed_count: int
    cancelled_count: int
    items: list[JobOut]
    preset: dict[str, Any] = Field(default_factory=dict)
    max_parallelism: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
