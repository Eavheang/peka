import logging

import httpx

from app.config import settings
from app.engine.chunks.chunker import passage_text
from app.engine.chunks.embeddings import EmbeddingError, embed_texts
from app.engine.search.repository import search_repository

logger = logging.getLogger(__name__)


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


def rerank_scores(query: str, texts: list[str]) -> list[float] | None:
    """Cross-encoder relevance of each text to the query, in the given order. None if the reranker fails."""
    try:
        response = httpx.post(
            f"{settings.rerank_base_url.rstrip('/')}/rerank",
            # The model reads 512 tokens per pair; TEI can reject longer pairs unless asked to cut.
            json={"query": query, "texts": texts, "truncate": True},
            timeout=10,
        )
        response.raise_for_status()
        scores = [0.0] * len(texts)
        for rank in response.json():
            scores[rank["index"]] = float(rank["score"])
        return scores
    except (httpx.HTTPError, httpx.InvalidURL, IndexError, KeyError, TypeError, ValueError) as error:
        logger.warning("Reranker failed: %r", error)
        return None


def rerank(query: str, rows: list[dict]) -> list[dict]:
    """Order rows by cross-encoder relevance, keeping the given order if the reranker fails."""
    # Even one row is scored: chat's evidence check reads the score.
    if not rows:
        return rows
    # Same shape the embedder sees: a query can name the document instead of the section.
    scores = rerank_scores(query, [passage_text(row["stem"], row["heading"], row["content"]) for row in rows])
    if scores is None:
        # Hybrid order is still a good answer: a reranker outage must not fail a chat turn.
        return rows
    ranked = sorted(range(len(rows)), key=lambda index: scores[index], reverse=True)
    return [{**rows[index], "rerank_score": scores[index]} for index in ranked]


def search_knowledge(query: str, user_role: str, top_k: int | None = None) -> list[dict]:
    """Best permitted chunks for a query. Without top_k, returns the small set chat prompts use."""
    limit = top_k or settings.rerank_top_k
    vector = embed_query(query)
    # Candidates come from the access-filtered SQL, so the reranker only ever sees permitted rows.
    results = search_repository.search_chunks(
        vector,
        access_levels_for_role(user_role),
        top_k=max(limit, settings.rerank_candidates),
        query_text=query,
    )
    return [
        {
            "chunk_id": str(row["id"]),
            "file_id": str(row["file_id"]),
            "title": row["file_path"].rsplit("/", 1)[-1],
            "heading": row["heading"],
            "snippet": row["content"][:300],
            "content": row["content"],
            "source_locations": row["source_locations"],
            "score": float(row["score"]),
            # None when the reranker did not run, which says nothing about the evidence.
            "rerank_score": row.get("rerank_score"),
        }
        for row in rerank(query, results)[:limit]
    ]
