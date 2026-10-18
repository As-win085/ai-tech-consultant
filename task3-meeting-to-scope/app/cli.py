"""Command-line interface for the Meeting-to-Scope Agent.

Examples::

    python -m app.cli ingest data/transcripts/mtg-001-kickoff.json
    python -m app.cli requirements brightpath-directory
    python -m app.cli assess brightpath-directory
    python -m app.cli proposal brightpath-directory
    python -m app.cli baseline brightpath-directory --approve-by pm@example.com
    python -m app.cli review <requirement_id> --status approved --actor pm@example.com

The CLI uses the PostgreSQL store when ``DATABASE_URL`` is set (so state persists
between commands); otherwise it uses an in-memory store and prints a notice.
"""

from __future__ import annotations

import argparse
import json
import sys

from app.config import load_settings
from app.kb_client import build_kb_client
from app.service import MeetingToScopeService, build_default_service, build_postgres_service
from app.transcript import TranscriptError, load_transcript_file


def _build_service() -> MeetingToScopeService:
    settings = load_settings()
    kb = None
    try:
        kb = build_kb_client(settings)
    except Exception:
        kb = None
    if settings.database_url:
        return build_postgres_service(settings=settings, kb_client=kb)
    print("[note] DATABASE_URL not set: using an in-memory store (state is ephemeral).", file=sys.stderr)
    return build_default_service(settings=settings, kb_client=kb)


def cmd_ingest(args: argparse.Namespace) -> int:
    service = _build_service()
    settings = service.settings
    try:
        transcript = load_transcript_file(args.file, max_chars=settings.max_transcript_chars)
    except TranscriptError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    result = service.ingest_transcript(transcript)
    print(f"transcript: {result.transcript.transcript_id} (idempotent={result.idempotent})")
    for req in result.requirements:
        print(f"  {req.requirement_id}  {req.requirement_type:13} {req.statement_kind:17} {req.description}")
    if result.warnings:
        print("warnings:")
        for w in result.warnings:
            print(f"  - {w}")
    if result.change_summary:
        print("change summary:", json.dumps(result.change_summary.counts))
        print("scope creep count:", result.change_summary.scope_creep_count)
    return 0


def cmd_requirements(args: argparse.Namespace) -> int:
    service = _build_service()
    reqs = service.list_requirements(args.project_id)
    for req in reqs:
        print(f"{req.requirement_id}  {req.status:18} {req.requirement_type:13} {req.description[:70]}")
    return 0


def cmd_assess(args: argparse.Namespace) -> int:
    service = _build_service()
    assessments = service.assess_feasibility(args.project_id)
    for rid, a in assessments.items():
        print(f"{rid}  {a.status:38} {a.basis}")
    return 0


def cmd_proposal(args: argparse.Namespace) -> int:
    service = _build_service()
    proposal = service.generate_proposal(args.project_id)
    print(f"proposal {proposal.proposal_id} v{proposal.version} status={proposal.status}")
    print(f"  in_scope={len(proposal.in_scope)} out_of_scope={len(proposal.out_of_scope)} "
          f"milestones={len(proposal.milestones)} estimates={len(proposal.estimates)} "
          f"risks={len(proposal.risks)} open_questions={len(proposal.open_questions)}")
    return 0


def cmd_baseline(args: argparse.Namespace) -> int:
    service = _build_service()
    baseline = service.create_baseline(args.project_id, approved_by=args.approve_by, note=args.note)
    print(f"baseline {baseline.baseline_id} v{baseline.version} status={baseline.status} "
          f"requirements={len(baseline.requirement_snapshot)}")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    service = _build_service()
    req = service.review_requirement(args.requirement_id, to_status=args.status, actor=args.actor, reason=args.reason)
    print(f"{req.requirement_id} -> {req.status}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli", description="Meeting-to-Scope Agent CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Ingest a transcript JSON file")
    p_ingest.add_argument("file")
    p_ingest.set_defaults(func=cmd_ingest)

    p_req = sub.add_parser("requirements", help="List requirements for a project")
    p_req.add_argument("project_id")
    p_req.set_defaults(func=cmd_requirements)

    p_assess = sub.add_parser("assess", help="Assess feasibility for a project's requirements")
    p_assess.add_argument("project_id")
    p_assess.set_defaults(func=cmd_assess)

    p_prop = sub.add_parser("proposal", help="Generate a draft proposal")
    p_prop.add_argument("project_id")
    p_prop.set_defaults(func=cmd_proposal)

    p_base = sub.add_parser("baseline", help="Create (and optionally approve) a baseline")
    p_base.add_argument("project_id")
    p_base.add_argument("--approve-by", default=None)
    p_base.add_argument("--note", default=None)
    p_base.set_defaults(func=cmd_baseline)

    p_review = sub.add_parser("review", help="Review a single requirement")
    p_review.add_argument("requirement_id")
    p_review.add_argument("--status", required=True, choices=["approved", "rejected", "needs_clarification", "pending_review"])
    p_review.add_argument("--actor", required=True)
    p_review.add_argument("--reason", default=None)
    p_review.set_defaults(func=cmd_review)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
