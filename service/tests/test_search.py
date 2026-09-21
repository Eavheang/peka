from fastapi.testclient import TestClient

from app.engine.search import service as search_service
from app.main import app


def test_staff_cannot_see_confidential(monkeypatch) -> None:
    seen: dict = {}

    class FakeRepo:
        def search_chunks(self, vector, allowed_access_levels, top_k=None):
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
        def search_chunks(self, vector, levels, top_k=None):
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
    assert body[0]["title"] == "policy.pdf"
    assert len(body[0]["snippet"]) == 300
    assert body[0]["score"] == 0.87
    app.dependency_overrides.clear()
