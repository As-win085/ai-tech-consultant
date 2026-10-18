"""Manifest-backed full ingestion orchestration for the Knowledge Brain."""

from __future__ import annotations

import json
from pathlib import Path

from app.crawler import SITEMAP_URL, crawl
from app.embeddings import EmbeddingProvider, build_embedding_provider
from app.indexer import IndexConfig, index_document
from app.settings import get_chat_settings, get_embedding_settings, require_database_url


def _open_store():
    from app.db import apply_migrations, connect
    from app.postgres_store import PostgresKnowledgeStore

    connection = connect(require_database_url())
    apply_migrations(connection)
    return connection, PostgresKnowledgeStore(connection)


def run_ingestion(
    *,
    sitemap_url: str = SITEMAP_URL,
    manifest_path: str | Path = "data/ingestion-manifest.json",
    output_path: str | Path = "data/articles-current.json",
    store=None,
    provider: EmbeddingProvider | None = None,
    crawler=crawl,
) -> dict:
    """Crawl the sitemap, index successful records, and deactivate removed IDs.

    Store/provider/crawler injection keeps the orchestration testable without a
    database or external model. Production calls create a PostgreSQL store and
    use the configured embedding provider.
    """
    owned_connection = None
    if store is None:
        owned_connection, store = _open_store()
    if provider is None:
        provider = build_embedding_provider(get_embedding_settings())
    run_id = store.start_ingestion_run(sitemap_url)
    source: dict = {}
    deactivated = 0
    try:
        chat_provider = None
        settings = get_chat_settings()
        if settings.provider.lower() != "fake":
            from app.chat import build_chat_provider
            chat_provider = build_chat_provider(settings)
        describe = getattr(chat_provider, "describe_image", None) if chat_provider else None
        document = crawler(
            limit=None,
            sitemap_url=sitemap_url,
            output_path=output_path,
            manifest_path=manifest_path,
            image_describer=describe,
        )
        source = document["source"]
        present_ids = set(source.get("article_ids_in_sitemap", []))
        if not present_ids:
            raise RuntimeError("the complete sitemap contained no article IDs; refusing to deactivate existing pages")

        # A failed fetch is not evidence that a previously indexed page is gone.
        successful = [article for article in document.get("articles", []) if article.get("status") == "ok"]
        report = index_document(store, provider, {"articles": successful}, IndexConfig())
        deactivated = store.deactivate_missing_articles(present_ids)
        status = "ok" if report.status == "ok" and source.get("articles_failed", 0) == 0 else "partial"
        store.finish_ingestion_run(run_id, status, source, deactivated)
        return {
            "run_id": run_id,
            "status": status,
            "source": source,
            "index": report.summary(),
            "articles_deactivated": deactivated,
        }
    except Exception as exc:
        store.finish_ingestion_run(run_id, "failed", source, deactivated, type(exc).__name__)
        raise
    finally:
        if owned_connection is not None:
            owned_connection.close()


def get_ingestion_status() -> dict | None:
    connection, store = _open_store()
    try:
        return store.latest_ingestion_run()
    finally:
        store.close()


def cli() -> int:
    """Run one ingestion suitable for cron or Windows Task Scheduler."""
    result = run_ingestion()
    print(json.dumps(result, default=str, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(cli())
