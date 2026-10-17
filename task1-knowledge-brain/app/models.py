"""Data records and validation for the Knowledge Brain persistence layer.

These dataclasses are the contract between the indexer and any knowledge store
(in-memory for tests, PostgreSQL/pgvector for real persistence). Validation
happens at construction time so bad metadata fails loudly and early rather than
being silently written.
"""

from dataclasses import dataclass, field
import math

ARTICLE_STATUSES = frozenset({"ok", "failed", "skipped"})
RUN_STATUSES = {"ok", "partial", "failed"}


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [-1, 1]; 0.0 for missing/zero/mismatched vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


@dataclass
class ArticleRecord:
    """A support article as persisted for grounding and citations."""

    article_id: str
    title: str = ""
    canonical_url: str | None = None
    source_url: str | None = None
    last_modified: str | None = None
    change_frequency: str | None = None
    priority: float | None = None
    fetched_at: str | None = None
    http_status: int | None = None
    source_content_hash: str | None = None
    normalized_content_hash: str | None = None
    char_count: int = 0
    status: str = "ok"
    error: str | None = None
    is_active: bool = True

    def __post_init__(self) -> None:
        if not self.article_id:
            raise ValueError("article_id is required")
        if self.status not in {"ok", "failed", "skipped"}:
            raise ValueError(f"invalid article status: {self.status!r}")
        if self.char_count < 0:
            raise ValueError("char_count must be >= 0")


@dataclass
class ChunkRecord:
    chunk_id: str
    article_id: str
    chunk_index: int
    content: str
    heading_context: str = ""
    char_count: int = 0
    content_hash: str = ""
    article_content_hash: str | None = None

    def __post_init__(self) -> None:
        if not self.chunk_id:
            raise ValueError("chunk_id is required")
        if not self.article_id:
            raise ValueError("chunk article_id is required")
        if self.chunk_index < 0:
            raise ValueError("chunk_index must be >= 0")
        if not self.content or not self.content.strip():
            raise ValueError("chunk content must not be empty")
        if self.char_count < 0:
            raise ValueError("chunk char_count must be >= 0")


@dataclass
class EmbeddingRecord:
    chunk_id: str
    embedding: list[float]
    model: str
    dimensions: int

    def __post_init__(self) -> None:
        if not self.chunk_id:
            raise ValueError("embedding chunk_id is required")
        if not self.model:
            raise ValueError("embedding model is required")
        if self.dimensions < 1:
            raise ValueError("embedding dimensions must be >= 1")
        if len(self.embedding) != self.dimensions:
            raise ValueError(
                f"embedding length {len(self.embedding)} != dimensions {self.dimensions}"
            )


@dataclass
class IndexReport:
    """Outcome of one indexing run, including per-chunk failure counts."""

    model: str
    dimensions: int
    status: str = "failed"
    run_id: int | None = None
    articles_processed: int = 0
    articles_failed: int = 0
    chunks_written: int = 0
    chunks_pruned: int = 0
    chunks_embedded: int = 0
    chunks_skipped: int = 0
    chunks_failed: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "status": self.status,
            "run_id": self.run_id,
            "model": self.model,
            "dimensions": self.dimensions,
            "articles_processed": self.articles_processed,
            "articles_failed": self.articles_failed,
            "chunks_written": self.chunks_written,
            "chunks_pruned": self.chunks_pruned,
            "chunks_embedded": self.chunks_embedded,
            "chunks_skipped": self.chunks_skipped,
            "chunks_failed": self.chunks_failed,
            "errors": self.errors,
        }


@dataclass
class SearchHit:
    """One chunk returned by similarity search, joined with its article."""

    chunk_id: str
    article_id: str
    title: str
    canonical_url: str | None
    source_url: str | None
    heading_context: str
    content: str
    chunk_index: int
    score: float


@dataclass
class IndexMetadata:
    """What is currently searchable in the vector index."""

    indexed_chunks: int
    model_dimensions: dict[tuple[str, int], int] = field(default_factory=dict)

    def has(self, model: str, dimensions: int) -> bool:
        return self.model_dimensions.get((model, dimensions), 0) > 0

    def summary(self) -> dict:
        return {
            "indexed_chunks": self.indexed_chunks,
            "model_dimensions": [
                {"model": model, "dimensions": dim, "chunks": count}
                for (model, dim), count in sorted(self.model_dimensions.items())
            ],
        }
