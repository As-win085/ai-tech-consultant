"""Opt-in retrieval integration tests against real PostgreSQL + pgvector.

Skipped unless ``TEST_DATABASE_URL`` is set. These prove that semantic retrieval
computed in the database (pgvector cosine ``<=>``) agrees with the in-memory
reference implementation, and that inactive/failed articles and model mismatches
are handled exactly as in the unit tests.

    $env:TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:55432/knowledge_brain"
    python -m pytest tests/test_retrieval_integration.py -v
"""

import os

import pytest

from app.crawler import compute_content_hash
from app.db import apply_migrations, connect
from app.embeddings import FakeEmbeddingProvider
from app.indexer import IndexConfig, index_document
from app.postgres_store import PostgresKnowledgeStore
from app.retriever import IndexModelMismatch, RetrievalConfig, Retriever
from app.store import InMemoryKnowledgeStore

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set"),
]

TABLES = "chunk_embeddings, chunks, articles, indexing_runs"
BASE = "https://support.brilliantdirectories.com"
PROVIDER = FakeEmbeddingProvider(model_name="retrieval-test-model", dimensions=8)
CONFIG = IndexConfig(chunk_size=1000, overlap=200, batch_size=64)


def make_article(article_id, title, paragraphs, **overrides):
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


DOCUMENT = {
    "source": {"site": "example"},
    "articles": [
        make_article("1", "Password Reset", ["Open Account settings and reset your password."]),
        make_article("2", "Billing", ["Invoices are billed monthly to the card on file."]),
        make_article("3", "Membership", ["Membership levels control directory access."]),
        make_article("4", "Broken", [], status="failed", text=None, error="HTTP 404"),
    ],
}

CONFIG = IndexConfig(chunk_size=1000, overlap=200, batch_size=64)


@pytest.fixture
def store():
    connection = connect(TEST_DATABASE_URL)
    apply_migrations(connection)
    connection.run(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE")
    yield PostgresKnowledgeStore(connection)
    connection.close()


def index_all(store):
    index_document(store, PROVIDER, DOCUMENT, CONFIG)


def test_database_retrieval_matches_in_memory_reference(store):
    index_all(store)
    memory = InMemoryKnowledgeStore()
    index_document(memory, PROVIDER, DOCUMENT, CONFIG)

    config = RetrievalConfig(top_k=5, min_score=-1.0, max_per_article=5, oversample=4)
    db_result = Retriever(store, PROVIDER, config).retrieve("password reset")
    memory_result = Retriever(memory, PROVIDER, config).retrieve("password reset")

    assert db_result.indexed_chunks == memory_result.indexed_chunks
    assert [h.chunk_id for h in db_result.hits] == [h.chunk_id for h in memory_result.hits]
    for db_hit, memory_hit in zip(db_result.hits, memory_result.hits):
        assert db_hit.score == pytest.approx(memory_hit.score, abs=1e-6)
        assert db_hit.title == memory_hit.title
        assert db_hit.canonical_url == memory_hit.canonical_url


def test_scores_are_descending_and_above_threshold(store):
    index_all(store)
    config = RetrievalConfig(top_k=5, min_score=0.1, max_per_article=5, oversample=4)
    result = Retriever(store, PROVIDER, config).retrieve("billing invoice")
    scores = [hit.score for hit in result.hits]
    assert scores == sorted(scores, reverse=True)
    assert all(score >= 0.1 for score in scores)


def test_inactive_article_is_excluded(store):
    index_all(store)
    store.connection.run("UPDATE articles SET is_active = FALSE WHERE article_id = '1'")

    config = RetrievalConfig(top_k=10, min_score=-1.0, max_per_article=10, oversample=4)
    result = Retriever(store, PROVIDER, config).retrieve("password reset")
    assert all(hit.article_id != "1" for hit in result.hits)

    active_chunks = store.connection.run(
        "SELECT count(*) FROM chunk_embeddings e JOIN chunks c ON c.chunk_id = e.chunk_id "
        "JOIN articles a ON a.article_id = c.article_id WHERE a.is_active"
    )[0][0]
    assert result.indexed_chunks == active_chunks


def test_failed_article_is_excluded(store):
    index_all(store)
    config = RetrievalConfig(top_k=10, min_score=-1.0, max_per_article=10, oversample=4)
    result = Retriever(store, PROVIDER, config).retrieve("anything")
    assert all(hit.article_id != "4" for hit in result.hits)


def test_model_mismatch_raises(store):
    index_all(store)
    other = FakeEmbeddingProvider(model_name="different-model", dimensions=8)
    with pytest.raises(IndexModelMismatch):
        Retriever(store, other, RetrievalConfig(min_score=-1.0)).retrieve("password")
