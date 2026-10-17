# Task 1 — Knowledge Brain

Shared knowledge service for the AI Tech Consultant project. This service owns support-article
ingestion and (in later milestones) chunking, embeddings, retrieval, and grounded answers with
citations. Task 2 and Task 3 must call this service over HTTP rather than copy its logic.

Current milestone: **Milestone 4 — PostgreSQL + pgvector storage and the embedding/indexing
pipeline**. Retrieval, cited answer generation, abstention, and the HTTP knowledge API are
**not implemented yet**.

## Requirements

- Python 3.10+ (developed and verified on 3.14)
- Git

## Setup

```powershell
cd task1-knowledge-brain
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If a virtual environment does not exist yet:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run the API

```powershell
python -m uvicorn app.main:app --reload
```

- `GET /` — service identity
- `GET /health` — process health
- `GET /docs` — interactive OpenAPI docs

## Crawler

Reads the Brilliant Directories support sitemap, extracts article content, and writes structured JSON.
Only article URLs (`/support/solutions/articles/...`) are ingested; folders and other pages are skipped.

```powershell
# Small batch (recommended for local testing)
python -m app.crawler --limit 5 --output data/articles-sample.json

# Full run
python -m app.crawler --limit 0 --output data/articles.json
```

Options:

| Option | Default | Description |
| --- | --- | --- |
| `--limit` | `5` | Number of articles to crawl (`0` = all) |
| `--sitemap` | support sitemap URL | Sitemap or sitemap-index URL |
| `--output` | `data/articles.json` | Output JSON path |
| `--delay` | `0.5` | Seconds between article requests (pacing) |

Behavior:

- Supports both direct sitemaps (`<urlset>`) and nested sitemap indexes (`<sitemapindex>`).
- Descriptive `User-Agent`, 30-second timeout, and request pacing via `--delay`.
- Per-URL error isolation: HTTP errors, network failures, timeouts, malformed HTML, and empty
  pages are recorded as `status: "failed"` and never stop the rest of the crawl.
- Empty extractions are treated as failed and are **not** valid knowledge.
- Duplicate article URLs are de-duplicated using safe URL normalization (fragments and trailing
  slashes are normalized; distinct article IDs are never merged).

### Output shape

```json
{
  "source": {
    "sitemap_url": "...",
    "site": "support.brilliantdirectories.com",
    "crawled_at": "...",
    "article_urls_found": 1537,
    "articles_crawled": 5,
    "articles_ok": 5,
    "articles_failed": 0
  },
  "articles": [
    {
      "id": "5000558363",
      "url": "...",
      "canonical_url": "...",
      "title": "...",
      "text": "...",
      "headings": [{ "level": 2, "text": "..." }],
      "char_count": 2130,
      "content_hash": "...",
      "last_modified": "...",
      "change_frequency": "always",
      "priority": 0.512,
      "fetched_at": "...",
      "http_status": 200,
      "status": "ok",
      "error": null
    }
  ]
}
```

Generated data lives in `task1-knowledge-brain/data/`, which is git-ignored.

## Normalization and chunking

The normalized + chunked pipeline turns crawled articles into retrieval-ready units. It is pure
and deterministic (no embeddings, database, or model calls), so it can be run offline and tested
in isolation.

### Normalization (`app.normalizer`)

The crawler stores article text as one line per inline text node, which splits any paragraph that
contained links/bold/code into fragments. Normalization rebuilds structure:

- `build_blocks` re-detects headings in order and rejoins paragraph fragments (smart spacing,
  closing a paragraph on `.`/`!`/`?`).
- `build_sections` groups paragraphs under a heading hierarchy and produces a `breadcrumb`
  (`"Parent > Child"`).
- `normalize_article` returns `None` for records that are not `status: "ok"` or have empty text,
  so failed/empty pages are never turned into knowledge. `normalize_articles` de-duplicates by
  `article_id` and preserves order.

### Chunking (`app.chunker`)

```powershell
# Uses the sample crawl; writes retrieval chunks
python -m app.chunker --input data/articles-sample.json --output data/chunks-sample.json
```

Options:

| Option | Default | Description |
| --- | --- | --- |
| `--input` | `data/articles-sample.json` | Crawled articles JSON |
| `--output` | `data/chunks-sample.json` | Chunks JSON output path |
| `--chunk-size` | `1000` | Max chunk size (`ChunkConfig.chunk_size`) |
| `--overlap` | `200` | Shared size between adjacent chunks |

Behavior:

- Chunk size and overlap are configurable as a `ChunkConfig`; invalid values (size `< 1`,
  overlap `< 0`, or `overlap >= chunk_size`) raise `ValueError`.
- Boundaries snap back to a sentence, then newline, then word boundary so chunks read cleanly;
  overlap is applied as a shared tail between adjacent chunks of the same section.
- Every chunk links back to its article (`article_id`, `title`, `canonical_url`, `source_url`) and
  carries a `heading_context` breadcrumb, a `chunk_index`, a `content_hash`, and the article's
  `content_hash`.
- `chunk_id` is a stable hash of `article_id|chunk_index|content_hash`, so reprocessing an
  unchanged article yields identical chunk identifiers (no duplicates).
- Empty/boilerplate-only sections produce no chunks. Sizing is character-based — there is no
  tokenizer installed, which is a documented limitation.

### Chunk output shape

```json
{
  "config": { "chunk_size": 1000, "overlap": 200, "unit": "characters" },
  "source": { "articles_normalized": 5, "chunks_total": 29, "generated_at": "..." },
  "articles": [
    { "article_id": "5000558363", "title": "...", "canonical_url": "...", "chunks": 6 }
  ],
  "chunks": [
    {
      "chunk_id": "...",
      "article_id": "5000558363",
      "title": "...",
      "canonical_url": "...",
      "source_url": "...",
      "chunk_index": 0,
      "heading_context": "Emails \u00bb Email Accounts",
      "content": "...",
      "char_count": 213,
      "content_hash": "...",
      "article_content_hash": "..."
    }
  ]
}
```

## Indexing pipeline (PostgreSQL + pgvector)

The indexing pipeline normalizes and chunks the crawl, persists articles/chunks, and stores one
embedding per chunk in PostgreSQL with the pgvector extension. It is **idempotent**: re-running the
same input creates no duplicates.

### Prerequisites

A PostgreSQL 16 server with the `vector` extension available. For local development a throwaway
container is enough (this is what the milestone was verified against):

```powershell
docker run -d --name aitech-kb-pg -p 55432:5432 `
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=knowledge_brain pgvector/pgvector:pg16
```

### Configuration

Copy `.env.example` to `.env` and fill in values. `.env` is git-ignored; never commit real secrets.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL/pgvector connection string (required unless `--dry-run`) |
| `EMBEDDING_PROVIDER` | `fake` \| `openai` \| `openai_compatible` \| `ollama` |
| `EMBEDDING_MODEL` | Model name sent to the provider (required for every non-fake provider) |
| `EMBEDDING_DIMENSIONS` | Expected vector size; validated against every returned vector |
| `EMBEDDING_API_KEY` | Required for `openai` / `openai_compatible` |
| `EMBEDDING_BASE_URL` | Override endpoint; defaults per provider |
| `EMBEDDING_BATCH_SIZE` | Chunks per embedding request (default `64`) |

The real provider speaks the OpenAI-compatible `POST {base_url}/embeddings` API, so it works with
OpenAI, Azure-compatible gateways, and a local Ollama server (`EMBEDDING_PROVIDER=ollama`,
`EMBEDDING_BASE_URL=http://localhost:11434/v1`). The `fake` provider is deterministic and offline
and is **not** a real embedding — it is for tests and dry runs only.

### Running

```powershell
# Validate the whole pipeline without touching the database or any API
python -m app.indexer --input data/articles-sample.json --dry-run

# Real run: persist to PostgreSQL and embed with the configured provider
python -m app.indexer --input data/articles-sample.json
```

Options:

| Option | Default | Description |
| --- | --- | --- |
| `--input` | `data/articles-sample.json` | Crawled articles JSON |
| `--chunk-size` | `1000` | Max characters per chunk |
| `--overlap` | `200` | Shared characters between chunks |
| `--batch-size` | from env | Embedding batch size override |
| `--dry-run` | off | In-memory store + fake embeddings; nothing persisted |

The CLI applies pending SQL migrations (from `app/migrations/`) on startup and records every run in
`indexing_runs`.

### Behavior

- Schema: `articles` (PK `article_id`) ← `chunks` (FK `article_id`, PK `chunk_id`) ←
  `chunk_embeddings` (FK `chunk_id`, 1:1). `chunk_embeddings` also stores `embedding_model` and
  `embedding_dim`, constrained by `CHECK (vector_dims(embedding) = embedding_dim)`.
- Re-running unchanged input skips already-embedded chunks (no re-embedding, no duplicates).
- Changed content re-embeds only the affected chunks and prunes chunks that no longer exist.
- Changing the embedding model or dimension re-embeds every chunk; embeddings from different
  models are never mixed in the same index.
- Transient provider failures (HTTP 429/5xx/timeouts) are retried with backoff; each run records
  per-chunk failures and an overall `ok` / `partial` / `failed` status.
- The driver is `pg8000` (pure Python) because `psycopg` has no wheels for the Python 3.14 runtime
  used here.

Coverage includes sitemap/urlset parsing, nested sitemap indexes (including a failed child),
article extraction (title, text, headings, canonical URL, metadata, content hash), HTTP 404,
network failure, timeout, malformed and empty HTML, duplicate URL de-duplication, URL
normalization safety, per-URL failure isolation, and the limit option. For normalization and
chunking it covers block/paragraph reconstruction, breadcrumb building, dropping failed/empty
records, deduplication and determinism, chunk-size/overlap validation, boundary snapping,
overlap sharing, no content loss, empty-section skipping, content-hash/`chunk_id` stability, and
document aggregation. For indexing it covers the provider contract (retries, timeouts, dimension
and count validation) and the pipeline against the in-memory store (idempotent re-runs, content
changes, model/dimension changes, partial failures, restart recovery).

The embedding/indexing tests use an in-memory store and a deterministic fake provider, so they are
offline. A small integration suite additionally exercises the real PostgreSQL + pgvector store; it
is **skipped unless `TEST_DATABASE_URL` is set**:

```powershell
$env:TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:55432/knowledge_brain"
python -m pytest -m integration
```

## Known limitations

- No retrieval, answer generation, citations, abstention, or HTTP knowledge API yet (Milestone 5).
- Chunk sizing is character-based; no tokenizer is installed, so sizes are not token-aligned.
- Inline-markup paragraph reconstruction is heuristic (punctuation-based), not an HTML re-parse.
- No ANN/vector index is created yet; similarity search (a later milestone) will scan all rows
  until an appropriate index (e.g. HNSW/IVFFlat) is added and tuned.
- Embedding dimensions must be consistent for a given `EMBEDDING_MODEL`; switching models or
  dimensions triggers a full re-embed by design (no mixed indexes).
- No readiness/diagnostics HTTP endpoint that distinguishes database/index/model availability yet.
- No scheduled/incremental ingestion trigger yet; `content_hash` is stored and a re-run already
  detects changes, but nothing invokes it on a schedule.
- `requirements.txt` is currently a full `pip freeze` (now including `pg8000`); it will be curated
  in a later milestone.
