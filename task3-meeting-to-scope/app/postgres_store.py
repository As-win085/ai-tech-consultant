"""PostgreSQL implementation of :class:`~app.store.Store`.

Aggregates are stored as validated Pydantic models serialized to JSONB (so the
schema evolves with the models), while the columns we filter on
(project_id, status, version, transcript hash) are promoted to real columns and
indexed. All writes are parameterized; no SQL is built from user input.
"""

from __future__ import annotations

import json

import pg8000.native

from app.db import validate_schema_name
from app.schemas import (
    Baseline,
    BaselineUpdateProposal,
    ChangeSummary,
    FeasibilityAssessment,
    Proposal,
    Requirement,
    ReviewEvent,
    Transcript,
)
from app.store import StoreError


def _dump(model) -> str:
    return json.dumps(model.model_dump(mode="json"))


def _load(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


class PostgresStore:
    def __init__(self, connection: pg8000.native.Connection, *, schema: str = "meeting_to_scope") -> None:
        self.connection = connection
        self.schema = validate_schema_name(schema)
        self.connection.run(f"SET search_path TO {self.schema}")

    def _run(self, sql: str, **params):
        return self.connection.run(sql, **params)

    # projects
    def upsert_project(self, project_id: str, title: str | None = None) -> None:
        self._run(
            """
            INSERT INTO mt_project (project_id, title) VALUES (:project_id, :title)
            ON CONFLICT (project_id) DO UPDATE SET
                title = CASE WHEN :title <> '' THEN :title ELSE mt_project.title END,
                updated_at = now()
            """,
            project_id=project_id,
            title=title or "",
        )

    def get_project(self, project_id: str) -> dict | None:
        rows = self._run("SELECT project_id, title FROM mt_project WHERE project_id = :project_id", project_id=project_id)
        if not rows:
            return None
        return {"project_id": rows[0][0], "title": rows[0][1]}

    def list_projects(self) -> list[dict]:
        return [{"project_id": r[0], "title": r[1]} for r in self._run("SELECT project_id, title FROM mt_project ORDER BY project_id")]

    # transcripts
    def save_transcript(self, transcript: Transcript) -> None:
        self.upsert_project(transcript.project_id, transcript.title)
        self._run(
            """
            INSERT INTO mt_transcript (transcript_id, project_id, sequence, content_hash, data)
            VALUES (:transcript_id, :project_id, :sequence, :content_hash, :data::jsonb)
            ON CONFLICT (transcript_id) DO UPDATE SET
                project_id = EXCLUDED.project_id,
                sequence = EXCLUDED.sequence,
                content_hash = EXCLUDED.content_hash,
                data = EXCLUDED.data
            """,
            transcript_id=transcript.transcript_id,
            project_id=transcript.project_id,
            sequence=transcript.sequence,
            content_hash=transcript.content_hash,
            data=_dump(transcript),
        )

    def get_transcript(self, transcript_id: str) -> Transcript | None:
        rows = self._run("SELECT data FROM mt_transcript WHERE transcript_id = :transcript_id", transcript_id=transcript_id)
        if not rows:
            return None
        return Transcript.model_validate(_load(rows[0][0]))

    def find_transcript_by_hash(self, project_id: str, content_hash: str) -> Transcript | None:
        rows = self._run(
            "SELECT data FROM mt_transcript WHERE project_id = :project_id AND content_hash = :content_hash LIMIT 1",
            project_id=project_id,
            content_hash=content_hash,
        )
        if not rows:
            return None
        return Transcript.model_validate(_load(rows[0][0]))

    def list_transcripts(self, project_id: str) -> list[Transcript]:
        rows = self._run(
            "SELECT data FROM mt_transcript WHERE project_id = :project_id ORDER BY sequence",
            project_id=project_id,
        )
        return [Transcript.model_validate(_load(r[0])) for r in rows]

    # requirements
    def save_requirements(self, project_id: str, requirements: list[Requirement]) -> None:
        for r in requirements:
            self._run(
                """
                INSERT INTO mt_requirement (requirement_id, project_id, transcript_id, status, data)
                VALUES (:requirement_id, :project_id, :transcript_id, :status, :data::jsonb)
                ON CONFLICT (requirement_id) DO UPDATE SET
                    status = EXCLUDED.status, data = EXCLUDED.data, updated_at = now()
                """,
                requirement_id=r.requirement_id,
                project_id=r.project_id,
                transcript_id=r.transcript_id,
                status=r.status,
                data=_dump(r),
            )

    def get_requirement(self, requirement_id: str) -> Requirement | None:
        rows = self._run("SELECT data FROM mt_requirement WHERE requirement_id = :requirement_id", requirement_id=requirement_id)
        if not rows:
            return None
        return Requirement.model_validate(_load(rows[0][0]))

    def list_requirements(self, project_id: str) -> list[Requirement]:
        rows = self._run("SELECT data FROM mt_requirement WHERE project_id = :project_id ORDER BY requirement_id", project_id=project_id)
        return [Requirement.model_validate(_load(r[0])) for r in rows]

    def update_requirement(self, requirement: Requirement) -> None:
        rows = self._run("SELECT 1 FROM mt_requirement WHERE requirement_id = :requirement_id", requirement_id=requirement.requirement_id)
        if not rows:
            raise StoreError(f"unknown requirement: {requirement.requirement_id}")
        self._run(
            "UPDATE mt_requirement SET status = :status, data = :data::jsonb, updated_at = now() WHERE requirement_id = :requirement_id",
            requirement_id=requirement.requirement_id,
            status=requirement.status,
            data=_dump(requirement),
        )

    # feasibility
    def save_assessments(self, assessments: dict[str, FeasibilityAssessment]) -> None:
        for rid, a in assessments.items():
            self._run(
                """
                INSERT INTO mt_assessment (requirement_id, project_id, status, data)
                VALUES (:requirement_id, :project_id, :status, :data::jsonb)
                ON CONFLICT (requirement_id) DO UPDATE SET status = EXCLUDED.status, data = EXCLUDED.data
                """,
                requirement_id=rid,
                project_id=a.project_id,
                status=a.status,
                data=_dump(a),
            )

    def get_assessment(self, requirement_id: str) -> FeasibilityAssessment | None:
        rows = self._run("SELECT data FROM mt_assessment WHERE requirement_id = :requirement_id", requirement_id=requirement_id)
        if not rows:
            return None
        return FeasibilityAssessment.model_validate(_load(rows[0][0]))

    def list_assessments(self, project_id: str) -> dict[str, FeasibilityAssessment]:
        rows = self._run("SELECT requirement_id, data FROM mt_assessment WHERE project_id = :project_id", project_id=project_id)
        return {r[0]: FeasibilityAssessment.model_validate(_load(r[1])) for r in rows}

    # proposals
    def save_proposal(self, proposal: Proposal) -> None:
        self._run(
            """
            INSERT INTO mt_proposal (proposal_id, project_id, version, status, data)
            VALUES (:proposal_id, :project_id, :version, :status, :data::jsonb)
            ON CONFLICT (proposal_id) DO UPDATE SET version = EXCLUDED.version, status = EXCLUDED.status, data = EXCLUDED.data
            """,
            proposal_id=proposal.proposal_id,
            project_id=proposal.project_id,
            version=proposal.version,
            status=proposal.status,
            data=_dump(proposal),
        )

    def get_proposal(self, proposal_id: str) -> Proposal | None:
        rows = self._run("SELECT data FROM mt_proposal WHERE proposal_id = :proposal_id", proposal_id=proposal_id)
        if not rows:
            return None
        return Proposal.model_validate(_load(rows[0][0]))

    def list_proposals(self, project_id: str) -> list[Proposal]:
        rows = self._run("SELECT data FROM mt_proposal WHERE project_id = :project_id ORDER BY version", project_id=project_id)
        return [Proposal.model_validate(_load(r[0])) for r in rows]

    def update_proposal(self, proposal: Proposal) -> None:
        rows = self._run("SELECT 1 FROM mt_proposal WHERE proposal_id = :proposal_id", proposal_id=proposal.proposal_id)
        if not rows:
            raise StoreError(f"unknown proposal: {proposal.proposal_id}")
        self._run(
            "UPDATE mt_proposal SET status = :status, data = :data::jsonb WHERE proposal_id = :proposal_id",
            proposal_id=proposal.proposal_id,
            status=proposal.status,
            data=_dump(proposal),
        )

    # baselines
    def save_baseline(self, baseline: Baseline) -> None:
        self._run(
            """
            INSERT INTO mt_baseline (project_id, version, status, data, approved_at)
            VALUES (:project_id, :version, :status, :data::jsonb, :approved_at)
            ON CONFLICT (project_id, version) DO UPDATE SET status = EXCLUDED.status, data = EXCLUDED.data, approved_at = EXCLUDED.approved_at
            """,
            project_id=baseline.project_id,
            version=baseline.version,
            status=baseline.status,
            data=_dump(baseline),
            approved_at=baseline.approved_at,
        )

    def get_baseline(self, project_id: str, version: int) -> Baseline | None:
        rows = self._run("SELECT data FROM mt_baseline WHERE project_id = :project_id AND version = :version", project_id=project_id, version=version)
        if not rows:
            return None
        return Baseline.model_validate(_load(rows[0][0]))

    def list_baselines(self, project_id: str) -> list[Baseline]:
        rows = self._run("SELECT data FROM mt_baseline WHERE project_id = :project_id ORDER BY version", project_id=project_id)
        return [Baseline.model_validate(_load(r[0])) for r in rows]

    def update_baseline(self, baseline: Baseline) -> None:
        rows = self._run("SELECT 1 FROM mt_baseline WHERE project_id = :project_id AND version = :version", project_id=baseline.project_id, version=baseline.version)
        if not rows:
            raise StoreError(f"unknown baseline: {baseline.project_id} v{baseline.version}")
        self._run(
            "UPDATE mt_baseline SET status = :status, data = :data::jsonb, approved_at = :approved_at WHERE project_id = :project_id AND version = :version",
            project_id=baseline.project_id,
            version=baseline.version,
            status=baseline.status,
            data=_dump(baseline),
            approved_at=baseline.approved_at,
        )

    # change summaries / baseline updates
    def save_change_summary(self, summary: ChangeSummary) -> None:
        self._run(
            """
            INSERT INTO mt_change_summary (project_id, to_transcript_id, data)
            VALUES (:project_id, :to_transcript_id, :data::jsonb)
            ON CONFLICT (project_id, to_transcript_id) DO UPDATE SET data = EXCLUDED.data
            """,
            project_id=summary.project_id,
            to_transcript_id=summary.to_transcript_id,
            data=_dump(summary),
        )

    def get_change_summary(self, project_id: str, transcript_id: str) -> ChangeSummary | None:
        rows = self._run("SELECT data FROM mt_change_summary WHERE project_id = :project_id AND to_transcript_id = :tid", project_id=project_id, tid=transcript_id)
        if not rows:
            return None
        return ChangeSummary.model_validate(_load(rows[0][0]))

    def list_change_summaries(self, project_id: str) -> list[ChangeSummary]:
        rows = self._run("SELECT data FROM mt_change_summary WHERE project_id = :project_id", project_id=project_id)
        return [ChangeSummary.model_validate(_load(r[0])) for r in rows]

    def save_baseline_update(self, update: BaselineUpdateProposal) -> None:
        self._run(
            """
            INSERT INTO mt_baseline_update (project_id, to_transcript_id, proposed_version, data)
            VALUES (:project_id, :to_transcript_id, :proposed_version, :data::jsonb)
            ON CONFLICT (project_id, to_transcript_id) DO UPDATE SET proposed_version = EXCLUDED.proposed_version, data = EXCLUDED.data
            """,
            project_id=update.project_id,
            to_transcript_id=update.to_transcript_id,
            proposed_version=update.proposed_version,
            data=_dump(update),
        )

    def list_baseline_updates(self, project_id: str) -> list[BaselineUpdateProposal]:
        rows = self._run("SELECT data FROM mt_baseline_update WHERE project_id = :project_id", project_id=project_id)
        return [BaselineUpdateProposal.model_validate(_load(r[0])) for r in rows]

    # review events
    def add_event(self, event: ReviewEvent) -> None:
        self._run(
            """
            INSERT INTO mt_review_event (event_id, project_id, entity_type, entity_id, data, at)
            VALUES (:event_id, :project_id, :entity_type, :entity_id, :data::jsonb, :at)
            ON CONFLICT (event_id) DO NOTHING
            """,
            event_id=event.id,
            project_id=event.project_id,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            data=_dump(event),
            at=event.at,
        )

    def list_events(self, project_id: str | None = None, entity_id: str | None = None) -> list[ReviewEvent]:
        if project_id is not None and entity_id is not None:
            rows = self._run("SELECT data FROM mt_review_event WHERE project_id = :project_id AND entity_id = :entity_id ORDER BY at", project_id=project_id, entity_id=entity_id)
        elif project_id is not None:
            rows = self._run("SELECT data FROM mt_review_event WHERE project_id = :project_id ORDER BY at", project_id=project_id)
        elif entity_id is not None:
            rows = self._run("SELECT data FROM mt_review_event WHERE entity_id = :entity_id ORDER BY at", entity_id=entity_id)
        else:
            rows = self._run("SELECT data FROM mt_review_event ORDER BY at")
        return [ReviewEvent.model_validate(_load(r[0])) for r in rows]
