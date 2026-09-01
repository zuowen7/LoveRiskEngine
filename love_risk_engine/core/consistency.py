"""Pure record-level self-consistency audit rules.

The module deliberately does not attempt to detect a hidden psychological
state. It compares explicit, timestamped records and returns informational
findings with no proposed decision. Same inputs always produce the same audit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from .bias_detector import BiasFinding
from .history import StateChange
from .observation import JudgmentDirection, Observation
from .timeutil import parse_iso

SELF_REPORTED_RATIONALIZATION_RUN = 3  # uncalibrated


@dataclass(frozen=True)
class CriterionDirectionCandidate:
    """Two records using the same criterion with opposite trust directions."""

    criterion_key: str
    observation_a_id: str
    relationship_a_id: str
    direction_a: JudgmentDirection
    observation_b_id: str
    relationship_b_id: str
    direction_b: JudgmentDirection


def normalize_criterion_key(value: str) -> str:
    """Normalize an explicit comparison key, never observation free text."""
    return re.sub(r"[\s_-]+", "_", value.strip().lower()).strip("_")


def _dated(value: str) -> datetime | None:
    return parse_iso(value)


def _window_bounds(start: str, end: str) -> tuple[datetime, datetime]:
    start_at = _dated(start)
    end_at = _dated(end)
    if start_at is None or end_at is None:
        raise ValueError("audit window timestamps must be valid ISO-8601 values")
    if start_at > end_at:
        raise ValueError("audit window start must not be after end")
    return start_at, end_at


def _in_window(value: str, start_at: datetime, end_at: datetime) -> bool:
    at = _dated(value)
    return at is not None and start_at <= at <= end_at


def trust_change_without_new_evidence(
    history: list[StateChange],
    evidence_timestamps: list[str],
    start: str,
    end: str,
) -> BiasFinding | None:
    """Surface trust transitions with no newly timestamped evidence.

    Evidence uses the open/closed interval `(previous, current]`: a record at
    the previous snapshot is already known, while one at the current snapshot
    may support the update. Reconsidering older evidence remains a valid
    explanation, so the finding is informational only.
    """
    start_at, end_at = _window_bounds(start, end)
    dated_history = [
        (at, change) for change in history if (at := _dated(change.timestamp))
    ]
    dated_history.sort(key=lambda item: (item[0], item[1].id))
    evidence = [at for value in evidence_timestamps if (at := _dated(value))]
    gaps: list[tuple[StateChange, StateChange]] = []
    for (previous_at, previous), (current_at, current) in zip(
        dated_history, dated_history[1:], strict=False
    ):
        if not start_at <= current_at <= end_at or previous.trust == current.trust:
            continue
        if not any(previous_at < evidence_at <= current_at for evidence_at in evidence):
            gaps.append((previous, current))
    if not gaps:
        return None
    previous, current = gaps[-1]
    return BiasFinding(
        "trust_change_without_new_evidence",
        f"{len(gaps)} trust change(s) had no currently recorded observation or "
        f"verification timestamp between snapshots; latest "
        f"{previous.id}->{current.id}: {previous.trust:.1f} -> "
        f"{current.trust:.1f}. This may reflect reconsideration of older "
        "evidence or a missing record, not self-deception.",
        severity=1,
        proposed_decision=None,
        msg_key="trust_change_without_new_evidence",
        msg_params={
            "count": str(len(gaps)),
            "previous_id": previous.id,
            "current_id": current.id,
            "before": f"{previous.trust:.1f}",
            "after": f"{current.trust:.1f}",
        },
    )


def interpretation_without_alternative(
    observations: list[Observation], start: str, end: str
) -> BiasFinding | None:
    """Surface windowed interpretations that lack an alternative reading."""
    start_at, end_at = _window_bounds(start, end)
    missing = sorted(
        (
            observation
            for observation in observations
            if _in_window(observation.timestamp, start_at, end_at)
            and observation.interpretation.strip()
            and not observation.alternative_explanation.strip()
        ),
        key=lambda observation: (observation.timestamp, observation.id),
    )
    if not missing:
        return None
    ids = ", ".join(observation.id for observation in missing[:5])
    if len(missing) > 5:
        ids += ", ..."
    return BiasFinding(
        "interpretation_without_alternative",
        f"{len(missing)} interpretation(s) have no recorded alternative "
        f"explanation ({ids}). This is a one-sided record, not proof that the "
        "interpretation is wrong.",
        severity=1,
        proposed_decision=None,
        msg_key="interpretation_without_alternative",
        msg_params={"count": str(len(missing)), "ids": ids},
    )


def self_reported_rationalization_run(
    observations: list[Observation], start: str, end: str
) -> BiasFinding | None:
    """Report the longest run of explicit, user-supplied rationalization flags."""
    start_at, end_at = _window_bounds(start, end)
    ordered = sorted(
        (
            observation
            for observation in observations
            if _in_window(observation.timestamp, start_at, end_at)
        ),
        key=lambda observation: (_dated(observation.timestamp), observation.id),
    )
    best_run = run = 0
    for observation in ordered:
        if observation.rationalization:
            run += 1
            best_run = max(best_run, run)
        else:
            run = 0
    if best_run < SELF_REPORTED_RATIONALIZATION_RUN:
        return None
    return BiasFinding(
        "self_reported_rationalization_run",
        f"{best_run} consecutive self-reported rationalization flags were "
        "recorded. These are user annotations, not automatic psychological "
        "detection.",
        severity=1,
        proposed_decision=None,
        msg_key="self_reported_rationalization_run",
        msg_params={"count": str(best_run)},
    )


def unresolved_structured_conflicts(count: int) -> BiasFinding | None:
    """Report persisted, unresolved structured conflicts only."""
    if count <= 0:
        return None
    return BiasFinding(
        "unresolved_structured_conflicts",
        f"{count} unresolved structured conflict(s) are recorded. This does "
        "not include semantic conflicts inferred from free text.",
        severity=1,
        proposed_decision=None,
        msg_key="unresolved_structured_conflicts",
        msg_params={"count": str(count)},
    )


def detect_criterion_direction_conflicts(
    observations: list[Observation],
    target_relationship_id: str,
    start: str,
    end: str,
) -> list[CriterionDirectionCandidate]:
    """Compare opposite explicit directions under the same explicit key."""
    start_at, end_at = _window_bounds(start, end)
    comparable = sorted(
        (
            observation
            for observation in observations
            if _in_window(observation.timestamp, start_at, end_at)
            and normalize_criterion_key(observation.criterion_key)
            and observation.judgment_direction
            in {
                JudgmentDirection.SUPPORTS_TRUST,
                JudgmentDirection.WEAKENS_TRUST,
            }
        ),
        key=lambda observation: (observation.timestamp, observation.id),
    )
    candidates: list[CriterionDirectionCandidate] = []
    for index, observation_a in enumerate(comparable):
        key_a = normalize_criterion_key(observation_a.criterion_key)
        for observation_b in comparable[index + 1 :]:
            if normalize_criterion_key(observation_b.criterion_key) != key_a:
                continue
            if observation_a.judgment_direction == observation_b.judgment_direction:
                continue
            if target_relationship_id not in {
                observation_a.relationship_id,
                observation_b.relationship_id,
            }:
                continue
            candidates.append(
                CriterionDirectionCandidate(
                    criterion_key=key_a,
                    observation_a_id=observation_a.id,
                    relationship_a_id=observation_a.relationship_id,
                    direction_a=observation_a.judgment_direction,
                    observation_b_id=observation_b.id,
                    relationship_b_id=observation_b.relationship_id,
                    direction_b=observation_b.judgment_direction,
                )
            )
    return candidates


def _criterion_direction_conflict(
    candidates: list[CriterionDirectionCandidate],
) -> BiasFinding | None:
    if not candidates:
        return None
    first = candidates[0]
    return BiasFinding(
        "criterion_direction_conflict",
        f"{len(candidates)} pair(s) use the same explicit criterion with "
        f"opposite trust directions; first '{first.criterion_key}' "
        f"({first.observation_a_id}/{first.relationship_a_id} "
        f"{first.direction_a.value} vs {first.observation_b_id}/"
        f"{first.relationship_b_id} {first.direction_b.value}). Context may "
        "justify the difference; this is a review candidate, not a diagnosis.",
        severity=1,
        proposed_decision=None,
        msg_key="criterion_direction_conflict",
        msg_params={
            "count": str(len(candidates)),
            "criterion": first.criterion_key,
            "observation_a": first.observation_a_id,
            "relationship_a": first.relationship_a_id,
            "direction_a": first.direction_a.value,
            "observation_b": first.observation_b_id,
            "relationship_b": first.relationship_b_id,
            "direction_b": first.direction_b.value,
        },
    )


def audit_consistency(
    *,
    target_relationship_id: str,
    state_history: list[StateChange],
    observations: list[Observation],
    all_observations: list[Observation],
    evidence_timestamps: list[str],
    unresolved_structured_count: int,
    start: str,
    end: str,
) -> list[BiasFinding]:
    """Run all audit rules in the documented, deterministic order."""
    candidates = detect_criterion_direction_conflicts(
        all_observations, target_relationship_id, start, end
    )
    possible = (
        trust_change_without_new_evidence(
            state_history, evidence_timestamps, start, end
        ),
        interpretation_without_alternative(observations, start, end),
        self_reported_rationalization_run(observations, start, end),
        unresolved_structured_conflicts(unresolved_structured_count),
        _criterion_direction_conflict(candidates),
    )
    return [finding for finding in possible if finding is not None]
