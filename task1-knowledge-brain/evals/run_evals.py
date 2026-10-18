"""Run Knowledge Brain evaluation cases against a live KnowledgeService.

Two store modes are supported:

- ``env`` (default): use ``build_default_service()`` — the real PostgreSQL index and
  the embedding/chat providers configured in the environment.
- ``memory``: index ``data/articles-sample.json`` into an in-memory store with the
  configured embedding provider (useful for trying a chat model without a database).

Usage (PowerShell)::

    # Real database + real providers (recommended)
    $env:DATABASE_URL = "postgresql://postgres:postgres@localhost:55432/knowledge_brain"
    $env:EMBEDDING_PROVIDER = "ollama"; $env:EMBEDDING_MODEL = "nomic-embed-text"; $env:EMBEDDING_DIMENSIONS = "768"
    $env:CHAT_PROVIDER = "ollama"; $env:CHAT_MODEL = "llama3.2:1b"
    python evals/run_evals.py

    # No database required
    python evals/run_evals.py --store memory

Exit code is 0 only when every case passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.answer import SYSTEM_PROMPT, AnswerConfig
from app.chat import build_chat_provider
from app.embeddings import build_embedding_provider
from app.indexer import IndexConfig, index_document
from app.retriever import RetrievalConfig
from app.schemas import AskRequest, AskResponse
from app.service import KnowledgeService, ServiceUnavailable, build_default_service
from app.store import InMemoryKnowledgeStore

DEFAULT_CASES = ROOT / "evals" / "cases.json"
DEFAULT_SAMPLE = ROOT / "data" / "articles-sample.json"


def load_cases(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SystemExit(f"no cases found in {path}")
    return cases


def build_memory_service(sample_path: Path) -> KnowledgeService:
    if not sample_path.exists():
        raise SystemExit(
            f"sample document not found: {sample_path}. Crawl sample data first "
            f"(see README) or run with --store env."
        )
    document = json.loads(sample_path.read_text(encoding="utf-8"))
    embedding_provider = build_embedding_provider()
    chat_provider = build_chat_provider()
    store = InMemoryKnowledgeStore()
    report = index_document(store, embedding_provider, document, IndexConfig())
    print(
        f"indexed {report.chunks_written} chunk(s) into the in-memory store "
        f"using {embedding_provider.model_name} ({embedding_provider.dimensions}d)"
    )
    return KnowledgeService(
        store_factory=lambda: store,
        embedding_provider=embedding_provider,
        chat_provider=chat_provider,
        retrieval_config=RetrievalConfig(),
        answer_config=AnswerConfig(),
        embedding_detail=f"{embedding_provider.model_name} ({embedding_provider.dimensions}d)",
        chat_detail=chat_provider.model_name,
    )


def score(case: dict, response: AskResponse) -> list[str]:
    problems: list[str] = []
    if response.evidence_status not in case["expect_status"]:
        problems.append(
            f"status={response.evidence_status!r} not in {case['expect_status']}"
        )

    cited = [c.article_id for c in response.citations]
    expected = case.get("expect_articles") or []
    if expected and not (set(cited) & set(expected)):
        problems.append(f"citations {cited} did not include any of {expected}")
    if case.get("expect_no_citations") and response.citations:
        problems.append(f"expected no citations but got {cited}")

    for citation in response.citations:
        if not citation.chunk_id:
            problems.append("citation is missing a chunk_id")

    answer = (response.answer or "").lower()
    if SYSTEM_PROMPT[:50].lower() in answer:
        problems.append("answer leaked the system prompt")
    for forbidden in case.get("forbid_in_answer", []):
        if forbidden.lower() in answer:
            problems.append(f"answer contained forbidden text {forbidden!r}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Knowledge Brain eval cases.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--store", choices=["env", "memory"], default="env")
    parser.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json-report", type=Path, default=None)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    if args.limit:
        cases = cases[: args.limit]

    if args.store == "memory":
        service = build_memory_service(args.sample)
    else:
        service = build_default_service()

    results: list[dict] = []
    passed = 0
    for case in cases:
        started = time.perf_counter()
        error = None
        try:
            response = service.ask(AskRequest(question=case["question"]))
            problems = score(case, response)
        except ServiceUnavailable as exc:
            problems = [f"service unavailable ({exc.dependency})"]
            error = {"type": "ServiceUnavailable", "dependency": exc.dependency}
            response = None
        except Exception as exc:  # noqa: BLE001 - report, never crash the harness
            problems = [f"unexpected error: {type(exc).__name__}"]
            error = {"type": type(exc).__name__}
            response = None

        ok = not problems
        passed += ok
        results.append(
            {
                "id": case["id"],
                "category": case["category"],
                "passed": ok,
                "problems": problems,
                "answer": None if response is None else response.answer,
                "evidence_status": None if response is None else response.evidence_status,
                "citations": []
                if response is None
                else [c.article_id for c in response.citations],
                "escalate": None if response is None else response.needs_escalation,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "error": error,
                "raw_response": None if response is None else response.model_dump(mode="json"),
            }
        )

        marker = "PASS" if ok else "FAIL"
        print(f"[{marker}] {case['id']:<18} {case['category']:<12} {case['question'][:60]}")
        if not ok:
            for problem in problems:
                print(f"         - {problem}")
        elif args.verbose:
            print(f"         status={results[-1]['evidence_status']} cites={results[-1]['citations']}")
            print(f"         answer={results[-1]['answer']}")

    total = len(results)
    print(f"\n{passed}/{total} cases passed")
    if args.json_report:
        case_bytes = args.cases.read_bytes()
        embedding = getattr(service, "embedding_provider", None)
        chat = getattr(service, "chat_provider", None)
        args.json_report.write_text(
            json.dumps({
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "cases_file": str(args.cases),
                "cases_sha256": hashlib.sha256(case_bytes).hexdigest(),
                "store_mode": args.store,
                "embedding_model": getattr(embedding, "model_name", None),
                "chat_model": getattr(chat, "model_name", None),
                "response_source": "actual configured providers for this run; inspect model fields and raw responses",
                "passed": passed,
                "total": total,
                "results": results,
            }, indent=2),
            encoding="utf-8",
        )
        print(f"wrote report to {args.json_report}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
