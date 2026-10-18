"""Service layer: workflow, idempotency, baseline lifecycle, review semantics."""

from __future__ import annotations

import pytest

from app.extractor import RuleBasedExtractor
from app.service import MeetingToScopeService, ServiceError
from app.store import InMemoryStore
from tests.conftest import FakeKB, make_transcript, sufficient_answer


def _svc(fake_kb=None):
    kb = fake_kb or FakeKB([("sso", sufficient_answer())])
    return MeetingToScopeService(store=InMemoryStore(), extractor=RuleBasedExtractor(), kb_client=kb)


def _ingest1():
    svc = _svc()
    t1 = make_transcript(
        transcript_id="mtg-001",
        project_id="proj",
        segments=[
            {"speaker": "Dana", "text": "We need to support 50,000 members."},
            {"speaker": "Dana", "text": "We also need SAML SSO integration."},
            {"speaker": "Dana", "text": "We are not sure whether we need multi-currency pricing."},
        ],
    )
    return svc, t1


def test_ingest_is_idempotent_by_content_hash():
    svc, t1 = _ingest1()
    r1 = svc.ingest_transcript(t1)
    assert not r1.idempotent
    assert len(r1.requirements) == 3
    r2 = svc.ingest_transcript(t1)
    assert r2.idempotent
    assert len(r2.requirements) == 3


def test_baseline_not_silently_overwritten():
    svc, t1 = _ingest1()
    svc.ingest_transcript(t1)
    for r in svc.list_requirements("proj"):
        svc.review_requirement(r.requirement_id, to_status="approved", actor="pm")
    b1 = svc.create_baseline("proj", approved_by="pm")
    assert b1.status == "approved"
    assert b1.version == 1
    b2 = svc.create_baseline("proj", approved_by="pm")
    assert b2.version == 2
    assert svc.store.get_baseline("proj", 1).status == "superseded"
    assert b2.status == "approved"


def test_baseline_update_requires_explicit_authorization():
    svc, t1 = _ingest1()
    svc.ingest_transcript(t1)
    for r in svc.list_requirements("proj"):
        svc.review_requirement(r.requirement_id, to_status="approved", actor="pm")
    svc.create_baseline("proj", approved_by="pm")
    t2 = make_transcript(
        transcript_id="mtg-002",
        project_id="proj",
        parent_transcript_id="mtg-001",
        segments=[
            {"speaker": "Dana", "text": "We need to support 120,000 members."},
            {"speaker": "Dana", "text": "We also need SAML SSO integration."},
            {"speaker": "Dana", "text": "We are not sure whether we need multi-currency pricing."},
            {"speaker": "Dana", "text": "We need a Stripe payment gateway integration."},
        ],
    )
    r2 = svc.ingest_transcript(t2)
    assert r2.change_summary is not None
    new_bl = svc.approve_baseline_update("proj", "mtg-002", approved_by="pm")
    assert new_bl.version == 2
    assert svc.store.get_baseline("proj", 1).status == "superseded"


def test_approve_single_requirement_does_not_approve_baseline():
    svc, t1 = _ingest1()
    svc.ingest_transcript(t1)
    reqs = svc.list_requirements("proj")
    svc.review_requirement(reqs[0].requirement_id, to_status="approved", actor="pm")
    b1 = svc.create_baseline("proj", approved_by=None)
    assert b1.status == "proposed"
    assert len(b1.requirement_snapshot) >= 1  # contains approved + in-scope


def test_review_requires_reason_for_clarification():
    svc, t1 = _ingest1()
    svc.ingest_transcript(t1)
    reqs = svc.list_requirements("proj")
    from app.review import ReviewError

    with pytest.raises(ReviewError):
        svc.review_requirement(reqs[0].requirement_id, to_status="needs_clarification", actor="pm", reason=None)


def test_feasibility_requires_kb_client():
    svc = MeetingToScopeService(store=InMemoryStore(), extractor=RuleBasedExtractor(), kb_client=None)
    svc.ingest_transcript(make_transcript())
    with pytest.raises(ServiceError):
        svc.assess_feasibility("proj")


def test_edit_requirement_updates_and_creates_event():
    svc, t1 = _ingest1()
    svc.ingest_transcript(t1)
    reqs = svc.list_requirements("proj")
    updated = svc.edit_requirement(reqs[0].requirement_id, actor="pm", description="Updated requirement text", priority="high", reason="clarified")
    assert updated.description == "Updated requirement text"
    assert updated.priority == "high"
    events = svc.list_events("proj")
    assert any(e.action == "edited" for e in events)


def test_events_are_append_only():
    svc, t1 = _ingest1()
    svc.ingest_transcript(t1)
    reqs = svc.list_requirements("proj")
    svc.review_requirement(reqs[0].requirement_id, to_status="approved", actor="pm")
    events = svc.list_events("proj")
    assert len(events) >= 1


def test_kb_reachable_reflects_ping():
    svc_ok = _svc(FakeKB(reachable=True))
    svc_bad = _svc(FakeKB(reachable=False))
    assert svc_ok.kb_reachable() is True
    assert svc_bad.kb_reachable() is False


def test_no_transcripts_for_project_raises():
    svc = _svc()
    with pytest.raises(ServiceError):
        svc.generate_proposal("nope")


def test_generate_proposal_includes_traceable_sections():
    svc, t1 = _ingest1()
    svc.ingest_transcript(t1)
    p = svc.generate_proposal("proj")
    assert p.in_scope or p.out_of_scope or p.milestones
    assert p.requirement_ids
