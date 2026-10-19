"""Provider-independent chat/LLM access for LLM-backed requirement extraction.

The model/provider is fully externalized (no hardcoded model name). Providers:

* :class:`FakeChatProvider` — deterministic, offline; used by unit tests.
* :class:`OpenAICompatibleChatProvider` — ``/chat/completions`` (Ollama, OpenAI).
* :class:`AnthropicChatProvider` — Claude Messages API.

Transient failures (HTTP 429/5xx, timeouts) are retried with bounded backoff and
then raised as :class:`ChatError`, so callers surface a visible failure instead of
pretending extraction succeeded. Secrets are never logged or embedded in errors.
"""

from __future__ import annotations

import time
import logging
import os
from typing import Callable, Protocol, runtime_checkable

import httpx

from app.config import ConfigError, Settings
from app.throttle import MODEL_REQUEST_THROTTLE, response_retry_after, retry_delay_seconds

ANTHROPIC_VERSION = "2023-06-01"
logger = logging.getLogger(__name__)

DEFAULT_BASE_URLS = {
    "anthropic": "https://api.anthropic.com/v1",
    "openai": "https://api.openai.com/v1",
    "openai_compatible": "https://api.openai.com/v1",
    "ollama": "http://localhost:11434/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


class ChatError(RuntimeError):
    """Base class for chat/LLM failures."""


class ChatConfigError(ChatError, ConfigError):
    """The chat provider is not configured correctly."""


class ChatRequestError(ChatError):
    """A retryable request failed after retries were exhausted."""


class ChatResponseError(ChatError):
    """The provider returned an unusable payload."""


@runtime_checkable
class ChatProvider(Protocol):
    model_name: str

    def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        ...


class FakeChatProvider:
    """Deterministic provider for tests and dry runs."""

    def __init__(
        self,
        model_name: str = "fake-chat",
        response: str = "[]",
        responder: Callable[[str, str], str] | None = None,
    ) -> None:
        self.model_name = model_name
        self.response = response
        self.responder = responder
        self.calls: list[dict] = []

    def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        self.calls.append({"system": system, "user": user, "temperature": temperature, "max_tokens": max_tokens})
        if self.responder is not None:
            return self.responder(system, user)
        return self.response


class _HTTPChatProvider:
    def __init__(
        self,
        model_name: str,
        base_url: str,
        *,
        timeout: float = 60.0,
        max_retries: int = 1,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        client: httpx.Client | None = None,
        sleeper: Callable[[float], None] | None = None,
        backoff_seconds: float = 1.0,
    ) -> None:
        if not model_name:
            raise ChatConfigError("a chat model name is required")
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.max_tokens = max(1, max_tokens)
        self.temperature = temperature
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None
        self._sleeper = sleeper or time.sleep
        self._backoff_seconds = backoff_seconds
        self._request_delay_seconds = max(0.0, float(os.getenv("LLM_REQUEST_DELAY_MS", "0")) / 1000)
        self.retry_count = 0
        self.usage_totals: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}
        self.provider_reported_cost_usd: float | None = None

    def _record_usage(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            return
        for target, names in (
            ("input_tokens", ("input_tokens", "prompt_tokens")),
            ("output_tokens", ("output_tokens", "completion_tokens")),
        ):
            for name in names:
                value = usage.get(name)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    self.usage_totals[target] += int(value)
                    break
        cost = usage.get("cost")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool):
            self.provider_reported_cost_usd = (self.provider_reported_cost_usd or 0.0) + float(cost)

    def _post(self, path: str, *, json: dict, headers: dict) -> str:
        self.retry_count = 0
        attempts = self.max_retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                with MODEL_REQUEST_THROTTLE.request():
                    response = self._client.post(f"{self.base_url}{path}", json=json, headers=headers)
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < attempts - 1:
                    self.retry_count += 1
                    logger.warning("llm retry attempt=%d/%d error=%s", attempt + 1, attempts - 1, type(exc).__name__)
                    self._sleeper(retry_delay_seconds(None, attempt, self._backoff_seconds))
                    continue
                raise ChatRequestError(f"chat request failed after {attempts} attempt(s): {exc}") from exc

            if response.status_code == 429 or 500 <= response.status_code < 600:
                last_error = ChatResponseError(f"retryable HTTP {response.status_code}")
                if attempt < attempts - 1:
                    self.retry_count += 1
                    logger.warning("llm retry attempt=%d/%d status=%d", attempt + 1, attempts - 1, response.status_code)
                    self._sleeper(retry_delay_seconds(response_retry_after(response), attempt, self._backoff_seconds))
                    continue
                raise ChatResponseError(f"chat request failed with HTTP {response.status_code}")
            if response.status_code >= 400:
                raise ChatResponseError(f"chat request failed with HTTP {response.status_code}")

            payload = response.json()
            self._record_usage(payload)
            return self._extract(payload)

        raise ChatRequestError(f"chat request failed: {last_error}")

    def _extract(self, payload: object) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


class AnthropicChatProvider(_HTTPChatProvider):
    def __init__(self, model_name: str, api_key: str, base_url: str = "https://api.anthropic.com/v1", **kwargs) -> None:
        if not api_key:
            raise ChatConfigError("LLM_API_KEY is required for the anthropic provider")
        super().__init__(model_name, base_url, **kwargs)
        self.api_key = api_key

    def complete(self, system: str, user: str, *, temperature: float | None = None, max_tokens: int | None = None) -> str:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }
        body = {
            "model": self.model_name,
            "max_tokens": int(max_tokens or self.max_tokens),
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "temperature": self.temperature if temperature is None else temperature,
        }
        return self._post("/messages", json=body, headers=headers)

    def _extract(self, payload: object) -> str:
        blocks = payload.get("content") if isinstance(payload, dict) else None
        if not isinstance(blocks, list):
            raise ChatResponseError("anthropic response is missing 'content'")
        text = "".join(
            block.get("text", "") for block in blocks if isinstance(block, dict) and block.get("type") == "text"
        ).strip()
        if not text:
            raise ChatResponseError("anthropic response contained no text")
        return text


class OpenAICompatibleChatProvider(_HTTPChatProvider):
    def __init__(self, model_name: str, base_url: str = "https://api.openai.com/v1", api_key: str | None = None, **kwargs) -> None:
        super().__init__(model_name, base_url, **kwargs)
        self.api_key = api_key

    def complete(self, system: str, user: str, *, temperature: float | None = None, max_tokens: int | None = None) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": int(max_tokens or self.max_tokens),
            "temperature": self.temperature if temperature is None else temperature,
        }
        return self._post("/chat/completions", json=body, headers=headers)

    def _extract(self, payload: object) -> str:
        choices = payload.get("choices") if isinstance(payload, dict) else None
        if not isinstance(choices, list) or not choices:
            raise ChatResponseError("chat payload is missing choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise ChatResponseError("chat payload is missing message content")
        return content


def build_chat_provider(
    settings: Settings,
    *,
    client: httpx.Client | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> ChatProvider:
    provider = (settings.llm_provider or "").lower()
    if provider in {"fake", "test"}:
        return FakeChatProvider()

    model = settings.llm_model
    provider_keys = {
        "openrouter": settings.openrouter_api_key or os.environ.get("OPENROUTER_API_KEY"),
        "groq": settings.groq_api_key or os.environ.get("GROQ_API_KEY"),
        "gemini": settings.gemini_api_key or os.environ.get("GEMINI_API_KEY"),
        "google": settings.gemini_api_key or os.environ.get("GEMINI_API_KEY"),
        "anthropic": settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY"),
    }
    api_key = provider_keys.get(provider) or settings.llm_api_key
    base_url = (settings.llm_base_url or DEFAULT_BASE_URLS.get(provider, "")).rstrip("/")

    if provider == "anthropic":
        if not model:
            raise ChatConfigError("LLM_MODEL is required for the anthropic provider")
        if not api_key:
            raise ChatConfigError("LLM_API_KEY is required for the anthropic provider")
        return AnthropicChatProvider(
            model,
            api_key,
            base_url or "https://api.anthropic.com/v1",
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
            client=client,
            sleeper=sleeper,
        )

    if provider in {"openai", "openai_compatible", "ollama", "compatible", "gemini", "google", "groq", "openrouter"}:
        if not model:
            raise ChatConfigError(f"LLM_MODEL is required for LLM_PROVIDER={provider!r}")
        if not base_url:
            raise ChatConfigError("LLM_BASE_URL could not be determined")
        return OpenAICompatibleChatProvider(
            model,
            base_url,
            api_key=api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
            client=client,
            sleeper=sleeper,
        )

    raise ChatConfigError(f"unsupported LLM_PROVIDER: {settings.llm_provider!r}")
