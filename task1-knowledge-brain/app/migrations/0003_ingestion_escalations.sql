CREATE TABLE IF NOT EXISTS escalations (
    escalation_id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    reason TEXT NOT NULL,
    request_id TEXT UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'resolved')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_escalations_status_created
    ON escalations (status, created_at DESC);

CREATE TABLE IF NOT EXISTS escalation_answers (
    escalation_id TEXT NOT NULL REFERENCES escalations (escalation_id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version > 0),
    answer TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    article_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (escalation_id, version),
    UNIQUE (article_id)
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id BIGSERIAL PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('running', 'ok', 'partial', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    sitemap_url TEXT NOT NULL,
    article_urls_found INTEGER NOT NULL DEFAULT 0,
    articles_crawled INTEGER NOT NULL DEFAULT 0,
    articles_ok INTEGER NOT NULL DEFAULT 0,
    articles_failed INTEGER NOT NULL DEFAULT 0,
    articles_deactivated INTEGER NOT NULL DEFAULT 0,
    error TEXT
);
