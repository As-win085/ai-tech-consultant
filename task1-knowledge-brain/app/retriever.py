"""Semantic retrieval over the pgvector index.

Retrieval embeds the question with the *same* embedding model used at index
time, then asks the store for the nearest chunks by cosine similarity. Cosine
similarity is chosen because the supported embedding models (OpenAI and
``nomic-embed-text`` via Ollama) are trained for angular similarity and cosine is
scale-invariant; pgvector's ``<=>`` operator computes cosine distance, which the
store converts to a similarity score.

The retriever is deliberately strict:

- it refuses to answer from an index built with a different model or dimension
  (mixing embeddings would silently produce meaningless neighbors);
- it never treats failed or inactive articles as evidence;
- it drops weakly-related chunks below ``min_score`` and de-duplicates
  near-identical chunks so one article cannot dominate the evidence set.

It depends only on a ``RetrievalStore`` and an ``EmbeddingProvider``, so it is
testable with the in-memory store and a fake provider.
"""

from dataclasses import dataclass

from app.embeddings import EmbeddingProvider
from app.models import SearchHit
from app.store import RetrievalStore


class RetrievalError(RuntimeError):
    """Base class for retrieval failures."""


class IndexModelMismatch(RetrievalError):
    """The query embedding configuration does not match the stored index."""


@dataclass
class RetrievalConfig:
    top_k: int = 5
    min_score: float = 0.35
    max_per_article: int = 2
    oversample: int = 4

    def __post_init__(self) -> None:
        if self.top_k < 1:
            raise ValueError("top_k must be >= 1")
        if self.max_per_article < 1:
            raise ValueError("max_per_article must be >= 1")
        if self.oversample < 1:
            raise ValueError("oversample must be >= 1")
        if not -1.0 <= self.min_score <= 1.0:
            raise ValueError("min_score must be between -1 and 1")


@dataclass
class RetrievalResult:
    query: str
    model: str
    dimensions: int
    hits: list[SearchHit]
    indexed_chunks: int
    notes: list[str]


def _tokens(text: str) -> set[str]:
    return {token for token in text.lower().split() if token}


def _is_near_duplicate(left: str, right: str, threshold: float = 0.85) -> bool:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return left.strip() == right.strip()
    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return union > 0 and (overlap / union) >= threshold


class Retriever:
    def __init__(
        self,
        store: RetrievalStore,
        embedding_provider: EmbeddingProvider,
        config: RetrievalConfig | None = None,
    ) -> None:
        self.store = store
        self.provider = embedding_provider
        self.config = config or RetrievalConfig()

    def retrieve(
        self,
        question: str,
        *,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> RetrievalResult:
        query = (question or "").strip()
        if not query:
            raise ValueError("question must not be empty")
        top_k = top_k if top_k is not None else self.config.top_k
        min_score = min_score if min_score is not None else self.config.min_score
        if top_k < 1:
            raise ValueError("top_k must be >= 1")

        model = self.provider.model_name
        dimensions = self.provider.dimensions
        index = self.store.index_metadata()

        if index.indexed_chunks == 0:
            return RetrievalResult(
                query=query,
                model=model,
                dimensions=dimensions,
                hits=[],
                indexed_chunks=0,
                notes=["the knowledge index is empty"],
            )

        if not index.has(model, dimensions):
            available = ", ".join(
                f"{name} ({dim}d)" for name, dim in sorted(index.model_dimensions)
            ) or "none"
            raise IndexModelMismatch(
                f"the index was built with a different embedding configuration "
                f"(query model={model!r}, dimensions={dimensions}); available: {available}"
            )

        vectors = self.provider.embed([query])
        if len(vectors) != 1 or len(vectors[0]) != dimensions:
            raise IndexModelMismatch(
                "the embedding provider returned a vector that does not match its "
                "declared dimensions"
            )
        query_vector = vectors[0]

        fetch_limit = max(top_k * self.config.oversample, top_k)
        candidates = self.store.search_similar(query_vector, model, dimensions, fetch_limit)

        above_threshold = [hit for hit in candidates if hit.score >= min_score]
        selected, dropped_duplicates = self._select(above_threshold, top_k)

        notes: list[str] = []
        if len(above_threshold) < len(candidates):
            notes.append(
                f"{len(candidates) - len(above_threshold)} chunk(s) below min_score "
                f"{min_score:.3f} were ignored"
            )
        if dropped_duplicates:
            notes.append(
                f"{dropped_duplicates} near-duplicate chunk(s) were dropped"
            )
        if not selected:
            notes.append("no chunk cleared the relevance threshold")

        return RetrievalResult(
            query=query,
            model=model,
            dimensions=dimensions,
            hits=selected,
            indexed_chunks=index.indexed_chunks,
            notes=notes,
        )

    def _select(
        self, hits: list[SearchHit], top_k: int
    ) -> tuple[list[SearchHit], int]:
        selected: list[SearchHit] = []
        per_article: dict[str, int] = {}
        dropped = 0
        for hit in hits:
            if per_article.get(hit.article_id, 0) >= self.config.max_per_article:
                dropped += 1
                continue
            if any(
                other.article_id == hit.article_id
                and _is_near_duplicate(other.content, hit.content)
                for other in selected
            ):
                dropped += 1
                continue
            if any(
                other.article_id != hit.article_id and other.content == hit.content
                for other in selected
            ):
                dropped += 1
                continue
            selected.append(hit)
            per_article[hit.article_id] = per_article.get(hit.article_id, 0) + 1
            if len(selected) >= top_k:
                break
        return selected, dropped
