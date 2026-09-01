"""Calibration / evaluation (architecture §4, measurement phase v1).

Honest measurement, never faked: the engine's thresholds stay uncalibrated
placeholders. This module collects the USER's own retrospective labels on past
reviews (`lre evaluate`) and reports per-rule fire counts against them
(`lre calibration`) — counts, not probabilities-as-truth; your own labeled
history, not population statistics.

Guardrail (invariant #5): labels NEVER feed the engine automatically. No
threshold changes, no re-ranking. Personal threshold overrides are a deferred
slice that only becomes admissible once this data exists.
"""

from __future__ import annotations

from dataclasses import dataclass

from .review import Review

VALID_OUTCOMES = ("good", "bad", "neutral")


@dataclass(frozen=True)
class ReviewOutcome:
    review_id: str
    outcome: str
    note: str
    labeled_at: str


@dataclass(frozen=True)
class RuleStat:
    rule_id: str
    fired: int  # reviews where the rule was among the triggered hooks
    labeled: int  # of those, how many carry an outcome label
    bad: int  # of the labeled, how many were judged bad


@dataclass(frozen=True)
class CalibrationReport:
    rules: list[RuleStat]
    reviews_labeled: int
    total_reviews: int


def compute_calibration(
    reviews: list[Review], outcomes: list[ReviewOutcome]
) -> CalibrationReport:
    """Per-rule fire/label/bad counts over the given reviews and labels."""
    outcome_by_review = {o.review_id: o for o in outcomes}
    counts: dict[str, dict[str, int]] = {}
    for review in reviews:
        label = outcome_by_review.get(review.id)
        for hook in review.triggered_hooks:
            c = counts.setdefault(hook, {"fired": 0, "labeled": 0, "bad": 0})
            c["fired"] += 1
            if label is not None:
                c["labeled"] += 1
                if label.outcome == "bad":
                    c["bad"] += 1
    rules = [
        RuleStat(rule_id, c["fired"], c["labeled"], c["bad"])
        for rule_id, c in counts.items()
    ]
    rules.sort(key=lambda s: (-s.fired, s.rule_id))
    return CalibrationReport(
        rules=rules,
        reviews_labeled=len(outcomes),
        total_reviews=len(reviews),
    )
