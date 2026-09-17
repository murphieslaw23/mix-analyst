from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ArtifactOut(BaseModel):
    id: str
    role: str
    key: str
    sha256: str
    algorithm_version: str
    media_type: str
    byte_length: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
