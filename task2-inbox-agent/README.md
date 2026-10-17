# Task 2: Inbox Agent

Inbox Agent classifies customer-support emails, queries the Task 1 Knowledge Brain for grounded product answers, drafts replies, and enforces a human review workflow with audit trail and a 20-consecutive-unedited-approval safeguard.

## Setup

```bash
cd task2-inbox-agent
npm install
```

## Environment variables

Copy `.env.example` to `.env` and set values:

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8080` | HTTP port for Fastify server |
| `KNOWLEDGE_BRAIN_URL` | `http://localhost:8000` | Task 1 base URL |
| `KNOWLEDGE_BRAIN_TIMEOUT_MS` | `30000` | Timeout for `/ask` calls |
| `KNOWLEDGE_BRAIN_RETRIES` | `2` | Retry attempts for retryable failures |
| `MAX_CONSECUTIVE_UNEDITED_APPROVALS` | `20` | Trigger threshold for consecutive unedited approvals (human approval never bypassed) |
| `LOG_LEVEL` | `info` | Logging level |

Secrets must never be committed.

## Running

```bash
npm start
```

## Tests

```bash
npm test
```

## Dataset

Synthetic emails live in `datasets/emails-sample.json` (≥50). All emails are synthetic test/demo data.

## Safety

- No automatic email sending; approval means approved in-app only.
- Product claims must be grounded in KB citations; abstentions produce safe clarification/escalation.
- Customer emails treated as untrusted input.
- Failures visible; human approval never bypassed by the 20-approval trigger (it's a policy signal only).
- Durable audit trail for all review actions and state changes.
