"""Knowledge Brain client: parsing, honesty, and failure handling."""

from __future__ import annotations

import httpx
import pytest

from app.kb_client import (
    KbConfigError,
    KbResponseError,
    KbTimeout,
    KbUnavailable,
    KnowledgeBrainClient,
    build_kb_client,
)

SUFFICIENT = {
    "answer": "Yes, it is supported.",
    "evidence_status": "sufficient",
    "citations": [
        {"article_id": "a1", "title": "Doc", "canonical_url": "https://x", "heading": "H", "chunk_id": "c1", "chunk_index": 0, "score": 0.8}
    ],
    "confidence": {"level": "high", "score": 0.8, "basis": "kb"},
    "needs_escalation": False,
    "escalation_reason": None,
    "model": "m",
    "request_id": "req-1",
}


def _client(handler) -> KnowledgeBrainClient:
    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, timeout=1.0)
    return KnowledgeBrainClient("http://kb.local", max_retries=0, client=http, sleeper=lambda _: None)


def test_successful_answer_parsed():
    def handler(request):
        assert request.url.path == "/ask"
        return httpx.Response(200, json=SUFFICIENT)

    answer = _client(handler).ask("Does it support SSO?")
    assert answer.evidence_status == "sufficient"
    assert answer.citations[0].article_id == "a1"
    assert answer.confidence.level == "high"
    assert answer.request_id == "req-1"


def test_abstention_is_preserved_not_upgraded():
    def handler(request):
        return httpx.Response(200, json={"answer": "No info.", "evidence_status": "insufficient", "confidence": {"level": "none", "score": 0.0, "basis": "kb"}, "needs_escalation": True})

    answer = _client(handler).ask("Unknown thing?")
    assert answer.evidence_status == "insufficient"
    assert answer.needs_escalation is True


def test_server_error_raises_unavailable():
    def handler(request):
        return httpx.Response(503, json={"error": {"code": "service_unavailable"}})

    with pytest.raises(KbUnavailable):
        _client(handler).ask("q")


def test_timeout_raises_kb_timeout():
    def handler(request):
        raise httpx.TimeoutException("timed out")

    with pytest.raises(KbTimeout):
        _client(handler).ask("q")


def test_connection_error_raises_unavailable():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(KbUnavailable):
        _client(handler).ask("q")


def test_malformed_json_raises_response_error():
    def handler(request):
        return httpx.Response(200, content=b"not json", headers={"content-type": "text/plain"})

    with pytest.raises(KbResponseError):
        _client(handler).ask("q")


def test_validation_error_surfaces():
    def handler(request):
        return httpx.Response(422, json={"error": {"code": "validation_error"}})

    with pytest.raises(KbResponseError):
        _client(handler).ask("q")


def test_ping_reflects_health():
    def handler(request):
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "healthy"})
        return httpx.Response(404)

    assert _client(handler).ping() is True


def test_ping_false_on_error():
    def handler(request):
        raise httpx.ConnectError("refused")

    assert _client(handler).ping() is False


def test_empty_base_url_is_config_error():
    with pytest.raises(KbConfigError):
        KnowledgeBrainClient("")


def test_build_kb_client_uses_settings(settings):
    client = build_kb_client(settings)
    assert client.base_url == "http://localhost:8000"
    assert client.timeout == settings.knowledge_brain_timeout_seconds
