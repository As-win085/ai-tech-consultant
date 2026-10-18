"""Baseline change detection: added/removed/modified/clarified/unresolved + scope creep."""

from __future__ import annotations

from app.baseline import build_baseline_update_proposal, compute_change_summary, create_baseline
from app.extractor import RuleBasedExtractor
from app.transcript import new_transcript

CUSTOMER = {"name": "Dana", "side": "customer"}
CONSULTANT = {"name": "Sam", "side": "consultant"}


def _reqs(segments):
    t = new_transcript(transcript_id="t", project_id="p", participants=[CUSTOMER, CONSULTANT], segments=segments)
    return RuleBasedExtractor().extract(t).requirements


def _summary(baseline_reqs, new_reqs):
    baseline = create_baseline(project_id="p", requirements=baseline_reqs, version=1, approved_by="pm")
    return compute_change_summary(baseline, new_reqs, transcript_id="t2")


def _by_type(summary):
    out = {}
    for c in summary.changes:
        out.setdefault(c.change_type, []).append(c)
    return out


def test_added_requirement_and_scope_creep():
    base = _reqs([{"speaker": "Dana", "text": "We need to support 50,000 members."}])
    new = _reqs(
        [
            {"speaker": "Dana", "text": "We need to support 50,000 members."},
            {"speaker": "Dana", "text": "We need a Stripe payment gateway integration."},
        ]
    )
    summary = _summary(base, new)
    types = _by_type(summary)
    assert "added" in types
    assert any(c.scope_creep for c in types["added"])


def test_removed_requirement():
    base = _reqs(
        [
            {"speaker": "Dana", "text": "We need to support 50,000 members."},
            {"speaker": "Dana", "text": "We need a newsletter integration with Mailchimp."},
        ]
    )
    new = _reqs([{"speaker": "Dana", "text": "We need to support 50,000 members."}])
    summary = _summary(base, new)
    assert "removed" in _by_type(summary)
    assert not _by_type(summary)["removed"][0].scope_creep


def test_modified_scale_flagged_as_scope_creep():
    base = _reqs([{"speaker": "Dana", "text": "We need to support 50,000 members."}])
    new = _reqs([{"speaker": "Dana", "text": "We need to support 120,000 members."}])
    summary = _summary(base, new)
    modified = _by_type(summary).get("modified", [])
    assert modified
    assert modified[0].field == "scale"
    assert modified[0].scope_creep
    assert "50000" in modified[0].old_value and "120000" in modified[0].new_value


def test_unchanged_requirement_produces_no_change():
    base = _reqs([{"speaker": "Dana", "text": "We need to support 50,000 members."}])
    new = _reqs([{"speaker": "Dana", "text": "We need to support 50,000 members."}])
    summary = _summary(base, new)
    assert summary.changes == []


def test_unresolved_statement_is_not_scope_creep():
    base = _reqs([{"speaker": "Dana", "text": "We need to support 50,000 members."}])
    new = _reqs(
        [
            {"speaker": "Dana", "text": "We need to support 50,000 members."},
            {"speaker": "Dana", "text": "We are not sure whether we need multi-currency pricing."},
        ]
    )
    summary = _summary(base, new)
    unresolved = _by_type(summary).get("unresolved", [])
    assert unresolved
    assert not unresolved[0].scope_creep


def test_modified_integration_is_scope_creep():
    base = _reqs([{"speaker": "Dana", "text": "We need to integrate with SAML SSO."}])
    new = _reqs([{"speaker": "Dana", "text": "We need to integrate with SAML SSO and Okta specifically."}])
    summary = _summary(base, new)
    modified = _by_type(summary).get("modified", [])
    assert modified and modified[0].scope_creep


def test_baseline_update_proposal_is_proposed_not_applied():
    base = _reqs([{"speaker": "Dana", "text": "We need to support 50,000 members."}])
    new = _reqs([{"speaker": "Dana", "text": "We need to support 120,000 members."}])
    summary = _summary(base, new)
    baseline = create_baseline(project_id="p", requirements=base, version=1, approved_by="pm")
    proposal = build_baseline_update_proposal(summary, baseline)
    assert proposal.status == "proposed"
    assert proposal.proposed_version == 2
    assert proposal.changes
