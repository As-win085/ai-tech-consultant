import json

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_service
from app.answer import AnswerConfig
from app.chat import FakeChatProvider
from app.embeddings import FakeEmbeddingProvider
from app.schemas import (
    AskResponse,
    Citation,
    DependencyStatus,
    EvidenceConfidence,
    ReadyReport,
)
from app.service import ServiceUnavailable
from app.retriever import RetrievalConfig
from app.store import InMemoryKnowledgeStore
from app.service import KnowledgeService


def make_response(**overrides) -> "AskResponse":
    payload = {
        "answer": "Open Account > Security and click Reset.",
        "citations": [
            {
                "article_id": "a1",
                "title": "Password Reset Guide",
                "canonical_url": "https://support.example/a1",
                "heading": "Account",
                "chunk_id": "c1",
                "chunk_index": 0,
                "score": 0.91,
            }
        ],
        "evidence_status": "sufficient",
        "confidence": {"level": "high", "score": 0.9, "basis": "test"},
        "needs_escalation": False,
        "escalation_reason": None,
        "retrieved_chunks": None,
        "model": "stub-model",
        "request_id": "abc123",
    }
    payload.update(overrides)
    return AskResponse.model_validate(payload)


class StubService:
    def __init__(self, response=None, error=None, readiness_report=None):
        self.response = response
        self.error = error
        self.readiness_report = readiness_report

    def ask(self, request):
        if self.error is not None:
            raise self.error
        return self.response

    def readiness(self):
        if self.error is not None:
            raise self.error
        return self.readiness_report


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def use_service(client, service):
    app.dependency_overrides[get_service] = lambda: service


def teardown_function():
    app.dependency_overrides.clear()


def ready_report(ready: bool) -> ReadyReport:
    status = "ok" if ready else "error"
    return ReadyReport(
        status="ready" if ready else "unavailable",
        ready=ready,
        dependencies=[
            DependencyStatus(name="database", status=status, detail="checked"),
            DependencyStatus(name="embedding_provider", status="ok", detail="checked"),
            DependencyStatus(name="chat_provider", status="ok", detail="checked"),
        ],
        index={"articles": 5, "chunks": 29},
    )


def test_root_endpoint_unchanged(client):
    use_service(client, StubService())
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_health_endpoint_unchanged(client):
    use_service(client, StubService())
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["version"] == "0.2.0"


def test_ask_returns_grounded_answer_with_citations(client):
    use_service(client, StubService(response=make_response()))
    response = client.post("/ask", json={"question": "How do I reset a password?"})
    assert response.status_code == 200
    body = response.json()
    assert body["evidence_status"] == "sufficient"
    assert body["citations"][0]["chunk_id"] == "c1"
    assert body["request_id"] == "abc123"


def test_ask_abstention_is_http_200(client):
    abstention = AskResponse.model_validate(
        {
            "answer": "I could not find relevant evidence.",
            "citations": [],
            "evidence_status": "insufficient",
            "confidence": {"level": "low", "score": 0.1, "basis": "weak"},
            "needs_escalation": True,
            "escalation_reason": "no evidence",
            "model": None,
            "request_id": "xyz",
        }
    )
    use_service(client, StubService(response=abstention))
    response = client.post("/ask", json={"question": "Unknown question"})
    assert response.status_code == 200
    assert response.json()["evidence_status"] == "insufficient"
    assert response.json()["citations"] == []


def test_ask_rejects_blank_question_with_422(client):
    use_service(client, StubService(response=make_response()))
    response = client.post("/ask", json={"question": "   "})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_ask_rejects_missing_body(client):
    use_service(client, StubService(response=make_response()))
    response = client.post("/ask", json={})
    assert response.status_code == 422


def test_ask_dependency_failure_returns_safe_503(client):
    error = ServiceUnavailable("database", "the database is unavailable (RuntimeError)")
    use_service(client, StubService(error=error))
    response = client.post("/ask", json={"question": "How do I reset a password?"})
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "service_unavailable"
    text = response.text
    assert "Traceback" not in text
    assert "secret" not in text
    assert "pg8000" not in text


def test_ask_unhandled_error_returns_safe_500(client):
    use_service(client, StubService(error=RuntimeError("boom secret-xyz details")))
    response = client.post("/ask", json={"question": "How do I reset a password?"})
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "secret-xyz" not in response.text
    assert "Traceback" not in response.text


def test_ask_validation_error_has_no_stack_trace(client):
    use_service(client, StubService(response=make_response()))
    response = client.post("/ask", json={"question": ""})
    assert response.status_code == 422
    assert "Traceback" not in response.text


def test_ready_returns_200_when_ready(client):
    use_service(client, StubService(readiness_report=ready_report(True)))
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["ready"] is True


def test_ready_returns_503_when_not_ready(client):
    use_service(client, StubService(readiness_report=ready_report(False)))
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["ready"] is False


def test_ready_service_unavailable_is_safe(client):
    use_service(client, StubService(error=ServiceUnavailable("database", "not reachable")))
    response = client.get("/ready")
    assert response.status_code == 503
    assert "Traceback" not in response.text


def test_query_alias_and_chat_page(client):
    use_service(client, StubService(response=make_response()))
    response = client.post("/query", json={"question": "How do I reset a password?"})
    assert response.status_code == 200
    assert response.json()["citations"][0]["chunk_id"] == "c1"
    page = client.get("/chat")
    assert page.status_code == 200
    assert "Knowledge Chat" in page.text
    assert "Service unavailable" in page.text


def test_ingestion_run_and_status_routes(client, monkeypatch):
    from app import ingestion

    monkeypatch.setattr(ingestion, "run_ingestion", lambda: {"run_id": 7, "status": "ok"})
    monkeypatch.setattr(ingestion, "get_ingestion_status", lambda: {"run_id": 7, "status": "ok"})
    assert client.post("/ingestion/run").json() == {"run_id": 7, "status": "ok"}
    assert client.get("/ingestion/status").json() == {"latest_run": {"run_id": 7, "status": "ok"}}


def test_abstention_is_persisted_and_reviewed_answer_is_indexed(client):
    store = InMemoryKnowledgeStore()
    service = KnowledgeService(
        store_factory=lambda: store,
        embedding_provider=FakeEmbeddingProvider(dimensions=8),
        chat_provider=FakeChatProvider(),
        retrieval_config=RetrievalConfig(),
        answer_config=AnswerConfig(),
        embedding_detail="fake test provider",
        chat_detail="fake test provider",
    )
    use_service(client, service)
    response = client.post("/ask", json={"question": "How do I configure an unknown feature?"})
    assert response.status_code == 200
    escalation_id = response.json()["escalation_id"]
    assert response.json()["needs_escalation"] is True

    resolved = client.post(
        f"/escalations/{escalation_id}/resolve",
        json={"answer": "Open Settings and select Features.", "reviewer": "reviewer-1"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["answers"][0]["version"] == 1
    article_id = resolved.json()["answers"][0]["article_id"]
    assert article_id in store.articles
    assert any(chunk.article_id == article_id for chunk in store.chunks.values())
    assert any(record.chunk_id in store.chunks for record in store.embeddings.values())
