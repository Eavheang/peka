import httpx
import pytest

from app.engine import llm_client


@pytest.mark.parametrize("allow_tools", [True, False])
def test_tool_completion_sends_controlled_payload(monkeypatch, allow_tools):
    sent = []
    message = {"role": "assistant", "content": None, "tool_calls": [{"id": "call-1"}]}

    def post(url, **kwargs):
        sent.append(kwargs["json"])
        return httpx.Response(200, json={"choices": [{"message": message}]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(llm_client.httpx, "post", post)
    tools = [{"type": "function", "function": {"name": "search_knowledge_base"}}]
    assert llm_client.chat_tool_completion([{"role": "user", "content": "question"}], tools, allow_tools=allow_tools) == message
    assert sent[0]["tools"] == tools
    assert sent[0]["tool_choice"] == ("auto" if allow_tools else "none")
    assert sent[0]["parallel_tool_calls"] is False
    if not allow_tools:
        assert sent[0]["response_format"] == {"type": "json_object"}


def test_tool_completion_can_require_a_specific_tool(monkeypatch):
    sent = []
    message = {"role": "assistant", "content": None, "tool_calls": []}

    def post(url, **kwargs):
        sent.append(kwargs["json"])
        return httpx.Response(200, json={"choices": [{"message": message}]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(llm_client.httpx, "post", post)
    llm_client.chat_tool_completion(
        [{"role": "user", "content": "question"}],
        [{"type": "function", "function": {"name": "web_search"}}],
        required_tool="web_search",
    )

    assert sent[0]["tool_choice"] == {
        "type": "function",
        "function": {"name": "web_search"},
    }


@pytest.mark.parametrize("payload", [{}, {"choices": []}, {"choices": [{"message": "invalid"}]}])
def test_malformed_provider_response_is_a_safe_error(monkeypatch, payload):
    monkeypatch.setattr(llm_client.httpx, "post", lambda url, **kwargs: httpx.Response(
        200, json=payload, request=httpx.Request("POST", url),
    ))
    with pytest.raises(llm_client.LLMError):
        llm_client.chat_tool_completion([], [])


def test_existing_text_completion_remains_compatible(monkeypatch):
    sent = []

    def post(url, **kwargs):
        sent.append(kwargs["json"])
        return httpx.Response(200, json={"choices": [{"message": {"content": "converted text"}}]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(llm_client.httpx, "post", post)
    assert llm_client.chat_completion([], json_mode=True) == "converted text"
    assert "tools" not in sent[0]
    assert sent[0]["response_format"] == {"type": "json_object"}


def test_provider_failure_does_not_leak_response_body(monkeypatch):
    monkeypatch.setattr(llm_client.httpx, "post", lambda url, **kwargs: httpx.Response(
        500, text="private provider details", request=httpx.Request("POST", url),
    ))
    with pytest.raises(llm_client.LLMError, match="HTTP 500") as error:
        llm_client.chat_tool_completion([], [])
    assert "private" not in str(error.value)
