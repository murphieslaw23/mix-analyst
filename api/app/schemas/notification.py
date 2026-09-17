from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    id: str
    job_id: str | None = None
    kind: str
    deep_link: str
    status: str
    created_at: datetime
    read_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PushSubscriptionIn(BaseModel):
    endpoint: str
    keys: dict[str, str] = {}


class PushSubscriptionOut(BaseModel):
    id: str
    endpoint_hash: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
