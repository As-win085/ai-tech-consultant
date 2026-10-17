"""Deterministic article chunking for the Knowledge Brain.

Chunks are the unit of retrieval (Milestone 5). This module splits each
normalized article section into retrieval-sized pieces while:

- keeping every chunk linked to its article, canonical URL, and heading context,
- using a configurable size and overlap (character based; no tokenizer),
- snapping boundaries to sentence then word boundaries so chunks read cleanly,
- producing stable ``chunk_id`` values so an unchanged article reprocessed
  yields identical chunk identifiers (KB-FR-03).

No embeddings, database, or model calls happen here.
"""

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.crawler import compute_content_hash
from app.normalizer import normalize_articles

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_OVERLAP = 200
DEFAULT_INPUT = "data/articles-sample.json"
DEFAULT_OUTPUT = "data/chunks-sample.json"
SENTENCE_SUFFIXES = (". ", "! ", "? ")


@dataclass(frozen=True)
class ChunkConfig:
    """Chunk size/overlap settings (character based by default)."""

    chunk_size: int = DEFAULT_CHUNK_SIZE
    overlap: int = DEFAULT_OVERLAP
    unit: str = "characters"

    def __post_init__(self) -> None:
        if self.chunk_size < 1:
            raise ValueError("chunk_size must be >= 1")
        if self.overlap < 0:
            raise ValueError("overlap must be >= 0")
        if self.overlap >= self.chunk_size:
            raise ValueError("overlap must be < chunk_size")


def _snap_end(body: str, start: int, end: int, min_ratio: float = 0.5) -> int:
    """Pull ``end`` back to the nearest sentence, newline, or word boundary."""
    floor = start + int((end - start) * min_ratio)
    segment = body[floor:end]
    for suffix in SENTENCE_SUFFIXES:
        index = segment.rfind(suffix)
        if index != -1:
            return floor + index + len(suffix)
    newline = segment.rfind("\n")
    if newline != -1:
        return floor + newline + 1
    space = segment.rfind(" ")
    if space != -1:
        return floor + space + 1
    return end


def _overlap_tail(content: str, config: ChunkConfig) -> str:
    """Return the shared prefix for the next chunk (boundary-snapped)."""
    overlap = config.overlap
    if overlap <= 0:
        return ""
    tail = content if len(content) <= overlap else content[-overlap:]
    for suffix in SENTENCE_SUFFIXES + ("\n",):
        index = tail.find(suffix)
        if index != -1:
            return tail[index + len(suffix):]
    space = tail.find(" ")
    if space != -1:
        return tail[space + 1:]
    return tail


def pack_chunks(body: str, config: ChunkConfig) -> list[str]:
    """Split ``body`` into <= ``chunk_size`` pieces with ``overlap`` sharing."""
    body = (body or "").strip()
    if not body:
        return []
    if len(body) <= config.chunk_size:
        return [body]

    chunks: list[str] = []
    position = 0
    prefix = ""
    total = len(body)

    while position < total:
        budget = config.chunk_size - len(prefix)
        if budget < 1:
            prefix = ""
            budget = config.chunk_size
        end = position + budget
        if end < total:
            end = _snap_end(body, position, end)
        content = f"{prefix}{body[position:end]}".strip()
        if content:
            chunks.append(content)
        if end >= total:
            break
        prefix = _overlap_tail(content, config)
        position = end

    return chunks


def chunk_article(article: dict, config: ChunkConfig) -> list[dict]:
    """Chunk every non-empty section of a normalized article."""
    chunks: list[dict] = []
    index = 0
    for section in article.get("sections", []):
        body = (section.get("text") or "").strip()
        if not body:
            continue
        heading_context = section.get("breadcrumb") or article.get("title") or ""
        for piece in pack_chunks(body, config):
            content_hash = compute_content_hash(f"{heading_context}\n\n{piece}")
            chunk_id = hashlib.sha256(
                f"{article['article_id']}|{index}|{content_hash}".encode("utf-8")
            ).hexdigest()[:32]
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "article_id": article["article_id"],
                    "title": article.get("title", ""),
                    "canonical_url": article.get("canonical_url", ""),
                    "source_url": article.get("source_url"),
                    "chunk_index": index,
                    "heading_context": heading_context,
                    "content": piece,
                    "char_count": len(piece),
                    "content_hash": content_hash,
                    "article_content_hash": article.get("normalized_content_hash"),
                }
            )
            index += 1
    return chunks


def build_chunks_document(crawl_document: dict, config: ChunkConfig | None = None) -> dict:
    """Normalize a crawl document and produce all chunks plus a summary."""
    config = config or ChunkConfig()
    articles = normalize_articles((crawl_document or {}).get("articles", []))

    all_chunks: list[dict] = []
    article_summaries: list[dict] = []
    for article in articles:
        article_chunks = chunk_article(article, config)
        all_chunks.extend(article_chunks)
        article_summaries.append(
            {
                "article_id": article["article_id"],
                "title": article.get("title"),
                "canonical_url": article.get("canonical_url"),
                "chunks": len(article_chunks),
            }
        )

    source = (crawl_document or {}).get("source", {})
    return {
        "config": {
            "chunk_size": config.chunk_size,
            "overlap": config.overlap,
            "unit": config.unit,
        },
        "source": {
            "sitemap_url": source.get("sitemap_url"),
            "site": source.get("site"),
            "crawled_at": source.get("crawled_at"),
            "articles_normalized": len(articles),
            "chunks_total": len(all_chunks),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "articles": article_summaries,
        "chunks": all_chunks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize crawled articles and split them into retrieval chunks."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Crawled articles JSON path.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Chunks JSON output path.")
    parser.add_argument(
        "--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE, help="Max characters per chunk."
    )
    parser.add_argument(
        "--overlap", type=int, default=DEFAULT_OVERLAP, help="Shared characters between chunks."
    )
    args = parser.parse_args(argv)

    config = ChunkConfig(chunk_size=args.chunk_size, overlap=args.overlap)
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return 1

    crawl_document = json.loads(input_path.read_text(encoding="utf-8"))
    document = build_chunks_document(crawl_document, config)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    summary = document["source"]
    print(f"Articles normalized: {summary['articles_normalized']}")
    print(f"Chunks produced:     {summary['chunks_total']}")
    print(f"Chunk size/overlap:  {config.chunk_size}/{config.overlap} {config.unit}")
    print(f"Output written to:   {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
