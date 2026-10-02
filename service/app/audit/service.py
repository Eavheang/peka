import base64
import binascii
from datetime import datetime
from uuid import UUID

from app.audit.repository import audit_repository
from app.audit.schemas import AuditEventType


class InvalidAuditCursor(Exception):
    """The list cursor is not a valid created_at and id keyset token."""


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
    value = f"{row['created_at'].isoformat()}|{row['id']}"
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        padding = "=" * (-len(cursor) % 4)
        value = base64.urlsafe_b64decode(cursor + padding).decode()
        created_at, event_id = value.split("|", 1)
        return datetime.fromisoformat(created_at), UUID(event_id)
    except (ValueError, UnicodeDecodeError, binascii.Error) as error:
        raise InvalidAuditCursor("Invalid audit cursor") from error
