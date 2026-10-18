"""Persistence for transcripts, requirements, proposals, baselines, and reviews.

Two implementations satisfy :class:`Store`:

* :class:`InMemoryStore` — used by unit tests and dry runs; no external services.
* :class:`PostgresStore` (in :mod:`app.postgres_store`) — durable, schema-isolated.

The interface is deliberately small and entity-oriented. Values are returned as
copies where mutation could leak, and everything is keyed by stable ids so
re-processing a transcript is idempotent.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

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


class StoreError(RuntimeError):
    pass


@runtime_checkable
class Store(Protocol):
    # projects
    def upsert_project(self, project_id: str, title: str | None = None) -> None: ...
    def get_project(self, project_id: str) -> dict | None: ...
    def list_projects(self) -> list[dict]: ...

    # transcripts
    def save_transcript(self, transcript: Transcript) -> None: ...
    def get_transcript(self, transcript_id: str) -> Transcript | None: ...
    def find_transcript_by_hash(self, project_id: str, content_hash: str) -> Transcript | None: ...
    def list_transcripts(self, project_id: str) -> list[Transcript]: ...

    # requirements
    def save_requirements(self, project_id: str, requirements: list[Requirement]) -> None: ...
    def get_requirement(self, requirement_id: str) -> Requirement | None: ...
    def list_requirements(self, project_id: str) -> list[Requirement]: ...
    def update_requirement(self, requirement: Requirement) -> None: ...

    # feasibility
    def save_assessments(self, assessments: dict[str, FeasibilityAssessment]) -> None: ...
    def get_assessment(self, requirement_id: str) -> FeasibilityAssessment | None: ...
    def list_assessments(self, project_id: str) -> dict[str, FeasibilityAssessment]: ...

    # proposals
    def save_proposal(self, proposal: Proposal) -> None: ...
    def get_proposal(self, proposal_id: str) -> Proposal | None: ...
    def list_proposals(self, project_id: str) -> list[Proposal]: ...
    def update_proposal(self, proposal: Proposal) -> None: ...

    # baselines
    def save_baseline(self, baseline: Baseline) -> None: ...
    def get_baseline(self, project_id: str, version: int) -> Baseline | None: ...
    def list_baselines(self, project_id: str) -> list[Baseline]: ...
    def update_baseline(self, baseline: Baseline) -> None: ...

    # change summaries / baseline updates
    def save_change_summary(self, summary: ChangeSummary) -> None: ...
    def get_change_summary(self, project_id: str, transcript_id: str) -> ChangeSummary | None: ...
    def list_change_summaries(self, project_id: str) -> list[ChangeSummary]: ...
    def save_baseline_update(self, update: BaselineUpdateProposal) -> None: ...
    def list_baseline_updates(self, project_id: str) -> list[BaselineUpdateProposal]: ...

    # review events (append-only)
    def add_event(self, event: ReviewEvent) -> None: ...
    def list_events(self, project_id: str | None = None, entity_id: str | None = None) -> list[ReviewEvent]: ...


class InMemoryStore:
    """In-process store for tests and dry runs."""

    def __init__(self) -> None:
        self._projects: dict[str, dict] = {}
        self._transcripts: dict[str, Transcript] = {}
        self._requirements: dict[str, Requirement] = {}
        self._assessments: dict[str, FeasibilityAssessment] = {}
        self._proposals: dict[str, Proposal] = {}
        self._baselines: dict[tuple[str, int], Baseline] = {}
        self._summaries: dict[tuple[str, str], ChangeSummary] = {}
        self._baseline_updates: dict[tuple[str, str], BaselineUpdateProposal] = {}
        self._events: list[ReviewEvent] = []

    # projects
    def upsert_project(self, project_id: str, title: str | None = None) -> None:
        entry = self._projects.setdefault(project_id, {"project_id": project_id, "title": title or ""})
        if title:
            entry["title"] = title

    def get_project(self, project_id: str) -> dict | None:
        entry = self._projects.get(project_id)
        return dict(entry) if entry else None

    def list_projects(self) -> list[dict]:
        return [dict(p) for p in self._projects.values()]

    # transcripts
    def save_transcript(self, transcript: Transcript) -> None:
        self._transcripts[transcript.transcript_id] = transcript.model_copy(deep=True)
        self.upsert_project(transcript.project_id, transcript.title)

    def get_transcript(self, transcript_id: str) -> Transcript | None:
        t = self._transcripts.get(transcript_id)
        return t.model_copy(deep=True) if t else None

    def find_transcript_by_hash(self, project_id: str, content_hash: str) -> Transcript | None:
        for t in self._transcripts.values():
            if t.project_id == project_id and t.content_hash == content_hash:
                return t.model_copy(deep=True)
        return None

    def list_transcripts(self, project_id: str) -> list[Transcript]:
        items = [t for t in self._transcripts.values() if t.project_id == project_id]
        return [t.model_copy(deep=True) for t in sorted(items, key=lambda x: x.sequence)]

    # requirements
    def save_requirements(self, project_id: str, requirements: list[Requirement]) -> None:
        for r in requirements:
            self._requirements[r.requirement_id] = r.model_copy(deep=True)

    def get_requirement(self, requirement_id: str) -> Requirement | None:
        r = self._requirements.get(requirement_id)
        return r.model_copy(deep=True) if r else None

    def list_requirements(self, project_id: str) -> list[Requirement]:
        return [
            r.model_copy(deep=True)
            for r in self._requirements.values()
            if r.project_id == project_id
        ]

    def update_requirement(self, requirement: Requirement) -> None:
        if requirement.requirement_id not in self._requirements:
            raise StoreError(f"unknown requirement: {requirement.requirement_id}")
        self._requirements[requirement.requirement_id] = requirement.model_copy(deep=True)

    # feasibility
    def save_assessments(self, assessments: dict[str, FeasibilityAssessment]) -> None:
        for rid, a in assessments.items():
            self._assessments[rid] = a.model_copy(deep=True)

    def get_assessment(self, requirement_id: str) -> FeasibilityAssessment | None:
        a = self._assessments.get(requirement_id)
        return a.model_copy(deep=True) if a else None

    def list_assessments(self, project_id: str) -> dict[str, FeasibilityAssessment]:
        return {
            rid: a.model_copy(deep=True)
            for rid, a in self._assessments.items()
            if a.project_id == project_id
        }

    # proposals
    def save_proposal(self, proposal: Proposal) -> None:
        self._proposals[proposal.proposal_id] = proposal.model_copy(deep=True)

    def get_proposal(self, proposal_id: str) -> Proposal | None:
        p = self._proposals.get(proposal_id)
        return p.model_copy(deep=True) if p else None

    def list_proposals(self, project_id: str) -> list[Proposal]:
        items = [p for p in self._proposals.values() if p.project_id == project_id]
        return [p.model_copy(deep=True) for p in sorted(items, key=lambda x: x.version)]

    def update_proposal(self, proposal: Proposal) -> None:
        if proposal.proposal_id not in self._proposals:
            raise StoreError(f"unknown proposal: {proposal.proposal_id}")
        self._proposals[proposal.proposal_id] = proposal.model_copy(deep=True)

    # baselines
    def save_baseline(self, baseline: Baseline) -> None:
        self._baselines[(baseline.project_id, baseline.version)] = baseline.model_copy(deep=True)

    def get_baseline(self, project_id: str, version: int) -> Baseline | None:
        b = self._baselines.get((project_id, version))
        return b.model_copy(deep=True) if b else None

    def list_baselines(self, project_id: str) -> list[Baseline]:
        items = [b for (pid, _), b in self._baselines.items() if pid == project_id]
        return [b.model_copy(deep=True) for b in sorted(items, key=lambda x: x.version)]

    def update_baseline(self, baseline: Baseline) -> None:
        if (baseline.project_id, baseline.version) not in self._baselines:
            raise StoreError(f"unknown baseline: {baseline.project_id} v{baseline.version}")
        self._baselines[(baseline.project_id, baseline.version)] = baseline.model_copy(deep=True)

    # change summaries / baseline updates
    def save_change_summary(self, summary: ChangeSummary) -> None:
        self._summaries[(summary.project_id, summary.to_transcript_id)] = summary.model_copy(deep=True)

    def get_change_summary(self, project_id: str, transcript_id: str) -> ChangeSummary | None:
        s = self._summaries.get((project_id, transcript_id))
        return s.model_copy(deep=True) if s else None

    def list_change_summaries(self, project_id: str) -> list[ChangeSummary]:
        return [s.model_copy(deep=True) for (pid, _), s in self._summaries.items() if pid == project_id]

    def save_baseline_update(self, update: BaselineUpdateProposal) -> None:
        self._baseline_updates[(update.project_id, update.to_transcript_id)] = update.model_copy(deep=True)

    def list_baseline_updates(self, project_id: str) -> list[BaselineUpdateProposal]:
        return [u.model_copy(deep=True) for (pid, _), u in self._baseline_updates.items() if pid == project_id]

    # review events
    def add_event(self, event: ReviewEvent) -> None:
        self._events.append(event.model_copy(deep=True))

    def list_events(self, project_id: str | None = None, entity_id: str | None = None) -> list[ReviewEvent]:
        out = [e for e in self._events if (project_id is None or e.project_id == project_id)]
        if entity_id is not None:
            out = [e for e in out if e.entity_id == entity_id]
        return [e.model_copy(deep=True) for e in out]
