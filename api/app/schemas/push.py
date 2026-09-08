from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PushKeysIn(BaseModel):
    p256dh: str = Field(min_length=1)
    auth: str = Field(min_length=1)


class PushSubscriptionIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    endpoint: str = Field(min_length=1)
    expiration_time: int | None = Field(default=None, alias="expirationTime")
    keys: PushKeysIn


class PushSubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    active: bool
    created_at: datetime
    deactivated_at: datetime | None


class PushConfigOut(BaseModel):
    enabled: bool
    vapid_public_key: str | None
