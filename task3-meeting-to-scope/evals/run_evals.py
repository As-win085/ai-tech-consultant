"""Run the frozen Task 3 synthetic eval set and save raw case outputs.

Two extractor modes:

- ``--extractor rules`` (default): deterministic baseline, no live model calls.
- ``--extractor llm``: live LLM extraction; provider/model come from the
  environment (EXTRACTOR/LLM_PROVIDER/LLM_MODEL/LLM_BASE_URL/keys). Feasibility
  checks still use the scripted Task 1 mock, so only extraction is measured.

``--split tuning`` runs only tuning cases (prompt tuning must never run the
holdout). Cost fields come from the shared pricing table
(shared-docs/evals/pricing.json, source and retrieval date recorded in report).
Exit code is 0 only when every case passes (1 = some cases failed, report written).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.kb_client import KbAnswer, KbUnavailable
from app.schemas import Citation, Indicator
from app.service import MeetingToScopeService
from app.extractor import build_extractor
from app.store import InMemoryStore
from app.transcript import new_transcript

DEFAULT_CASES = Path(__file__).with_name("cases.json")
DEFAULT_REPORT = Path(__file__).with_name("report-task3.json")
PRICING_TABLE = ROOT.parent / "shared-docs" / "evals" / "pricing.json"


def load_pricing() -> dict:
    if not PRICING_TABLE.exists():
        return {}
    return json.loads(PRICING_TABLE.read_text(encoding="utf-8"))


def cost_block(extractor, pricing: dict) -> dict:
    """Token usage and cost for this run, priced from the shared pricing table."""
    provider = getattr(extractor, "provider", None)
    usage = getattr(provider, "usage_totals", None)
    input_tokens = int(usage.get("input_tokens", 0)) if usage else 0
    output_tokens = int(usage.get("output_tokens", 0)) if usage else 0
    model = getattr(provider, "model_name", None)
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
        basis = "no chat tokens used (offline provider, rules extractor, or run failed before chat)"
    else:
        cost_usd = None
        basis = "model is missing from the pricing table; cost unavailable"
    return {
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
        "cost_basis": basis,
        "provider_reported_cost_usd": getattr(provider, "provider_reported_cost_usd", None),
        "pricing_table": "shared-docs/evals/pricing.json",
        "pricing_source": pricing.get("source"),
        "pricing_retrieved_at": pricing.get("retrieved_at"),
        "embedding_cost_included": False,
        "embedding_cost_note": "Task 3 feasibility uses a scripted Task 1 mock in evals; no embedding cost",
    }


def select_split(cases: list[dict], split: str) -> list[dict]:
    """Filter cases to one split; cases without a split field count as tuning."""
    if split == "all":
        return cases
    selected = [case for case in cases if case.get("split", "tuning") == split]
    if not selected:
        raise SystemExit(f"no cases with split={split!r}")
    return selected


class ScriptedKB:
    def __init__(self, status: str) -> None:
        self.status = status
        self.calls = 0

    def ask(self, question: str) -> KbAnswer:
        self.calls += 1
        if self.status == "unavailable":
            raise KbUnavailable("simulated Task 1 outage")
        citations = [] if self.status != "sufficient" else [
            Citation(article_id="synthetic-kb-article", title="Synthetic fixture", chunk_id="synthetic-c1", score=0.91)
        ]
        confidence = Indicator(level="high" if citations else "none", score=0.91 if citations else 0.0, basis="mock fixture")
        return KbAnswer(
            answer="Synthetic fixture response; not a live Knowledge Brain answer.",
            evidence_status=self.status,
            citations=citations,
            confidence=confidence,
            needs_escalation=self.status != "sufficient",
            request_id=f"eval-{self.calls}",
            model="scripted-fake",
        )


def run_case(case: dict, extractor, settings: Settings) -> dict:
    started = time.perf_counter()
    transcript = new_transcript(
        transcript_id=f"eval-{case['id']}",
        project_id=f"project-{case['id']}",
        title=f"Synthetic evaluation: {case['id']}",
        participants=[{"name": "Dana", "side": "customer"}, {"name": "Sam", "side": "consultant"}],
        segments=case["segments"],
    )
    kb = ScriptedKB(case.get("kb_status", "sufficient"))
    service = MeetingToScopeService(
        store=InMemoryStore(),
        extractor=extractor,
        kb_client=kb,
        settings=settings,
    )
    ingested = service.ingest_transcript(transcript)
    requirements = ingested.requirements
    assessments = service.assess_feasibility(transcript.project_id) if requirements else {}
    proposal = service.generate_proposal(transcript.project_id) if requirements else None

    descriptions = [r.description.lower() for r in requirements]
    terms = case.get("expected_terms", [])
    matched_terms = [term for term in terms if any(term.lower() in description for description in descriptions)]
    segment_ids = {segment.segment_id for segment in transcript.segments}
    attributed = [r for r in requirements if r.source_refs and all(ref.segment_id in segment_ids for ref in r.source_refs)]
    minimum = int(case.get("min_requirements", 1 if terms else 0))
    maximum = case.get("max_requirements")
    problems = []
    if len(matched_terms) != len(terms):
        problems.append(f"matched {len(matched_terms)}/{len(terms)} expected terms")
    if len(requirements) < minimum:
        problems.append(f"requirements below minimum {minimum}")
    if maximum is not None and len(requirements) > int(maximum):
        problems.append(f"requirements above maximum {maximum}")
    if len(attributed) != len(requirements):
        problems.append(f"source attribution {len(attributed)}/{len(requirements)}")
    expected_status = case.get("expected_feasibility")
    actual_statuses = sorted({assessment.status for assessment in assessments.values()})
    if expected_status and expected_status not in actual_statuses:
        problems.append(f"expected feasibility {expected_status}, got {actual_statuses}")

    return {
        "id": case["id"],
        "passed": not problems,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "retry_count": int(getattr(getattr(extractor, "provider", None), "retry_count", 0)),
        "problems": problems,
        "input": {"transcript": transcript.model_dump(mode="json"), "kb_mode": "scripted_mock", "kb_status": kb.status},
        "output": {
            "requirements": [item.model_dump(mode="json") for item in requirements],
            "assessments": {key: value.model_dump(mode="json") for key, value in assessments.items()},
            "proposal": proposal.model_dump(mode="json") if proposal else None,
            "kb_calls": kb.calls,
        },
        "checks": {
            "expected_terms": terms,
            "matched_terms": matched_terms,
            "source_attribution_count": len(attributed),
            "requirement_count": len(requirements),
            "expected_feasibility": expected_status,
            "actual_feasibility_statuses": actual_statuses,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--extractor",
        choices=["rules", "llm"],
        default="rules",
        help="rules = offline deterministic baseline; llm = live model extraction",
    )
    parser.add_argument(
        "--split",
        choices=["all", "tuning", "holdout"],
        default="all",
        help="run only cases from one split; cases without a split field count as tuning",
    )
    args = parser.parse_args()
    case_bytes = args.cases.read_bytes()
    data = json.loads(case_bytes)
    cases = select_split(data["cases"], args.split)
    settings = Settings(extractor=args.extractor)
    extractor = build_extractor(settings)
    results = [run_case(case, extractor, settings) for case in cases]
    passed = sum(result["passed"] for result in results)
    provider = getattr(extractor, "provider", None)
    if args.extractor == "llm":
        mode_text = f"live llm extractor ({getattr(provider, 'model_name', None)})"
        provider_mode = (
            f"llm extractor via {getattr(provider, 'model_name', None)}; "
            "scripted Task 1 mock for feasibility; in-memory persistence"
        )
        harness_mode = "live llm extraction"
    else:
        mode_text = "deterministic rules extractor"
        provider_mode = "deterministic rules extractor + scripted Task 1 mock; zero live model calls"
        harness_mode = "mock/offline"
    pricing = load_pricing()
    run_cost = cost_block(extractor, pricing)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation": f"Task 3 extraction and feasibility behavior; {mode_text}; scripted fake Task 1 responses; in-memory persistence",
        "cases_file_sha256": hashlib.sha256(case_bytes).hexdigest(),
        "split": args.split,
        "extractor": args.extractor,
        "cases_run": len(results),
        "passed": passed,
        "total": len(results),
        "cost": run_cost,
        "metrics": {
            "case_pass_rate": passed / len(results) if results else 0,
            "median_latency_ms": statistics.median(r["latency_ms"] for r in results) if results else None,
            "p95_latency_ms": sorted(r["latency_ms"] for r in results)[max(0, math.ceil(len(results) * .95) - 1)] if results else None,
            "model_tokens": {"input_tokens": run_cost["input_tokens"], "output_tokens": run_cost["output_tokens"]},
            "retry_count": sum(r["retry_count"] for r in results),
            "failure_causes": {result["id"]: "; ".join(result["problems"]) for result in results if not result["passed"]},
            "harness_mode": harness_mode,
            "failures": len(results) - passed,
            "provider_mode": provider_mode,
        },
        "results": results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for result in results:
        print(f"{'PASS' if result['passed'] else 'FAIL'} {result['id']}")
        for problem in result["problems"]:
            print(f"  - {problem}")
    print(
        f"{passed}/{len(results)} cases passed; "
        f"cost_usd={run_cost['cost_usd']} "
        f"(input_tokens={run_cost['input_tokens']}, output_tokens={run_cost['output_tokens']}); "
        f"raw results: {args.report}"
    )
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
