import asyncio
import json

import ai
import pytest

from pydantic import ValidationError

from app.chat.service import ModelAnswer
from app.engine import ai_runtime
from app.engine.ai_runtime import (
    AIModelError,
    _repair_json_strings,
    generate_structured,
    parse_structured_output,
    stream_structured_text,
)


def test_generate_structured_returns_validated_pydantic_output() -> None:
    model = ai.testing.FakeModel([
        ai.user_message("question"),
        ai.assistant_message(json.dumps({
            "blocks": [{"kind": "general", "text": "Answer", "source_ids": []}]
        })),
    ])

    result = generate_structured(
        [ai.user_message("question")], ModelAnswer, model=model
    )

    assert isinstance(result, ModelAnswer)
    assert result.blocks[0].text == "Answer"


def test_generate_structured_rejects_non_structured_model_output() -> None:
    model = ai.testing.FakeModel([
        ai.user_message("question"),
        ai.assistant_message("Here is the answer: ```json {\"bad\": true}```"),
    ])

    with pytest.raises(AIModelError, match="invalid structured"):
        generate_structured(
            [ai.user_message("question")], ModelAnswer, model=model
        )
    assert len(model.calls) == 2, "should retry once before failing"


def test_generate_structured_accepts_json_markdown_fence() -> None:
    model = ai.testing.FakeModel([
        ai.user_message("question"),
        ai.assistant_message(
            '```json\n{"blocks":[{"kind":"general","text":"Answer","source_ids":[]}]}\n```'
        ),
    ])

    result = generate_structured(
        [ai.user_message("question")], ModelAnswer, model=model
    )

    assert result.blocks[0].text == "Answer"


def test_stream_structured_text_yields_model_text_deltas() -> None:
    model = ai.testing.FakeModel([
        ai.user_message("question"),
        ai.assistant_message(json.dumps({
            "blocks": [{"kind": "general", "text": "Answer", "source_ids": []}]
        })),
    ])

    async def collect() -> list[str]:
        return [
            chunk
            async for chunk in stream_structured_text(
                [ai.user_message("question")], ModelAnswer, model=model
            )
        ]

    chunks = asyncio.run(collect())

    assert "Answer" in "".join(chunks)


ANSWER = json.dumps({"blocks": [{"kind": "general", "text": "Answer", "source_ids": []}]})


def _fake_model() -> "ai.testing.FakeModel":
    return ai.testing.FakeModel([ai.user_message("question"), ai.assistant_message(ANSWER)])


def _flaky_stream(
    monkeypatch, plan: list[str], message: str = "The operation was aborted"
) -> list[str]:
    """Make ai.stream fail as planned per call: "ok", "fail" (on entry) or "fail_after_text"."""
    real_stream, calls = ai.stream, []

    class Flaky:
        def __init__(self, inner, mode):
            self.inner, self.mode, self.stream = inner, mode, None

        async def __aenter__(self):
            if self.mode == "fail":
                raise ai.errors.ProviderAPIError(message)
            self.stream = await self.inner.__aenter__()
            return self

        async def __aexit__(self, *exc):
            return await self.inner.__aexit__(*exc)

        def __getattr__(self, name):
            return getattr(self.stream, name)

        async def __aiter__(self):
            async for event in self.stream:
                yield event
                if self.mode == "fail_after_text" and isinstance(event, ai.events.TextDelta):
                    raise ai.errors.ProviderAPIError(message)

    def fake(*args, **kwargs):
        mode = plan[len(calls)] if len(calls) < len(plan) else "ok"
        calls.append(mode)
        return Flaky(real_stream(*args, **kwargs), mode)

    monkeypatch.setattr(ai, "stream", fake)
    return calls


def _collect_stream(model) -> list[str]:
    async def collect() -> list[str]:
        return [
            chunk
            async for chunk in stream_structured_text(
                [ai.user_message("question")], ModelAnswer, model=model
            )
        ]

    return asyncio.run(collect())


def test_stream_retries_a_provider_failure_before_any_text(monkeypatch) -> None:
    calls = _flaky_stream(monkeypatch, ["fail", "ok"])

    assert "Answer" in "".join(_collect_stream(_fake_model()))
    assert calls == ["fail", "ok"]


def test_stream_does_not_retry_after_text_was_already_streamed(monkeypatch) -> None:
    calls = _flaky_stream(monkeypatch, ["fail_after_text", "ok"])

    with pytest.raises(AIModelError, match="provider request failed"):
        _collect_stream(_fake_model())
    assert calls == ["fail_after_text"], "a retry would repeat text the user already saw"


def test_stream_gives_up_after_a_second_provider_failure(monkeypatch) -> None:
    calls = _flaky_stream(monkeypatch, ["fail", "fail", "ok"])

    with pytest.raises(AIModelError, match="provider request failed"):
        _collect_stream(_fake_model())
    assert calls == ["fail", "fail"]


def test_generate_structured_retries_a_provider_failure(monkeypatch) -> None:
    calls = _flaky_stream(monkeypatch, ["fail", "ok"])

    result = generate_structured([ai.user_message("question")], ModelAnswer, model=_fake_model())

    assert result.blocks[0].text == "Answer"
    assert calls == ["fail", "ok"]


@pytest.mark.parametrize(
    "message, waits",
    [("Context size has been exceeded.", True), ("The operation was aborted", False)],
)
@pytest.mark.parametrize(
    "call",
    [
        lambda: _collect_stream(_fake_model()),
        lambda: generate_structured([ai.user_message("question")], ModelAnswer, model=_fake_model()),
    ],
    ids=["stream", "generate"],
)
def test_only_a_context_overflow_delays_the_retry(monkeypatch, call, message, waits) -> None:
    calls = _flaky_stream(monkeypatch, ["fail", "ok"], message)
    real_sleep, delays = asyncio.sleep, []

    async def sleep(delay, *args):
        delays.append(delay)
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", sleep)

    call()

    assert calls == ["fail", "ok"]
    assert (ai_runtime._CONTEXT_FULL_RETRY_SECONDS in delays) is waits


QUOTED = 'Systems moved toward "agentic" workflows and use "reranking" to sort.'


def _raw(*texts: str, ids: str = "[]") -> str:
    blocks = ",".join(f'{{"kind":"general","text":"{t}","source_ids":{ids}}}' for t in texts)
    return '{"blocks":[' + blocks + "]}"


def test_parse_repairs_unescaped_quotes_inside_text() -> None:
    result = parse_structured_output(_raw(QUOTED, ids='["source-1"]'), ModelAnswer)

    assert result.blocks[0].text == QUOTED
    assert result.blocks[0].source_ids == ["source-1"]


def test_parse_repairs_every_block_and_keeps_the_structure() -> None:
    result = parse_structured_output(_raw('First "one".', 'Second "two", then more.'), ModelAnswer)

    assert [b.text for b in result.blocks] == ['First "one".', 'Second "two", then more.']


def test_parse_repairs_raw_line_breaks_inside_text() -> None:
    raw = '{"blocks":[{"kind":"general","text":"line one\nline two\tend","source_ids":[]}]}'

    assert parse_structured_output(raw, ModelAnswer).blocks[0].text == "line one\nline two\tend"


def test_parse_repairs_a_quote_before_a_colon_or_comma_in_prose() -> None:
    text = 'The "Naive RAG": a baseline, he said "hi", then left.'

    assert parse_structured_output(_raw(text), ModelAnswer).blocks[0].text == text


def test_parse_repairs_broken_json_inside_a_markdown_fence() -> None:
    fenced = "```json\n" + _raw(QUOTED) + "\n```"

    assert parse_structured_output(fenced, ModelAnswer).blocks[0].text == QUOTED


def test_repair_leaves_valid_json_untouched() -> None:
    valid = json.dumps({"blocks": [{"kind": "general", "text": 'He said "hi"\nand left', "source_ids": []}]})

    assert _repair_json_strings(valid) == valid
    assert parse_structured_output(valid, ModelAnswer).blocks[0].text == 'He said "hi"\nand left'


@pytest.mark.parametrize("raw", ["Just a plain prose answer.", '{"blocks": [', '{"blocks": []}'])
def test_parse_still_rejects_output_that_cannot_be_repaired(raw: str) -> None:
    with pytest.raises(ValidationError):
        parse_structured_output(raw, ModelAnswer)
