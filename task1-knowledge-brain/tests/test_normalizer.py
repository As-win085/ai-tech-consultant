from app.crawler import ARTICLE_MARKER, compute_content_hash
from app.normalizer import (
    build_blocks,
    build_normalized_document,
    build_sections,
    normalize_article,
    normalize_articles,
)

BASE = "https://support.brilliantdirectories.com"
URL = f"{BASE}{ARTICLE_MARKER}5000558363-emails-email-accounts"

FRAGMENTED_TEXT = "\n".join(
    [
        "Emails \u00bb Email Accounts",
        "Email accounts (mailboxes) at the website's own domain, such as",
        "support@example.com",
        ", are created and managed in",
        "Settings > Domain Manager > Mailboxes",
        ". The",
        "Emails > Email Accounts",
        "menu item opens that tab directly.",
        "Before starting",
        "Connect a custom domain to the website.",
    ]
)

FRAGMENTED_HEADINGS = [
    {"level": 1, "text": "Emails \u00bb Email Accounts"},
    {"level": 2, "text": "Before starting"},
]


def ok_record(**overrides) -> dict:
    record = {
        "id": "5000558363",
        "url": URL,
        "canonical_url": URL,
        "title": "Emails \u00bb Email Accounts",
        "text": FRAGMENTED_TEXT,
        "headings": FRAGMENTED_HEADINGS,
        "char_count": len(FRAGMENTED_TEXT),
        "content_hash": compute_content_hash(FRAGMENTED_TEXT),
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


def test_normalize_article_rejects_failed_status():
    assert normalize_article(ok_record(status="failed", text=None)) is None


def test_normalize_article_rejects_empty_text():
    assert normalize_article(ok_record(text="   \n  ")) is None


def test_normalize_article_rejects_non_dict():
    assert normalize_article(None) is None
    assert normalize_article("not a record") is None


def test_build_blocks_reconstructs_fragmented_paragraph():
    blocks = build_blocks(FRAGMENTED_TEXT, FRAGMENTED_HEADINGS)

    assert blocks[0] == {
        "type": "heading",
        "level": 1,
        "text": "Emails \u00bb Email Accounts",
    }
    assert blocks[1]["type"] == "paragraph"
    assert blocks[1]["text"] == (
        "Email accounts (mailboxes) at the website's own domain, such as "
        "support@example.com, are created and managed in Settings > Domain "
        "Manager > Mailboxes. The Emails > Email Accounts menu item opens that "
        "tab directly."
    )
    assert blocks[2] == {"type": "heading", "level": 2, "text": "Before starting"}
    assert blocks[3] == {
        "type": "paragraph",
        "text": "Connect a custom domain to the website.",
    }


def test_build_blocks_splits_paragraphs_on_sentence_punctuation():
    text = "First sentence.\nSecond sentence.\nA line without end\nstill going."
    blocks = build_blocks(text, [])
    paragraphs = [block["text"] for block in blocks]
    assert paragraphs == [
        "First sentence.",
        "Second sentence.",
        "A line without end still going.",
    ]


def test_build_sections_builds_breadcrumbs_and_groups_paragraphs():
    blocks = build_blocks(FRAGMENTED_TEXT, FRAGMENTED_HEADINGS)
    sections = build_sections(blocks, "Emails \u00bb Email Accounts")

    assert len(sections) == 2
    assert sections[0]["level"] == 1
    assert sections[0]["heading"] == "Emails \u00bb Email Accounts"
    assert sections[0]["breadcrumb"] == "Emails \u00bb Email Accounts"
    assert "support@example.com" in sections[0]["text"]

    assert sections[1]["level"] == 2
    assert sections[1]["heading"] == "Before starting"
    assert sections[1]["breadcrumb"] == "Emails \u00bb Email Accounts > Before starting"
    assert sections[1]["text"] == "Connect a custom domain to the website."


def test_build_sections_handles_content_before_first_heading():
    blocks = build_blocks("Intro line one.\nBody line.", [])
    sections = build_sections(blocks, "My Article")
    assert len(sections) == 1
    assert sections[0]["level"] == 0
    assert sections[0]["heading"] is None
    assert sections[0]["breadcrumb"] == "My Article"
    assert sections[0]["text"] == "Intro line one.\n\nBody line."


def test_normalize_article_produces_expected_fields():
    article = normalize_article(ok_record())

    assert article["article_id"] == "5000558363"
    assert article["title"] == "Emails \u00bb Email Accounts"
    assert article["canonical_url"] == URL
    assert article["source_url"] == URL
    assert article["metadata"]["last_modified"] == "2026-06-18T20:33:08+05:30"
    assert article["metadata"]["change_frequency"] == "always"
    assert article["metadata"]["priority"] == 0.512
    assert article["source_content_hash"] == compute_content_hash(FRAGMENTED_TEXT)
    assert article["char_count"] == len(article["text"])
    assert article["normalized_content_hash"] == compute_content_hash(article["text"])
    assert article["sections"]


def test_normalize_article_id_falls_back_to_canonical_url():
    record = ok_record(id=None, url="", canonical_url=f"{BASE}{ARTICLE_MARKER}42-slug")
    article = normalize_article(record)
    assert article["article_id"] == "42"


def test_normalize_article_id_falls_back_to_url_hash_without_numeric_id():
    record = ok_record(id=None, url="", canonical_url=f"{BASE}/support/somewhere")
    article = normalize_article(record)
    assert article["article_id"].startswith("url-")


def test_normalize_articles_dedupes_and_preserves_order():
    first = ok_record(id="1", title="First")
    second = ok_record(id="2", title="Second")
    duplicate = ok_record(id="1", title="Duplicate")
    failed = ok_record(id="3", status="failed", text=None)

    articles = normalize_articles([first, second, duplicate, failed])
    assert [article["article_id"] for article in articles] == ["1", "2"]
    assert articles[0]["title"] == "First"


def test_normalize_articles_is_deterministic():
    records = [ok_record()]
    first = normalize_articles(records)
    second = normalize_articles(records)
    assert first == second


def test_build_normalized_document_summarizes_source():
    document = build_normalized_document(
        {
            "source": {"sitemap_url": "sitemap", "site": "site", "crawled_at": "now"},
            "articles": [ok_record(), ok_record(id="9", status="failed", text=None)],
        }
    )
    assert document["source"]["articles_in"] == 2
    assert document["source"]["articles_normalized"] == 1
    assert len(document["articles"]) == 1
