"""Counterfactual review service (roadmap #2).

Re-runs a stored review against only the evidence available at that time — an
audit of your past decision and of the rationalization since. This is also the
honest generator of user-labeled decision outcomes for the calibration
strategy (ARCHITECTURE_AND_PLAN.md §4): nothing here feeds back into the
engine automatically.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.counterfactual import (
    FrozenEvidence,
    freeze_boundary_hits,
    freeze_exposure,
    freeze_inconsistency_count,
    freeze_observations,
    freeze_state,
)
from ..core.decision import decide
from ..core.evidence import compute_evidence_support
from ..core.hooks import ReviewContext, run_hooks
from ..core.profiles import PROFILES, get_profile
from ..core.relationship import Kind
from ..storage.database import Database


@dataclass(frozen=True)
class CounterfactualResult:
    review_id: str
    as_of: str
    original_recommendation: str
    recomputed_recommendation: str
    matched: bool
    fired_rule_ids: tuple[str, ...]
    evidence: FrozenEvidence


def run_counterfactual(
    db: Database, relationship_id: str, review_id: str
) -> CounterfactualResult:
    """Recompute a stored review against the evidence frozen at its timestamp."""
    review = db.get_review(review_id)
    if review is None:
        raise ValueError(f"review {review_id!r} not found")
    if review.relationship_id != relationship_id:
        raise ValueError(f"review {review_id!r} belongs to another relationship")
    rel = db.get_relationship(relationship_id)
    profile = get_profile(rel.kind) if rel else PROFILES[Kind.LOVER]
    as_of = review.timestamp

    observations = freeze_observations(db.get_observations(relationship_id), as_of)
    state = freeze_state(db.list_state_history(relationship_id), relationship_id, as_of)
    exposure = freeze_exposure(
        db.list_exposure_history(relationship_id), relationship_id, as_of
    )
    hits = freeze_boundary_hits(db.list_boundary_hits(relationship_id), as_of)
    inc_count = freeze_inconsistency_count(
        db.list_all_inconsistencies(relationship_id), as_of
    )
    exposure_history = [
        h for h in db.list_exposure_history(relationship_id) if h.timestamp <= as_of
    ]
    support = compute_evidence_support(observations)

    ctx = ReviewContext(
        state=state,
        exposure=exposure,
        observations=observations,
        inconsistency_count=inc_count,
        hard_boundary_hit=len(hits) > 0,
        evidence_support=support,
        profile=profile,
        exposure_history=exposure_history,
    )
    findings = run_hooks(ctx)
    decision = decide(findings, ctx.hard_boundary_hit)

    evidence = FrozenEvidence(
        review_id=review_id,
        as_of=as_of,
        observation_count=len(observations),
        boundary_hit_count=len(hits),
        unresolved_inconsistency_count=inc_count,
        exposure_total=exposure.total,
        attraction=state.attraction,
        trust=state.trust,
        uncertainty=state.uncertainty,
        emotional_state=state.emotional_state.value,
    )
    return CounterfactualResult(
        review_id=review_id,
        as_of=as_of,
        original_recommendation=review.recommendation,
        recomputed_recommendation=decision.value,
        matched=decision.value == review.recommendation,
        fired_rule_ids=tuple(f.rule_id for f in findings),
        evidence=evidence,
    )
