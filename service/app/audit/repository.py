from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from app.audit.schemas import AuditEventType
from app.database import get_connection


class AuditRepository:
    def insert(
        self,
        event_type: AuditEventType,
        summary: str,
        actor_id: UUID | None,
        metadata: dict,
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO audit_events (type, actor_id, summary, metadata) "
                "VALUES (%s, %s, %s, %s)",
                (event_type, actor_id, summary, Jsonb(metadata)),
            )

    def fetch(
        self,
        event_type: AuditEventType | None,
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
