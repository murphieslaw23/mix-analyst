"""Public notification-center response contracts."""

from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: str
    job_id: str | None = None
    kind: str
    title: str
    body: str | None = None
    deep_link: str
    read_at: datetime | None = None
    dismissed_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    items: list[NotificationOut]
    total: int
