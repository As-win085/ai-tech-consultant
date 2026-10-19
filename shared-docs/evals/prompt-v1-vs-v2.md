# Prompt v1 vs v2 — tuning-split measurement

**Date:** 2026-10-19. **Split:** tuning only (holdout untouched). **Model:** `qwen/qwen3.8-27b`
via Groq's OpenAI-compatible API (cheap, non-reasoning, honours JSON instructions).

- OpenRouter was unusable (account balance exhausted, HTTP 402) and the Gemini free tier was
  exhausted for the day (chat and `embed_content` quotas), so Groq was used for all chat calls.
- Task 1 retrieval needed embeddings, and the Gemini embedding quota
  (`EmbedContentRequestsPerDayPerProjectPerModel-FreeTier`, resets in ~18 h) was exhausted mid-run.
  Both Task 1 runs therefore indexed the sample corpus with a **local `BAAI/bge-base-en-v1.5`
  (768d)** embedding server, identical for v1 and v2, so the v1-vs-v2 delta is still comparable.
  Production stays on `gemini-embedding-001`; re-run Task 1 with Gemini once the quota resets.
- Groq's per-model limit is **1000 output tokens/minute**, so runs were paced (Task 1 ~15 s,
  Task 2 ~9 s, Task 3 ~7 s per call).

## Results (tuning split)

| Task | Prompt | v1 | v2 | Winner |
| --- | --- | --- | --- | --- |
| 1 | `answer_system` | 18/20 passed (fails `social-03`, `unanswerable-01`) | **19/20 passed** (fails `social-03`) | **v2** |
| 2 | `classifier_system` | category 0.861, urgency 0.633, macro-F1 0.839, escalation recall 0.848 / precision 0.875 | **category 0.899, urgency 0.759, macro-F1 0.883**, escalation recall 0.758 / precision 0.862 | v1 kept (see below) |
| 3 | `extraction_system` | 14/14 passed | 14/14 passed | tie — v1 kept |

Task 2 drafts 4/4, safety 4/4, review 6/6 on both versions. All Task 2 pass thresholds still hold
for v2 (category ≥ 0.60, escalation recall ≥ 0.70), but v2 trades ~9 points of escalation recall
for better category/urgency accuracy. For an inbox triage agent a missed escalation is the more
costly error, so **v1 stays active** until a prompt can raise urgency accuracy without lowering
escalation recall.

## Decision

- `task1-knowledge-brain/prompts/active.json` → `{"answer_system": 2}` (v2 fixes the abstention
  case `unanswerable-01` and keeps the injection refusal).
- `task2-inbox-agent/prompts/active.json` → `{"classifier_system": 1}` (v2 measured, not promoted).
- `task3-meeting-to-scope/prompts/active.json` → `{"extraction_system": 1}` (v2's duplicate-segment
  rule targets a failure only observed under Claude Haiku; qwen passes both).

## Rollback

One line: set the version back in the task's `prompts/active.json`, e.g.

```json
{"answer_system": 1}
```

No code change, no redeploy of prompt text — the loader reads the manifest at import.

## Reports

- `task1-tuning-prompt-v{1,2}-qwen3.8-27b.json`
- `task2-tuning-prompt-v{1,2}-qwen3.8-27b.json`
- `task3-tuning-prompt-v{1,2}-qwen3.8-27b.json`

Each report records `prompt.name`, `prompt.version` and `prompt.sha256`, so a result is tied to
the exact prompt bytes that produced it.
