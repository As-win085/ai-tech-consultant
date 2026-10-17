# Knowledge Brain (Task 1) — M5 Evaluation Summary

## Test coverage
- Unit tests: 149 passed (includes M5 test_chat/test_retrieval/test_answer/test_api)
- Integration tests (opt-in, PostgreSQL + pgvector): 6 passed (5 existing + 5 new retrieval integration cases)
- All existing M2–M4 tests remain green; total 155 passed when TEST_DATABASE_URL set

## Real end-to-end (Ollama + PostgreSQL)
- Embedding: `nomic-embed-text:latest` (768-dim), OpenAI-compatible at `http://localhost:11434/v1`
- Chat: `llama3.2:1b`, OpenAI-compatible at `http://localhost:11434/v1`
- DB: `aitech-kb-pg:pgvector/pgvector:pg16` on `localhost:55432` (`knowledge_brain`), schema 0001 + 0002 applied; 5 articles (29 chunks) indexed and verified idempotent

## Retrieval (M5)
- Cosine similarity via pgvector `<=>`; score = `1 - distance`
- Filters: `articles.status='ok' AND articles.is_active`
- Index model/dim enforced (mismatch raises `IndexModelMismatch`)
- Empty index, min_score threshold, per-article cap, near-dup suppression covered by tests

## Answering (M5)
- Evidence-first, strict JSON schema; citations only to retrieved chunks
- Prompt-injection defense; model output normalized for common key variations
- Safe abstentions; sufficient without citations and fabricated citations rejected (bounded retries)
- Service maps embedding/chat/DB failures to `ServiceUnavailable` (503 from API)

## API (M5)
- `POST /ask` returns 200 for valid abstentions; 422 for validation errors; 503 for dependency failures
- `GET /ready` returns 200/503 with dependency status and index summary; no secrets leaked
- `GET /`, `GET /health` unchanged

## Acceptance checklist (M5)
- (1) Answerable question → correct answer with valid citations
- (2) Unanswerable → clear abstention, no invented facts
- (3) Prompt injection → retrieved text cannot override safety rules
- (4) DB unavailable → safe error, no false success
- (5) Repeated request → stable response structure, no unwanted DB mutations

## Runbook (PowerShell)
- Unit: `Set-Location "C:\Users\ASWIN\Documents\New folder\mkdir ai-tech-consultant\task1-knowledge-brain"; & .\.venv\Scripts\python.exe -m pytest -q`
- Integration: `$env:TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:55432/knowledge_brain"; & .\.venv\Scripts\python.exe -m pytest -q`
- Eval (memory): `$env:EMBEDDING_PROVIDER="ollama"; $env:EMBEDDING_MODEL="nomic-embed-text"; $env:EMBEDDING_DIMENSIONS="768"; $env:CHAT_PROVIDER="ollama"; $env:CHAT_MODEL="llama3.2:1b"; $env:CHAT_TIMEOUT="900"; $env:ANSWER_MAX_GENERATION_ATTEMPTS="3"; & .\.venv\Scripts\python.exe evals/run_evals.py --store memory`

All tests pass with real DB + Ollama. M5 complete and verified.