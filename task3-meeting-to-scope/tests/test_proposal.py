"""Proposal generation: completeness, traceability, and honest estimates."""

from __future__ import annotations

from app.feasibility import assess_requirements
from app.extractor import RuleBasedExtractor
from app.proposal import build_proposal, render_proposal_markdown
from tests.conftest import FakeKB, insufficient_answer, make_transcript, sufficient_answer


def _build(kb=None):
    kb = kb or FakeKB([("sso", sufficient_answer())])
    t = make_transcript(
        segments=[
            {"speaker": "Dana", "timestamp": "00:01:00", "text": "We need to support 50,000 members so that the site stays fast."},
            {"speaker": "Dana", "timestamp": "00:02:00", "text": "We also need SAML SSO integration."},
            {"speaker": "Dana", "timestamp": "00:03:00", "text": "I assume PCI compliance is handled by the host."},
            {"speaker": "Dana", "timestamp": "00:04:00", "text": "We are not sure whether we need multi-currency pricing."},
            {"speaker": "Sam", "timestamp": "00:05:00", "text": "We could add a caching layer."},
        ]
    )
    reqs = RuleBasedExtractor().extract(t).requirements
    assessments = assess_requirements(reqs, kb)
    return build_proposal(t, reqs, assessments)


def test_proposal_has_required_sections():
    p = _build()
    assert p.overview
    assert p.in_scope
    assert p.milestones
    assert p.estimates
    assert p.exclusions
    assert p.estimate_conditions


def test_every_scope_item_is_traceable():
    p = _build()
    for item in p.in_scope:
        assert item.requirement_ids
    for d in p.deliverables:
        assert d.requirement_ids


def test_estimates_are_preliminary_with_ranges():
    p = _build()
    assert p.estimates
    for e in p.estimates:
        assert e.provisional is True
        assert e.high >= e.low
        assert e.rationale
        assert e.conditions


def test_out_of_scope_lists_consultant_proposals():
    p = _build()
    assert any("caching" in item.description.lower() for item in p.out_of_scope)


def test_assumptions_and_open_questions_are_separated():
    p = _build()
    assert any("pci" in a.lower() for a in p.assumptions)
    assert any("multi-currency" in q.question.lower() for q in p.open_questions)


def test_unsupported_requirement_becomes_a_risk():
    p = _build(kb=FakeKB(default=insufficient_answer()))
    assert any("must be validated" in r.description for r in p.risks)


def test_no_invented_acceptance_criteria_or_prices():
    p = _build()
    # none were stated, so none are fabricated
    assert p.acceptance_criteria == []
    markdown = render_proposal_markdown(p)
    assert "not invented" in markdown
    assert "$" not in markdown


def test_markdown_renders():
    md = render_proposal_markdown(_build())
    assert "# " in md
    assert "In scope" in md
    assert "Preliminary estimates" in md
