from dataclasses import dataclass

from app.engine.chunks.embeddings import EmbeddingError, embed_texts
from app.engine.search.repository import search_repository


def embed_query(query: str) -> list[float]:
    try:
        return embed_texts(
            [query],
            timeout=60,
            error_message="Unable to embed query",
        )[0]
    except (EmbeddingError, IndexError) as error:
        raise RuntimeError(str(error)) from error


ROLE_ACCESS_LEVELS = {
    "admin": ("general", "confidential"),
    "senior": ("general", "confidential"),
    "staff": ("general",),
}

def access_levels_for_role(role: str) -> tuple[str, ...]:
    return ROLE_ACCESS_LEVELS.get(role, ("general",))


@dataclass(frozen=True)
class RetrievalResult:
    """ACL-filtered vector hits plus the best cosine score among them."""

    hits: list[dict]
    top_score: float | None


def search_knowledge(query: str, user_role: str) -> RetrievalResult:
    vector = embed_query(query)
    results = search_repository.search_chunks(vector, access_levels_for_role(user_role))
    hits = [
        {
            "chunk_id": str(row["id"]),
            "file_id": str(row["file_id"]),
            "title": search_repository.file_title(row["file_id"]),
            "heading": row["heading"],
            "snippet": row["content"][:300],
            "content": row["content"],
            "source_locations": row["source_locations"],
            "score": float(row["score"]),
        }
        for row in results
    ]
    top_score = max((hit["score"] for hit in hits), default=None)
    return RetrievalResult(hits=hits, top_score=top_score)
