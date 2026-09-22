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
