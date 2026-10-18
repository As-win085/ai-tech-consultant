"""Provider-independent embedding generation.

A dedicated embedding provider is required (the chat/LLM model is not assumed to
produce embeddings). Two implementations ship here:

- ``FakeEmbeddingProvider`` — deterministic, offline, used by unit tests.
- ``OpenAICompatibleEmbeddingProvider`` — HTTP ``/embeddings`` client that works
  with OpenAI, Ollama's OpenAI-compatible endpoint, and other compatible APIs.

Responses are validated (shape and vector length) and transient failures are
retried with bounded exponential backoff. Failures raise so the caller records
them; embeddings are never silently faked or replaced with placeholders.
"""

import hashlib
import logging
import os
import time
from typing import Callable, Protocol, runtime_checkable

import httpx

from app.settings import ConfigError, EmbeddingSettings

logger = logging.getLogger(__name__)


class EmbeddingError(RuntimeError):
    """Base class for embedding failures."""


class EmbeddingConfigError(EmbeddingError, ConfigError):
    """The provider is not configured correctly."""


class EmbeddingRequestError(EmbeddingError):
    """A retryable request failed after retries were exhausted."""


class EmbeddingResponseError(EmbeddingError):
    """The provider returned an unusable payload (bad shape or dimensions)."""


@runtime_checkable
class EmbeddingProvider(Protocol):
    model_name: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class FakeEmbeddingProvider:
    """Deterministic embeddings derived from a hash. For tests only."""

    def __init__(self, model_name: str = "fake-embedding", dimensions: int = 64) -> None:
        if dimensions < 1:
            raise EmbeddingConfigError("fake embedding dimensions must be >= 1")
        self.model_name = model_name
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        values: list[float] = []
        counter = 0
        while len(values) < self.dimensions:
            seed = f"{self.model_name}\x1f{text}\x1f{counter}".encode("utf-8")
            digest = hashlib.sha256(seed).digest()
            for offset in range(0, len(digest), 4):
                if len(values) >= self.dimensions:
                    break
                integer = int.from_bytes(digest[offset : offset + 4], "big")
                values.append((integer / 0xFFFFFFFF) * 2.0 - 1.0)
            counter += 1
        return values


class OpenAICompatibleEmbeddingProvider:
    """Calls an OpenAI-compatible ``POST {base_url}/embeddings`` endpoint."""

    def __init__(
        self,
        model_name: str,
        dimensions: int,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 30.0,
        max_retries: int = 3,
        client: httpx.Client | None = None,
        sleeper: Callable[[float], None] | None = None,
        backoff_seconds: float = 1.0,
    ) -> None:
        if not model_name:
            raise EmbeddingConfigError("EMBEDDING_MODEL is required for this provider")
        if dimensions is None or dimensions < 1:
            raise EmbeddingConfigError("EMBEDDING_DIMENSIONS is required for this provider")
        self.model_name = model_name
        self.dimensions = dimensions
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.request_delay_seconds = max(0.0, float(os.getenv("LLM_REQUEST_DELAY_MS", "0")) / 1000)
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None
        self._sleeper = sleeper or time.sleep
        self._backoff_seconds = backoff_seconds

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = {"model": self.model_name, "input": texts}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        attempts = self.max_retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                if self.request_delay_seconds:
                    self._sleeper(self.request_delay_seconds)
                response = self._client.post(
                    f"{self.base_url}/embeddings", json=payload, headers=headers
                )
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < attempts - 1:
                    logger.warning("embedding retry attempt=%d/%d error=%s", attempt + 1, attempts - 1, type(exc).__name__)
                    self._sleeper(self._backoff_seconds * (2**attempt))
                    continue
                raise EmbeddingRequestError(
                    f"embedding request failed after {attempts} attempt(s): {exc}"
                ) from exc

            if response.status_code == 429 or 500 <= response.status_code < 600:
                last_error = EmbeddingResponseError(
                    f"retryable HTTP {response.status_code}"
                )
                if attempt < attempts - 1:
                    logger.warning("embedding retry attempt=%d/%d status=%d", attempt + 1, attempts - 1, response.status_code)
                    self._sleeper(self._backoff_seconds * (2**attempt))
                    continue
                raise self._as_error(response)
            if response.status_code >= 400:
                raise self._as_error(response)

            return self._parse(response.json(), len(texts))

        raise EmbeddingRequestError(f"embedding request failed: {last_error}")

    def _parse(self, payload: object, expected_count: int) -> list[list[float]]:
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or len(data) != expected_count:
            got = len(data) if isinstance(data, list) else "non-list"
            raise EmbeddingResponseError(
                f"expected {expected_count} embeddings, received {got}"
            )
        vectors: list[list[float]] = []
        for item in data:
            vector = item.get("embedding") if isinstance(item, dict) else None
            if not isinstance(vector, list) or not vector:
                raise EmbeddingResponseError("embedding payload is missing a vector")
            if len(vector) != self.dimensions:
                raise EmbeddingResponseError(
                    f"embedding dimension mismatch: expected {self.dimensions}, "
                    f"received {len(vector)}"
                )
            vectors.append([float(value) for value in vector])
        return vectors

    def _as_error(self, response: httpx.Response) -> EmbeddingResponseError:
        detail = ""
        try:
            detail = response.text[:200]
        except Exception:
            detail = ""
        suffix = f": {detail}" if detail else ""
        return EmbeddingResponseError(
            f"embedding request failed with HTTP {response.status_code}{suffix}"
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


class GeminiEmbeddingProvider:
    """Google Gemini batch embedding endpoint with explicit output dimension."""
    def __init__(self, model_name: str, dimensions: int, api_key: str,
                 base_url: str = "https://generativelanguage.googleapis.com/v1beta",
                 timeout: float = 30.0, client: httpx.Client | None = None) -> None:
        if not model_name or not api_key or not dimensions:
            raise EmbeddingConfigError("Gemini embeddings require model, API key, and dimensions")
        self.model_name, self.dimensions, self.api_key = model_name, dimensions, api_key
        self.base_url = base_url.rstrip("/")
        self.request_delay_seconds = max(0.0, float(os.getenv("LLM_REQUEST_DELAY_MS", "0")) / 1000)
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        body = {"requests": [{"model": f"models/{self.model_name}",
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": self.dimensions} for text in texts]}
        if self.request_delay_seconds:
            time.sleep(self.request_delay_seconds)
        attempts = 4
        for attempt in range(attempts):
            try:
                response = self._client.post(
                    f"{self.base_url}/models/{self.model_name}:batchEmbedContents",
                    json=body, headers={"x-goog-api-key": self.api_key})
                if response.status_code == 429 or 500 <= response.status_code < 600:
                    if attempt + 1 < attempts:
                        delay = 0.25 * (2 ** attempt)
                        logger.warning("embedding retry provider=gemini attempt=%d/%d status=%d delay_seconds=%.2f", attempt + 1, attempts - 1, response.status_code, delay)
                        time.sleep(delay)
                        continue
                    raise EmbeddingRequestError(f"Gemini embedding request failed after {attempts} attempts with HTTP {response.status_code}")
                if response.status_code >= 400:
                    raise EmbeddingRequestError(f"Gemini embedding request failed with HTTP {response.status_code}")
                break
            except httpx.HTTPError as exc:
                if attempt + 1 == attempts:
                    raise EmbeddingRequestError(f"Gemini embedding request failed after {attempts} attempts: {type(exc).__name__}") from exc
                delay = 0.25 * (2 ** attempt)
                logger.warning("embedding retry provider=gemini attempt=%d/%d error=%s delay_seconds=%.2f", attempt + 1, attempts - 1, type(exc).__name__, delay)
                time.sleep(delay)
        payload = response.json()
        vectors = [item.get("values") for item in payload.get("embeddings", [])]
        if len(vectors) != len(texts) or any(not isinstance(v, list) or len(v) != self.dimensions for v in vectors):
            raise EmbeddingResponseError("Gemini embeddings response has unexpected dimensions")
        return vectors

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


def build_embedding_provider(
    settings: EmbeddingSettings | None = None,
    client: httpx.Client | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> EmbeddingProvider:
    """Build a provider from settings, validating required values."""
    settings = settings or EmbeddingSettings()
    provider = settings.provider.lower()

    if provider in {"fake", "test"}:
        return FakeEmbeddingProvider(
            model_name=settings.model or "fake-embedding",
            dimensions=settings.dimensions or 64,
        )

    provider = __import__("os").environ.get("EMBEDDING_PROVIDER", provider).lower()
    if provider in {"gemini", "google"}:
        model = settings.model or "gemini-embedding-001"
        dimensions = settings.dimensions or 768
        key = settings.api_key or __import__("os").environ.get("LLM_API_KEY")
        if not key:
            raise EmbeddingConfigError("LLM_API_KEY is required for Gemini embeddings")
        return GeminiEmbeddingProvider(model, dimensions, key,
            settings.effective_base_url() or "https://generativelanguage.googleapis.com/v1beta",
            settings.timeout, client)
    if provider in {"openai", "openai_compatible", "ollama", "compatible", "groq", "openrouter"}:
        if not settings.model:
            raise EmbeddingConfigError(
                f"EMBEDDING_MODEL is required for EMBEDDING_PROVIDER={provider!r}"
            )
        if not settings.dimensions:
            raise EmbeddingConfigError(
                f"EMBEDDING_DIMENSIONS is required for EMBEDDING_PROVIDER={provider!r}"
            )
        if provider in {"openai", "openai_compatible"} and not settings.api_key:
            raise EmbeddingConfigError(
                f"EMBEDDING_API_KEY is required for EMBEDDING_PROVIDER={provider!r}"
            )
        base_url = settings.effective_base_url()
        if not base_url:
            raise EmbeddingConfigError("EMBEDDING_BASE_URL could not be determined")
        return OpenAICompatibleEmbeddingProvider(
            model_name=settings.model,
            dimensions=settings.dimensions,
            api_key=settings.api_key,
            base_url=base_url,
            timeout=settings.timeout,
            max_retries=settings.max_retries,
            client=client,
            sleeper=sleeper,
        )

    raise EmbeddingConfigError(f"unsupported EMBEDDING_PROVIDER: {settings.provider!r}")
