from fastapi.testclient import TestClient

from app.chat import service as chat_service
from app.auth.routes import authenticated
from app.main import app


def _override_admin() -> None:
    app.dependency_overrides[authenticated] = lambda: {"id": "u1", "role": "admin"}


def test_refusal_makes_zero_llm_calls(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(chat_service, "search_knowledge", lambda query, role: [])
    monkeypatch.setattr(chat_service, "chat_completion", lambda messages: calls.append(messages))

    response = chat_service.answer_from_knowledge("anything", "staff")

    assert response.refused is True
    assert response.citations == []
    assert "cannot answer" in response.answer.lower()
    assert calls == []


def test_grounded_answer_carries_citations(monkeypatch) -> None:
    results = [
        {
            "title": "policy.pdf",
            "heading": "Refund rules",
            "snippet": "Refunds take 14 days.",
            "source_locations": [{"page": 3}],
            "score": 0.9,
        },
        {
            "title": "handbook.pptx",
            "heading": "Slide notes",
            "snippet": "Speaker note text.",
            "source_locations": [{"slide": 5}, {"slide": 6}],
            "score": 0.8,
        },
    ]
    seen: dict = {}

    def fake_completion(messages):
        seen["prompt"] = messages[1]["content"]
        return "Refunds take 14 days [1]."

    monkeypatch.setattr(chat_service, "search_knowledge", lambda query, role: results)
    monkeypatch.setattr(chat_service, "chat_completion", fake_completion)

    response = chat_service.answer_from_knowledge("refund time?", "admin")

    assert response.refused is False
    assert "[1]" in seen["prompt"] and "handbook.pptx" in seen["prompt"]
    assert len(response.citations) == 2
    assert response.citations[0].title == "policy.pdf"
    assert response.citations[0].page == 3
    assert response.citations[1].source_locations[0] == {"slide": 5}


def test_chat_endpoint_requires_auth(client: TestClient) -> None:
    response = client.post("/chat", json={"query": "hello"})
    assert response.status_code in (401, 403)


def test_chat_endpoint_returns_answer(monkeypatch) -> None:
    from app.chat import routes as chat_routes
    monkeypatch.setattr(
        chat_routes,
        "answer_from_knowledge",
        lambda query, role: chat_service.ChatResponse(answer="ok [1]", refused=False, citations=[]),
    )
    _override_admin()
    try:
        client = TestClient(app)
        response = client.post("/chat", json={"query": "q"})
        assert response.status_code == 200
        body = response.json()
        assert body == {"answer": "ok [1]", "refused": False, "citations": []}
    finally:
        app.dependency_overrides.clear()
