from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.audit.repository import audit_repository
from app.audit.schemas import AuditEventsResponse
from app.auth.routes import admin_only

router = APIRouter(prefix="/admin", tags=["audit"])


@router.get("/audit-events", response_model=AuditEventsResponse)
def list_audit_events(
    event_type: Literal["sync", "query", "system"] | None = Query(default=None, alias="type"),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    _: dict = Depends(admin_only),
) -> dict:
    try:
        return audit_repository.list_events(event_type, limit, cursor)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid audit cursor") from None
