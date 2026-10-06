import base64
import logging
from datetime import datetime
from typing import Literal
from uuid import UUID

from app.audit.repository import audit_repository
from app.audit.schemas import AuditEventType

logger = logging.getLogger(__name__)

AuditEventName = Literal["sync_completed", "sync_failed", "chat_turn", "chat_turn_stopped", "chat_turn_failed", "login_success", "admin_gate_deny"]

AUDIT_EVENTS: dict[AuditEventName, tuple[AuditEventType, str]] = {
    "sync_completed": ("sync", "Sync completed"),
    "sync_failed": ("sync", "Sync failed"),
    "chat_turn": ("query", "Chat turn"),
    "chat_turn_stopped": ("query", "Chat turn stopped"),
    "chat_turn_failed": ("query", "Chat turn failed"),
    "login_success": ("system", "Login success"),
    "admin_gate_deny": ("system", "Admin gate deny"),
}


class InvalidAuditCursor(Exception):
    """The list cursor is not a valid created_at and id keyset token."""


def record_audit_event(
    event: AuditEventName,
    actor_id: UUID | None = None,
    metadata: dict | None = None,
) -> None:
    """Persist one audit event. Failures are logged and never raised to callers."""
    event_type, summary = AUDIT_EVENTS[event]
    try:
        audit_repository.insert(event_type, summary, actor_id, {"event": event, **(metadata or {})})
    except Exception:
        logger.exception("Failed to record audit event %s", event)


def list_events(
    event_type: AuditEventType | None,
    limit: int,
    cursor: str | None,
) -> dict:
    decoded = _decode_cursor(cursor) if cursor else None
    rows = audit_repository.fetch(event_type, limit + 1, decoded)
    has_more = len(rows) > limit
    items = rows[:limit]
    return {
        "items": items,
        "next_cursor": _encode_cursor(items[-1]) if has_more else None,
    }


def _encode_cursor(row: dict) -> str:
    return base64.urlsafe_b64encode(f"{row['created_at'].isoformat()}|{row['id']}".encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        created_at, event_id = base64.urlsafe_b64decode(cursor).decode().split("|", 1)
        return datetime.fromisoformat(created_at), UUID(event_id)
    except ValueError as error:  # binascii.Error and UnicodeDecodeError are ValueErrors
        raise InvalidAuditCursor("Invalid audit cursor") from error
