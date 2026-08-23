from app.engine.search.repository import search_repository

import httpx
from app.config import settings


def embed_query(query: str) -> list[float]:
    try:
        response = httpx.post(
            f"{settings.embedding_base_url.rstrip('/')}/embeddings",
            json={"input": [query], "model": settings.embedding_model, "encoding_format": "float"},
            timeout=60,
        )
        response.raise_for_status()
        vector = sorted(response.json()["data"], key=lambda item: item["index"])[0]["embedding"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
        raise RuntimeError("Unable to embed query") from error
    if not isinstance(vector, list) or len(vector) != settings.embedding_dimensions:
        raise RuntimeError("Query embedding has invalid dimensions")
    return vector


ROLE_ACCESS_LEVELS = {
    "admin": ("general", "confidential"),
    "senior": ("general", "confidential"),
    "staff": ("general",),
}

def access_levels_for_role(role: str) -> tuple[str, ...]:
    return ROLE_ACCESS_LEVELS.get(role, ("general",))


def search_knowledge(query: str, user_role: str) -> list[dict]:
    vector = embed_query(query)
    results = search_repository.search_chunks(vector, access_levels_for_role(user_role))
    return [
        {
            "title": search_repository.file_title(row["file_id"]),
            "heading": row["heading"],
            "snippet": row["content"][:300],
            "source_locations": row["source_locations"],
            "score": float(row["score"]),
        }
        for row in results
    ]
