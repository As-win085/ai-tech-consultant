"""Human-review workflow: status transitions and audit history.

Review is where a human decides on extracted requirements, proposals, baselines,
and detected scope changes. This module enforces *valid* state transitions and
records an immutable audit :class:`~app.schemas.ReviewEvent` for every action.

Key guarantees:
* Approving a single requirement does **not** approve a proposal or baseline.
* A proposal/baseline can only be approved by an explicit authorized action.
* Rejections and clarifications require (and record) a reason.
* Invalid transitions raise :class:`ReviewError` rather than silently applying.
"""

from __future__ import annotations

import uuid

from app.schemas import ReviewEvent, utcnow

# entity_type -> {from_status: {allowed_to_status, ...}}
TRANSITIONS: dict[str, dict[str, set[str]]] = {
    "requirement": {
        "pending_review": {"approved", "rejected", "needs_clarification"},
        "needs_clarification": {"approved", "rejected", "pending_review"},
        "approved": {"needs_clarification"},
        "rejected": {"needs_clarification"},
    },
    "proposal": {
        "draft": {"in_review", "rejected"},
        "in_review": {"approved", "rejected", "draft"},
        "approved": {"superseded"},
        "rejected": {"draft"},
        "superseded": set(),
    },
    "baseline": {
        "proposed": {"approved"},
        "approved": {"superseded"},
        "superseded": set(),
    },
    "scope_change": {
        "proposed": {"accepted", "rejected", "needs_review"},
        "needs_review": {"accepted", "rejected"},
        "accepted": set(),
        "rejected": set(),
    },
}


class ReviewError(ValueError):
    """An invalid review action (bad transition, missing reason, unknown entity)."""


def allowed_transitions(entity_type: str, from_status: str) -> set[str]:
    return set(TRANSITIONS.get(entity_type, {}).get(from_status, set()))


def can_transition(entity_type: str, from_status: str, to_status: str) -> bool:
    return to_status in allowed_transitions(entity_type, from_status)


def validate_transition(entity_type: str, from_status: str, to_status: str) -> None:
    if entity_type not in TRANSITIONS:
        raise ReviewError(f"unknown entity type: {entity_type!r}")
    if from_status not in TRANSITIONS[entity_type]:
        raise ReviewError(f"unknown status for {entity_type}: {from_status!r}")
    if to_status not in TRANSITIONS[entity_type][from_status]:
        raise ReviewError(
            f"invalid transition for {entity_type}: {from_status!r} -> {to_status!r}"
        )


def make_event(
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    project_id: str | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    actor: str | None = None,
    reason: str | None = None,
) -> ReviewEvent:
    return ReviewEvent(
        id=f"evt-{uuid.uuid4().hex[:12]}",
        project_id=project_id,
        entity_type=entity_type,  # type: ignore[arg-type]
        entity_id=entity_id,
        action=action,
        from_status=from_status,
        to_status=to_status,
        actor=actor,
        reason=reason,
        at=utcnow(),
    )


def require_reason(to_status: str, reason: str | None) -> None:
    if to_status in {"rejected", "needs_clarification", "needs_review"} and not (reason or "").strip():
        raise ReviewError(f"a reason is required when moving to {to_status!r}")
