-- Task 3 (Meeting-to-Scope Agent) initial schema.
-- All tables live in the configured schema (default: meeting_to_scope).
-- Each aggregate is stored as a validated Pydantic model serialized to JSONB,
-- with the identifiers/status that we query on promoted to real columns.

CREATE TABLE IF NOT EXISTS mt_project (
    project_id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mt_transcript (
    transcript_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    sequence INTEGER NOT NULL DEFAULT 1,
    content_hash TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, content_hash)
);

CREATE TABLE IF NOT EXISTS mt_requirement (
    requirement_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    transcript_id TEXT NOT NULL,
    status TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mt_assessment (
    requirement_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    status TEXT NOT NULL,
    data JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS mt_proposal (
    proposal_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    status TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mt_baseline (
    project_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    status TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_at TIMESTAMPTZ,
    PRIMARY KEY (project_id, version)
);

CREATE TABLE IF NOT EXISTS mt_change_summary (
    project_id TEXT NOT NULL,
    to_transcript_id TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, to_transcript_id)
);

CREATE TABLE IF NOT EXISTS mt_baseline_update (
    project_id TEXT NOT NULL,
    to_transcript_id TEXT NOT NULL,
    proposed_version INTEGER NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, to_transcript_id)
);

CREATE TABLE IF NOT EXISTS mt_review_event (
    event_id TEXT PRIMARY KEY,
    project_id TEXT,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    data JSONB NOT NULL,
    at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS mt_requirement_project_idx ON mt_requirement (project_id);
CREATE INDEX IF NOT EXISTS mt_proposal_project_idx ON mt_proposal (project_id);
CREATE INDEX IF NOT EXISTS mt_review_event_project_idx ON mt_review_event (project_id);
