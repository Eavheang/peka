import base64
import binascii
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from app.database import get_connection


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
        raise ValueError("Invalid audit cursor") from error


class AuditRepository:
    def insert(
        self,
        event_type: str,
        summary: str,
        actor_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO audit_events (type, actor_id, summary, metadata) "
                "VALUES (%s, %s, %s, %s)",
                (event_type, actor_id, summary, Jsonb(metadata or {})),
            )

    def list_events(
        self,
        event_type: str | None,
        limit: int,
        cursor: str | None,
    ) -> dict:
        decoded = _decode_cursor(cursor) if cursor else None
        rows = self._fetch(event_type, limit + 1, decoded)
        has_more = len(rows) > limit
        items = rows[:limit]
        return {
            "items": items,
            "next_cursor": _encode_cursor(items[-1]) if has_more else None,
        }

    def _fetch(
        self,
        event_type: str | None,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> list[dict[str, Any]]:
        query = (
            "SELECT id, type, actor_id, summary, metadata, created_at "
            "FROM audit_events WHERE TRUE"
        )
        params: list[Any] = []
        if event_type is not None:
            query += " AND type = %s"
            params.append(event_type)
        if cursor is not None:
            query += " AND (created_at, id) < (%s, %s)"
            params.extend(cursor)
        query += " ORDER BY created_at DESC, id DESC LIMIT %s"
        params.append(limit)
        with get_connection() as connection:
            return list(connection.execute(query, tuple(params)).fetchall())


audit_repository = AuditRepository()
