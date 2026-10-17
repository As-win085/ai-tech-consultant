-- 0002_articles_active: track whether an article is currently searchable.
--
-- KB-FR-07 requires removed/stale sources to be marked inactive rather than
-- silently left as current. Retrieval only returns chunks whose article is
-- status = 'ok' AND is_active = TRUE. The indexing pipeline reactivates an
-- article whenever it is re-crawled and upserted.

ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE articles
    ADD COLUMN IF NOT EXISTS deactivated_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_articles_active ON articles (is_active) WHERE is_active;
