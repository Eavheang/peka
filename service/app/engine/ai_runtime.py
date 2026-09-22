import asyncio
import logging
import re
from collections.abc import AsyncIterator
from typing import TypeVar

import ai
from pydantic import BaseModel, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)

StructuredOutput = TypeVar("StructuredOutput", bound=BaseModel)
_JSON_CODE_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)
_MAX_STRUCTURED_ATTEMPTS = 2


class AIModelError(RuntimeError):
    pass


def _model() -> tuple[ai.Model, ai.Provider]:
    if not settings.llm_api_key.get_secret_value():
        raise AIModelError("LLM_API_KEY is not configured")

    provider = ai.get_provider(
        "openai",
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value(),
    )
    return ai.Model(id=settings.llm_model, provider=provider), provider


def _inference_params() -> ai.InferenceRequestParams:
    return ai.InferenceRequestParams(output=ai.OutputParams(max_tokens=settings.llm_max_tokens))


def parse_structured_output(
    raw_output: str,
    output_type: type[StructuredOutput],
) -> StructuredOutput:
    candidate = raw_output.strip()
    match = _JSON_CODE_FENCE.search(candidate)
    if match:
        candidate = match.group(1)

    try:
        return output_type.model_validate_json(candidate)
    except ValidationError:
        # Also tolerate a short preamble or trailing note around an otherwise
        # valid JSON object from an OpenAI-compatible local server.
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            raise
        return output_type.model_validate_json(candidate[start:end + 1])


async def _run_structured_stream(
    model: ai.Model,
    messages: list[ai.messages.Message],
    output_type: type[StructuredOutput],
) -> StructuredOutput:
    async with ai.stream(
        model, messages, output_type=output_type, params=_inference_params()
    ) as stream:
        async for _ in stream:
            pass
        try:
            output = stream.output
        except ValidationError:
            # Some OpenAI-compatible local servers ignore structured-output
            # mode and wrap the otherwise valid JSON in a Markdown fence.
            try:
                output = parse_structured_output(stream.message.text, output_type)
            except ValidationError:
                logger.warning(
                    "Model returned invalid structured output for %s: %r",
                    output_type.__name__, stream.message.text[:2000],
                )
                raise

    if not isinstance(output, output_type):
        raise AIModelError("Model returned an invalid structured response")
    return output


async def _generate_structured(
    messages: list[ai.messages.Message],
    output_type: type[StructuredOutput],
    *,
    model: ai.Model | None = None,
) -> StructuredOutput:
    provider: ai.Provider | None = None
    try:
        if model is None:
            model, provider = _model()

        for attempt in range(_MAX_STRUCTURED_ATTEMPTS):
            try:
                return await _run_structured_stream(model, messages, output_type)
            except (ValidationError, AIModelError) as error:
                if attempt == _MAX_STRUCTURED_ATTEMPTS - 1:
                    raise AIModelError(
                        "Model returned an invalid structured response"
                    ) from error
    except AIModelError:
        raise
    except ai.AIError as error:
        raise AIModelError("AI provider request failed") from error
    except Exception as error:
        raise AIModelError("AI generation failed") from error
    finally:
        if provider is not None:
            await provider.aclose()


async def stream_structured_text(
    messages: list[ai.messages.Message],
    output_type: type[StructuredOutput],
    *,
    model: ai.Model | None = None,
) -> AsyncIterator[str]:
    """Yield text deltas while asking the model for structured output.

    The caller is responsible for validating the completed text with
    :func:`parse_structured_output`. This lets a caller render safe previews
    while retaining the existing structured response contract at completion.
    """
    provider: ai.Provider | None = None
    try:
        if model is None:
            model, provider = _model()

        async with ai.stream(
            model, messages, output_type=output_type, params=_inference_params()
        ) as stream:
            async for event in stream:
                if isinstance(event, ai.events.TextDelta):
                    yield event.chunk
    except AIModelError:
        raise
    except ai.AIError as error:
        raise AIModelError("AI provider request failed") from error
    except Exception as error:
        raise AIModelError("AI generation failed") from error
    finally:
        if provider is not None:
            await provider.aclose()


def generate_structured(
    messages: list[ai.messages.Message],
    output_type: type[StructuredOutput],
    *,
    model: ai.Model | None = None,
) -> StructuredOutput:
    return asyncio.run(_generate_structured(messages, output_type, model=model))
