"""Pydantic request/response contracts for the Knowledge Brain API.

These schemas are the public contract (KB-FR-05, KB-FR-08). They are shared by
the answer service, the FastAPI app, and the evaluation harness, and are exported
through FastAPI's OpenAPI document.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

EvidenceStatus = Literal["sufficient", "insufficient", "conflicting", "unavailable"]
ConfidenceLevel = Literal["high", "medium", "low", "none"]
ReadinessStatus = Literal["ready", "degraded", "unavailable"]


class AskRequest(BaseModel):
    """A question for the Knowledge Brain."""

    question: str = Field(
        min_length=1,
        max_length=2000,
        description="Natural-language question about Brilliant Directories.",
        examples=["How do I reset a member's password?"],
    )
    top_k: int | None = Field(
        default=None, ge=1, le=50, description="Override the number of evidence chunks."
    )
    min_score: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Override the minimum cosine-similarity threshold for evidence.",
    )
    include_chunks: bool = Field(
        default=False, description="Include retrieved chunk diagnostics in the response."
    )

    @field_validator("question")
    @classmethod
    def _question_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be empty or whitespace")
        return stripped


class Citation(BaseModel):
    """A verifiable reference to a retrieved support chunk."""

    article_id: str
    title: str
    canonical_url: str | None = None
    heading: str | None = None
    chunk_id: str
    chunk_index: int
    score: float


class RetrievedChunk(BaseModel):
    """Diagnostic view of a retrieved chunk (optional, size-limited)."""

    chunk_id: str
    article_id: str
    title: str
    canonical_url: str | None = None
    heading: str | None = None
    score: float
    content: str


class EvidenceConfidence(BaseModel):
    """Evidence-strength indicator.

    This is a heuristic derived from retrieval signals (best and mean similarity,
    number of supporting chunks, citation coverage). It is **not** a calibrated
    probability and must not be interpreted as one.
    """

    level: ConfidenceLevel
    score: float = Field(ge=0.0, le=1.0)
    basis: str


class AskResponse(BaseModel):
    """Structured, grounded answer (or a safe abstention)."""

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    evidence_status: EvidenceStatus
    confidence: EvidenceConfidence
    needs_escalation: bool
    escalation_reason: str | None = None
    retrieved_chunks: list[RetrievedChunk] | None = None
    model: str | None = None
    request_id: str
    escalation_id: str | None = None


class EscalationCreateRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=1, max_length=1000)


class EscalationResolveRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=12000)
    reviewer: str = Field(min_length=1, max_length=200)


class DependencyStatus(BaseModel):
    name: str
    status: Literal["ok", "error", "not_configured", "mismatch"]
    detail: str


class ReadyReport(BaseModel):
    status: ReadinessStatus
    ready: bool
    dependencies: list[DependencyStatus]
    index: dict


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
