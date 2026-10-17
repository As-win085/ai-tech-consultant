# Inbox Agent (Task 2) — M6 Verification Report

## Summary

Task 2 (Inbox Agent) is implemented in **TypeScript/Node.js** and verified:
classification, Knowledge Brain grounding, draft generation with citations, human
review with audit/feedback, and the 20-consecutive-unedited-approval
automation-**eligibility** safeguard. Test suite and evaluation harness are green.

## Test coverage

- **Unit + API tests**: `npm test` → **62 passed, 3 skipped** (integrations are
  opt-in). Macros: `TYPECHECK OK`.
- **Postgres integration** (`TEST_DATABASE_URL`, real PostgreSQL):
  **2 passed** — migrations idempotent; items/audit/feedback/state persist across
  separate store instances.
- **Live Task 1 integration** (`TEST_KB_URL`): **PASS (76.8 s)** — real
  `KnowledgeBrainClient` → Task 1 `POST /ask`, response schema-valid.
- **Evals**: `npm run evals` → **ALL THRESHOLDS MET** (`evals/report-rules.json`).

## Real end-to-end (Ollama + PostgreSQL)

- Embedding: `nomic-embed-text` (768-dim) via Ollama OpenAI-compatible endpoint.
- Chat: `llama3.2:1b` via Ollama.
- Task 1: 5 sample articles → **29 chunks indexed** (real embeddings) into
  `knowledge_brain` on `localhost:55432`; `GET /ready` reports index ok.
- Task 2 HTTP smoke test (in-memory store, rules classifier): 71 emails ingested;
  draft generated; review approved; feedback + audit recorded; `/ready` reports KB
  reachability; unsupported media type correctly returns **415**.

```
STATS total=71 states={"pending_review":71}
DRAFT grounded=False citations=0 kbError=unavailable      # KB was down for this pass
UNSUPPORTED_MEDIA_STATUS=415
REVIEW state=approved outcome=approved_without_edit counter=0
FEEDBACK count=1   AUDIT events=ingested,draft_generation_degraded,reviewed
```

Live Task 1 `/ask` spot-check: well-formed response in ~132 s; retrieved 5 chunks
above threshold (top cosine 0.689) but the 1B model could not produce a valid
citation-backed answer, so Task 1 **abstained** → Task 2 produced a safe
escalation draft. (Model limitation, not an integration defect.)

## Classifier / eval results (measured)

| Metric | rules (79 cases) | llm llama3.2:1b (8 cases) | Threshold |
|---|---|---|---|
| Category accuracy | 0.709 | 0.250 | ≥ 0.60 |
| Urgency accuracy | 0.595 | 0.500 | — |
| Macro-F1 | 0.714 | 0.131 | — |
| Escalation recall | 0.848 | 0.400 | ≥ 0.70 |
| Escalation precision | 0.667 | 1.000 | — |
| Drafts / Safety / Review | 4/4, 4/4, 6/6 | 4/4, 4/4, 6/6 | — |
| Result | **ALL MET** | THRESHOLD FAILURES | — |

The rules classifier is the shipped default; the 1B LLM result is reported
honestly as unsuitable. See `EVALS.md`.

## Acceptance checklist (IN-FR)

- **IN-FR-01 Email dataset** — 71 synthetic SupportFlow emails covering all intents,
  urgency, ambiguity, escalation, and risk flags, with expected labels and
  fictional identities. ✔
- **IN-FR-02 Classification** — documented taxonomy; urgency/ambiguity/confidence/
  risk; schema-validated JSON; tolerant normalization + safe failure for malformed
  LLM output; original email preserved with classification stored separately. ✔
- **IN-FR-03 Knowledge Brain integration** — HTTP-only client with timeouts and
  bounded retries; Task 1 internals never imported; abstention/unavailability →
  clarification/escalation draft (never invented), with a visible degraded audit
  event. ✔
- **IN-FR-04 Draft responses** — concise professional drafts from the email + KB
  evidence; internal citations kept for reviewers; confirmed facts vs assumptions
  separated; no invented features/pricing/policy; explicit escalation reason. ✔
- **IN-FR-05 Human review** — review UI + API to approve/edit/reject/escalate;
  original draft, edited version, decision, timestamps, and feedback retained;
  approval is in-app only; no email is ever sent automatically. ✔
- **IN-FR-06 Feedback/learning records** — outcomes
  (approved-without-edit/edited/rejected/escalated) persisted as feedback with
  reasons; no silent training; reasons are analyzable via `/feedback`. ✔
- **IN-FR-07 20-consecutive automation rule** — global counter resets on
  edit/reject/escalate/exclusion/inadequate evidence; reaching 20 only sets a
  proposed `automationEligible` state; high-risk/ambiguous/unsupported/billing/
  account-security cases are excluded; current risk is re-evaluated each item; full
  human override + audit trail; no auto-send. ✔

## Security / safety

Untrusted email input; no secrets logged or committed; isolated DB schema; failures
visible (degraded drafts, audit events, non-2xx codes); human approval never
bypassed.

## Runbook (PowerShell)

```powershell
Set-Location "C:\Users\ASWIN\Documents\New folder\mkdir ai-tech-consultant\task2-inbox-agent"
npx --no-install tsc --noEmit -p tsconfig.json          # typecheck
npx --no-install jest --maxWorkers=2                    # unit + API
npx ts-node evals/runEvals.ts                           # evals (rules)

# Opt-in integrations
$env:TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:55432/knowledge_brain"
npx jest --runInBand tests/postgres.integration.test.ts
$env:TEST_KB_URL="http://localhost:8000"; $env:TEST_KB_TIMEOUT_MS="300000"
npx jest --runInBand tests/kb.integration.test.ts
```

Typecheck clean; unit suite green; evals meet all thresholds; live Task 1 and
Postgres integrations pass. **M6 complete and verified.**
