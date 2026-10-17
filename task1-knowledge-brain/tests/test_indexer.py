import pytest

from app.crawler import compute_content_hash
from app.embeddings import EmbeddingError, FakeEmbeddingProvider
from app.indexer import IndexConfig, index_document, prepare_article
from app.store import InMemoryKnowledgeStore

BASE = "https://support.brilliantdirectories.com"
CONFIG = IndexConfig(chunk_size=1000, overlap=200, batch_size=64)


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


def make_document(articles: list[dict]) -> dict:
    return {"source": {"site": "example", "sitemap_url": "sitemap"}, "articles": articles}


def article_one(paragraph="First article body paragraph.") -> dict:
    return make_article("1", "Article One", [paragraph])


def article_two() -> dict:
    return make_article("2", "Article Two", ["Second article body paragraph."])


def failed_article() -> dict:
    return make_article(
        "3", "Broken", [], status="failed", text=None, error="HTTP 404: not found"
    )


class BoomProvider:
    model_name = "boom"
    dimensions = 4

    def embed(self, texts):
        raise EmbeddingError("provider unavailable")


class FlakyProvider:
    model_name = "flaky"
    dimensions = 4

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        if self.calls == 1:
            return [[0.0] * 4 for _ in texts]
        raise EmbeddingError("second batch failed")


class ShortProvider:
    model_name = "short"
    dimensions = 8

    def embed(self, texts):
        return [[0.0] * 4 for _ in texts]


class ExplodingStore(InMemoryKnowledgeStore):
    def sync_chunks(self, article_id, chunks):
        raise RuntimeError("database connection lost")


def test_index_document_persists_articles_chunks_and_embeddings():
    store = InMemoryKnowledgeStore()
    provider = FakeEmbeddingProvider(model_name="fake-v1", dimensions=8)
    report = index_document(store, provider, make_document([article_one(), article_two(), failed_article()]), CONFIG)

    assert report.status == "ok"
    assert report.articles_processed == 2
    assert report.articles_failed == 1
    assert report.chunks_written == 2
    assert report.chunks_embedded == 2
    assert report.chunks_skipped == 0
    assert len(store.chunks) == 2
    assert len(store.embeddings) == 2
    assert store.articles["3"].status == "failed"
    assert store.articles["3"].error == "HTTP 404: not found"
    assert store.chunks_for_article("3") == []


def test_repeat_run_creates_no_duplicates_and_skips_embeddings():
    store = InMemoryKnowledgeStore()
    provider = FakeEmbeddingProvider(model_name="fake-v1", dimensions=8)
    document = make_document([article_one(), article_two()])

    index_document(store, provider, document, CONFIG)
    article_count = len(store.articles)
    chunk_count = len(store.chunks)
    embedding_count = len(store.embeddings)

    report = index_document(store, provider, document, CONFIG)

    assert report.chunks_embedded == 0
    assert report.chunks_skipped == chunk_count
    assert len(store.articles) == article_count
    assert len(store.chunks) == chunk_count
    assert len(store.embeddings) == embedding_count


def test_changed_content_reembeds_only_changed_chunks():
    store = InMemoryKnowledgeStore()
    provider = FakeEmbeddingProvider(model_name="fake-v1", dimensions=8)

    index_document(store, provider, make_document([article_one(), article_two()]), CONFIG)
    stable_chunk_ids = {
        chunk_id for chunk_id, chunk in store.chunks.items() if chunk.article_id == "2"
    }

    changed = article_one(paragraph="Completely different body paragraph now.")
    report = index_document(store, provider, make_document([changed, article_two()]), CONFIG)

    assert report.chunks_pruned == 1
    assert report.chunks_embedded == 1
    assert report.chunks_skipped == 1
    assert stable_chunk_ids <= set(store.chunks)
    assert stable_chunk_ids <= set(store.embeddings)


def test_changed_model_reembeds_all_without_mixing():
    store = InMemoryKnowledgeStore()
    document = make_document([article_one(), article_two()])
    index_document(store, FakeEmbeddingProvider(model_name="model-a", dimensions=8), document, CONFIG)

    report = index_document(
        store, FakeEmbeddingProvider(model_name="model-b", dimensions=8), document, CONFIG
    )

    assert report.chunks_embedded == len(store.chunks)
    assert report.chunks_skipped == 0
    assert len(store.embeddings) == len(store.chunks)
    assert {record.model for record in store.embeddings.values()} == {"model-b"}


def test_changed_dimensions_reembed():
    store = InMemoryKnowledgeStore()
    document = make_document([article_one()])
    index_document(store, FakeEmbeddingProvider(model_name="model-a", dimensions=8), document, CONFIG)

    report = index_document(
        store, FakeEmbeddingProvider(model_name="model-a", dimensions=16), document, CONFIG
    )

    assert report.chunks_embedded == 1
    assert {record.dimensions for record in store.embeddings.values()} == {16}


def test_provider_failure_marks_all_chunks_failed():
    store = InMemoryKnowledgeStore()
    report = index_document(store, BoomProvider(), make_document([article_one(), article_two()]), CONFIG)

    assert report.status == "failed"
    assert report.chunks_embedded == 0
    assert report.chunks_failed == report.chunks_written
    assert len(store.chunk_errors) == report.chunks_failed
    assert report.errors


def test_partial_failure_reports_partial_status():
    store = InMemoryKnowledgeStore()
    config = IndexConfig(chunk_size=1000, overlap=200, batch_size=1)
    report = index_document(store, FlakyProvider(), make_document([article_one(), article_two()]), config)

    assert report.status == "partial"
    assert report.chunks_embedded == 1
    assert report.chunks_failed == 1
    assert len(store.chunk_errors) == 1


def test_restart_after_partial_failure_completes_missing_chunks():
    store = InMemoryKnowledgeStore()
    document = make_document([article_one(), article_two()])
    index_document(store, FlakyProvider(), document, IndexConfig(batch_size=1))

    report = index_document(
        store, FakeEmbeddingProvider(model_name="flaky", dimensions=4), document, IndexConfig(batch_size=1)
    )

    assert report.chunks_embedded == 1
    assert report.chunks_skipped == 1
    assert report.status == "ok"
    assert not store.chunk_errors


def test_dimension_mismatch_from_provider_marks_failed():
    store = InMemoryKnowledgeStore()
    report = index_document(store, ShortProvider(), make_document([article_one()]), CONFIG)

    assert report.chunks_embedded == 0
    assert report.chunks_failed == 1
    assert report.status == "failed"


def test_batch_size_does_not_change_embeddings():
    provider = FakeEmbeddingProvider(model_name="fake-v1", dimensions=8)
    document = make_document([article_one(), article_two()])

    small = InMemoryKnowledgeStore()
    large = InMemoryKnowledgeStore()
    index_document(small, provider, document, IndexConfig(batch_size=1))
    index_document(large, provider, document, IndexConfig(batch_size=10))

    small_vectors = {cid: list(rec.embedding) for cid, rec in small.embeddings.items()}
    large_vectors = {cid: list(rec.embedding) for cid, rec in large.embeddings.items()}
    assert small_vectors == large_vectors


def test_article_and_chunk_metadata_preserved():
    store = InMemoryKnowledgeStore()
    index_document(store, FakeEmbeddingProvider(model_name="m", dimensions=8), make_document([article_one()]), CONFIG)

    article = store.articles["1"]
    assert article.canonical_url == f"{BASE}/support/solutions/articles/1-slug"
    assert article.source_url == f"{BASE}/support/solutions/articles/1-slug"
    assert article.priority == 0.5
    assert article.last_modified == "2026-01-01T00:00:00+00:00"
    assert article.normalized_content_hash

    chunk = next(iter(store.chunks.values()))
    assert store.articles[chunk.article_id].canonical_url == article.canonical_url


def test_empty_body_article_produces_no_chunks_but_is_persisted():
    store = InMemoryKnowledgeStore()
    title_only = make_article("7", "Only A Title", [])
    report = index_document(store, FakeEmbeddingProvider(dimensions=8), make_document([title_only]), CONFIG)

    assert report.chunks_written == 0
    assert store.articles["7"].status == "ok"
    assert store.chunks_for_article("7") == []


def test_prepare_article_marks_failed_records():
    article, chunks = prepare_article(failed_article(), CONFIG.chunk_config())
    assert article.status == "failed"
    assert article.error == "HTTP 404: not found"
    assert chunks == []


def test_store_error_marks_run_failed_and_reraises():
    store = ExplodingStore()
    with pytest.raises(RuntimeError):
        index_document(store, FakeEmbeddingProvider(dimensions=8), make_document([article_one()]), CONFIG)

    assert store.runs[1]["status"] == "failed"
    assert any("run failed" in error for error in store.runs[1]["errors"])
