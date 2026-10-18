from app.crawler import compute_content_hash
from app.daily_ingest import seconds_until_next_run
from app.embeddings import FakeEmbeddingProvider
from app.ingestion import run_ingestion
from app.models import ArticleRecord
from app.store import InMemoryKnowledgeStore


def _article(article_id: str, text: str) -> dict:
    url = f"https://support.example/support/solutions/articles/{article_id}-sample"
    return {
        "id": article_id,
        "url": url,
        "canonical_url": url,
        "title": f"Article {article_id}",
        "text": text,
        "headings": [],
        "char_count": len(text),
        "content_hash": compute_content_hash(text),
        "last_modified": "2026-01-01",
        "fetched_at": "2026-01-01T00:00:00Z",
        "http_status": 200,
        "status": "ok",
        "error": None,
    }


def test_run_ingestion_indexes_present_pages_and_deactivates_removed_pages(tmp_path):
    store = InMemoryKnowledgeStore()
    store.upsert_article(ArticleRecord(article_id="old", title="Old", status="ok"))
    doc = {
        "source": {
            "article_urls_found": 1,
            "articles_crawled": 1,
            "articles_ok": 1,
            "articles_failed": 0,
            "article_ids_in_sitemap": ["current"],
        },
        "articles": [_article("current", "Current support content.")],
    }

    def fake_crawl(**kwargs):
        return doc

    result = run_ingestion(
        store=store,
        provider=FakeEmbeddingProvider(dimensions=8),
        crawler=fake_crawl,
        manifest_path=tmp_path / "manifest.json",
        output_path=tmp_path / "articles.json",
    )
    assert result["status"] == "ok"
    assert store.articles["current"].is_active
    assert not store.articles["old"].is_active
    assert result["articles_deactivated"] == 1
    assert store.latest_ingestion_run()["status"] == "ok"


def test_daily_trigger_computes_next_utc_run():
    from datetime import datetime, timezone

    now = datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)
    assert seconds_until_next_run(now, hour_utc=2) == 3600
    assert seconds_until_next_run(now.replace(hour=3), hour_utc=2) == 23 * 3600
