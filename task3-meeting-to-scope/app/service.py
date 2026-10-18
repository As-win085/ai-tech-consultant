"""Service layer: the Meeting-to-Scope workflow, independent of HTTP.

The service orchestrates ingestion, extraction, feasibility, proposal generation,
baseline management, change detection, and human review. Keeping this logic here
(not in FastAPI handlers) makes it testable with an in-memory store, a fake KB
client, and the deterministic rules extractor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.baseline import build_baseline_update_proposal, compute_change_summary, create_baseline
from app.config import Settings, load_settings
from app.extractor import Extractor, build_extractor
from app.feasibility import assess_requirements
from app.kb_client import KbError, KnowledgeBrainClient, build_kb_client
from app.proposal import build_proposal
from app.review import make_event, require_reason, validate_transition
from app.schemas import (
    Baseline,
    ChangeSummary,
    FeasibilityAssessment,
    FeasibilityStatus,
    Proposal,
    Requirement,
    ReviewEvent,
    Transcript,
    utcnow,
)
from app.store import InMemoryStore, Store
from app.transcript import TranscriptError, validate_transcript


class ServiceError(ValueError):
    """A workflow action could not be completed as requested."""


@dataclass
class IngestResult:
    transcript: Transcript
    requirements: list[Requirement]
    warnings: list[str] = field(default_factory=list)
    idempotent: bool = False
    change_summary: ChangeSummary | None = None
    baseline_update: object | None = None


class MeetingToScopeService:
    def __init__(
        self,
        *,
        store: Store,
        extractor: Extractor,
        kb_client: KnowledgeBrainClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.store = store
        self.extractor = extractor
        self.kb_client = kb_client
        self.settings = settings or load_settings()

    # -- ingestion ------------------------------------------------------------

    def ingest_transcript(self, transcript: Transcript) -> IngestResult:
        validate_transcript(transcript, max_chars=self.settings.max_transcript_chars)
        self.store.upsert_project(transcript.project_id, transcript.title)

        existing = self.store.find_transcript_by_hash(transcript.project_id, transcript.content_hash)
        if existing is not None:
            requirements = [
                r for r in self.store.list_requirements(transcript.project_id) if r.transcript_id == existing.transcript_id
            ]
            return IngestResult(transcript=existing, requirements=requirements, idempotent=True)

        # assign a sequence if this is an additional transcript in the project
        prior = self.store.list_transcripts(transcript.project_id)
        if prior and transcript.sequence == 1 and transcript.parent_transcript_id is None:
            transcript = transcript.model_copy(update={"sequence": max(t.sequence for t in prior) + 1})

        self.store.save_transcript(transcript)
        result = self.extractor.extract(transcript)
        self.store.save_requirements(transcript.project_id, result.requirements)

        baseline = self._latest_approved_baseline(transcript.project_id)
        change_summary = None
        baseline_update = None
        if baseline is not None and (transcript.sequence > 1 or transcript.parent_transcript_id is not None):
            change_summary = compute_change_summary(baseline, result.requirements, transcript_id=transcript.transcript_id)
            self.store.save_change_summary(change_summary)
            baseline_update = build_baseline_update_proposal(change_summary, baseline)
            self.store.save_baseline_update(baseline_update)

        return IngestResult(
            transcript=transcript,
            requirements=result.requirements,
            warnings=result.warnings,
            change_summary=change_summary,
            baseline_update=baseline_update,
        )

    # -- feasibility ----------------------------------------------------------

    def assess_feasibility(self, project_id: str) -> dict[str, FeasibilityAssessment]:
        if self.kb_client is None:
            raise ServiceError("no knowledge-brain client is configured")
        requirements = self.store.list_requirements(project_id)
        assessments = assess_requirements(requirements, self.kb_client)
        self.store.save_assessments(assessments)
        return assessments

    # -- proposal -------------------------------------------------------------

    def generate_proposal(self, project_id: str, *, version: int | None = None, title: str | None = None) -> Proposal:
        transcripts = self.store.list_transcripts(project_id)
        if not transcripts:
            raise ServiceError(f"no transcripts found for project {project_id!r}")
        latest = transcripts[-1]
        requirements = self.store.list_requirements(project_id)
        assessments = self.store.list_assessments(project_id)
        existing = self.store.list_proposals(project_id)
        version = version or (max((p.version for p in existing), default=0) + 1)
        baseline = self._latest_approved_baseline(project_id)
        proposal = build_proposal(
            latest,
            requirements,
            assessments,
            version=version,
            title=title,
            based_on_baseline_version=baseline.version if baseline else None,
        )
        self.store.save_proposal(proposal)
        return proposal

    # -- baselines ------------------------------------------------------------

    def _latest_approved_baseline(self, project_id: str) -> Baseline | None:
        approved = [b for b in self.store.list_baselines(project_id) if b.status == "approved"]
        return max(approved, key=lambda b: b.version) if approved else None

    def create_baseline(
        self,
        project_id: str,
        *,
        approved_by: str | None = None,
        note: str | None = None,
        proposal_id: str | None = None,
    ) -> Baseline:
        requirements = self.store.list_requirements(project_id)
        if not requirements:
            raise ServiceError(f"no requirements found for project {project_id!r}")
        approved = [r for r in requirements if r.status == "approved"]
        snapshot = approved or [r for r in requirements if r.statement_kind in {"explicit", "inferred"}]
        if not snapshot:
            raise ServiceError("no eligible requirements to baseline")
        existing = self.store.list_baselines(project_id)
        version = max((b.version for b in existing), default=0) + 1
        supersedes = max((b.version for b in existing), default=None)
        baseline = create_baseline(
            project_id=project_id,
            requirements=snapshot,
            version=version,
            proposal_id=proposal_id,
            note=note,
            supersedes_version=supersedes,
            approved_by=approved_by,
        )
        self.store.save_baseline(baseline)
        if approved_by:
            for b in existing:
                if b.status == "approved":
                    b.status = "superseded"
                    self.store.update_baseline(b)
            self._event("baseline", baseline.baseline_id, "approved", project_id, from_status="proposed", to_status="approved", actor=approved_by)
        else:
            self._event("baseline", baseline.baseline_id, "proposed", project_id, from_status=None, to_status="proposed", actor=None)
        return baseline

    # -- review ---------------------------------------------------------------

    def _event(self, entity_type, entity_id, action, project_id, *, from_status=None, to_status=None, actor=None, reason=None):
        event = make_event(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            project_id=project_id,
            from_status=from_status,
            to_status=to_status,
            actor=actor,
            reason=reason,
        )
        self.store.add_event(event)
        return event

    def review_requirement(self, requirement_id: str, *, to_status: str, actor: str, reason: str | None = None) -> Requirement:
        req = self.store.get_requirement(requirement_id)
        if req is None:
            raise ServiceError(f"unknown requirement: {requirement_id}")
        validate_transition("requirement", req.status, to_status)
        require_reason(to_status, reason)
        from_status = req.status
        req.status = to_status  # type: ignore[assignment]
        req.updated_at = utcnow()
        self.store.update_requirement(req)
        self._event("requirement", req.requirement_id, to_status, req.project_id, from_status=from_status, to_status=to_status, actor=actor, reason=reason)
        return req

    def edit_requirement(self, requirement_id: str, *, actor: str, description: str | None = None, priority: str | None = None, reason: str | None = None) -> Requirement:
        req = self.store.get_requirement(requirement_id)
        if req is None:
            raise ServiceError(f"unknown requirement: {requirement_id}")
        if description:
            req.description = description
        if priority:
            req.priority = priority  # type: ignore[assignment]
        req.updated_at = utcnow()
        self.store.update_requirement(req)
        self._event("requirement", req.requirement_id, "edited", req.project_id, actor=actor, reason=reason)
        return req

    def review_proposal(self, proposal_id: str, *, to_status: str, actor: str, reason: str | None = None) -> Proposal:
        proposal = self.store.get_proposal(proposal_id)
        if proposal is None:
            raise ServiceError(f"unknown proposal: {proposal_id}")
        validate_transition("proposal", proposal.status, to_status)
        require_reason(to_status, reason)
        from_status = proposal.status
        proposal.status = to_status  # type: ignore[assignment]
        if to_status == "approved":
            proposal.approved_at = utcnow()
            proposal.approved_by = actor
        self.store.update_proposal(proposal)
        self._event("proposal", proposal.proposal_id, to_status, proposal.project_id, from_status=from_status, to_status=to_status, actor=actor, reason=reason)
        return proposal

    def review_scope_change(self, project_id: str, change_id: str, *, to_status: str, actor: str, reason: str | None = None):
        summary = self._find_change_summary(project_id, change_id)
        if summary is None:
            raise ServiceError(f"unknown scope change: {change_id}")
        change = next((c for c in summary.changes if c.change_id == change_id), None)
        if change is None:
            raise ServiceError(f"unknown scope change: {change_id}")
        validate_transition("scope_change", change.status, to_status)
        require_reason(to_status, reason)
        from_status = change.status
        change.status = to_status  # type: ignore[assignment]
        change.decided_by = actor
        change.decided_at = utcnow()
        change.decision_notes = reason
        self.store.save_change_summary(summary)
        self._event("scope_change", change_id, to_status, project_id, from_status=from_status, to_status=to_status, actor=actor, reason=reason)
        return change

    def _find_change_summary(self, project_id: str, change_id: str) -> ChangeSummary | None:
        for summary in self.store.list_change_summaries(project_id):
            if any(c.change_id == change_id for c in summary.changes):
                return summary
        return None

    def approve_baseline_update(self, project_id: str, transcript_id: str, *, approved_by: str) -> Baseline:
        if not (approved_by or "").strip():
            raise ServiceError("an authorized approver is required to approve a baseline update")
        baseline = self._latest_approved_baseline(project_id)
        if baseline is None:
            raise ServiceError("no approved baseline exists to update")
        summary = self.store.get_change_summary(project_id, transcript_id)
        if summary is None:
            raise ServiceError(f"no change summary for transcript {transcript_id!r}")

        snapshot = baseline.snapshot_by_id()
        for change in summary.changes:
            if change.change_type == "added":
                req = self.store.get_requirement(change.requirement_id)
                if req is not None:
                    snapshot[req.requirement_id] = req
            elif change.change_type == "removed" and change.baseline_requirement_id:
                snapshot.pop(change.baseline_requirement_id, None)
            elif change.change_type in {"modified", "clarified"}:
                req = self.store.get_requirement(change.requirement_id)
                if req is not None:
                    snapshot[req.requirement_id] = req
                    if change.baseline_requirement_id and change.baseline_requirement_id != req.requirement_id:
                        snapshot.pop(change.baseline_requirement_id, None)
            # unresolved: retained unchanged

        new_baseline = create_baseline(
            project_id=project_id,
            requirements=list(snapshot.values()),
            version=baseline.version + 1,
            note=f"Approved update from transcript {transcript_id}",
            supersedes_version=baseline.version,
            approved_by=approved_by,
        )
        baseline.status = "superseded"
        self.store.update_baseline(baseline)
        self.store.save_baseline(new_baseline)
        self._event("baseline", new_baseline.baseline_id, "approved", project_id, from_status="proposed", to_status="approved", actor=approved_by, reason=f"update from {transcript_id}")
        return new_baseline

    # -- read helpers ---------------------------------------------------------

    def get_requirement(self, requirement_id: str) -> Requirement | None:
        return self.store.get_requirement(requirement_id)

    def list_requirements(self, project_id: str) -> list[Requirement]:
        return self.store.list_requirements(project_id)

    def get_proposal(self, proposal_id: str) -> Proposal | None:
        return self.store.get_proposal(proposal_id)

    def list_events(self, project_id: str | None = None) -> list[ReviewEvent]:
        return self.store.list_events(project_id=project_id)

    def kb_reachable(self) -> bool:
        if self.kb_client is None:
            return False
        return self.kb_client.ping()


def build_default_service(
    *,
    settings: Settings | None = None,
    store: Store | None = None,
    kb_client: KnowledgeBrainClient | None = None,
    extractor: Extractor | None = None,
) -> MeetingToScopeService:
    settings = settings or load_settings()
    store = store or InMemoryStore()
    if extractor is None:
        extractor = build_extractor(settings)
    if kb_client is None:
        try:
            kb_client = build_kb_client(settings)
        except Exception:  # pragma: no cover - config error surfaces via /ready
            kb_client = None
    return MeetingToScopeService(store=store, extractor=extractor, kb_client=kb_client, settings=settings)


def build_postgres_service(
    *,
    settings: Settings | None = None,
    kb_client: KnowledgeBrainClient | None = None,
    extractor: Extractor | None = None,
) -> MeetingToScopeService:
    from app.db import apply_migrations, connect
    from app.postgres_store import PostgresStore

    settings = settings or load_settings()
    if not settings.database_url:
        raise ServiceError("DATABASE_URL is required for the Postgres-backed service")
    connection = connect(settings.database_url)
    apply_migrations(connection, schema=settings.database_schema)
    store = PostgresStore(connection, schema=settings.database_schema)
    return build_default_service(settings=settings, store=store, kb_client=kb_client, extractor=extractor)
