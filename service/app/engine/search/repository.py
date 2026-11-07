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
        top_k: int,
        query_text: str | None = None,
    ) -> list[dict[str, Any]]:
        """Hybrid search over active chunk sets, permission-filtered in SQL.

        Vector and keyword (full-text, any query term) rankings are merged with reciprocal rank
        fusion: embeddings alone miss exact lookups such as one metric row in a table. Only the
        best-ranked format of a file stem is kept, so the .pdf/.docx/.md copies of one document
        can't fill every slot or mix their conflicting figures.
        """
        with get_connection() as connection:
            register_vector(connection)
            rows = connection.execute(
                # ponytail: exact vector scan, about 150-190 ms at 50,000 chunks. See migration 021 before adding HNSW.
                r"""
                WITH terms AS (
                    SELECT replace(plainto_tsquery('english', coalesce(%(text)s, ''))::text, '&', '|')::tsquery AS q
                ), matches AS (  -- not access-filtered: the keyword ranking below must filter these rows
                    SELECT id FROM knowledge_chunks WHERE search_words @@ (SELECT q FROM terms)
                    UNION
                    SELECT kc.id FROM knowledge_chunks kc JOIN files f ON f.id = kc.file_id
                    WHERE f.path_words @@ (SELECT q FROM terms)
                ), ranked AS (
                    (SELECT kc.id, row_number() OVER (ORDER BY kc.embedding <=> %(vector)s) AS rank
                     FROM knowledge_chunks kc
                     JOIN chunk_sets cs ON cs.id = kc.chunk_set_id AND cs.status = 'active'
                     JOIN files f ON f.id = kc.file_id
                     WHERE f.access_level = ANY(%(levels)s)
                        AND 1 - (kc.embedding <=> %(vector)s) >= %(floor)s
                     ORDER BY kc.embedding <=> %(vector)s LIMIT %(pool)s)
                    UNION ALL
                    (SELECT kc.id, row_number() OVER (
                            ORDER BY ts_rank_cd(f.path_words || kc.search_words, (SELECT q FROM terms)) DESC
                        ) AS rank
                     FROM matches m
                     JOIN knowledge_chunks kc ON kc.id = m.id
                     JOIN chunk_sets cs ON cs.id = kc.chunk_set_id AND cs.status = 'active'
                     JOIN files f ON f.id = kc.file_id
                     WHERE f.access_level = ANY(%(levels)s)
                     ORDER BY rank LIMIT %(pool)s)
                ), fused AS (
                    SELECT kc.id, kc.file_id, regexp_replace(f.path, '^.*/', '') AS title,
                        s.stem,
                        kc.heading, kc.content, kc.source_locations,
                        1 - (kc.embedding <=> %(vector)s) AS score, r.rrf,
                        first_value(kc.file_id) OVER (
                            PARTITION BY s.stem ORDER BY r.rrf DESC
                        ) AS best_file
                    FROM (SELECT id, sum(1.0 / (60 + rank)) AS rrf FROM ranked GROUP BY id) r
                    JOIN knowledge_chunks kc ON kc.id = r.id
                    JOIN files f ON f.id = kc.file_id
                    CROSS JOIN LATERAL (SELECT regexp_replace(f.path, '^.*/|\.[^./]*$', '', 'g') AS stem) s
                )
                SELECT id, file_id, title, stem, heading, content, source_locations, score
                FROM fused WHERE file_id = best_file ORDER BY rrf DESC LIMIT %(limit)s
                """,
                {
                    "levels": list(allowed_access_levels),
                    "text": query_text,
                    "vector": Vector(query_vector),
                    "floor": settings.search_similarity_floor,
                    "pool": top_k * 4,
                    "limit": top_k,
                },
            ).fetchall()
            return cast(list[dict[str, Any]], rows)

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
