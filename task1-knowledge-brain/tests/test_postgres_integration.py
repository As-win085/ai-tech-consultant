"""Opt-in integration tests against a real PostgreSQL database with pgvector.

These are skipped unless ``TEST_DATABASE_URL`` is set. They are the only tests
that prove the persistence layer works against a real database; ordinary tests
use the in-memory store.

Run with, for example:

    $env:TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:55432/knowledge_brain"
    python -m pytest tests/test_postgres_integration.py -v
"""

import os

import pytest

from app.crawler import compute_content_hash
from app.db import apply_migrations, connect
from app.embeddings import FakeEmbeddingProvider
from app.indexer import IndexConfig, index_document
from app.postgres_store import PostgresKnowledgeStore

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set"
    ),
]

TABLES = "chunk_embeddings, chunks, articles, indexing_runs"

BASE = "https://support.brilliantdirectories.com"
CONFIG = IndexConfig(chunk_size=1000, overlap=200, batch_size=64)
TABLES = "chunk_embeddings, chunks, articles, indexing_runs"


def make_article(article_id: str, title: str, paragraphs: list[str], **overrides) -> dict:
    text = "\n".join([title, *paragraphs])
    record = {
        "id": article_id,
        "url": f"{BASE}/support/solutions/articles/{article_id}-slug",
        "canonical_url": f"{BASE}/support/solutions/articles/{article_id}-slug",
        "title": title,
        "text": text,
        "headings": [{"level": 1, "text": title}],
        "char_count": len(text),
        "content_hash": compute_content_hash(text),
        "last_modified": "2026-01-01T00:00:00+00:00",
        "change_frequency": "always",
        "priority": 0.5,
        "fetched_at": "2026-01-02T00:00:00+00:00",
        "http_status": 200,
        "status": "ok",
        "error": None,
    }
    record.update(overrides)
    return record


def make_document(articles):
    return {"source": {"site": "example"}, "articles": articles}


@pytest.fixture
def store():
    connection = connect(TEST_DATABASE_URL)
    apply_migrations(connection)
    connection.run(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE")
    yield PostgresKnowledgeStore(connection)
    connection.close()


def counts(store) -> dict:
    conn = store.connection
    return {
        "articles": conn.run("SELECT count(*) FROM articles")[0][0],
        "chunks": conn.run("SELECT count(*) FROM chunks")[0][0],
        "embeddings": conn.run("SELECT count(*) FROM chunk_embeddings")[0][0],
        "runs": conn.run("SELECT count(*) FROM indexing_runs")[0][0],
    }


def test_index_persists_rows_matching_report(store):
    document = make_document(
        [
            make_article("1", "One", ["Body one."]),
            make_article("2", "Two", ["Body two."]),
            make_article("3", "Broken", [], status="failed", text=None, error="HTTP 404"),
        ]
    )
    report = index_document(store, FakeEmbeddingProvider(model_name="m", dimensions=8), document, IndexConfig())

    persisted = counts(store)
    assert report.status == "ok"
    assert persisted["articles"] == 3
    assert persisted["chunks"] == report.chunks_written == 2
    assert persisted["embeddings"] == report.chunks_embedded == 2
    assert persisted["runs"] == 1

    status = store.connection.run("SELECT status FROM articles WHERE article_id='3'")[0][0]
    assert status == "failed"


def test_repeat_run_creates_no_duplicates(store):
    document = make_document([make_article("1", "One", ["Body one."]), make_article("2", "Two", ["Body two."])])
    provider = FakeEmbeddingProvider(model_name="m", dimensions=8)

    index_document(store, provider, document, IndexConfig())
    before = counts(store)
    report = index_document(store, provider, document, IndexConfig())
    after = counts(store)

    assert report.chunks_embedded == 0
    assert report.chunks_skipped == before["chunks"]
    assert before["articles"] == after["articles"]
    assert before["chunks"] == after["chunks"]
    assert before["embeddings"] == after["embeddings"]


def test_changed_content_prunes_and_reembeds(store):
    provider = FakeEmbeddingProvider(model_name="m", dimensions=8)
    index_document(
        store,
        provider,
        make_document([make_article("1", "One", ["Original body."]), make_article("2", "Two", ["Body two."])]),
        IndexConfig(),
    )
    stable = store.connection.run("SELECT chunk_id FROM chunks WHERE article_id='2'")[0][0]

    report = index_document(
        store,
        provider,
        make_document([make_article("1", "One", ["Changed body."]), make_article("2", "Two", ["Body two."])]),
        IndexConfig(),
    )

    assert report.chunks_pruned == 1
    assert report.chunks_embedded == 1
    assert report.chunks_skipped == 1
    assert store.connection.run("SELECT count(*) FROM chunks WHERE chunk_id=:c", c=stable)[0][0] == 1
    assert counts(store)["embeddings"] == counts(store)["chunks"]


def test_changed_model_reembeds_without_mixing(store):
    document = make_document([make_article("1", "One", ["Body one."]), make_article("2", "Two", ["Body two."])])
    index_document(store, FakeEmbeddingProvider(model_name="model-a", dimensions=8), document, IndexConfig())

    report = index_document(
        store, FakeEmbeddingProvider(model_name="model-b", dimensions=8), document, IndexConfig()
    )

    assert report.chunks_embedded == counts(store)["chunks"]
    assert report.chunks_skipped == 0
    models = store.connection.run("SELECT DISTINCT embedding_model FROM chunk_embeddings")
    assert [row[0] for row in models] == ["model-b"]
    assert counts(store)["embeddings"] == counts(store)["chunks"]


def test_metadata_and_vector_dimensions_persisted(store):
    document = make_document([make_article("1", "One", ["Body one."])])
    index_document(store, FakeEmbeddingProvider(model_name="m", dimensions=12), document, IndexConfig())

    row = store.connection.run(
        "SELECT a.canonical_url, a.priority, e.embedding_model, vector_dims(e.embedding) "
        "FROM articles a JOIN chunks c ON c.article_id = a.article_id "
        "JOIN chunk_embeddings e ON e.chunk_id = c.chunk_id WHERE a.article_id='1'"
    )[0]
    assert row[0] == "https://support.brilliantdirectories.com/support/solutions/articles/1-slug"
    assert row[1] == 0.5
    assert row[2] == "m"
    assert row[3] == 12
