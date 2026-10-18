"""Human review: transitions, audit events, approval semantics."""

from __future__ import annotations

import pytest

from app.review import (
    ReviewError,
    allowed_transitions,
    can_transition,
    make_event,
    require_reason,
    validate_transition,
)


def test_valid_requirement_transitions():
    assert can_transition("requirement", "pending_review", "approved")
    assert can_transition("requirement", "pending_review", "rejected")
    assert can_transition("requirement", "pending_review", "needs_clarification")
    assert can_transition("requirement", "approved", "needs_clarification")
    assert not can_transition("requirement", "approved", "rejected")
    assert not can_transition("requirement", "rejected", "approved")


def test_invalid_transition_raises():
    with pytest.raises(ReviewError):
        validate_transition("requirement", "approved", "rejected")
    with pytest.raises(ReviewError):
        validate_transition("proposal", "approved", "rejected")


def test_reason_required_for_rejection_and_clarification():
    require_reason("approved", None)
    require_reason("pending_review", None)
    with pytest.raises(ReviewError):
        require_reason("rejected", None)
    with pytest.raises(ReviewError):
        require_reason("rejected", "   ")
    require_reason("rejected", "explanation is fine")


def test_proposal_transitions_are_tight():
    allowed = allowed_transitions("proposal", "in_review")
    assert {"approved", "rejected", "draft"} <= allowed
    allowed = allowed_transitions("proposal", "approved")
    assert "superseded" in allowed
    assert "rejected" not in allowed


def test_baseline_only_approved_then_superseded():
    assert allowed_transitions("baseline", "proposed") == {"approved"}
    assert allowed_transitions("baseline", "approved") == {"superseded"}
    assert not can_transition("baseline", "proposed", "rejected")


def test_scope_change_transitions():
    assert can_transition("scope_change", "proposed", "accepted")
    assert can_transition("scope_change", "proposed", "rejected")
    assert can_transition("scope_change", "needs_review", "accepted")
    assert not can_transition("scope_change", "accepted", "rejected")


def test_make_event_records_audit():
    ev = make_event(entity_type="requirement", entity_id="r1", action="approved", project_id="p1", from_status="pending_review", to_status="approved", actor="pm", reason=None)
    assert ev.id
    assert ev.at
    assert ev.entity_type == "requirement"
