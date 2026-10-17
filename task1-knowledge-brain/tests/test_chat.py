import httpx
import pytest

from app.chat import (
    AnthropicChatProvider,
    ChatConfigError,
    ChatRequestError,
    ChatResponseError,
    FakeChatProvider,
    OpenAICompatibleChatProvider,
    build_chat_provider,
)
from app.settings import ChatSettings


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fake_provider_returns_default_abstention_json():
    provider = FakeChatProvider()
    raw = provider.complete("system", "user")
    assert "insufficient" in raw
    assert len(provider.calls) == 1


def test_fake_provider_uses_responder():
    provider = FakeChatProvider(responder=lambda s, u: f"{s}|{u}")
    assert provider.complete("S", "U") == "S|U"


def test_anthropic_provider_sends_auth_and_parses_text():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-api-key")
        seen["version"] = request.headers.get("anthropic-version")
        seen["body"] = request.read().decode()
        return httpx.Response(
            200, json={"content": [{"type": "text", "text": "hello"}]}
        )

    provider = AnthropicChatProvider(
        "claude-x", "secret-key", client=make_client(handler)
    )
    assert provider.complete("sys", "question") == "hello"
    assert seen["url"].endswith("/v1/messages")
    assert seen["key"] == "secret-key"
    assert seen["version"] == "2023-06-01"
    assert '"system" in seen["body"]'


def test_anthropic_rejects_malformed_payload():
    def handler(request):
        return httpx.Response(200, json={"content": []})

    provider = AnthropicChatProvider("m", "k", client=make_client(handler))
    with pytest.raises(ChatResponseError):
        provider.complete("s", "u")


def test_openai_compatible_provider_parses_message_content():
    def handler(request):
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "hi"}}]}
        )

    provider = OpenAICompatibleChatProvider(
        "llama", base_url="http://localhost:11434/v1", client=make_client(handler)
    )
    assert provider.complete("s", "u") == "hi"


def test_provider_retries_retryable_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, text="slow down")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    provider = OpenAICompatibleChatProvider(
        "m", "http://x/v1", max_retries=2, client=make_client(handler), sleeper=lambda _: None
    )
    assert provider.complete("s", "u") == "ok"
    assert calls["n"] == 2


def test_provider_raises_after_retries_exhausted():
    def handler(request):
        return httpx.Response(500, text="boom")

    provider = OpenAICompatibleChatProvider(
        "m", "http://x/v1", max_retries=1, client=make_client(handler), sleeper=lambda _: None
    )
    with pytest.raises(ChatResponseError):
        provider.complete("s", "u")


def test_provider_timeout_raises_request_error():
    def handler(request):
        raise httpx.ReadTimeout("timed out", request=request)

    provider = OpenAICompatibleChatProvider(
        "m", "http://x/v1", max_retries=1, client=make_client(handler), sleeper=lambda _: None
    )
    with pytest.raises(ChatRequestError):
        provider.complete("s", "u")


def test_provider_does_not_retry_non_retryable_error():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(400, text="bad request")

    provider = OpenAICompatibleChatProvider(
        "m", "http://x/v1", max_retries=3, client=make_client(handler), sleeper=lambda _: None
    )
    with pytest.raises(ChatResponseError):
        provider.complete("s", "u")
    assert calls["n"] == 1


def test_error_message_does_not_leak_api_key():
    def handler(request):
        return httpx.Response(401, text="unauthorized")

    provider = AnthropicChatProvider(
        "m", "super-secret-key", client=make_client(handler), sleeper=lambda _: None
    )
    with pytest.raises(ChatResponseError) as info:
        provider.complete("s", "u")
    assert "super-secret-key" not in str(info.value)


def test_factory_selects_fake():
    assert isinstance(build_chat_provider(ChatSettings(provider="fake")), FakeChatProvider)


def test_factory_anthropic_requires_model_and_key():
    with pytest.raises(ChatConfigError):
        build_chat_provider(ChatSettings(provider="anthropic"))
    with pytest.raises(ChatConfigError):
        build_chat_provider(ChatSettings(provider="anthropic", model="claude-x"))


def test_factory_anthropic_builds_with_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    provider = build_chat_provider(
        ChatSettings(provider="anthropic", model="claude-x", api_key="k")
    )
    assert isinstance(provider, AnthropicChatProvider)
    assert provider.base_url == "https://api.anthropic.com/v1"


def test_factory_anthropic_reads_anthropic_env_fallbacks(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-from-env")
    provider = build_chat_provider(ChatSettings(provider="anthropic"))
    assert isinstance(provider, AnthropicChatProvider)
    assert provider.model_name == "claude-from-env"


def test_factory_ollama_default_base_url():
    provider = build_chat_provider(
        ChatSettings(provider="ollama", model="llama3.2:1b")
    )
    assert provider.base_url == "http://localhost:11434/v1"


def test_factory_rejects_unknown_provider():
    with pytest.raises(ChatConfigError):
        build_chat_provider(ChatSettings(provider="nope"))
