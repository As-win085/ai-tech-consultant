"""PostgreSQL + pgvector implementation of the KnowledgeStore interface."""

from typing import Sequence

import pg8000.native

from app.models import (
    ArticleRecord,
    ChunkRecord,
    EmbeddingRecord,
    IndexMetadata,
    IndexReport,
    SearchHit,
)

_UPSERT_ARTICLE = """
INSERT INTO articles (
    article_id, canonical_url, source_url, title, last_modified, change_frequency,
    priority, fetched_at, http_status, source_content_hash, normalized_content_hash,
    char_count, status, error, is_active, created_at, updated_at
) VALUES (
    :article_id, :canonical_url, :source_url, :title, :last_modified, :change_frequency,
    :priority, :fetched_at, :http_status, :source_content_hash, :normalized_content_hash,
    :char_count, :status, :error, TRUE, now(), now()
)
ON CONFLICT (article_id) DO UPDATE SET
    canonical_url = EXCLUDED.canonical_url,
    source_url = EXCLUDED.source_url,
    title = EXCLUDED.title,
    last_modified = EXCLUDED.last_modified,
    change_frequency = EXCLUDED.change_frequency,
    priority = EXCLUDED.priority,
    fetched_at = EXCLUDED.fetched_at,
    http_status = EXCLUDED.http_status,
    source_content_hash = EXCLUDED.source_content_hash,
    normalized_content_hash = EXCLUDED.normalized_content_hash,
    char_count = EXCLUDED.char_count,
    status = EXCLUDED.status,
    error = EXCLUDED.error,
    is_active = TRUE,
    updated_at = now()
"""

_UPSERT_CHUNK = """
INSERT INTO chunks (
    chunk_id, article_id, chunk_index, heading_context, content, char_count,
    content_hash, article_content_hash, embedding_status, created_at, updated_at
) VALUES (
    :chunk_id, :article_id, :chunk_index, :heading_context, :content, :char_count,
    :content_hash, :article_content_hash, 'pending', now(), now()
)
ON CONFLICT (chunk_id) DO UPDATE SET
    chunk_index = EXCLUDED.chunk_index,
    heading_context = EXCLUDED.heading_context,
    content = EXCLUDED.content,
    char_count = EXCLUDED.char_count,
    content_hash = EXCLUDED.content_hash,
    article_content_hash = EXCLUDED.article_content_hash,
    updated_at = now()
"""

_UPSERT_EMBEDDING = """
INSERT INTO chunk_embeddings (
    chunk_id, embedding, embedding_model, embedding_dim, embedded_at
) VALUES (
    :chunk_id, :vector::vector, :model, :dimensions, now()
)
ON CONFLICT (chunk_id) DO UPDATE SET
    embedding = EXCLUDED.embedding,
    embedding_model = EXCLUDED.embedding_model,
    embedding_dim = EXCLUDED.embedding_dim,
    embedded_at = now()
"""


def format_vector(values: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(value)) for value in values) + "]"


# Cosine distance (``<=>``) is the pgvector operator that matches the cosine
# similarity used by the in-memory store and by OpenAI/Ollama embedding models.
# Similarity is reported as ``1 - distance`` so higher is better.
_SEARCH_SIMILAR = """
SELECT c.chunk_id, c.article_id, c.chunk_index, c.heading_context, c.content,
       a.title, a.canonical_url, a.source_url,
       1 - (e.embedding <=> :vector::vector) AS score
FROM chunk_embeddings e
JOIN chunks c ON c.chunk_id = e.chunk_id
JOIN articles a ON a.article_id = c.article_id
WHERE a.status = 'ok' AND a.is_active
  AND e.embedding_model = :model AND e.embedding_dim = :dimensions
ORDER BY e.embedding <=> :vector::vector ASC
LIMIT :limit
"""

_INDEX_METADATA = """
SELECT e.embedding_model, e.embedding_dim, count(*)
FROM chunk_embeddings e
JOIN chunks c ON c.chunk_id = e.chunk_id
JOIN articles a ON a.article_id = c.article_id
WHERE a.status = 'ok' AND a.is_active
GROUP BY e.embedding_model, e.embedding_dim
"""

class PostgresKnowledgeStore:
    def __init__(self, connection: pg8000.native.Connection) -> None:
        self.connection = connection

    def _run(self, sql: str, **params: object) -> list:
        return self.connection.run(sql, **params)

    def start_run(self, model: str, dimensions: int) -> int:
        rows = self._run(
            "INSERT INTO indexing_runs (status, model, dimensions) "
            "VALUES ('running', :model, :dimensions) RETURNING run_id",
            model=model,
            dimensions=dimensions,
        )
        return int(rows[0][0])

    def finish_run(self, run_id: int, report: IndexReport) -> None:
        self._run(
            "UPDATE indexing_runs SET "
            "status = :status, model = :model, dimensions = :dimensions, "
            "finished_at = now(), articles_processed = :ap, articles_failed = :af, "
            "chunks_written = :cw, chunks_pruned = :cp, chunks_embedded = :ce, "
            "chunks_skipped = :cs, chunks_failed = :cf, error = :error "
            "WHERE run_id = :run_id",
            status=report.status,
            model=report.model,
            dimensions=report.dimensions,
            ap=report.articles_processed,
            af=report.articles_failed,
            cw=report.chunks_written,
            cp=report.chunks_pruned,
            ce=report.chunks_embedded,
            cs=report.chunks_skipped,
            cf=report.chunks_failed,
            error="; ".join(report.errors) or None,
            run_id=run_id,
        )

    def upsert_article(self, article: ArticleRecord) -> None:
        self._run(
            _UPSERT_ARTICLE,
            article_id=article.article_id,
            canonical_url=article.canonical_url,
            source_url=article.source_url,
            title=article.title,
            last_modified=article.last_modified,
            change_frequency=article.change_frequency,
            priority=article.priority,
            fetched_at=article.fetched_at,
            http_status=article.http_status,
            source_content_hash=article.source_content_hash,
            normalized_content_hash=article.normalized_content_hash,
            char_count=article.char_count,
            status=article.status,
            error=article.error,
        )

    def sync_chunks(self, article_id: str, chunks: Sequence[ChunkRecord]) -> int:
        existing = {
            row[0]
            for row in self._run(
                "SELECT chunk_id FROM chunks WHERE article_id = :article_id",
                article_id=article_id,
            )
        }
        incoming = {chunk.chunk_id for chunk in chunks}
        stale = [chunk_id for chunk_id in existing if chunk_id not in incoming]
        for chunk_id in stale:
            self._run("DELETE FROM chunks WHERE chunk_id = :chunk_id", chunk_id=chunk_id)

        for chunk in chunks:
            self._run(
                _UPSERT_CHUNK,
                chunk_id=chunk.chunk_id,
                article_id=chunk.article_id,
                chunk_index=chunk.chunk_index,
                heading_context=chunk.heading_context,
                content=chunk.content,
                char_count=chunk.char_count,
                content_hash=chunk.content_hash,
                article_content_hash=chunk.article_content_hash,
            )

        self._run(
            "UPDATE articles SET chunk_count = :count, updated_at = now() "
            "WHERE article_id = :article_id",
            count=len(chunks),
            article_id=article_id,
        )
        return len(stale)

    def get_embeddings_index(self) -> dict[str, tuple[str, int]]:
        rows = self._run(
            "SELECT chunk_id, embedding_model, embedding_dim FROM chunk_embeddings"
        )
        return {row[0]: (row[1], int(row[2])) for row in rows}

    def save_embedding(self, record: EmbeddingRecord) -> None:
        self._run(
            _UPSERT_EMBEDDING,
            chunk_id=record.chunk_id,
            vector=format_vector(record.embedding),
            model=record.model,
            dimensions=record.dimensions,
        )
        self._run(
            "UPDATE chunks SET embedding_status = 'embedded', embedding_error = NULL, "
            "updated_at = now() WHERE chunk_id = :chunk_id",
            chunk_id=record.chunk_id,
        )

    def record_embedding_failure(self, chunk_id: str, error: str) -> None:
        self._run(
            "UPDATE chunks SET embedding_status = 'failed', embedding_error = :error, "
            "updated_at = now() WHERE chunk_id = :chunk_id",
            chunk_id=chunk_id,
            error=error[:1000],
        )

    def search_similar(
        self, embedding: list[float], model: str, dimensions: int, limit: int
    ) -> list[SearchHit]:
        vector = format_vector(embedding)
        rows = self._run(
            _SEARCH_SIMILAR,
            vector=vector,
            model=model,
            dimensions=dimensions,
            limit=int(limit),
        )
        return [
            SearchHit(
                chunk_id=row[0],
                article_id=row[1],
                chunk_index=int(row[2]),
                heading_context=row[3] or "",
                content=row[4],
                title=row[5] or "",
                canonical_url=row[6],
                source_url=row[7],
                score=float(row[8]),
            )
            for row in rows
        ]

    def index_metadata(self) -> IndexMetadata:
        counts: dict[tuple[str, int], int] = {}
        for model, dimension, count in self._run(_INDEX_METADATA):
            counts[(model, int(dimension))] = int(count)
        return IndexMetadata(
            indexed_chunks=sum(counts.values()), model_dimensions=counts
        )

    def close(self) -> None:
        self.connection.close()
