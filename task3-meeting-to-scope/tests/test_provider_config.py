from app.config import Settings
from app.llm import OpenAICompatibleChatProvider, build_chat_provider


def test_openrouter_provider_uses_specific_key_and_default_url():
    settings = Settings(
        llm_provider="openrouter",
        llm_model="openrouter/test-model",
        openrouter_api_key="openrouter-test-only",
        llm_api_key="generic-test-only",
        llm_base_url=None,
    )
    provider = build_chat_provider(settings)
    assert isinstance(provider, OpenAICompatibleChatProvider)
    assert provider.base_url == "https://openrouter.ai/api/v1"
    assert provider.api_key == "openrouter-test-only"


def test_groq_provider_uses_specific_key_and_default_url():
    settings = Settings(
        llm_provider="groq",
        llm_model="test-model",
        groq_api_key="groq-test-only",
        llm_base_url=None,
    )
    provider = build_chat_provider(settings)
    assert isinstance(provider, OpenAICompatibleChatProvider)
    assert provider.base_url == "https://api.groq.com/openai/v1"
    assert provider.api_key == "groq-test-only"
