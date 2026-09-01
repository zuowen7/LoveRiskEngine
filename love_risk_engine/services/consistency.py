"""Orchestration for the informational self-consistency audit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from ..core.bias_detector import BiasFinding
from ..core.consistency import audit_consistency
from ..core.timeutil import parse_iso, utc_now_iso
from ..storage.database import Database


@dataclass(frozen=True)
class ConsistencyAudit:
    relationship_id: str
    days: int
    start: str
    end: str
    findings: list[BiasFinding]


def run_consistency_audit(
    db: Database,
    relationship_id: str,
    *,
    days: int = 30,
    now: str | None = None,
) -> ConsistencyAudit:
    """Load domain records and run both consistency-audit stages."""
    if days <= 0:
        raise ValueError("days must be a positive integer")
    if db.get_relationship(relationship_id) is None:
        raise ValueError(f"relationship {relationship_id!r} not found")

    end_at = parse_iso(now or utc_now_iso())
    if end_at is None:
        raise ValueError("now must be a valid ISO-8601 timestamp")
    start_at = end_at - timedelta(days=days)
    start = start_at.isoformat(timespec="seconds")
    end = end_at.isoformat(timespec="seconds")

    observations = db.get_observations(relationship_id)
    verification_transitions = [
        item.verified_at
        for item in db.list_verification_items(relationship_id)
        if item.verified_at
    ]
    evidence_timestamps = [observation.timestamp for observation in observations]
    evidence_timestamps.extend(verification_transitions)
    unresolved_structured_count = sum(
        1
        for item in db.list_inconsistencies(relationship_id, resolved=False)
        if item.kind == "detected"
    )
    findings = audit_consistency(
        target_relationship_id=relationship_id,
        state_history=db.list_state_history(relationship_id),
        observations=observations,
        all_observations=db.list_all_observations(),
        evidence_timestamps=evidence_timestamps,
        unresolved_structured_count=unresolved_structured_count,
        start=start,
        end=end,
    )
    return ConsistencyAudit(
        relationship_id=relationship_id,
        days=days,
        start=start,
        end=end,
        findings=findings,
    )
