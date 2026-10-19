# AI Tech Consultant — Feature & Architecture Analysis

> Generated: October 18, 2026

## 1. System Overview

The AI Tech Consultant is a multi-service system with three backend microservices and a Vite/React frontend.

**Services:**
| Service | Role | Runtime | Port | Base URL |
|---|---|---|---|---|
| Task 1 — Knowledge Brain | Shared knowledge retrieval + grounded answers with citations | FastAPI (Python) | 8000 | http://localhost:8000 |
| Task 2 — Inbox Agent | Email triage, KB-grounded drafting, human review workflow with audit | Fastify (TypeScript/Node) | 8080 | http://localhost:8080 |
| Task 3 — Meeting-to-Scope | Transcript ingestion → requirements → feasibility → proposal → versioned baselines | FastAPI (Python) | 8090 | http://localhost:8090 |
| Frontend | Dashboard/workspace UI | Vite+React+TS | 5173 | http://localhost:5173 |


## 2. Architecture

* Frontend: frontend/src/app/App.tsx, frontend/src/components/layout/WorkspaceShell.tsx, frontend/src/api/*.ts
* Task 1: task1-knowledge-brain/app/main.py (FastAPI), app/service.py, app/kb_client.py, app/models.py, app/schemas.py
* Task 2: task2-inbox-agent/src/server.ts, src/agent.ts, src/review.ts, src/kbClient.ts, src/factory.ts, src/store.ts, src/postgresStore.ts
* Task 3: task3-meeting-to-scope/app/main.py (FastAPI), app/service.py, app/store.py, app/kb_client.py, app/schemas.py, app/config.py

**CORS:** All backends allow http://localhost:5173 and http://127.0.0.1:5173.

## 3. Key Endpoints

**Task 1 (8000):** POST /ask, GET /health, GET /ready, GET /, GET /chat, POST /ingestion/run, GET /ingestion/status, POST /query, POST /escalations, GET /escalations, POST /escalations/{id}/resolve

**Task 2 (8080):** GET /health, GET /ready, POST /emails, GET /emails, GET /emails/:id, POST /emails/:id/draft, POST /emails/:id/review, GET /emails/:id/audit, GET /feedback, GET /stats, GET /

**Task 3 (8090):** GET /health, GET /ready, POST /transcripts, GET /projects, project-scoped GETs/POSTs for feasibility/proposals/baselines/updates/changes/reviews; also GET /ui, GET /

## 4. Core Features

**Task 1 Knowledge Brain:** Evidence-first answering with citations to retrieved chunks; safe abstention when insufficient evidence; prompt-injection guard; readiness reports index state; ingestion/status endpoints; escalation model (	ask1-knowledge-brain/app/main.py, pp/service.py).

**Task 2 Inbox Agent:** Deterministic rules or LLM classification; KB-grounded draft generation via Task 1 /ask; human review state machine (approve/edit/reject/escalate) with audit trail; automation eligibility safeguard (threshold); in-memory or Postgres store (src/agent.ts, src/review.ts, src/factory.ts, src/server.ts).

**Task 3 Meeting-to-Scope:** Transcript ingest/parse; extract requirements with evidence; feasibility assessment (grounded via KB); generate traceable proposal; versioned baselines (only explicit approval creates baseline); change summaries/events; human review actions for requirements/proposals/scope changes (pp/service.py, pp/main.py, pp/schemas.py).

**Frontend:** Route-based workspace (App.tsx), sidebar nav; live pages (pages/Knowledge.tsx, pages/Inbox.tsx, pages/MeetingToScope.tsx, pages/Overview.tsx, pages/Settings.tsx) call real APIs; demo feature views under eatures/* for alternative UX; shared API clients/config (rontend/src/api/*).

## 5. Technology Stack

**Frontend:** React 19, TypeScript, Vite 8, react-router-dom 6, @tanstack/react-query, Tailwind CSS v4, zod, lucide-react, vitest/testing-library (rontend/package.json).
**Task 1:** FastAPI, Pydantic, SQLAlchemy, pgvector, httpx, beautifulsoup4, openai/ollama-compatible clients; Python 3.10+ (	ask1-knowledge-brain/requirements.txt).
**Task 2:** Fastify, zod, axios, pg/pg-pool, dotenv, pino, ts-node (	ask2-inbox-agent/package.json).
**Task 3:** FastAPI, Pydantic v2, httpx, SQLAlchemy, pgvector, python-dateutil (	ask3-meeting-to-scope/requirements.txt).

## 6. Data & Persistence

**Task 1:** PostgreSQL + pgvector for articles/chunks/embeddings/index metadata (schema/migrations implied by models; pp/models.py, ingestion code). Can operate with DB configured; DATABASE_URL from env.
**Task 2:** In-memory store by default (src/store.ts); Postgres store (src/postgresStore.ts) when DATABASE_URL set (schema inbox_agent). Demo dataset auto-loaded from EMAIL_DATASET_PATH (src/config.ts, src/server.ts).
**Task 3:** In-memory store (pp/store.py:InMemoryStore) default; Postgres-backed store via uild_postgres_service when settings.database_url set (pp/main.py:58-68, pp/service.py).
**Frontend:** No server-side DB; all state via React Query + local component state.

## 7. Integration & Cross-Service Calls

- Task 2 → Task 1: KnowledgeBrainClient.ask() posts to {KB_BASE}/ask with timeout/retries (	ask2-inbox-agent/src/kbClient.ts:13-119).
- Task 3 → Task 1: KbClient.ask() posts to /ask with timeout (	ask3-meeting-to-scope/app/kb_client.py:1-70).
- Frontend → all: per-service clients; http.ts centralizes fetch with JSON headers and error mapping.
- Timeouts/retries configured per service (Task 2 has KNOWLEDGE_BRAIN_TIMEOUT_MS, RETRIES; Task 3 has equest_timeout_seconds; Task 1 uses httpx timeouts).

## 8. Health, Readiness, Resiliency

- All services expose GET /health (liveness).
- Task 1: GET /ready returns dependency/index summary (	ask1-knowledge-brain/app/main.py:116-126, pp/service.py:199-210).
- Task 2: GET /ready includes KB reachability (knowledge_brain_reachable) (	ask2-inbox-agent/src/server.ts:87-96).
- Task 3: GET /ready reports KB reachability (	ask3-meeting-to-scope/app/main.py:157-167).
- KB clients implement retries with backoff (Task 2). Timeouts enforced across service boundaries.

## 9. Configuration

**Task 1:** .env / .env.example for DB, embedding/chat providers, models, timeouts (	ask1-knowledge-brain/.env.example).
**Task 2:** .env for PORT, KB URL, CLASSIFIER/LLM, timeouts/retries, MAX_CONSECUTIVE_UNEDITED_APPROVALS, DATABASE_URL, EMAIL_DATASET_PATH (	ask2-inbox-agent/.env.example).
**Task 3:** pp/config.py loads env (PORT, DATABASE_URL, KB_URL, timeouts) (	ask3-meeting-to-scope/app/config.py:1-38).
**Frontend:** Vite env (VITE_*) via import.meta.env; defaults in rontend/src/api/config.ts:20-22.

## 10. Current State & Observed Issues

**Working well:** URLs match across frontend/backend; CORS configured on all services; live API pages wire correctly to backends; Task 2/3 call Task 1; health/readiness implemented; review workflows present.

**Known issues (from audit):**
* Overview page reads index.chunks/index.document_count but Task 1 returns indexed_chunks → tile always 'Unavailable' (pages/Overview.tsx:86-92 vs 	ask1-knowledge-brain/app/models.py:164-171).
* Demo Inbox 'Approve & send'/'Reject' only mutate local state (no API call) (eatures/inbox/InboxAgentView.tsx:319-333).
* /overview route orphaned from nav; live pages /knowledge, /inbox, /meeting only reachable from Overview (pp/App.tsx:80-83).
* Several demo view CTAs/inputs inert (KnowledgeBrain demo ask not wired to real API; KB Mgmt/Escalations/Meeting demo CTAs have no handlers).
* Dead shell chrome (org selector, sync status, help, kebab, project selection) (components/layout/WorkspaceShell.tsx).
* href=\
* Minor client guards missing (empty editedDraft on edit → 400; empty approved_by on baseline approve → 422).
* Some API functions unused (knowledgeApi.health, inboxApi.health, inboxApi.ingestEmails, inboxApi.audit, inboxApi.feedback, meetingApi.health, meetingApi.listTranscripts).

## 11. Testing & Quality

**Frontend:** 
pm run typecheck (tsc -b) passes; 
pm run lint (oxlint) passes with warnings only; 
pm run test (vitest) passes 4/4 (rontend/package.json:6-14).
**Task 1:** pytest configured (pytest.ini); tests include unit + integration (opt-in with TEST_DATABASE_URL). See M5_VERIFICATION_REPORT.md for coverage.
**Task 2/3:** TypeScript/Node and FastAPI projects with their own tests (not all executed in this session).

## 12. Notes

- All services bind to localhost for dev; Task 2 binds 0.0.0.0 in listen but CORS/origin control applies (	ask2-inbox-agent/src/server.ts:170).
- Task 3's Settings.port defined but server started via uvicorn command line (	ask3-meeting-to-scope/app/config.py:25); effective port is the one passed to uvicorn.
- Demo dataset loaded at Task 2 startup when in-memory store used (datasets/emails-sample.json).

---
*Document generated by automated analysis of the codebase.*
