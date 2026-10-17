-- 0001_init: Knowledge Brain core schema (PostgreSQL 16 + pgvector)
--
-- Requires the pgvector extension. The connecting role must be allowed to
-- CREATE EXTENSION (a superuser or a role granted the extension), or the
-- extension must already be installed in the target database.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS articles (
    article_id              TEXT PRIMARY KEY,
    canonical_url           TEXT,
    source_url              TEXT,
    title                   TEXT NOT NULL DEFAULT '',
    last_modified           TEXT,
    change_frequency        TEXT,
    priority                DOUBLE PRECISION,
    fetched_at              TEXT,
    http_status             INTEGER,
    source_content_hash     TEXT,
    normalized_content_hash TEXT,
    char_count              INTEGER NOT NULL DEFAULT 0,
    status                  TEXT NOT NULL,
    error                   TEXT,
    chunk_count             INTEGER NOT NULL DEFAULT 0,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT articles_status_check CHECK (status IN ('ok', 'failed', 'skipped'))
);

CREATE INDEX IF NOT EXISTS idx_articles_status ON articles (status);
CREATE INDEX IF NOT EXISTS idx_articles_canonical_url ON articles (canonical_url);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id             TEXT PRIMARY KEY,
    article_id           TEXT NOT NULL REFERENCES articles (article_id) ON DELETE CASCADE,
    chunk_index          INTEGER NOT NULL,
    heading_context      TEXT NOT NULL DEFAULT '',
    content              TEXT NOT NULL,
    char_count           INTEGER NOT NULL DEFAULT 0,
    content_hash         TEXT NOT NULL,
    article_content_hash TEXT,
    embedding_status     TEXT NOT NULL DEFAULT 'pending',
    embedding_error      TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chunks_embedding_status_check
        CHECK (embedding_status IN ('pending', 'embedded', 'failed')),
    CONSTRAINT chunks_article_index_unique UNIQUE (article_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_article_id ON chunks (article_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_status ON chunks (embedding_status);

-- One current embedding per chunk. The vector column is deliberately
-- dimensionless so the embedding model/dimension stays configurable; the CHECK
-- keeps the stored dimension and the vector length consistent, and the pipeline
-- re-embeds (never mixes) when the configured model or dimension changes.
CREATE TABLE IF NOT EXISTS chunk_embeddings (
    chunk_id        TEXT PRIMARY KEY REFERENCES chunks (chunk_id) ON DELETE CASCADE,
    embedding       vector NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_dim   INTEGER NOT NULL,
    embedded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chunk_embeddings_dim_check CHECK (vector_dims(embedding) = embedding_dim)
);

CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_model ON chunk_embeddings (embedding_model);

CREATE TABLE IF NOT EXISTS indexing_runs (
    run_id             BIGSERIAL PRIMARY KEY,
    status             TEXT NOT NULL,
    model              TEXT,
    dimensions         INTEGER,
    started_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at        TIMESTAMPTZ,
    articles_processed INTEGER NOT NULL DEFAULT 0,
    articles_failed    INTEGER NOT NULL DEFAULT 0,
    chunks_written     INTEGER NOT NULL DEFAULT 0,
    chunks_pruned      INTEGER NOT NULL DEFAULT 0,
    chunks_embedded    INTEGER NOT NULL DEFAULT 0,
    chunks_skipped     INTEGER NOT NULL DEFAULT 0,
    chunks_failed      INTEGER NOT NULL DEFAULT 0,
    error              TEXT,
    CONSTRAINT indexing_runs_status_check
        CHECK (status IN ('running', 'ok', 'partial', 'failed'))
);
