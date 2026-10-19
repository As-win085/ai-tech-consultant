import httpx
import pytest

from app.llm import AnthropicChatProvider, OpenAICompatibleChatProvider


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_openai_compatible_provider_accumulates_usage_and_cost():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "[{\"description\": \"ok\"}]"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 5, "cost": 0.000031},
            },
        )

    provider = OpenAICompatibleChatProvider(
        "m", "http://x/v1", api_key="k", client=make_client(handler)
    )
    provider.complete("s", "u")
    provider.complete("s", "u")
    assert provider.usage_totals == {"input_tokens": 24, "output_tokens": 10}
    assert provider.provider_reported_cost_usd == pytest.approx(0.000062)


def test_anthropic_provider_accumulates_usage_with_anthropic_field_names():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "[]"}],
                "usage": {"input_tokens": 7, "output_tokens": 3},
            },
        )

    provider = AnthropicChatProvider("claude-x", "k", client=make_client(handler))
    provider.complete("sys", "q")
    assert provider.usage_totals == {"input_tokens": 7, "output_tokens": 3}
    assert provider.provider_reported_cost_usd is None


def test_usage_stays_zero_when_payload_has_no_usage_field():
    def handler(request):
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "[]"}}]}
        )

    provider = OpenAICompatibleChatProvider(
        "m", "http://x/v1", client=make_client(handler)
    )
    provider.complete("s", "u")
    assert provider.usage_totals == {"input_tokens": 0, "output_tokens": 0}
    assert provider.provider_reported_cost_usd is None
