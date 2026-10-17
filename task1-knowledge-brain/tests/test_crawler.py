import hashlib

import httpx
import pytest

from app.crawler import (
    ARTICLE_MARKER,
    SitemapEntry,
    compute_content_hash,
    crawl,
    extract_article_id,
    fetch_article,
    fetch_sitemap_entries,
    is_article_url,
    normalize_url,
    parse_article,
    parse_sitemap,
)

BASE = "https://support.brilliantdirectories.com"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def urlset(entries) -> str:
    items = ""
    for loc, lastmod, changefreq, priority in entries:
        items += "<url>"
        items += f"<loc>{loc}</loc>"
        if lastmod:
            items += f"<lastmod>{lastmod}</lastmod>"
        if changefreq:
            items += f"<changefreq>{changefreq}</changefreq>"
        if priority is not None:
            items += f"<priority>{priority}</priority>"
        items += "</url>"
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="{SITEMAP_NS}">{items}</urlset>'


def sitemapindex(locs) -> str:
    items = "".join(f"<sitemap><loc>{loc}</loc></sitemap>" for loc in locs)
    return f'<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="{SITEMAP_NS}">{items}</sitemapindex>'


def article_html(title="Sample Title", body="<p>Hello body text.</p>", canonical=None) -> str:
    can = f'<link rel="canonical" href="{canonical}"/>' if canonical else ""
    return (
        f"<html><head><title>{title}</title>{can}</head><body>"
        '<nav class="site-nav">Navigation junk</nav>'
        '<section class="main content">'
        '<article class="article-body" id="article-body">'
        f'<h1 class="post-title">{title}</h1>'
        '<p class="the-article-link">Link: <a href="#">internal</a></p>'
        "<h2>First Heading</h2>"
        f"{body}"
        "<h3>Sub Heading</h3><p>More detail.</p>"
        '<div class="article-footer-content">Related junk</div>'
        "<script>var junk = 1;</script>"
        "</article></section>"
        "<footer>Footer junk</footer>"
        "</body></html>"
    )


@pytest.mark.parametrize(
    "url,expected",
    [
        (f"{BASE}{ARTICLE_MARKER}5000558363-emails", True),
        (f"{BASE}{ARTICLE_MARKER}5000558363-emails/", True),
        (f"{BASE}/support/solutions/folders/12000000697", False),
        (f"{BASE}/support/solutions", False),
        (f"{BASE}/support/home", False),
        (f"{BASE}/support/sitemap.xml", False),
    ],
)
def test_is_article_url(url, expected):
    assert is_article_url(url) is expected


def test_extract_article_id():
    assert extract_article_id(f"{BASE}{ARTICLE_MARKER}5000558363-emails") == "5000558363"
    assert extract_article_id(f"{BASE}/support/solutions/folders/123") is None


def test_parse_sitemap_urlset_extracts_entries_and_metadata():
    xml = urlset([(f"{BASE}{ARTICLE_MARKER}123-alpha", "2024-01-01T00:00:00+00:00", "always", 0.512)])
    entries, children = parse_sitemap(xml)
    assert children == []
    assert len(entries) == 1
    entry = entries[0]
    assert entry.url == f"{BASE}{ARTICLE_MARKER}123-alpha"
    assert entry.last_modified == "2024-01-01T00:00:00+00:00"
    assert entry.change_frequency == "always"
    assert entry.priority == 0.512


def test_parse_sitemap_index_returns_child_sitemaps():
    xml = sitemapindex([f"{BASE}/sitemap1.xml", f"{BASE}/sitemap2.xml"])
    entries, children = parse_sitemap(xml)
    assert entries == []
    assert children == [f"{BASE}/sitemap1.xml", f"{BASE}/sitemap2.xml"]


def test_parse_sitemap_malformed_returns_empty_without_crashing():
    entries, children = parse_sitemap("<urlset><url><loc>oops")
    assert entries == []
    assert children == []


def test_fetch_sitemap_entries_follows_index_and_skips_failed_child():
    root = sitemapindex([f"{BASE}/good.xml", f"{BASE}/bad.xml"])
    good = urlset([(f"{BASE}{ARTICLE_MARKER}1-a", None, None, None)])

    def handler(request):
        url = str(request.url)
        if url == f"{BASE}/sitemap.xml":
            return httpx.Response(200, text=root)
        if url == f"{BASE}/good.xml":
            return httpx.Response(200, text=good)
        raise httpx.ConnectError("boom", request=request)

    with make_client(handler) as client:
        entries = fetch_sitemap_entries(client, f"{BASE}/sitemap.xml")
    assert [entry.url for entry in entries] == [f"{BASE}{ARTICLE_MARKER}1-a"]


def test_parse_article_extracts_all_required_fields():
    url = f"{BASE}{ARTICLE_MARKER}1-sample-article"
    metadata = SitemapEntry(url=url, last_modified="2024-05-01", change_frequency="always", priority=0.5)
    html = article_html(
        title="Emails and Accounts",
        body="<p>Body paragraph text.</p>",
        canonical=f"{BASE}{ARTICLE_MARKER}1",
    )
    record = parse_article(html, url, metadata)

    assert record["title"] == "Emails and Accounts"
    assert "Body paragraph text." in record["text"]
    assert record["canonical_url"] == f"{BASE}{ARTICLE_MARKER}1"
    assert record["last_modified"] == "2024-05-01"
    assert record["change_frequency"] == "always"
    assert record["priority"] == 0.5
    assert record["status"] == "ok"
    assert record["char_count"] == len(record["text"])
    assert record["content_hash"] == compute_content_hash(record["text"])
    assert record["fetched_at"]

    levels = {(heading["level"], heading["text"]) for heading in record["headings"]}
    assert (2, "First Heading") in levels
    assert (3, "Sub Heading") in levels


def test_parse_article_strips_page_chrome():
    record = parse_article(article_html(body="<p>Body only.</p>"), f"{BASE}{ARTICLE_MARKER}2-y")
    assert "Body only." in record["text"]
    assert "Navigation junk" not in record["text"]
    assert "Footer junk" not in record["text"]
    assert "Related junk" not in record["text"]
    assert "internal" not in record["text"]
    assert "var junk" not in record["text"]


def test_parse_article_empty_html_is_marked_failed():
    record = parse_article("<html><body></body></html>", f"{BASE}{ARTICLE_MARKER}3-z")
    assert record["status"] == "failed"
    assert record["text"] is None
    assert record["content_hash"] is None
    assert record["char_count"] == 0
    assert record["error"] == "empty article content"


def test_parse_article_malformed_html_does_not_crash():
    record = parse_article(
        "<html><body><main><h1>Broken</h1><p>Partial fragment",
        f"{BASE}{ARTICLE_MARKER}4-w",
    )
    assert record["title"] == "Broken"
    assert "Partial fragment" in record["text"]
    assert record["status"] == "ok"


def test_canonical_falls_back_to_page_url():
    url = f"{BASE}{ARTICLE_MARKER}5-v"
    record = parse_article(article_html(), url)
    assert record["canonical_url"] == url


def test_relative_canonical_is_resolved():
    html = article_html(canonical=f"{ARTICLE_MARKER}5")
    record = parse_article(html, f"{BASE}{ARTICLE_MARKER}5-v")
    assert record["canonical_url"] == f"{BASE}{ARTICLE_MARKER}5"


def test_normalize_url_removes_fragment_and_trailing_slash():
    assert normalize_url(f"{BASE}{ARTICLE_MARKER}1-a/") == f"{BASE}{ARTICLE_MARKER}1-a"
    assert normalize_url(f"{BASE}{ARTICLE_MARKER}1-a#section") == f"{BASE}{ARTICLE_MARKER}1-a"
    assert normalize_url(f"HTTPS://{BASE.split('//')[1].upper()}/1") == f"{BASE}/1"


def test_normalize_url_does_not_merge_distinct_articles():
    first = normalize_url(f"{BASE}{ARTICLE_MARKER}1-a")
    second = normalize_url(f"{BASE}{ARTICLE_MARKER}2-b")
    assert first != second


def test_content_hash_is_stable():
    assert compute_content_hash("abc") == hashlib.sha256(b"abc").hexdigest()


def test_fetch_article_http_404_is_marked_failed():
    def handler(request):
        return httpx.Response(404, text="not found")

    entry = SitemapEntry(url=f"{BASE}{ARTICLE_MARKER}99-missing")
    with make_client(handler) as client:
        record = fetch_article(client, entry)
    assert record["status"] == "failed"
    assert record["http_status"] == 404
    assert "404" in record["error"]
    assert record["text"] is None


def test_fetch_article_network_failure_is_marked_failed():
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    entry = SitemapEntry(url=f"{BASE}{ARTICLE_MARKER}98-down")
    with make_client(handler) as client:
        record = fetch_article(client, entry)
    assert record["status"] == "failed"
    assert record["http_status"] is None
    assert "request failed" in record["error"]


def test_fetch_article_timeout_is_marked_failed():
    def handler(request):
        raise httpx.ReadTimeout("timed out", request=request)

    entry = SitemapEntry(url=f"{BASE}{ARTICLE_MARKER}97-slow")
    with make_client(handler) as client:
        record = fetch_article(client, entry)
    assert record["status"] == "failed"
    assert "request failed" in record["error"]


def _mixed_sitemap_handler(sitemap: str):
    def handler(request):
        url = str(request.url)
        if url == f"{BASE}/sitemap.xml":
            return httpx.Response(200, text=sitemap)
        if url.endswith("/1-a"):
            return httpx.Response(200, text=article_html(title="Alpha", body="<p>Alpha body.</p>"))
        if url.endswith("/2-b"):
            return httpx.Response(404, text="not found")
        if url.endswith("/3-c"):
            return httpx.Response(200, text="<html><body></body></html>")
        if url.endswith("/4-d"):
            return httpx.Response(200, text=article_html(title="Delta", body="<p>Delta body.</p>"))
        return httpx.Response(404, text="not found")

    return handler


def test_crawl_dedupes_articles_and_isolates_failures(tmp_path):
    sitemap = urlset(
        [
            (f"{BASE}{ARTICLE_MARKER}1-a", None, None, None),
            (f"{BASE}{ARTICLE_MARKER}1-a/", None, None, None),
            (f"{BASE}{ARTICLE_MARKER}2-b", None, None, None),
            (f"{BASE}{ARTICLE_MARKER}3-c", None, None, None),
            (f"{BASE}{ARTICLE_MARKER}4-d", None, None, None),
            (f"{BASE}/support/solutions/folders/120", None, None, None),
        ]
    )
    output = tmp_path / "articles.json"
    with make_client(_mixed_sitemap_handler(sitemap)) as client:
        document = crawl(sitemap_url=f"{BASE}/sitemap.xml", output_path=output, delay=0, client=client)

    source = document["source"]
    assert source["article_urls_found"] == 4
    assert source["articles_crawled"] == 4
    assert source["articles_ok"] == 2
    assert source["articles_failed"] == 2

    statuses = {article["id"]: article["status"] for article in document["articles"]}
    assert statuses == {"1": "ok", "2": "failed", "3": "failed", "4": "ok"}
    assert output.exists()


def test_failed_and_empty_records_are_not_valid_knowledge(tmp_path):
    sitemap = urlset(
        [
            (f"{BASE}{ARTICLE_MARKER}1-a", None, None, None),
            (f"{BASE}{ARTICLE_MARKER}2-b", None, None, None),
            (f"{BASE}{ARTICLE_MARKER}3-c", None, None, None),
        ]
    )
    output = tmp_path / "articles.json"
    with make_client(_mixed_sitemap_handler(sitemap)) as client:
        document = crawl(sitemap_url=f"{BASE}/sitemap.xml", output_path=output, delay=0, client=client)

    for article in document["articles"]:
        if article["status"] != "ok":
            assert not article["text"]
            assert article["content_hash"] is None


def test_crawl_respects_limit(tmp_path):
    entries = [(f"{BASE}{ARTICLE_MARKER}{index}-x{index}", None, None, None) for index in range(1, 6)]
    sitemap = urlset(entries)

    def handler(request):
        url = str(request.url)
        if url == f"{BASE}/sitemap.xml":
            return httpx.Response(200, text=sitemap)
        return httpx.Response(200, text=article_html(title="T", body="<p>body</p>"))

    output = tmp_path / "articles.json"
    with make_client(handler) as client:
        document = crawl(limit=2, sitemap_url=f"{BASE}/sitemap.xml", output_path=output, delay=0, client=client)
    assert document["source"]["article_urls_found"] == 5
    assert document["source"]["articles_crawled"] == 2
