"""Feasibility assessment: explicit outcomes, honesty, and no fabricated citations."""

from __future__ import annotations

from tests.conftest import (
    FakeKB,
    conflicting_answer,
    insufficient_answer,
    make_transcript,
    sufficient_answer,
)
from app.feasibility import assess_requirement, assess_requirements
from app.kb_client import KbTimeout
from app.schemas import Requirement, utcnow


def _service(store, fake_kb, settings):
    from app.extractor import RuleBasedExtractor
    from app.service import MeetingToScopeService

    return MeetingToScopeService(store=store, extractor=RuleBasedExtractor(), kb_client=fake_kb, settings=settings)


def test_supported_by_knowledge(store, settings):
    kb = FakeKB([("sso", sufficient_answer())])
    reqs = make_transcript().segments
    from app.extractor import RuleBasedExtractor

    t = make_transcript(segments=[{"speaker": "Dana", "text": "We need SAML SSO integration."}])
    req = RuleBasedExtractor().extract(t).requirements[0]
    a = assess_requirement(req, kb)
    assert a.status == "supported_by_knowledge"
    assert a.citations  # carried through verbatim
    assert a.kb_request_id == "req-1"


def test_insufficient_evidence_is_not_impossibility():
    kb = FakeKB(default=insufficient_answer())
    t = make_transcript(segments=[{"speaker": "Dana", "text": "We need a quantum teleport module."}])
    from app.extractor import RuleBasedExtractor

    req = RuleBasedExtractor().extract(t).requirements[0]
    a = assess_requirement(req, kb)
    assert a.status == "not_supported_by_available_evidence"
    assert "not proof of impossibility" in a.basis


def test_conflicting_evidence_outcome():
    kb = FakeKB([("sso", conflicting_answer())])
    t = make_transcript(segments=[{"speaker": "Dana", "text": "We need SAML SSO integration."}])
    from app.extractor import RuleBasedExtractor

    req = RuleBasedExtractor().extract(t).requirements[0]
    a = assess_requirement(req, kb)
    assert a.status == "conflicting_evidence"


def test_kb_failure_yields_assessment_unavailable_without_citations():
    kb = FakeKB([("sso", KbTimeout("timed out"))])
    t = make_transcript(segments=[{"speaker": "Dana", "text": "We need SAML SSO integration."}])
    from app.extractor import RuleBasedExtractor

    req = RuleBasedExtractor().extract(t).requirements[0]
    a = assess_requirement(req, kb)
    assert a.status == "assessment_unavailable"
    assert a.citations == []
    assert a.error


def test_open_question_requires_customer_clarification_without_kb_call():
    kb = FakeKB()
    t = make_transcript(segments=[{"speaker": "Dana", "text": "We are not sure whether we need multi-currency pricing."}])
    from app.extractor import RuleBasedExtractor

    req = RuleBasedExtractor().extract(t).requirements[0]
    a = assess_requirement(req, kb)
    assert a.status == "requires_customer_clarification"
    assert kb.calls == []  # no KB call made


def test_proposed_solution_needs_validation_even_with_evidence():
    kb = FakeKB([("cach", sufficient_answer())])
    t = make_transcript(segments=[{"speaker": "Sam", "text": "We could add a caching layer."}])
    from app.extractor import RuleBasedExtractor

    req = RuleBasedExtractor().extract(t).requirements[0]
    a = assess_requirement(req, kb)
    assert a.status == "potentially_feasible_needs_validation"


def test_assess_requirements_returns_all():
    kb = FakeKB([("sso", sufficient_answer())])
    t = make_transcript()
    from app.extractor import RuleBasedExtractor

    reqs = RuleBasedExtractor().extract(t).requirements
    result = assess_requirements(reqs, kb)
    assert set(result) == {r.requirement_id for r in reqs}
