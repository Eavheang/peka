from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


AccessLevel = Literal["general", "confidential"]


class IndexStatusResponse(BaseModel):
    file_id: str
    index_status: str
    index_attempts: int
    index_error: str | None


class FileResponse(BaseModel):
    id: UUID
    path: str
    content_type: str | None
    sha256: str | None
    author_id: UUID
    access_level: AccessLevel
    created_at: datetime
    index_status: Literal["queued", "processing", "completed", "failed"]
    index_attempts: int
    index_error: str | None


class AccessLevelUpdate(BaseModel):
    access_level: AccessLevel
