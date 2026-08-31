from love_risk_engine.core.boundaries import BoundaryHit
from love_risk_engine.core.inconsistency import Inconsistency
from love_risk_engine.core.observation import Observation
from love_risk_engine.core.review import Review
from love_risk_engine.core.signals import SignalType
from love_risk_engine.core.timeline import build_timeline, format_timeline


def _obs(idx, signal=SignalType.UNSPECIFIED, claims=None, rationalization=False):
    return Observation(
        id=f"O{idx:03d}",
        relationship_id="R001",
        timestamp=f"2026-01-{idx:02d}T10:00:00",
        category="signal",
        observation=f"obs {idx}",
        interpretation="i",
        alternative_explanation="alt",
        source="self",
        confidence=5.0,
        signal_type=signal,
        claims=claims or [],
        rationalization=rationalization,
    )


def _hit(idx=1, day=2):
    return BoundaryHit(
        id=f"H{idx:03d}",
        boundary_id="B001",
        relationship_id="R001",
        evidence="crossed a line",
        timestamp=f"2026-01-{day:02d}T00:00:00",
    )


def _inc(day=3, resolved=False, resolution=None, note=""):
    return Inconsistency(
        id="I001",
        relationship_id="R001",
        description="story mismatch",
        resolved=resolved,
        created_at=f"2026-01-{day:02d}T00:00:00",
        kind="detected",
        resolution=resolution,
        resolution_note=note,
    )


def _rev(day=4):
    return Review(
        id="RV001",
        relationship_id="R001",
        timestamp=f"2026-01-{day:02d}T00:00:00",
        triggered_hooks=[],
        unresolved_inconsistencies=0,
        recommendation="PAUSE",
        notes="high emotion",
    )


def test_empty_timeline():
    events = build_timeline([], [], [], [])
    assert events == []
    assert format_timeline(events) == "(no timestamped events yet)"


def test_observations_appear_with_signal_tag():
    obs = [_obs(1, SignalType.COSTLY), _obs(2, SignalType.CHEAP)]
    events = build_timeline(obs, [], [], [])
    assert len(events) == 2
    assert "[COSTLY]" in events[0].label
    assert "[CHEAP]" in events[1].label


def test_events_sorted_chronologically():
    obs = [_obs(5), _obs(1), _obs(3)]
    events = build_timeline(obs, [], [], [])
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps)


def test_mixed_event_types_merge():
    events = build_timeline([_obs(1)], [_hit()], [_inc()], [_rev()])
    kinds = [e.kind for e in events]
    assert kinds == ["observation", "boundary_hit", "inconsistency", "review"]


def test_boundary_hits_arrive_as_domain_objects():
    """Regression: storage returns `BoundaryHit`, not a `sqlite3.Row`.

    `build_timeline` used to index boundary hits as rows (`h["timestamp"]`),
    which raised AttributeError once `list_boundary_hits` started returning
    domain objects. Every fixture in this module now uses the real types, so a
    shape mismatch fails here rather than in `lre timeline`.
    """
    events = build_timeline([], [_hit()], [], [])
    assert len(events) == 1
    assert events[0].kind == "boundary_hit"
    assert events[0].timestamp == "2026-01-02T00:00:00"
    assert "B001" in events[0].label
    assert "crossed a line" in events[0].label


def test_timeline_reads_exactly_what_storage_returns(tmp_path):
    """End-to-end guard: feed `build_timeline` a real Database result.

    Unit fakes drift. This asserts against the objects the storage layer
    actually hands over, so a future row-mapping migration fails here instead
    of in `lre timeline`.
    """
    from love_risk_engine.storage.database import Database

    db = Database(str(tmp_path / "timeline.db"))
    try:
        db.init()
        rid = db.add_relationship("Alex")
        bid = db.add_boundary("no lying", "HARD")
        db.add_boundary_hit(bid, rid, "denied a message")
        db.add_inconsistency(rid, "story mismatch")
        events = build_timeline(
            db.get_observations(rid),
            db.list_boundary_hits(rid),
            db.list_all_inconsistencies(rid),
            db.list_reviews(rid),
        )
    finally:
        db.close()
    assert [e.kind for e in events] == ["boundary_hit", "inconsistency"]
    assert "B001" in events[0].label
    assert "story mismatch" in events[1].label


def test_format_timeline_groups_by_day():
    obs = [_obs(1), _obs(2)]
    events = build_timeline(obs, [], [], [])
    out = format_timeline(events)
    assert "--- 2026-01-01 ---" in out
    assert "--- 2026-01-02 ---" in out


def test_resolved_inconsistency_shows_resolution():
    incs = [
        _inc(day=1, resolved=True, resolution="genuine_inconsistency", note="red flag")
    ]
    events = build_timeline([], [], incs, [])
    assert "genuine_inconsistency" in events[0].detail
    assert "red flag" in events[0].detail
