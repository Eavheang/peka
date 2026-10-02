from fastapi import APIRouter, Depends, HTTPException, Query

from app.audit.schemas import AuditEventType, AuditEventsResponse
from app.audit.service import InvalidAuditCursor, list_events
from app.auth.routes import admin_only

router = APIRouter(prefix="/admin", tags=["audit"])


@router.get("/audit-events", response_model=AuditEventsResponse)
def list_audit_events(
    event_type: AuditEventType | None = Query(default=None, alias="type"),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    _: dict = Depends(admin_only),
) -> dict:
    try:
        return list_events(event_type, limit, cursor)
    except InvalidAuditCursor:
        raise HTTPException(status_code=400, detail="Invalid audit cursor") from None
