"""Hook runner: assembles the review context and runs the detectors.

A "hook" is a check that may raise a warning. `run_hooks` returns the list of
findings for the current relationship; the decision engine consumes it.

Since S1 the relationship's `RelationshipProfile` decides which hooks run
(`enabled_hooks`) and, from S3, how sensitively (`exit_cost`). Every kind runs
the original six v0.1 detectors; windowed kinds (BOSS / MENTOR / COLLEAGUE)
additionally run `promise_expiry`.
"""

from __future__ import annotations

from dataclasses import dataclass

from .bias_detector import (
    BiasFinding,
    Sensitivity,
    attraction_exceeds_trust,
    exposure_outpaces_evidence,
    high_emotion_major_decision,
    repeated_rationalization,
    unresolved_inconsistencies,
)
from .escalation import detect_rapid_exposure_escalation
from .evidence import EvidenceSupport
from .exposure import Exposure
from .history import ExposureChange
from .observation import Observation
from .patterns import detect_love_bombing
from .profiles import Ordinal, RelationshipProfile
from .promises import detect_expired_promises, detect_repeated_repromises
from .state import RelationshipState


@dataclass
class ReviewContext:
    state: RelationshipState
    exposure: Exposure
    observations: list[Observation]
    inconsistency_count: int
    hard_boundary_hit: bool
    evidence_support: EvidenceSupport
    profile: RelationshipProfile
    exposure_history: list[ExposureChange]


def run_hooks(ctx: ReviewContext) -> list[BiasFinding]:
    findings: list[BiasFinding] = []
    hooks = set(ctx.profile.enabled_hooks)
    sensitivity = (
        Sensitivity.HIGH_EXIT_COST
        if ctx.profile.exit_cost is Ordinal.HIGH
        else Sensitivity.NORMAL
    )

    if "attraction_exceeds_trust" in hooks:
        f = attraction_exceeds_trust(ctx.state, ctx.observations, sensitivity)
        if f:
            findings.append(f)

    if "repeated_rationalization" in hooks:
        f = repeated_rationalization(ctx.observations, sensitivity)
        if f:
            findings.append(f)

    if "exposure_outpaces_evidence" in hooks:
        findings.append(exposure_outpaces_evidence(ctx.exposure, ctx.evidence_support))

    if "high_emotion_major_decision" in hooks:
        f = high_emotion_major_decision(ctx.state, ctx.exposure)
        if f:
            findings.append(f)

    if "unresolved_inconsistencies" in hooks:
        f = unresolved_inconsistencies(ctx.inconsistency_count)
        if f:
            findings.append(f)

    if "love_bombing_pattern" in hooks:
        f = detect_love_bombing(ctx.observations)
        if f:
            findings.append(f)

    if "rapid_exposure_escalation" in hooks:
        f = detect_rapid_exposure_escalation(ctx.exposure_history, ctx.observations)
        if f:
            findings.append(f)

    if "promise_expiry" in hooks:
        f = detect_expired_promises(ctx.observations, ctx.profile.promise_window_days)
        if f:
            findings.append(f)

    if "repeated_repromises" in hooks:
        f = detect_repeated_repromises(
            ctx.observations, ctx.profile.promise_window_days
        )
        if f:
            findings.append(f)

    return findings
