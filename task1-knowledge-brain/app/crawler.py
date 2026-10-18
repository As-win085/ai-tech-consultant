import argparse
import hashlib
import json
import re
import time
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
from typing import Callable
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


def _get_with_retry(client: httpx.Client, url: str, *, retries: int = 3, backoff: float = 0.25) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = client.get(url)
            if response.status_code == 429 or response.status_code >= 500:
                response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            last_error = exc
            retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code == 429 or exc.response.status_code >= 500
            if not retryable or attempt == retries:
                raise
            time.sleep(backoff * (2**attempt))
    raise httpx.RequestError("request failed after retries", request=httpx.Request("GET", url)) from last_error


def _robots_parser(client: httpx.Client, base_url: str) -> RobotFileParser:
    parts = urlsplit(base_url)
    robots_url = urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
    parser = RobotFileParser(robots_url)
    try:
        response = _get_with_retry(client, robots_url)
        if response.status_code == 404:
            parser.parse(["User-agent: *", "Allow: /"])
        else:
            response.raise_for_status()
            parser.parse(response.text.splitlines())
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            parser.parse(["User-agent: *", "Allow: /"])
        else:
            raise
    return parser


def _write_manifest(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temp_name = stream.name
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def fetch_sitemap_entries(client: httpx.Client, sitemap_url: str = SITEMAP_URL, *, max_retries: int = 3) -> list[SitemapEntry]:
    response = _get_with_retry(client, sitemap_url, retries=max_retries)
    response.raise_for_status()
    entries, child_sitemaps = parse_sitemap(response.text)
    for child in child_sitemaps:
        child_response = _get_with_retry(client, child, retries=max_retries)
        child_response.raise_for_status()
        child_entries, _ = parse_sitemap(child_response.text)
        entries.extend(child_entries)
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

    image_records = []
    for image in article.find_all("img"):
        src = image.get("src") or image.get("data-src") or image.get("data-lazy-src")
        if not src:
            continue
        neighbor = image.previous_sibling or image.next_sibling
        surrounding = collapse_whitespace(neighbor.get_text(" ", strip=True)) if getattr(neighbor, "get_text", None) else collapse_whitespace(str(neighbor or ""))
        image_records.append({"url": urljoin(url, src.strip()), "alt": collapse_whitespace(image.get("alt", "")), "context": surrounding})

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
    if image_records:
        image_lines = [
            "Image reference: " + image["url"]
            + (". Alt text: " + image["alt"] if image["alt"] else ".")
            + (" Surrounding text: " + image["context"] if image["context"] else "")
            for image in image_records
        ]
        text = "\n".join(part for part in (text, *image_lines) if part)

    is_valid = bool(text)
    article_id = extract_article_id(url)
    return {
        "id": article_id,
        "url": url,
        "canonical_url": canonical,
        "title": title,
        "text": text if is_valid else None,
        "headings": headings,
        "images": image_records,
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


def fetch_article(client: httpx.Client, entry: SitemapEntry, *, max_retries: int = 3) -> dict:
    try:
        response = _get_with_retry(client, entry.url, retries=max_retries)
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
        "images": [],
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
    manifest_path: str | Path | None = None,
    max_retries: int = 3,
    respect_robots: bool = True,
    image_describer: Callable[[str, str], str] | None = None,
) -> dict:
    output_path = Path(output_path)
    owns_client = client is None
    if client is None:
        client = build_client()
    try:
        entries = fetch_sitemap_entries(client, sitemap_url, max_retries=max_retries)
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
        robots = _robots_parser(client, sitemap_url) if respect_robots else None
        manifest_file = Path(manifest_path) if manifest_path else None
        if manifest_file:
            manifest_file.parent.mkdir(parents=True, exist_ok=True)
        prior: dict[str, dict] = {}
        if manifest_file and manifest_file.exists():
            try:
                manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                prior = {normalize_url(item["url"]): item for item in manifest_data.get("articles", []) if item.get("url") and item.get("status") == "ok" and item.get("last_modified")}
            except (OSError, ValueError, TypeError):
                prior = {}
        records: list[dict] = []
        vision_described = 0
        vision_failed = 0
        for index, entry in enumerate(selected):
            normalized = normalize_url(entry.url)
            cached = prior.get(normalized)
            if cached and cached.get("last_modified") == entry.last_modified:
                record = cached
            elif robots and not robots.can_fetch(USER_AGENT, entry.url):
                record = _failed_record(entry, "disallowed by robots.txt", 403)
                record["status"] = "skipped"
                record["error"] = "disallowed by robots.txt"
            else:
                record = fetch_article(client, entry, max_retries=max_retries)
            if record["status"] == "ok" and image_describer and vision_described == 0:
                for image in record.get("images", []):
                    image_host = urlsplit(image["url"]).hostname
                    article_host = urlsplit(entry.url).hostname
                    if urlsplit(image["url"]).scheme != "https" or image_host != article_host:
                        continue
                    try:
                        description = collapse_whitespace(image_describer(image["url"], image.get("context", "")))[:1000]
                        if description:
                            image["description"] = description
                            record["text"] = (record.get("text") or "") + f"\nImage description: {description}"
                            record["content_hash"] = compute_content_hash(record["text"])
                            record["char_count"] = len(record["text"])
                            vision_described += 1
                    except Exception:
                        vision_failed += 1
                    break
            records.append(record)
            if manifest_file:
                _write_manifest(manifest_file, {"sitemap_url": sitemap_url, "articles": records})
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
            "articles_skipped": sum(1 for record in records if record["status"] == "skipped"),
            "article_ids_in_sitemap": sorted({extract_article_id(entry.url) for entry in unique_entries if extract_article_id(entry.url)}),
            "vision_described": vision_described,
            "vision_failed": vision_failed,
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
    parser.add_argument("--manifest", default="data/ingestion-manifest.json", help="Manifest used to resume and cache unchanged pages.")
    args = parser.parse_args()

    limit = None if args.limit == 0 else args.limit
    document = crawl(limit=limit, sitemap_url=args.sitemap, output_path=args.output, delay=args.delay, manifest_path=args.manifest)
    source = document["source"]
    print(f"Article URLs found: {source['article_urls_found']}")
    print(f"Articles crawled:   {source['articles_crawled']}")
    print(f"  ok:               {source['articles_ok']}")
    print(f"  failed:           {source['articles_failed']}")
    print(f"Output written to:  {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
