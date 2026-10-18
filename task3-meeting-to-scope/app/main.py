"""FastAPI application for the Meeting-to-Scope Agent.

HTTP handlers are thin: they validate input, delegate to
:class:`~app.service.MeetingToScopeService`, and map domain errors to HTTP
status codes. All workflow logic lives in the service layer.
"""

from __future__ import annotations

from typing import Literal

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse

from app import __version__
from app.config import load_settings
from app.kb_client import KbError
from app.schemas import (
    Baseline,
    BaselineUpdateProposal,
    ChangeSummary,
    FeasibilityAssessment,
    Participant,
    Proposal,
    Requirement,
    ReviewEvent,
    Transcript,
    TranscriptSegment,
)
from app.service import (
    IngestResult,
    MeetingToScopeService,
    ServiceError,
    build_default_service,
    build_postgres_service,
)
from app.store import StoreError
from app.transcript import TranscriptError, parse_transcript_text
from pydantic import BaseModel, Field

app = FastAPI(
    title="AI Tech Consultant - Meeting-to-Scope Agent",
    description=(
        "Turns meeting transcripts into structured requirements, evidence-grounded "
        "feasibility assessments, a traceable draft proposal, and a versioned "
        "baseline that only changes through explicit human approval."
    ),
    version=__version__,
)

_service: MeetingToScopeService | None = None


def get_service() -> MeetingToScopeService:
    global _service
    if _service is None:
        settings = load_settings()
        if settings.database_url:
            _service = build_postgres_service(settings=settings)
        else:
            _service = build_default_service(settings=settings)
    return _service


# --- request / response models ----------------------------------------------


class TranscriptCreate(BaseModel):
    """Ingest a transcript either as structured segments or as labelled text."""

    project_id: str = Field(min_length=1)
    transcript_id: str = Field(min_length=1)
    title: str = ""
    meeting_date: str | None = None
    sequence: int = 1
    parent_transcript_id: str | None = None
    participants: list[Participant] = Field(default_factory=list)
    segments: list[TranscriptSegment] | None = None
    text: str | None = None


class IngestResponse(BaseModel):
    transcript: Transcript
    requirements: list[Requirement]
    warnings: list[str] = Field(default_factory=list)
    idempotent: bool = False
    change_summary: ChangeSummary | None = None
    baseline_update: BaselineUpdateProposal | None = None


class ReviewRequest(BaseModel):
    to_status: str
    actor: str = Field(min_length=1)
    reason: str | None = None


class EditRequirementRequest(BaseModel):
    actor: str = Field(min_length=1)
    description: str | None = None
    priority: str | None = None
    reason: str | None = None


class ProposalRequest(BaseModel):
    version: int | None = None
    title: str | None = None


class BaselineRequest(BaseModel):
    approved_by: str | None = None
    note: str | None = None
    proposal_id: str | None = None


class ApproveBaselineRequest(BaseModel):
    approved_by: str = Field(min_length=1)


class ReadyResponse(BaseModel):
    status: Literal["ready", "degraded"]
    ready: bool
    extractor: str
    store: str
    knowledge_brain_reachable: bool


# --- routes ------------------------------------------------------------------


@app.get("/")
async def root():
    return {"service": "meeting-to-scope", "version": __version__, "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "meeting-to-scope", "version": __version__}


@app.get("/ui", response_class=HTMLResponse)
async def ui():
    from app.ui import get_ui_html

    return HTMLResponse(get_ui_html())


@app.get("/ready", response_model=ReadyResponse)
def ready(service: MeetingToScopeService = Depends(get_service)) -> ReadyResponse:
    kb = service.kb_reachable()
    store_name = type(service.store).__name__
    return ReadyResponse(
        status="ready" if kb else "degraded",
        ready=True,
        extractor=type(service.extractor).__name__,
        store=store_name,
        knowledge_brain_reachable=kb,
    )


@app.post("/transcripts", response_model=IngestResponse, status_code=201)
def ingest_transcript(payload: TranscriptCreate, service: MeetingToScopeService = Depends(get_service)) -> IngestResponse:
    transcript = _build_transcript(payload)
    result: IngestResult = service.ingest_transcript(transcript)
    return IngestResponse(
        transcript=result.transcript,
        requirements=result.requirements,
        warnings=result.warnings,
        idempotent=result.idempotent,
        change_summary=result.change_summary,
        baseline_update=result.baseline_update,
    )


@app.get("/projects")
def list_projects(service: MeetingToScopeService = Depends(get_service)):
    return {"projects": service.store.list_projects()}


@app.get("/projects/{project_id}/transcripts", response_model=list[Transcript])
def list_transcripts(project_id: str, service: MeetingToScopeService = Depends(get_service)):
    return service.store.list_transcripts(project_id)


@app.get("/projects/{project_id}/requirements", response_model=list[Requirement])
def list_requirements(project_id: str, service: MeetingToScopeService = Depends(get_service)):
    return service.list_requirements(project_id)


@app.get("/requirements/{requirement_id}", response_model=Requirement)
def get_requirement(requirement_id: str, service: MeetingToScopeService = Depends(get_service)):
    req = service.get_requirement(requirement_id)
    if req is None:
        raise _not_found(f"unknown requirement: {requirement_id}")
    return req


@app.post("/requirements/{requirement_id}/review", response_model=Requirement)
def review_requirement(requirement_id: str, payload: ReviewRequest, service: MeetingToScopeService = Depends(get_service)):
    return service.review_requirement(requirement_id, to_status=payload.to_status, actor=payload.actor, reason=payload.reason)


@app.post("/requirements/{requirement_id}/edit", response_model=Requirement)
def edit_requirement(requirement_id: str, payload: EditRequirementRequest, service: MeetingToScopeService = Depends(get_service)):
    return service.edit_requirement(requirement_id, actor=payload.actor, description=payload.description, priority=payload.priority, reason=payload.reason)


@app.post("/projects/{project_id}/feasibility", response_model=dict[str, FeasibilityAssessment])
def assess_feasibility(project_id: str, service: MeetingToScopeService = Depends(get_service)):
    return service.assess_feasibility(project_id)


@app.post("/projects/{project_id}/proposals", response_model=Proposal, status_code=201)
def create_proposal(project_id: str, payload: ProposalRequest | None = None, service: MeetingToScopeService = Depends(get_service)):
    payload = payload or ProposalRequest()
    return service.generate_proposal(project_id, version=payload.version, title=payload.title)


@app.get("/proposals/{proposal_id}", response_model=Proposal)
def get_proposal(proposal_id: str, service: MeetingToScopeService = Depends(get_service)):
    prop = service.get_proposal(proposal_id)
    if prop is None:
        raise _not_found(f"unknown proposal: {proposal_id}")
    return prop


@app.post("/proposals/{proposal_id}/review", response_model=Proposal)
def review_proposal(proposal_id: str, payload: ReviewRequest, service: MeetingToScopeService = Depends(get_service)):
    return service.review_proposal(proposal_id, to_status=payload.to_status, actor=payload.actor, reason=payload.reason)


@app.post("/projects/{project_id}/baselines", response_model=Baseline, status_code=201)
def create_baseline(project_id: str, payload: BaselineRequest, service: MeetingToScopeService = Depends(get_service)):
    return service.create_baseline(project_id, approved_by=payload.approved_by, note=payload.note, proposal_id=payload.proposal_id)


@app.get("/projects/{project_id}/baselines", response_model=list[Baseline])
def list_baselines(project_id: str, service: MeetingToScopeService = Depends(get_service)):
    return service.store.list_baselines(project_id)


@app.get("/projects/{project_id}/change-summaries", response_model=list[ChangeSummary])
def list_change_summaries(project_id: str, service: MeetingToScopeService = Depends(get_service)):
    return service.store.list_change_summaries(project_id)


@app.post("/projects/{project_id}/scope-changes/{change_id}/review")
def review_scope_change(project_id: str, change_id: str, payload: ReviewRequest, service: MeetingToScopeService = Depends(get_service)):
    return service.review_scope_change(project_id, change_id, to_status=payload.to_status, actor=payload.actor, reason=payload.reason)


@app.post("/projects/{project_id}/baseline-updates/{transcript_id}/approve", response_model=Baseline)
def approve_baseline_update(project_id: str, transcript_id: str, payload: ApproveBaselineRequest, service: MeetingToScopeService = Depends(get_service)):
    return service.approve_baseline_update(project_id, transcript_id, approved_by=payload.approved_by)


@app.get("/projects/{project_id}/events", response_model=list[ReviewEvent])
def list_events(project_id: str, service: MeetingToScopeService = Depends(get_service)):
    return service.list_events(project_id)


def _build_transcript(payload: TranscriptCreate) -> Transcript:
    if payload.segments:
        from app.transcript import from_dict

        data = {
            "transcript_id": payload.transcript_id,
            "project_id": payload.project_id,
            "title": payload.title,
            "meeting_date": payload.meeting_date,
            "sequence": payload.sequence,
            "parent_transcript_id": payload.parent_transcript_id,
            "participants": [p.model_dump() for p in payload.participants],
            "segments": [s.model_dump() for s in payload.segments],
        }
        return from_dict(data)
    if payload.text:
        return parse_transcript_text(
            payload.text,
            transcript_id=payload.transcript_id,
            project_id=payload.project_id,
            title=payload.title,
            meeting_date=payload.meeting_date,
            participants=payload.participants,
        )
    raise TranscriptError("provide either 'segments' or 'text'")


# --- error handling ----------------------------------------------------------


def _not_found(message: str) -> ServiceError:
    return ServiceError(message)


@app.exception_handler(TranscriptError)
async def _transcript_error_handler(request: Request, exc: TranscriptError):
    return JSONResponse(status_code=422, content={"error": {"code": "invalid_transcript", "message": str(exc)}})


@app.exception_handler(ServiceError)
async def _service_error_handler(request: Request, exc: ServiceError):
    message = str(exc)
    if "knowledge-brain client" in message:
        return JSONResponse(status_code=503, content={"error": {"code": "knowledge_brain_unconfigured", "message": message}})
    if message.startswith("unknown") or message.startswith("no "):
        return JSONResponse(status_code=404, content={"error": {"code": "not_found", "message": message}})
    return JSONResponse(status_code=400, content={"error": {"code": "invalid_request", "message": message}})


@app.exception_handler(StoreError)
async def _store_error_handler(request: Request, exc: StoreError):
    return JSONResponse(status_code=409, content={"error": {"code": "store_conflict", "message": str(exc)}})


@app.exception_handler(KbError)
async def _kb_error_handler(request: Request, exc: KbError):
    return JSONResponse(status_code=503, content={"error": {"code": "knowledge_brain_unavailable", "message": str(exc)}})


@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": "the request body failed validation"}})


@app.exception_handler(Exception)
async def _unhandled_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "an unexpected internal error occurred"}})
