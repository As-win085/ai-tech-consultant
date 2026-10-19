"""Composition root and application service for the Knowledge Brain API.

``KnowledgeService`` wires settings, providers, and a per-request database
connection into the retrieval + answer pipeline. Provider construction is
captured (not raised) at startup so ``/ready`` can report *why* the service is
not ready without crashing the process or leaking secrets.
"""

import uuid
from datetime import datetime, timezone

from app.answer import AnswerConfig, generate_answer
from app.chat import ChatError, ChatProvider
from app.embeddings import EmbeddingError, EmbeddingProvider
from app.models import IndexMetadata
from app.retriever import IndexModelMismatch, RetrievalConfig, Retriever
from app.schemas import (
    AskRequest,
    AskResponse,
    DependencyStatus,
    EvidenceConfidence,
    ReadyReport,
)


class ServiceUnavailable(RuntimeError):
    """A required dependency is unavailable; a safe error response is returned."""

    def __init__(self, dependency: str, message: str) -> None:
        super().__init__(message)
        self.dependency = dependency
        self.message = message


class KnowledgeService:
    def __init__(
        self,
        *,
        store_factory,
        embedding_provider: EmbeddingProvider | None,
        chat_provider: ChatProvider | None,
        retrieval_config: RetrievalConfig,
        answer_config: AnswerConfig,
        embedding_detail: str,
        chat_detail: str,
    ) -> None:
        self.store_factory = store_factory
        self.embedding_provider = embedding_provider
        self.chat_provider = chat_provider
        self.retrieval_config = retrieval_config
        self.answer_config = answer_config
        self.embedding_detail = embedding_detail
        self.chat_detail = chat_detail

    def ask(self, request: AskRequest) -> AskResponse:
        request_id = uuid.uuid4().hex
        if self.embedding_provider is None:
            raise ServiceUnavailable("embedding_provider", self.embedding_detail)
        if self.chat_provider is None:
            raise ServiceUnavailable("chat_provider", self.chat_detail)

        store = self._open_store()
        try:
            retriever = Retriever(
                store, self.embedding_provider, self.retrieval_config
            )
            try:
                retrieval = retriever.retrieve(
                    request.question,
                    top_k=request.top_k,
                    min_score=request.min_score,
                )
            except IndexModelMismatch as exc:
                response = self._unavailable_answer(request, str(exc), request_id)
                self._record_escalation(store, request, response, request_id)
                return response
            except EmbeddingError as exc:
                raise ServiceUnavailable(
                    "embedding_provider",
                    f"the embedding provider failed: {type(exc).__name__}: {exc}",
                ) from exc

            min_score = (
                request.min_score
                if request.min_score is not None
                else self.retrieval_config.min_score
            )
            try:
                response = generate_answer(
                    request,
                    retrieval,
                    self.chat_provider,
                    self.answer_config,
                    min_score,
                    request_id,
                )
                self._record_escalation(store, request, response, request_id)
                return response
            except ChatError as exc:
                raise ServiceUnavailable(
                    "chat_provider",
                    f"the chat provider failed: {type(exc).__name__}: {exc}",
                ) from exc
        finally:
            store.close()

    @staticmethod
    def _record_escalation(store, request: AskRequest, response: AskResponse, request_id: str) -> None:
        if not response.needs_escalation and response.evidence_status == "sufficient":
            return
        response.needs_escalation = True
        if not response.escalation_reason:
            response.escalation_reason = "The available evidence was insufficient or conflicting."
        escalation = store.create_escalation(
            request.question, response.escalation_reason, request_id
        )
        response.escalation_id = escalation["escalation_id"]

    def list_escalations(self, limit: int = 100) -> list[dict]:
        store = self._open_store()
        try:
            return store.list_escalations(limit)
        finally:
            store.close()

    def create_escalation(self, question: str, reason: str) -> dict:
        store = self._open_store()
        try:
            return store.create_escalation(question, reason)
        finally:
            store.close()

    def resolve_escalation(self, escalation_id: str, answer: str, reviewer: str) -> dict:
        if self.embedding_provider is None:
            raise ServiceUnavailable("embedding_provider", self.embedding_detail)
        store = self._open_store()
        try:
            escalation = store.get_escalation(escalation_id)
            if escalation is None:
                raise KeyError(escalation_id)
            version = 1 + max((item["version"] for item in escalation["answers"]), default=0)
            from app.crawler import compute_content_hash
            from app.indexer import IndexConfig, index_document

            article_id = f"reviewed-escalation-{escalation_id}-v{version}"
            text = f"Question: {escalation['question']}\n\nReviewed answer: {answer.strip()}"
            article = {
                "id": article_id,
                "url": f"https://knowledge-brain.local/escalations/{escalation_id}/v{version}",
                "canonical_url": f"https://knowledge-brain.local/escalations/{escalation_id}/v{version}",
                "title": f"Reviewed answer: {escalation['question'][:120]}",
                "text": text,
                "headings": [{"level": 1, "text": "Reviewed answer"}],
                "char_count": len(text),
                "content_hash": compute_content_hash(text),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "http_status": 200,
                "status": "ok",
                "error": None,
            }
            report = index_document(store, self.embedding_provider, {"articles": [article]}, IndexConfig())
            if report.status != "ok":
                raise ServiceUnavailable("embedding_provider", "the reviewed answer could not be indexed")
            return store.resolve_escalation(escalation_id, answer.strip(), reviewer.strip(), version)
        finally:
            store.close()

    def _open_store(self):
        try:
            return self.store_factory()
        except ServiceUnavailable:
            raise
        except Exception as exc:  # connection/config failure
            raise ServiceUnavailable(
                "database", f"the database is unavailable: {type(exc).__name__}"
            ) from exc

    def _unavailable_answer(
        self, request: AskRequest, reason: str, request_id: str
    ) -> AskResponse:
        return AskResponse(
            answer=(
                "The Knowledge Brain index is not compatible with the configured "
                "embedding model, so I cannot retrieve reliable evidence."
            ),
            citations=[],
            evidence_status="unavailable",
            confidence=EvidenceConfidence(level="none", score=0.0, basis=reason),
            needs_escalation=False,
            escalation_reason=reason,
            retrieved_chunks=None,
            model=None,
            request_id=request_id,
        )

    def _open_store_for_probe(self):
        return self.store_factory()

    def readiness(self) -> ReadyReport:
        dependencies: list[DependencyStatus] = []
        index_summary: dict = {}

        database_status = "ok"
        database_detail = "database is reachable"
        index_meta: IndexMetadata | None = None
        try:
            store = self._open_store_for_probe()
            try:
                index_meta = store.index_metadata()
                index_summary = index_meta.summary()
            finally:
                store.close()
        except Exception:
            database_status = "error"
            database_detail = "database is not reachable or is not migrated"
        dependencies.append(
            DependencyStatus(
                name="database", status=database_status, detail=database_detail
            )
        )

        if self.embedding_provider is None:
            embedding_status = "not_configured"
        elif (
            database_status == "ok"
            and index_meta is not None
            and index_meta.indexed_chunks > 0
            and not index_meta.has(
                self.embedding_provider.model_name, self.embedding_provider.dimensions
            )
        ):
            embedding_status = "mismatch"
        else:
            embedding_status = "ok"
        dependencies.append(
            DependencyStatus(
                name="embedding_provider",
                status=embedding_status,
                detail=self.embedding_detail,
            )
        )

        chat_status = "not_configured" if self.chat_provider is None else "ok"
        dependencies.append(
            DependencyStatus(
                name="chat_provider", status=chat_status, detail=self.chat_detail
            )
        )

        ready = all(dep.status == "ok" for dep in dependencies)
        if ready:
            status = "ready"
        elif database_status != "ok":
            status = "unavailable"
        else:
            status = "degraded"

        return ReadyReport(
            status=status,
            ready=ready,
            dependencies=dependencies,
            index=index_summary,
        )


def build_default_service() -> KnowledgeService:
    """Build the service from environment settings without raising."""
    from app.answer import AnswerConfig
    from app.chat import build_chat_provider
    from app.db import apply_migrations, connect
    from app.embeddings import build_embedding_provider
    from app.postgres_store import PostgresKnowledgeStore
    from app.retriever import RetrievalConfig
    from app.settings import (
        get_answer_settings,
        get_chat_settings,
        get_database_settings,
        get_embedding_settings,
        get_retrieval_settings,
    )

    embedding_settings = get_embedding_settings()
    try:
        embedding_provider: EmbeddingProvider | None = build_embedding_provider(
            embedding_settings
        )
        embedding_detail = (
            f"provider={embedding_settings.provider}, model="
            f"{embedding_provider.model_name}, dimensions={embedding_provider.dimensions}"
        )
    except Exception as exc:
        embedding_provider = None
        embedding_detail = f"embedding provider is not configured: {type(exc).__name__}"

    chat_settings = get_chat_settings()
    try:
        chat_provider: ChatProvider | None = build_chat_provider(chat_settings)
        chat_detail = (
            f"provider={chat_settings.provider}, model={chat_provider.model_name}"
        )
    except Exception as exc:
        chat_provider = None
        chat_detail = f"chat provider is not configured: {type(exc).__name__}"

    database_url = get_database_settings().database_url
    if database_url:
        def store_factory():
            connection = connect(database_url)
            apply_migrations(connection)
            return PostgresKnowledgeStore(connection)
    else:
        def store_factory():
            raise ServiceUnavailable(
                "database", "DATABASE_URL is not configured"
            )

    retrieval_settings = get_retrieval_settings()
    answer_settings = get_answer_settings()
    return KnowledgeService(
        store_factory=store_factory,
        embedding_provider=embedding_provider,
        chat_provider=chat_provider,
        retrieval_config=RetrievalConfig(
            top_k=retrieval_settings.top_k,
            min_score=retrieval_settings.min_score,
            max_per_article=retrieval_settings.max_per_article,
            oversample=retrieval_settings.oversample,
        ),
        answer_config=AnswerConfig(
            max_context_chars=answer_settings.max_context_chars,
            max_citations=answer_settings.max_citations,
            max_generation_attempts=answer_settings.max_generation_attempts,
        ),
        embedding_detail=embedding_detail,
        chat_detail=chat_detail,
    )
