"""Proposal / statement-of-work generation.

The proposal is a deterministic transformation of extracted requirements plus
feasibility assessments. Every scope statement carries ``requirement_ids`` so it is
traceable to transcript passages. Estimates are explicitly preliminary (units +
rationale + low/high uncertainty + conditions) and no prices or calendar dates are
invented — none were agreed in the transcripts.

Outcomes flagged by the Knowledge Brain as ``not_supported_by_available_evidence``
are surfaced as risks requiring validation, never dropped or silently approved.
"""

from __future__ import annotations

from app.schemas import (
    Deliverable,
    Estimate,
    FeasibilityAssessment,
    Milestone,
    OpenQuestion,
    Proposal,
    Requirement,
    Risk,
    ScopeItem,
    Transcript,
    utcnow,
)

_IN_SCOPE_TYPES = {"functional", "integration", "non_functional", "constraint"}

_PRELIMINARY_CONDITIONS = [
    "Estimates are preliminary and must be validated before any commitment.",
    "Assumes access to a staging environment for integration work.",
    "Assumes timely availability of customer stakeholders for clarification.",
]

_DEFAULT_EXCLUSIONS = [
    "Third-party license, hosting, and subscription costs are excluded unless stated.",
    "Content authoring, copywriting, and graphic design are excluded unless stated.",
    "Ongoing support and maintenance after handover are excluded unless stated.",
]


def _estimate_for(items: list[Requirement], item_label: str) -> Estimate:
    count = max(1, len(items))
    low = float(count) * 4.0
    high = float(count) * 10.0
    return Estimate(
        item=item_label,
        unit="hours",
        low=low,
        high=high,
        rationale=(
            f"Preliminary range based on {len(items)} requirement(s); "
            "low/high reflect uncertainty, not a committed effort figure."
        ),
        dependencies=sorted({d for r in items for d in r.dependencies}),
        provisional=True,
        conditions=list(_PRELIMINARY_CONDITIONS),
        requirement_ids=[r.requirement_id for r in items],
    )


def build_proposal(
    transcript: Transcript,
    requirements: list[Requirement],
    assessments: dict[str, FeasibilityAssessment],
    *,
    version: int = 1,
    title: str | None = None,
    based_on_baseline_version: int | None = None,
) -> Proposal:
    in_scope_reqs = [
        r
        for r in requirements
        if r.requirement_type in _IN_SCOPE_TYPES and r.statement_kind in {"explicit", "inferred"}
    ]
    proposed_reqs = [r for r in requirements if r.statement_kind == "proposed_solution"]
    assumption_reqs = [r for r in requirements if r.requirement_type == "assumption"]
    open_q_reqs = [r for r in requirements if r.requirement_type == "open_question" or r.status == "needs_clarification"]

    in_scope = [
        ScopeItem(description=r.description, requirement_ids=[r.requirement_id], rationale=r.rationale)
        for r in in_scope_reqs
    ]
    out_of_scope = [
        ScopeItem(
            description=r.description,
            requirement_ids=[r.requirement_id],
            rationale="consultant proposal, not yet agreed by the customer",
        )
        for r in proposed_reqs
    ]

    # Deliverables grouped by requirement type.
    deliverable_groups: dict[str, list[Requirement]] = {}
    for r in in_scope_reqs:
        deliverable_groups.setdefault(r.requirement_type, []).append(r)
    deliverables = [
        Deliverable(
            name=_deliverable_name(type_, reqs),
            description=", ".join(r.description for r in reqs[:3]),
            requirement_ids=[r.requirement_id for r in reqs],
        )
        for type_, reqs in deliverable_groups.items()
    ]

    assumptions = [r.description for r in assumption_reqs]
    dependencies = sorted({d for r in requirements for d in r.dependencies})

    risks: list[Risk] = []
    for r in requirements:
        for risk_text in r.risks:
            risks.append(Risk(description=risk_text, severity="unspecified", requirement_ids=[r.requirement_id]))
    for rid, assessment in assessments.items():
        if assessment.status == "not_supported_by_available_evidence":
            risks.append(
                Risk(
                    description=(
                        "No supporting evidence found in the knowledge base for this "
                        "requirement; feasibility must be validated."
                    ),
                    severity="medium",
                    mitigation="Validate against documentation or a proof of concept.",
                    requirement_ids=[rid],
                )
            )
        elif assessment.status in {"conflicting_evidence"}:
            risks.append(
                Risk(
                    description="Conflicting evidence in the knowledge base.",
                    severity="high",
                    mitigation="Resolve the conflict with the customer before committing.",
                    requirement_ids=[rid],
                )
            )
        elif assessment.status == "assessment_unavailable":
            risks.append(
                Risk(
                    description="Feasibility could not be assessed (knowledge base unavailable).",
                    severity="medium",
                    mitigation="Re-run the assessment when the knowledge base is available.",
                    requirement_ids=[rid],
                )
            )

    open_questions = [
        OpenQuestion(question=r.description, requirement_ids=[r.requirement_id], blocking=(r.statement_kind == "uncertain"))
        for r in open_q_reqs
    ]

    acceptance_criteria = sorted({ac for r in requirements for ac in r.acceptance_criteria})
    business_objectives = sorted({r.rationale for r in requirements if r.rationale})

    milestones: list[Milestone] = []
    if open_q_reqs:
        milestones.append(
            Milestone(
                milestone_id=f"{transcript.project_id}-M1",
                name="Discovery & clarification",
                objective="Resolve open questions, assumptions, and conflicts.",
                deliverables=["Clarified requirements"],
                requirement_ids=[r.requirement_id for r in open_q_reqs],
                estimate=_estimate_for(open_q_reqs, "Clarification effort"),
            )
        )
    if in_scope_reqs:
        milestones.append(
            Milestone(
                milestone_id=f"{transcript.project_id}-M{len(milestones) + 1}",
                name="Core build",
                objective="Deliver the agreed in-scope functionality.",
                deliverables=[d.name for d in deliverables],
                depends_on=[m.milestone_id for m in milestones],
                requirement_ids=[r.requirement_id for r in in_scope_reqs],
                estimate=_estimate_for(in_scope_reqs, "Core build effort"),
            )
        )
    integration_reqs = [r for r in requirements if r.requirement_type == "integration"]
    if integration_reqs:
        milestones.append(
            Milestone(
                milestone_id=f"{transcript.project_id}-M{len(milestones) + 1}",
                name="Integration & validation",
                objective="Implement and validate integrations against the knowledge base.",
                deliverables=["Integrated systems", "Validation report"],
                depends_on=[m.milestone_id for m in milestones],
                requirement_ids=[r.requirement_id for r in integration_reqs],
                estimate=_estimate_for(integration_reqs, "Integration effort"),
            )
        )

    estimates = [m.estimate for m in milestones if m.estimate is not None]
    all_ids = [r.requirement_id for r in requirements]

    overview = (
        f"Proposal for project '{transcript.project_id}' derived from transcript "
        f"{transcript.transcript_id} ({transcript.meeting_date or 'date unknown'}). "
        f"It covers {len(in_scope_reqs)} in-scope requirement(s), "
        f"{len(proposed_reqs)} consultant proposal(s), and "
        f"{len(open_q_reqs)} item(s) requiring clarification."
    )

    return Proposal(
        proposal_id=f"{transcript.project_id}-P{version:02d}",
        project_id=transcript.project_id,
        version=version,
        status="draft",
        title=title or f"Statement of Work — {transcript.project_id}",
        overview=overview,
        business_objectives=business_objectives,
        in_scope=in_scope,
        out_of_scope=out_of_scope,
        deliverables=deliverables,
        assumptions=assumptions,
        dependencies=dependencies,
        risks=risks,
        open_questions=open_questions,
        acceptance_criteria=acceptance_criteria,
        milestones=milestones,
        estimates=estimates,
        exclusions=list(_DEFAULT_EXCLUSIONS),
        estimate_conditions=list(_PRELIMINARY_CONDITIONS),
        requirement_ids=all_ids,
        based_on_baseline_version=based_on_baseline_version,
        created_at=utcnow(),
    )


def _deliverable_name(req_type: str, reqs: list[Requirement]) -> str:
    mapping = {
        "functional": "Core functionality",
        "integration": "Integrations",
        "non_functional": "Non-functional requirements (performance/security)",
        "constraint": "Constraints & compliance",
    }
    base = mapping.get(req_type, "Deliverable")
    return f"{base} ({len(reqs)})"


def render_proposal_markdown(proposal: Proposal) -> str:
    """Render a stored proposal as Markdown. Markdown is a view, not the source of truth."""
    lines: list[str] = []
    lines.append(f"# {proposal.title}")
    lines.append("")
    lines.append(f"- Proposal ID: `{proposal.proposal_id}`")
    lines.append(f"- Project: `{proposal.project_id}`")
    lines.append(f"- Version: {proposal.version}")
    lines.append(f"- Status: **{proposal.status}**")
    if proposal.based_on_baseline_version is not None:
        lines.append(f"- Based on baseline version: {proposal.based_on_baseline_version}")
    lines.append("")
    lines.append("## Overview")
    lines.append(proposal.overview or "_(none)_")
    lines.append("")

    def _scope_section(name: str, items: list[ScopeItem]) -> None:
        lines.append(f"## {name}")
        if not items:
            lines.append("_(none)_")
        for item in items:
            trace = f" _(refs: {', '.join(item.requirement_ids)})_" if item.requirement_ids else ""
            lines.append(f"- {item.description}{trace}")
        lines.append("")

    if proposal.business_objectives:
        lines.append("## Business objectives")
        for obj in proposal.business_objectives:
            lines.append(f"- {obj}")
        lines.append("")

    _scope_section("In scope", proposal.in_scope)
    _scope_section("Out of scope", proposal.out_of_scope)

    lines.append("## Deliverables")
    if not proposal.deliverables:
        lines.append("_(none)_")
    for d in proposal.deliverables:
        trace = f" _(refs: {', '.join(d.requirement_ids)})_" if d.requirement_ids else ""
        lines.append(f"- **{d.name}**: {d.description or ''}{trace}")
    lines.append("")

    lines.append("## Assumptions")
    lines.extend(f"- {a}" for a in proposal.assumptions) if proposal.assumptions else lines.append("_(none)_")
    lines.append("")

    lines.append("## Dependencies")
    lines.extend(f"- {d}" for d in proposal.dependencies) if proposal.dependencies else lines.append("_(none)_")
    lines.append("")

    lines.append("## Risks")
    if not proposal.risks:
        lines.append("_(none)_")
    for r in proposal.risks:
        trace = f" _(refs: {', '.join(r.requirement_ids)})_" if r.requirement_ids else ""
        lines.append(f"- ({r.severity}) {r.description}{trace}")
    lines.append("")

    lines.append("## Open questions")
    if not proposal.open_questions:
        lines.append("_(none)_")
    for q in proposal.open_questions:
        blocking = " **[blocking]**" if q.blocking else ""
        lines.append(f"- {q.question}{blocking}")
    lines.append("")

    lines.append("## Acceptance criteria")
    lines.extend(f"- {ac}" for ac in proposal.acceptance_criteria) if proposal.acceptance_criteria else lines.append(
        "_(none stated in the transcripts — not invented)_"
    )
    lines.append("")

    lines.append("## Milestones")
    for m in proposal.milestones:
        deps = f" (depends on: {', '.join(m.depends_on)})" if m.depends_on else ""
        lines.append(f"- **{m.name}**{deps}: {m.objective}")
    if not proposal.milestones:
        lines.append("_(none)_")
    lines.append("")

    lines.append("## Preliminary estimates")
    lines.append(
        "_Estimates are preliminary, expressed with uncertainty ranges, and are not "
        "prices or committed dates._"
    )
    for e in proposal.estimates:
        lines.append(
            f"- {e.item}: {e.low:g}–{e.high:g} {e.unit} (provisional={e.provisional}). {e.rationale}"
        )
    if not proposal.estimates:
        lines.append("_(none)_")
    lines.append("")

    lines.append("## Exclusions & estimate conditions")
    for ex in proposal.exclusions:
        lines.append(f"- {ex}")
    for cond in proposal.estimate_conditions:
        lines.append(f"- Condition: {cond}")
    lines.append("")

    lines.append("## Traceability")
    lines.append(
        f"All {len(proposal.requirement_ids)} requirements are traceable to transcript "
        "segments; see each requirement's source references."
    )
    return "\n".join(lines)
