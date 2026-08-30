"""Cheap-talk / costly-signal classification (roadmap feature, v0.2).

Grounded in signaling theory: assertions that cost the sender nothing and are
easy to fake (cheap talk) carry less evidentiary weight than actions or claims
that impose a real cost and are hard to fake (costly signals).

Design constraints (honest, no pseudoscience):
  - Classification is *user-decided* at observe time via `--signal-type`.
  - `suggest_signal_type()` is a crude keyword heuristic that returns a *hint*
    only; it never auto-sets and prints its uncertainty. It exists to nudge the
    user toward thinking in this frame, not to judge for them.
  - The weight a signal carries in the evidence-support model is a transparent
    placeholder coefficient (see core/evidence.py), not a calibrated likelihood.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional


class SignalType(str, Enum):
    CHEAP = "CHEAP"            # easy to say, hard to verify, low cost to fake
    COSTLY = "COSTLY"          # imposes cost / hard to fake / verifiable action
    UNSPECIFIED = "UNSPECIFIED"

    @property
    def evidence_weight(self) -> float:
        """Placeholder weight used by the evidence-support model.

        Costly signals weigh MORE than cheap talk because they are harder to
        fake. UNSPECIFIED stays neutral so we never punish users for not
        classifying. Coefficients are uncalibrated placeholders.
        """
        if self is SignalType.COSTLY:
            return 2.0
        if self is SignalType.CHEAP:
            return 0.5
        return 1.0


# Crude keyword lexicons. Intentionally short and obvious; the goal is to
# prompt the user to think, not to be a NLP classifier.
_CHEAP_MARKERS = (
    "i promise", "i swear", "trust me", "i'd never", "i would never",
    "i love you", "believe me", "i'd never lie", "cross my heart",
)
_COSTLY_MARKERS = (
    "introduced me to", "met my", "introduced me", "paid", "paid back",
    "showed up", "showed up on time", "signed", "moved in", "gave me the keys",
    "put my name on", "added me to", "came with me to", "drove me to the",
    "stayed with me at the", "co-signed",
)


def suggest_signal_type(text: str) -> Optional[SignalType]:
    """Return a *hint* for the user, or None if no clear marker.

    If both cheap and costly markers appear, returns None (ambiguous) so the
    user must decide. This is a keyword heuristic, not a judgment.
    """
    lower = text.lower()
    cheap_hit = any(m in lower for m in _CHEAP_MARKERS)
    costly_hit = any(m in lower for m in _COSTLY_MARKERS)
    if cheap_hit and costly_hit:
        return None  # ambiguous -> user decides
    if costly_hit:
        return SignalType.COSTLY
    if cheap_hit:
        return SignalType.CHEAP
    return None
