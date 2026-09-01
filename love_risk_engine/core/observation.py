"""Observation and Inconsistency records.

Design principle #2 (Observation != Interpretation):
  Every Observation preserves the three-way split:
    observation               - what was objectively perceived
    interpretation            - how the user explains it
    alternative_explanation   - another plausible reading when interpretation
                                is supplied through the interactive CLI
  `confidence` and `source` make the evidence quality explicit.

Facts-only and imported/legacy records may leave both interpretation fields
empty. The consistency audit surfaces one-sided legacy/imported records rather
than rewriting canonical evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .signals import SignalType


class JudgmentDirection(StrEnum):
    """How an observation was applied to the user's trust judgment.

    This is an explicit user label, not an inference from free text.
    `UNSPECIFIED` preserves legacy observations; `NEUTRAL` is an intentional
    judgment that does not participate in opposite-direction comparisons.
    """

    UNSPECIFIED = "UNSPECIFIED"
    SUPPORTS_TRUST = "SUPPORTS_TRUST"
    WEAKENS_TRUST = "WEAKENS_TRUST"
    NEUTRAL = "NEUTRAL"


@dataclass
class Claim:
    """A single structured factual assertion extracted from an observation.

    Claims are the unit the contradiction tracker compares. Keeping them
    structured (attribute=value) makes conflict detection deterministic and
    explainable instead of relying on fuzzy text matching or AI judgment.
    """

    attribute: str
    value: str


@dataclass
class Observation:
    id: str
    relationship_id: str
    timestamp: str  # ISO-8601, lexicographically sortable
    category: str
    observation: str
    interpretation: str
    alternative_explanation: str
    source: str
    confidence: float  # 0..10
    rationalization: bool = False
    inconsistency_flag: bool = False
    claims: list[Claim] = field(default_factory=list)
    signal_type: SignalType = SignalType.UNSPECIFIED
    criterion_key: str = ""
    judgment_direction: JudgmentDirection = JudgmentDirection.UNSPECIFIED


@dataclass
class Inconsistency:
    id: str
    relationship_id: str
    description: str
    resolved: bool
    created_at: str
