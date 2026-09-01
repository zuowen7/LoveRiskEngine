"""State/exposure change history (roadmap item #1).

The history tables store *snapshots* — each row is the full set of values at
the time of a change. Deltas are derived at read time by comparing consecutive
rows of the same series; nothing here ever rewrites or deletes a row.

Baseline: the first write of each series is recorded as a baseline snapshot,
so history is complete from the first change onward. No-op writes (values
unchanged) are filtered by the storage layer and never appear.
"""

from __future__ import annotations

from dataclasses import dataclass

_EXPOSURE_AXES = ("time", "emotional", "privacy", "financial", "life_decision")
_STATE_FIELDS = ("attraction", "trust", "uncertainty")


@dataclass(frozen=True)
class StateChange:
    id: str
    relationship_id: str
    timestamp: str
    attraction: float
    trust: float
    uncertainty: float
    emotional_state: str


@dataclass(frozen=True)
class ExposureChange:
    id: str
    relationship_id: str
    timestamp: str
    time: float
    emotional: float
    privacy: float
    financial: float
    life_decision: float

    @property
    def total(self) -> float:
        return (
            self.time
            + self.emotional
            + self.privacy
            + self.financial
            + self.life_decision
        )


def describe_state_change(prev: StateChange | None, curr: StateChange) -> str:
    """One-line description; a baseline (prev None) lists the full snapshot."""
    if prev is None:
        return (
            "baseline: "
            f"attraction {curr.attraction:.1f}, trust {curr.trust:.1f}, "
            f"uncertainty {curr.uncertainty:.1f}, emotional {curr.emotional_state}"
        )
    parts = [
        f"{field} {getattr(prev, field):.1f} -> {getattr(curr, field):.1f}"
        for field in _STATE_FIELDS
        if getattr(prev, field) != getattr(curr, field)
    ]
    if prev.emotional_state != curr.emotional_state:
        parts.append(f"emotional {prev.emotional_state} -> {curr.emotional_state}")
    return ", ".join(parts)


def describe_exposure_change(prev: ExposureChange | None, curr: ExposureChange) -> str:
    """One-line description; a baseline (prev None) lists the full snapshot."""
    if prev is None:
        axes = ", ".join(f"{a} {getattr(curr, a):.1f}" for a in _EXPOSURE_AXES)
        return f"baseline: total {curr.total:.1f} ({axes})"
    changed = [
        f"{a} {getattr(prev, a):.1f} -> {getattr(curr, a):.1f}"
        for a in _EXPOSURE_AXES
        if getattr(prev, a) != getattr(curr, a)
    ]
    if not changed:
        return ""  # defensive: storage never records an unchanged write
    line = f"total {prev.total:.1f} -> {curr.total:.1f}"
    line += " (" + ", ".join(changed) + ")"
    return line
