"""Per-kind profile registry tests (relationship-kinds proposal, S1).

The registry is editorial data: the ordinal bands and promise windows were
reviewed with the user and are pinned here so an accidental re-tune fails
loudly. In S1 the bands are *context* only — they reach detector thresholds in
S3 — so these tests pin what the user sees, not a formula.
"""

from __future__ import annotations

import dataclasses

import pytest
from love_risk_engine.core.profiles import (
    PROFILES,
    Ordinal,
    RelationshipProfile,
    get_profile,
)
from love_risk_engine.core.relationship import Kind

# Today's v0.1 detectors, by rule_id (see core/hooks.py). LOVER must enable
# exactly this set so the new field changes nothing for existing users.
_HOOKS_V1 = (
    "attraction_exceeds_trust",
    "repeated_rationalization",
    "exposure_outpaces_evidence",
    "high_emotion_major_decision",
    "unresolved_inconsistencies",
    "love_bombing_pattern",
)


def test_every_kind_has_a_profile():
    assert set(PROFILES) == set(Kind)


def test_profiles_are_frozen():
    for profile in PROFILES.values():
        assert isinstance(profile, RelationshipProfile)
        with pytest.raises(dataclasses.FrozenInstanceError):
            profile.exit_cost = Ordinal.HIGH


def test_lover_profile_pins_todays_behavior():
    profile = PROFILES[Kind.LOVER]
    assert all(hook in profile.enabled_hooks for hook in _HOOKS_V1)
    assert "rapid_exposure_escalation" in profile.enabled_hooks
    assert profile.promise_window_days is None


def test_all_kinds_run_rapid_escalation():
    """Exposure outpacing evidence is dangerous in any kind of relationship."""
    for profile in PROFILES.values():
        assert "rapid_exposure_escalation" in profile.enabled_hooks


def test_windowed_kinds_enable_promise_expiry():
    for kind in (Kind.BOSS, Kind.MENTOR, Kind.COLLEAGUE):
        assert "promise_expiry" in PROFILES[kind].enabled_hooks
    for kind in (Kind.LOVER, Kind.FRIEND, Kind.PARENT, Kind.STRANGER):
        assert "promise_expiry" not in PROFILES[kind].enabled_hooks


def test_approved_ordinal_table():
    assert PROFILES[Kind.LOVER].power_asymmetry is Ordinal.LOW
    assert PROFILES[Kind.LOVER].exit_cost is Ordinal.MED
    assert PROFILES[Kind.FRIEND].power_asymmetry is Ordinal.LOW
    assert PROFILES[Kind.FRIEND].exit_cost is Ordinal.LOW
    assert PROFILES[Kind.PARENT].power_asymmetry is Ordinal.MED
    assert PROFILES[Kind.PARENT].exit_cost is Ordinal.HIGH
    assert PROFILES[Kind.BOSS].power_asymmetry is Ordinal.HIGH
    assert PROFILES[Kind.BOSS].exit_cost is Ordinal.HIGH
    assert PROFILES[Kind.MENTOR].power_asymmetry is Ordinal.HIGH
    assert PROFILES[Kind.MENTOR].exit_cost is Ordinal.HIGH
    assert PROFILES[Kind.COLLEAGUE].power_asymmetry is Ordinal.MED
    assert PROFILES[Kind.COLLEAGUE].exit_cost is Ordinal.MED
    assert PROFILES[Kind.STRANGER].power_asymmetry is Ordinal.LOW
    assert PROFILES[Kind.STRANGER].exit_cost is Ordinal.LOW


def test_promise_windows_follow_the_approved_table():
    assert PROFILES[Kind.BOSS].promise_window_days == 90
    assert PROFILES[Kind.MENTOR].promise_window_days == 90
    assert PROFILES[Kind.COLLEAGUE].promise_window_days == 90
    assert PROFILES[Kind.LOVER].promise_window_days is None
    assert PROFILES[Kind.PARENT].promise_window_days is None
    assert PROFILES[Kind.STRANGER].promise_window_days is None


def test_get_profile_resolves_stored_kind_strings():
    assert get_profile("MENTOR") is PROFILES[Kind.MENTOR]


def test_get_profile_fails_open_on_unknown_kind():
    """A hand-edited row must never crash `status`.

    The fallback is the LOVER profile — the default equals today's behavior —
    and `status` still prints the raw kind string, so the mismatch stays
    visible instead of being silently corrected.
    """
    assert get_profile("SOME_GARBAGE") is PROFILES[Kind.LOVER]
