import asyncio
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from uuid import uuid4

import ai
import pytest

from app.chat import service as chat_service
from app.auth.routes import authenticated
from app.engine import ai_runtime
from app.main import app


def _search_plan(tool="none", query=None):
    return chat_service.SearchPlan(tool=tool, query=query)


def _no_generation(*args, **kwargs):
    pytest.fail("This turn must not make a one-shot model call")


_real_needs_documents = chat_service._needs_documents


@pytest.fixture(autouse=True)
def _empty_knowledge_base(monkeypatch) -> None:
    # Chat always searches; tests that need results patch search_knowledge again.
    monkeypatch.setattr(chat_service, "search_knowledge", lambda query, role: [])
    # With no evidence the question counts as general unless a test says otherwise.
    monkeypatch.setattr(chat_service, "_needs_documents", lambda *args: False)


def _override_admin() -> None:
    app.dependency_overrides[authenticated] = lambda: {"id": "u1", "role": "admin"}


ANSWER_JSON = '{"blocks":[{"kind":"general","text":"Answer","source_ids":[]}]}'
WAITING = chat_service.ChatStreamStatus("Waiting for other answers to finish...")


@pytest.fixture
def two_slots(monkeypatch) -> threading.BoundedSemaphore:
    slots = threading.BoundedSemaphore(2)
    monkeypatch.setattr(chat_service, "_chat_slots", slots)
    return slots


def test_third_simultaneous_chat_waits_then_answers(monkeypatch, two_slots) -> None:
    running = peak = 0

    async def stream_text(messages, output_type):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.2)
        running -= 1
        yield ANSWER_JSON

    monkeypatch.setattr(chat_service, "stream_structured_text", stream_text)

    async def chat():
        return [event async for event in chat_service.stream_answer_from_knowledge("q", "staff")]

    async def three_chats():
        return await asyncio.gather(chat(), chat(), chat())

    results = asyncio.run(three_chats())

    assert peak == 2
    assert [events[-1].response.answer for events in results] == ["Answer"] * 3
    assert sum(WAITING in events for events in results) == 1


def test_non_streaming_chats_share_the_same_slots(monkeypatch, two_slots) -> None:
    lock = threading.Lock()
    running = peak = 0

    def generate(messages, output_type):
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        time.sleep(0.1)
        with lock:
            running -= 1
        return chat_service.ModelAnswer.model_validate_json(ANSWER_JSON)

    monkeypatch.setattr(chat_service, "generate_structured", generate)

    with ThreadPoolExecutor(3) as pool:
        answers = list(pool.map(lambda _: chat_service.answer_from_knowledge("q", "staff"), range(3)))

    assert peak == 2
    assert [answer.answer for answer in answers] == ["Answer"] * 3


def test_stopping_a_chat_frees_its_slot_and_cancels_its_model_call(monkeypatch, two_slots) -> None:
    closed = []

    async def stream_text(messages, output_type):
        try:
            yield '{"blocks":[{"kind":"general","text":"Ans'
            await asyncio.sleep(60)
        finally:
            closed.append(two_slots._value)

    monkeypatch.setattr(chat_service, "stream_structured_text", stream_text)

    async def stop_chats():
        answering = chat_service.stream_answer_from_knowledge("q", "staff")
        holding = chat_service.stream_answer_from_knowledge("q", "staff")
        waiting = chat_service.stream_answer_from_knowledge("q", "staff")
        while not isinstance(await anext(answering), chat_service.ChatStreamText):
            pass
        await anext(holding)
        assert await anext(waiting) == WAITING
        await waiting.aclose()
        await holding.aclose()
        await answering.aclose()

    asyncio.run(stop_chats())

    assert closed == [1], "the model call must end before its slot is released"
    assert two_slots._value == 2


_EARLIER_TURN = [
    {"role": "user", "content": "What is the refund policy?"},
    {"role": "assistant", "content": "Refunds take 14 days."},
]
both_chat_paths = pytest.mark.parametrize("path", ["plain", "stream"])


def _count_model_calls(monkeypatch, plan=None) -> list:
    """Fake the model on both chat paths and return what it was asked for, in order."""
    calls = []

    def generate(messages, output_type):
        calls.append(output_type)
        if output_type is chat_service.SearchPlan:
            return plan
        return chat_service.ModelAnswer.model_validate_json(ANSWER_JSON)

    async def stream_text(messages, output_type):
        calls.append(output_type)
        yield ANSWER_JSON

    monkeypatch.setattr(chat_service, "generate_structured", generate)
    monkeypatch.setattr(chat_service, "stream_structured_text", stream_text)
    return calls


def _record_searches(monkeypatch) -> list:
    searches = []
    monkeypatch.setattr(
        chat_service, "search_knowledge", lambda query, role: searches.append(query) or []
    )
    return searches


def _ask(path, query, history=None, web_search=False):
    if path == "plain":
        return chat_service.answer_from_knowledge(query, "staff", history, web_search=web_search)

    async def collect():
        return [
            event
            async for event in chat_service.stream_answer_from_knowledge(
                query, "staff", history, web_search=web_search
            )
        ]

    return asyncio.run(collect())[-1].response


@both_chat_paths
def test_first_turn_searches_the_raw_question_with_one_model_call(monkeypatch, path) -> None:
    calls = _count_model_calls(monkeypatch)
    searches = _record_searches(monkeypatch)

    response = _ask(path, "What is the refund window?")

    assert calls == [chat_service.ModelAnswer]
    assert searches == ["What is the refund window?"]
    assert response.answer == "Answer"


@both_chat_paths
def test_first_turn_with_web_search_on_still_plans(monkeypatch, path) -> None:
    calls = _count_model_calls(monkeypatch, _search_plan("web_search", "latest release"))
    searched = []
    monkeypatch.setattr(
        chat_service, "perform_web_search", lambda query: searched.append(query) or []
    )

    _ask(path, "What is the newest release?", web_search=True)

    assert calls == [chat_service.SearchPlan, chat_service.ModelAnswer]
    assert searched == ["latest release"]


def test_query_rewrite_sends_only_the_last_exchanges(monkeypatch) -> None:
    sent = []

    def generate(messages, output_type):
        sent.extend(messages)
        return chat_service.SearchPlan(tool="search_knowledge_base", query="rewritten")

    monkeypatch.setattr(chat_service, "generate_structured", generate)
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i}"} for i in range(10)]

    plan = chat_service._search_plan("and the target?", history, web_search=False)

    assert plan.query == "rewritten"
    assert len(sent) == 1 + chat_service._REWRITE_HISTORY_MESSAGES + 1  # System, recent history, question.


@both_chat_paths
def test_follow_up_rewrites_the_search_query(monkeypatch, path) -> None:
    calls = _count_model_calls(
        monkeypatch, _search_plan("search_knowledge_base", "refund policy duration")
    )
    searches = _record_searches(monkeypatch)

    _ask(path, "How long does that take?", _EARLIER_TURN)

    assert calls == [chat_service.SearchPlan, chat_service.ModelAnswer]
    assert searches == ["refund policy duration"]


@both_chat_paths
@pytest.mark.parametrize("web_search", [False, True])
def test_none_plan_still_searches_the_knowledge_base(monkeypatch, path, web_search) -> None:
    calls = _count_model_calls(monkeypatch, _search_plan())
    searches = _record_searches(monkeypatch)
    monkeypatch.setattr(
        chat_service, "perform_web_search", lambda query: pytest.fail("A none plan must not search the web")
    )

    _ask(path, "And the deadline?", _EARLIER_TURN, web_search)

    assert calls == [chat_service.SearchPlan, chat_service.ModelAnswer]
    assert searches == ["And the deadline?"]


def test_invalid_answer_json_is_not_regenerated_without_streaming(monkeypatch) -> None:
    models = []

    def generate(messages, output_type, **kwargs):
        models.append(ai.testing.FakeModel([*messages, ai.assistant_message("not json")]))
        return ai_runtime.generate_structured(messages, output_type, model=models[-1], **kwargs)

    monkeypatch.setattr(chat_service, "generate_structured", generate)

    with pytest.raises(chat_service.AIModelError, match="invalid structured"):
        chat_service.answer_from_knowledge("question", "staff")

    assert [len(model.calls) for model in models] == [1]


def test_search_plan_without_query_searches_with_raw_question(monkeypatch) -> None:
    searched = []
    monkeypatch.setattr(
        chat_service, "search_knowledge", lambda query, role: searched.append(query) or []
    )
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

    response = chat_service.answer_from_knowledge("hi", "staff", _EARLIER_TURN)
    assert searched == ["hi"]
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
    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: results)

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
    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: results)

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


def test_empty_search_falls_back_without_citations(monkeypatch):
    calls = []

    def generate(messages, output_type):
        calls.append(output_type)
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
    assert calls == [chat_service.ModelAnswer]


@pytest.mark.parametrize("blocks", [
    [{"kind": "grounded", "text": "Invented.", "source_ids": ["source-99"]}],
    [{"kind": "grounded", "text": "Uncited.", "source_ids": []}],
    [{"kind": "general", "text": "Incorrect citation.", "source_ids": ["source-1"]}],
])
def test_invalid_answer_sources_are_dropped_without_retry(monkeypatch, blocks):
    monkeypatch.setattr(
        chat_service,
        "generate_structured",
        lambda messages, output_type: chat_service.ModelAnswer(blocks=blocks),
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
        return results

    def generate(messages, output_type):
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
    assert searches == [("Report and your opinion?", "staff")]


def test_answer_formats_markdown_bullets_without_changing_stream_content(monkeypatch):
    results = [{"title": "report.pdf", "heading": "Sales", "snippet": "Sales increased.", "source_locations": []}]

    def generate(messages, output_type):
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
        "- Sales increased.\n- Distribution grew. [1]\n\n"
        "- Customer retention improved. [1]\n\nConsider expanding distribution."
    )


def test_enforces_one_search_per_turn(monkeypatch):
    searches = []
    def generate(messages, output_type):
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
        if output_type is chat_service.SearchPlan:
            return _search_plan()
        seen.extend(messages)
        return chat_service.ModelAnswer(
            blocks=[{"kind": "general", "text": "More details.", "source_ids": []}]
        )

    monkeypatch.setattr(chat_service, "generate_structured", generate)
    chat_service.answer_from_knowledge("What about the second option?", "staff", history)
    # 20 history messages + system + question + retrieval context
    assert len(seen) == 23
    assert seen[-3].role == "assistant"
    assert seen[-3].text == "Option two is distribution."
    assert seen[-2].text == "What about the second option?"


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


@pytest.fixture
def frozen_now(monkeypatch) -> datetime:
    frozen = datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen.astimezone(tz) if tz is not None else frozen

    monkeypatch.setattr(chat_service, "datetime", FrozenDateTime)
    return frozen


def test_conversation_messages_include_current_datetime(frozen_now) -> None:
    messages = chat_service._conversation_messages("hello", None, "You are Peka.")

    assert frozen_now.astimezone().isoformat(timespec="minutes") in messages[0].text


def test_conversation_messages_use_client_timezone(frozen_now) -> None:
    messages = chat_service._conversation_messages(
        "hello", None, "You are Peka.", "Asia/Phnom_Penh"
    )

    assert "Tuesday 2026-10-06T16:00+07:00 (Asia/Phnom_Penh)" in messages[0].text


def test_unknown_timezone_falls_back_to_server_local_time(monkeypatch) -> None:
    messages = chat_service._conversation_messages(
        "hello", None, "You are Peka.", "Not/A_Zone"
    )

    assert "Current date/time:" in messages[0].text


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
        lambda query, role: searches.append((query, role)) or [result],
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
    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: [])

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
    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: [])

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
        lambda query, role, history, **kwargs: chat_service.ChatResponse(answer="ok [1]", refused=False, citations=[]),
    )
    monkeypatch.setattr(chat_service, "persist_response", lambda query, user_id, response, conversation_id=None, **_: response)
    _override_admin()
    try:
        client = TestClient(app)
        response = client.post("/chat", json={"query": "q"})
        assert response.status_code == 200
        body = response.json()
        assert body == {"answer": "ok [1]", "refused": False, "citations": []}
    finally:
        app.dependency_overrides.clear()


def test_chat_endpoint_forwards_client_timezone(monkeypatch) -> None:
    from app.chat import routes as chat_routes

    seen = {}

    def answer(query, role, history, web_search=False, timezone=None):
        seen["timezone"] = timezone
        return chat_service.ChatResponse(answer="ok", refused=False, citations=[])

    monkeypatch.setattr(chat_routes, "answer_from_knowledge", answer)
    monkeypatch.setattr(
        chat_service, "persist_response", lambda query, user_id, response, conversation_id=None, **_: response
    )
    _override_admin()
    try:
        response = TestClient(app).post(
            "/chat", json={"query": "q", "timezone": "Asia/Phnom_Penh"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert seen["timezone"] == "Asia/Phnom_Penh"


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

    def persist(*args, **kwargs):
        return args[2].model_copy(
            update={"conversation_id": conversation_id, "messages": []}
        )

    monkeypatch.setattr(chat_routes.chat_service, "stream_answer_from_knowledge", stream_answer)
    monkeypatch.setattr(chat_routes.chat_service, "persist_response", persist)
    monkeypatch.setattr(chat_routes.chat_service, "model_name", lambda: "test-model")
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


def test_regenerate_conflict_is_a_409_on_both_endpoints(monkeypatch) -> None:
    from app.chat import routes as chat_routes
    from app.chat.repository import ConversationChangedError

    history = [
        {"id": uuid4(), "role": "user", "content": "q"},
        {"id": uuid4(), "role": "assistant", "content": "a"},
    ]
    answer = chat_service.ChatResponse(answer="new", refused=False, citations=[])

    async def stream_answer(*_args, **_kwargs):
        yield chat_service.ChatStreamCompleted(answer)

    def persist(*_args, **_kwargs):
        raise ConversationChangedError

    monkeypatch.setattr(chat_routes.chat_service, "get_conversation", lambda *_: {"messages": history})
    monkeypatch.setattr(chat_routes, "answer_from_knowledge", lambda *_args, **_kwargs: answer)
    monkeypatch.setattr(chat_routes.chat_service, "stream_answer_from_knowledge", stream_answer)
    monkeypatch.setattr(chat_routes.chat_service, "persist_response", persist)
    monkeypatch.setattr(chat_routes.chat_service, "audit_unsaved_turn", lambda *_args: None)
    monkeypatch.setattr(chat_routes.chat_service, "model_name", lambda: "test-model")
    body = {"query": "x", "conversation_id": str(uuid4()), "regenerate": True}
    _override_admin()
    try:
        client = TestClient(app)
        plain = client.post("/chat", json=body)
        stream = client.post("/chat/stream", json=body)
    finally:
        app.dependency_overrides.clear()

    assert plain.status_code == 409
    assert plain.json() == {"detail": "The conversation changed. Please try again."}
    assert '"type": "error", "status": 409' in stream.text


def test_chat_stream_regenerate_replays_last_question_and_replaces_pair(monkeypatch) -> None:
    from app.chat import routes as chat_routes

    conversation_id = uuid4()
    history = [
        {"id": uuid4(), "role": role, "content": content}
        for role, content in [("user", "first"), ("assistant", "one"), ("user", "second"), ("assistant", "two")]
    ]
    seen: dict = {}

    async def stream_answer(query, role, hist, **kwargs):
        seen["query"], seen["history"] = query, hist
        yield chat_service.ChatStreamCompleted(
            chat_service.ChatResponse(answer="new", refused=False, citations=[])
        )

    def persist(query, user_id, response, conversation_id=None, **kwargs):
        seen["replace_ids"] = kwargs["replace_ids"]
        return response.model_copy(update={"conversation_id": conversation_id, "messages": []})

    monkeypatch.setattr(chat_routes.chat_service, "get_conversation", lambda *_: {"messages": history})
    monkeypatch.setattr(chat_routes.chat_service, "stream_answer_from_knowledge", stream_answer)
    monkeypatch.setattr(chat_routes.chat_service, "persist_response", persist)
    monkeypatch.setattr(chat_routes.chat_service, "model_name", lambda: "test-model")
    _override_admin()
    try:
        client = TestClient(app)
        ok = client.post(
            "/chat/stream",
            json={"query": "ignored", "conversation_id": str(conversation_id), "regenerate": True},
        )
        no_conversation = client.post("/chat/stream", json={"query": "x", "regenerate": True})
    finally:
        app.dependency_overrides.clear()

    assert ok.status_code == 200
    assert seen == {
        "query": "second", "history": history[:2],
        "replace_ids": (history[2]["id"], history[3]["id"]),
    }
    assert no_conversation.status_code == 409


def test_stream_answer_parses_incremental_json_and_validates_answer(monkeypatch) -> None:
    async def stream_text(*args, **kwargs):
        for chunk in (
            '{"blocks":[{"kind":"general","text":"Hello ',
            'world\\nline',
            '","source_ids":[]}]}'
        ):
            yield chunk

    monkeypatch.setattr(chat_service, "stream_structured_text", stream_text)
    monkeypatch.setattr(chat_service, "generate_structured", _no_generation)

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
    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: [result])
    monkeypatch.setattr(chat_service, "generate_structured", _no_generation)

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
        def create_exchange(self, owner_id, title, query, response, conversation_id=None, status="completed", new_conversation_id=None, replace_ids=None):
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
    monkeypatch.setattr(chat_routes, "answer_from_knowledge", lambda query, role, history, **kwargs: chat_service.ChatResponse(
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

    def answer(query, role, context, **kwargs):
        seen.append(context)
        return chat_service.ChatResponse(answer="Details", refused=False, citations=[])

    monkeypatch.setattr(chat_service, "get_conversation", get_conversation)
    monkeypatch.setattr(chat_routes, "answer_from_knowledge", answer)
    monkeypatch.setattr(chat_service, "persist_response", lambda *args, **_: args[2])
    _override_admin()
    try:
        response = TestClient(app).post("/chat", json={"query": "More details?", "conversation_id": str(conversation_id)})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == (200 if found else 404)
    assert seen == ([history] if found else [])


def _stream_events(monkeypatch, chunks: list[str]):
    async def stream_text(*args, **kwargs):
        for chunk in chunks:
            yield chunk

    monkeypatch.setattr(chat_service, "stream_structured_text", stream_text)
    monkeypatch.setattr(chat_service, "generate_structured", _no_generation)

    async def collect():
        return [event async for event in chat_service.stream_answer_from_knowledge("hello", "staff")]

    return asyncio.run(collect())


def test_stream_repairs_unescaped_quotes_without_regenerating(monkeypatch) -> None:
    broken = (
        '{"blocks":[{"kind":"general","text":"Systems use "reranking" to sort.","source_ids":[]}]}'
    )

    events = _stream_events(monkeypatch, [broken[:40], broken[40:]])
    completed = next(e for e in events if isinstance(e, chat_service.ChatStreamCompleted))

    assert completed.response.answer == 'Systems use "reranking" to sort.'


def test_stream_falls_back_to_the_plain_text_answer_without_regenerating(monkeypatch) -> None:
    prose = "RAG evolved in three stages [1]. Advanced systems rerank results [1, 2]."

    events = _stream_events(monkeypatch, [prose])
    completed = next(e for e in events if isinstance(e, chat_service.ChatStreamCompleted))
    shown = _visible_text(events)

    assert "RAG evolved in three stages." in completed.response.answer
    assert "[1" not in completed.response.answer
    assert "Sources could not be attached" in completed.response.answer
    assert completed.response.citations == [] and completed.response.refused is False
    assert shown == completed.response.answer


def test_stream_fails_clearly_on_broken_json_without_regenerating(monkeypatch, two_slots) -> None:
    calls = []

    async def stream_text(messages, output_type):
        calls.append(output_type)
        yield '{"blocks":[{"kind":"gen'

    monkeypatch.setattr(chat_service, "stream_structured_text", stream_text)
    monkeypatch.setattr(chat_service, "generate_structured", _no_generation)

    with pytest.raises(chat_service.AIModelError, match="cut off or malformed"):
        _ask("stream", "hello")

    assert calls == [chat_service.ModelAnswer]
    assert two_slots._value == 2, "a failed answer must release its slot"


def test_plain_text_fallback_cleans_markers_and_rejects_json_and_empty() -> None:
    cleaned = chat_service._plain_text_fallback('Answer [1] here {"source-1"} and {"source-2, source-3} more [2, 3].')

    assert cleaned.startswith("Answer here and more.")
    assert "source-" not in cleaned and "[" not in cleaned.split("\n\n")[0]
    for unusable in ("", "   ", '{"blocks":[]}', "```json\n{}\n```", "[1]"):
        assert chat_service._plain_text_fallback(unusable) is None


def _visible_text(events) -> str:
    """The text a client shows: deltas since the last reset."""
    shown = ""
    for event in events:
        if isinstance(event, chat_service.ChatStreamReset):
            shown = ""
        elif isinstance(event, chat_service.ChatStreamText):
            shown += event.delta
    return shown


_POLICY_SOURCE = {
    "title": "policy.pdf",
    "heading": "Attendance",
    "content": "Policy details.",
    "source_locations": [],
}


@pytest.mark.parametrize(
    "block",
    [
        {"kind": "grounded", "text": "Staff badge in.", "source_ids": ["source-1"]},
        {"source_ids": ["source-1"], "kind": "grounded", "text": "Staff badge in."},
        {"kind": "grounded", "source_ids": ["source-1"], "text": "Staff badge in."},
    ],
)
def test_streamed_text_matches_final_answer_in_any_field_order(monkeypatch, block) -> None:
    payload = json.dumps({"blocks": [block, {"source_ids": [], "text": "Ask HR.", "kind": "general"}]})

    async def stream_text(*args, **kwargs):
        for index in range(0, len(payload), 5):
            yield payload[index:index + 5]

    monkeypatch.setattr(chat_service, "stream_structured_text", stream_text)
    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: [_POLICY_SOURCE])
    monkeypatch.setattr(chat_service, "generate_structured", _no_generation)

    async def collect():
        return [event async for event in chat_service.stream_answer_from_knowledge("policy", "staff")]

    events = asyncio.run(collect())
    completed = next(e for e in events if isinstance(e, chat_service.ChatStreamCompleted))

    assert completed.response.answer == "Staff badge in. [1]\n\nAsk HR."
    assert _visible_text(events) == completed.response.answer
    assert not any(isinstance(e, chat_service.ChatStreamReset) for e in events)


def test_stream_resets_shown_text_before_the_plain_text_answer(monkeypatch) -> None:
    events = _stream_events(monkeypatch, ['Note "text":"Shown" and the rest.'])
    completed = next(e for e in events if isinstance(e, chat_service.ChatStreamCompleted))

    assert next(e for e in events if isinstance(e, chat_service.ChatStreamText)).delta == "Shown"
    assert _visible_text(events) == completed.response.answer
    assert completed.response.answer.startswith('Note "text":"Shown" and the rest.')


class _StreamRecorder:
    def __init__(self, monkeypatch, events, persist_error: Exception | None = None) -> None:
        from app.chat import routes as chat_routes

        self.routes = chat_routes
        self.saved: list[tuple] = []
        self.new_conversation_ids: list = []
        self.request = None
        self.audited: list[tuple] = []
        self.closed = False

        async def stream_answer(*args, **kwargs):
            try:
                for event in events:
                    if isinstance(event, Exception):
                        raise event
                    yield event
            finally:
                self.closed = True

        def persist(
            query, user_id, response, conversation_id=None, status="completed", metrics=None,
            new_conversation_id=None, replace_ids=None,
        ):
            if persist_error:
                raise persist_error
            self.saved.append((response.answer, status, metrics))
            self.new_conversation_ids.append(new_conversation_id)
            return response.model_copy(update={"conversation_id": uuid4(), "messages": []})

        monkeypatch.setattr(chat_routes.chat_service, "stream_answer_from_knowledge", stream_answer)
        monkeypatch.setattr(chat_routes.chat_service, "persist_response", persist)
        monkeypatch.setattr(chat_routes.chat_service, "model_name", lambda: "test-model")
        monkeypatch.setattr(
            chat_routes.chat_service,
            "audit_unsaved_turn",
            lambda event, user_id, conversation_id, metadata: self.audited.append((event, metadata)),
        )

    def generator(self):
        from app.chat.schemas import ChatRequest

        return self.routes._stream_events(
            self.request or ChatRequest(query="hello"), {"id": uuid4(), "role": "staff"}, []
        )

    def run(self) -> list[dict]:
        async def collect():
            return [chunk async for chunk in self.generator()]

        return [json.loads(chunk[6:]) for chunk in asyncio.run(collect()) if chunk != "data: [DONE]\n\n"]

    def stop_after(self, chunks: int) -> None:
        """Read some events, then cancel the request the way a client disconnect does."""

        async def drive():
            stream = self.generator()
            for _ in range(chunks):
                await anext(stream)
            with pytest.raises(asyncio.CancelledError):
                await stream.athrow(asyncio.CancelledError())

        asyncio.run(drive())


def _done(answer: str):
    return chat_service.ChatStreamCompleted(chat_service.ChatResponse(answer=answer, refused=False, citations=[]))


def test_stop_while_streaming_saves_the_shown_text_as_stopped(monkeypatch) -> None:
    recorder = _StreamRecorder(monkeypatch, [
        chat_service.ChatStreamStatus("Writing response..."),
        chat_service.ChatStreamText("Partial "),
        chat_service.ChatStreamText("answer"),
        _done("never reached"),
    ])

    recorder.stop_after(3)

    assert recorder.closed
    assert [(answer, status) for answer, status, _ in recorder.saved] == [("Partial answer", "stopped")]
    assert recorder.saved[0][2]["model"] == "test-model"
    assert recorder.saved[0][2]["ttft_ms"] is not None


def test_stop_right_after_a_reset_saves_nothing(monkeypatch) -> None:
    recorder = _StreamRecorder(monkeypatch, [
        chat_service.ChatStreamText("Broken"),
        chat_service.ChatStreamReset(),
        _done("Fallback"),
    ])

    recorder.stop_after(2)

    assert recorder.closed
    assert recorder.saved == []
    assert [event for event, _ in recorder.audited] == ["chat_turn_stopped"]


def test_stop_before_the_first_token_saves_nothing(monkeypatch) -> None:
    recorder = _StreamRecorder(monkeypatch, [
        chat_service.ChatStreamStatus("Thinking..."),
        chat_service.ChatStreamText("Too late"),
    ])

    recorder.stop_after(1)

    assert recorder.saved == []
    assert recorder.audited[0][1]["ttft_ms"] is None


def test_completed_stream_records_model_and_time_to_first_token(monkeypatch) -> None:
    recorder = _StreamRecorder(monkeypatch, [chat_service.ChatStreamText("Hi"), _done("Hi")])

    events = recorder.run()

    assert [event["type"] for event in events] == ["text", "done"]
    assert recorder.saved[0][1] == "completed"
    assert recorder.saved[0][2]["model"] == "test-model"


def test_save_failure_sends_an_error_event_and_is_audited(monkeypatch) -> None:
    recorder = _StreamRecorder(
        monkeypatch, [chat_service.ChatStreamText("Hi"), _done("Hi")], persist_error=OSError("db down")
    )

    events = recorder.run()

    assert events[-1] == {"type": "error", "message": "We could not save this answer. Please try again."}
    assert recorder.audited == [("chat_turn_failed", {"model": "test-model", "ttft_ms": recorder.audited[0][1]["ttft_ms"], "reason": "save_failed"})]


def test_model_failure_sends_its_message_and_saves_nothing(monkeypatch) -> None:
    recorder = _StreamRecorder(
        monkeypatch, [chat_service.ChatStreamText("Cut "), chat_service.AIModelError("Please try again.")]
    )

    events = recorder.run()

    assert events[-1] == {"type": "error", "message": "Please try again."}
    assert recorder.saved == []
    assert recorder.audited[0][0] == "chat_turn_failed"


def test_unexpected_stream_failure_sends_an_error_event_and_is_audited(monkeypatch) -> None:
    recorder = _StreamRecorder(monkeypatch, [chat_service.ChatStreamText("Hi"), KeyError("boom")])

    events = recorder.run()

    assert events[-1] == {"type": "error", "message": "The answer could not be generated."}
    assert recorder.audited[0][0] == "chat_turn_failed"
    assert recorder.audited[0][1]["reason"] == "KeyError"


def test_stop_in_a_new_conversation_saves_under_the_client_chosen_id(monkeypatch) -> None:
    from app.chat.schemas import ChatRequest

    recorder = _StreamRecorder(monkeypatch, [chat_service.ChatStreamText("Partial"), _done("never")])
    new_id = uuid4()
    recorder.request = ChatRequest(query="hello", new_conversation_id=new_id)

    recorder.stop_after(1)

    assert recorder.new_conversation_ids == [new_id]


def test_history_and_question_share_one_character_budget() -> None:
    history = [{"role": "user", "content": "x" * 1000}] * 20
    query = "q" * 1500

    messages = chat_service._conversation_messages(query, history, "system")

    assert sum(len(message.text) for message in messages[1:]) == chat_service._HISTORY_MAX_CHARS
    assert messages[-1].text == query


def test_message_that_overflows_the_budget_is_cut_not_dropped() -> None:
    history = [
        {"role": "user", "content": "Write the report."},
        {"role": "assistant", "content": "r" * 50_000},
    ]

    messages = chat_service._conversation_messages("Shorten it.", history, "system")

    assert [message.text[0] for message in messages[1:]] == ["r", "S"]
    assert len(messages[1].text) == chat_service._HISTORY_MAX_CHARS - len("Shorten it.")


def test_a_long_question_is_not_sent_again_whole_as_the_search_query() -> None:
    context = chat_service._source_context("search_knowledge_base", "§" * 4000, {})

    assert context.count("§") == chat_service._SEARCH_QUERY_MAX_CHARS


def test_stream_keeps_the_shown_text_when_the_reply_is_cut_off(monkeypatch) -> None:
    results = [{"title": "report.pdf", "heading": "Sales", "snippet": "Sales rose.", "source_locations": []}]
    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: results)

    events = _stream_events(monkeypatch, [
        '{"blocks":[{"kind":"grounded","text":"Sales rose.","source_ids":["source-1"]},',
        '{"kind":"grounded","text":"And then',
    ])
    completed = next(e for e in events if isinstance(e, chat_service.ChatStreamCompleted))

    assert completed.response.answer.startswith("Sales rose. [1]\n\nAnd then")
    # The unfinished block never reached its source_ids, so the reader is told it has none.
    assert "cut off" in completed.response.answer and "no sources" in completed.response.answer
    assert _visible_text(events) == completed.response.answer
    assert [citation.title for citation in completed.response.citations] == ["report.pdf"]
    assert completed.response.refused is False


_WEAK_EVIDENCE = [{
    "title": "secret.pdf", "heading": "Pay", "snippet": "Salaries.", "source_locations": [], "rerank_score": 0.01,
}]


@pytest.mark.parametrize("results", [[], _WEAK_EVIDENCE], ids=["empty", "weak"])
def test_evidence_floor_of_zero_turns_the_check_off(monkeypatch, results) -> None:
    monkeypatch.setattr(chat_service.settings, "search_evidence_floor", 0)

    assert chat_service._weak_evidence(results) is False


@pytest.mark.parametrize("path", ["plain", "stream"])
@pytest.mark.parametrize("results", [[], _WEAK_EVIDENCE], ids=["empty", "weak"])
def test_document_question_without_evidence_is_refused_without_an_answer_call(monkeypatch, path, results) -> None:
    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: results)
    monkeypatch.setattr(chat_service, "_needs_documents", lambda *args: True)
    monkeypatch.setattr(chat_service, "generate_structured", _no_generation)
    monkeypatch.setattr(chat_service, "stream_structured_text", _no_generation)

    response = _ask(path, "What is the CEO's home address?")

    assert response.refused is True
    assert response.answer == chat_service._clarifying_answer(results)
    assert response.citations == []


def test_clarifying_answer_names_the_closest_documents_once() -> None:
    titles = ["a.pdf", "a.pdf", "b`.pdf", "c.pdf", "d.pdf"]

    answer = chat_service._clarifying_answer([{"title": title} for title in titles])

    assert "- `a.pdf`\n- `b.pdf`\n- `c.pdf`\n\n" in answer
    assert "d.pdf" not in answer
    assert answer.count("a.pdf") == 1


def test_clarifying_answer_still_asks_back_without_results() -> None:
    answer = chat_service._clarifying_answer([])

    assert "?" in answer and "upload" in answer


def test_stream_shows_the_clarifying_answer(monkeypatch) -> None:
    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: _WEAK_EVIDENCE)
    monkeypatch.setattr(chat_service, "_needs_documents", lambda *args: True)

    events = _stream_events(monkeypatch, [])

    assert _visible_text(events) == chat_service._clarifying_answer(_WEAK_EVIDENCE)
    assert "secret.pdf" in _visible_text(events)


@pytest.mark.parametrize("path", ["plain", "stream"])
def test_other_question_without_evidence_still_reaches_the_model(monkeypatch, path) -> None:
    async def stream_text(messages, output_type):
        yield ANSWER_JSON

    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: _WEAK_EVIDENCE)
    monkeypatch.setattr(
        chat_service,
        "generate_structured",
        lambda messages, output_type: chat_service.ModelAnswer(
            blocks=[{"kind": "general", "text": "Answer", "source_ids": []}]
        ),
    )
    monkeypatch.setattr(chat_service, "stream_structured_text", stream_text)

    response = _ask(path, "Summarize the documents")

    assert response.answer == "Answer" and response.refused is False


@pytest.mark.parametrize("score", [0.9, None], ids=["strong", "reranker down"])
def test_usable_evidence_reaches_the_model_without_the_classifier(monkeypatch, score) -> None:
    prompts = []

    def generate(messages, output_type):
        prompts.append(messages[-1].text)
        return chat_service.ModelAnswer(blocks=[{"kind": "general", "text": "Answer", "source_ids": []}])

    results = [{**_WEAK_EVIDENCE[0], "rerank_score": score}]
    monkeypatch.setattr(chat_service, "search_knowledge", lambda *args: results)
    monkeypatch.setattr(chat_service, "_needs_documents", _no_generation)
    monkeypatch.setattr(chat_service, "generate_structured", generate)

    assert chat_service.answer_from_knowledge("Who is paid what?", "staff").refused is False
    assert "secret.pdf" in prompts[-1] and "rerank_score" not in prompts[-1]


def test_web_search_results_are_not_gated(monkeypatch) -> None:
    def generate(messages, output_type):
        if output_type is chat_service.SearchPlan:
            return _search_plan("web_search", "latest news")
        return chat_service.ModelAnswer(blocks=[{"kind": "general", "text": "Answer", "source_ids": []}])

    monkeypatch.setattr(chat_service, "generate_structured", generate)
    monkeypatch.setattr(chat_service, "perform_web_search", lambda query: [])
    monkeypatch.setattr(chat_service, "_needs_documents", _no_generation)

    assert chat_service.answer_from_knowledge("Any news?", "staff", web_search=True).refused is False


def test_needs_documents_reads_the_classifier_with_recent_history(monkeypatch) -> None:
    seen = []

    def generate(messages, output_type):
        seen.append(messages)
        return output_type(scope="organization_fact")

    monkeypatch.setattr(chat_service, "generate_structured", generate)
    history = [{"role": "user", "content": str(index)} for index in range(10)]

    assert _real_needs_documents("And its risks?", history, None) is True
    assert [message.text for message in seen[0][1:]] == ["6", "7", "8", "9", "And its risks?"]


def test_needs_documents_answers_normally_when_the_classifier_fails(monkeypatch) -> None:
    def fail(messages, output_type):
        raise chat_service.AIModelError("down")

    monkeypatch.setattr(chat_service, "generate_structured", fail)

    assert _real_needs_documents("hello", None, None) is False
