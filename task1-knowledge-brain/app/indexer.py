"""Embedding + indexing pipeline for the Knowledge Brain.

Takes a crawler document, normalizes and chunks it, persists articles and
chunks, and generates/stores embeddings for chunks that need them. The pipeline
is idempotent and restartable:

- articles are upserted by ``article_id``;
- chunks are upserted by stable ``chunk_id`` and stale chunks are pruned;
- a chunk is re-embedded only if it is new/changed or its stored embedding was
  produced by a different model or with different dimensions;
- per-chunk embedding failures are recorded without marking the run successful.

It depends only on the ``KnowledgeStore`` interface and an ``EmbeddingProvider``,
so it runs against the in-memory store with a fake provider in tests.
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, TypeVar

from app.chunker import ChunkConfig, chunk_article
from app.embeddings import (
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingResponseError,
    build_embedding_provider,
)
from app.models import ArticleRecord, ChunkRecord, EmbeddingRecord, IndexReport
from app.normalizer import normalize_article, resolve_article_id
from app.settings import ConfigError, get_embedding_settings, require_database_url
from app.store import InMemoryKnowledgeStore, KnowledgeStore

DEFAULT_INPUT = "data/articles-sample.json"

T = TypeVar("T")


@dataclass
class IndexConfig:
    chunk_size: int = 1000
    overlap: int = 200
    batch_size: int = 64

    def chunk_config(self) -> ChunkConfig:
        return ChunkConfig(chunk_size=self.chunk_size, overlap=self.overlap)


def _batched(items: list[T], size: int) -> Iterator[list[T]]:
    step = max(1, size)
    for index in range(0, len(items), step):
        yield items[index : index + step]


def prepare_article(
    raw_record: dict, chunk_config: ChunkConfig
) -> tuple[ArticleRecord, list[ChunkRecord]]:
    """Build an article record and its chunks from one crawler record."""
    normalized = normalize_article(raw_record)
    if normalized is None:
        article = ArticleRecord(
            article_id=resolve_article_id(raw_record),
            title=(raw_record.get("title") or "").strip(),
            canonical_url=raw_record.get("canonical_url") or raw_record.get("url"),
            source_url=raw_record.get("url"),
            last_modified=raw_record.get("last_modified"),
            change_frequency=raw_record.get("change_frequency"),
            priority=raw_record.get("priority"),
            fetched_at=raw_record.get("fetched_at"),
            http_status=raw_record.get("http_status"),
            source_content_hash=raw_record.get("content_hash"),
            normalized_content_hash=None,
            char_count=int(raw_record.get("char_count") or 0),
            status="failed",
            error=raw_record.get("error") or "record not normalized (failed or empty)",
        )
        return article, []

    metadata = normalized["metadata"]
    article = ArticleRecord(
        article_id=normalized["article_id"],
        title=normalized["title"],
        canonical_url=normalized["canonical_url"],
        source_url=normalized["source_url"],
        last_modified=metadata.get("last_modified"),
        change_frequency=metadata.get("change_frequency"),
        priority=metadata.get("priority"),
        fetched_at=metadata.get("fetched_at"),
        http_status=metadata.get("http_status"),
        source_content_hash=normalized["source_content_hash"],
        normalized_content_hash=normalized["normalized_content_hash"],
        char_count=normalized["char_count"],
        status="ok",
        error=None,
    )

    chunks = [
        ChunkRecord(
            chunk_id=chunk["chunk_id"],
            article_id=chunk["article_id"],
            chunk_index=chunk["chunk_index"],
            content=chunk["content"],
            heading_context=chunk["heading_context"],
            char_count=chunk["char_count"],
            content_hash=chunk["content_hash"],
            article_content_hash=chunk["article_content_hash"],
        )
        for chunk in chunk_article(normalized, chunk_config)
    ]
    return article, chunks


def _compute_status(report: IndexReport) -> str:
    if report.chunks_failed == 0:
        return "ok"
    if report.chunks_embedded == 0:
        return "failed"
    return "partial"


def index_document(
    store: KnowledgeStore,
    provider: EmbeddingProvider,
    crawl_document: dict,
    config: IndexConfig | None = None,
) -> IndexReport:
    config = config or IndexConfig()
    report = IndexReport(model=provider.model_name, dimensions=provider.dimensions)
    report.run_id = store.start_run(provider.model_name, provider.dimensions)
    chunk_config = config.chunk_config()

    try:
        embeddings_index = store.get_embeddings_index()
        pending: list[ChunkRecord] = []

        for raw_record in (crawl_document or {}).get("articles", []):
            article, chunks = prepare_article(raw_record, chunk_config)
            store.upsert_article(article)

            if article.status != "ok":
                report.articles_failed += 1
                continue

            report.articles_processed += 1
            report.chunks_pruned += store.sync_chunks(article.article_id, chunks)
            report.chunks_written += len(chunks)

            for chunk in chunks:
                if embeddings_index.get(chunk.chunk_id) == (
                    provider.model_name,
                    provider.dimensions,
                ):
                    report.chunks_skipped += 1
                else:
                    pending.append(chunk)

        for batch in _batched(pending, config.batch_size):
            try:
                vectors = provider.embed([chunk.content for chunk in batch])
                if len(vectors) != len(batch):
                    raise EmbeddingResponseError(
                        f"provider returned {len(vectors)} vectors for {len(batch)} chunks"
                    )
                for vector in vectors:
                    if len(vector) != provider.dimensions:
                        raise EmbeddingResponseError(
                            f"provider returned a {len(vector)}-dimension vector, "
                            f"expected {provider.dimensions}"
                        )
                for chunk, vector in zip(batch, vectors):
                    store.save_embedding(
                        EmbeddingRecord(
                            chunk_id=chunk.chunk_id,
                            embedding=vector,
                            model=provider.model_name,
                            dimensions=provider.dimensions,
                        )
                    )
                    report.chunks_embedded += 1
            except EmbeddingError as exc:
                for chunk in batch:
                    store.record_embedding_failure(chunk.chunk_id, str(exc))
                    report.chunks_failed += 1
                report.errors.append(
                    f"embedding batch of {len(batch)} chunk(s) failed: {exc}"
                )
    except Exception as exc:  # run-level failure (e.g. database error)
        report.status = "failed"
        report.errors.append(f"run failed: {exc}")
        try:
            store.finish_run(report.run_id, report)
        except Exception:
            pass
        raise

    report.status = _compute_status(report)
    store.finish_run(report.run_id, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize, chunk, persist, and embed crawled support articles."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Crawled articles JSON path.")
    parser.add_argument("--chunk-size", type=int, default=1000, help="Max characters per chunk.")
    parser.add_argument("--overlap", type=int, default=200, help="Shared characters between chunks.")
    parser.add_argument(
        "--batch-size", type=int, default=None, help="Embedding batch size (default from env)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use an in-memory store and fake embeddings; nothing is persisted.",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return 1
    crawl_document = json.loads(input_path.read_text(encoding="utf-8"))

    settings = get_embedding_settings()
    config = IndexConfig(
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        batch_size=args.batch_size or settings.batch_size,
    )

    connection = None
    try:
        if args.dry_run:
            from app.embeddings import FakeEmbeddingProvider

            print(
                "[DRY RUN] In-memory store + deterministic fake embeddings. "
                "Nothing is persisted and these are NOT real embeddings."
            )
            store: KnowledgeStore = InMemoryKnowledgeStore()
            provider: EmbeddingProvider = FakeEmbeddingProvider(
                model_name="dry-run-fake", dimensions=64
            )
        else:
            database_url = require_database_url()
            from app.db import apply_migrations, connect
            from app.postgres_store import PostgresKnowledgeStore

            connection = connect(database_url)
            applied = apply_migrations(connection)
            if applied:
                print(f"Applied migrations: {', '.join(applied)}")
            store = PostgresKnowledgeStore(connection)
            provider = build_embedding_provider(settings)

        report = index_document(store, provider, crawl_document, config)
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        return 2
    finally:
        if connection is not None:
            connection.close()

    summary = report.summary()
    print(f"Status:            {summary['status']}")
    print(f"Model/dimensions:  {summary['model']}/{summary['dimensions']}")
    print(f"Articles processed:{summary['articles_processed']}")
    print(f"Articles failed:   {summary['articles_failed']}")
    print(f"Chunks written:    {summary['chunks_written']}")
    print(f"Chunks pruned:     {summary['chunks_pruned']}")
    print(f"Chunks embedded:   {summary['chunks_embedded']}")
    print(f"Chunks skipped:    {summary['chunks_skipped']}")
    print(f"Chunks failed:     {summary['chunks_failed']}")
    for message in summary["errors"]:
        print(f"  ! {message}")
    return 0 if summary["status"] == "ok" else 3


if __name__ == "__main__":
    raise SystemExit(main())
