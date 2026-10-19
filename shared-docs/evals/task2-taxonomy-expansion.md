# Task 2 taxonomy expansion (P0-5)

## New taxonomy (`src/types.ts:1`)

`product_howto, troubleshooting, billing_account, refund, feature_request, quote, new_project, complaint, follow_up, unsupported_unclear`

Adds the four requested intents (`refund`, `quote`, `new_project`, `follow_up`) while keeping every pre-existing label.

## Mechanical holdout label mapping (`datasets/holdout-20.json`)

Rule applied to the frozen 20-case file: `billing_account -> refund` when the case text mentions refund/cancel/duplicate charge; every other old label is identity-mapped. The mapping is stored in the file under `taxonomy_mapping` and each case keeps `prior_category`.

| id | old | new |
|---|---|---|
| email-05 | billing_account | refund |
| email-06 | billing_account | refund |
| email-19 | billing_account | refund |

email-13 ("Suspicious login") stays `billing_account` (no refund/cancel wording). The other 16 cases are unchanged. File version is now `2026-10-19-v2-taxonomy`.

## Always-human-review policy (`src/review.ts`)

`ALWAYS_REVIEW_CATEGORIES = billing_account, refund, quote, new_project, complaint, unsupported_unclear`. Any classification in these categories is excluded from autonomous sending regardless of how many clean approvals preceded it. `follow_up` is deliberately not in the set (it stays automatable).

## Per-category 20-consecutive counter (`src/agent.ts`, `src/types.ts`)

`AgentState.categories` holds an independent `{consecutiveUneditedApprovals, automationEligible, automationThresholdReachedAt}` per category. A category becomes automation-eligible only when it reaches `MAX_CONSECUTIVE_UNEDITED_APPROVALS` (20) of its own `approved_without_edit` outcomes. The counter resets on `edit`, `reject`, `escalate`, draft-generation failure (excluded items) and on a failed approval; activity in one category never resets another. Always-review categories are hard-blocked from ever reaching eligibility. The top-level `consecutiveUneditedApprovals` / `automationEligible` fields mirror the category of the most recent review action for API/UI backward compatibility.

## Prompt v3 (`prompts/classifier_system.v3.md`)

Built on the conservative v1 wording (v2 lost escalation recall) with the 10-bullet taxonomy and one added line about human-reviewed categories. Active manifest is `classifier_system: 3`. sha256 `b5022c4e8915fdca9ba87726e7282405c32c2a47c51ed4593bcf67c0ee90e057`. Rollback is the usual one-line manifest edit.

## Tuning split

Eight synthetic tuning emails (`e072`-`e079`) added to `datasets/emails-sample.json` covering the four new categories. No holdout content was used while tuning. Rules-baseline tuning run: 87 cases, category accuracy 0.655, macro-F1 0.735, escalation P 0.708 / R 0.872; drafts 4/4, safety 4/4, review 6/6; all thresholds met.

## Frozen holdout, run once per model (Groq)

| model | category acc | macro-F1 | urgency acc | escalation P / R | median / p95 ms | cost USD | failures / retries |
|---|---:|---:|---:|---:|---:|---:|---:|
| qwen/qwen3.8-27b (strong) | 0.70 | 0.699 | 0.60 | 1.00 / 0.75 | 15006 / 15176 | 0.009278 | 0 / 0 |
| allam-2-7b (low-cost) | 0.45 | 0.541 | 0.60 | 0.688 / 0.917 | 15002 / 15027 | 0.000000 | 2 / 0 |
| RuleBasedClassifier | 0.75 | 0.691 | 0.75 | 0.857 / 1.00 | 2 / 6 | — | 0 / 0 |

Raw reports (per-case classifications, raw model responses, attempts, token usage, retries, failures, latency): `evals/reports/holdout-20-qwen_qwen3.8-27b.json`, `holdout-20-allam-2-7b.json`, `holdout-20-rules-mock.json`, `comparison-holdout-20.json`.

Notes: Gemini and OpenRouter keys are exhausted, so both models ran on Groq; latency is dominated by the 15s pacing needed to stay under Groq's 1000 output-token/min limit, so it is not a clean speed comparison. Costs come from the Groq rates in `shared-docs/evals/pricing.json` ($0.80/$4.00 for qwen3.8-27b, $0/$0 for allam-2-7b). On this 20-case synthetic set the deterministic rules baseline still edges out both models, so the rules path remains the production default for triage classification.
