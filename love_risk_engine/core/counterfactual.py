"""Counterfactual review (roadmap #2): freeze evidence at a past timestamp.

"RedTeamMe": re-run a past decision against only the evidence that existed at
that time, to audit whether you would have decided differently — and whether
your current self is rationalizing the past. Everything here is pure: no
database, no clock.

Honesty notes (stated in the CLI output too):
  - The frozen unresolved-inconsistency count is an approximation: resolutions
    carry no timestamp, so we count rows created at or before `as_of` that are
    *currently* unresolved.
  - The recompute applies today's thresholds and profiles to past evidence;
    the rules may have changed since the original decision.
"""

from __future__ import annotations

from dataclasses import dataclass

from .boundaries import BoundaryHit
from .exposure import Exposure
from .history import ExposureChange, StateChange
from .inconsistency import Inconsistency
from .observation import Observation
from .state import EmotionalState, RelationshipState


@dataclass(frozen=True)
class FrozenEvidence:
    review_id: str
    as_of: str
    observation_count: int
    boundary_hit_count: int
    unresolved_inconsistency_count: int
    exposure_total: float
    attraction: float
    trust: float
    uncertainty: float
    emotional_state: str


def _not_after(timestamp: str, as_of: str) -> bool:
    return timestamp <= as_of


def freeze_state(
    history: list[StateChange], relationship_id: str, as_of: str
) -> RelationshipState:
    rows = [h for h in history if _not_after(h.timestamp, as_of)]
    if not rows:
        return RelationshipState(relationship_id)
    latest = max(rows, key=lambda h: (h.timestamp, h.id))
    try:
        emotional = EmotionalState(latest.emotional_state)
    except ValueError:
        emotional = EmotionalState.NEUTRAL  # fail open on corrupt rows
    return RelationshipState(
        relationship_id,
        attraction=latest.attraction,
        trust=latest.trust,
        uncertainty=latest.uncertainty,
        emotional_state=emotional,
    )


def freeze_exposure(
    history: list[ExposureChange], relationship_id: str, as_of: str
) -> Exposure:
    rows = [h for h in history if _not_after(h.timestamp, as_of)]
    if not rows:
        return Exposure(relationship_id)
    latest = max(rows, key=lambda h: (h.timestamp, h.id))
    return Exposure(
        relationship_id,
        time=latest.time,
        emotional=latest.emotional,
        privacy=latest.privacy,
        financial=latest.financial,
        life_decision=latest.life_decision,
    )


def freeze_observations(
    observations: list[Observation], as_of: str
) -> list[Observation]:
    return [o for o in observations if _not_after(o.timestamp, as_of)]


def freeze_boundary_hits(hits: list[BoundaryHit], as_of: str) -> list[BoundaryHit]:
    return [h for h in hits if _not_after(h.timestamp, as_of)]


def freeze_inconsistency_count(items: list[Inconsistency], as_of: str) -> int:
    return sum(1 for i in items if _not_after(i.created_at, as_of) and not i.resolved)
