from uuid import UUID

from pgvector import Vector
from pgvector.psycopg import register_vector

from app.database import get_connection
from app.engine.chunked.chunker import OKFChunk


class KnowledgeChunksRepository:
    def replace_for_file(
        self,
        file_id: UUID,
        chunks: list[OKFChunk],
        vectors: list[list[float]],
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Every OKF chunk requires one embedding")
        with get_connection() as connection:
            register_vector(connection)
            connection.execute("DELETE FROM knowledge_chunks WHERE file_id = %s", (file_id,))
            for chunk, vector in zip(chunks, vectors, strict=True):
                connection.execute(
                    "INSERT INTO knowledge_chunks "
                    "(file_id, heading, content, source_locations, embedding) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (
                        file_id,
                        chunk.heading,
                        chunk.content,
                        list(chunk.source_locations),
                        Vector(vector),
                    ),
                )


knowledge_chunks_repository = KnowledgeChunksRepository()
