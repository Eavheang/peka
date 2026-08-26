import httpx

from app.config import settings


class LLMError(RuntimeError):
    pass


def chat_completion(messages: list[dict], *, json_mode: bool = False, timeout: int = 600) -> str:
    if settings.llm_api_key is None:
        raise LLMError("LLM_API_KEY is not configured")
    body: dict = {"model": settings.llm_model, "messages": messages}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    try:
        response = httpx.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key.get_secret_value()}"},
            json=body,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as error:
        raise LLMError(f"LLM request failed with HTTP {error.response.status_code}") from error
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
        raise LLMError("Unable to complete LLM request") from error
