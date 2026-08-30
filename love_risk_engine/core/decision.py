"""Decision engine.

Design principle #4 (Default action is CONTINUE_OBSERVING):
  The engine never defaults to TRUST or REJECT. The five available outputs are
  ordered by severity; the most severe triggered finding wins.

  EXIT is reserved for recorded hard-boundary hits with evidence - the engine
  will not invent an EXIT on its own.
"""
from __future__ import annotations

from enum import Enum
from typing import List

from .bias_detector import BiasFinding


class Decision(str, Enum):
    CONTINUE_OBSERVING = "CONTINUE_OBSERVING"
    WAIT = "WAIT"
    PAUSE = "PAUSE"
    DECREASE_EXPOSURE = "DECREASE_EXPOSURE"
    EXIT = "EXIT"


# Most-severe first. Used to pick the single recommendation.
_PRIORITY: List[Decision] = [
    Decision.EXIT,
    Decision.PAUSE,
    Decision.DECREASE_EXPOSURE,
    Decision.WAIT,
    Decision.CONTINUE_OBSERVING,
]


def decide(
    findings: List[BiasFinding], has_hard_boundary_hit: bool
) -> Decision:
    if has_hard_boundary_hit:
        return Decision.EXIT

    proposed = [
        Decision(f.proposed_decision)
        for f in findings
        if f.proposed_decision
    ]
    for decision in _PRIORITY:
        if decision in proposed:
            return decision
    return Decision.CONTINUE_OBSERVING
