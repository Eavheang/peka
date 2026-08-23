from typing import Any, cast
from uuid import UUID

from pgvector import Vector
from pgvector.psycopg import register_vector

from app.config import settings
from app.database import get_connection


class SearchRepository:
    def search_chunks(
        self,
        query_vector: list[float],
        allowed_access_levels: tuple[str, ...],
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Vector search over active chunk sets, permission-filtered in SQL."""
        limit = top_k or settings.search_top_k
        floor = settings.search_similarity_floor
        with get_connection() as connection:
            register_vector(connection)
            rows = connection.execute(
                "SELECT kc.file_id, kc.heading, kc.content, kc.source_locations, "
                "1 - (kc.embedding <=> %s) AS score "
                "FROM knowledge_chunks kc "
                "JOIN chunk_sets cs ON cs.id = kc.chunk_set_id AND cs.status = 'active' "
                "JOIN files f ON f.id = kc.file_id "
                "WHERE f.access_level = ANY(%s) AND 1 - (kc.embedding <=> %s) >= %s "
                "ORDER BY kc.embedding <=> %s LIMIT %s",
                (
                    Vector(query_vector),
                    list(allowed_access_levels),
                    Vector(query_vector),
                    floor,
                    Vector(query_vector),
                    limit,
                ),
            ).fetchall()
            return cast(list[dict[str, Any]], rows)

    def file_title(self, file_id: UUID) -> str:
        with get_connection() as connection:
            row = connection.execute("SELECT path FROM files WHERE id = %s", (file_id,)).fetchone()
            return row["path"].rsplit("/", 1)[-1] if row else "unknown"


search_repository = SearchRepository()
