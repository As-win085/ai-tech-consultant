import hashlib

import pytest

from app.chunker import (
    ChunkConfig,
    build_chunks_document,
    chunk_article,
    pack_chunks,
)
from app.crawler import ARTICLE_MARKER, compute_content_hash
from app.normalizer import normalize_article

BASE = "https://support.brilliantdirectories.com"
URL = f"{BASE}{ARTICLE_MARKER}5000558363-emails-email-accounts"

ARTICLE_TEXT = (
    "Emails \u00bb Email Accounts\n"
    "Email accounts (mailboxes) at the website's own domain, such as\n"
    "support@example.com\n"
    ", are created and managed in\n"
    "Settings > Domain Manager > Mailboxes\n"
    ". The\n"
    "Emails > Email Accounts\n"
    "menu item opens that tab directly.\n"
    "Before starting\n"
    "Connect a custom domain to the website."
)

ARTICLE_HEADINGS = [
    {"level": 1, "text": "Emails \u00bb Email Accounts"},
    {"level": 2, "text": "Before starting"},
]


def ok_record(**overrides) -> dict:
    record = {
        "id": "5000558363",
        "url": URL,
        "canonical_url": URL,
        "title": "Emails \u00bb Email Accounts",
        "text": ARTICLE_TEXT,
        "headings": ARTICLE_HEADINGS,
        "char_count": len(ARTICLE_TEXT),
        "content_hash": compute_content_hash(ARTICLE_TEXT),
        "last_modified": "2026-06-18T20:33:08+05:30",
        "change_frequency": "always",
        "priority": 0.512,
        "fetched_at": "2026-10-16T20:13:34+00:00",
        "http_status": 200,
        "status": "ok",
        "error": None,
    }
    record.update(overrides)
    return record


def test_chunk_config_defaults():
    config = ChunkConfig()
    assert config.chunk_size == 1000
    assert config.overlap == 200
    assert config.unit == "characters"


@pytest.mark.parametrize(
    "chunk_size,overlap",
    [(0, 0), (-1, 0), (10, -1), (10, 10), (10, 11), (5, 200)],
)
def test_chunk_config_rejects_invalid_values(chunk_size, overlap):
    with pytest.raises(ValueError):
        ChunkConfig(chunk_size=chunk_size, overlap=overlap)


def test_pack_chunks_empty_body():
    assert pack_chunks("", ChunkConfig()) == []
    assert pack_chunks("   ", ChunkConfig()) == []


def test_pack_chunks_short_body_is_single_chunk():
    config = ChunkConfig(chunk_size=1000, overlap=200)
    assert pack_chunks("Short body.", config) == ["Short body."]


def test_pack_chunks_splits_and_respects_size():
    body = "x" * 200
    config = ChunkConfig(chunk_size=100, overlap=20)
    chunks = pack_chunks(body, config)

    assert len(chunks) > 1
    assert all(len(chunk) <= config.chunk_size for chunk in chunks)


def test_pack_chunks_applies_overlap():
    body = "x" * 200
    without = pack_chunks(body, ChunkConfig(chunk_size=100, overlap=0))
    with_overlap = pack_chunks(body, ChunkConfig(chunk_size=100, overlap=20))

    without_chars = sum(len(chunk) for chunk in without)
    with_overlap_chars = sum(len(chunk) for chunk in with_overlap)
    assert with_overlap_chars > without_chars


def test_pack_chunks_loses_no_content():
    tokens = [f"t{index}" for index in range(100)]
    body = " ".join(tokens)
    config = ChunkConfig(chunk_size=40, overlap=10)
    chunks = pack_chunks(body, config)

    joined = " ".join(chunks)
    for token in tokens:
        assert token in joined


def test_chunk_article_links_content_and_metadata():
    article = normalize_article(ok_record())
    config = ChunkConfig(chunk_size=1000, overlap=200)
    chunks = chunk_article(article, config)

    assert len(chunks) == 2
    assert [chunk["chunk_index"] for chunk in chunks] == [0, 1]

    first = chunks[0]
    assert first["article_id"] == article["article_id"]
    assert first["title"] == article["title"]
    assert first["canonical_url"] == article["canonical_url"]
    assert first["source_url"] == article["source_url"]
    assert first["heading_context"] == "Emails \u00bb Email Accounts"
    assert "support@example.com" in first["content"]
    assert first["char_count"] == len(first["content"])
    assert first["article_content_hash"] == article["normalized_content_hash"]

    assert chunks[1]["heading_context"] == (
        "Emails \u00bb Email Accounts > Before starting"
    )


def test_chunk_content_hash_and_id_are_stable():
    article = normalize_article(ok_record())
    config = ChunkConfig(chunk_size=1000, overlap=200)
    chunk = chunk_article(article, config)[0]

    expected_hash = compute_content_hash(
        f"{chunk['heading_context']}\n\n{chunk['content']}"
    )
    expected_id = hashlib.sha256(
        f"{article['article_id']}|{chunk['chunk_index']}|{expected_hash}".encode("utf-8")
    ).hexdigest()[:32]

    assert chunk["content_hash"] == expected_hash
    assert chunk["chunk_id"] == expected_id


def test_chunk_article_skips_empty_sections():
    article = {
        "article_id": "1",
        "title": "Title",
        "canonical_url": URL,
        "source_url": URL,
        "normalized_content_hash": "abc",
        "sections": [
            {"level": 1, "heading": "Empty", "breadcrumb": "Empty", "text": ""},
            {"level": 2, "heading": "Body", "breadcrumb": "Title > Body", "text": "Real content."},
        ],
    }
    chunks = chunk_article(article, ChunkConfig(chunk_size=1000, overlap=200))
    assert len(chunks) == 1
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["heading_context"] == "Title > Body"


def test_chunk_article_splits_long_section():
    long_body = ". ".join(f"Sentence number {index}" for index in range(200)) + "."
    article = {
        "article_id": "1",
        "title": "Title",
        "canonical_url": URL,
        "source_url": URL,
        "normalized_content_hash": "abc",
        "sections": [
            {"level": 1, "heading": "Long", "breadcrumb": "Title > Long", "text": long_body}
        ],
    }
    config = ChunkConfig(chunk_size=300, overlap=50)
    chunks = chunk_article(article, config)

    assert len(chunks) > 1
    assert all(len(chunk["content"]) <= config.chunk_size for chunk in chunks)
    assert [chunk["chunk_index"] for chunk in chunks] == list(range(len(chunks)))


def test_build_chunks_document_summarizes_and_is_deterministic():
    crawl_document = {
        "source": {"sitemap_url": "sitemap", "site": "site", "crawled_at": "now"},
        "articles": [
            ok_record(),
            ok_record(id="9", status="failed", text=None),
        ],
    }
    config = ChunkConfig(chunk_size=1000, overlap=200)

    first = build_chunks_document(crawl_document, config)
    second = build_chunks_document(crawl_document, config)

    assert first["config"] == {"chunk_size": 1000, "overlap": 200, "unit": "characters"}
    assert first["source"]["articles_normalized"] == 1
    assert first["source"]["chunks_total"] == len(first["chunks"])
    assert first["articles"][0]["chunks"] == len(first["chunks"])
    assert [chunk["chunk_id"] for chunk in first["chunks"]] == [
        chunk["chunk_id"] for chunk in second["chunks"]
    ]
