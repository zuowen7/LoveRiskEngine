"""Relationship state: attraction, trust, uncertainty, emotional state.

Design principle #1 (Attraction != Trust):
  attraction and trust are stored and mutated independently. Nothing in this
  module ever derives trust from attraction (or vice versa).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

MAX_SCORE = 10.0


class EmotionalState(str, Enum):
    """Self-reported emotional state of the user at assessment time.

    `is_high` flags states that impair judgement during major decisions.
    This is the user's own state, never an inference about the other person.
    """

    CALM = "CALM"
    NEUTRAL = "NEUTRAL"
    TENSE = "TENSE"
    EXCITED = "EXCITED"
    ANXIOUS = "ANXIOUS"
    OVERWHELMED = "OVERWHELMED"

    @property
    def is_high(self) -> bool:
        return self in (
            EmotionalState.EXCITED,
            EmotionalState.ANXIOUS,
            EmotionalState.OVERWHELMED,
        )


@dataclass
class RelationshipState:
    relationship_id: str
    attraction: float = 0.0
    trust: float = 0.0
    uncertainty: float = 0.0
    emotional_state: EmotionalState = EmotionalState.NEUTRAL

    def clamp(self) -> None:
        """Keep scores inside the 0..10 range. Mutates in place."""
        for field_name in ("attraction", "trust", "uncertainty"):
            value = float(getattr(self, field_name))
            setattr(self, field_name, max(0.0, min(MAX_SCORE, value)))
