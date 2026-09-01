"""Pattern detectors (roadmap feature, v0.2).

Higher-order patterns built on top of the structured observations / signal
classifications. Unlike the per-rule bias detectors in bias_detector.py, these
look for *clusters* of signals across a time window.

Design constraints (honest, no pseudoscience):
  - Detection is a transparent count over the early-relationship window. No
    model, no probability, no "love-bombing score 73.2%".
  - It only *surfaces* a pattern for the user to consider; it does not label
    the other person a manipulator. The user always decides.
  - Thresholds are explicitly documented as uncalibrated placeholders.
"""

from __future__ import annotations

from .bias_detector import BiasFinding
from .observation import Observation
from .signals import SignalType

# --- tunable (uncalibrated) thresholds ---
# Love bombing classic signature: a burst of cheap affection talk ("I love
# you", "you're the one", promises) paired with intense costly gestures
# (meeting family very early, big gifts, moving fast) compressed into the
# opening phase of the relationship. The *pairing* matters — cheap talk alone
# is just enthusiasm; cheap talk + costly gestures early is the manipulation
# precursor.
EARLY_WINDOW_OBSERVATIONS = 10  # the "early phase" is the first N observations
MIN_CHEAP_FOR_LOVE_BOMBING = 3  # >= this many CHEAP signals in the window
MIN_COSTLY_FOR_LOVE_BOMBING = (
    1  # >= this many COSTLY signals paired with the cheap talk
)
MIN_TOTAL_SIGNALS = 5  # cheap + costly combined in the window


def detect_love_bombing(
    observations: list[Observation],
) -> BiasFinding | None:
    """Flag a possible love-bombing pattern in the early relationship window.

    Looks at the first `EARLY_WINDOW_OBSERVATIONS` observations (by timestamp).
    Fires when the window contains >= MIN_CHEAP_FOR_LOVE_BOMBING cheap-talk
    signals AND >= MIN_COSTLY_FOR_LOVE_BOMBING costly signals AND >=
    MIN_TOTAL_SIGNALS total (cheap + costly) signals. The pairing matters:
    cheap talk alone is just enthusiasm; cheap talk + costly gestures
    compressed early is the classic manipulation precursor.

    Thresholds are uncalibrated placeholders. This rule proposes PAUSE because
    love bombing impairs judgement — the user should pause before raising
    exposure, not because the other person has been convicted of anything.
    """
    if not observations:
        return None
    early = sorted(observations, key=lambda o: o.timestamp)[:EARLY_WINDOW_OBSERVATIONS]
    cheap = sum(1 for o in early if o.signal_type is SignalType.CHEAP)
    costly = sum(1 for o in early if o.signal_type is SignalType.COSTLY)
    total_signals = cheap + costly
    if (
        cheap >= MIN_CHEAP_FOR_LOVE_BOMBING
        and costly >= MIN_COSTLY_FOR_LOVE_BOMBING
        and total_signals >= MIN_TOTAL_SIGNALS
    ):
        return BiasFinding(
            "love_bombing_pattern",
            f"Possible love-bombing pattern in early window "
            f"({len(early)} observations): {cheap} cheap-talk + {costly} costly "
            f"signals compressed early. Pause before raising exposure; do not "
            f"convict on a pattern alone.",
            severity=3,
            proposed_decision="PAUSE",
            msg_key="love_bombing_pattern",
            msg_params={
                "n": str(len(early)),
                "cheap": str(cheap),
                "costly": str(costly),
            },
        )
    return None
