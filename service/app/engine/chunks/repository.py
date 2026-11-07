from uuid import UUID

from pgvector import Vector
from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb

from app.database import get_connection
from app.engine.chunks.chunker import OKFChunk


class KnowledgeChunksRepository:
    def swap_active_set(
        self,
        file_id: UUID,
        chunks: list[OKFChunk],
        vectors: list[list[float]],
    ) -> None:
        """Build a new set and flip it active atomically; readers never see partial re-indexes."""
        if len(chunks) != len(vectors):
            raise ValueError("Every OKF chunk requires one embedding")
        if not chunks:
            raise ValueError("Refusing to activate an empty chunk set")
        with get_connection() as connection:
            register_vector(connection)
            set_id = connection.execute(
                "INSERT INTO chunk_sets (file_id, status) VALUES (%s, 'building') RETURNING id",
                (file_id,),
            ).fetchone()["id"]
            for chunk, vector in zip(chunks, vectors, strict=True):
                connection.execute(
                    "INSERT INTO knowledge_chunks "
                    "(file_id, file_path, chunk_set_id, heading, content, source_locations, embedding) "
                    "VALUES (%s, (SELECT path FROM files WHERE id = %s), %s, %s, %s, %s, %s)",
                    (
                        file_id,
                        file_id,
                        set_id,
                        chunk.heading,
                        chunk.content,
                        Jsonb(list(chunk.source_locations)),
                        Vector(vector),
                    ),
                )
            connection.execute(
                "UPDATE chunk_sets SET centroid = "
                "(SELECT avg(embedding) FROM knowledge_chunks WHERE chunk_set_id = %s) WHERE id = %s",
                (set_id, set_id),
            )
            superseded = [
                row["id"]
                for row in connection.execute(
                    "UPDATE chunk_sets SET status = 'superseded' "
                    "WHERE file_id = %s AND status = 'active' RETURNING id",
                    (file_id,),
                ).fetchall()
            ]
            if superseded:
                connection.execute(
                    "DELETE FROM knowledge_chunks WHERE chunk_set_id = ANY(%s)",
                    (superseded,),
                )
            connection.execute(
                "UPDATE chunk_sets SET status = 'active' WHERE id = %s",
                (set_id,),
            )


knowledge_chunks_repository = KnowledgeChunksRepository()
