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
        query_text: str | None = None,
    ) -> list[dict[str, Any]]:
        """Hybrid search over active chunk sets, permission-filtered in SQL.

        Vector and keyword (full-text, any query term) rankings are merged with reciprocal rank
        fusion: embeddings alone miss exact lookups such as one metric row in a table. One chunk
        is kept per file stem + heading, so the .pdf/.docx/.md copies of one document don't fill
        every slot with the same section.
        """
        limit = top_k or settings.search_top_k
        with get_connection() as connection:
            register_vector(connection)
            rows = connection.execute(
                # ponytail: tsvector computed per query; add a generated column + GIN index if the corpus grows.
                r"""
                WITH allowed AS (
                    SELECT kc.*, regexp_replace(f.path, '^.*/|\.[^./]*$', '', 'g') AS stem,
                        to_tsvector('english', regexp_replace(f.path, '[^[:alnum:]]+', ' ', 'g')
                            || ' ' || kc.heading || ' ' || kc.content) AS words
                    FROM knowledge_chunks kc
                    JOIN chunk_sets cs ON cs.id = kc.chunk_set_id AND cs.status = 'active'
                    JOIN files f ON f.id = kc.file_id
                    WHERE f.access_level = ANY(%(levels)s)
                ), terms AS (
                    SELECT replace(plainto_tsquery('english', coalesce(%(text)s, ''))::text, '&', '|')::tsquery AS q
                ), ranked AS (
                    (SELECT id, row_number() OVER (ORDER BY embedding <=> %(vector)s) AS rank FROM allowed
                     WHERE 1 - (embedding <=> %(vector)s) >= %(floor)s
                     ORDER BY embedding <=> %(vector)s LIMIT %(pool)s)
                    UNION ALL
                    (SELECT id, row_number() OVER (ORDER BY ts_rank_cd(words, q) DESC) AS rank
                     FROM allowed, terms WHERE words @@ q
                     ORDER BY ts_rank_cd(words, q) DESC LIMIT %(pool)s)
                ), fused AS (
                    SELECT DISTINCT ON (a.stem, a.heading) a.id, a.file_id, a.heading, a.content,
                        a.source_locations, 1 - (a.embedding <=> %(vector)s) AS score, r.rrf
                    FROM (SELECT id, sum(1.0 / (60 + rank)) AS rrf FROM ranked GROUP BY id) r
                    JOIN allowed a ON a.id = r.id
                    ORDER BY a.stem, a.heading, r.rrf DESC
                )
                SELECT id, file_id, heading, content, source_locations, score
                FROM fused ORDER BY rrf DESC LIMIT %(limit)s
                """,
                {
                    "levels": list(allowed_access_levels),
                    "text": query_text,
                    "vector": Vector(query_vector),
                    "floor": settings.search_similarity_floor,
                    "pool": limit * 4,
                    "limit": limit,
                },
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
