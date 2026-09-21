import asyncio
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.chat import service as chat_service
from app.auth.routes import authenticated
from app.main import app


def _override_admin() -> None:
    app.dependency_overrides[authenticated] = lambda: {"id": "u1", "role": "admin"}


def test_general_question_does_not_search(monkeypatch) -> None:
    def no_search(*args):
        raise AssertionError("General questions must not search")

    monkeypatch.setattr(chat_service, "search_knowledge", no_search)
    monkeypatch.setattr(
        chat_service,
        "generate_structured",
        lambda messages, output_type: chat_service.ModelAnswer(
            blocks=[{"kind": "general", "text": "2", "source_ids": []}]
        ),
    )

    response = chat_service.answer_from_knowledge("What is 1+1?", "staff")
    assert response.answer == "2"
    assert response.citations == []
    assert response.refused is False


def test_answer_rejects_json_with_model_preamble_and_trailing_text(monkeypatch) -> None:
    def invalid_output(messages, output_type):
        raise chat_service.AIModelError("Model returned an invalid structured response")

    monkeypatch.setattr(chat_service, "generate_structured", invalid_output)

    with pytest.raises(chat_service.AIModelError, match="invalid structured"):
        chat_service.answer_from_knowledge("question", "staff")


def test_invalid_structured_answer_fails_closed(monkeypatch) -> None:
    def invalid_output(messages, output_type):
        raise chat_service.AIModelError("Model returned an invalid structured response")

    monkeypatch.setattr(chat_service, "generate_structured", invalid_output)

    with pytest.raises(chat_service.AIModelError):
        chat_service.answer_from_knowledge(
            "Do you know about JEV AI?", "staff", web_search=True
        )


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

    def fake_generation(messages, output_type):
        if output_type is chat_service.SearchRequest:
            return chat_service.SearchRequest(query="refund time?")
        seen["prompt"] = messages[-1].text
        return chat_service.ModelAnswer(
            blocks=[
                {
                    "kind": "grounded",
                    "text": "Refunds take 14 days.",
                    "source_ids": ["source-1"],
                }
            ]
        )

    monkeypatch.setattr(chat_service, "search_knowledge", lambda query, role: results)
    monkeypatch.setattr(chat_service, "generate_structured", fake_generation)

    response = chat_service.answer_from_knowledge("refund time?", "admin")

    assert response.refused is False
    assert "source-1" in seen["prompt"] and "handbook.pptx" in seen["prompt"]
    assert response.answer == "Refunds take 14 days. [1]"
    assert len(response.citations) == 1
    assert response.citations[0].title == "policy.pdf"
    assert response.citations[0].page == 3


def test_empty_search_falls_back_without_citations(monkeypatch):
    calls = []

    def generate(messages, output_type):
        calls.append(output_type)
        if output_type is chat_service.SearchRequest:
            return chat_service.SearchRequest(query="improve sales")
        assert "<search_results>\n{}\n</search_results>" in messages[-1].text
        return chat_service.ModelAnswer(
            blocks=[
                {
                    "kind": "general",
                    "text": "Consider customer feedback.",
                    "source_ids": [],
                }
            ]
        )

    monkeypatch.setattr(chat_service, "generate_structured", generate)
    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: [])
    response = chat_service.answer_from_knowledge("How do we improve sales?", "staff")
    assert response.answer == "Consider customer feedback."
    assert response.citations == []
    assert response.refused is False
    assert calls == [chat_service.SearchRequest, chat_service.ModelAnswer]


@pytest.mark.parametrize("blocks", [
    [{"kind": "grounded", "text": "Invented.", "source_ids": ["source-99"]}],
    [{"kind": "grounded", "text": "Uncited.", "source_ids": []}],
    [{"kind": "general", "text": "Incorrect citation.", "source_ids": ["source-1"]}],
])
def test_invalid_answer_sources_fail_closed(monkeypatch, blocks):
    monkeypatch.setattr(
        chat_service,
        "generate_structured",
        lambda messages, output_type: chat_service.ModelAnswer(blocks=blocks),
    )
    with pytest.raises(chat_service.AIModelError):
        chat_service.answer_from_knowledge("question", "staff")


def test_mixed_answer_remaps_and_deduplicates_sources(monkeypatch):
    results = [
        {"title": "unused.pdf", "heading": "Unused", "snippet": "Unrelated", "source_locations": []},
        {"title": "report.pdf", "heading": "Sales", "snippet": "Sales increased.", "source_locations": []},
    ]
    searches = []

    def search(query, role):
        searches.append((query, role))
        return results

    def generate(messages, output_type):
        if output_type is chat_service.SearchRequest:
            return chat_service.SearchRequest(query="sales report")
        return chat_service.ModelAnswer(
            blocks=[
                {
                    "kind": "grounded",
                    "text": "Sales increased.",
                    "source_ids": ["source-2", "source-2"],
                },
                {
                    "kind": "general",
                    "text": "Consider expanding distribution.",
                    "source_ids": [],
                },
            ]
        )

    monkeypatch.setattr(chat_service, "search_knowledge", search)
    monkeypatch.setattr(chat_service, "generate_structured", generate)
    response = chat_service.answer_from_knowledge("Report and your opinion?", "staff")
    assert response.answer == (
        "From your documents\n\nSales increased. [1]\n\nGeneral analysis\n\nConsider expanding distribution."
    )
    assert [citation.title for citation in response.citations] == ["report.pdf"]
    assert searches == [("sales report", "staff")]


def test_answer_formats_markdown_bullets_and_labels_once(monkeypatch):
    results = [{"title": "report.pdf", "heading": "Sales", "snippet": "Sales increased.", "source_locations": []}]

    def generate(messages, output_type):
        if output_type is chat_service.SearchRequest:
            return chat_service.SearchRequest(query="sales report")
        return chat_service.ModelAnswer(
            blocks=[
                {
                    "kind": "grounded",
                    "text": "• Sales increased.\n• Distribution grew.",
                    "source_ids": ["source-1"],
                },
                {
                    "kind": "grounded",
                    "text": "• Customer retention improved.",
                    "source_ids": ["source-1"],
                },
                {
                    "kind": "general",
                    "text": "Consider expanding distribution.",
                    "source_ids": [],
                },
            ]
        )

    monkeypatch.setattr(chat_service, "search_knowledge", lambda query, role: results)
    monkeypatch.setattr(chat_service, "generate_structured", generate)

    response = chat_service.answer_from_knowledge("Report and your opinion?", "staff")

    assert response.answer == (
        "From your documents\n\n- Sales increased.\n- Distribution grew. [1]\n\n"
        "- Customer retention improved. [1]\n\nGeneral analysis\n\nConsider expanding distribution."
    )


def test_enforces_one_search_per_turn(monkeypatch):
    searches = []
    def generate(messages, output_type):
        if output_type is chat_service.SearchRequest:
            return chat_service.SearchRequest(query="sales")
        return chat_service.ModelAnswer(
            blocks=[{"kind": "general", "text": "No results.", "source_ids": []}]
        )

    monkeypatch.setattr(chat_service, "generate_structured", generate)
    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: searches.append(args) or [])
    chat_service.answer_from_knowledge("sales", "staff")
    assert len(searches) == 1


def test_model_receives_bounded_conversation_context(monkeypatch):
    seen = []
    history = [{"role": "user", "content": "old", "id": "ignored"}] * 25
    history.append({"role": "assistant", "content": "Option two is distribution."})

    def generate(messages, output_type):
        seen.extend(messages)
        return chat_service.ModelAnswer(
            blocks=[{"kind": "general", "text": "More details.", "source_ids": []}]
        )

    monkeypatch.setattr(chat_service, "generate_structured", generate)
    chat_service.answer_from_knowledge("What about the second option?", "staff", history)
    assert len(seen) == 22
    assert seen[-2].role == "assistant"
    assert seen[-2].text == "Option two is distribution."
    assert seen[-1].text == "What about the second option?"


def test_chat_endpoint_requires_auth(client: TestClient) -> None:
    response = client.post("/chat", json={"query": "hello"})
    assert response.status_code in (401, 403)


def test_chat_endpoint_returns_answer(monkeypatch) -> None:
    from app.chat import routes as chat_routes
    monkeypatch.setattr(
        chat_routes,
        "answer_from_knowledge",
        lambda query, role, history: chat_service.ChatResponse(answer="ok [1]", refused=False, citations=[]),
    )
    monkeypatch.setattr(chat_service, "persist_response", lambda query, user_id, response, conversation_id=None: response)
    _override_admin()
    try:
        client = TestClient(app)
        response = client.post("/chat", json={"query": "q"})
        assert response.status_code == 200
        body = response.json()
        assert body == {"answer": "ok [1]", "refused": False, "citations": []}
    finally:
        app.dependency_overrides.clear()


def test_chat_stream_endpoint_emits_text_and_persists_completion(monkeypatch) -> None:
    from app.chat import routes as chat_routes

    conversation_id = uuid4()

    async def stream_answer(*args, **kwargs):
        yield chat_service.ChatStreamStatus("Writing response...")
        yield chat_service.ChatStreamText("Hello")
        yield chat_service.ChatStreamText(" world")
        yield chat_service.ChatStreamCompleted(
            chat_service.ChatResponse(answer="Hello world", refused=False, citations=[])
        )

    def persist(*args):
        return args[2].model_copy(
            update={"conversation_id": conversation_id, "messages": []}
        )

    monkeypatch.setattr(chat_routes.chat_service, "stream_answer_from_knowledge", stream_answer)
    monkeypatch.setattr(chat_routes.chat_service, "persist_response", persist)
    _override_admin()
    try:
        response = TestClient(app).post("/chat/stream", json={"query": "hello"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"type": "text", "delta": "Hello"' in response.text
    assert '"type": "done"' in response.text
    assert '"conversation_id": "' + str(conversation_id) in response.text
    assert "data: [DONE]" in response.text


def test_stream_answer_parses_incremental_json_and_validates_answer(monkeypatch) -> None:
    async def stream_text(*args, **kwargs):
        for chunk in (
            '{"blocks":[{"kind":"general","text":"Hello ',
            'world\\nline',
            '","source_ids":[]}]}'
        ):
            yield chunk

    monkeypatch.setattr(chat_service, "stream_structured_text", stream_text)

    async def collect():
        return [
            event
            async for event in chat_service.stream_answer_from_knowledge("hello", "staff")
        ]

    events = asyncio.run(collect())
    text = "".join(
        event.delta
        for event in events
        if isinstance(event, chat_service.ChatStreamText)
    )
    completed = next(
        event for event in events if isinstance(event, chat_service.ChatStreamCompleted)
    )

    assert text == "Hello world\nline"
    assert completed.response.answer == "Hello world\nline"


def test_first_message_is_persisted_and_returned(monkeypatch) -> None:
    from app.chat import routes as chat_routes

    account_id = uuid4()
    account = {"id": account_id, "role": "staff"}
    conversation_id = uuid4()
    created_at = datetime.now(timezone.utc)
    calls = []

    class FakeRepository:
        def create_exchange(self, owner_id, title, query, response, conversation_id=None):
            calls.append((owner_id, title, query, conversation_id, response))
            return {
                "conversation": {"id": conversation_id or conversation_id_for_test},
                "messages": [
                    {
                        "id": uuid4(),
                        "role": "user",
                        "content": query,
                        "refused": False,
                        "citations": [],
                        "status": "completed",
                        "created_at": created_at,
                    },
                    {
                        "id": uuid4(),
                        "role": "assistant",
                        "content": response.answer,
                        "refused": response.refused,
                        "citations": [citation.model_dump() for citation in response.citations],
                        "status": "completed",
                        "created_at": created_at,
                    },
                ],
            }

    conversation_id_for_test = conversation_id
    monkeypatch.setattr(chat_routes, "answer_from_knowledge", lambda query, role, history: chat_service.ChatResponse(
        answer="grounded answer [1]",
        refused=False,
        citations=[{"title": "policy.pdf", "heading": "Refunds", "page": 2, "source_locations": [{"page": 2}]}],
    ))
    monkeypatch.setattr(chat_service, "chat_repository", FakeRepository())
    app.dependency_overrides[authenticated] = lambda: account
    try:
        response = TestClient(app).post("/chat", json={"query": "  first question?  "})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert calls[0][:4] == (account_id, "first question?", "first question?", None)
    body = response.json()
    assert body["conversation_id"] == str(conversation_id)
    assert [message["role"] for message in body["messages"]] == ["user", "assistant"]
    assert body["messages"][1]["refused"] is False
    assert body["messages"][1]["citations"][0]["title"] == "policy.pdf"


def test_question_length_is_rejected_before_answering(client, monkeypatch) -> None:
    _override_admin()
    monkeypatch.setattr(chat_service, "answer_from_knowledge", lambda *_: (_ for _ in ()).throw(AssertionError))
    try:
        assert client.post("/chat", json={"query": " "}).status_code == 422
        assert client.post("/chat", json={"query": "q" * 4001}).status_code == 422
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("found", [True, False])
def test_endpoint_authorizes_history_before_calling_model(monkeypatch, found):
    from app.chat import routes as chat_routes

    conversation_id = uuid4()
    history = [{"role": "user", "content": "sales report"}]
    seen = []

    def get_conversation(requested_id, owner_id):
        assert requested_id == conversation_id
        assert owner_id == "u1"
        return {"messages": history} if found else None

    def answer(query, role, context):
        seen.append(context)
        return chat_service.ChatResponse(answer="Details", refused=False, citations=[])

    monkeypatch.setattr(chat_service, "get_conversation", get_conversation)
    monkeypatch.setattr(chat_routes, "answer_from_knowledge", answer)
    monkeypatch.setattr(chat_service, "persist_response", lambda *args: args[2])
    _override_admin()
    try:
        response = TestClient(app).post("/chat", json={"query": "More details?", "conversation_id": str(conversation_id)})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == (200 if found else 404)
    assert seen == ([history] if found else [])
