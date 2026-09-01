"""Timeline view (roadmap feature, v0.2).

Merges the timestamped events we actually have — observations, boundary hits,
inconsistencies, reviews, and (since schema v3) state/exposure changes — into
a single chronological stream so the user can see the relationship's history
at a glance.

Honesty note: state/exposure history is recorded from the first change after
schema v3 onward — the pre-v3 past was upserted (last-write-wins) and left no
trace, so the timeline cannot reconstruct it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .history import (
    ExposureChange,
    StateChange,
    describe_exposure_change,
    describe_state_change,
)
from .i18n import t
from .observation import Observation
from .signals import SignalType

if TYPE_CHECKING:
    from .boundaries import BoundaryHit
    from .inconsistency import Inconsistency
    from .review import Review


@dataclass
class TimelineEvent:
    timestamp: str
    kind: str  # observation | boundary_hit | inconsistency | review | state | exposure
    label: str  # one-line human-readable summary
    detail: str = ""  # optional second line (claims, resolution, etc.)


def build_timeline(
    observations: list[Observation],
    boundary_hits: list[BoundaryHit],
    inconsistencies: list[Inconsistency],
    reviews: list[Review],
    state_changes: list[StateChange] | None = None,
    exposure_changes: list[ExposureChange] | None = None,
) -> list[TimelineEvent]:
    """Merge all timestamped events into one chronologically-sorted stream."""
    events: list[TimelineEvent] = []
    state_changes = state_changes or []
    exposure_changes = exposure_changes or []

    for o in observations:
        sig = ""
        if o.signal_type is SignalType.COSTLY:
            sig = " [COSTLY]"
        elif o.signal_type is SignalType.CHEAP:
            sig = " [CHEAP]"
        flags = []
        if o.rationalization:
            flags.append("rationalization")
        if o.inconsistency_flag:
            flags.append("inconsistency_flag")
        flag_str = f" ({', '.join(flags)})" if flags else ""
        claims_str = ""
        if o.claims:
            claims_str = " | claims: " + ", ".join(
                f"{c.attribute}={c.value}" for c in o.claims
            )
        events.append(
            TimelineEvent(
                timestamp=o.timestamp,
                kind="observation",
                label=f"{o.id} {o.category}{sig}{flag_str}: {o.observation}",
                detail=(
                    f"interp: {o.interpretation}"
                    + (
                        f" | alt: {o.alternative_explanation}"
                        if o.alternative_explanation
                        else ""
                    )
                    + claims_str
                ).strip(" |"),
            )
        )

    for h in boundary_hits:
        events.append(
            TimelineEvent(
                timestamp=h.timestamp,
                kind="boundary_hit",
                label=f"{h.id} BOUNDARY HIT ({h.boundary_id}): {h.evidence}",
            )
        )

    for i in inconsistencies:
        detail = f"[{i.kind}] {'resolved' if i.resolved else 'open'}"
        if i.resolution:
            detail += f" -> {i.resolution}"
        if i.resolution_note:
            detail += f" | {i.resolution_note}"
        events.append(
            TimelineEvent(
                timestamp=i.created_at,
                kind="inconsistency",
                label=f"{i.id} INCONSISTENCY: {i.description}",
                detail=detail,
            )
        )

    for r in reviews:
        events.append(
            TimelineEvent(
                timestamp=r.timestamp,
                kind="review",
                label=f"{r.id} REVIEW -> {r.recommendation}",
                detail=r.notes,
            )
        )

    prev_state: StateChange | None = None
    for sc in sorted(state_changes, key=lambda e: (e.timestamp, e.id)):
        events.append(
            TimelineEvent(
                timestamp=sc.timestamp,
                kind="state",
                label=f"{sc.id} STATE {describe_state_change(prev_state, sc)}",
            )
        )
        prev_state = sc

    prev_exposure: ExposureChange | None = None
    for ec in sorted(exposure_changes, key=lambda e: (e.timestamp, e.id)):
        events.append(
            TimelineEvent(
                timestamp=ec.timestamp,
                kind="exposure",
                label=f"{ec.id} EXPOSURE {describe_exposure_change(prev_exposure, ec)}",
            )
        )
        prev_exposure = ec

    # Sort by timestamp; events without a timestamp go last but keep stable order
    events.sort(key=lambda e: (e.timestamp or "9999",))
    return events


def format_timeline(events: list[TimelineEvent]) -> str:
    if not events:
        return t("timeline_empty")
    lines: list[str] = []
    last_ts = ""
    for e in events:
        ts = e.timestamp or "?"
        day = ts[:10] if len(ts) >= 10 else ts
        if day != last_ts:
            lines.append(f"--- {day} ---")
            last_ts = day
        lines.append(f"  [{e.kind}] {e.label}")
        if e.detail:
            lines.append(f"        {e.detail}")
    return "\n".join(lines)
