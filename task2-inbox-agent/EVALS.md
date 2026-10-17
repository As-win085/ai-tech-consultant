# Inbox Agent — Evaluation (Task 2)

All numbers below are **measured**, produced by `evals/runEvals.ts`. Raw reports
are written to `evals/report.json`, `evals/report-rules.json`, and
`evals/report-llm.json`.

## 1. Method

- **Classification corpus (79 cases)** = 71 labeled synthetic emails
  (`datasets/emails-sample.json`) + 8 hand-written edge cases in
  `evals/cases.json`. Metrics compare predicted labels against expected labels.
- **Draft / Safety / Review suites** are behavioral cases in `evals/cases.json`.
- **Thresholds** gate a pass:

  | Metric | Threshold |
  |---|---|
  | `categoryAccuracy` | ≥ 0.60 |
  | `escalationRecall` | ≥ 0.70 |
  | `groundednessAccuracy` | ≥ 0.90 |
  | `safetyNoFabrication` | ≥ 1.00 |
  | `reviewCorrectness` | ≥ 1.00 |

### Dataset composition (71 emails)

| Category | # | | Urgency | # | | Answerability | # | | Risk flag | # |
|---|---|---|---|---|---|---|---|---|---|---|
| product_howto | 12 | | low | 30 | | answerable | 33 | | account_security | 5 |
| troubleshooting | 13 | | medium | 17 | | ambiguous | 21 | | billing_refund | 6 |
| billing_account | 15 | | high | 17 | | unanswerable | 17 | | legal_threat | 5 |
| feature_request | 6 | | urgent | 7 | | | | | prompt_injection | 3 |
| complaint | 8 | | | | | | | | out_of_scope | 3 |
| unsupported_unclear | 17 | | | | | | | | mass_spam | 3 |
| | | | | | | | | | pii_exposure | 3 |

Escalation expected on **28/71** emails.

### Commands

```bash
npm run evals                                   # rules classifier (default)
npm run evals -- --classifier=llm --no-dataset  # LLM classifier
```

## 2. Classifier comparison — rules vs LLM

Rules = deterministic keyword/heuristic classifier (offline).
LLM = `llama3.2:1b` served by local Ollama (OpenAI-compatible endpoint).

| Metric | **rules** (79 cases) | **llm** (8 cases) | Threshold |
|---|---|---|---|
| Category accuracy | **0.709** | 0.250 | ≥ 0.60 |
| Urgency accuracy | 0.595 | 0.500 | — |
| Macro-F1 (category) | 0.714 | 0.131 | — |
| Escalation recall | **0.848** | 0.400 | ≥ 0.70 |
| Escalation precision | 0.667 | 1.000 | — |
| **Result** | **ALL THRESHOLDS MET** | THRESHOLD FAILURES | — |

Draft / Safety / Review suites were identical for both (they exercise
deterministic logic, not the classifier): **drafts 4/4, safety 4/4, review 6/6**.

### Interpretation (honest)

- The **rules classifier meets every threshold** and is the shipped default. Its
  weakness is **urgency** (0.595): keyword cues for "medium vs high" are noisy.
- The **1B local LLM is materially worse** (category 0.25, macro-F1 0.131) and
  **fails** the category-accuracy and escalation-recall gates. It still scores
  precision 1.0 on escalation (when it escalates it is right), but it escalates
  too rarely. This is an expected capability limit of a 1B model, not an
  integration defect — the classifier is pluggable, and a larger hosted model or a
  fine-tuned small model would be required for production `CLASSIFIER=llm`.
- The LLM run used only the 8 hand-written cases (`--no-dataset`) to bound the
  ~2-min/call latency; it is a representative spot-check, not a full-corpus score.

## 3. Behavioral suites (deterministic)

| Suite | Cases | Passing | What it proves |
|---|---|---|---|
| Drafts | 4 | 4 | grounded / abstain / conflicting / no-citation drafts are correct and safe |
| Safety | 4 | 4 | KB timeout / unavailable / malformed and LLM malformed never fabricate a product claim; degraded drafts escalate |
| Review | 6 | 6 | approve / edit / reject / escalate transitions + terminal-state block + billing exclusion behave exactly as specified |

`safetyNoFabrication = 1.0` and `reviewCorrectness = 1.0`.

## 4. Test suites (not evals)

- **Unit + API**: `npm test` → **62 passed, 3 skipped** (integrations opt-in).
- **Postgres integration** (`TEST_DATABASE_URL`): **2 passed** — migrations are
  idempotent and data persists across separate store instances.
- **Live Task 1 integration** (`TEST_KB_URL`): **PASS (76.8 s)** — the
  `KnowledgeBrainClient` reached the real Task 1 `/ask` and the response passed
  schema validation.
- **Live `/ask` spot-check**: a real Task 1 `/ask` returned a well-formed response
  in ~132 s; it retrieved 5 chunks above the score threshold (top cosine 0.689)
  but the 1B chat model could not produce a valid citation-backed answer, so Task 1
  **abstained**. The agent then produced a safe escalation draft and recorded the
  outcome. This demonstrates the intended end-to-end safety behavior when upstream
  grounding is weak.

## 5. Known limitations

- Rules classifier urgency accuracy (0.595) is below the category accuracy; treat
  urgency as a hint, not ground truth.
- The 79-case corpus is synthetic and small; it is a sanity/direction check, not a
  statistically robust benchmark.
- The LLM comparison covers 8 cases on a 1B model; it is indicative only.
- Local Ollama latency (≈2 min/`/ask`) limits large live end-to-end runs.

## 6. Reproduction note

Reports include `generatedAt`, `host.node`, and `classifier` for provenance. The
rules report (`evals/report-rules.json`) is the authoritative threshold result:
**`"passed": true`** (all five gates).
