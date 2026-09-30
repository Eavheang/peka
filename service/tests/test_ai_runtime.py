import asyncio
import json

import ai
import pytest

from app.chat.service import ModelAnswer
from app.engine.ai_runtime import AIModelError, generate_structured, stream_structured_text


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


def _flaky_stream(monkeypatch, plan: list[str]) -> list[str]:
    """Make ai.stream fail as planned per call: "ok", "fail" (on entry) or "fail_after_text"."""
    real_stream, calls = ai.stream, []

    class Flaky:
        def __init__(self, inner, mode):
            self.inner, self.mode, self.stream = inner, mode, None

        async def __aenter__(self):
            if self.mode == "fail":
                raise ai.errors.ProviderAPIError("The operation was aborted")
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
                    raise ai.errors.ProviderAPIError("The operation was aborted")

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
