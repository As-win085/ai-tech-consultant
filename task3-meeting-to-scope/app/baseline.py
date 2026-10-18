"""Baseline management and change detection.

A baseline is an approved snapshot of a project's requirements. When a follow-up
transcript arrives, its requirements are compared against the baseline snapshot to
produce a reviewable change summary. The baseline is never silently overwritten:
changes are proposed and only an authorized approval creates a new version.

Requirement ids are transcript-scoped, so requirements are matched across
transcripts by *content similarity*, not by id. Each change is classified as added,
removed, modified, clarified, or unresolved, and genuine scope creep (new/changed
committed scope) is flagged separately from mere clarification or duplicate noise.
"""

from __future__ import annotations

import re

from app.extractor import _number_topic
from app.schemas import (
    Baseline,
    BaselineUpdateProposal,
    ChangeSummary,
    Indicator,
    Requirement,
    ScopeChange,
    utcnow,
)

_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "our", "your", "you", "we",
    "they", "will", "would", "should", "must", "need", "needs", "want", "also",
    "able", "support", "supports", "have", "has", "into", "from", "about",
    "when", "then", "than", "them", "there", "their", "been", "being", "are",
    "was", "were", "can", "could", "not", "but", "all", "any", "some", "more",
    "very", "just", "like", "make", "made", "get", "got", "use", "using",
    "site", "system", "platform", "please", "want", "needed", "make",
}

_IN_SCOPE_TYPES = {"functional", "integration", "non_functional", "constraint"}
_MATCH_THRESHOLD = 0.5


_NUM_RE = re.compile(r"\d[\d,]*k?", re.IGNORECASE)


def _tokens(text: str) -> set[str]:
    normalized = _NUM_RE.sub(" # ", text.lower())
    words = re.findall(r"[a-z#]+", normalized)
    return {w for w in words if (len(w) > 2 or w == "#") and w not in _STOPWORDS}


def _similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _match_score(a: str, b: str) -> float:
    """Similarity with a boost when both mention the same scale-topic noun.

    Numbers are normalised to ``#`` so a re-stated scale (e.g. "50,000 members"
    vs "100,000 members") is treated as the *same* requirement that changed,
    rather than an unrelated add + remove.
    """
    score = _similarity(a, b)
    _, topic_a = _number_topic(a)
    _, topic_b = _number_topic(b)
    if topic_a and topic_b and topic_a == topic_b:
        score = max(score, 0.7)
    return score


def create_baseline(
    *,
    project_id: str,
    requirements: list[Requirement],
    version: int,
    proposal_id: str | None = None,
    note: str | None = None,
    supersedes_version: int | None = None,
    approved_by: str | None = None,
) -> Baseline:
    approved_at = utcnow() if approved_by else None
    return Baseline(
        baseline_id=f"{project_id}-B{version:02d}",
        project_id=project_id,
        version=version,
        status="approved" if approved_by else "proposed",
        proposal_id=proposal_id,
        requirement_ids=[r.requirement_id for r in requirements],
        requirement_snapshot=[r.model_copy(deep=True) for r in requirements],
        note=note,
        created_at=utcnow(),
        approved_at=approved_at,
        approved_by=approved_by,
        supersedes_version=supersedes_version,
    )


def _best_match(new_req: Requirement, candidates: list[Requirement]) -> tuple[Requirement | None, float]:
    best: Requirement | None = None
    best_score = 0.0
    for cand in candidates:
        score = _match_score(new_req.description, cand.description)
        if score > best_score:
            best, best_score = cand, score
    return best, best_score


def _scope_creep_for(change_type: str, new_req: Requirement, *, numeric_increase: bool) -> bool:
    if change_type == "added":
        return new_req.statement_kind in {"explicit", "inferred"} and new_req.requirement_type in _IN_SCOPE_TYPES
    if change_type == "modified":
        return numeric_increase or new_req.requirement_type == "integration"
    return False


def compute_change_summary(
    baseline: Baseline,
    new_requirements: list[Requirement],
    *,
    transcript_id: str,
) -> ChangeSummary:
    snapshot = list(baseline.requirement_snapshot)
    matched_baseline_ids: set[str] = set()
    changes: list[ScopeChange] = []
    counter = 0

    def _next_id() -> str:
        nonlocal counter
        counter += 1
        return f"{baseline.project_id}-C{counter:03d}"

    for new_req in new_requirements:
        base_req, score = _best_match(new_req, [s for s in snapshot if s.requirement_id not in matched_baseline_ids])
        if base_req is None or score < _MATCH_THRESHOLD:
            change_type = "unresolved" if new_req.statement_kind == "uncertain" else "added"
            changes.append(
                _change(
                    baseline,
                    _next_id(),
                    transcript_id,
                    change_type,
                    new_req,
                    base_req=None,
                    summary=f"{change_type.capitalize()}: {new_req.description}",
                    rationale="present in the follow-up transcript only",
                    scope_creep=_scope_creep_for(change_type, new_req, numeric_increase=False),
                )
            )
            continue

        matched_baseline_ids.add(base_req.requirement_id)
        new_num, new_topic = _number_topic(new_req.description)
        old_num, old_topic = _number_topic(base_req.description)
        numeric_increase = bool(new_num and old_num and new_topic == old_topic and int(new_num) > int(old_num))
        numeric_change = bool(new_num and old_num and new_topic == old_topic and new_num != old_num)

        if new_req.description.strip().lower() == base_req.description.strip().lower():
            if base_req.status == "needs_clarification" and new_req.status != "needs_clarification":
                change_type, field, old_v, new_v = "clarified", "status", base_req.status, new_req.status
                summary = f"Clarified: {new_req.description}"
            else:
                continue
        elif numeric_change:
            change_type, field = "modified", "scale"
            old_v, new_v = f"{old_num} {old_topic}", f"{new_num} {new_topic}"
            summary = f"Modified scale: {old_v} -> {new_v}"
        elif new_req.priority != base_req.priority:
            change_type, field = "modified", "priority"
            old_v, new_v = base_req.priority, new_req.priority
            summary = f"Priority changed: {old_v} -> {new_v}"
        else:
            change_type, field = "modified", "description"
            old_v, new_v = base_req.description, new_req.description
            summary = "Modified wording/wording-level change"

        changes.append(
            _change(
                baseline,
                _next_id(),
                transcript_id,
                change_type,
                new_req,
                base_req=base_req,
                summary=summary,
                rationale="compared against baseline snapshot",
                field=field,
                old_value=old_v,
                new_value=new_v,
                scope_creep=_scope_creep_for(change_type, new_req, numeric_increase=numeric_increase),
            )
        )

    for base_req in snapshot:
        if base_req.requirement_id in matched_baseline_ids:
            continue
        changes.append(
            _change(
                baseline,
                _next_id(),
                transcript_id,
                "removed",
                None,
                base_req=base_req,
                summary=f"Removed: {base_req.description}",
                rationale="present in the baseline but absent from the follow-up transcript",
            )
        )

    counts: dict[str, int] = {}
    for c in changes:
        counts[c.change_type] = counts.get(c.change_type, 0) + 1

    return ChangeSummary(
        project_id=baseline.project_id,
        from_baseline_version=baseline.version,
        to_transcript_id=transcript_id,
        generated_at=utcnow(),
        counts=counts,
        scope_creep_count=sum(1 for c in changes if c.scope_creep),
        changes=changes,
    )


def _change(
    baseline: Baseline,
    change_id: str,
    transcript_id: str,
    change_type: str,
    new_req: Requirement | None,
    *,
    base_req: Requirement | None,
    summary: str,
    rationale: str,
    field: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    scope_creep: bool = False,
) -> ScopeChange:
    confidence = Indicator(level="medium", score=0.6, basis="content-similarity match against baseline")
    if change_type == "unresolved":
        confidence = Indicator(level="low", score=0.4, basis="statement is vague/unresolved")
    return ScopeChange(
        change_id=change_id,
        project_id=baseline.project_id,
        from_baseline_version=baseline.version,
        to_transcript_id=transcript_id,
        change_type=change_type,
        requirement_id=(new_req.requirement_id if new_req else (base_req.requirement_id if base_req else "")),
        baseline_requirement_id=(base_req.requirement_id if base_req else None),
        summary=summary,
        rationale=rationale,
        field=field,
        old_value=old_value,
        new_value=new_value,
        new_source_refs=list(new_req.source_refs) if new_req else [],
        baseline_source_refs=list(base_req.source_refs) if base_req else [],
        confidence=confidence,
        scope_creep=scope_creep,
        estimate_impact="may increase effort" if scope_creep else None,
        status="proposed",
    )


def build_baseline_update_proposal(summary: ChangeSummary, baseline: Baseline) -> BaselineUpdateProposal:
    return BaselineUpdateProposal(
        project_id=baseline.project_id,
        from_baseline_version=baseline.version,
        to_transcript_id=summary.to_transcript_id,
        proposed_requirement_ids=sorted({c.requirement_id for c in summary.changes if c.requirement_id}),
        proposed_version=baseline.version + 1,
        status="proposed",
        rationale=(
            f"{len(summary.changes)} change(s) detected "
            f"({summary.scope_creep_count} flagged as scope creep). "
            "Awaiting explicit authorization before a new baseline is approved."
        ),
        changes=list(summary.changes),
        created_at=utcnow(),
    )
