import pytest

from app.models import ArticleRecord, ChunkRecord, EmbeddingRecord
from app.retriever import IndexModelMismatch, RetrievalConfig, Retriever
from app.store import InMemoryKnowledgeStore

DIM = 3


def seed(store, article_id, chunks, status="ok", is_active=True, title=None):
    store.upsert_article(
        ArticleRecord(
            article_id=article_id,
            title=title or f"Article {article_id}",
            canonical_url=f"https://support.example/{article_id}",
            source_url=f"https://support.example/{article_id}",
            status=status,
            is_active=is_active,
        )
    )
    records = [
        ChunkRecord(
            chunk_id=chunk_id,
            article_id=article_id,
            chunk_index=index,
            content=content,
            heading_context=heading,
        )
        for index, (chunk_id, content, _, heading) in enumerate(chunks)
    ]
    store.sync_chunks(article_id, records)
    for chunk_id, _content, vector, _heading in chunks:
        store.save_embedding(
            EmbeddingRecord(
                chunk_id=chunk_id,
                embedding=vector,
                model="stub",
                dimensions=len(vector),
            )
        )


def three_article_store() -> InMemoryKnowledgeStore:
    store = InMemoryKnowledgeStore()
    seed(store, "a1", [("c1", "password reset instructions", [1.0, 0.0, 0.0], "Account")])
    seed(store, "a2", [("c2", "billing invoice questions", [0.7, 0.7, 0.0], "Billing")])
    seed(store, "a3", [("c3", "unrelated widgets topic", [0.0, 0.0, 1.0], "Widgets")])
    return store


class StubProvider:
    def __init__(self, vector, model_name="stub"):
        self.vector = list(vector)
        self.model_name = model_name
        self.dimensions = len(vector)

    def embed(self, texts):
        return [list(self.vector) for _ in texts]


def test_nearest_neighbor_ordering():
    store = three_article_store()
    retriever = Retriever(store, StubProvider([1.0, 0.0, 0.0]), RetrievalConfig(top_k=5, min_score=0.0))
    result = retriever.retrieve("how do I reset a password?")
    assert [hit.chunk_id for hit in result.hits] == ["c1", "c2", "c3"]
    assert result.hits[0].score > result.hits[1].score > result.hits[2].score
    assert result.hits[0].title
    assert result.hits[0].canonical_url
    assert result.hits[0].heading_context == "Account"
    assert result.indexed_chunks == 3


def test_result_limit():
    store = three_article_store()
    retriever = Retriever(store, StubProvider([1.0, 0.0, 0.0]), RetrievalConfig(top_k=2))
    result = retriever.retrieve("password")
    assert len(result.hits) == 2


def test_threshold_filters_weak_matches():
    store = three_article_store()
    retriever = Retriever(store, StubProvider([1.0, 0.0, 0.0]), RetrievalConfig(min_score=0.99))
    result = retriever.retrieve("password")
    assert [hit.chunk_id for hit in result.hits] == ["c1"]
    assert any("min_score" in note for note in result.notes)


def test_empty_index_returns_no_hits():
    store = InMemoryKnowledgeStore()
    retriever = Retriever(store, StubProvider([1.0, 0.0, 0.0]))
    result = retriever.retrieve("anything")
    assert result.hits == []
    assert result.indexed_chunks == 0
    assert "empty" in result.notes[0]


def test_model_mismatch_raises():
    store = three_article_store()
    retriever = Retriever(store, StubProvider([1.0, 0.0, 0.0], model_name="different"))
    with pytest.raises(IndexModelMismatch):
        retriever.retrieve("password")


def test_dimension_mismatch_raises():
    store = three_article_store()
    retriever = Retriever(store, StubProvider([1.0, 0.0, 0.0, 0.0]))  # 4 dims vs 3
    with pytest.raises(IndexModelMismatch):
        retriever.retrieve("password")


def test_inactive_article_is_excluded():
    store = three_article_store()
    store.articles["a1"].is_active = False
    retriever = Retriever(store, StubProvider([1.0, 0.0, 0.0]))
    result = retriever.retrieve("password")
    assert "c1" not in {hit.chunk_id for hit in result.hits}
    assert result.indexed_chunks == 2


def test_failed_article_is_excluded():
    store = InMemoryKnowledgeStore()
    seed(store, "bad", [("cbad", "broken", [1.0, 0.0, 0.0], "")], status="failed")
    retriever = Retriever(store, StubProvider([1.0, 0.0, 0.0]))
    result = retriever.retrieve("broken")
    assert result.hits == []
    assert result.indexed_chunks == 0


def test_near_duplicate_chunks_are_dropped():
    store = InMemoryKnowledgeStore()
    seed(
        store,
        "a1",
        [
            ("c1", "reset your password via the email link", [1.0, 0.0, 0.0], "Account"),
            ("c2", "reset your password via the email link option", [0.99, 0.01, 0.0], "Account"),
        ],
    )
    retriever = Retriever(
        store,
        StubProvider([1.0, 0.0, 0.0]),
        RetrievalConfig(max_per_article=5, min_score=0.0),
    )
    result = retriever.retrieve("password reset")
    assert len(result.hits) == 1
    assert any("duplicate" in note for note in result.notes)


def test_per_article_cap_limits_dominance():
    store = InMemoryKnowledgeStore()
    seed(
        store,
        "a1",
        [
            ("c1", "alpha content one", [1.0, 0.0, 0.0], ""),
            ("c2", "beta content two", [0.9, 0.1, 0.0], ""),
            ("c3", "gamma content three", [0.8, 0.2, 0.0], ""),
        ],
    )
    retriever = Retriever(
        store, StubProvider([1.0, 0.0, 0.0]), RetrievalConfig(max_per_article=2, min_score=0.0)
    )
    result = retriever.retrieve("content")
    assert len(result.hits) == 2


def test_empty_question_raises():
    store = three_article_store()
    retriever = Retriever(store, StubProvider([1.0, 0.0, 0.0]))
    with pytest.raises(ValueError):
        retriever.retrieve("   ")


def test_top_k_override():
    store = three_article_store()
    retriever = Retriever(store, StubProvider([1.0, 0.0, 0.0]), RetrievalConfig(top_k=5))
    result = retriever.retrieve("password", top_k=1)
    assert len(result.hits) == 1
