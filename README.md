# AI Tech Consultant

An AI-powered business workflow automation platform that combines knowledge retrieval, email assistance, and meeting-to-scope generation into a unified application. The system uses specialized AI agents to retrieve technical documentation, assist with customer support emails, and convert meeting discussions into structured project scopes and proposals—with human review at critical decision points.

## Table of Contents

- [Overview](#overview)
- [Project Objectives](#project-objectives)
- [Core Features](#core-features)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Application Workflows](#application-workflows)
- [Getting Started](#getting-started)
- [Environment Configuration](#environment-configuration)
- [Running the Application](#running-the-application)
- [Testing and Evaluation](#testing-and-evaluation)
- [Security and Reliability](#security-and-reliability)
- [Project Documentation](#project-documentation)
- [Roadmap](#roadmap)

## Overview

AI Tech Consultant is designed to automate repetitive technical consulting and business operations while preserving human oversight.

The application consists of three specialized agents:

1. **Knowledge Brain Agent** — retrieves information from technical documentation and answers questions with supporting sources.
2. **Inbox Agent** — classifies incoming emails, identifies urgency and risk, retrieves relevant knowledge, and prepares responses for review.
3. **Meeting-to-Scope Agent** — converts meeting transcripts into requirements, estimates, project scopes, and proposals while tracking changes to previously approved scopes.

The agents are accessible through a web interface that enables users to interact with knowledge, review email drafts, and build project scopes.

## Project Objectives

- Build reliable AI agents for practical business workflows.
- Use retrieval-augmented generation (RAG) to ground answers in source documentation.
- Automate repetitive work without removing necessary human approval.
- Connect frontend interfaces to backend APIs and persistent storage.
- Evaluate AI quality, latency, and cost using repeatable test cases.
- Make the system maintainable, observable, and suitable for future extension.

## Core Features

### 1. Knowledge Brain Agent

The Knowledge Brain provides a searchable knowledge base using documentation from the Brilliant Directories Solution Center.

Source sitemap: https://support.brilliantdirectories.com/support/sitemap.xml

**Features**

- Discover and ingest documentation pages from the sitemap.
- Extract article text and relevant metadata, including source URLs and available image information.
- Clean and split content into retrieval-friendly chunks.
- Generate embeddings and store searchable vector representations.
- Retrieve relevant passages for user questions.
- Generate answers grounded in retrieved documentation.
- Display source citations so users can verify answers.
- Abstain or recommend escalation when the available evidence is insufficient.
- Support re-ingestion when source documentation changes.
- Expose knowledge retrieval through an API for use by other agents.

**Expected workflow**

`Sitemap → Document ingestion → Text extraction → Chunking → Embeddings → Vector storage → Retrieval → Grounded answer`

### 2. Inbox Agent

The Inbox Agent assists with customer-support email processing and response preparation.

**Features**

- Process a dataset containing at least 50 realistic emails.
- Classify messages into appropriate categories.
- Identify urgency, risk, and messages requiring escalation.
- Query the Knowledge Brain for relevant technical information.
- Generate context-aware email drafts.
- Present drafts for human review and approval.
- Support editing, approval, rejection, and escalation.
- Record reviewer decisions and feedback.
- Track consecutive unchanged drafts by category.
- Apply controlled auto-sending eligibility after 20 consecutive unchanged drafts within a category, subject to configured safety checks and approval policies.

**Expected workflow**

`Incoming email → Classification → Urgency/risk analysis → Knowledge retrieval → Draft generation → Human review → Approved action`

Auto-sending must never be enabled solely because a numerical threshold was reached. The system should also enforce appropriate eligibility rules, authorization, logging, and safeguards.

### 3. Meeting-to-Scope Agent

The Meeting-to-Scope Agent transforms meeting discussions into actionable project documentation.

**Features**

- Process at least three role-play meeting transcripts.
- Support follow-up discussions that introduce scope changes.
- Extract functional requirements, constraints, assumptions, and open questions.
- Check technical feasibility against available knowledge.
- Identify missing information and dependencies.
- Produce a structured project scope.
- Estimate tasks using low, likely, and high effort estimates.
- Generate a proposal from the approved requirements and estimates.
- Compare updated scope against an approved baseline.
- Highlight additions, removals, and modifications.
- Require human review and approval before finalizing scope changes.

**Expected workflow**

`Meeting transcript → Requirement extraction → Knowledge and feasibility checks → Task breakdown → Estimates → Proposal → Human approval`

For follow-up meetings, the agent should generate a scope difference report rather than silently overwriting the approved baseline.

## System Architecture

The application follows a frontend-and-backend architecture with specialized agent services and shared persistence.

```text
                       Web Application
                             |
             +---------------+---------------+
             |               |               |
        Knowledge Chat   Inbox Review    Scope Builder
             |               |               |
             +---------------+---------------+
                             |
                         Backend APIs
                             |
          +------------------+------------------+
          |                  |                  |
     Knowledge Brain     Inbox Agent     Meeting-to-Scope
          |                  |                  |
          +------------------+------------------+
                             |
                 Shared AI and Data Services
                             |
             +---------------+---------------+
             |               |               |
          LLM API       PostgreSQL         pgvector
                             |
                    Background Processing
```

This diagram describes the intended logical architecture. Update it to reflect the actual service boundaries and integrations implemented in the repository.

### Main components

| Component | Responsibility |
|---|---|
| Frontend | User interaction, data display, review controls, and workflow navigation |
| Knowledge Brain API | Document ingestion, retrieval, grounded answers, and citations |
| Inbox Agent API | Email classification, drafting, review states, and feedback tracking |
| Meeting-to-Scope API | Requirement extraction, estimates, proposals, and scope comparison |
| LLM provider | Language understanding, classification, extraction, and generation |
| PostgreSQL | Persistent application records and workflow state |
| pgvector | Vector similarity search for embedded documentation |
| Background workers | Long-running ingestion or processing tasks, where implemented |

## Technology Stack

The following is the recommended stack for this project. Keep only the technologies that are actually implemented in your application.

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript |
| Backend APIs | Python, FastAPI |
| Inbox Agent service | TypeScript, Node.js, if implemented as a separate service |
| Database | PostgreSQL |
| Vector search | pgvector |
| AI integration | OpenAI API or another supported LLM provider |
| Embeddings | A compatible embedding model |
| Background processing | A task queue or worker system, if required |
| Testing | Backend unit tests, API integration tests, and frontend tests |
| Version control | Git |

The project may use a single backend language instead of separate Python and Node.js services. Document the actual implementation and avoid listing dependencies that are not used.

## Application Workflows

### Knowledge Chat

1. The user submits a question through the frontend.
2. The frontend sends the question to the Knowledge Brain API.
3. The backend retrieves relevant documentation chunks.
4. The language model generates an answer using the retrieved context.
5. The backend returns the answer, citations, and any relevant source metadata.
6. The frontend displays the answer and allows the user to open its sources.

**Success criteria:** The answer is relevant, sources point to the correct documents, and insufficient evidence results in an appropriate abstention or escalation.

### Inbox Review

1. Emails are loaded from the configured source or evaluation dataset.
2. The backend classifies each email and assesses urgency and risk.
3. The agent retrieves supporting information from the Knowledge Brain.
4. A response draft is generated and stored.
5. The frontend fetches and displays the email, classification, risk, and draft.
6. A reviewer edits, approves, rejects, or escalates the draft.
7. The backend persists the decision and records the audit trail.
8. Any automatic sending follows explicit eligibility and safety rules.

**Success criteria:** Email state changes persist correctly, drafts are grounded where appropriate, and approval or rejection in the frontend produces the expected backend result.

### Scope Builder

1. The user uploads or selects a meeting transcript.
2. The backend extracts requirements and constraints.
3. The agent checks relevant technical knowledge and identifies uncertainties.
4. The system generates tasks, estimates, and a proposal.
5. The user reviews and approves the proposed baseline.
6. Follow-up transcripts are processed against the approved baseline.
7. The application displays scope changes for review.

**Success criteria:** Requirements and estimates are traceable to the meeting, and follow-up changes are accurately compared with the approved baseline.

## Getting Started

### Prerequisites

Install the tools required by your actual implementation:

- Git
- Node.js and npm, if the frontend or any backend service uses Node.js
- Python and pip, if the backend uses Python
- PostgreSQL with the required database extensions
- An API key for the configured language model
- Any additional services required by the repository

### 1. Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd <YOUR_PROJECT_DIRECTORY>
```

### 2. Configure the environment

Create the environment files expected by each application. Use the actual `.env.example` files in the repository as the source of truth.

Do not commit API keys, database passwords, or other secrets.

### 3. Install dependencies

For a Python backend:

```bash
cd <BACKEND_DIRECTORY>
python -m venv .venv
```

Activate the environment.

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Then install the project's dependencies:

```bash
pip install -r requirements.txt
```

For a Node.js application:

```bash
cd <APPLICATION_DIRECTORY>
npm install
```

Repeat only for the frontend and services that exist in your repository.

### 4. Prepare the database

1. Create the PostgreSQL database.
2. Enable pgvector if vector search is used.
3. Configure the connection string.
4. Run the migrations or database initialization scripts provided by the project.
5. Verify that the required tables, indexes, and vector columns exist.

Do not assume the database is ready simply because the backend process starts successfully.

### 5. Ingest the knowledge base

Run the repository's document-ingestion command or API to import the configured documentation sources. Verify that the documents were extracted, embedded, and persisted before testing retrieval.

The exact command depends on the implemented ingestion pipeline.

## Environment Configuration

Create a local environment file based on the project's environment template.

Example variable names are shown below for illustration. Replace them with the exact names expected by the application.

```dotenv
# Application
APP_ENV=development
API_HOST=127.0.0.1
API_PORT=8000

# Database
DATABASE_URL=postgresql://<USER>:<PASSWORD>@<HOST>:5432/<DATABASE>

# LLM provider
OPENAI_API_KEY=<YOUR_API_KEY>
OPENAI_MODEL=<YOUR_SUPPORTED_MODEL>
EMBEDDING_MODEL=<YOUR_EMBEDDING_MODEL>

# Frontend
VITE_API_BASE_URL=http://localhost:8000
```

Important configuration notes:

- Use the provider and model names supported by your actual SDK and implementation.
- Configure separate variables for the chat model and embedding model if your application requires both.
- Use a separate database configuration for testing when possible.
- Keep server-side secrets on the backend. Never expose a secret API key through frontend environment variables.
- If the Inbox Agent or Meeting-to-Scope Agent runs as a separate service, configure its API URL as required.
- Do not use production credentials in local development or automated tests.

## Running the Application

Start each service using its documented development command.

For example, a FastAPI application might use:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

A Vite-based React frontend might use:

```bash
npm run dev
```

These are example commands, not verified commands for this repository. Check the backend entry point and each `package.json` before using them.

Once the services are running:

1. Open the frontend development URL shown in the terminal.
2. Open the backend's health endpoint or API documentation if available.
3. Test Knowledge Chat with a question whose answer exists in the indexed documentation.
4. Open Inbox Review and verify that email records and drafts load from the backend.
5. Open Scope Builder and generate a scope from a sample transcript.
6. Approve or reject a draft and verify that the updated state persists after refreshing the page.

A working frontend page alone does not prove that its backend integration is correct. Confirm that requests reach the intended service and that returned data matches what the interface displays.

## Testing and Evaluation

Testing should cover individual components, API contracts, complete workflows, and AI output quality.

### Functional testing

- [ ] Knowledge documents can be ingested and retrieved.
- [ ] Answers include valid source citations.
- [ ] Unsupported questions trigger abstention or escalation.
- [ ] At least 50 realistic email records are available for testing.
- [ ] Email classifications and urgency/risk assessments are returned correctly.
- [ ] Drafts can be reviewed, edited, approved, rejected, and escalated.
- [ ] Auto-send eligibility follows the configured policy.
- [ ] At least three meeting transcripts can be processed.
- [ ] Scope proposals contain requirements and low, likely, and high estimates.
- [ ] Follow-up transcripts produce a scope-diff report.
- [ ] Human approvals are persisted and enforced.

### Frontend/backend integration testing

- [ ] Each frontend screen calls the correct backend endpoint.
- [ ] Request and response schemas match the API contract.
- [ ] Loading, empty, and error states are handled.
- [ ] Data shown in the interface comes from the correct server response.
- [ ] Changes made in the interface persist in the database.
- [ ] Refreshing a page does not unexpectedly lose saved decisions.
- [ ] Authentication and authorization are enforced where required.
- [ ] Long-running operations report progress or failure appropriately.

### AI evaluation

Maintain a reproducible evaluation dataset for all three agents. The project brief calls for at least 20 evaluation cases per task and comparison of at least two model choices or configurations.

Evaluate:

- **Knowledge Brain:** retrieval relevance, answer correctness, citation validity, and abstention quality.
- **Inbox Agent:** classification accuracy, urgency/risk identification, factual grounding, draft quality, and escalation decisions.
- **Meeting-to-Scope Agent:** requirement extraction, estimate usefulness, proposal completeness, and scope-diff accuracy.

Record model configuration, evaluation inputs, expected outcomes, actual outputs, quality scores, latency, and estimated cost. Document the evaluation method and limitations in `EVALS.md`.

## Security and Reliability

The application should follow these principles:

- Keep API keys and credentials out of frontend bundles and version control.
- Validate user input and enforce appropriate request-size limits.
- Use authentication and role-based authorization where applicable.
- Treat email bodies, documents, and meeting transcripts as untrusted input.
- Do not let instructions inside retrieved documents override system security rules.
- Require explicit authorization for external actions such as sending emails.
- Persist human decisions and important state transitions.
- Handle model API failures, timeouts, rate limits, and malformed responses.
- Log operational errors without exposing secrets or unnecessary sensitive content.
- Avoid duplicate actions when jobs are retried.
- Ensure the system can recover from failed ingestion and processing jobs.

## Project Documentation

The project submission should include the following documents:

| File | Purpose |
|---|---|
| `README.md` | Project overview, setup, architecture, and usage |
| `DESIGN.md` | Architecture decisions, components, data flow, and trade-offs |
| `EVALS.md` | Evaluation cases, results, model comparisons, cost, and latency |
| `AI_LOG.md` | Record of AI-assisted development, decisions, and validation |

Also prepare a demonstration video of no more than 10 minutes, showing the implemented agents and their principal workflows.

## Roadmap

Use this checklist to track remaining work. Mark items complete only after verification.

- [ ] Verify document ingestion and retrieval end to end.
- [ ] Verify the Knowledge Chat UI and source citations.
- [ ] Verify Inbox Agent classification and draft generation.
- [ ] Verify reviewer actions and persistent email states.
- [ ] Verify auto-send eligibility and safeguards.
- [ ] Verify transcript processing, estimates, and proposal generation.
- [ ] Verify scope comparison against an approved baseline.
- [ ] Test all frontend-to-backend connections.
- [ ] Run the required evaluation cases and model comparisons.
- [ ] Complete `DESIGN.md`, `EVALS.md`, and `AI_LOG.md`.
- [ ] Record the final demonstration video.
- [ ] Resolve critical defects and document known limitations.

## Contributing

Keep changes focused, document important architecture decisions, add regression tests for bug fixes, and verify affected frontend and backend workflows before considering a change complete.

## License

Add the license required by the project or submission instructions. Do not claim an open-source license unless one has been selected and applied.
