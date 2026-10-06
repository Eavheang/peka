import asyncio
import json
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.chat import service as chat_service
from app.auth.routes import authenticated
from app.engine.search.service import RetrievalResult
from app.main import app


def _search_plan(tool="none", query=None):
    return chat_service.SearchPlan(tool=tool, query=query)


def _retrieval(hits=None, top_score=None) -> RetrievalResult:
    hits = list(hits or [])
    if top_score is None and hits:
        top_score = max(float(hit.get("score", 0.99)) for hit in hits)
    return RetrievalResult(hits=hits, top_score=top_score)


def _override_admin() -> None:
    app.dependency_overrides[authenticated] = lambda: {"id": "u1", "role": "admin"}


def test_general_question_does_not_search(monkeypatch) -> None:
    def no_search(*args):
        raise AssertionError("General questions must not search")

    monkeypatch.setattr(chat_service, "search_knowledge", no_search)
    monkeypatch.setattr(
        chat_service,
        "generate_structured",
        lambda messages, output_type: (
            _search_plan()
            if output_type is chat_service.SearchPlan
            else chat_service.ModelAnswer(
                blocks=[{"kind": "general", "text": "2", "source_ids": []}]
            )
        ),
    )

    response = chat_service.answer_from_knowledge("What is 1+1?", "staff")
    assert response.answer == "2"
    assert response.citations == []
    assert response.refused is False


def test_search_plan_without_query_answers_without_search(monkeypatch) -> None:
    def no_search(*args):
        raise AssertionError("A plan without a query must not search")

    monkeypatch.setattr(chat_service, "search_knowledge", no_search)
    monkeypatch.setattr(
        chat_service,
        "generate_structured",
        lambda messages, output_type: (
            _search_plan("search_knowledge_base", None)
            if output_type is chat_service.SearchPlan
            else chat_service.ModelAnswer(
                blocks=[{"kind": "general", "text": "Hello", "source_ids": []}]
            )
        ),
    )

    response = chat_service.answer_from_knowledge("hi", "staff")
    assert response.answer == "Hello"
    assert response.citations == []


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
    file_id = uuid4()
    results = [
        {
            "file_id": str(file_id),
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
        if output_type is chat_service.SearchPlan:
            return _search_plan("search_knowledge_base", "refund time?")
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

    monkeypatch.setattr(chat_service, "search_knowledge", lambda query, role: _retrieval(results))
    monkeypatch.setattr(chat_service, "generate_structured", fake_generation)

    response = chat_service.answer_from_knowledge("refund time?", "admin")

    assert response.refused is False
    assert response.answer_status == "answered"
    assert "source-1" in seen["prompt"] and "handbook.pptx" in seen["prompt"]
    assert response.answer == "Refunds take 14 days. [1]"
    assert len(response.citations) == 1
    assert response.citations[0].title == "policy.pdf"
    assert response.citations[0].page == 3
    assert response.citations[0].file_id == file_id


def test_invalid_source_is_dropped_without_retry(monkeypatch):
    results = [
        {
            "title": "school-policy.pdf",
            "heading": "Student conduct",
            "snippet": "Fighting is prohibited.",
            "source_locations": [],
        }
    ]
    answer_calls = 0

    def generate(_messages, output_type):
        nonlocal answer_calls
        if output_type is chat_service.SearchPlan:
            return _search_plan("search_knowledge_base", "school policy fighting")
        answer_calls += 1
        return chat_service.ModelAnswer(
            blocks=[
                {
                    "kind": "grounded",
                    "text": "Fighting is prohibited.",
                    "source_ids": ["source-2"],
                }
            ]
        )

    monkeypatch.setattr(chat_service, "generate_structured", generate)
    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: _retrieval(results))

    response = chat_service.answer_from_knowledge(
        "Is fighting against school policy?", "staff", web_search=True
    )

    assert response.answer == "Fighting is prohibited."
    assert response.citations == []
    assert answer_calls == 1


def test_stream_invalid_source_is_dropped_without_retry(monkeypatch):
    results = [
        {
            "title": "school-policy.pdf",
            "heading": "Student conduct",
            "snippet": "Fighting is prohibited.",
            "source_locations": [],
        }
    ]
    stream_calls = []

    monkeypatch.setattr(
        chat_service,
        "generate_structured",
        lambda messages, output_type: _search_plan("search_knowledge_base", "school policy fighting")
        if output_type is chat_service.SearchPlan
        else pytest.fail("Answer generation should use the streaming path"),
    )
    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: _retrieval(results))

    async def stream_text(messages, output_type):
        stream_calls.append(messages)
        yield json.dumps(
            {
                "blocks": [
                    {
                        "kind": "grounded",
                        "text": "Original answer.",
                        "source_ids": ["source-2"],
                    }
                ]
            }
        )

    monkeypatch.setattr(chat_service, "stream_structured_text", stream_text)

    async def collect():
        return [
            event
            async for event in chat_service.stream_answer_from_knowledge(
                "Is fighting against school policy?", "staff", web_search=True
            )
        ]

    events = asyncio.run(collect())
    completed = next(
        event for event in events if isinstance(event, chat_service.ChatStreamCompleted)
    )
    assert completed.response.answer == "Original answer."
    assert completed.response.citations == []
    assert len(stream_calls) == 1


def test_empty_knowledge_search_refuses_without_calling_the_answer_model(monkeypatch):
    calls = []

    def generate(messages, output_type):
        calls.append(output_type)
        if output_type is chat_service.SearchPlan:
            return _search_plan("search_knowledge_base", "improve sales")
        raise AssertionError("Empty KB retrieval must skip the answer model")

    monkeypatch.setattr(chat_service, "generate_structured", generate)
    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: _retrieval([]))
    response = chat_service.answer_from_knowledge("How do we improve sales?", "staff")
    assert response.answer == chat_service.NO_EVIDENCE_ANSWER
    assert response.citations == []
    assert response.refused is True
    assert response.answer_status == "refused"
    assert calls == [chat_service.SearchPlan]


@pytest.mark.parametrize("blocks", [
    [{"kind": "grounded", "text": "Invented.", "source_ids": ["source-99"]}],
    [{"kind": "grounded", "text": "Uncited.", "source_ids": []}],
    [{"kind": "general", "text": "Incorrect citation.", "source_ids": ["source-1"]}],
])
def test_invalid_answer_sources_are_dropped_without_retry(monkeypatch, blocks):
    monkeypatch.setattr(
        chat_service,
        "generate_structured",
        lambda messages, output_type: (
            _search_plan()
            if output_type is chat_service.SearchPlan
            else chat_service.ModelAnswer(blocks=blocks)
        ),
    )
    response = chat_service.answer_from_knowledge("question", "staff")

    assert response.answer == blocks[0]["text"]
    assert response.citations == []


def test_mixed_answer_remaps_and_deduplicates_sources(monkeypatch):
    results = [
        {"title": "unused.pdf", "heading": "Unused", "snippet": "Unrelated", "source_locations": []},
        {"title": "report.pdf", "heading": "Sales", "snippet": "Sales increased.", "source_locations": []},
    ]
    searches = []

    def search(query, role):
        searches.append((query, role))
        return _retrieval(results)

    def generate(messages, output_type):
        if output_type is chat_service.SearchPlan:
            return _search_plan("search_knowledge_base", "sales report")
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
        "Sales increased. [1]\n\nConsider expanding distribution."
    )
    assert [citation.title for citation in response.citations] == ["report.pdf"]
    assert searches == [("sales report", "staff")]


def test_answer_formats_markdown_bullets_without_changing_stream_content(monkeypatch):
    results = [{"title": "report.pdf", "heading": "Sales", "snippet": "Sales increased.", "source_locations": []}]

    def generate(messages, output_type):
        if output_type is chat_service.SearchPlan:
            return _search_plan("search_knowledge_base", "sales report")
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

    monkeypatch.setattr(chat_service, "search_knowledge", lambda query, role: _retrieval(results))
    monkeypatch.setattr(chat_service, "generate_structured", generate)

    response = chat_service.answer_from_knowledge("Report and your opinion?", "staff")

    assert response.answer == (
        "- Sales increased.\n- Distribution grew. [1]\n\n"
        "- Customer retention improved. [1]\n\nConsider expanding distribution."
    )


def test_enforces_one_search_per_turn(monkeypatch):
    searches = []
    def generate(messages, output_type):
        if output_type is chat_service.SearchPlan:
            return _search_plan("search_knowledge_base", "sales")
        return chat_service.ModelAnswer(
            blocks=[{"kind": "general", "text": "No results.", "source_ids": []}]
        )

    monkeypatch.setattr(chat_service, "generate_structured", generate)
    monkeypatch.setattr(
        chat_service,
        "search_knowledge",
        lambda *args: searches.append(args) or _retrieval([]),
    )
    chat_service.answer_from_knowledge("sales", "staff")
    assert len(searches) == 1


def test_model_receives_bounded_conversation_context(monkeypatch):
    seen = []
    history = [{"role": "user", "content": "old", "id": "ignored"}] * 25
    history.append({"role": "assistant", "content": "Option two is distribution."})

    def generate(messages, output_type):
        if output_type is chat_service.SearchPlan:
            return _search_plan()
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


def test_historical_citation_markers_are_not_sent_back_as_context():
    messages = chat_service._conversation_messages(
        "What about attendance?",
        [
            {"role": "user", "content": "What is school policy?"},
            {"role": "assistant", "content": "Attendance is at least 95%. [1]"},
        ],
        "system",
    )

    assert messages[-2].text == "Attendance is at least 95%."


def test_model_routes_ambiguous_follow_up_to_current_knowledge_search(monkeypatch):
    history = [
        {"role": "user", "content": "What is school policy?"},
        {
            "role": "assistant",
            "content": "Students are expected to maintain at least 95% attendance. [1]",
            "citations": [{"title": "school-policy.pdf"}],
        },
    ]
    searches = []
    router_messages = []
    result = {
        "title": "school-policy.pdf",
        "heading": "Attendance & Punctuality",
        "snippet": "Students are expected to maintain at least 95% attendance.",
        "content": "Students are expected to maintain at least 95% attendance.",
        "source_locations": [],
    }

    def generate(messages, output_type):
        if output_type is chat_service.SearchPlan:
            router_messages.extend(messages)
            return _search_plan(
                "search_knowledge_base",
                "school policy attendance consequences of missing more than 40 times a year",
            )
        return chat_service.ModelAnswer(
            blocks=[{
                "kind": "grounded",
                "text": "The policy requires at least 95% attendance.",
                "source_ids": ["source-1"],
            }]
        )

    monkeypatch.setattr(chat_service, "generate_structured", generate)
    monkeypatch.setattr(
        chat_service,
        "search_knowledge",
        lambda query, role: searches.append((query, role)) or _retrieval([result]),
    )

    response = chat_service.answer_from_knowledge(
        "What if I miss more than 40 times a year?", "staff", history
    )

    assert searches == [
        ("school policy attendance consequences of missing more than 40 times a year", "staff")
    ]
    assert router_messages[-2].text == "Students are expected to maintain at least 95% attendance."
    assert response.answer.endswith("[1]")


def test_retrieval_router_prompt_has_only_search_plan_schema(monkeypatch):
    history = [
        {"role": "user", "content": "Can you tell me about the school policy?"},
        {"role": "assistant", "content": "The policy defines three discipline levels."},
    ]

    def generate(messages, output_type):
        if output_type is chat_service.SearchPlan:
            assert '"blocks"' not in messages[0].text
            return _search_plan("search_knowledge_base", "school policy discipline consequences")
        return chat_service.ModelAnswer(
            blocks=[{"kind": "general", "text": "Details.", "source_ids": []}]
        )

    monkeypatch.setattr(chat_service, "generate_structured", generate)
    monkeypatch.setattr(
        chat_service,
        "search_knowledge",
        lambda *args: _retrieval(
            [{
                "title": "school-policy.pdf",
                "heading": "Discipline",
                "snippet": "Three levels.",
                "source_locations": [],
                "score": 0.9,
            }]
        ),
    )

    response = chat_service.answer_from_knowledge(
        "But based on the school policy, what will happen?", "admin", history
    )

    assert response.answer == "Details."


def test_model_selects_knowledge_base_for_contextual_follow_up(monkeypatch):
    history = [
        {"role": "user", "content": "Can you tell me about the school policy?"},
        {"role": "assistant", "content": "The policy covers student conduct."},
    ]

    seen = []

    def generate(messages, output_type):
        seen.append(output_type)
        if output_type is chat_service.SearchPlan:
            return _search_plan(
                "search_knowledge_base",
                "school policy student fighting disciplinary consequences",
            )
        return chat_service.ModelAnswer(
            blocks=[{"kind": "general", "text": "Details.", "source_ids": []}]
        )

    monkeypatch.setattr(chat_service, "generate_structured", generate)
    monkeypatch.setattr(
        chat_service,
        "search_knowledge",
        lambda *args: _retrieval(
            [{
                "title": "school-policy.pdf",
                "heading": "Conduct",
                "snippet": "Fighting is prohibited.",
                "source_locations": [],
                "score": 0.9,
            }]
        ),
    )

    chat_service.answer_from_knowledge(
        "What happens if a student fights?", "admin", history, web_search=True
    )
    assert seen == [chat_service.SearchPlan, chat_service.ModelAnswer]


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
        assert body == {
            "answer": "ok [1]",
            "refused": False,
            "answer_status": "answered",
            "citations": [],
        }
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
    monkeypatch.setattr(
        chat_service,
        "generate_structured",
        lambda messages, output_type: _search_plan()
        if output_type is chat_service.SearchPlan
        else pytest.fail("Answer generation should use the streaming path"),
    )

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


def test_streamed_markdown_matches_final_answer(monkeypatch) -> None:
    result = {
        "title": "policy.pdf",
        "heading": "Attendance",
        "snippet": "Policy details.",
        "content": "Policy details.",
        "source_locations": [],
    }

    async def stream_text(*args, **kwargs):
        payload = json.dumps(
            {
                "blocks": [
                    {
                        "kind": "grounded",
                        "text": "**Important**:\n• First item\n• Second item",
                        "source_ids": ["source-1"],
                    },
                    {
                        "kind": "general",
                        "text": "**Advice**\n- Keep records.",
                        "source_ids": [],
                    },
                ]
            }
        )
        for index in range(0, len(payload), 7):
            yield payload[index:index + 7]

    monkeypatch.setattr(chat_service, "stream_structured_text", stream_text)
    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: _retrieval([result]))
    monkeypatch.setattr(
        chat_service,
        "generate_structured",
        lambda messages, output_type: _search_plan("search_knowledge_base", "policy")
        if output_type is chat_service.SearchPlan
        else pytest.fail("Answer generation should use the streaming path"),
    )

    async def collect():
        return [
            event
            async for event in chat_service.stream_answer_from_knowledge("policy", "staff")
        ]

    events = asyncio.run(collect())
    streamed = "".join(
        event.delta for event in events if isinstance(event, chat_service.ChatStreamText)
    )
    completed = next(
        event for event in events if isinstance(event, chat_service.ChatStreamCompleted)
    )

    assert streamed == completed.response.answer


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


def _stream_events(monkeypatch, chunks: list[str], regenerate_error: bool = True):
    async def stream_text(*args, **kwargs):
        for chunk in chunks:
            yield chunk

    def generate(messages, output_type):
        if output_type is chat_service.SearchPlan:
            return _search_plan()
        if regenerate_error:
            raise chat_service.AIModelError("Model returned an invalid structured response")
        pytest.fail("A repairable answer must not be regenerated")

    monkeypatch.setattr(chat_service, "stream_structured_text", stream_text)
    monkeypatch.setattr(chat_service, "generate_structured", generate)

    async def collect():
        return [event async for event in chat_service.stream_answer_from_knowledge("hello", "staff")]

    return asyncio.run(collect())


def test_stream_repairs_unescaped_quotes_without_regenerating(monkeypatch) -> None:
    broken = (
        '{"blocks":[{"kind":"general","text":"Systems use "reranking" to sort.","source_ids":[]}]}'
    )

    events = _stream_events(monkeypatch, [broken[:40], broken[40:]], regenerate_error=False)
    completed = next(e for e in events if isinstance(e, chat_service.ChatStreamCompleted))

    assert completed.response.answer == 'Systems use "reranking" to sort.'


def test_stream_falls_back_to_the_plain_text_answer_when_regeneration_fails(monkeypatch) -> None:
    prose = "RAG evolved in three stages [1]. Advanced systems rerank results [1, 2]."

    events = _stream_events(monkeypatch, [prose])
    completed = next(e for e in events if isinstance(e, chat_service.ChatStreamCompleted))
    shown = "".join(e.delta for e in events if isinstance(e, chat_service.ChatStreamText))

    assert "RAG evolved in three stages." in completed.response.answer
    assert "[1" not in completed.response.answer
    assert "Sources could not be attached" in completed.response.answer
    assert completed.response.citations == [] and completed.response.refused is False
    assert shown == completed.response.answer


def test_stream_still_fails_when_the_output_is_broken_json_and_regeneration_fails(monkeypatch) -> None:
    with pytest.raises(chat_service.AIModelError):
        _stream_events(monkeypatch, ['{"blocks":[{"kind":"general","text":"cut off'])


def test_plain_text_fallback_cleans_markers_and_rejects_json_and_empty() -> None:
    cleaned = chat_service._plain_text_fallback('Answer [1] here {"source-1"} and {"source-2, source-3} more [2, 3].')

    assert cleaned.startswith("Answer here and more.")
    assert "source-" not in cleaned and "[" not in cleaned.split("\n\n")[0]
    for unusable in ("", "   ", '{"blocks":[]}', "```json\n{}\n```", "[1]"):
        assert chat_service._plain_text_fallback(unusable) is None


def test_below_threshold_refuses_without_llm_or_citations(monkeypatch) -> None:
    answer_calls = 0
    hit = {
        "title": "noise.pdf",
        "heading": "Unrelated",
        "snippet": "Weak match.",
        "source_locations": [],
        "score": 0.55,
    }

    def generate(messages, output_type):
        nonlocal answer_calls
        if output_type is chat_service.SearchPlan:
            return _search_plan("search_knowledge_base", "pet policy")
        answer_calls += 1
        raise AssertionError("Below-threshold retrieval must skip the answer model")

    monkeypatch.setattr(chat_service.settings, "no_evidence_threshold", 0.70)
    monkeypatch.setattr(chat_service, "generate_structured", generate)
    monkeypatch.setattr(
        chat_service, "search_knowledge", lambda *args: _retrieval([hit], top_score=0.55)
    )

    response = chat_service.answer_from_knowledge("What is our pet policy?", "staff")

    assert answer_calls == 0
    assert response.answer == chat_service.NO_EVIDENCE_ANSWER
    assert response.citations == []
    assert response.refused is True
    assert response.answer_status == "refused"


def test_at_threshold_runs_normal_answer_path(monkeypatch) -> None:
    hit = {
        "title": "policy.pdf",
        "heading": "Leave",
        "snippet": "20 days of leave.",
        "content": "20 days of leave.",
        "source_locations": [{"page": 1}],
        "score": 0.70,
    }
    answer_calls = 0

    def generate(messages, output_type):
        nonlocal answer_calls
        if output_type is chat_service.SearchPlan:
            return _search_plan("search_knowledge_base", "leave days")
        answer_calls += 1
        return chat_service.ModelAnswer(
            blocks=[{
                "kind": "grounded",
                "text": "Every employee gets 20 days of leave.",
                "source_ids": ["source-1"],
            }]
        )

    monkeypatch.setattr(chat_service.settings, "no_evidence_threshold", 0.70)
    monkeypatch.setattr(chat_service, "generate_structured", generate)
    monkeypatch.setattr(
        chat_service, "search_knowledge", lambda *args: _retrieval([hit], top_score=0.70)
    )

    response = chat_service.answer_from_knowledge("How much leave?", "staff")

    assert answer_calls == 1
    assert response.refused is False
    assert response.answer_status == "answered"
    assert response.answer == "Every employee gets 20 days of leave. [1]"
    assert len(response.citations) == 1


def test_stream_refusal_emits_fixed_text_and_answer_status(monkeypatch) -> None:
    monkeypatch.setattr(chat_service.settings, "no_evidence_threshold", 0.70)
    monkeypatch.setattr(
        chat_service,
        "generate_structured",
        lambda messages, output_type: _search_plan("search_knowledge_base", "missing topic")
        if output_type is chat_service.SearchPlan
        else pytest.fail("Refusal must not call the answer model"),
    )
    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: _retrieval([]))

    async def collect():
        return [
            event
            async for event in chat_service.stream_answer_from_knowledge(
                "What is the Antarctica stipend?", "staff"
            )
        ]

    events = asyncio.run(collect())
    text = "".join(
        event.delta for event in events if isinstance(event, chat_service.ChatStreamText)
    )
    completed = next(
        event for event in events if isinstance(event, chat_service.ChatStreamCompleted)
    )

    assert text == chat_service.NO_EVIDENCE_ANSWER
    assert completed.response.answer_status == "refused"
    assert completed.response.refused is True
    assert completed.response.citations == []


def test_refusal_persist_writes_refused_flag_and_audit(monkeypatch) -> None:
    owner_id = uuid4()
    created_conversation_id = uuid4()
    audits = []
    persisted = []

    class FakeRepository:
        def create_exchange(self, owner_id, title, query, response, conversation_id=None):
            persisted.append(response)
            created_at = datetime.now(timezone.utc)
            return {
                "conversation": {"id": created_conversation_id},
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
                        "citations": [],
                        "status": "completed",
                        "created_at": created_at,
                    },
                ],
            }

    monkeypatch.setattr(chat_service, "chat_repository", FakeRepository())
    monkeypatch.setattr(
        chat_service,
        "record_audit_event",
        lambda name, actor_id=None, metadata=None: audits.append(
            (name, actor_id, metadata)
        ),
    )

    saved = chat_service.persist_response(
        "missing evidence?",
        owner_id,
        chat_service.ChatResponse(
            answer=chat_service.NO_EVIDENCE_ANSWER, refused=True, citations=[]
        ),
    )

    assert persisted[0].refused is True
    assert persisted[0].answer_status == "refused"
    assert saved.messages[1].refused is True
    assert audits == [
        ("chat_turn", owner_id, {"conversation_id": str(created_conversation_id)})
    ]


def test_answered_stream_payload_includes_answer_status(monkeypatch) -> None:
    """Blast-radius check: answered path stays the same except answer_status."""
    async def stream_text(*args, **kwargs):
        yield json.dumps(
            {"blocks": [{"kind": "general", "text": "Hello", "source_ids": []}]}
        )

    monkeypatch.setattr(chat_service, "stream_structured_text", stream_text)
    monkeypatch.setattr(
        chat_service,
        "generate_structured",
        lambda messages, output_type: _search_plan()
        if output_type is chat_service.SearchPlan
        else pytest.fail("Answer generation should use the streaming path"),
    )

    async def collect():
        return [
            event
            async for event in chat_service.stream_answer_from_knowledge("hello", "staff")
        ]

    events = asyncio.run(collect())
    completed = next(
        event for event in events if isinstance(event, chat_service.ChatStreamCompleted)
    )
    payload = completed.response.model_dump(mode="json", exclude_none=True)

    assert payload["answer"] == "Hello"
    assert payload["refused"] is False
    assert payload["citations"] == []
    assert payload["answer_status"] == "answered"
    assert set(payload) == {"answer", "refused", "citations", "answer_status"}
