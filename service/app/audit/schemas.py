from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

AuditEventType = Literal["sync", "query", "system"]


class AuditEvent(BaseModel):
    id: UUID
    type: AuditEventType
    actor_id: UUID | None = None
    summary: str
    metadata: dict
    created_at: datetime


class AuditEventsResponse(BaseModel):
    items: list[AuditEvent]
    next_cursor: str | None = None
