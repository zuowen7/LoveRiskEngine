"""Review workflow service.

`run_review` is the single entry point that:
  1. loads the relationship's state / exposure / observations / inconsistencies
  2. loads recorded hard-boundary hits
  3. runs all hooks (bias detectors)
  4. computes the decision
  5. persists a Review record
"""

from __future__ import annotations

import contextlib

from ..core.bias_detector import BiasFinding
from ..core.cooldown import cooldown_hours_for, is_blocking
from ..core.decision import Decision, decide
from ..core.evidence import EvidenceSupport, compute_evidence_support
from ..core.exposure import Exposure
from ..core.hooks import ReviewContext, run_hooks
from ..core.observation import Observation
from ..core.profiles import PROFILES, get_profile
from ..core.relationship import Kind
from ..core.review import Review
from ..core.state import RelationshipState
from ..core.timeutil import expires_utc_iso, utc_now_iso
from ..storage.database import Database


def _next_review_id(db: Database) -> str:
    cur = db._db.execute("SELECT id FROM reviews WHERE id LIKE 'RV%'")
    nums: list[int] = []
    for (val,) in cur.fetchall():
        with contextlib.suppress(ValueError):
            nums.append(int(str(val)[2:]))
    n = (max(nums) + 1) if nums else 1
    return f"RV{n:03d}"


def build_context(db: Database, relationship_id: str) -> ReviewContext:
    """Assemble the data needed for a review from the database."""
    rel = db.get_relationship(relationship_id)
    profile = get_profile(rel.kind) if rel else PROFILES[Kind.LOVER]
    state = db.get_state(relationship_id) or RelationshipState(relationship_id)
    exposure = db.get_exposure(relationship_id) or Exposure(relationship_id)
    observations: list[Observation] = db.get_observations(relationship_id)
    exposure_history = db.list_exposure_history(relationship_id)
    inconsistencies = db.list_inconsistencies(relationship_id, resolved=False)
    hard_hits = db.list_boundary_hits(relationship_id, only_hard=True)
    support: EvidenceSupport = compute_evidence_support(observations)
    return ReviewContext(
        state=state,
        exposure=exposure,
        observations=observations,
        inconsistency_count=len(inconsistencies),
        hard_boundary_hit=len(hard_hits) > 0,
        evidence_support=support,
        profile=profile,
        exposure_history=exposure_history,
    )


def analyze(ctx: ReviewContext) -> tuple[list[BiasFinding], Decision]:
    """Run hooks and decide. Pure: does not touch the database."""
    findings = run_hooks(ctx)
    decision = decide(findings, ctx.hard_boundary_hit)
    return findings, decision


def run_review(
    db: Database, relationship_id: str, ctx: ReviewContext | None = None
) -> Review:
    """Run the full review workflow; `ctx` lets callers reuse an analysis."""
    if ctx is None:
        ctx = build_context(db, relationship_id)
    findings, decision = analyze(ctx)
    inconsistencies_count = ctx.inconsistency_count

    cooldown_id = ""
    if is_blocking(decision):
        hours = cooldown_hours_for(decision)
        reason = (
            "; ".join(
                f.rule_id for f in findings if f.proposed_decision == decision.value
            )
            or decision.value
        )
        cooldown_id = db.add_cooldown(
            relationship_id=relationship_id,
            decision=decision.value,
            reason=reason,
            started_at=utc_now_iso(),
            expires_at=expires_utc_iso(hours),
        )

    review = Review(
        id=_next_review_id(db),
        relationship_id=relationship_id,
        timestamp=utc_now_iso(),
        triggered_hooks=[f.rule_id for f in findings],
        unresolved_inconsistencies=inconsistencies_count,
        recommendation=decision.value,
        notes="; ".join(f.message for f in findings),
        cooldown_id=cooldown_id,
    )
    db.save_review(review)
    return review
