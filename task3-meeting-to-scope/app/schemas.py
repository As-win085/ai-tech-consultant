"""Pydantic domain and API schemas for the Meeting-to-Scope Agent.

These are the validated contracts for requirement extraction, feasibility
assessment, proposals, baselines, and scope changes. They are shared by the
service layer, the persistence layer, the FastAPI app (via OpenAPI), and the
evaluation harness.

Design notes
------------
* ``Indicator`` is an explicit *heuristic* confidence indicator, not a calibrated
  probability (see ``basis``). This mirrors the Knowledge Brain's confidence
  contract.
* ``statement_kind`` records whether a statement is explicitly stated by the
  customer, inferred by the agent, uncertain/needs clarification, or a proposed
  solution rather than an agreed requirement.
* Source references (``SourceRef``) preserve an exact supporting quote plus the
  stable ``segment_id`` (and speaker/timestamp when available).
"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --- Enumerations (documented taxonomies) ------------------------------------

RequirementType = Literal[
    "functional",
    "non_functional",
    "integration",
    "constraint",
    "assumption",
    "open_question",
]
Priority = Literal["high", "medium", "low", "unspecified"]
StatementKind = Literal["explicit", "inferred", "uncertain", "proposed_solution"]
RequirementStatus = Literal["pending_review", "approved", "rejected", "needs_clarification"]
ScopeDisposition = Literal["in_scope", "out_of_scope", "undecided"]
ConfidenceLevel = Literal["high", "medium", "low", "none"]
FeasibilityStatus = Literal[
    "supported_by_knowledge",
    "potentially_feasible_needs_validation",
    "not_supported_by_available_evidence",
    "conflicting_evidence",
    "requires_customer_clarification",
    "assessment_unavailable",
    "not_assessed",
]
ProposalStatus = Literal["draft", "in_review", "approved", "rejected", "superseded"]
BaselineStatus = Literal["proposed", "approved", "superseded"]
ChangeType = Literal[
    "added",
    "removed",
    "modified",
    "clarified",
    "unresolved",
    "unchanged",
]
EstimateUnit = Literal["hours", "days", "points"]
ScopeChangeStatus = Literal["proposed", "accepted", "rejected", "needs_review"]

REQUIREMENT_TYPES = (
    "functional",
    "non_functional",
    "integration",
    "constraint",
    "assumption",
    "open_question",
)

# --- Shared value objects ----------------------------------------------------


class Indicator(BaseModel):
    """Heuristic confidence indicator (NOT a calibrated probability)."""

    level: ConfidenceLevel
    score: float = Field(ge=0.0, le=1.0)
    basis: str


class SourceRef(BaseModel):
    """A stable reference to an exact supporting transcript passage."""

    transcript_id: str
    segment_id: str
    speaker: str | None = None
    timestamp: str | None = None
    quote: str

    @field_validator("quote")
    @classmethod
    def _quote_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("source reference quote must not be blank")
        return value.strip()


class Citation(BaseModel):
    """A knowledge-base citation preserved verbatim from the Task 1 response."""

    article_id: str | None = None
    title: str | None = None
    canonical_url: str | None = None
    heading: str | None = None
    chunk_id: str | None = None
    score: float | None = None


# --- Transcript --------------------------------------------------------------


class Participant(BaseModel):
    name: str
    role: str | None = None
    organization: str | None = None
    side: Literal["customer", "consultant", "other"] = "other"


class TranscriptSegment(BaseModel):
    segment_id: str = ""
    speaker: str | None = None
    timestamp: str | None = None
    text: str

    @field_validator("text")
    @classmethod
    def _text_not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("segment text must not be blank")
        return value.strip()


class ProjectContext(BaseModel):
    project_id: str
    name: str
    customer: str | None = None
    consultant: str | None = None
    product: str | None = None


class Transcript(BaseModel):
    transcript_id: str
    project_id: str
    title: str = ""
    meeting_date: str | None = None
    sequence: int = 1
    parent_transcript_id: str | None = None
    participants: list[Participant] = Field(default_factory=list)
    segments: list[TranscriptSegment] = Field(default_factory=list)
    content_hash: str = ""

    def combined_text(self) -> str:
        return "\n".join(seg.text for seg in self.segments)


# --- Requirements ------------------------------------------------------------


class Requirement(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    requirement_id: str
    project_id: str
    transcript_id: str
    description: str
    requirement_type: RequirementType = "functional"
    statement_kind: StatementKind = "explicit"
    priority: Priority = "unspecified"
    rationale: str | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)
    confidence: Indicator = Field(
        default_factory=lambda: Indicator(level="low", score=0.0, basis="not set")
    )
    status: RequirementStatus = "pending_review"
    scope: ScopeDisposition = "undecided"
    extraction_status: Literal["extracted", "needs_review", "failed"] = "extracted"
    conflicts_with: list[str] = Field(default_factory=list)
    supersedes: str | None = None
    notes: str | None = None
    revision: int = 1
    created_at: str | None = None
    updated_at: str | None = None

    def source_segment_ids(self) -> list[str]:
        return [ref.segment_id for ref in self.source_refs]


# --- Feasibility -------------------------------------------------------------


class FeasibilityAssessment(BaseModel):
    requirement_id: str
    project_id: str
    status: FeasibilityStatus = "not_assessed"
    question: str = ""
    evidence_status: str | None = None
    answer: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    kb_request_id: str | None = None
    kb_model: str | None = None
    basis: str = ""
    error: str | None = None
    assessed_at: str | None = None

    @property
    def has_citations(self) -> bool:
        return len(self.citations) > 0


# --- Proposal / SOW ----------------------------------------------------------


class ScopeItem(BaseModel):
    description: str
    requirement_ids: list[str] = Field(default_factory=list)
    rationale: str | None = None


class Deliverable(BaseModel):
    name: str
    description: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)


class Risk(BaseModel):
    description: str
    severity: Literal["high", "medium", "low", "unspecified"] = "unspecified"
    mitigation: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)


class Estimate(BaseModel):
    item: str
    unit: EstimateUnit = "hours"
    low: float = Field(ge=0.0)
    high: float = Field(ge=0.0)
    rationale: str = ""
    dependencies: list[str] = Field(default_factory=list)
    provisional: bool = True
    conditions: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)

    @field_validator("high")
    @classmethod
    def _high_ge_low(cls, value: float, info) -> float:
        low = info.data.get("low")
        if low is not None and value < low:
            raise ValueError("estimate high must be >= low")
        return value


class Milestone(BaseModel):
    milestone_id: str
    name: str
    objective: str = ""
    deliverables: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    estimate: Estimate | None = None
    requirement_ids: list[str] = Field(default_factory=list)


class OpenQuestion(BaseModel):
    question: str
    requirement_ids: list[str] = Field(default_factory=list)
    blocking: bool = False


class Proposal(BaseModel):
    proposal_id: str
    project_id: str
    version: int = 1
    status: ProposalStatus = "draft"
    title: str = ""
    overview: str = ""
    business_objectives: list[str] = Field(default_factory=list)
    in_scope: list[ScopeItem] = Field(default_factory=list)
    out_of_scope: list[ScopeItem] = Field(default_factory=list)
    deliverables: list[Deliverable] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    milestones: list[Milestone] = Field(default_factory=list)
    estimates: list[Estimate] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    estimate_conditions: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    based_on_baseline_version: int | None = None
    created_at: str | None = None
    approved_at: str | None = None
    approved_by: str | None = None

    def requirement_id_set(self) -> set[str]:
        return set(self.requirement_ids)


# --- Baseline ----------------------------------------------------------------


class Baseline(BaseModel):
    baseline_id: str
    project_id: str
    version: int
    status: BaselineStatus = "proposed"
    proposal_id: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    requirement_snapshot: list[Requirement] = Field(default_factory=list)
    note: str | None = None
    created_at: str | None = None
    approved_at: str | None = None
    approved_by: str | None = None
    supersedes_version: int | None = None

    def snapshot_by_id(self) -> dict[str, Requirement]:
        return {req.requirement_id: req for req in self.requirement_snapshot}


# --- Scope changes -----------------------------------------------------------


class ScopeChange(BaseModel):
    change_id: str
    project_id: str
    from_baseline_version: int
    to_transcript_id: str
    change_type: ChangeType
    requirement_id: str
    baseline_requirement_id: str | None = None
    summary: str = ""
    rationale: str = ""
    field: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    new_source_refs: list[SourceRef] = Field(default_factory=list)
    baseline_source_refs: list[SourceRef] = Field(default_factory=list)
    confidence: Indicator = Field(
        default_factory=lambda: Indicator(level="low", score=0.0, basis="not set")
    )
    scope_creep: bool = False
    estimate_impact: str | None = None
    status: ScopeChangeStatus = "proposed"
    decided_by: str | None = None
    decided_at: str | None = None
    decision_notes: str | None = None


class ChangeSummary(BaseModel):
    project_id: str
    from_baseline_version: int
    to_transcript_id: str
    generated_at: str
    counts: dict[str, int] = Field(default_factory=dict)
    scope_creep_count: int = 0
    changes: list[ScopeChange] = Field(default_factory=list)


class BaselineUpdateProposal(BaseModel):
    project_id: str
    from_baseline_version: int
    to_transcript_id: str
    proposed_requirement_ids: list[str] = Field(default_factory=list)
    proposed_version: int = 1
    status: BaselineStatus = "proposed"
    rationale: str = ""
    changes: list[ScopeChange] = Field(default_factory=list)
    created_at: str | None = None


# --- Review / audit ----------------------------------------------------------


class ReviewEvent(BaseModel):
    id: str
    project_id: str | None = None
    entity_type: Literal["requirement", "proposal", "baseline", "scope_change", "transcript"]
    entity_id: str
    action: str
    from_status: str | None = None
    to_status: str | None = None
    actor: str | None = None
    reason: str | None = None
    at: str


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
