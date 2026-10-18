"""Feasibility assessment of requirements against the Knowledge Brain.

Feasibility is answered *only* from Task 1 evidence — the agent never asserts that
something is impossible merely because the documentation is silent. Each outcome is
one of the explicit :data:`~app.schemas.FeasibilityStatus` values:

* ``supported_by_knowledge`` — KB returned sufficient evidence with good confidence.
* ``potentially_feasible_needs_validation`` — evidence exists but is weak/partial,
  or the requirement is a consultant proposal rather than a customer commitment.
* ``not_supported_by_available_evidence`` — KB answers but finds insufficient
  evidence; the docs are silent, which is *not* proof of impossibility.
* ``conflicting_evidence`` — KB reports conflicting evidence.
* ``requires_customer_clarification`` — the requirement is an open question or an
  assumption; feasibility cannot be assessed without the customer.
* ``assessment_unavailable`` — the KB call failed (timeout/unavailable/malformed);
  no feasibility claim is made.

Citations from the KB response are copied verbatim. If a call fails, no citations
are fabricated and the failure is recorded in ``error``.
"""

from __future__ import annotations

from app.kb_client import KbAnswer, KbError, KnowledgeBrainClient
from app.schemas import FeasibilityAssessment, Requirement, RequirementType, utcnow

_CLARIFICATION_TYPES: set[RequirementType] = {"open_question", "assumption"}


def build_question(requirement: Requirement) -> str:
    """Turn a requirement into a knowledge-base question."""
    return (
        "Is the following capability supported in Brilliant Directories, and how "
        "would it be implemented? " + requirement.description
    )


def _status_from_answer(requirement: Requirement, answer: KbAnswer) -> tuple[str, str]:
    """Map a KB answer to a feasibility status and a human-readable basis."""
    if answer.evidence_status == "conflicting":
        return "conflicting_evidence", "knowledge base reports conflicting evidence"
    if answer.evidence_status == "unavailable":
        return "assessment_unavailable", "knowledge base could not retrieve evidence"
    if answer.evidence_status == "insufficient":
        return (
            "not_supported_by_available_evidence",
            "knowledge base found no sufficient evidence; docs are silent (not proof of impossibility)",
        )
    # sufficient
    level = answer.confidence.level if answer.confidence else "none"
    if requirement.statement_kind == "proposed_solution":
        return "potentially_feasible_needs_validation", "consultant proposal; evidence supports a related capability"
    if level in {"high", "medium"} and answer.citations:
        return "supported_by_knowledge", f"knowledge base evidence ({level} confidence)"
    return "potentially_feasible_needs_validation", "weak or partial evidence; needs validation"


def assess_requirement(requirement: Requirement, client: KnowledgeBrainClient) -> FeasibilityAssessment:
    """Assess a single requirement, never fabricating an outcome."""
    assessment = FeasibilityAssessment(
        requirement_id=requirement.requirement_id,
        project_id=requirement.project_id,
        question=build_question(requirement),
        assessed_at=utcnow(),
    )

    if requirement.requirement_type in _CLARIFICATION_TYPES or requirement.statement_kind == "uncertain":
        assessment.status = "requires_customer_clarification"
        assessment.basis = "requirement is an open question, assumption, or too vague to assess"
        return assessment

    try:
        answer = client.ask(assessment.question)
    except KbError as exc:
        assessment.status = "assessment_unavailable"
        assessment.basis = "knowledge base call failed; no feasibility claim made"
        assessment.error = f"{exc.__class__.__name__}: {exc}"
        return assessment

    status, basis = _status_from_answer(requirement, answer)
    assessment.status = status
    assessment.basis = basis
    assessment.evidence_status = answer.evidence_status
    assessment.answer = answer.answer or None
    assessment.citations = list(answer.citations)
    assessment.kb_request_id = answer.request_id
    assessment.kb_model = answer.model
    return assessment


def assess_requirements(
    requirements: list[Requirement], client: KnowledgeBrainClient
) -> dict[str, FeasibilityAssessment]:
    """Assess every requirement; returns a mapping keyed by requirement id."""
    return {req.requirement_id: assess_requirement(req, client) for req in requirements}
