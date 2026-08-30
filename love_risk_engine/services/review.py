"""Review workflow service.

`run_review` is the single entry point that:
  1. loads the relationship's state / exposure / observations / inconsistencies
  2. loads recorded hard-boundary hits
  3. runs all hooks (bias detectors)
  4. computes the decision
  5. persists a Review record
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List

from ..core.bias_detector import BiasFinding
from ..core.cooldown import cooldown_hours_for, is_blocking
from ..core.decision import Decision, decide
from ..core.evidence import EvidenceSupport, compute_evidence_support
from ..core.exposure import Exposure
from ..core.hooks import ReviewContext, run_hooks
from ..core.observation import Observation
from ..core.state import EmotionalState, RelationshipState
from ..storage.database import Database


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _now_utc_iso() -> str:
    from datetime import timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _expires_utc_iso(hours: int) -> str:
    from datetime import timedelta, timezone
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(
        timespec="seconds"
    )


@dataclass
class Review:
    id: str
    relationship_id: str
    timestamp: str
    triggered_hooks: List[str]
    unresolved_inconsistencies: int
    recommendation: str
    notes: str
    cooldown_id: str = ""  # set when a cooldown was created by this review


def _next_review_id(db: Database) -> str:
    cur = db.conn.execute(  # type: ignore[union-attr]
        "SELECT id FROM reviews WHERE id LIKE 'RV%'"
    )
    nums: List[int] = []
    for (val,) in cur.fetchall():
        try:
            nums.append(int(str(val)[2:]))
        except ValueError:
            pass
    n = (max(nums) + 1) if nums else 1
    return f"RV{n:03d}"


def build_context(db: Database, relationship_id: str) -> ReviewContext:
    """Assemble the data needed for a review from the database."""
    state = db.get_state(relationship_id) or RelationshipState(relationship_id)
    exposure = db.get_exposure(relationship_id) or Exposure(relationship_id)
    observations: List[Observation] = db.get_observations(relationship_id)
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
    )


def analyze(ctx: ReviewContext) -> tuple[List[BiasFinding], Decision]:
    """Run hooks and decide. Pure: does not touch the database."""
    findings = run_hooks(ctx)
    decision = decide(findings, ctx.hard_boundary_hit)
    return findings, decision


def run_review(db: Database, relationship_id: str) -> Review:
    ctx = build_context(db, relationship_id)
    findings, decision = analyze(ctx)
    inconsistencies_count = ctx.inconsistency_count

    cooldown_id = ""
    if is_blocking(decision):
        hours = cooldown_hours_for(decision)
        reason = "; ".join(
            f.rule_id for f in findings if f.proposed_decision == decision.value
        ) or decision.value
        cooldown_id = db.add_cooldown(
            relationship_id=relationship_id,
            decision=decision.value,
            reason=reason,
            started_at=_now_utc_iso(),
            expires_at=_expires_utc_iso(hours),
        )

    review = Review(
        id=_next_review_id(db),
        relationship_id=relationship_id,
        timestamp=_now(),
        triggered_hooks=[f.rule_id for f in findings],
        unresolved_inconsistencies=inconsistencies_count,
        recommendation=decision.value,
        notes="; ".join(f.message for f in findings),
        cooldown_id=cooldown_id,
    )
    db.save_review(review)
    return review
