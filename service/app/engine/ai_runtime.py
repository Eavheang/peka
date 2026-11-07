import asyncio
import logging
import re
from collections.abc import AsyncIterator
from typing import TypeVar

import ai
from ai.providers.openai import OpenAIChatCompletionsProtocol
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.workspace_settings import provider_config

logger = logging.getLogger(__name__)

StructuredOutput = TypeVar("StructuredOutput", bound=BaseModel)
_JSON_CODE_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)
_MAX_STRUCTURED_ATTEMPTS = 2
_CONTEXT_FULL_RETRY_SECONDS = 10.0  # about one answer on the minimum hardware


class AIModelError(RuntimeError):
    pass


def _model() -> tuple[ai.Model, ai.Provider]:
    config = provider_config()
    if not config["llm_api_key"]:
        raise AIModelError("LLM_API_KEY is not configured")

    provider = ai.get_provider(
        "openai",
        base_url=config["llm_base_url"],
        api_key=config["llm_api_key"],
        # Responses API (the "openai" default) breaks on llama.cpp with history.
        protocol=OpenAIChatCompletionsProtocol(),
    )
    return ai.Model(id=config["llm_model"], provider=provider), provider


def _inference_params(max_tokens: int | None = None) -> ai.InferenceRequestParams:
    return ai.InferenceRequestParams(
        output=ai.OutputParams(max_tokens=max_tokens or settings.llm_max_tokens)
    )


def first_error_line(error: ValidationError) -> str:
    """The parser's own message (e.g. "Invalid JSON: expected `,` or `}` at line 1 column 109")."""
    return " ".join(str(error).split("\n")[1:3]).strip()[:200]


def _skip_space(text: str, i: int) -> int:
    while i < len(text) and text[i] in " \t\r\n":
        i += 1
    return i


def _ends_json_string(text: str, after: int) -> bool:
    """Whether a quote followed by text[after:] closes a JSON string rather than being content."""
    i = _skip_space(text, after)
    if i >= len(text) or text[i] in "}]":
        return True
    if text[i] == ",":  # a comma leads to the next key or value
        i = _skip_space(text, i + 1)
        return i < len(text) and text[i] in '"{['
    if text[i] == ":":  # a key is followed by a value, not by more prose
        i = _skip_space(text, i + 1)
        return text.startswith(('"', "{", "[", "-", "true", "false", "null"), i) or text[i:i + 1].isdigit()
    return False


def _repair_json_strings(text: str) -> str:
    """Escape quotes and control characters that were left raw inside JSON strings.

    A quote inside a string only ends it when what follows is structural: `:`, `}`, `]`, the end
    of the text, or a `,` leading to the next key or value. Any other quote is content and is
    escaped, as are raw newlines and tabs. Already-escaped sequences are kept as written.
    """
    out: list[str] = []
    in_string, i, n = False, 0, len(text)
    while i < n:
        char = text[i]
        if not in_string:
            out.append(char)
            in_string = char == '"'
        elif char == "\\" and i + 1 < n:
            out.append(text[i:i + 2])
            i += 1
        elif char == '"':
            if _ends_json_string(text, i + 1):
                out.append(char)
                in_string = False
            else:
                out.append('\\"')
        elif char in "\n\r\t":
            out.append({"\n": "\\n", "\r": "\\r", "\t": "\\t"}[char])
        else:
            out.append(char)
        i += 1
    return "".join(out)


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
    except ValidationError as error:
        # Also tolerate a short preamble or trailing note around an otherwise
        # valid JSON object from an OpenAI-compatible local server.
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            raise
        candidate = candidate[start:end + 1]
        try:
            return output_type.model_validate_json(candidate)
        except ValidationError:
            pass
        # Weaker models often leave quotes ("like this") or line breaks unescaped inside a
        # long markdown string, which breaks otherwise complete JSON.
        try:
            return output_type.model_validate_json(_repair_json_strings(candidate))
        except ValidationError:
            raise error from None


async def _log_and_back_off(error: ai.AIError) -> None:
    logger.warning("AI provider request failed, retrying", exc_info=True)
    # llama.cpp: "Context size has been exceeded". An immediate retry would overflow again.
    if "context size" in str(error).lower():
        await asyncio.sleep(_CONTEXT_FULL_RETRY_SECONDS)


async def _run_structured_stream(
    model: ai.Model,
    messages: list[ai.messages.Message],
    output_type: type[StructuredOutput],
    max_tokens: int | None = None,
) -> StructuredOutput:
    async with ai.stream(
        model, messages, output_type=output_type, params=_inference_params(max_tokens)
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
            except ValidationError as error:
                text = stream.message.text
                message = first_error_line(error)
                if "EOF while parsing" in message:
                    message += " (reply cut off: likely hit the max output tokens limit)"
                logger.warning(
                    "Model returned invalid structured output for %s (%d chars): %s | start: %r | end: %r",
                    output_type.__name__, len(text), message, text[:300], text[-300:],
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
    max_tokens: int | None = None,
) -> StructuredOutput:
    provider: ai.Provider | None = None
    try:
        if model is None:
            model, provider = _model()

        for attempt in range(_MAX_STRUCTURED_ATTEMPTS):
            try:
                return await _run_structured_stream(model, messages, output_type, max_tokens)
            except (ValidationError, AIModelError) as error:
                # A second full generation would hold the model while others wait.
                raise AIModelError("Model returned an invalid structured response") from error
            except ai.AIError as error:
                # Providers (free tiers especially) sometimes abort a call; retry once.
                if attempt == _MAX_STRUCTURED_ATTEMPTS - 1:
                    raise
                await _log_and_back_off(error)
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

        for attempt in range(_MAX_STRUCTURED_ATTEMPTS):
            emitted = False
            try:
                async with ai.stream(
                    model, messages, output_type=output_type, params=_inference_params()
                ) as stream:
                    async for event in stream:
                        if isinstance(event, ai.events.TextDelta):
                            emitted = True
                            yield event.chunk
                return
            except ai.AIError as error:
                # Retry a provider failure once, but only if nothing was streamed yet: after
                # that a retry would repeat text the caller has already shown.
                if emitted or attempt == _MAX_STRUCTURED_ATTEMPTS - 1:
                    raise
                await _log_and_back_off(error)
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
    max_tokens: int | None = None,
) -> StructuredOutput:
    return asyncio.run(
        _generate_structured(messages, output_type, model=model, max_tokens=max_tokens)
    )
