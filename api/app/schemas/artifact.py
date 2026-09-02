from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ArtifactOut(BaseModel):
    id: str
    role: str
    key: str
    sha256: str
    algorithm_version: str
    media_type: str
    byte_length: int
    report: dict[str, Any] | None = None
    download_url: str
    created_at: datetime
