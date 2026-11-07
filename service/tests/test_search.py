import logging

import httpx
import pytest
from fastapi.testclient import TestClient

from app.engine.search import service as search_service
from app.main import app


def candidates(count: int) -> list[dict]:
    """Rows in RRF order, with descending cosine score, as `search_chunks` returns them."""
    return [
        {
            "id": f"00000000-0000-0000-0000-{index:012}",
            "file_id": "00000000-0000-0000-0000-000000000001",
            "stem": "handbook",
            "heading": f"Section {index}",
            "content": f"passage {index}",
            "source_locations": [],
            "score": 0.9 - index / 100,
        }
        for index in range(count)
    ]


class Reranker:
    """Fake TEI: scores a higher index higher unless given a canned reply or error."""

    def __init__(self, reply=None, error=None):
        self.requests, self.reply, self.error = [], reply, error

    def post(self, url, **kwargs):
        self.requests.append((url, kwargs["json"]))
        if self.error:
            raise self.error
        reply = self.reply
        if reply is None:
            reply = [{"index": index, "score": index} for index in range(len(kwargs["json"]["texts"]))]
        return httpx.Response(200, json=reply, request=httpx.Request("POST", url))


@pytest.fixture()
def search(monkeypatch):
    """Fakes the embedder and database. Sets the row count; returns repository calls and setup."""

    def setup(count: int = 30, reranker: Reranker | None = None):
        calls = []

        def search_chunks(vector, levels, top_k=None, query_text=None):
            calls.append({"levels": levels, "top_k": top_k})
            return candidates(min(count, top_k))

        reranker = reranker or Reranker()
        monkeypatch.setattr(search_service, "embed_query", lambda query: [0.0])
        monkeypatch.setattr(search_service.search_repository, "search_chunks", search_chunks)
        monkeypatch.setattr(search_service.search_repository, "file_title", lambda file_id: "handbook.pdf")
        monkeypatch.setattr(search_service.httpx, "post", reranker.post)
        monkeypatch.setattr(search_service.settings, "rerank_base_url", "http://reranker:80/")
        monkeypatch.setattr(search_service.settings, "rerank_candidates", 20)
        monkeypatch.setattr(search_service.settings, "rerank_top_k", 5)
        monkeypatch.setattr(search_service.settings, "search_top_k", 10)
        return calls, reranker

    return setup


def test_chat_default_sends_the_top_reranked_sources(search) -> None:
    calls, reranker = search()

    results = search_service.search_knowledge("what is the leave policy?", "staff")

    # The fake prefers the last candidates, so the order is the reranker's and not RRF's.
    assert [r["heading"] for r in results] == [f"Section {i}" for i in (19, 18, 17, 16, 15)]
    assert calls == [{"levels": ("general",), "top_k": 20}]
    url, body = reranker.requests[0]
    assert url == "http://reranker:80/rerank"
    assert body["query"] == "what is the leave policy?"
    assert body["truncate"] is True
    assert len(body["texts"]) == 20
    assert body["texts"][3] == "Document: handbook\nSection: Section 3\n\npassage 3"


def test_score_stays_cosine_similarity_after_reranking(search) -> None:
    search()

    results = search_service.search_knowledge("query", "staff")

    assert [r["score"] for r in results] == pytest.approx([0.9 - i / 100 for i in (19, 18, 17, 16, 15)])


def test_search_route_can_still_return_ten_results(search) -> None:
    from app.auth.routes import authenticated

    calls, _ = search()
    app.dependency_overrides[authenticated] = lambda: {"id": "u", "role": "admin"}
    try:
        response = TestClient(app).post("/search", json={"query": "policy"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(response.json()) == 10
    assert response.json()[0]["heading"] == "Section 19"
    assert calls == [{"levels": ("general", "confidential"), "top_k": 20}]


def test_candidate_pool_is_never_smaller_than_the_requested_count(search) -> None:
    calls, _ = search()

    assert len(search_service.search_knowledge("query", "staff", top_k=25)) == 25
    assert calls[0]["top_k"] == 25


@pytest.mark.parametrize(
    "reranker",
    [
        Reranker(error=httpx.ConnectError("connection refused")),
        Reranker(error=httpx.ReadTimeout("too slow")),
        Reranker(error=httpx.InvalidURL("bad port")),
        Reranker(reply={"error": "Model is overloaded"}),
        Reranker(reply=[{"index": 0}]),
        Reranker(reply=[{"index": 99, "score": float(i)} for i in range(20)]),
        Reranker(reply=[{"index": float(i), "score": float(i)} for i in range(20)]),
    ],
)
def test_reranker_failure_keeps_rrf_order_at_the_normal_count(search, caplog, reranker) -> None:
    search(reranker=reranker)

    with caplog.at_level(logging.WARNING, logger=search_service.logger.name):
        results = search_service.search_knowledge("query", "staff")

    assert [r["heading"] for r in results] == [f"Section {i}" for i in range(5)]
    assert "Reranker failed" in caplog.text


def test_reranker_error_status_keeps_rrf_order(search, monkeypatch) -> None:
    search()
    monkeypatch.setattr(
        search_service.httpx, "post",
        lambda url, **kwargs: httpx.Response(429, request=httpx.Request("POST", url)),
    )

    results = search_service.search_knowledge("query", "staff")

    assert [r["heading"] for r in results] == [f"Section {i}" for i in range(5)]


@pytest.mark.parametrize("count", [0, 1])
def test_too_few_candidates_skip_the_reranker(search, count) -> None:
    _, reranker = search(count=count)

    assert len(search_service.search_knowledge("query", "staff")) == count
    assert reranker.requests == []


def test_staff_cannot_see_confidential(monkeypatch) -> None:
    seen: dict = {}

    class FakeRepo:
        def search_chunks(self, vector, allowed_access_levels, top_k=None, query_text=None):
            seen["levels"] = allowed_access_levels
            return []

        def file_title(self, file_id):
            return "doc.pdf"

    monkeypatch.setattr(search_service.search_repository, "search_chunks", FakeRepo().search_chunks)
    assert search_service.access_levels_for_role("staff") == ("general",)
    assert search_service.access_levels_for_role("admin") == ("general", "confidential")
    assert search_service.access_levels_for_role("senior") == ("general", "confidential")


def test_search_endpoint_requires_auth(client: TestClient) -> None:
    response = client.post("/search", json={"query": "policy"})
    assert response.status_code == 403 or response.status_code == 401


def test_search_returns_results_for_authenticated_user(monkeypatch) -> None:
    monkeypatch.setattr(search_service, "embed_query", lambda query: [0.0] * 1024)

    class FakeRepo:
        def search_chunks(self, vector, levels, top_k=None, query_text=None):
            return [
                {
                    "id": "00000000-0000-0000-0000-000000000002",
                    "file_id": "00000000-0000-0000-0000-000000000001",
                    "heading": "Intro",
                    "content": "x" * 400,
                    "source_locations": [{"page": 2}],
                    "score": 0.87,
                }
            ]

        def file_title(self, file_id):
            return "policy.pdf"

    fake = FakeRepo()
    monkeypatch.setattr(search_service.search_repository, "search_chunks", fake.search_chunks)
    monkeypatch.setattr(search_service.search_repository, "file_title", fake.file_title)
    from app.auth.routes import authenticated

    # bypass DB by overriding dependency directly
    token_user = {"id": "u", "role": "admin"}
    app.dependency_overrides[authenticated] = lambda: token_user
    client = TestClient(app)
    response = client.post("/search", json={"query": "what is the policy"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["file_id"] == "00000000-0000-0000-0000-000000000001"
    assert body[0]["title"] == "policy.pdf"
    assert len(body[0]["snippet"]) == 300
    assert body[0]["score"] == 0.87
    app.dependency_overrides.clear()
