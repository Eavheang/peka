import httpx

from app.config import settings
from app.engine.chunks.chunker import OKFChunk


class EmbeddingError(RuntimeError):
    pass


def embed_texts(
    texts: list[str], *, timeout: float, error_message: str
) -> list[list[float]]:
    try:
        response = httpx.post(
            f"{settings.embedding_base_url.rstrip('/')}/embeddings",
            json={
                "input": texts,
                "model": settings.embedding_model,
                "encoding_format": "float",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = sorted(response.json()["data"], key=lambda item: item["index"])
        vectors = [item["embedding"] for item in data]
    except (httpx.HTTPError, IndexError, KeyError, TypeError, ValueError) as error:
        raise EmbeddingError(error_message) from error
    if len(vectors) != len(texts) or any(
        not isinstance(vector, list) or len(vector) != settings.embedding_dimensions
        for vector in vectors
    ):
        raise EmbeddingError("Embedding response has invalid dimensions")
    return vectors


def embed_chunks(chunks: list[OKFChunk]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), settings.embedding_batch_size):
        batch = chunks[start : start + settings.embedding_batch_size]
        batch_vectors = embed_texts(
            [chunk.embedding_text for chunk in batch],
            timeout=300,
            error_message="Unable to generate BGE-M3 embeddings",
        )
        vectors.extend(batch_vectors)
    return vectors
