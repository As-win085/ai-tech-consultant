import argparse
import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree as ET

import httpx
from bs4 import BeautifulSoup

SITEMAP_URL = "https://support.brilliantdirectories.com/support/sitemap.xml"
ARTICLE_MARKER = "/support/solutions/articles/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
USER_AGENT = "AI-Tech-Consultant-KnowledgeBrain/0.1 (+support-crawler)"
DEFAULT_TIMEOUT = 30.0
DEFAULT_DELAY = 0.5
DEFAULT_OUTPUT = "data/articles.json"


@dataclass
class SitemapEntry:
    url: str
    last_modified: str | None = None
    change_frequency: str | None = None
    priority: float | None = None


def build_client(timeout: float = DEFAULT_TIMEOUT) -> httpx.Client:
    return httpx.Client(
        follow_redirects=True,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xml"},
    )


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def normalize_url(url: str) -> str:
    stripped = url.strip()
    parts = urlsplit(stripped)
    if not parts.scheme and not parts.netloc:
        return stripped
    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_sitemap(xml_text: str) -> tuple[list[SitemapEntry], list[str]]:
    entries: list[SitemapEntry] = []
    child_sitemaps: list[str] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return entries, child_sitemaps

    root_name = _localname(root.tag)
    if root_name == "sitemapindex":
        for node in root:
            if _localname(node.tag) != "sitemap":
                continue
            loc = node.find(f"{{{SITEMAP_NS}}}loc")
            if loc is not None and loc.text:
                child_sitemaps.append(loc.text.strip())
        return entries, child_sitemaps

    for node in root:
        if _localname(node.tag) != "url":
            continue
        loc = node.find(f"{{{SITEMAP_NS}}}loc")
        if loc is None or not loc.text:
            continue
        lastmod = node.find(f"{{{SITEMAP_NS}}}lastmod")
        changefreq = node.find(f"{{{SITEMAP_NS}}}changefreq")
        priority = node.find(f"{{{SITEMAP_NS}}}priority")
        try:
            priority_value = float(priority.text) if priority is not None and priority.text else None
        except ValueError:
            priority_value = None
        entries.append(
            SitemapEntry(
                url=loc.text.strip(),
                last_modified=lastmod.text.strip() if lastmod is not None and lastmod.text else None,
                change_frequency=changefreq.text.strip() if changefreq is not None and changefreq.text else None,
                priority=priority_value,
            )
        )
    return entries, child_sitemaps


def fetch_sitemap_entries(client: httpx.Client, sitemap_url: str = SITEMAP_URL) -> list[SitemapEntry]:
    response = client.get(sitemap_url)
    response.raise_for_status()
    entries, child_sitemaps = parse_sitemap(response.text)
    for child in child_sitemaps:
        try:
            child_response = client.get(child)
            child_response.raise_for_status()
            child_entries, _ = parse_sitemap(child_response.text)
            entries.extend(child_entries)
        except httpx.HTTPError:
            continue
    return entries


def is_article_url(url: str) -> bool:
    return ARTICLE_MARKER in normalize_url(url)


def extract_article_id(url: str) -> str | None:
    match = re.search(re.escape(ARTICLE_MARKER) + r"(\d+)", url)
    return match.group(1) if match else None


def collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _extract_title(soup: BeautifulSoup, article) -> str:
    if article is not None:
        heading = article.find("h1")
        if heading:
            text = collapse_whitespace(heading.get_text(" "))
            if text:
                return text
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        return collapse_whitespace(og_title["content"])
    if soup.title and soup.title.string:
        return collapse_whitespace(soup.title.string)
    return ""


def _extract_canonical(soup: BeautifulSoup, url: str) -> str:
    link = soup.find("link", attrs={"rel": "canonical"})
    if link and link.get("href"):
        return urljoin(url, link["href"].strip())
    return url


def parse_article(html: str, url: str, metadata: SitemapEntry | None = None) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article", id="article-body")
    if article is None:
        article = soup.find("article", class_="article-body")
    if article is None:
        article = soup.find("main")
    if article is None:
        article = soup.body if soup.body is not None else soup

    title = _extract_title(soup, article)
    canonical = _extract_canonical(soup, url)

    for node in article.select(
        "script, style, noscript, nav, form, .the-article-link, "
        ".article-footer-content, .article-vote, .sidebar"
    ):
        node.decompose()

    headings: list[dict] = []
    for level in range(1, 5):
        for heading in article.find_all(f"h{level}"):
            text = collapse_whitespace(heading.get_text(" "))
            if text:
                headings.append({"level": level, "text": text})

    raw_text = article.get_text("\n")
    lines = [collapse_whitespace(line) for line in raw_text.splitlines()]
    text = "\n".join(line for line in lines if line)

    is_valid = bool(text)
    article_id = extract_article_id(url)
    return {
        "id": article_id,
        "url": url,
        "canonical_url": canonical,
        "title": title,
        "text": text if is_valid else None,
        "headings": headings,
        "char_count": len(text),
        "content_hash": compute_content_hash(text) if is_valid else None,
        "last_modified": metadata.last_modified if metadata else None,
        "change_frequency": metadata.change_frequency if metadata else None,
        "priority": metadata.priority if metadata else None,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "http_status": 200,
        "status": "ok" if is_valid else "failed",
        "error": None if is_valid else "empty article content",
    }


def fetch_article(client: httpx.Client, entry: SitemapEntry) -> dict:
    try:
        response = client.get(entry.url)
        status = response.status_code
        response.raise_for_status()
        record = parse_article(response.text, entry.url, entry)
        record["http_status"] = status
        return record
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else None
        return _failed_record(entry, f"HTTP {status}: {exc}", status)
    except httpx.HTTPError as exc:
        return _failed_record(entry, f"request failed: {exc}", None)
    except Exception as exc:
        return _failed_record(entry, f"parse failed: {exc}", None)


def _failed_record(entry: SitemapEntry, error: str, status: int | None) -> dict:
    return {
        "id": extract_article_id(entry.url),
        "url": entry.url,
        "canonical_url": entry.url,
        "title": None,
        "text": None,
        "headings": [],
        "char_count": 0,
        "content_hash": None,
        "last_modified": entry.last_modified,
        "change_frequency": entry.change_frequency,
        "priority": entry.priority,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "http_status": status,
        "status": "failed",
        "error": error,
    }


def crawl(
    limit: int | None = None,
    sitemap_url: str = SITEMAP_URL,
    output_path: str | Path = DEFAULT_OUTPUT,
    delay: float = DEFAULT_DELAY,
    client: httpx.Client | None = None,
) -> dict:
    output_path = Path(output_path)
    owns_client = client is None
    if client is None:
        client = build_client()
    try:
        entries = fetch_sitemap_entries(client, sitemap_url)
        article_entries = [entry for entry in entries if is_article_url(entry.url)]

        seen: set[str] = set()
        unique_entries: list[SitemapEntry] = []
        for entry in article_entries:
            normalized = normalize_url(entry.url)
            if normalized in seen:
                continue
            seen.add(normalized)
            unique_entries.append(entry)

        selected = unique_entries[:limit] if limit else unique_entries
        records: list[dict] = []
        for index, entry in enumerate(selected):
            records.append(fetch_article(client, entry))
            if delay and index < len(selected) - 1:
                time.sleep(delay)
    finally:
        if owns_client:
            client.close()

    succeeded = sum(1 for record in records if record["status"] == "ok")
    document = {
        "source": {
            "sitemap_url": sitemap_url,
            "site": "support.brilliantdirectories.com",
            "crawled_at": datetime.now(timezone.utc).isoformat(),
            "article_urls_found": len(unique_entries),
            "articles_crawled": len(records),
            "articles_ok": succeeded,
            "articles_failed": len(records) - succeeded,
        },
        "articles": records,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description="Crawl Brilliant Directories support articles into JSON.")
    parser.add_argument("--limit", type=int, default=5, help="Number of articles to crawl (0 = all).")
    parser.add_argument("--sitemap", default=SITEMAP_URL, help="Sitemap URL to read.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output JSON path.")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="Seconds between article requests.")
    args = parser.parse_args()

    limit = None if args.limit == 0 else args.limit
    document = crawl(limit=limit, sitemap_url=args.sitemap, output_path=args.output, delay=args.delay)
    source = document["source"]
    print(f"Article URLs found: {source['article_urls_found']}")
    print(f"Articles crawled:   {source['articles_crawled']}")
    print(f"  ok:               {source['articles_ok']}")
    print(f"  failed:           {source['articles_failed']}")
    print(f"Output written to:  {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
