import pytest
from pydantic import SecretStr

from app.chat import service as chat_service
from app.engine.web_search import service as web_search_service


def test_search_web_normalizes_exa_results(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "results": [{
                    "title": "Exa result",
                    "url": "https://example.com/article",
                    "highlights": ["First passage.", "Second passage."],
                    "score": 0.8,
                }]
            }

    seen = {}

    def post(url, **kwargs):
        seen["url"] = url
        seen["kwargs"] = kwargs
        return FakeResponse()

    monkeypatch.setattr(web_search_service.settings, "exa_api_key", SecretStr("test-key"))
    monkeypatch.setattr(web_search_service.httpx, "post", post)

    results = web_search_service.web_search("latest news")

    assert seen["url"].endswith("/search")
    assert seen["kwargs"]["json"]["query"] == "latest news"
    assert results[0]["title"] == "Exa result"
    assert results[0]["url"] == "https://example.com/article"
    assert results[0]["content"] == "First passage.\n\nSecond passage."


def test_search_web_removes_duplicate_titles_and_ellipsis(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "results": [{
                    "title": "Article title",
                    "url": "https://example.com/article",
                    "highlights": ["# Article title", "...", "First passage.\n...\nSecond passage."],
                }]
            }

    monkeypatch.setattr(web_search_service.settings, "exa_api_key", SecretStr("test-key"))
    monkeypatch.setattr(web_search_service.httpx, "post", lambda *args, **kwargs: FakeResponse())

    results = web_search_service.web_search("query")

    assert results[0]["content"] == "First passage.\n\nSecond passage."


def test_search_web_skips_invalid_urls(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [{"url": "javascript:alert(1)", "text": "unsafe"}]}

    monkeypatch.setattr(web_search_service.settings, "exa_api_key", SecretStr("test-key"))
    monkeypatch.setattr(web_search_service.httpx, "post", lambda *args, **kwargs: FakeResponse())

    assert web_search_service.web_search("query") == []


def test_chat_uses_web_search_only_when_enabled(monkeypatch) -> None:
    web_results = [{
        "title": "Public article",
        "heading": "",
        "snippet": "Current information.",
        "content": "Current information.",
        "source_locations": [],
        "score": 0.9,
        "url": "https://example.com/article",
    }]
    seen = []

    def generate(messages, output_type):
        seen.append(output_type)
        if output_type is chat_service.SearchRequest:
            return chat_service.SearchRequest(query="current information")
        return chat_service.ModelAnswer(
            blocks=[{
                "kind": "grounded",
                "text": "Current information.",
                "source_ids": ["source-1"],
            }]
        )

    monkeypatch.setattr(chat_service, "perform_web_search", lambda query: web_results)
    monkeypatch.setattr(chat_service, "generate_structured", generate)

    response = chat_service.answer_from_knowledge("What is current?", "staff", web_search=True)

    assert seen == [chat_service.SearchRequest, chat_service.ModelAnswer]
    assert response.citations[0].url == "https://example.com/article"
    assert response.answer == "Current information. [1]"


def test_chat_can_answer_directly_when_web_search_is_enabled(monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service,
        "generate_structured",
        lambda messages, output_type: chat_service.ModelAnswer(
            blocks=[{"kind": "general", "text": "Stale", "source_ids": []}]
        ),
    )

    response = chat_service.answer_from_knowledge("What is 1 + 1?", "staff", web_search=True)

    assert response.answer == "Stale"
    assert response.citations == []
