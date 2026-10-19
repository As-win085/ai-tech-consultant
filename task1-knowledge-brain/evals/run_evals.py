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

    # Tuning split only (holdout cases are never run during prompt tuning)
    python evals/run_evals.py --store memory --split tuning

Exit code is 0 only when every case passes (1 = some cases failed, report written).
Cost fields are computed from the shared pricing table (shared-docs/evals/pricing.json,
source and retrieval date recorded in the report); token usage is captured from the
live chat provider responses.
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

from app.answer import ANSWER_PROMPT, SYSTEM_PROMPT, AnswerConfig
from app.chat import build_chat_provider
from app.embeddings import build_embedding_provider
from app.indexer import IndexConfig, index_document
from app.retriever import RetrievalConfig, Retriever
from app.schemas import AskRequest, AskResponse
from app.service import KnowledgeService, ServiceUnavailable, build_default_service
from app.store import InMemoryKnowledgeStore

DEFAULT_CASES = ROOT / "evals" / "cases.json"
DEFAULT_SAMPLE = ROOT / "data" / "articles-sample.json"
PRICING_TABLE = ROOT.parent / "shared-docs" / "evals" / "pricing.json"


def load_pricing() -> dict:
    if not PRICING_TABLE.exists():
        return {}
    return json.loads(PRICING_TABLE.read_text(encoding="utf-8"))


def cost_block(chat, pricing: dict) -> dict:
    """Token usage and cost for this run, priced from the shared pricing table."""
    usage = getattr(chat, "usage_totals", None)
    input_tokens = int(usage.get("input_tokens", 0)) if usage else 0
    output_tokens = int(usage.get("output_tokens", 0)) if usage else 0
    model = getattr(chat, "model_name", None)
    entry = (pricing.get("models") or {}).get(model) if model else None
    if entry is not None:
        cost_usd = round(
            (input_tokens / 1_000_000) * float(entry["input"])
            + (output_tokens / 1_000_000) * float(entry["output"]),
            6,
        )
        basis = (
            f"tokens x pricing.json list prices (source: {pricing.get('source')}, "
            f"retrieved: {pricing.get('retrieved_at')})"
        )
    elif input_tokens == 0 and output_tokens == 0:
        cost_usd = 0.0
        basis = "no chat tokens used (offline provider or run failed before chat)"
    else:
        cost_usd = None
        basis = "model is missing from the pricing table; cost unavailable"
    return {
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
        "cost_basis": basis,
        "provider_reported_cost_usd": getattr(chat, "provider_reported_cost_usd", None),
        "pricing_table": "shared-docs/evals/pricing.json",
        "pricing_source": pricing.get("source"),
        "pricing_retrieved_at": pricing.get("retrieved_at"),
        "embedding_cost_included": False,
        "embedding_cost_note": (
            "embedding cost is excluded from the model comparison: it is identical "
            "across compared chat models (gemini-embedding-001, free tier)"
        ),
    }


def load_cases(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SystemExit(f"no cases found in {path}")
    return cases


def select_split(cases: list[dict], split: str) -> list[dict]:
    """Filter cases to one split; cases without a split field count as tuning."""
    if split == "all":
        return cases
    selected = [case for case in cases if case.get("split", "tuning") == split]
    if not selected:
        raise SystemExit(f"no cases with split={split!r}")
    return selected


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
        f"indexed chunks_written={report.chunks_written} chunks_embedded={report.chunks_embedded} "
        f"chunks_failed={report.chunks_failed} status={report.status} "
        f"using {embedding_provider.model_name} ({embedding_provider.dimensions}d)"
    )
    service = KnowledgeService(
        store_factory=lambda: store,
        embedding_provider=embedding_provider,
        chat_provider=chat_provider,
        retrieval_config=RetrievalConfig(),
        answer_config=AnswerConfig(),
        embedding_detail=f"{embedding_provider.model_name} ({embedding_provider.dimensions}d)",
        chat_detail=chat_provider.model_name,
    )
    service.eval_store = store
    service.eval_index_report = report
    return service


def retrieval_diagnostics(service: KnowledgeService, cases: list[dict]) -> dict:
    """Inspect the real indexed vectors independently of answer-model availability."""
    store = getattr(service, "eval_store", None)
    provider = getattr(service, "embedding_provider", None)
    if store is None or provider is None:
        return {"status": "not_available_for_store_mode", "cases": []}
    target_cases = [case for case in cases if case.get("category") == "answerable"]
    try:
        vectors = provider.embed([case["question"] for case in target_cases])
        retriever = Retriever(store, provider, service.retrieval_config)
        rows = []
        for case, vector in zip(target_cases, vectors):
            candidates = store.search_similar(
                vector, provider.model_name, provider.dimensions,
                max(service.retrieval_config.top_k * service.retrieval_config.oversample,
                    service.retrieval_config.top_k),
            )
            above = [hit for hit in candidates if hit.score >= service.retrieval_config.min_score]
            selected, _ = retriever._select(above, service.retrieval_config.top_k)
            expected = case.get("expect_articles") or []
            rows.append({
                "id": case["id"], "expected_articles": expected,
                "top_candidate_article": candidates[0].article_id if candidates else None,
                "top_candidate_score": round(candidates[0].score, 6) if candidates else None,
                "expected_article_in_candidates": any(hit.article_id in expected for hit in candidates),
                "expected_article_above_threshold": any(hit.article_id in expected for hit in above),
                "selected_articles": [hit.article_id for hit in selected],
                "selected_sources": [{"article_id": hit.article_id, "chunk_id": hit.chunk_id,
                    "score": round(hit.score, 6), "title": hit.title,
                    "canonical_url": hit.canonical_url, "content": hit.content} for hit in selected],
            })
        return {"status": "measured_real_embeddings", "min_score": service.retrieval_config.min_score,
                "indexed_chunks": store.index_metadata().indexed_chunks, "cases": rows}
    except Exception as exc:
        return {"status": "diagnostic_failed", "error_type": type(exc).__name__, "cases": []}


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
    parser.add_argument(
        "--split",
        choices=["all", "tuning", "holdout"],
        default="all",
        help="run only cases from one split; cases without a split field count as tuning",
    )
    parser.add_argument("--store", choices=["env", "memory"], default="env")
    parser.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json-report", type=Path, default=None)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    cases = select_split(cases, args.split)
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
            response = service.ask(AskRequest(question=case["question"], include_chunks=True))
            problems = score(case, response)
        except ServiceUnavailable as exc:
            problems = [f"service unavailable ({exc.dependency})"]
            error = {
                "type": "ServiceUnavailable",
                "dependency": exc.dependency,
                "detail": exc.message,
            }
            response = None
        except Exception as exc:  # noqa: BLE001 - report, never crash the harness
            problems = [f"unexpected error: {type(exc).__name__}"]
            error = {"type": type(exc).__name__, "detail": str(exc)[:500]}
            response = None

        ok = not problems
        passed += ok
        cited = [] if response is None else [citation.article_id for citation in response.citations]
        expected_articles = case.get("expect_articles") or []
        if response is None:
            citation_correctness = None
            abstention_correctness = None
        else:
            citation_correctness = (
                bool(set(cited) & set(expected_articles))
                if expected_articles
                else not response.citations if case.get("expect_no_citations") else None
            )
            expected_abstention = case["category"] != "answerable"
            observed_abstention = response.evidence_status != "sufficient"
            abstention_correctness = expected_abstention == observed_abstention
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
                "retrieved_sources": None if response is None else [
                    chunk.model_dump(mode="json") for chunk in (response.retrieved_chunks or [])
                ],
                "expected_citation_articles": expected_articles,
                "citation_correctness": citation_correctness,
                "expected_abstention": None if response is None else case["category"] != "answerable",
                "observed_abstention": None if response is None else response.evidence_status != "sufficient",
                "abstention_correctness": abstention_correctness,
                "escalate": None if response is None else response.needs_escalation,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "retry_count": int(getattr(getattr(service, "chat_provider", None), "retry_count", 0)),
                "model_failure": error is not None,
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
        pricing = load_pricing()
        run_cost = cost_block(chat, pricing)
        print(
            f"cost: model={run_cost['model']} "
            f"input_tokens={run_cost['input_tokens']} "
            f"output_tokens={run_cost['output_tokens']} "
            f"cost_usd={run_cost['cost_usd']}"
        )
        args.json_report.write_text(
            json.dumps({
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "cases_file": str(args.cases),
                "cases_sha256": hashlib.sha256(case_bytes).hexdigest(),
                "split": args.split,
                "cases_run": total,
                "store_mode": args.store,
                "embedding_model": getattr(embedding, "model_name", None),
                "chat_model": getattr(chat, "model_name", None),
                "prompt": ANSWER_PROMPT.report_block(),
                "response_source": "actual configured providers for this run; inspect model fields and raw responses",
                "passed": passed,
                "total": total,
                "cost": run_cost,
                "citation_correct_cases": sum(r["citation_correctness"] is True for r in results),
                "citation_scored_cases": sum(r["citation_correctness"] is not None for r in results),
                "abstention_correct_cases": sum(r["abstention_correctness"] is True for r in results),
                "abstention_scored_cases": sum(r["abstention_correctness"] is not None for r in results),
                "retry_attempts_total": sum(r["retry_count"] for r in results),
                "retried_cases": sum(r["retry_count"] > 0 for r in results),
                "model_failures": sum(r["model_failure"] for r in results),
                "indexing": (service.eval_index_report.summary() if hasattr(service, "eval_index_report") else None),
                "retrieval_diagnostics": retrieval_diagnostics(service, cases),
                "results": results,
            }, indent=2),
            encoding="utf-8",
        )
        print(f"wrote report to {args.json_report}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
