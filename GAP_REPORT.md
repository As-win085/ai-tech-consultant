# GAP REPORT v2 — AI Tech Consultant (Phase 1 Audit, firm statuses)

**Audit basis:** `AI_Tech_Consultant_Project_Requirements.md` (the brief).
**Method:** read-only code inspection (grep/read with file:line evidence) + actual test runs.
**Date:** 2026-10-19. **Repo root:** `C:\Users\ASWIN\Documents\New folder\mkdir ai-tech-consultant` (single `.git`; verified via `git rev-parse --show-toplevel`). This report already lives at that root. Note: the root folder's own name contains an accidental `mkdir ` prefix — rename the folder to `ai-tech-consultant` manually (stop servers first) if desired; git history is unaffected.

**Status legend:** DONE / PARTIAL / MISSING. Fix size: S (<half day), M (1–2 days), L (3+ days).

---

## TASK 1 — Knowledge Brain (FastAPI, :8000)

| # | Requirement | Status | Evidence | Size |
|---|---|---|---|---|
| 1 | Crawl: sitemap parse, rate limit, batching, checkpoint/resume | **PARTIAL** | Sitemap parse + per-URL error handling + `--delay` pacing + `--limit`: `task1-knowledge-brain/app/crawler.py:157-185, 313-340, 417-424`. Article-URL filtering: `crawler.py` path filter (`/support/solutions/articles/`). Embedding batching: `app/embeddings.py` (BATCH config). **Missing:** crash checkpoint/resume — only an output manifest is written (`crawler.py:384`), no resume-from-partial-run logic anywhere. | M |
| 2 | Images: vision captioning, image→article link, image text searchable in retrieval | **MISSING** | `grep -rn 'vision\|caption\|ocr\|image' task1-knowledge-brain/app` → no extraction/captioning/storing code. Chunks carry text only (`app/chunker.py:134,174`). | L |
| 3 | Daily freshness: scheduled job, added/updated/removed diff, re-index only changes, removed never in answers (proved by test) | **PARTIAL→near DONE** | In-process daily scheduler EXISTS: `app/daily_ingest.py:1-28` (UTC loop, `seconds_until_next_run`, calls `run_ingestion`). Manual trigger: `POST /ingestion/run` (`app/main.py:55-62`) + `ingestion.py:95` ("suitable for cron or Windows Task Scheduler"). Removed→inactive diff: `ingestion.py:32`, `postgres_store.py:228-235`, `store.py:136-137`. Retrieval excludes inactive: `postgres_store.py:91,102`, `store.py:207`, `retriever.py:14`. **Tests proving it:** `tests/test_ingestion.py:29-57` (deactivates removed pages), `tests/test_retrieval.py:111-113` + `tests/test_retrieval_integration.py:112-122` (inactive excluded). **Remaining:** "re-index only changes" incremental re-embedding not fully verified per-chunk; external cron intentionally not used (see DROP list). | S |
| 4 | Chatbot: citations from retrieved chunks, honest "I don't know", injection guard | **DONE** | `POST /ask` (`main.py:88-99`); citations/abstention logic `app/answer.py:328-438`; injection treated as data + cannot force uncited answer: `tests/test_answer.py:339-366`; malformed model output safe: `tests/test_answer.py:258-293`; chat UI `GET /chat` (`main.py:49-52`). | — |
| 5 | Escalation: unanswered → task; resolved expert answer re-ingested and cited in next answer to same question | **PARTIAL** | Create/list/resolve endpoints exist: `main.py:133-158`; auto-record on insufficient evidence: `service.py:108-117`; answer versioning with `article_id = reviewed-escalation-{id}-v{n}`: `store.py:164-176`, `postgres_store.py:280-292`. **Missing:** the resolved answer is stored only in the escalations table — it is never turned into an ArticleRecord/chunk/embedding, so it cannot be retrieved or cited later. No re-ingestion path exists. | M |
| 6 | API docs sufficient for an outside developer | **PARTIAL** | FastAPI auto OpenAPI at `/docs` (schemas in `app/schemas.py` with field descriptions, e.g. AskResponse at `schemas.py:85-97`). Missing: worked request/response examples per endpoint, documented error-code table, auth (none exists). | S |
| 7 | Config-driven source (any help center URL), not hardcoded | **DONE** | Default constant `SITEMAP_URL` (`crawler.py:20`) but every entry point is parameterized: `fetch_sitemap_entries(..., sitemap_url=...)` (`crawler.py:157`), `crawl(..., sitemap_url=...)` (`crawler.py:313`), CLI `--sitemap` (`crawler.py:417`), `run_ingestion(sitemap_url=...)` (`ingestion.py:25`). Any help-center sitemap URL works. | — |

## TASK 2 — Inbox Agent (TypeScript/Fastify, :8080)

| # | Requirement | Status | Evidence | Size |
|---|---|---|---|---|
| 8 | Classification taxonomy + 50+ sample emails counted by kind | **PARTIAL** | Dataset has **71 emails** (`task2-inbox-agent/datasets/emails-sample.json`; loaded at startup: server log "dataset loaded, loaded=71"). Distribution by `expected.category`: `unsupported_unclear` 17, `billing_account` 15, `troubleshooting` 13, `product_howto` 12, `complaint` 8, `feature_request` 6 (=71). Structured JSON classification w/ zod validation: `src/schemas.ts`, `src/classifier.ts`. **Gap vs brief taxonomy:** no `refund`, `quote`, `follow-up`, or `new project request` kinds; `threadId` is null in samples (no follow-up threads). | M |
| 9 | Tool calling / MCP usage (KB lookup as a tool) | **MISSING** | KB is a direct method call (`src/kbClient.ts:13-119`, invoked from `src/agent.ts`), not a tool-calling loop with tool schemas. No MCP wrapper; no tool registry. (MCP wrapper itself optional per user; tool calling required.) | M |
| 10 | Learning from human edits: what stored, how used later, metric proving improvement | **MISSING** | Feedback records stored (`GET /feedback` `server.ts:146-150`; store `feedback` tables/arrays; review history per item `postgresStore.ts:140-150`). **Missing:** no mechanism injects past edits into later drafts; no before/after improvement metric anywhere in code or evals. | M |
| 11 | Auto-send: "same kind"/"unchanged" definitions, 20-in-a-row, autonomy loss on quality drop | **PARTIAL** | 20-in-a-row counter + eligibility + reset on edit/reject/escalate: `src/agent.ts:216-269` (`consecutiveUneditedApprovals`, `automationEligible`, `automation_counter_reset` audit events); exclusions with reasons re-checked per email: `src/agent.ts:89-90,143-144,200-201`; persisted: `src/postgresStore.ts:69-71,252-258`; surfaced in `/stats` + `/ready`: `src/server.ts:88-94,153-165`; threshold config `MAX_CONSECUTIVE_UNEDITED_APPROVALS` (`src/config.ts`). "Unchanged" = approved without edit (implied by counter logic). **Missing:** explicit "same kind" definition (counter is global, not per-category); explicit demotion-on-quality-drop rule beyond the reset (e.g. rolling failure-rate demotion); simulated send endpoint. | M |
| 12 | Follow-up tracking and reminders | **MISSING** | No follow-up/reminder/schedule code in `src/` (grep: zero matches). Sample emails have `threadId: null`. | L |
| 13 | Prompt-injection + malformed-email handling; retry/timeout | **DONE** | Injection risk flag: `src/classifier.ts:13` (`prompt_injection` in `src/types.ts:23`); classifier prompt lists injection among risks (`classifier.ts:187`); tests: `tests/safety.test.ts:14-23`, `tests/classifier.test.ts:31-35`. Malformed model output → bounded retry then safe failure: `tests/classifier.test.ts:92`; malformed KB responses → typed errors: `src/kbClient.ts:102-107`, tests `tests/kbClient.test.ts:33-40`. KB retries/timeouts: `src/kbClient.ts` (timeout+retries config), `src/config.ts`. Email ingest validated by zod (`src/schemas.ts`). | — |

## TASK 3 — Meeting-to-Scope (FastAPI, :8090)

| # | Requirement | Status | Evidence | Size |
|---|---|---|---|---|
| 14 | Named agent roles, inputs/outputs, handoffs | **MISSING** | Pipeline exists as modules (`app/extractor.py`, `app/feasibility.py`, `app/proposal.py`, `app/baseline.py`, orchestrated by `app/service.py`) but there is no named-agent abstraction, no role I/O contracts, no handoff model in code or docs. | M |
| 15 | Outputs: SOW, task list with hour estimates, client-ready proposal | **DONE** | Hour estimates: `_estimate_for(..., unit="hours")` `app/proposal.py:44-50`; milestones with estimates `proposal.py:160-193`; `estimates` + `estimate_conditions` `schemas.py:289-291`; out-of-scope section `proposal.py:86`; client-ready markdown renderer with scope/estimates/exclusions sections `proposal.py:273-337`. | — |
| 16 | Clarifying questions a senior consultant would ask | **PARTIAL** | Open questions become `needs_clarification` requirements (`app/extractor.py:384`, kind list `extractor.py:150`), feasibility marks `requires_customer_clarification` (`app/feasibility.py:13,68`), proposal includes a Discovery & clarification milestone (`proposal.py:160-164`). **Missing:** no generated list of pointed consultant questions per requirement (only status flags). | S |
| 17 | KB "existing setting solves this" check, with cost impact | **MISSING** | Feasibility calls Task 1 `/ask` for grounding (`app/kb_client.py`, `app/feasibility.py`) but no code path checks whether an existing BD setting solves the need nor attaches cost impact. | M |
| 18 | Long-transcript handling (chunking/map-reduce, evidence kept) | **MISSING** | Long transcripts are **rejected**, not processed: `app/transcript.py:35,160` ("empty, malformed, too long, or otherwise unusable"). No chunking/map-reduce; evidence kept only for accepted transcripts. | L |
| 19 | Second-meeting diff: changed/new/out-of-scope (quote extra) | **DONE** | Baseline diff classifies removed/modified/clarified/unresolved + scope creep (`app/baseline.py:10-11,161-162,262`); `estimate_impact="may increase effort"` on creep (`baseline.py:262`); change summaries + events API (`main.py:251,266`); review flow for scope changes (`main.py:257-258`, `service.py:236-251`). Sample follow-up transcript exists (`data/transcripts/mtg-002-followup.json`). | — |
| 20 | Human approval gate before anything reaches the client | **DONE** | Baseline creation requires explicit approval (`main.py:241`, `schemas.py` BaselineRequest); requirement/proposal/scope-change review endpoints with enforced state machine and mandatory rejection reasons (`main.py:207-258`, `app/review.py:23-40,98`); UI approve/reject/clarify buttons (`app/ui.py:108`). | — |
| 21 | 3+ sample transcripts incl. one follow-up | **DONE** | `task3-meeting-to-scope/data/transcripts/`: `mtg-001-kickoff.json`, `mtg-002-followup.json`, `mtg-003-security-review.json` = **3 transcripts, one follow-up**. | — |

## CROSS-CUTTING

| # | Requirement | Status | Evidence | Size |
|---|---|---|---|---|
| 22 | Evals: 20+ cases/task, 2+ models compared, quality/cost/speed, one command, results saved | **PARTIAL** | **Case counts (real):** Task 1 = **29** (`task1-knowledge-brain/evals/cases.json` → `cases.Count=29`); Task 2 = **22** in `evals/cases.json` (classification 8 + draft 4 + review 6 + safety 4) **plus a 20-case holdout** (`evals/reports/holdout-20-*.json`); Task 3 = **20** (`evals/cases.json`). All ≥20. **One-command runners + saved results:** T1 `python -m evals.run_evals` (`evals/run_evals.py:47,153-155`, reports `report-task1*.json`); T2 `npm run evals` / `evals:holdout` (`package.json:16-18`, reports under `evals/reports/`); T3 `python -m evals.run_evals` (`evals/run_evals.py:122-154`, writes `report-task3.json`, prints `passed/total`). **Models compared:** T2 = 3 rows (live openrouter `liquid_lfm-2.5-2.6b_free` 20 cases, `gemini-3.8-flash` **not evaluated — quota exhausted**, rules baseline) — comparison table `evals/reports/comparison-holdout-20.json`; T1 = fake-chat (13/29) + live `gemini-3.8-flash` (**3/29**) only — 1 real model; T3 = **mock only** (`report-task3.json` metrics: "harness_mode":"mock/offline","zero live model calls") — 0 real models. **Cost/speed:** latency logged everywhere (median/p95); T2 logs input/output tokens (`comparison-holdout-20.json` rows, e.g. 4419/9904) but `estimated_cost_usd: null` ("pricing metadata not captured"); T1/T3 no cost. **Gaps:** T1 and T3 need a second real model; T3 needs live-model runs; cost estimation missing everywhere. | M |
| 23 | Cost + latency logging per LLM call; model routing with justification | **PARTIAL** | Latency/token logging exists **only in eval harnesses** (`task2/evals/runHoldout.ts:201-212`, `task3/evals/run_evals.py:100,137-138`). **No per-call cost/latency logging in service runtime** (`src/` and `app/` grep: zero matches outside evals). Single configured provider per service (`task1/app/settings.py`, `task2/src/config.ts`); no routing logic; justification not documented. Global throttling exists (`LLM_MIN_DELAY_MS`, throttle test `tests/throttle.test.ts`). | M |
| 24 | Prompts as versioned files + schema outputs + measure/rollback | **PARTIAL** | Schema-validated outputs: Pydantic (`task1/app/schemas.py`, `task3/app/schemas.py`), zod (`task2/src/schemas.ts`); malformed-output retry tests in all three. **Missing:** no `prompts/` folder exists anywhere (glob `**/prompts/**` → none). Prompts are embedded strings: `task1/app/answer.py:49-55` (JSON contract), `task2/src/classifier.ts:187`, `task3/app/prompt.py` (`build_extraction_user_prompt`). No prompt versioning, no A/B measurement or rollback mechanism. | M |
| 25 | One-command startup, .env.example, seed data | **PARTIAL** | **.env.example:** present per service (`task1/.env.example`, `task2/.env.example`, `task3/.env.example`, `frontend/.env.example`). **Seed data:** T1 `data/articles-sample.json`; T2 `datasets/emails-sample.json` (71 emails, auto-loaded); T3 `data/transcripts/` (3). **Missing:** no root `docker-compose.yml`, no root start script (`start.ps1/.cmd/.sh`, `run.ps1` — all absent at repo root); `shared-docs/` directory exists but is **empty**. Startup requires 4 separate manual commands. | M |
| 26 | Tests for main paths; run them and report pass/fail | **PARTIAL — RUN 2026-10-19** | **Task 1:** `python -m pytest -q` → **9 failed, 153 passed, 10 skipped** (180s). Failures: `test_chat.py` factory tests (anthropic/ollama/openrouter/groq key+URL handling ×6), `test_embeddings.py` factory tests (openai model/dim/key, ollama base URL ×3). **Task 2:** `npm test` → **68 passed, 3 skipped, 0 failed** (9 suites; 16.7s). **Task 3:** `python -m pytest -q` → **5 failed, 80 passed, 1 skipped** (10.8s). Failures: `test_api.py::test_ingest_transcript_via_api` (assert 500==201), `test_list_requirements_and_feasibility` (0==2), `test_review_actions` (IndexError), `test_provider_config.py` openrouter+groq (×2). **Frontend:** `npm run test` → **4 passed**; `npm run typecheck` clean; `npm run lint` warnings-only (2026-10-19 earlier run). | M |
| 27 | Frontend: wire/remove inert controls, nav to all live pages, Overview chunk bug, input guards, every screen calls real API | **PARTIAL (firm, from full audit)** | Live pages correctly call APIs with matching contracts: `pages/Knowledge.tsx:176-194`→`POST /ask`; `pages/Inbox.tsx:33-59,171-180`→`/emails*`,`/draft`,`/review`; `pages/MeetingToScope.tsx:49-125`→`/transcripts`,`/feasibility`,`/proposals`,`/baselines`. **Bugs to fix:** (a) Overview "Indexed chunks" reads `index.document_count`/`index.chunks` but Task 1 returns `indexed_chunks` → always "Unavailable" (`pages/Overview.tsx:86-92` vs `task1/app/models.py:164-171`); (b) `/overview` route orphaned — `/knowledge`,`/inbox`,`/meeting` unreachable by nav (`app/App.tsx:80-83`; no `to="/overview"` anywhere); (c) demo views have inert CTAs (`features/knowledge/KnowledgeBrainView.tsx:85-98,103-130` ask never hits API; `features/inbox/InboxAgentView.tsx:319-333` approve/reject local-only; `features/kmgmt/KnowledgeManagementView.tsx:72-83,117-122`; `features/escalations/EscalationsView.tsx:57-62,114-125`; `features/meeting/MeetingToScopeView.tsx:121-126,181-183` + dead `href="#"` at `:75,275`); (d) shell chrome dead buttons (`components/layout/WorkspaceShell.tsx:88-99,188-190,247-253`); (e) no guard: empty `editedDraft` on Save edit → backend 400 (`features/inbox/EmailDetail.tsx:97-115` vs `task2/src/schemas.ts:63`); (f) no guard: empty reviewer → `approved_by=""` → 422 (`pages/MeetingToScope.tsx:35,217` vs `task3/app/main.py:126`). | M |
| 28 | Submission files: README 1p, DESIGN.md 3-5p+diagram, EVALS.md 2-3p, AI_LOG.md 1p, demo script w/ planned failure | **MISSING (root)** | At repo root: **no README.md, no DESIGN.md, no EVALS.md, no AI_LOG.md, no demo script** (Test-Path all false). Task 2 alone has `DESIGN.md`, `EVALS.md`, `AI_LOG.md` (`task2-inbox-agent/`). Task 1/3 have only `M5/M6/M7_VERIFICATION_REPORT.md`. `shared-docs/` empty. Nothing meets the root-level submission set; no demo script with planned failure exists anywhere. | M |

---

## ADDRESSED PER REVIEWER DIRECTION

- **Config-driven source (any help center):** DONE — see Task 1 #7 evidence.
- **Injection + malformed-input in Tasks 2 and 3:** DONE — see Task 2 #13; Task 3 injection filter `app/extractor.py:216,309,411` + tests `tests/test_extractor.py:76-84`; malformed transcripts rejected `app/transcript.py:160` + test `tests/test_transcript.py:48`; malformed KB JSON `tests/test_kb_client.py:82`.
- **Submission docs status:** firm MISSING at root — see #28.

## TEST RUN LOG (2026-10-19, actual output)

```
Task 1: 9 failed, 153 passed, 10 skipped in 180.35s
  FAILED test_chat.py::test_factory_anthropic_requires_model_and_key
  FAILED test_chat.py::test_factory_anthropic_builds_with_key
  FAILED test_chat.py::test_factory_anthropic_reads_anthropic_env_fallbacks
  FAILED test_chat.py::test_factory_ollama_default_base_url
  FAILED test_chat.py::test_factory_uses_openrouter_specific_key_and_default_url
  FAILED test_chat.py::test_factory_uses_groq_specific_key_and_default_url
  FAILED test_embeddings.py::test_factory_requires_model_and_dimensions_for_openai
  FAILED test_embeddings.py::test_factory_requires_api_key_for_openai
  FAILED test_embeddings.py::test_factory_ollama_default_base_url_and_no_key
Task 2: Tests: 3 skipped, 68 passed, 71 total (9 suites passed, 2 skipped) in 16.7s — 0 failures
Task 3: 5 failed, 80 passed, 1 skipped in 10.77s
  FAILED test_api.py::test_ingest_transcript_via_api (assert 500 == 201)
  FAILED test_api.py::test_list_requirements_and_feasibility (assert 0 == 2)
  FAILED test_api.py::test_review_actions (IndexError)
  FAILED test_provider_config.py::test_openrouter_provider_uses_specific_key_and_default_url
  FAILED test_provider_config.py::test_groq_provider_uses_specific_key_and_default_url
Frontend: vitest 4 passed (1 file); tsc -b clean; oxlint warnings only
```

## DATASET COUNTS (actual)

- **Task 2 emails: 71** — unsupported_unclear 17, billing_account 15, troubleshooting 13, product_howto 12, complaint 8, feature_request 6. Brief kinds missing: refund, quote, follow-up, new-project-request (as distinct kinds).
- **Task 3 transcripts: 3** — kickoff, follow-up, security-review (one follow-up ✓).

## PRIORITY LIST (eval harness first; every later fix measured by it)

| Pri | Item | Impact | Size | Measured by |
|---|---|---|---|---|
| **P0-1** | **Unify eval harness usage:** run T3 evals against a live model (2nd model), add 2nd real model to T1, capture cost (token×price) in all three harnesses; one root command `npm run evals` (or `eval-all.ps1`) orchestrating all three; results to `shared-docs/evals/` | 20 (Evals) | M | Eval pass-rates + cost/latency tables |
| **P0-2** | **Fix failing tests:** T1 9 factory failures (env leakage from `.env` likely), T3 5 failures (ingest 500 is a real bug) | 15 (Quality) | M | pytest green |
| **P0-3** | **Versioned prompts:** `prompts/<task>/<name>.vN.md` + output schema (Pydantic/zod) + eval-before/after + rollback note | 15 (Prompts) | M | Eval harness delta per prompt version |
| **P1-1** | Frontend fixes (#27 a–f): Overview bug, nav, guards, wire-or-remove demo CTAs | 15 (Writing/demo) + Integration | M | Manual demo script + vitest |
| **P1-2** | Task 5 escalation re-ingestion: resolve → index expert answer as KB article → prove next `/ask` cites it (test) | 15 (Problem/Design) | M | New pytest |
| **P1-3** | Task 2 tool calling: expose KB lookup as a tool schema; agent loop calls tool | 20 (Design) | M | New jest tests + eval |
| **P1-4** | Task 3 tool calling + "existing setting solves this" check w/ cost impact | 20 (Design) | M | New pytest + eval cases |
| **P1-5** | Task 2 edit-learning: store edit diffs, inject guidance into later drafts of same category, metric = edit-rate before/after | 15 (Prompts/self-improvement) | M | Eval metric |
| **P1-6** | Task 2 auto-send: per-category ("same kind") counters, simulated send endpoint, rolling demotion | 15 (Design) | M | jest + eval |
| **P2-1** | Task 1 image captioning (vision model → caption stored with article, text indexed for retrieval) | 10 | L | Eval cases w/ image Qs |
| **P2-2** | Task 1 checkpoint/resume + per-chunk incremental re-embed proof | 10 | M | pytest |
| **P2-3** | Task 3 long-transcript chunked/map-reduce extraction keeping evidence | 10 | L | New pytest |
| **P2-4** | Task 3 named agent roles/handoffs doc+code | 10 | M | DESIGN.md diagram |
| **P2-5** | Task 2 follow-up tracking (threadId linkage + reminder records) | 8 | L | jest |
| **P2-6** | One-command startup (root `start-all.ps1` + .env.example consolidation) | 8 (Demo) | M | Script run |
| **P2-7** | Submission docs: root README, DESIGN.md (diagram), EVALS.md (real numbers), AI_LOG.md, DEMO.md with planned failure | 15 (Writing/demo) | M | File presence + 1-page/length check |
| **P2-8** | Task 2 taxonomy alignment: add refund/quote/follow-up/new-project kinds + follow-up thread samples (keep 50+) | 8 | S | Dataset count by kind |
| **P2-9** | Task 1 API docs polish: examples, error-code table | 5 | S | Read-through |
| **P2-10** | Task 3 pointed clarifying-question generation per open requirement | 8 | S | pytest |

## REVISED DROP LIST (score-impact justified)

Per reviewer direction, the following are **NOT dropped** (scored requirements): tool calling in Tasks 2 & 3 (MCP wrapper optional), basic image captioning linked to the parent article and searchable, in-process daily scheduler + manual trigger + added/updated/removed diff, auto-send eligibility + demotion (simulated send acceptable).

**Dropping (with justification):**

| Item | Reason | Score risk |
|---|---|---|
| Heavy OCR / layout vision (full-page visual parsing, table reconstruction) | Brief only requires basic captioning + searchable image text; OCR pipelines consume large effort with little rubric weight. | Low — captioning + alt-text indexing covers the scored requirement. |
| External cron infrastructure (Windows Task Scheduler docs beyond a README note, celery/APScheduler, docker cron) | In-process daily loop (`daily_ingest.py`) + manual trigger satisfies "daily freshness"; adding schedulers violates "avoid infrastructure unless required". | Low — brief asks for repeatable daily ingestion, not a specific scheduler product. |
| Real email sending in Task 2 | Explicitly out of scope in requirements (IN-FR-05: sending only with explicit later authorization); simulated send satisfies the demo. | None — safer. |
| MCP protocol wrapper | Tool calling is required; the MCP wire protocol is not. A typed tool interface + tool-calling loop scores the same Design points with less risk. | Low. |
| Root-level docker-compose full stack | Windows + mixed Python/Node venvs make containerization high-effort/low-demo-value; a root `start-all.ps1` achieves the one-command goal. | Low — one-command startup is what's scored. |

---

*Phase 1 (v2) complete. No code was changed. Awaiting approval to begin Phase 2 at P0-1.*
