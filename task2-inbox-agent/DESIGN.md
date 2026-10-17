# Inbox Agent — Design (Task 2)

## 1. Purpose and context

The Inbox Agent automates the *first pass* of customer-support email handling:
classify an email, retrieve a grounded answer from the **Task 1 Knowledge Brain**,
draft a cited reply, and route it through a **human review** workflow with an
audit trail. It is a separate service (TypeScript/Node.js) that talks to Task 1
only over its HTTP API — it never re-implements retrieval.

Non-goals: sending email, auto-replying without human approval, or answering from
model memory. Every product claim in a draft must trace to a Task 1 citation.

## 2. Architecture

```
                 ┌──────────────────────────────────────────────┐
   HTTP clients  │  Fastify API  (src/server.ts)                 │
   (UI / curl) ─▶│  /emails /emails/:id/draft /emails/:id/review │
                 │  /audit /feedback /stats /health /ready /      │
                 └───────────────┬──────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │  InboxAgent (agent.ts)  │  orchestration + audit
                    └───┬───────┬─────────┬───┘
        classify        │       │ ground  │ persist
                        ▼       ▼         ▼
             ┌──────────────┐ ┌────────────────────┐ ┌───────────────────┐
             │ Classifier   │ │ KnowledgeBrainClient│ │ Store             │
             │ rules | llm  │ │ → Task 1 POST /ask  │ │ InMemory|Postgres │
             └──────────────┘ └────────────────────┘ └───────────────────┘
                        │                                     │
                        ▼                                     ▼
                 DraftBuilder (draft.ts)            items · audit_log ·
                 ReviewStateMachine (review.ts)     feedback · agent_state
```

`factory.ts` wires the concrete implementations from `config.ts`
(`createAgentBundle`): it selects the classifier (`rules`/`llm`), builds the
`Store` (`InMemoryStore` when `DATABASE_URL` is unset, else `PostgresStore`), and
constructs the `KnowledgeBrainClient`.

## 3. Module map

| File | Responsibility |
|---|---|
| `src/types.ts` | Domain types + enumerated constants (`CATEGORIES`, `URGENCIES`, `RISK_FLAGS`, `REVIEW_STATES`, `REVIEW_ACTIONS`) |
| `src/schemas.ts` | Zod validators for HTTP bodies, the knowledge-brain response, and the dataset |
| `src/config.ts` | Environment configuration + defaults; `loadConfig(overrides?)` |
| `src/classifier.ts` | `RuleBasedClassifier`, `LlmClassifier`, `buildClassifier`, `normalizeClassificationJson` |
| `src/kbClient.ts` | `KbClient` interface + `KnowledgeBrainClient` (HTTP, timeout, retries) + `KnowledgeBrainError` |
| `src/draft.ts` | `buildDraft(email, kbAnswer)` → grounded or safe clarification/escalation draft |
| `src/review.ts` | `applyReviewAction` state machine, `evaluateAutomationExclusion`, `InvalidTransitionError` |
| `src/store.ts` | `Store` interface + `InMemoryStore` + `defaultAgentState` |
| `src/postgresStore.ts` | `PostgresStore` + embedded versioned `buildMigrations()` |
| `src/agent.ts` | `InboxAgent` orchestration (ingest, draft, review, audit, automation counter) |
| `src/factory.ts` | `createAgentBundle`, `buildStore` |
| `src/server.ts` | Fastify routes, error handler, `start()` (load dataset) |
| `src/ui.ts` | Minimal review UI (`reviewUiHtml`) |
| `src/index.ts` | Public exports |

## 4. Domain model

- **Email** — `id, from, to[], subject, body, receivedAt, threadId`.
- **Classification** — `category, urgency, riskFlags[]|ambiguity, confidence,
  needsEscalation, rationale, classifier, fallback`.
  - `category ∈ {product_howto, troubleshooting, billing_account,
    feature_request, complaint, unsupported_unclear}`.
  - `urgency ∈ {low, medium, high, urgent}`.
  - `riskFlags ⊆ {account_security, billing_refund, legal_threat,
    prompt_injection, pii_exposure, out_of_scope, mass_spam}`.
  - `ambiguity ∈ {clear, ambiguous}`.
- **Draft** — `id, emailId, body, grounded, citations[], confirmedFacts[],
  assumptions[], escalationReason, kbRequestId, kbEvidenceStatus,
  kbNeedsEscalation, createdAt`.
- **InboxItem** — `id, email, expected?, classification, originalDraft, draft,
  state, automationExcluded, automationExclusionReasons[], reviewHistory[],
  metadata, createdAt, updatedAt`.
- **AuditEntry** — `id, itemId|null, event, at, details`.
- **FeedbackRecord** — `id, itemId, draftId, outcome, reason, edited,
  reviewerId|null, at, category`.
- **AgentState** — `consecutiveUneditedApprovals, automationEligible,
  automationThresholdReachedAt`.

## 5. Classification

`buildClassifier(config)` returns either a **deterministic** rule-based classifier
(default) or an **LLM** classifier.

- **RuleBasedClassifier** — offline, deterministic, keyword/heuristic scoring over
  the subject+body. It sets `ambiguity` when the ask is very short
  (`≤ 4 words`) or lacks actionable content, derives risk flags (security,
  refund, legal threats, PII, prompt-injection phrases, mass-email, out-of-scope),
  and marks `needsEscalation` for high-risk/unclear items.
- **LlmClassifier** — calls an OpenAI-compatible or Anthropic chat endpoint with a
  strict JSON prompt, then runs `normalizeClassificationJson` to coerce common
  model quirks (unknown enum values, empty-string array entries, missing fields)
  into the domain schema. On unrecoverable failure it throws (safe-fail), so a
  broken LLM never silently produces garbage labels.

Both implement the same `Classifier` interface, so the engine is pluggable and the
rest of the system is unchanged.

## 6. Grounding and drafting

`InboxAgent.generateDraft` sends `Subject + body` to the Knowledge Brain and maps
the response through `buildDraft`:

- **Grounded** when `evidence_status === 'sufficient'` *and* there is at least one
  citation → the draft states only the KB answer and keeps the citations.
- **Safe clarification/escalation** otherwise → the draft asks a clarifying
  question, sets `escalationReason`, and carries **no** invented facts.
- **KB unavailable / timeout / malformed** (`KnowledgeBrainError`) → the agent
  synthesizes a degraded escalation *response* so the workflow can still continue,
  records `metadata.kbError`, sets `escalationReason`, and writes a
  `draft_generation_degraded` audit event. (Requirement IN-FR-03: never invent an
  answer when Task 1 is unavailable.) Any *non-KB* error is **not** swallowed — it
  propagates to a 500 so failures stay visible.

## 7. Review workflow

State machine (`applyReviewAction`):

```
pending_review ──approve──▶ approved
      │        ──edit────▶ edited_and_approved
      │        ──reject──▶ rejected
      └──────────escalate▶ escalated
(approved / edited_and_approved / rejected / escalated are terminal)
```

Illegal transitions (e.g. re-reviewing a terminal item) throw
`InvalidTransitionError` → HTTP `409 invalid_transition`. Every action appends a
`reviewHistory` entry and an audit event, and creates a `FeedbackRecord`
(`outcome ∈ {approved_without_edit, edited, rejected, escalated}`). An `edit`
requires a non-empty `editedDraft`.

## 8. Automation-eligibility safeguard

The requirement is to *detect* when a reviewer has approved many drafts without
changes. The agent keeps a **global** counter `consecutiveUneditedApprovals` in
`AgentState`:

- Increments **only** for an approval of a **grounded, non-excluded** draft with
  no edit.
- Resets to 0 on any edit/reject/escalate, on an excluded item, or when the draft
  lacks adequate evidence.
- At the threshold (`MAX_CONSECUTIVE_UNEDITED_APPROVALS`, default 20) it sets
  `automationEligible = true` and records `automation_eligible_threshold_reached`.

`automationEligible` is a **policy signal only** — it never sends email and never
bypasses human review. Eligibility is deliberately excluded (`evaluateAutomationExclusion`)
for: any risk flag, `billing_account`/`complaint`/`unsupported_unclear`
categories, ambiguous asks, low confidence (`< 0.6`), classification-escalated
items, missing draft, ungrounded drafts, drafts without citations, or drafts whose
KB evidence was not `sufficient`.

## 9. Persistence

`Store` abstracts persistence: `InMemoryStore` (dev/tests, non-durable) and
`PostgresStore`. `PostgresStore` uses an **isolated schema** (`DATABASE_SCHEMA`,
default `inbox_agent`; tests use `inbox_agent_test`) so it cannot collide with
Task 1's tables, and applies embedded, versioned migrations tracked in
`schema_migrations`:

- `inbox_items` — one row per item (email, classification, draft, state as JSONB).
- `audit_log` — append-only audit events.
- `feedback` — reviewer feedback records.
- `agent_state` — single-row automation counter/eligibility.

Migrations are idempotent (verified by the opt-in integration test, which also
proves state survives across separate store instances).

## 10. HTTP API and error handling

Routes are listed in `README.md`. The central error handler maps domain failures
to stable codes:

| Condition | Status | `error.code` |
|---|---|---|
| Zod validation failure | 400 | `validation_error` |
| Missing/invalid field / unsupported media type | 400 / 415 | `invalid_request` / `bad_request` |
| Unknown item | 404 | `not_found` |
| Illegal review transition | 409 | `invalid_transition` |
| KB HTTP error | 502 | `knowledge_brain_http` |
| KB timeout | 504 | `knowledge_brain_timeout` |

`/ready` reports `status: ready|degraded` with `knowledgeBrain.reachable`; it
returns 200 in both cases (the service still operates in degraded mode) but never
claims readiness when the KB is unreachable. Errors are logged with the request id
on 5xx.

## 11. Configuration

All configuration is environment-driven (`config.ts`); see the README table.
Defaults are safe for local development (rules classifier, in-memory store,
localhost Task 1). No secret is logged.

## 12. Testing and evaluation

- **Unit/API tests** (`tests/*.test.ts`, KB mocked): classifier behavior, KB client
  error mapping, review state machine + exclusions, agent orchestration/degradation,
  HTTP routes/error codes, safety (no fabrication), and dataset integrity.
- **Opt-in integrations**: `postgres.integration.test.ts` (real Postgres) and
  `kb.integration.test.ts` (real Task 1 `/ask`).
- **Evals** (`evals/runEvals.ts`): classification metrics (category accuracy,
  urgency accuracy, macro-F1, escalation recall/precision) over labeled cases plus
  draft/safety/review suites, with thresholds. See `EVALS.md`.

## 13. Known limitations

- The default **rules** classifier is keyword/heuristic; it is deterministic and
  offline but has imperfect category/urgency accuracy (see `EVALS.md`).
- The local **1B** LLM used in evaluation is far weaker than the rules baseline
  and unsuitable for production classification; a larger hosted model is required
  for `CLASSIFIER=llm`.
- Local Ollama `/ask` latency (≈2 min) motivates the configurable KB timeout; with
  a fast provider the default 30 s is ample.
- The review UI is intentionally minimal (single-page fetch/JSON API consumer).
