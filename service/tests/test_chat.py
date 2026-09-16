from fastapi.testclient import TestClient
from datetime import datetime, timezone
from uuid import uuid4
import json

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
    monkeypatch.setattr(chat_service, "chat_tool_completion", lambda *args, **kwargs: {
        "role": "assistant",
        "content": json.dumps({"blocks": [{"kind": "general", "text": "2", "source_ids": []}]}),
    })

    response = chat_service.answer_from_knowledge("What is 1+1?", "staff")
    assert response.answer == "2"
    assert response.citations == []
    assert response.refused is False


def test_answer_accepts_json_with_model_preamble_and_trailing_text(monkeypatch) -> None:
    content = (
        "Here is the answer:\n```json\n"
        '{"blocks":[{"kind":"general","text":"Answer","source_ids":[]}]}'
        "\n```\nI hope this helps."
    )
    monkeypatch.setattr(
        chat_service, "chat_tool_completion", lambda *args, **kwargs: {"content": content},
    )

    response = chat_service.answer_from_knowledge("question", "staff")

    assert response.answer == "Answer"


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

    def fake_completion(messages, tools, *, allow_tools=True):
        if allow_tools:
            return search_call("refund time?")
        seen["prompt"] = messages[-1]["content"]
        return final_answer([
            {"kind": "grounded", "text": "Refunds take 14 days.", "source_ids": ["source-1"]},
        ])

    monkeypatch.setattr(chat_service, "search_knowledge", lambda query, role: results)
    monkeypatch.setattr(chat_service, "chat_tool_completion", fake_completion)

    response = chat_service.answer_from_knowledge("refund time?", "admin")

    assert response.refused is False
    assert "source-1" in seen["prompt"] and "handbook.pptx" in seen["prompt"]
    assert response.answer == "Refunds take 14 days. [1]"
    assert len(response.citations) == 1
    assert response.citations[0].title == "policy.pdf"
    assert response.citations[0].page == 3


def search_call(query):
    return {"role": "assistant", "content": None, "tool_calls": [{
        "id": "call-1", "type": "function",
        "function": {"name": "search_knowledge_base", "arguments": json.dumps({"query": query})},
    }]}


def final_answer(blocks):
    return {"role": "assistant", "content": json.dumps({"blocks": blocks})}


def test_empty_search_falls_back_without_citations(monkeypatch):
    calls = []

    def complete(messages, tools, *, allow_tools=True):
        calls.append(allow_tools)
        if allow_tools:
            return search_call("improve sales")
        assert json.loads(messages[-1]["content"]) == {}
        return final_answer([{"kind": "general", "text": "Consider customer feedback.", "source_ids": []}])

    monkeypatch.setattr(chat_service, "chat_tool_completion", complete)
    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: [])
    response = chat_service.answer_from_knowledge("How do we improve sales?", "staff")
    assert response.answer == "Consider customer feedback."
    assert response.citations == []
    assert response.refused is False
    assert calls == [True, False]


@pytest.mark.parametrize("blocks", [
    [{"kind": "grounded", "text": "Invented.", "source_ids": ["source-99"]}],
    [{"kind": "grounded", "text": "Uncited.", "source_ids": []}],
    [{"kind": "general", "text": "Incorrect citation.", "source_ids": ["source-1"]}],
    [],
])
def test_invalid_answer_sources_fail_closed(monkeypatch, blocks):
    monkeypatch.setattr(chat_service, "chat_tool_completion", lambda *args, **kwargs: final_answer(blocks))
    with pytest.raises(chat_service.LLMError):
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

    def complete(messages, tools, *, allow_tools=True):
        if allow_tools:
            return search_call("sales report")
        return final_answer([
            {"kind": "grounded", "text": "Sales increased.", "source_ids": ["source-2", "source-2"]},
            {"kind": "general", "text": "Consider expanding distribution.", "source_ids": []},
        ])

    monkeypatch.setattr(chat_service, "search_knowledge", search)
    monkeypatch.setattr(chat_service, "chat_tool_completion", complete)
    response = chat_service.answer_from_knowledge("Report and your opinion?", "staff")
    assert response.answer == (
        "From your documents\nSales increased. [1]\n\nGeneral analysis\nConsider expanding distribution."
    )
    assert [citation.title for citation in response.citations] == ["report.pdf"]
    assert searches == [("sales report", "staff")]


@pytest.mark.parametrize("multiple_initial_calls", [True, False])
def test_enforces_one_search_per_turn(monkeypatch, multiple_initial_calls):
    searches = []
    response = search_call("sales")
    if multiple_initial_calls:
        response["tool_calls"] *= 2
    monkeypatch.setattr(chat_service, "chat_tool_completion", lambda *args, **kwargs: response)
    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: searches.append(args) or [])
    with pytest.raises(chat_service.LLMError):
        chat_service.answer_from_knowledge("sales", "staff")
    assert len(searches) == (0 if multiple_initial_calls else 1)


def test_model_receives_bounded_conversation_context(monkeypatch):
    seen = []
    history = [{"role": "user", "content": "old", "id": "ignored"}] * 25
    history.append({"role": "assistant", "content": "Option two is distribution."})

    def complete(messages, tools, **kwargs):
        seen.extend(messages)
        return final_answer([{"kind": "general", "text": "More details.", "source_ids": []}])

    monkeypatch.setattr(chat_service, "chat_tool_completion", complete)
    chat_service.answer_from_knowledge("What about the second option?", "staff", history)
    assert len(seen) == 22
    assert seen[-2] == {"role": "assistant", "content": "Option two is distribution."}
    assert seen[-1]["content"] == "What about the second option?"
    assert all("id" not in message for message in seen)


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
