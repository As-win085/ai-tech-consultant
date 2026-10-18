"""Storage abstraction for the Knowledge Brain.

``KnowledgeStore`` is the narrow interface the indexing pipeline depends on.
``PostgresKnowledgeStore`` (see :mod:`app.postgres_store`) is the real
implementation; ``InMemoryKnowledgeStore`` lets the pipeline be tested without a
live database or credentials.
"""

from typing import Protocol, Sequence

from app.models import (
    ArticleRecord,
    ChunkRecord,
    EmbeddingRecord,
    IndexMetadata,
    IndexReport,
    SearchHit,
    cosine_similarity,
)


class KnowledgeStore(Protocol):
    def start_run(self, model: str, dimensions: int) -> int:
        ...

    def finish_run(self, run_id: int, report: IndexReport) -> None:
        ...

    def upsert_article(self, article: ArticleRecord) -> None:
        ...

    def sync_chunks(self, article_id: str, chunks: Sequence[ChunkRecord]) -> int:
        """Upsert chunks and prune stale ones. Returns the number pruned."""
        ...

    def get_embeddings_index(self) -> dict[str, tuple[str, int]]:
        """Map chunk_id -> (embedding_model, dimensions) for stored embeddings."""
        ...

    def save_embedding(self, record: EmbeddingRecord) -> None:
        ...

    def record_embedding_failure(self, chunk_id: str, error: str) -> None:
        ...

    def deactivate_missing_articles(self, active_article_ids: set[str]) -> int:
        ...

    def create_escalation(self, question: str, reason: str, request_id: str | None = None) -> dict:
        ...

    def list_escalations(self, limit: int = 100) -> list[dict]:
        ...

    def get_escalation(self, escalation_id: str) -> dict | None:
        ...

    def resolve_escalation(self, escalation_id: str, answer: str, reviewer: str, version: int) -> dict:
        ...


class RetrievalStore(Protocol):
    """Read side used by retrieval (implemented by both stores)."""

    def search_similar(
        self, embedding: list[float], model: str, dimensions: int, limit: int
    ) -> list[SearchHit]:
        """Return up to ``limit`` hits for ``model``/``dimensions`` by cosine similarity."""
        ...

    def index_metadata(self) -> IndexMetadata:
        ...

    def close(self) -> None:
        ...


class InMemoryKnowledgeStore:
    """A dependency-free store used for tests and the CLI dry run."""

    def __init__(self) -> None:
        self.articles: dict[str, ArticleRecord] = {}
        self.chunks: dict[str, ChunkRecord] = {}
        self.embeddings: dict[str, EmbeddingRecord] = {}
        self.chunk_errors: dict[str, str] = {}
        self.runs: dict[int, dict] = {}
        self._next_run_id = 1
        self.ingestion_runs: list[dict] = []
        self._next_ingestion_run_id = 1
        self.escalations: dict[str, dict] = {}

    def start_run(self, model: str, dimensions: int) -> int:
        run_id = self._next_run_id
        self._next_run_id += 1
        self.runs[run_id] = {"run_id": run_id, "model": model, "dimensions": dimensions}
        return run_id

    def finish_run(self, run_id: int, report: IndexReport) -> None:
        run = self.runs.setdefault(run_id, {"run_id": run_id})
        run.update(report.summary())

    def upsert_article(self, article: ArticleRecord) -> None:
        self.articles[article.article_id] = article

    def sync_chunks(self, article_id: str, chunks: Sequence[ChunkRecord]) -> int:
        incoming = {chunk.chunk_id for chunk in chunks}
        stale = [
            chunk_id
            for chunk_id, chunk in self.chunks.items()
            if chunk.article_id == article_id and chunk_id not in incoming
        ]
        for chunk_id in stale:
            del self.chunks[chunk_id]
            self.embeddings.pop(chunk_id, None)
            self.chunk_errors.pop(chunk_id, None)
        for chunk in chunks:
            self.chunks[chunk.chunk_id] = chunk
        return len(stale)

    def get_embeddings_index(self) -> dict[str, tuple[str, int]]:
        return {
            chunk_id: (record.model, record.dimensions)
            for chunk_id, record in self.embeddings.items()
        }

    def save_embedding(self, record: EmbeddingRecord) -> None:
        self.embeddings[record.chunk_id] = record
        self.chunk_errors.pop(record.chunk_id, None)

    def record_embedding_failure(self, chunk_id: str, error: str) -> None:
        self.chunk_errors[chunk_id] = error

    def deactivate_missing_articles(self, active_article_ids: set[str]) -> int:
        count = 0
        for article in self.articles.values():
            if article.is_active and article.article_id not in active_article_ids:
                article.is_active = False
                count += 1
        return count

    def create_escalation(self, question: str, reason: str, request_id: str | None = None) -> dict:
        import uuid
        from datetime import datetime, timezone

        row = {
            "escalation_id": uuid.uuid4().hex,
            "question": question,
            "reason": reason,
            "request_id": request_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "answers": [],
        }
        self.escalations[row["escalation_id"]] = row
        return dict(row)

    def list_escalations(self, limit: int = 100) -> list[dict]:
        return list(reversed(list(self.escalations.values())))[0:limit]

    def get_escalation(self, escalation_id: str) -> dict | None:
        return self.escalations.get(escalation_id)

    def resolve_escalation(self, escalation_id: str, answer: str, reviewer: str, version: int) -> dict:
        from datetime import datetime, timezone

        row = self.escalations.get(escalation_id)
        if row is None:
            raise KeyError(escalation_id)
        article_id = f"reviewed-escalation-{escalation_id}-v{version}"
        record = {"version": version, "answer": answer, "reviewer": reviewer, "article_id": article_id,
                  "created_at": datetime.now(timezone.utc).isoformat()}
        row["answers"].append(record)
        row["status"] = "resolved"
        row["updated_at"] = record["created_at"]
        return dict(row)

    def start_ingestion_run(self, sitemap_url: str) -> int:
        run_id = self._next_ingestion_run_id
        self._next_ingestion_run_id += 1
        self.ingestion_runs.append({"run_id": run_id, "status": "running", "sitemap_url": sitemap_url})
        return run_id

    def finish_ingestion_run(self, run_id: int, status: str, source: dict, deactivated: int, error: str | None = None) -> None:
        row = next(item for item in self.ingestion_runs if item["run_id"] == run_id)
        row.update(status=status, source=source, articles_deactivated=deactivated, error=error)

    def latest_ingestion_run(self) -> dict | None:
        return self.ingestion_runs[-1] if self.ingestion_runs else None

    def chunks_for_article(self, article_id: str) -> list[ChunkRecord]:
        return [
            chunk for chunk in self.chunks.values() if chunk.article_id == article_id
        ]

    def search_similar(
        self, embedding: list[float], model: str, dimensions: int, limit: int
    ) -> list[SearchHit]:
        hits: list[SearchHit] = []
        for chunk_id, record in self.embeddings.items():
            if record.model != model or record.dimensions != dimensions:
                continue
            chunk = self.chunks.get(chunk_id)
            if chunk is None:
                continue
            article = self.articles.get(chunk.article_id)
            if article is None or article.status != "ok" or not article.is_active:
                continue
            hits.append(
                SearchHit(
                    chunk_id=chunk.chunk_id,
                    article_id=chunk.article_id,
                    title=article.title,
                    canonical_url=article.canonical_url,
                    source_url=article.source_url,
                    heading_context=chunk.heading_context,
                    content=chunk.content,
                    chunk_index=chunk.chunk_index,
                    score=cosine_similarity(embedding, record.embedding),
                )
            )
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:limit]

    def index_metadata(self) -> IndexMetadata:
        counts: dict[tuple[str, int], int] = {}
        for chunk_id, record in self.embeddings.items():
            chunk = self.chunks.get(chunk_id)
            if chunk is None:
                continue
            article = self.articles.get(chunk.article_id)
            if article is None or article.status != "ok" or not article.is_active:
                continue
            key = (record.model, record.dimensions)
            counts[key] = counts.get(key, 0) + 1
        return IndexMetadata(
            indexed_chunks=sum(counts.values()), model_dimensions=counts
        )

    def close(self) -> None:
        return None
