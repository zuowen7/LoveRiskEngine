"""Per-kind relationship profiles (relationship-kinds proposal, S1).

A profile is *context*, not computation:

  - S1 (this file): `kind`, `power_asymmetry`, `exit_cost`, `voice` are
    consumed by the `lre status` context line. The remaining fields are
    editorial data staged for later slices and documented as such.
  - S2: `enabled_hooks` (kind-aware hook selection) and `promise_window_days`
    (display windowing, never deletion) become live.
  - S3: `boundary_seeds` (suggested boundaries at relationship creation) and
    threshold offsets driven by `exit_cost` become live.

Ordinals, never numbers: the external pitch proposed 0.9/0.6/0.2 power indices
and a +infinity exit cost. That is pseudo-precision (DESIGN.md Don't #1) and is
rejected — three bands are all the engine needs and all it claims. Every band
is an uncalibrated editorial default, in the same voice as the
`THRESHOLDS ARE PLACEHOLDERS` header in core/bias_detector.py.

No inescapability language: `exit_cost` HIGH brings warnings *forward* (the
user who cannot easily leave needs to know sooner). It must never phrase
anything as "you cannot leave".

No reply coaching: `power_asymmetry` is shown to the user as context; it is
never used to compute a suggested reply. No reply generation exists in this
product, period.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .relationship import Kind


class Ordinal(StrEnum):
    """Three bands. HIGH / MED / LOW — never a number."""

    HIGH = "HIGH"
    MED = "MED"
    LOW = "LOW"


# Today's v0.1 detectors, by rule_id (see core/hooks.py). Every kind runs all
# six plus the universal rapid-exposure detector; S2 made the per-kind
# selection live via `profile.enabled_hooks`, and windowed kinds additionally
# run `promise_expiry`.
_HOOKS_V1 = (
    "attraction_exceeds_trust",
    "repeated_rationalization",
    "exposure_outpaces_evidence",
    "high_emotion_major_decision",
    "unresolved_inconsistencies",
    "love_bombing_pattern",
)
_HOOKS_COMMON = _HOOKS_V1 + ("rapid_exposure_escalation",)


@dataclass(frozen=True)
class RelationshipProfile:
    kind: Kind
    enabled_hooks: tuple[str, ...]
    promise_window_days: int | None
    power_asymmetry: Ordinal
    exit_cost: Ordinal
    boundary_seeds: tuple[str, ...]
    voice: str


# Editorial defaults reviewed with the user (PROPOSAL_relationship_kinds.md §5).
# Pinned by tests/test_profiles.py so an accidental re-tune fails loudly.
PROFILES: dict[Kind, RelationshipProfile] = {
    Kind.LOVER: RelationshipProfile(
        kind=Kind.LOVER,
        enabled_hooks=_HOOKS_COMMON,
        promise_window_days=None,
        power_asymmetry=Ordinal.LOW,
        exit_cost=Ordinal.MED,
        boundary_seeds=(),
        voice="",
    ),
    Kind.FRIEND: RelationshipProfile(
        kind=Kind.FRIEND,
        enabled_hooks=_HOOKS_COMMON,
        promise_window_days=None,
        power_asymmetry=Ordinal.LOW,
        exit_cost=Ordinal.LOW,
        boundary_seeds=(),
        voice="",
    ),
    Kind.PARENT: RelationshipProfile(
        kind=Kind.PARENT,
        enabled_hooks=_HOOKS_COMMON,
        promise_window_days=None,
        power_asymmetry=Ordinal.MED,
        exit_cost=Ordinal.HIGH,
        boundary_seeds=(
            "respects my decisions about my own life",
            "does not pressure me into major decisions",
        ),
        voice="maintain explicit boundaries",
    ),
    Kind.BOSS: RelationshipProfile(
        kind=Kind.BOSS,
        enabled_hooks=_HOOKS_COMMON + ("promise_expiry",),
        promise_window_days=90,
        power_asymmetry=Ordinal.HIGH,
        exit_cost=Ordinal.HIGH,
        boundary_seeds=(
            "delivers on explicit promises",
            "no retaliation for pushing back",
        ),
        voice="verify promises before escalating",
    ),
    Kind.MENTOR: RelationshipProfile(
        kind=Kind.MENTOR,
        enabled_hooks=_HOOKS_COMMON + ("promise_expiry",),
        promise_window_days=90,
        power_asymmetry=Ordinal.HIGH,
        exit_cost=Ordinal.HIGH,
        boundary_seeds=(
            "delivers on explicit promises",
            "feedback is about work, not identity",
        ),
        voice="track promises; verify before escalating",
    ),
    Kind.COLLEAGUE: RelationshipProfile(
        kind=Kind.COLLEAGUE,
        enabled_hooks=_HOOKS_COMMON + ("promise_expiry",),
        promise_window_days=90,
        power_asymmetry=Ordinal.MED,
        exit_cost=Ordinal.MED,
        boundary_seeds=("separates work claims from evidence",),
        voice="separate work claims from evidence",
    ),
    Kind.STRANGER: RelationshipProfile(
        kind=Kind.STRANGER,
        enabled_hooks=_HOOKS_COMMON,
        promise_window_days=None,
        power_asymmetry=Ordinal.LOW,
        exit_cost=Ordinal.LOW,
        boundary_seeds=(),
        voice="low familiarity: prefer verification",
    ),
}


def get_profile(kind: str) -> RelationshipProfile:
    """Resolve a stored kind string to its profile.

    Fails open: an unknown kind (e.g. a hand-edited database row) falls back to
    the LOVER profile — the default equals today's behavior — so a corrupt row
    can never crash `status`. The raw value stays visible in `status`, so the
    mismatch is not silently hidden.
    """
    try:
        return PROFILES[Kind(kind)]
    except (ValueError, KeyError):
        return PROFILES[Kind.LOVER]
