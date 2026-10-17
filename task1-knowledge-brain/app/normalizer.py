"""Deterministic article normalization for the Knowledge Brain.

The crawler stores article text as one whitespace-collapsed line per inline
HTML text node. That makes plain paragraphs easy to read but splits any
paragraph that contained inline markup (links, bold, code) into fragments and
loses the paragraph/heading structure.

This module rebuilds a stable, testable representation:

- ``build_blocks`` reconstructs heading and paragraph blocks from the flat
  line list, joining fragments with a smart spacing rule and closing a
  paragraph on sentence-ending punctuation.
- ``build_sections`` groups paragraphs under their heading hierarchy and
  produces a ``breadcrumb`` for each section.
- ``normalize_article`` / ``normalize_articles`` turn crawler records into
  normalized articles and drop failed/empty records so they are never indexed.

Normalization is pure and deterministic: the same input always yields the same
output (no timestamps are added here).
"""

from app.crawler import (
    collapse_whitespace,
    compute_content_hash,
    extract_article_id,
    normalize_url,
)

SENTENCE_ENDINGS = (".", "!", "?")
NO_SPACE_BEFORE = ".,;:!?)]}\u00bb%"
MAX_HEADING_LINES = 4


def _match_heading(lines: list[str], start: int, heading_text: str) -> int:
    """Return how many consecutive lines form ``heading_text`` (0 if none).

    A heading is normally a single line, but inline markup can split it across
    a few lines, so we try progressively larger joins and stop once we pass the
    expected length.
    """
    joined = ""
    for offset in range(MAX_HEADING_LINES):
        index = start + offset
        if index >= len(lines):
            break
        joined = lines[index] if not joined else f"{joined} {lines[index]}"
        if joined == heading_text:
            return offset + 1
        if len(joined) >= len(heading_text):
            break
    return 0


def _smart_join(buffer: str, fragment: str) -> str:
    """Append ``fragment`` to ``buffer``, attaching leading punctuation."""
    if not buffer:
        return fragment
    if fragment[:1] in NO_SPACE_BEFORE:
        return buffer + fragment
    return f"{buffer} {fragment}"


def build_blocks(text: str, headings: list[dict]) -> list[dict]:
    """Reconstruct ordered heading/paragraph blocks from flat article text."""
    lines = [collapse_whitespace(line) for line in (text or "").splitlines()]
    lines = [line for line in lines if line]
    heading_list = [
        (collapse_whitespace(heading.get("text", "")), int(heading.get("level", 1)))
        for heading in (headings or [])
        if collapse_whitespace(heading.get("text", ""))
    ]

    blocks: list[dict] = []
    paragraph = ""
    line_index = 0
    heading_index = 0

    while line_index < len(lines):
        if heading_index < len(heading_list):
            heading_text, level = heading_list[heading_index]
            matched = _match_heading(lines, line_index, heading_text)
            if matched:
                if paragraph:
                    blocks.append({"type": "paragraph", "text": paragraph})
                    paragraph = ""
                blocks.append({"type": "heading", "level": level, "text": heading_text})
                line_index += matched
                heading_index += 1
                continue

        paragraph = _smart_join(paragraph, lines[line_index])
        if paragraph.endswith(SENTENCE_ENDINGS):
            blocks.append({"type": "paragraph", "text": paragraph})
            paragraph = ""
        line_index += 1

    if paragraph:
        blocks.append({"type": "paragraph", "text": paragraph})
    return blocks


def build_sections(blocks: list[dict], title: str) -> list[dict]:
    """Group blocks into sections using a heading-level stack for breadcrumbs."""
    sections: list[dict] = []
    stack: list[tuple[int, str]] = []
    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if current is not None:
            sections.append(
                {
                    "level": current["level"],
                    "heading": current["heading"],
                    "breadcrumb": current["breadcrumb"],
                    "text": "\n\n".join(current["paragraphs"]),
                }
            )
            current = None

    for block in blocks:
        if block["type"] == "heading":
            flush()
            level = block["level"]
            heading = block["text"]
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading))
            current = {
                "level": level,
                "heading": heading,
                "breadcrumb": " > ".join(text for _, text in stack),
                "paragraphs": [],
            }
        else:
            if current is None:
                current = {
                    "level": 0,
                    "heading": None,
                    "breadcrumb": collapse_whitespace(title or ""),
                    "paragraphs": [],
                }
            current["paragraphs"].append(block["text"])

    flush()
    return sections


def resolve_article_id(record: dict) -> str:
    raw_id = record.get("id")
    if raw_id not in (None, ""):
        return str(raw_id)
    for key in ("canonical_url", "url"):
        candidate = record.get(key)
        if candidate:
            derived = extract_article_id(candidate)
            if derived:
                return derived
    basis = record.get("canonical_url") or record.get("url")
    if basis:
        return "url-" + compute_content_hash(normalize_url(basis))[:16]
    return "content-" + compute_content_hash(record.get("text") or "")[:16]


def normalize_article(record: dict) -> dict | None:
    """Normalize one crawler record, or return ``None`` if it is not valid."""
    if not isinstance(record, dict) or record.get("status") != "ok":
        return None
    text = record.get("text")
    if not text or not text.strip():
        return None

    title = collapse_whitespace(record.get("title") or "")
    blocks = build_blocks(text, record.get("headings") or [])
    sections = build_sections(blocks, title)
    normalized_text = "\n\n".join(block["text"] for block in blocks)

    return {
        "article_id": resolve_article_id(record),
        "title": title,
        "canonical_url": record.get("canonical_url") or record.get("url") or "",
        "source_url": record.get("url"),
        "metadata": {
            "last_modified": record.get("last_modified"),
            "change_frequency": record.get("change_frequency"),
            "priority": record.get("priority"),
            "fetched_at": record.get("fetched_at"),
            "http_status": record.get("http_status"),
        },
        "source_content_hash": record.get("content_hash"),
        "normalized_content_hash": compute_content_hash(normalized_text),
        "char_count": len(normalized_text),
        "sections": sections,
        "text": normalized_text,
    }


def normalize_articles(records: list[dict]) -> list[dict]:
    """Normalize records in order, skipping invalid ones and duplicate IDs."""
    normalized: list[dict] = []
    seen: set[str] = set()
    for record in records or []:
        article = normalize_article(record)
        if article is None or article["article_id"] in seen:
            continue
        seen.add(article["article_id"])
        normalized.append(article)
    return normalized


def build_normalized_document(crawl_document: dict) -> dict:
    """Wrap normalized articles with a small source summary."""
    crawl_document = crawl_document or {}
    raw_articles = crawl_document.get("articles", [])
    articles = normalize_articles(raw_articles)
    source = crawl_document.get("source", {})
    return {
        "source": {
            "sitemap_url": source.get("sitemap_url"),
            "site": source.get("site"),
            "crawled_at": source.get("crawled_at"),
            "articles_in": len(raw_articles),
            "articles_normalized": len(articles),
        },
        "articles": articles,
    }
