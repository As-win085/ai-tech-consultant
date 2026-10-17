"""Provider-independent chat/LLM generation for grounded answers.

The chat model is separate from the embedding model (an embedding provider is
never assumed to also answer questions). Implementations:

- ``FakeChatProvider`` — deterministic, offline, used by unit tests and dry runs.
- ``AnthropicChatProvider`` — the documented default provider (Claude Messages API).
- ``OpenAICompatibleChatProvider`` — ``/chat/completions`` clients such as a local
  Ollama server or an OpenAI-compatible gateway.

Transient failures (HTTP 429/5xx, timeouts) are retried with bounded exponential
backoff. Failures raise so callers can return a safe, visible failure instead of
pretending an answer was produced. No secrets are logged or embedded in errors.
"""

import time
from typing import Callable, Protocol, runtime_checkable

import httpx

from app.settings import ChatSettings, ConfigError

ANTHROPIC_VERSION = "2023-06-01"

_FAKE_ABSTENTION = (
    '{"answer": "The knowledge base does not contain enough information to answer '
    'that question.", "cited_chunk_ids": [], "evidence_assessment": "insufficient", '
    '"needs_escalation": true, "escalation_reason": "No language model is configured."}'
)


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
    """Deterministic chat provider for tests and dry runs.

    Supply a fixed ``response`` or a ``responder(system, user) -> str`` callable.
    The default response is a valid abstention so the pipeline never crashes
    merely because no model is configured.
    """

    def __init__(
        self,
        model_name: str = "fake-chat",
        response: str | None = None,
        responder: Callable[[str, str], str] | None = None,
    ) -> None:
        self.model_name = model_name
        self.response = response if response is not None else _FAKE_ABSTENTION
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
        self.calls.append(
            {
                "system": system,
                "user": user,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self.responder is not None:
            return self.responder(system, user)
        return self.response


class _HTTPChatProvider:
    """Shared retry/timeout handling for HTTP chat providers."""

    def __init__(
        self,
        model_name: str,
        base_url: str,
        timeout: float = 60.0,
        max_retries: int = 2,
        max_tokens: int = 1024,
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

    def _post(self, path: str, *, json: dict, headers: dict) -> str:
        attempts = self.max_retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = self._client.post(
                    f"{self.base_url}{path}", json=json, headers=headers
                )
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < attempts - 1:
                    self._sleeper(self._backoff_seconds * (2**attempt))
                    continue
                raise ChatRequestError(
                    f"chat request failed after {attempts} attempt(s): {exc}"
                ) from exc

            if response.status_code == 429 or 500 <= response.status_code < 600:
                last_error = ChatResponseError(f"retryable HTTP {response.status_code}")
                if attempt < attempts - 1:
                    self._sleeper(self._backoff_seconds * (2**attempt))
                    continue
                raise self._as_error(response)
            if response.status_code >= 400:
                raise self._as_error(response)

            return self._extract(response.json())

        raise ChatRequestError(f"chat request failed: {last_error}")

    def _as_error(self, response: httpx.Response) -> ChatResponseError:
        return ChatResponseError(
            f"chat request failed with HTTP {response.status_code}"
        )

    def _extract(self, payload: object) -> str:
        raise NotImplementedError

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


class AnthropicChatProvider(_HTTPChatProvider):
    """Anthropic Claude Messages API client."""

    def __init__(
        self,
        model_name: str,
        api_key: str,
        base_url: str = "https://api.anthropic.com/v1",
        **kwargs,
    ) -> None:
        if not api_key:
            raise ChatConfigError("ANTHROPIC_API_KEY is required for the anthropic provider")
        super().__init__(model_name, base_url, **kwargs)
        self.api_key = api_key

    def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
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
        texts = [
            block.get("text", "")
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        text = "".join(text for text in texts if text).strip()
        if not text:
            raise ChatResponseError("anthropic response contained no text")
        return text

    def _as_error(self, response: httpx.Response) -> ChatResponseError:
        return ChatResponseError(
            f"chat request failed with HTTP {response.status_code}"
        )


class OpenAICompatibleChatProvider(_HTTPChatProvider):
    """``POST {base_url}/chat/completions`` chat provider (Ollama, OpenAI)."""

    def __init__(
        self,
        model_name: str,
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(model_name, base_url, **kwargs)
        self.api_key = api_key

    def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
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
    settings: ChatSettings | None = None,
    client: httpx.Client | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> ChatProvider:
    """Build a chat provider from settings, validating required values."""
    settings = settings or ChatSettings()
    provider = settings.provider.lower()

    if provider in {"fake", "test"}:
        return FakeChatProvider()

    model = settings.resolved_model()
    api_key = settings.resolved_api_key()
    base_url = settings.effective_base_url()

    if provider == "anthropic":
        if not model:
            raise ChatConfigError(
                "CHAT_MODEL (or ANTHROPIC_MODEL) is required for the anthropic provider"
            )
        if not api_key:
            raise ChatConfigError(
                "CHAT_API_KEY (or ANTHROPIC_API_KEY) is required for the anthropic provider"
            )
        return AnthropicChatProvider(
            model_name=model,
            api_key=api_key,
            base_url=base_url or "https://api.anthropic.com/v1",
            timeout=settings.timeout,
            max_retries=settings.max_retries,
            max_tokens=settings.max_tokens,
            temperature=settings.temperature,
            client=client,
            sleeper=sleeper,
        )

    if provider in {"openai", "openai_compatible", "ollama", "compatible"}:
        if not model:
            raise ChatConfigError(
                f"CHAT_MODEL is required for CHAT_PROVIDER={provider!r}"
            )
        if provider == "openai" and not api_key:
            raise ChatConfigError("CHAT_API_KEY is required for the openai provider")
        if not base_url:
            raise ChatConfigError("CHAT_BASE_URL could not be determined")
        return OpenAICompatibleChatProvider(
            model_name=model,
            base_url=base_url,
            api_key=api_key,
            timeout=settings.timeout,
            max_retries=settings.max_retries,
            max_tokens=settings.max_tokens,
            temperature=settings.temperature,
            client=client,
            sleeper=sleeper,
        )

    raise ChatConfigError(f"unsupported CHAT_PROVIDER: {settings.provider!r}")
