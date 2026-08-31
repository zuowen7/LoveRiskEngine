"""Hook runner: assembles the review context and runs all v0.1 detectors.

A "hook" is a check that may raise a warning. `run_hooks` returns the list of
findings for the current relationship; the decision engine consumes it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .bias_detector import (
    BiasFinding,
    attraction_exceeds_trust,
    exposure_outpaces_evidence,
    high_emotion_major_decision,
    repeated_rationalization,
    unresolved_inconsistencies,
)
from .evidence import EvidenceSupport
from .exposure import Exposure
from .observation import Observation
from .patterns import detect_love_bombing
from .state import RelationshipState


@dataclass
class ReviewContext:
    state: RelationshipState
    exposure: Exposure
    observations: list[Observation]
    inconsistency_count: int
    hard_boundary_hit: bool
    evidence_support: EvidenceSupport


def run_hooks(ctx: ReviewContext) -> list[BiasFinding]:
    findings: list[BiasFinding] = []

    f = attraction_exceeds_trust(ctx.state, ctx.observations)
    if f:
        findings.append(f)

    f = repeated_rationalization(ctx.observations)
    if f:
        findings.append(f)

    findings.append(exposure_outpaces_evidence(ctx.exposure, ctx.evidence_support))

    f = high_emotion_major_decision(ctx.state, ctx.exposure)
    if f:
        findings.append(f)

    f = unresolved_inconsistencies(ctx.inconsistency_count)
    if f:
        findings.append(f)

    f = detect_love_bombing(ctx.observations)
    if f:
        findings.append(f)

    return findings
