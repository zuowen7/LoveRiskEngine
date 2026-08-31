"""Evidence support quantification (v0.2, quality-calibrated).

Replaces the v0.1 raw-observation-count proxy with a transparent, quality-weighted
"evidence support" measure. Each observation contributes a base unit scaled by:

  - confidence_weight : 0.5 + (confidence / 10.0)
                       confidence=0 -> 0.5, confidence=5 -> 1.0 (neutral),
                       confidence=10 -> 1.5
  - signal_weight     : SignalType.evidence_weight
                       COSTLY=2.0 (hard to fake), CHEAP=0.5 (easy to fake),
                       UNSPECIFIED=1.0 (neutral)

Plus structural bonuses that reward good evidence hygiene:
  - triangulation : 0.5 per distinct source beyond the first
  - rigor         : 1.0 per observation that also records an alternative
                    explanation (intellectual honesty)
  - concreteness  : 1.0 per observation carrying >=1 structured claim
                    (falsifiable, comparable)

This is NOT a probability and NOT a Bayesian posterior. Coefficients are still
uncalibrated placeholders — but they now respond to *quality dimensions* the
user controls (confidence, signal type, rigor, claims) instead of treating
every observation as interchangeable. The composite is fully auditable:
`status` prints every component so you can see exactly why exposure is or
isn't supported.
"""

from __future__ import annotations

from dataclasses import dataclass

from .observation import Observation
from .signals import SignalType

# uncalibrated placeholder coefficients (NOT a calibrated model)
BASE_PER_OBSERVATION = 2.0
TRIANGULATION_PER_SOURCE = 0.5
RIGOR_PER_ALTERNATIVE = 1.0
CONCRETENESS_PER_CLAIM = 1.0


@dataclass
class EvidenceSupport:
    observation_count: int
    distinct_sources: int
    with_alternative: int  # observations that recorded an alternative explanation
    with_claims: int  # observations carrying >=1 structured claim
    costly_count: int  # observations classified as COSTLY signal
    cheap_count: int  # observations classified as CHEAP signal
    support_units: float  # transparent composite, NOT a probability

    @property
    def rigor_ratio(self) -> float:
        if self.observation_count == 0:
            return 0.0
        return self.with_alternative / self.observation_count

    @property
    def concreteness_ratio(self) -> float:
        if self.observation_count == 0:
            return 0.0
        return self.with_claims / self.observation_count


def _confidence_weight(confidence: float) -> float:
    """0.5 at confidence=0, 1.0 at confidence=5, 1.5 at confidence=10."""
    return 0.5 + (max(0.0, min(10.0, float(confidence))) / 10.0)


def compute_evidence_support(observations: list[Observation]) -> EvidenceSupport:
    n = len(observations)
    distinct_sources = len({o.source for o in observations})
    with_alt = sum(1 for o in observations if o.alternative_explanation.strip())
    with_claims = sum(1 for o in observations if o.claims)
    costly_count = sum(1 for o in observations if o.signal_type is SignalType.COSTLY)
    cheap_count = sum(1 for o in observations if o.signal_type is SignalType.CHEAP)

    # Per-observation contribution: base * confidence_weight * signal_weight.
    base = sum(
        BASE_PER_OBSERVATION
        * _confidence_weight(o.confidence)
        * o.signal_type.evidence_weight
        for o in observations
    )
    triangulation = TRIANGULATION_PER_SOURCE * max(0, distinct_sources - 1)
    rigor = RIGOR_PER_ALTERNATIVE * with_alt
    concreteness = CONCRETENESS_PER_CLAIM * with_claims
    support = base + triangulation + rigor + concreteness

    return EvidenceSupport(
        observation_count=n,
        distinct_sources=distinct_sources,
        with_alternative=with_alt,
        with_claims=with_claims,
        costly_count=costly_count,
        cheap_count=cheap_count,
        support_units=support,
    )
