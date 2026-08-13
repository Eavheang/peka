import httpx

from app.config import settings
from app.engine.chunks.chunker import OKFChunk


class EmbeddingError(RuntimeError):
    pass


def embed_chunks(chunks: list[OKFChunk]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), settings.embedding_batch_size):
        batch = chunks[start : start + settings.embedding_batch_size]
        try:
            response = httpx.post(
                f"{settings.embedding_base_url.rstrip('/')}/embeddings",
                json={
                    "input": [chunk.embedding_text for chunk in batch],
                    "model": settings.embedding_model,
                    "encoding_format": "float",
                },
                timeout=300,
            )
            response.raise_for_status()
            data = sorted(response.json()["data"], key=lambda item: item["index"])
            batch_vectors = [item["embedding"] for item in data]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            raise EmbeddingError("Unable to generate BGE-M3 embeddings") from error
        if len(batch_vectors) != len(batch) or any(
            not isinstance(vector, list) or len(vector) != settings.embedding_dimensions
            for vector in batch_vectors
        ):
            raise EmbeddingError("Embedding response has invalid dimensions")
        vectors.extend(batch_vectors)
    return vectors
