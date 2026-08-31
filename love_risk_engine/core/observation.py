"""Observation and Inconsistency records.

Design principle #2 (Observation != Interpretation):
  Every Observation forces the three-way split:
    observation               - what was objectively perceived
    interpretation            - how the user explains it
    alternative_explanation   - at least one other plausible reading
  `confidence` and `source` make the evidence quality explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .signals import SignalType


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


@dataclass
class Inconsistency:
    id: str
    relationship_id: str
    description: str
    resolved: bool
    created_at: str
