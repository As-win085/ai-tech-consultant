# Inbox Agent — AI Usage Log (Task 2)

A short, honest record of how AI tooling was used while building Task 2 and what
was human-decided or human-verified.

## Approach

Development was AI-assisted (an agentic coding assistant) with human direction for
scope and key decisions. Decisions delegated to the human and recorded before
implementation:

1. **Language** — TypeScript/Node.js (as specified for Task 2).
2. **Classifier** — pluggable: deterministic rules by default, optional LLM.
3. **Persistence** — PostgreSQL now, in a **separate schema** from Task 1.
4. **Interfaces** — HTTP API plus a minimal web review UI.

## What the assistant produced

- TypeScript implementation (`src/`): classifier, KB client, draft builder, review
  state machine, in-memory + Postgres stores, agent orchestration, Fastify server,
  minimal UI.
- Tests (`tests/`) and an evaluation harness (`evals/`) with thresholds.
- A synthetic dataset (`datasets/emails-sample.json`, 71 emails).
- Documentation (`README.md`, `DESIGN.md`, `EVALS.md`, `M6_VERIFICATION_REPORT.md`).

## Human verification / corrections that mattered

- **TypeScript version**: an initial pin to TS 7 was incompatible with ts-jest 29;
  downgraded to TS 5.9 so the toolchain was valid.
- **Unknown-LLM output**: the 1B model emitted near-miss keys (e.g.
  `"riskFlags":[""]`); tolerant normalization was added rather than trusting model
  output blindly.
- **Classifier tuning**: the ambiguity heuristic was tightened (`≤ 4` words) after
  it mis-flagged short how-to questions.
- **Safe failure on KB outage**: an early version failed the request (or risked an
  ungrounded answer) when Task 1 was down; changed to a **degraded escalation
  draft** plus a visible audit event (requirement IN-FR-03).
- **Real smoke test caught a bug**: a failed `Invoke-RestMethod` revealed that
  Fastify's own 4xx errors (e.g. unsupported media type) were being mapped to 500;
  the error handler was fixed to honor `statusCode`, with a regression test added.
- **Model limitations recorded, not hidden**: the local 1B LLM scored far below the
  rules baseline; both results are reported in `EVALS.md` rather than only the
  favorable one.

## Principles followed

- Task 2 calls Task 1 over HTTP; retrieval is never re-implemented.
- Failures are surfaced (degraded drafts, audit events, non-2xx codes) — never
  faked as success.
- No secrets, generated artifacts, or customer data are committed; all emails are
  synthetic.
- Human approval is never bypassed; the 20-approval trigger is policy signal only.
