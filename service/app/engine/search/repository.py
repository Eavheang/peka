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
        similarity_floor: float | None = None,
    ) -> list[dict[str, Any]]:
        """Vector search over active chunk sets, permission-filtered in SQL."""
        limit = top_k or settings.search_top_k
        floor = settings.search_similarity_floor if similarity_floor is None else similarity_floor
        with get_connection() as connection:
            register_vector(connection)
            rows = connection.execute(
                "SELECT kc.id, kc.file_id, kc.heading, kc.content, kc.source_locations, "
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

    def find_source(
        self, chunk_id: UUID | None, title: str, heading: str,
        allowed_access_levels: tuple[str, ...],
    ) -> dict[str, Any] | None:
        query = (
            "SELECT kc.content, kc.file_id FROM knowledge_chunks kc "
            "JOIN chunk_sets cs ON cs.id = kc.chunk_set_id AND cs.status = 'active' "
            "JOIN files f ON f.id = kc.file_id "
            "WHERE f.access_level = ANY(%s) "
            "AND regexp_replace(f.path, '^.*/', '') = %s AND kc.heading = %s"
        )
        parameters: list[Any] = [list(allowed_access_levels), title, heading]
        if chunk_id is not None:
            query += " AND kc.id = %s"
            parameters.append(chunk_id)
        with get_connection() as connection:
            rows = connection.execute(query + " LIMIT 2", parameters).fetchall()
        # Older citations lack chunk IDs; never guess between multiple matching passages.
        return cast(dict[str, Any], rows[0]) if len(rows) == 1 else None


search_repository = SearchRepository()
