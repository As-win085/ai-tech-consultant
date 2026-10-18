import httpx
import pytest

from app.embeddings import (
    EmbeddingConfigError,
    EmbeddingRequestError,
    EmbeddingResponseError,
    FakeEmbeddingProvider,
    GeminiEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    build_embedding_provider,
)
from app.settings import EmbeddingSettings


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def embeddings_response(vectors) -> dict:
    return {"data": [{"embedding": vector} for vector in vectors]}


def test_fake_provider_is_deterministic_and_correctly_sized():
    provider = FakeEmbeddingProvider(model_name="m", dimensions=8)
    assert provider.embed(["hello"]) == provider.embed(["hello"])
    assert len(provider.embed(["hello"])[0]) == 8
    assert provider.embed(["hello"])[0] != provider.embed(["world"])[0]


def test_fake_provider_batches():
    vectors = FakeEmbeddingProvider(dimensions=4).embed(["a", "b", "c"])
    assert len(vectors) == 3
    assert all(len(vector) == 4 for vector in vectors)


def test_factory_builds_fake_provider():
    provider = build_embedding_provider(EmbeddingSettings(provider="fake", dimensions=16))
    assert provider.dimensions == 16


def test_factory_requires_model_and_dimensions_for_openai():
    with pytest.raises(EmbeddingConfigError):
        build_embedding_provider(EmbeddingSettings(provider="openai", model=None, dimensions=None))


def test_factory_requires_api_key_for_openai():
    with pytest.raises(EmbeddingConfigError):
        build_embedding_provider(
            EmbeddingSettings(provider="openai", model="text-embedding-3-small", dimensions=1536, api_key=None)
        )


def test_factory_ollama_default_base_url_and_no_key():
    provider = build_embedding_provider(
        EmbeddingSettings(provider="ollama", model="nomic-embed-text", dimensions=768, base_url=None)
    )
    assert provider.base_url == "http://localhost:11434/v1"
    assert provider.dimensions == 768


def test_factory_rejects_unknown_provider():
    with pytest.raises(EmbeddingConfigError):
        build_embedding_provider(EmbeddingSettings(provider="totally-made-up"))


def test_provider_retries_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, text="slow down")
        return httpx.Response(200, json=embeddings_response([[1, 2, 3]]))

    provider = OpenAICompatibleEmbeddingProvider(
        "m", 3, max_retries=2, client=make_client(handler), sleeper=lambda _: None
    )
    assert provider.embed(["a"]) == [[1.0, 2.0, 3.0]]
    assert calls["n"] == 2


def test_provider_rejects_dimension_mismatch():
    def handler(request):
        return httpx.Response(200, json=embeddings_response([[1, 2]]))

    provider = OpenAICompatibleEmbeddingProvider("m", 3, client=make_client(handler))
    with pytest.raises(EmbeddingResponseError):
        provider.embed(["a"])


def test_provider_rejects_wrong_embedding_count():
    def handler(request):
        return httpx.Response(200, json=embeddings_response([[1, 2, 3]]))

    provider = OpenAICompatibleEmbeddingProvider("m", 3, client=make_client(handler))
    with pytest.raises(EmbeddingResponseError):
        provider.embed(["a", "b"])


def test_provider_parses_response_and_sends_auth_header():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=embeddings_response([[1, 2, 3]]))

    provider = OpenAICompatibleEmbeddingProvider(
        "m", 3, api_key="secret", client=make_client(handler)
    )
    assert provider.embed(["a"]) == [[1.0, 2.0, 3.0]]
    assert seen["auth"] == "Bearer secret"


def test_provider_raises_after_retries_exhausted():
    def handler(request):
        return httpx.Response(500, text="boom")

    provider = OpenAICompatibleEmbeddingProvider(
        "m", 3, max_retries=1, client=make_client(handler), sleeper=lambda _: None
    )
    with pytest.raises(EmbeddingResponseError):
        provider.embed(["a"])


def test_provider_timeout_raises_request_error():
    def handler(request):
        raise httpx.ReadTimeout("timed out", request=request)

    provider = OpenAICompatibleEmbeddingProvider(
        "m", 3, max_retries=1, client=make_client(handler), sleeper=lambda _: None
    )
    with pytest.raises(EmbeddingRequestError):
        provider.embed(["a"])


def test_provider_does_not_retry_client_error():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(400, text="bad request")

    provider = OpenAICompatibleEmbeddingProvider(
        "m", 3, max_retries=3, client=make_client(handler), sleeper=lambda _: None
    )
    with pytest.raises(EmbeddingResponseError):
        provider.embed(["a"])
    assert calls["n"] == 1


def test_provider_empty_input_makes_no_request():
    def handler(request):
        raise AssertionError("no request expected for empty input")

    provider = OpenAICompatibleEmbeddingProvider("m", 3, client=make_client(handler))
    assert provider.embed([]) == []


def test_gemini_provider_batches_with_requested_dimensions():
    seen = {}
    def handler(request):
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-goog-api-key")
        seen["body"] = request.read().decode()
        return httpx.Response(200, json={"embeddings": [{"values": [0.1, 0.2]}]})
    provider = GeminiEmbeddingProvider("gemini-embedding-001", 2, "test-key", client=make_client(handler))
    assert provider.embed(["sample"]) == [[0.1, 0.2]]
    assert seen["key"] == "test-key"
    assert '"outputDimensionality":2' in seen["body"]
    assert seen["url"].endswith("/models/gemini-embedding-001:batchEmbedContents")
