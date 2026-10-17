# Task 2: Inbox Agent (TypeScript / Node.js)

The Inbox Agent ingests customer-support emails, classifies each one, retrieves
**grounded** answers from the Task 1 Knowledge Brain, drafts replies with
citations, and enforces a human-review workflow with a durable audit trail and an
automation-eligibility safeguard. It is implemented in **TypeScript** on Node.js
(spec: `AI_Tech_Consultant_Project_Requirements.md`, Task 2).

> The agent **never sends email**. "Approved" means approved *in-app*; a human
> always remains in the loop.

## Architecture (short)

```
HTTP API (Fastify) ─▶ InboxAgent ─▶ Classifier ─▶ (rules | LLM)
                          │
                          ├─▶ KnowledgeBrainClient ─▶ Task 1 POST /ask  (grounding + citations)
                          ├─▶ DraftBuilder                              (reply + citations)
                          ├─▶ ReviewStateMachine                        (approve/edit/reject/escalate)
                          └─▶ Store (InMemory | Postgres)               (items, audit log, feedback, agent_state)
```

See `DESIGN.md` for the full design and `EVALS.md` for measured results.

## Setup

```bash
cd task2-inbox-agent
npm install
cp .env.example .env   # then edit values
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8080` | HTTP port |
| `LOG_LEVEL` | `info` | Log verbosity |
| `KNOWLEDGE_BRAIN_URL` | `http://localhost:8000` | Task 1 base URL |
| `KNOWLEDGE_BRAIN_TIMEOUT_MS` | `30000` | Timeout for `/ask` (raise for slow local models) |
| `KNOWLEDGE_BRAIN_RETRIES` | `2` | Retries for retryable KB failures |
| `CLASSIFIER` | `rules` | `rules` (deterministic, offline) or `llm` |
| `LLM_PROVIDER` | `openai_compatible` | `openai_compatible` or `anthropic` (LLM mode) |
| `LLM_MODEL` / `CHAT_MODEL` | `llama3.2:1b` | Chat model for LLM classification |
| `LLM_BASE_URL` / `CHAT_BASE_URL` | — | Base URL for the LLM provider |
| `LLM_API_KEY` / `ANTHROPIC_API_KEY` | — | Provider key (not required by Ollama) |
| `LLM_TIMEOUT_MS` | `60000` | LLM classification timeout |
| `LLM_RETRIES` | `1` | LLM retries |
| `MAX_CONSECUTIVE_UNEDITED_APPROVALS` | `20` | Threshold for automation **eligibility** (never auto-sends) |
| `DATABASE_URL` | — | Postgres DSN. If unset, an in-memory store is used (not durable) |
| `DATABASE_SCHEMA` | `inbox_agent` | Schema for this service's tables (isolated from Task 1) |
| `EMAIL_DATASET_PATH` | `datasets/emails-sample.json` | Demo dataset auto-loaded at startup |

Secrets are read from the environment only and never logged.

## Running

```bash
npm start          # ts-node src/server.ts (loads the dataset, migrates if DATABASE_URL set)
npm run build      # compile to dist/
```

Open `http://localhost:8080/` for the minimal review UI.

## HTTP API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Minimal web review UI |
| `GET` | `/health` | Liveness |
| `GET` | `/ready` | Readiness; reports KB reachability (`ready`/`degraded`) |
| `POST` | `/emails` | Ingest one email |
| `GET` | `/emails` | List emails (filter by state/category) |
| `GET` | `/emails/:id` | Fetch one item |
| `POST` | `/emails/:id/draft` | Classify + ground + draft (idempotent per item) |
| `POST` | `/emails/:id/review` | Apply `approve` / `edit` / `reject` / `escalate` |
| `GET` | `/emails/:id/audit` | Audit trail for an item |
| `GET` | `/feedback` | Reviewer feedback records |
| `GET` | `/stats` | Counts + automation-eligibility state |

Errors use `{"error":{"code","message","request_id"}}` with status `400`
validation, `404` not found, `409` invalid transition, `415` unsupported media
type, `502/504` upstream KB failures.

## Tests

```bash
npm test                 # unit + API (KB mocked); integrations skipped
npm run typecheck        # tsc --noEmit
```

Opt-in integrations (require running dependencies):

```powershell
# Postgres persistence (migrations idempotent, data survives across stores)
$env:TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:55432/knowledge_brain"
npx jest --runInBand tests/postgres.integration.test.ts

# Live Task 1 API contract
$env:TEST_KB_URL="http://localhost:8000"; $env:TEST_KB_TIMEOUT_MS="300000"
npx jest --runInBand tests/kb.integration.test.ts
```

## Evals

```bash
npm run evals                                   # rules classifier (default)
npm run evals -- --classifier=llm --no-dataset  # LLM classifier (needs an LLM)
```

Reports are written to `evals/report.json`, `evals/report-rules.json`, and
`evals/report-llm.json`. See `EVALS.md` for measured numbers.

## Dataset

`datasets/emails-sample.json` holds **71 synthetic** SupportFlow emails with
expected labels (category, urgency, risk flags, answerability, escalation). All
data is synthetic; no real customer data is used.

## Safety properties

- **Grounding only**: product claims require Task 1 citations; abstentions become
  safe clarification/escalation drafts (never invented answers).
- **KB failure is visible**: if Task 1 is unreachable or abstains, the agent
  produces a degraded *escalation* draft (no citations) and records a
  `draft_generation_degraded` audit event — it does not silently fabricate.
- **No auto-send**: 20 consecutive unedited approvals only flip a policy flag
  (`automationEligible`); a human still approves every reply.
- **Untrusted input**: email bodies are treated as untrusted; the classifier and
  drafter never execute instructions found in email content.
- **Durable audit**: every ingest, draft, review action, feedback, and counter
  change is appended to an audit log.
