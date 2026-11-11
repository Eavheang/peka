from typing import Any, cast
from uuid import UUID

from pgvector import Vector
from pgvector.psycopg import register_vector

from app.config import settings
from app.database import get_connection


# Each search keeps its top_k * 4 best rows after collapsing copies, so read enough for 6 formats of each.
_CANDIDATES_PER_RESULT = 24
# Files with the same name count as one document at this centroid similarity. Real format copies
# measured 0.895 or above, and 95% of different documents 0.845 or below.
_SAME_DOCUMENT_SIMILARITY = 0.85


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
        best-ranked format of a document is kept, so the .pdf/.docx/.md copies of one document
        can't fill every slot or mix their conflicting figures.
        """
        with get_connection() as connection:
            register_vector(connection)
            # Without iterative scan, access filtering after the index scan could leave too few rows.
            connection.execute("SET LOCAL hnsw.iterative_scan = strict_order")
            connection.execute("SELECT set_config('hnsw.ef_search', '1000', true)")
            rows = connection.execute(
                r"""
                WITH terms AS (
                    SELECT replace(plainto_tsquery('english', coalesce(%(text)s, ''))::text, '&', '|')::tsquery AS q
                ), permitted AS NOT MATERIALIZED (
                    SELECT kc.id, kc.embedding, kc.search_words
                    FROM knowledge_chunks kc
                    JOIN chunk_sets cs ON cs.id = kc.chunk_set_id AND cs.status = 'active'
                    JOIN files f ON f.id = kc.file_id
                    WHERE f.access_level = ANY(%(levels)s)
                ), candidates AS (
                    (SELECT 'vector' AS branch, id, row_number() OVER (ORDER BY embedding <=> %(vector)s) AS rank
                     FROM permitted WHERE 1 - (embedding <=> %(vector)s) >= %(floor)s
                     ORDER BY embedding <=> %(vector)s LIMIT %(candidates)s)
                    UNION ALL
                    (SELECT 'keyword', id, row_number() OVER (
                            ORDER BY ts_rank_cd(search_words, (SELECT q FROM terms)) DESC
                        )
                     FROM permitted WHERE search_words @@ (SELECT q FROM terms)
                     ORDER BY 3 LIMIT %(candidates)s)
                ), documents AS (
                    SELECT r.id, kc.file_id, s.stem, cs.centroid,
                        first_value(kc.file_id) OVER best AS best_file,
                        first_value(cs.centroid) OVER best AS best_centroid
                    FROM (SELECT id, sum(1.0 / (60 + rank)) AS rrf FROM candidates GROUP BY id) r
                    JOIN knowledge_chunks kc ON kc.id = r.id
                    JOIN chunk_sets cs ON cs.id = kc.chunk_set_id
                    CROSS JOIN LATERAL (
                        SELECT regexp_replace(kc.file_path, '^.*/|\.[^./]*$', '', 'g') AS stem
                    ) s
                    WINDOW best AS (PARTITION BY lower(s.stem) ORDER BY r.rrf DESC)
                ), ranked AS (  -- ranks count after collapsing, so a document's copies don't push others down
                    SELECT c.id, row_number() OVER (PARTITION BY c.branch ORDER BY c.rank) AS rank
                    FROM candidates c JOIN documents d ON d.id = c.id
                    WHERE d.file_id = d.best_file OR 1 - (d.centroid <=> d.best_centroid) < %(same_document)s
                )
                SELECT kc.id, kc.file_id, kc.file_path, d.stem,
                    kc.heading, kc.content, kc.source_locations, 1 - (kc.embedding <=> %(vector)s) AS score
                FROM (SELECT id, sum(1.0 / (60 + rank)) AS rrf FROM ranked WHERE rank <= %(pool)s GROUP BY id) r
                JOIN knowledge_chunks kc ON kc.id = r.id
                JOIN documents d ON d.id = r.id
                ORDER BY r.rrf DESC LIMIT %(limit)s
                """,
                {
                    "levels": list(allowed_access_levels),
                    "text": query_text,
                    "vector": Vector(query_vector),
                    "floor": settings.search_similarity_floor,
                    "pool": top_k * 4,
                    "candidates": top_k * _CANDIDATES_PER_RESULT,
                    "same_document": _SAME_DOCUMENT_SIMILARITY,
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
            "JOIN chunk_sets cs ON cs.id = kc.chunk_set_id "
            "JOIN files f ON f.id = kc.file_id "
            "WHERE f.access_level = ANY(%s) "
            "AND regexp_replace(f.path, '^.*/', '') = %s AND kc.heading = %s"
        )
        parameters: list[Any] = [list(allowed_access_levels), title, heading]
        if chunk_id is not None:  # A cited chunk outlives re-indexing in its superseded set.
            query += " AND kc.id = %s"
            parameters.append(chunk_id)
        else:
            query += " AND cs.status = 'active'"
        with get_connection() as connection:
            rows = connection.execute(query + " LIMIT 2", parameters).fetchall()
        # Older citations lack chunk IDs; never guess between multiple matching passages.
        return cast(dict[str, Any], rows[0]) if len(rows) == 1 else None


search_repository = SearchRepository()
