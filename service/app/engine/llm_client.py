import httpx

from app.config import settings


class LLMError(RuntimeError):
    pass


def chat_completion(messages: list[dict], *, json_mode: bool = False, timeout: int = 600) -> str:
    message = _completion_message(messages, json_mode=json_mode, timeout=timeout)
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise LLMError("Model returned an empty response")
    return content


def chat_tool_completion(
    messages: list[dict], tools: list[dict], *, allow_tools: bool = True,
    required_tool: str | None = None,
) -> dict:
    if not allow_tools and required_tool is not None:
        raise LLMError("Cannot require a tool when tools are disabled")
    tool_choice = (
        {"type": "function", "function": {"name": required_tool}}
        if required_tool is not None
        else "auto" if allow_tools else "none"
    )
    return _completion_message(
        messages,
        json_mode=not allow_tools,
        tools=tools,
        tool_choice=tool_choice,
    )


def _completion_message(
    messages: list[dict], *, json_mode: bool = False, timeout: int = 600,
    tools: list[dict] | None = None, tool_choice: str | dict = "auto",
) -> dict:
    if settings.llm_api_key is None:
        raise LLMError("LLM_API_KEY is not configured")
    body: dict = {"model": settings.llm_model, "messages": messages}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if tools is not None:
        body.update(tools=tools, tool_choice=tool_choice, parallel_tool_calls=False)
    try:
        response = httpx.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key.get_secret_value()}"},
            json=body,
            timeout=timeout,
        )
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]
        if not isinstance(message, dict):
            raise LLMError("Model returned an invalid message")
        return message
    except httpx.HTTPStatusError as error:
        raise LLMError(f"LLM request failed with HTTP {error.response.status_code}") from error
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
        raise LLMError("Unable to complete LLM request") from error
