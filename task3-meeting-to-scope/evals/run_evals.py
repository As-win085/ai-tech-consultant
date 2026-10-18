"""Run the frozen Task 3 synthetic eval set and save raw case outputs."""

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
from app.extractor import RuleBasedExtractor
from app.store import InMemoryStore
from app.transcript import new_transcript

DEFAULT_CASES = Path(__file__).with_name("cases.json")
DEFAULT_REPORT = Path(__file__).with_name("report-task3.json")


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


def run_case(case: dict) -> dict:
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
        extractor=RuleBasedExtractor(),
        kb_client=kb,
        settings=Settings(extractor="rules"),
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
    args = parser.parse_args()
    case_bytes = args.cases.read_bytes()
    data = json.loads(case_bytes)
    results = [run_case(case) for case in data["cases"]]
    passed = sum(result["passed"] for result in results)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation": "Task 3 extraction and feasibility behavior; deterministic rules extractor; scripted fake Task 1 responses; in-memory persistence",
        "cases_file_sha256": hashlib.sha256(case_bytes).hexdigest(),
        "passed": passed,
        "total": len(results),
        "metrics": {
            "case_pass_rate": passed / len(results) if results else 0,
            "median_latency_ms": statistics.median(r["latency_ms"] for r in results) if results else None,
            "p95_latency_ms": sorted(r["latency_ms"] for r in results)[max(0, math.ceil(len(results) * .95) - 1)] if results else None,
            "model_tokens": None,
            "retry_count": 0,
        "failure_causes": {result["id"]: "; ".join(result["problems"]) for result in results if not result["passed"]},
        "harness_mode": "mock/offline",
            "failures": len(results) - passed,
            "provider_mode": "deterministic rules extractor + scripted Task 1 mock; zero live model calls",
        },
        "results": results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for result in results:
        print(f"{'PASS' if result['passed'] else 'FAIL'} {result['id']}")
        for problem in result["problems"]:
            print(f"  - {problem}")
    print(f"{passed}/{len(results)} cases passed; raw results: {args.report}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
