"""v0.1 bias / risk detectors.

Each rule returns a BiasFinding (or None). Findings carry:
  rule_id          - stable identifier
  message          - human-readable warning
  severity         - 0 (info) .. 5 (critical); 0 never drives a decision
  proposed_decision- optional Decision the rule argues for

THRESHOLDS ARE PLACEHOLDERS, NOT CALIBRATED.
We have no real likelihood / calibration data in v0.1, so these are
deliberately simple, explainable heuristics. They will be replaced by the
roadmap's calibration / Bayesian work later.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .evidence import EvidenceSupport
from .exposure import Exposure
from .observation import Observation
from .state import RelationshipState


class Sensitivity(StrEnum):
    """How sensitively a thresholded detector fires (relationship kinds, S3).

    NORMAL is today's behavior. HIGH_EXIT_COST shifts the two rules with clean
    scalar thresholds toward earlier warning — the user who cannot easily
    leave needs to know sooner, not later. Ordinals map to this in `run_hooks`;
    the shifted threshold is always printed in the finding message so the
    basis stays auditable (DESIGN.md Do's #3).
    """

    NORMAL = "NORMAL"
    HIGH_EXIT_COST = "HIGH_EXIT_COST"


# --- tunable (uncalibrated) thresholds ---
ATTRACTION_TRUST_GAP = 3.0  # attraction - trust >= this is a gap worth flagging
ATTRACTION_TRUST_GAP_HIGH_EXIT_COST = 2.0  # earlier warning under HIGH exit cost
MIN_OBSERVATIONS_FOR_TRUST = 3  # fewer observations => trust is "unsupported"
RATIONALIZATION_RUN = 3  # N consecutive rationalizations
RATIONALIZATION_RUN_HIGH_EXIT_COST = 2  # earlier warning under HIGH exit cost


@dataclass
class BiasFinding:
    rule_id: str
    message: str
    severity: int  # 0 info, 1 low, 2, 3 medium, 4 high, 5 critical
    proposed_decision: str | None = None


def attraction_exceeds_trust(
    state: RelationshipState,
    observations: list[Observation],
    sensitivity: Sensitivity = Sensitivity.NORMAL,
) -> BiasFinding | None:
    """Rule #1: attraction high but trust has no supporting evidence yet."""
    gap = (
        ATTRACTION_TRUST_GAP_HIGH_EXIT_COST
        if sensitivity is Sensitivity.HIGH_EXIT_COST
        else ATTRACTION_TRUST_GAP
    )
    if (
        state.attraction - state.trust >= gap
        and len(observations) < MIN_OBSERVATIONS_FOR_TRUST
    ):
        message = (
            f"Attraction ({state.attraction:.1f}) significantly exceeds "
            f"supported trust ({state.trust:.1f})"
        )
        if sensitivity is Sensitivity.HIGH_EXIT_COST:
            message += f" (exit-cost sensitive: gap threshold {gap:.1f})"
        return BiasFinding(
            "attraction_exceeds_trust",
            message + ".",
            severity=2,
            proposed_decision="CONTINUE_OBSERVING",
        )
    return None


def repeated_rationalization(
    observations: list[Observation],
    sensitivity: Sensitivity = Sensitivity.NORMAL,
) -> BiasFinding | None:
    """Rule #2: consecutive self-serving explanations of anomalies."""
    threshold = (
        RATIONALIZATION_RUN_HIGH_EXIT_COST
        if sensitivity is Sensitivity.HIGH_EXIT_COST
        else RATIONALIZATION_RUN
    )
    best_run = run = 0
    for obs in sorted(observations, key=lambda o: o.timestamp):
        if obs.rationalization:
            run += 1
            best_run = max(best_run, run)
        else:
            run = 0
    if best_run >= threshold:
        message = f"{best_run} consecutive rationalizations detected"
        if sensitivity is Sensitivity.HIGH_EXIT_COST:
            message += f" (exit-cost sensitive: run threshold {threshold})"
        return BiasFinding(
            "repeated_rationalization",
            message + ".",
            severity=3,
            proposed_decision="CONTINUE_OBSERVING",
        )
    return None


def exposure_outpaces_evidence(
    exposure: Exposure, support: EvidenceSupport
) -> BiasFinding:
    """Rule #3: exposure growing faster than evidence.

    Compares total exposure against `support.support_units` (an explainable
    composite of observation breadth, source triangulation, rigor, and
    concreteness) instead of the v0.1 raw observation count.

    Always returns a finding: a warning when over-exposed, otherwise an
    explicit 'within support' info line (severity 0, no decision impact).
    """
    if support.observation_count == 0:
        return BiasFinding(
            "exposure_within_support",
            "No observations recorded yet; evidence base is empty.",
            severity=0,
            proposed_decision=None,
        )
    if exposure.total > support.support_units:
        return BiasFinding(
            "exposure_outpaces_evidence",
            f"Exposure ({exposure.total:.1f}) outpaces current evidence support "
            f"({support.support_units:.1f} units from "
            f"{support.observation_count} observations, "
            f"{support.distinct_sources} source(s)).",
            severity=3,
            proposed_decision="DECREASE_EXPOSURE",
        )
    return BiasFinding(
        "exposure_within_support",
        f"Exposure remains within evidence support "
        f"({support.support_units:.1f} units; "
        f"{support.with_alternative}/{support.observation_count} with alternative "
        f"explanations, "
        f"{support.with_claims}/{support.observation_count} with claims).",
        severity=0,
        proposed_decision=None,
    )


def high_emotion_major_decision(
    state: RelationshipState, exposure: Exposure
) -> BiasFinding | None:
    """Rule #4: impaired judgement while a major decision is on the table."""
    if state.emotional_state.is_high and exposure.life_decision > 0:
        return BiasFinding(
            "high_emotion_major_decision",
            "High emotional state while considering a major life decision.",
            severity=4,
            proposed_decision="PAUSE",
        )
    return None


def unresolved_inconsistencies(count: int) -> BiasFinding | None:
    """Rule #5: unresolved major inconsistencies."""
    if count > 0:
        return BiasFinding(
            "unresolved_inconsistencies",
            f"{count} unresolved inconsistencies.",
            severity=3 if count >= 2 else 2,
            proposed_decision="CONTINUE_OBSERVING",
        )
    return None
