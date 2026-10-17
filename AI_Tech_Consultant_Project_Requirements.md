# AI Tech Consultant — Project Requirements

**Document type:** Functional and Technical Requirements
**Version:** 1.0
**Status:** Baseline for implementation
**Purpose:** This document is the source of truth for the coding agent and project contributors. Follow it before adding features. Preserve existing working code unless a change is necessary and justified.

## 1. Product Vision

Build an AI-powered consultant that helps a service business handle three connected workflows:

1. **Knowledge Brain:** Answer questions using the Brilliant Directories support knowledge base, with verifiable citations and safe abstention when evidence is insufficient.
2. **Inbox Agent:** Classify customer emails, use the Knowledge Brain to draft grounded responses, and require human approval until a carefully defined quality threshold is met.
3. **Meeting-to-Scope:** Convert meeting transcripts into structured requirements, feasibility assessments, a statement of work (SOW), task estimates, and a proposal while tracking changes against an approved baseline.

The system is a human-supervised business automation product, not an autonomous system that can make consequential customer or commercial commitments without safeguards.

## 2. Project Principles and Non-Negotiable Rules

The coding agent MUST:

- Read this document and inspect the current repository before making changes.
- Preserve existing working code and data. Do not overwrite, delete, or reorganize files without a clear reason.
- Make small, testable changes. Run relevant tests after each meaningful change.
- Keep secrets out of source control, logs, sample data, and generated reports.
- Use the Knowledge Brain API as the shared knowledge interface. Task 2 and Task 3 MUST call this API rather than copy its crawler, retrieval, or answer-generation implementation.
- Distinguish source-grounded facts from model-generated suggestions and assumptions.
- Provide source references for claims derived from support content.
- Abstain, ask a clarifying question, or escalate when evidence is insufficient or conflicting.
- Keep humans in control of outbound email, scope approval, and any action that could create a commitment.
- Make failures visible and recoverable. Do not silently convert errors into successful results.
- Avoid adding infrastructure or dependencies unless they support an explicit requirement.
- Document significant architecture, prompt, model, schema, and workflow changes.
- Never claim a feature is complete unless it is implemented and verified by tests or a documented manual check.

## 3. Repository and Service Boundaries

The existing repository contains:

- `task1-knowledge-brain/` — Python knowledge ingestion, indexing, and question-answering API.
- `task2-inbox-agent/` — TypeScript/Node.js email triage and response-drafting workflow.
- `task3-meeting-to-scope/` — Python meeting transcript analysis and scope/proposal workflow.
- `shared-docs/` — shared contracts, project documentation, schemas, prompts, and evaluation assets.

Before creating or renaming paths, inspect the actual repository. Keep the current layout unless a documented decision requires a change.

### Service ownership

- **Task 1 owns:** support sitemap crawling, article extraction, normalization, chunking, embeddings, retrieval, grounded answer generation, citations, abstention, and knowledge freshness.
- **Task 2 owns:** email ingestion/fixtures, classification, urgency/risk labels, Knowledge Brain API client, draft generation, human review, edits/rejections, feedback tracking, and automation eligibility.
- **Task 3 owns:** transcript ingestion, requirement extraction, source/time references, clarification tracking, feasibility checks through Task 1, SOW/proposal generation, estimates, baseline comparison, and approval.
- **Shared docs own:** cross-service API contracts, common terminology, test/evaluation cases, setup instructions, and architecture decisions.

## 4. Functional Requirements

### 4.1 Task 1 — Knowledge Brain

#### KB-FR-01: Source ingestion

- Read https://support.brilliantdirectories.com/support/sitemap.xml.
- Support both direct URL sets and nested sitemap indexes.
- Identify article URLs without treating sitemap files, assets, or unrelated pages as articles.
- Respect reasonable request timeouts, a descriptive User-Agent, and polite request pacing.
- Make crawl limits configurable for local testing and full ingestion.
- Handle HTTP errors, network errors, malformed HTML, and empty pages on a per-URL basis. One failed page must not terminate the entire crawl.
- Record per-URL status and a useful error summary without storing secrets.

#### KB-FR-02: Article extraction and normalization

For each successfully extracted article, store as available:

- Canonical URL (preferred citation URL).
- Page title.
- Main article text, excluding navigation, footer, cookie banners, and repeated page chrome where practical.
- Headings and their hierarchy.
- Crawl timestamp.
- Sitemap metadata such as lastmod and priority, when present.
- Extraction status and version/hash for change detection.

Store failed records separately or clearly mark them as failed; never index failed/empty records as valid knowledge.

#### KB-FR-03: Chunking

- Split article text into retrieval-sized chunks while preserving heading context.
- Avoid chunks that are empty or only contain boilerplate.
- Use a configurable chunk size and overlap.
- Keep every chunk linked to its source article and canonical URL.
- Store stable chunk identifiers and source metadata.
- Avoid duplicate chunks when an unchanged article is reprocessed.

#### KB-FR-04: Embeddings and index

- Use an embedding model suited to semantic retrieval; keep the provider/model configurable.
- Store embeddings and metadata in PostgreSQL with pgvector for the intended persistent index.
- Keep source article data and chunk metadata traceable.
- Support rebuilding the index from stored article content.
- Do not silently fall back to keyword-only or fake embeddings and report the index as healthy. If a provider or database is unavailable, report the limitation clearly.

#### KB-FR-05: Question answering

- Expose an API that accepts a user question and returns a grounded answer.
- Retrieve relevant chunks before generating the answer.
- The generation prompt must instruct the model to use retrieved evidence only for product-specific factual claims.
- Include citations containing at minimum article title and canonical URL; include relevant heading or chunk reference when available.
- Do not fabricate URLs, article titles, quotes, or citations.
- If retrieval confidence/evidence is insufficient, explicitly abstain or ask a clarifying question rather than guess.
- If sources conflict, explain the conflict or escalate instead of selecting an unsupported answer.
- Return a structured response including answer, citations, confidence/evidence status, and whether escalation is recommended.
- Keep model and retrieval parameters configurable.

#### KB-FR-06: Escalation

- Support an escalation recommendation for unanswered, ambiguous, high-risk, or conflicting questions.
- Include a short reason and the missing information/evidence.
- Do not claim a ticket or human notification was sent unless that integration exists and succeeds.

#### KB-FR-07: Incremental ingestion

- Support repeatable daily or manually triggered ingestion.
- Detect changed/new articles using available sitemap metadata and/or content hashes.
- Re-index changed content and avoid unnecessary re-embedding of unchanged chunks.
- Mark removed sources as inactive/stale rather than silently leaving them as current.
- Record the last successful run, counts, failures, and duration.
- Make retries bounded and observable.

#### KB-FR-08: API and health

- Provide a health endpoint for process status.
- Provide a readiness/diagnostics endpoint or equivalent that can distinguish API availability from database, index, and model-provider availability.
- Validate request bodies and return consistent error responses.
- Include API documentation via FastAPI/OpenAPI.
- Do not expose credentials, full prompts containing sensitive data, or internal stack traces to API consumers.

### 4.2 Task 2 — Inbox Agent

#### IN-FR-01: Email dataset

- Include at least 50 realistic synthetic customer emails.
- Cover different intents such as how-to questions, account/configuration issues, billing, bugs, feature requests, unclear requests, urgent issues, and questions outside the knowledge base.
- Include expected labels and evaluation metadata where appropriate.
- Use fictional names, domains, identifiers, and business details. Do not include real customer personal data.

#### IN-FR-02: Classification

- Classify each email into a documented intent taxonomy.
- Identify urgency, ambiguity, confidence, and risk/escalation needs.
- Return structured JSON validated against a schema.
- Handle malformed model output with bounded retry or a safe failure state.
- Preserve the original email and record classification output separately.

#### IN-FR-03: Knowledge Brain integration

- Call Task 1 through its public HTTP API for relevant support questions.
- Use timeouts, bounded retries, and clear error handling.
- Do not import Task 1 internals or duplicate its crawler, embedding, retrieval, or answer logic.
- If Task 1 is unavailable or abstains, draft a clarification/escalation response rather than inventing an answer.

#### IN-FR-04: Draft responses

- Generate concise, professional, customer-appropriate email drafts based on the email and Knowledge Brain evidence.
- Include internal source citations/references for reviewer verification; do not expose internal-only notes to the customer unless intentionally formatted as links.
- Clearly separate confirmed facts from assumptions.
- Never invent product features, account status, pricing, policy, delivery dates, refunds, or commitments.
- Provide an explicit escalation reason when a confident grounded response cannot be produced.

#### IN-FR-05: Human review

- Provide a simple interface or documented review workflow to approve, edit, or reject drafts.
- Keep original draft, edited version, reviewer decision, timestamps, and reviewer feedback.
- An approved draft may be marked ready to send; actual email sending is out of scope unless explicitly added with authorization and tests.
- No email is sent automatically merely because a draft was generated or approved in a local demo.

#### IN-FR-06: Feedback and learning records

- Track approved-without-edit, edited, rejected, and escalated outcomes.
- Store feedback as evaluation/training data with privacy-conscious retention.
- Do not silently train or fine-tune a model from feedback.
- Make it possible to analyze common rejection/edit reasons.

#### IN-FR-07: 20-consecutive-draft automation rule

- Track consecutive eligible drafts that are approved without edits.
- The counter must reset when a draft is edited, rejected, escalated, fails validation, or has inadequate evidence.
- Reaching 20 consecutive unedited approvals may only enable a proposed automation-eligible state, not unrestricted autonomous sending.
- Maintain a human override and an audit trail.
- Exclude high-risk, ambiguous, unsupported, policy-sensitive, billing/refund, account-security, and other configured sensitive cases from automation.
- Re-check current safeguards and evidence for every email; historical performance must not override a current risk signal.
- Any real auto-send capability requires an explicit later decision, authorization, scoped allowlist, rate limits, monitoring, rollback/disable switch, and dedicated tests.

### 4.3 Task 3 — Meeting-to-Scope

#### MS-FR-01: Transcript dataset

- Include at least three realistic synthetic meeting transcripts, including at least one follow-up meeting.
- Include speaker labels and timestamps or stable line references where practical.
- Cover clear requirements, ambiguous statements, constraints, dependencies, exclusions, and scope changes.
- Use fictional companies and people.

#### MS-FR-02: Structured requirements

- Extract requirements into a validated schema with fields such as:
  - Requirement ID and concise description.
  - Type/category and priority.
  - Acceptance criteria.
  - Source transcript and timestamp/line reference.
  - Confidence and ambiguity status.
  - Dependencies, assumptions, and open questions.
  - In-scope/out-of-scope/undecided status.
- Distinguish explicit customer statements from inferred suggestions.
- Do not invent a customer commitment to resolve missing information; create an open question instead.

#### MS-FR-03: Feasibility

- Check proposed requirements against the Knowledge Brain by calling Task 1's API.
- Cite the support evidence used for product capabilities.
- Classify each relevant requirement as supported, unsupported, unclear, or requiring human/technical review.
- Task 1 is a knowledge source, not a substitute for engineering judgment. Clearly flag estimates or technical feasibility conclusions that need human confirmation.

#### MS-FR-04: SOW and proposal

- Generate a draft SOW with objectives, scope, deliverables, assumptions, dependencies, exclusions, acceptance criteria, risks, and open questions.
- Generate a proposal summary suitable for human review.
- Provide task-level effort estimates with rationale, uncertainty/range, and dependencies.
- Label estimates as provisional, not guaranteed commitments.
- Keep source references from transcript requirements and knowledge citations.
- Do not fabricate prices, contract terms, legal advice, delivery guarantees, or customer approvals.

#### MS-FR-05: Baseline and scope-change detection

- Allow a reviewer to approve and freeze a baseline requirements/SOW version.
- Compare later transcript requirements or generated scope against the approved baseline.
- Identify added, removed, modified, conflicting, and unclear requirements.
- Flag likely out-of-scope requests with the original and new source references.
- Show the rationale and confidence; do not automatically accept scope changes.
- Preserve version history and reviewer decisions.

#### MS-FR-06: Human approval

- Require human approval before an SOW/proposal is considered final.
- Record reviewer, decision, timestamp, and comments.
- Keep drafts distinct from approved versions.

## 5. Cross-Cutting Functional Requirements

- Use consistent request IDs/correlation IDs across API calls and logs where practical.
- Validate all external input and model output against schemas.
- Make operations idempotent where repeated requests could create duplicate records.
- Use bounded retries and timeouts for external services.
- Provide useful errors and actionable logs without leaking secrets.
- Support local development with synthetic fixtures and mocked external services where possible.
- Expose model/provider failures and partial results instead of masking them.
- Maintain audit history for human decisions and important state transitions.
- Keep user-facing text professional, concise, and explicit about uncertainty.
- Support a documented local demo path that does not require real customer accounts.

## 6. Technical Requirements

### 6.1 Languages and frameworks

- **Task 1:** Python, FastAPI, Pydantic, httpx, XML parsing, BeautifulSoup or equivalent HTML parser, pytest.
- **Task 2:** TypeScript and Node.js; use a maintained HTTP client and a test framework compatible with the existing repository.
- **Task 3:** Python, Pydantic, an HTTP client for Task 1 integration, pytest.
- **Database:** PostgreSQL; use pgvector for embedding storage/retrieval.
- **Background processing:** use a lightweight worker/scheduler appropriate to the existing stack. Do not introduce a broker unless the workflow requires it and the decision is documented.
- **LLM:** Anthropic Claude API, with model/configuration selection externalized. Do not hardcode a model name throughout the code.
- **Embeddings:** use a separate suitable embedding model/provider; do not assume the chat model creates embeddings unless the selected provider explicitly supports it.
- **Local document storage:** keep source/derived documents on local disk for this capstone, with configurable paths and no reliance on cloud storage.
- **UI:** a simple review interface is sufficient; prioritize correct workflows, inspectability, and testability over visual polish.

### 6.2 Configuration and secrets

- Read configuration from environment variables and/or a local .env file that is excluded from Git.
- Provide a .env.example with placeholder values only.
- Never log API keys, passwords, encryption keys, authorization headers, or full secret-bearing environment configuration.
- Validate required configuration at startup and give actionable errors.
- Document which features can run without Claude, PostgreSQL, or the embedding provider.
- Never commit .env, local databases, generated article dumps, virtual environments, caches, or secrets.

Suggested configuration names (adjust to current code and document the final names):

- ANTHROPIC_API_KEY
- ANTHROPIC_MODEL
- EMBEDDING_PROVIDER
- EMBEDDING_MODEL
- DATABASE_URL
- KNOWLEDGE_BRAIN_BASE_URL
- ARTICLE_DATA_DIR
- CRAWL_USER_AGENT
- CRAWL_DELAY_SECONDS
- REQUEST_TIMEOUT_SECONDS

### 6.3 API contracts

- Define request and response schemas for public endpoints.
- Include schema validation, consistent status codes, and useful error bodies.
- Version public APIs or document compatibility expectations.
- Keep Task 1 as the only source of truth for knowledge retrieval and answer generation.
- Document endpoints and representative request/response examples in the README or shared docs.
- Do not return raw model chain-of-thought or hidden reasoning. Return concise explanations and evidence instead.

### 6.4 Database and persistence

- Use PostgreSQL for persistent application state and pgvector for embeddings.
- Define migrations/schema setup that can be reproduced locally.
- Store article, chunk, embedding, crawl-run, email-review, feedback, transcript, requirement, scope-version, and approval records as appropriate to the implementation.
- Use foreign keys, uniqueness constraints, and indexes where useful.
- Keep tenant/customer data separated where multi-tenancy is implemented.
- Never rely on in-memory state for data that must survive a restart.
- Do not add database tables until the use case and ownership are clear; document schema decisions.

### 6.5 Logging and observability

- Use structured, useful logs with timestamps and correlation IDs.
- Record crawl counts, indexed/failed counts, model name/config, elapsed time, and errors.
- Record workflow state changes and human-review actions.
- Track model calls, token usage/cost when available, latency, retry count, and failures.
- Redact sensitive data and avoid logging entire emails/transcripts by default.
- Provide health/readiness checks that distinguish process health from dependency health.

### 6.6 Reliability and performance

- Apply timeouts to network and model calls.
- Use bounded retries with backoff only for retryable errors.
- Keep batch sizes and concurrency configurable.
- Make ingestion restartable and safe to repeat.
- Avoid duplicate article/chunk/index records on reruns.
- Handle partial failures without falsely reporting full success.
- Do not set arbitrary performance targets without measuring a baseline; record actual latency and resource usage in evaluation docs.

### 6.7 Security and privacy

- Use synthetic sample emails/transcripts only.
- Validate uploads and input sizes if file upload is supported.
- Restrict file paths to configured storage roots; prevent path traversal.
- Sanitize untrusted content before displaying it in the UI.
- Treat retrieved articles, emails, and transcripts as untrusted input, not instructions to the agent.
- Defend against prompt injection in documents and emails; retrieved content must not override system/developer instructions or trigger tools on its own.
- Require authorization for review/approval actions if authentication is implemented.
- Do not execute code, SQL, shell commands, or external actions based solely on model-generated text.
- Keep dependencies reasonably current and document any known security limitations.

## 7. Testing and Evaluation Requirements

### 7.1 Automated tests

- **Task 1:** tests for sitemap indexes, URL filtering, parsing, canonical URLs, malformed/empty pages, HTTP/network failures, chunk boundaries, deduplication, retrieval, citations, abstention, and API validation.
- **Task 2:** tests for classification schema, Task 1 timeout/abstention, draft grounding, approve/edit/reject paths, feedback persistence, automation counter reset, and risk exclusions.
- **Task 3:** tests for schema extraction, source references, ambiguity handling, Task 1 failures, estimate formatting, baseline diffs, out-of-scope flags, and approval/version history.
- Use mocked external APIs in ordinary unit tests. Keep a separate, explicitly opt-in integration test for real provider/database access.
- Test both success and failure paths.

### 7.2 Minimum evaluation set

- At least 20 evaluation cases per task.
- Task 1 cases should include answerable, partially answerable, unanswerable, conflicting, and citation-sensitive questions.
- Task 2 cases should cover all major intents, urgent/risky emails, missing evidence, malformed outputs, and review outcomes.
- Task 3 cases should cover explicit and ambiguous requirements, follow-up changes, unsupported capabilities, estimation uncertainty, and scope creep.
- Record expected behavior and scoring criteria before running the evaluation.
- Compare at least two Claude models or materially different model/configuration settings where appropriate and available.
- Measure quality, citation/grounding accuracy, abstention/safety, cost, latency, and reliability. Report limitations and representative failures in EVALS.md.
- Do not claim an evaluation passes solely because the model's answer sounds plausible.

### 7.3 Suggested metrics

- **Task 1:** retrieval relevance, answer correctness, citation precision, unsupported-claim rate, appropriate abstention rate, API success rate, latency, cost.
- **Task 2:** intent macro-F1/accuracy, draft groundedness, unsupported-claim rate, human edit/rejection rate, escalation recall, latency, cost.
- **Task 3:** requirement extraction precision/recall, source-reference accuracy, ambiguity detection, scope-diff accuracy, estimate reviewability, unsupported-claim rate, latency, cost.
- Report dataset size, test method, model/configuration, and known limitations with every metric.

## 8. Required Documentation and Demo

Maintain these project documents:

- **README.md** — setup, architecture overview, run/test instructions, environment variables, endpoints, and demo steps. Keep it concise (target no more than one page, excluding unavoidable setup detail).
- **DESIGN.md** — architecture, service boundaries, data flow, schemas, security, key decisions, and trade-offs (target 3–5 pages).
- **EVALS.md** — evaluation datasets/methods, model/config comparisons, metrics, results, failure cases, cost/latency, and limitations (target 2–3 pages).
- **AI_LOG.md** — concise record of meaningful AI-assisted implementation decisions, prompts/changes, validation, and corrections (target no more than one page).
- **.env.example** — placeholders only.
- Tests and synthetic fixtures for all three tasks.
- API contract examples and sample output files where useful.

Prepare a demo lasting no more than 10 minutes that shows:

1. A successful Knowledge Brain answer with citations.
2. An unanswerable or conflicting question that safely abstains/escalates.
3. An email draft that is reviewed and edited/approved.
4. A transcript converted to requirements/SOW with a source reference.
5. A follow-up change flagged against an approved scope baseline.
6. At least one failure case and how the system handles it.

## 9. Definition of Done

A feature is complete only when:

- Requirements and intended behavior are clear.
- Implementation follows the current service boundary and existing code conventions.
- Inputs/outputs are schema-validated.
- Relevant unit tests cover success and failure paths.
- Tests pass, or any failure is explicitly documented with its cause.
- Logs/errors are useful and do not leak secrets.
- Documentation and examples are updated.
- A manual smoke test is recorded for the user-facing workflow.
- No unrelated files or existing working behavior were damaged.

The capstone is ready for final review when:

- All three tasks have working end-to-end paths.
- Task 2 and Task 3 call Task 1 through its API.
- Required synthetic datasets and at least 20 evaluation cases per task exist.
- Human review, escalation, and safe abstention work as specified.
- README.md, DESIGN.md, EVALS.md, and AI_LOG.md are present and accurate.
- The demo can be completed in under 10 minutes and includes a failure case.
- Known limitations, external service requirements, and reproducible setup steps are documented.

## 10. Implementation Sequence

Use this sequence unless repository inspection reveals a dependency that requires a documented adjustment:

1. Inspect the current repository, API, crawler, dependencies, .gitignore, and tests.
2. Add/verify crawler tests and a reproducible small-batch ingestion run.
3. Implement normalized article storage and chunking.
4. Set up PostgreSQL/pgvector schema and persistence.
5. Add embedding generation and index rebuilding.
6. Implement retrieval, citations, abstention, and the answer API.
7. Add incremental ingestion and diagnostics.
8. Build Task 2 email fixtures, classifier, Knowledge Brain client, drafts, review, and feedback.
9. Build Task 3 transcript fixtures, requirement extraction, feasibility, SOW/proposal, baseline diff, and approval.
10. Add cross-task evaluation sets, model/config comparisons, and safety tests.
11. Complete documentation, demo script, and final clean-room setup verification.

Do not jump to later stages while an earlier dependency is unverified. Reassess the repository before each stage and update this document only through an explicit, reviewed requirements change.

## 11. Current Project State (baseline at document creation)

Reported as complete:

- Repository has task1-knowledge-brain/, task2-inbox-agent/, task3-meeting-to-scope/, and shared-docs/.
- Task 1 has a FastAPI application with / and /health.
- Task 1 has app/crawler.py supporting sitemap indexes and article extraction.
- The sitemap crawl identified approximately 1,537 article URLs.
- The crawler supports small-batch and full-run modes, per-URL failures, request timeouts, a descriptive User-Agent, and a delay between requests.
- Sample output: data/articles-sample.json; full output path: data/articles.json.
- requirements.txt includes BeautifulSoup.
- Root .gitignore excludes .venv/, data/, and __pycache__/.
- No commits have been made yet.

This state is based on the project status reported by the user and must be re-verified from the repository before the next implementation step.

## 12. Immediate Next Action for the Coding Agent

Before implementing chunking or embeddings:

1. Inspect task1-knowledge-brain/app/crawler.py, app/main.py, requirements.txt, .gitignore, and the current sample output.
2. Run the crawler tests or add focused tests for sitemap indexes, successful article extraction, malformed/empty HTML, HTTP 404, network failure, canonical URL handling, and duplicate URLs.
3. Run a small crawl and verify that successful records have non-empty titles/text and valid canonical URLs, while failed records remain clearly marked.
4. Report what was inspected, the tests run, actual results, and any limitations.
5. Only then propose the article/chunk data model and implement chunking in a separate, testable module.

Do not start Step 4 until the crawler's current behavior and tests have been verified.
