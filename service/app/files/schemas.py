from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class FileResponse(BaseModel):
    id: UUID
    path: str
    content_type: str | None
    sha256: str | None
    author_id: UUID
    created_at: datetime
    okf_status: Literal["queued", "processing", "completed", "failed"]
    okf_attempts: int
    okf_error: str | None
