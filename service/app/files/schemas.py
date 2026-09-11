from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


AccessLevel = Literal["general", "confidential"]


class OKFStatusResponse(BaseModel):
    file_id: str
    okf_status: str
    okf_attempts: int
    okf_error: str | None


class FileResponse(BaseModel):
    id: UUID
    path: str
    content_type: str | None
    sha256: str | None
    author_id: UUID
    access_level: AccessLevel
    created_at: datetime
    okf_status: Literal["queued", "processing", "completed", "failed"]
    okf_attempts: int
    okf_error: str | None


class AccessLevelUpdate(BaseModel):
    access_level: AccessLevel
