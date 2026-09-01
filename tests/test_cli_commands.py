"""Command-level tests for the `lre` CLI.

These drive `main(argv)` in-process against a throwaway database in `tmp_path`
and assert on captured stdout.

Why in-process rather than subprocess: a subprocess per command would fork an
interpreter and lose branch attribution, which defeats the purpose of this
file. Calling `main()` directly also means a failure shows the real traceback
instead of an opaque exit code.

Coverage focus, in priority order:
  1. The cooldown gate (`exposure set` during a cooldown) and its audited
     override. This is the only place the CLI can refuse a user action, so a
     regression here is a safety regression, not a cosmetic one.
  2. Commands that had no coverage at all: boundary hit, inconsistency
     list/resolve, contradictions, chat import, timeline, cooldown.
  3. `format_status` branches that the happy path never reaches, because
     `run_hooks` always returns at least one finding and therefore the
     "no warnings" and "no hooks fired" branches are unreachable through
     `main()`. Those are exercised as direct unit tests instead.
"""

from __future__ import annotations

import json
import re

import pytest
from love_risk_engine.cli import format_status, main
from love_risk_engine.core.contradiction import ContradictionCandidate
from love_risk_engine.core.decision import Decision
from love_risk_engine.core.evidence import EvidenceSupport
from love_risk_engine.core.exposure import Exposure
from love_risk_engine.core.state import EmotionalState, RelationshipState

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Point the CLI at a throwaway database for the duration of the test."""
    path = tmp_path / "lre.db"
    monkeypatch.setenv("LRE_DB_PATH", str(path))
    return str(path)


@pytest.fixture
def run(db_path, capsys):
    """Invoke the CLI and return its stdout. Fails loudly on a non-zero exit."""

    def _run(*argv: str) -> str:
        code = main(list(argv))
        out = capsys.readouterr().out
        assert code == 0, f"`lre {' '.join(argv)}` exited {code}"
        return out

    return _run


@pytest.fixture
def seeded(run):
    """A database holding one relationship, ready for command tests."""
    run("init")
    run("relationship", "add", "Alex")
    return "Alex"


@pytest.fixture
def cooled_down(run, seeded):
    """A relationship with an *active* cooldown, and a known exposure baseline.

    Sequence matters: exposure is pinned to time=1/emotional=1 *before* the
    cooldown starts, so later assertions can tell "raising exposure" (blocked)
    apart from "lowering exposure" (always allowed).

    The cooldown comes from a recorded hard-boundary hit, which is the only way
    the engine reaches EXIT (it will not invent one on its own).
    """
    run("exposure", "set", "Alex", "--time", "1", "--emotional", "1")
    out = run(
        "boundary", "add", "--description", "never shouts at me", "--severity", "HARD"
    )
    bid = _first_id(out, "B")
    run(
        "boundary",
        "hit",
        bid,
        "--relationship",
        "Alex",
        "--evidence",
        "shouted at me in front of friends on 2026-08-01",
    )
    return run("review", "Alex")


def _first_id(out: str, prefix: str) -> str:
    """Pull the first `PREFIX###` token out of a command's stdout."""
    match = re.search(rf"\b{prefix}\d+\b", out)
    assert match is not None, f"no {prefix}#### id in output:\n{out}"
    return match.group(0)


# ---------------------------------------------------------------------------
# observe
# ---------------------------------------------------------------------------


def test_observe_rejects_claim_without_equals(run, seeded):
    with pytest.raises(SystemExit) as exc:
        run("observe", "Alex", "--observation", "x", "--claim", "relationship_status")
    assert "must be attribute=value" in str(exc.value)


def test_observe_rejects_claim_with_empty_attribute(run, seeded):
    with pytest.raises(SystemExit) as exc:
        run("observe", "Alex", "--observation", "x", "--claim", "=single")
    assert "attribute is empty" in str(exc.value)


def test_observe_records_structured_claims(run, seeded):
    out = run(
        "observe",
        "Alex",
        "--observation",
        "says he is single",
        "--claim",
        "relationship_status=single",
        "--claim",
        " city=Berlin ",
    )
    assert "with 2 claim(s)" in out


def test_observe_uses_explicit_signal_type(run, seeded):
    out = run(
        "observe",
        "Alex",
        "--observation",
        "showed up on time for the flight",
        "--signal-type",
        "COSTLY",
    )
    assert "[COSTLY]" in out


def test_observe_hints_when_text_matches_one_lexicon(run, seeded):
    out = run("observe", "Alex", "--observation", "she said i love you already")
    assert "(hint)" in out
    assert "CHEAP" in out


def test_observe_stays_silent_when_markers_are_ambiguous(run, seeded):
    """Both lexicons hit -> the heuristic abstains rather than guessing."""
    out = run(
        "observe",
        "Alex",
        "--observation",
        "i love you, and she met my parents",
    )
    assert "(hint)" not in out


# ---------------------------------------------------------------------------
# status / format_status
# ---------------------------------------------------------------------------


def _empty_support() -> EvidenceSupport:
    return EvidenceSupport(
        observation_count=0,
        distinct_sources=0,
        with_alternative=0,
        with_claims=0,
        costly_count=0,
        cheap_count=0,
        support_units=0.0,
    )


def test_format_status_reports_no_warnings():
    """Unreachable via `main()` — `run_hooks` always yields >=1 finding."""
    out = format_status(
        "R001",
        RelationshipState("R001"),
        Exposure("R001"),
        [],
        Decision.CONTINUE_OBSERVING,
        0,
        _empty_support(),
    )
    assert "- None." in out


def test_format_status_renders_contradictions_and_the_more_marker():
    candidates = [
        ContradictionCandidate(
            attribute="relationship_status",
            value_a="single",
            value_b="married",
            obs_a_id="O001",
            obs_b_id="O002",
            explanation="conflicting relationship_status",
        )
    ]
    out = format_status(
        "R001",
        RelationshipState("R001"),
        Exposure("R001"),
        [],
        Decision.CONTINUE_OBSERVING,
        0,
        _empty_support(),
        contradictions=candidates,
        more_conflicts=True,
    )
    assert "Conflicting claims (top):" in out
    assert "'single' vs 'married'" in out
    assert "to persist all" in out


def test_status_summarises_acknowledged_inconsistencies(run, seeded):
    run("inconsistency", "add", "Alex", "--description", "tuesday differs")
    run(
        "inconsistency",
        "resolve",
        "I001",
        "--as",
        "sequential_change",
        "--note",
        "timeline moved",
    )
    run("inconsistency", "add", "Alex", "--description", "second one")
    run("inconsistency", "resolve", "I002", "--as", "dismissed")
    out = run("status", "Alex")
    assert "Acknowledged (closed): 2 (1 dismissed, 1 sequential_change)" in out


def test_status_lists_top_contradictions(run, seeded):
    run(
        "observe",
        "Alex",
        "--observation",
        "says single",
        "--claim",
        "relationship_status=single",
    )
    run(
        "observe",
        "Alex",
        "--observation",
        "says married",
        "--claim",
        "relationship_status=married",
    )
    out = run("status", "Alex")
    assert "Conflicting claims (top):" in out
    # Detection order decides which value is "a" and which is "b"; assert on
    # the pair, not on an ordering the caller does not control.
    assert "[relationship_status]" in out
    assert "'single' vs 'married'" in out or "'married' vs 'single'" in out


# ---------------------------------------------------------------------------
# review
# ---------------------------------------------------------------------------


def test_review_reports_no_hooks_and_no_notes(monkeypatch, run, seeded):
    """Unreachable via `main()`: `run_hooks` always returns a finding.

    Patching `run_review` keeps the CLI's own formatting under test while
    forcing the empty-collection branches that production data cannot reach.
    """
    import love_risk_engine.cli as cli

    real_run_review = cli.run_review

    def no_hooks(db, relationship_id, ctx=None):
        review = real_run_review(db, relationship_id, ctx=ctx)
        review.triggered_hooks = []
        review.notes = ""
        return review

    monkeypatch.setattr(cli, "run_review", no_hooks)
    out = run("review", "Alex")
    assert "Triggered hooks:" in out
    assert "  - none" in out
    assert "Notes:" not in out


def test_review_announces_cooldown_after_hard_boundary_hit(run, seeded):
    out = run(
        "boundary", "add", "--description", "never shouts at me", "--severity", "HARD"
    )
    bid = _first_id(out, "B")
    run(
        "boundary",
        "hit",
        bid,
        "--relationship",
        "Alex",
        "--evidence",
        "shouted at me in public",
    )
    out = run("review", "Alex")
    assert "Recommendation: EXIT" in out
    assert "Cooldown C001 started" in out
    assert "are gated until it expires" in out


# ---------------------------------------------------------------------------
# boundary
# ---------------------------------------------------------------------------


def test_boundary_hit_records_evidence(run, seeded):
    out = run("boundary", "add", "--description", "no lying", "--severity", "HARD")
    bid = _first_id(out, "B")
    out = run(
        "boundary",
        "hit",
        bid,
        "--relationship",
        "Alex",
        "--evidence",
        "denied a message I have a screenshot of",
    )
    assert "Recorded boundary hit H001" in out
    assert f"boundary {bid}" in out


def test_boundary_hit_rejects_unknown_boundary(run, seeded):
    with pytest.raises(SystemExit) as exc:
        run(
            "boundary",
            "hit",
            "B999",
            "--relationship",
            "Alex",
            "--evidence",
            "anything",
        )
    assert "boundary not found" in str(exc.value)


def test_boundary_hit_rejects_unknown_relationship(run, seeded):
    out = run("boundary", "add", "--description", "no lying", "--severity", "HARD")
    bid = _first_id(out, "B")
    with pytest.raises(SystemExit) as exc:
        run("boundary", "hit", bid, "--relationship", "ghost", "--evidence", "x")
    assert "relationship not found" in str(exc.value)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_reports_an_empty_database(run):
    out = run("list")
    assert "Relationships:" in out
    assert "Boundaries:" in out
    assert out.count("(none)") == 2


def test_list_shows_relationships_and_boundaries(run, seeded):
    run("boundary", "add", "--description", "no lying", "--severity", "SOFT")
    out = run("list")
    assert "R001  Alex  [ACTIVE]" in out
    assert "[SOFT] no lying (ACTIVE)" in out


def test_boundary_retire_marks_inactive(run, seeded):
    """`boundary retire` is the CLI surface for `deactivate_boundary`.

    Before this command existed the only way to retire a boundary was to import
    `Database` and call the method by hand — which is exactly what this test
    used to do, meaning the storage capability was unreachable for real users.
    """
    out = run("boundary", "add", "--description", "retired rule", "--severity", "SOFT")
    bid = _first_id(out, "B")
    out = run("boundary", "retire", bid)
    assert f"Retired boundary {bid}" in out
    out = run("list")
    assert "[SOFT] retired rule (inactive)" in out


def test_boundary_retire_unknown_id_exits(db_path, run):
    run("init")
    with pytest.raises(SystemExit) as exc:
        main(["boundary", "retire", "B999"])
    assert "boundary not found" in str(exc.value)


def test_retired_boundary_keeps_its_hits(run, seeded):
    """Retiring must not erase history: past hits stay on the timeline."""
    out = run("boundary", "add", "--description", "no lying", "--severity", "HARD")
    bid = _first_id(out, "B")
    run("boundary", "hit", bid, "--relationship", seeded, "--evidence", "denied it")
    run("boundary", "retire", bid)
    out = run("timeline", seeded)
    assert "BOUNDARY HIT" in out
    assert bid in out


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("flag", "value", "expected"),
    [
        ("--attraction", "7.5", "Attraction       7.5 / 10"),
        ("--trust", "3", "Trust            3.0 / 10"),
        ("--uncertainty", "6", "Uncertainty      6.0 / 10"),
        (
            "--emotional",
            EmotionalState.ANXIOUS.name,
            f"Emotional        {EmotionalState.ANXIOUS.value}",
        ),
    ],
)
def test_state_set_updates_only_the_field_passed(run, seeded, flag, value, expected):
    run("state", "set", "Alex", flag, value)
    assert expected in run("status", "Alex")


def test_state_set_with_no_flags_is_a_no_op(run, seeded):
    out = run("state", "set", "Alex")
    assert "Updated state for R001" in out


# ---------------------------------------------------------------------------
# exposure — including the cooldown gate (safety-critical)
# ---------------------------------------------------------------------------


def test_exposure_set_updates_every_axis(run, seeded):
    out = run(
        "exposure",
        "set",
        "Alex",
        "--time",
        "2",
        "--emotional",
        "3",
        "--privacy",
        "1",
        "--financial",
        "0.5",
        "--life-decision",
        "1",
    )
    assert "total 0.0 -> 7.5" in out


def test_exposure_raise_is_blocked_during_cooldown(run, cooled_down):
    out = run("exposure", "set", "Alex", "--time", "5")
    assert "BLOCKED: an active cooldown prevents raising exposure." in out
    assert "C001 [EXIT]" in out
    assert "To override (logged for audit)" in out
    # The block must actually refuse the write, not just print a warning.
    assert "  Time           1.0" in run("status", "Alex")


def test_lowering_exposure_is_never_blocked(run, cooled_down):
    out = run("exposure", "set", "Alex", "--time", "0")
    assert "BLOCKED" not in out
    assert "Updated exposure" in out


def test_override_logs_reason_and_applies(run, cooled_down):
    out = run(
        "exposure",
        "set",
        "Alex",
        "--time",
        "5",
        "--override",
        "--reason",
        "we talked it through in person",
    )
    assert "OVERRIDE logged: raising exposure 2.0 -> 6.0" in out
    assert "Updated exposure" in out
    # ...and the audit trail is visible from the cooldown view.
    history = run("cooldown", "Alex")
    assert "Override history (1):" in history
    assert "we talked it through in person" in history


def test_override_without_a_reason_is_still_logged(run, cooled_down):
    run("exposure", "set", "Alex", "--time", "5", "--override")
    assert "(no reason)" in run("cooldown", "Alex")


def test_expired_cooldown_does_not_block(run, seeded, db_path):
    """A cooldown past its expiry must not gate, even while still flagged.

    `list_cooldowns(active_only=True)` filters on the `active` flag only;
    expiry is a separate check inside `is_active`. Without that second check a
    stale row would silently lock the user out of raising exposure forever.
    """
    from love_risk_engine.core.timeutil import expires_utc_iso
    from love_risk_engine.storage.database import Database

    db = Database(db_path)
    try:
        db.init()
        db.add_cooldown(
            relationship_id="R001",
            decision="PAUSE",
            reason="stale row from an old session",
            started_at=expires_utc_iso(-48),
            expires_at=expires_utc_iso(-24),
        )
    finally:
        db.close()

    out = run("exposure", "set", "Alex", "--time", "4")
    assert "BLOCKED" not in out
    assert "Updated exposure" in out
    # ...and it is not advertised as an active guardrail either.
    assert "  (none)" in run("cooldown", "Alex")


def test_cooldown_clear_lifts_the_gate(run, cooled_down):
    out = run("cooldown", "Alex", "clear")
    assert "Cleared 1 active cooldown(s) for R001." in out
    assert "BLOCKED" not in run("exposure", "set", "Alex", "--time", "5")


# ---------------------------------------------------------------------------
# inconsistency
# ---------------------------------------------------------------------------


def test_inconsistency_list_shows_open_items(run, seeded):
    run("inconsistency", "add", "Alex", "--description", "story differs")
    out = run("inconsistency", "list", "Alex")
    assert "Open inconsistencies for R001:" in out
    assert "I001 [manual] story differs" in out


def test_inconsistency_list_reports_empty_for_both_states(run, seeded):
    assert "(none)" in run("inconsistency", "list", "Alex")
    assert "(none)" in run("inconsistency", "list", "Alex", "--resolved")


def test_inconsistency_list_shows_resolution_and_note(run, seeded):
    run("inconsistency", "add", "Alex", "--description", "story differs")
    run(
        "inconsistency",
        "resolve",
        "I001",
        "--as",
        "genuine_inconsistency",
        "--note",
        "kept as a flag",
    )
    out = run("inconsistency", "list", "Alex", "--resolved")
    assert "Resolved inconsistencies for R001:" in out
    assert "-> genuine_inconsistency | kept as a flag" in out


def test_inconsistency_list_omits_an_empty_note(run, seeded):
    run("inconsistency", "add", "Alex", "--description", "story differs")
    run("inconsistency", "resolve", "I001", "--as", "dismissed")
    out = run("inconsistency", "list", "Alex", "--resolved")
    assert "-> dismissed" in out
    assert " | " not in out


def test_inconsistency_list_shows_detected_kind(run, seeded):
    run(
        "observe",
        "Alex",
        "--observation",
        "says single",
        "--claim",
        "relationship_status=single",
    )
    run(
        "observe",
        "Alex",
        "--observation",
        "says married",
        "--claim",
        "relationship_status=married",
    )
    run("contradictions", "Alex", "--save")
    assert "[detected]" in run("inconsistency", "list", "Alex")


def test_inconsistency_resolve_rejects_unknown_id(run, seeded):
    with pytest.raises(SystemExit) as exc:
        run("inconsistency", "resolve", "I999")
    assert "inconsistency not found" in str(exc.value)


# ---------------------------------------------------------------------------
# contradictions
# ---------------------------------------------------------------------------


@pytest.fixture
def conflicting_claims(run, seeded):
    run(
        "observe",
        "Alex",
        "--observation",
        "says single",
        "--claim",
        "relationship_status=single",
    )
    run(
        "observe",
        "Alex",
        "--observation",
        "says married",
        "--claim",
        "relationship_status=married",
    )
    return "Alex"


def test_contradictions_reports_none(run, seeded):
    assert "No contradictions detected for R001." in run("contradictions", "Alex")


def test_contradictions_marks_new_without_saving(run, conflicting_claims):
    out = run("contradictions", "Alex")
    assert "[new]" in out
    assert "Saved" not in out


def test_contradictions_save_is_idempotent(run, conflicting_claims):
    first = run("contradictions", "Alex", "--save")
    assert "[saved]" in first
    assert "Saved 1 new contradiction(s)" in first

    second = run("contradictions", "Alex", "--save")
    assert "[saved]" in second
    assert "Saved 0 new contradiction(s)" in second


# ---------------------------------------------------------------------------
# chat import
# ---------------------------------------------------------------------------


def _write(tmp_path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_chat_import_rejects_a_missing_file(run, seeded, tmp_path):
    with pytest.raises(SystemExit) as exc:
        run("chat", "import", "Alex", "--file", str(tmp_path / "nope.txt"))
    assert "chat file not found" in str(exc.value)


def test_chat_import_rejects_malformed_ndjson(run, seeded, tmp_path):
    bad = _write(tmp_path, "bad.jsonl", '{"timestamp": "2026-08-01T10:00:00+00:00",\n')
    with pytest.raises(SystemExit) as exc:
        run("chat", "import", "Alex", "--file", bad)
    assert "could not parse" in str(exc.value)


def test_chat_import_reports_an_empty_file(run, seeded, tmp_path):
    empty = _write(tmp_path, "empty.txt", "\n\n")
    assert "No messages parsed" in run("chat", "import", "Alex", "--file", empty)


def test_chat_import_extracts_claims_and_surfaces_conflicts(
    run, seeded, tmp_path, capsys
):
    chat = _write(
        tmp_path,
        "chat.jsonl",
        "\n".join(
            json.dumps(
                {
                    "timestamp": f"2026-08-0{day}T10:00:00+00:00",
                    "speaker": "Alex",
                    "text": text,
                }
            )
            for day, text in ((1, "he is single"), (2, "he is married"))
        ),
    )
    rules = _write(
        tmp_path,
        "rules.json",
        json.dumps(
            [
                {
                    "attribute": "relationship_status",
                    "pattern": r"\b(?:he|she|they) (?:is|was) (single|married)\b",
                }
            ]
        ),
    )
    out = run("chat", "import", "Alex", "--file", chat, "--rules", rules)
    assert "Imported 2 observation(s)" in out
    assert "Extracted 2 structured claim(s) via 1 rule(s)." in out
    assert "Detected 1 potential contradiction(s)" in out


def test_chat_import_reports_clean_when_no_conflicts(run, seeded, tmp_path):
    chat = _write(
        tmp_path,
        "chat.jsonl",
        json.dumps(
            {
                "timestamp": "2026-08-01T10:00:00+00:00",
                "speaker": "Alex",
                "text": "hello",
            }
        ),
    )
    out = run("chat", "import", "Alex", "--file", chat)
    assert "Imported 1 observation(s)" in out
    assert "Extracted 0 structured claim(s) via 0 rule(s)." in out
    assert "No contradictions detected in imported claims." in out


# ---------------------------------------------------------------------------
# timeline
# ---------------------------------------------------------------------------


def test_timeline_merges_every_event_kind(run, seeded):
    run(
        "observe",
        "Alex",
        "--observation",
        "showed up on time",
        "--signal-type",
        "COSTLY",
    )
    out = run("boundary", "add", "--description", "no lying", "--severity", "HARD")
    bid = _first_id(out, "B")
    run(
        "boundary",
        "hit",
        bid,
        "--relationship",
        "Alex",
        "--evidence",
        "denied a message",
    )
    run("inconsistency", "add", "Alex", "--description", "story differs")
    run("review", "Alex")

    out = run("timeline", "Alex")
    assert "Timeline for R001 (4 event(s)):" in out
    assert "O001" in out
    assert "H001" in out
    assert "I001" in out
    assert "RV001" in out


def test_timeline_reports_an_empty_history(run, seeded):
    out = run("timeline", "Alex")
    assert "Timeline for R001 (0 event(s)):" in out


# ---------------------------------------------------------------------------
# cooldown
# ---------------------------------------------------------------------------


def test_cooldown_list_reports_none(run, seeded):
    out = run("cooldown", "Alex")
    assert "Active cooldowns for R001:" in out
    assert "  (none)" in out


def test_cooldown_clear_with_nothing_active(run, seeded):
    assert "Cleared 0 active cooldown(s) for R001." in run("cooldown", "Alex", "clear")


def test_cooldown_list_shows_an_active_cooldown(run, cooled_down):
    out = run("cooldown", "Alex")
    assert "C001 [EXIT]" in out
    assert "remaining" in out


# ---------------------------------------------------------------------------
# relationship kinds (relationship-kinds proposal, S1)
# ---------------------------------------------------------------------------


def test_relationship_add_accepts_a_kind(run, db_path):
    run("init")
    out = run("relationship", "add", "Mentor", "--kind", "MENTOR")
    assert "kind: MENTOR" in out
    assert "MENTOR" in run("list")


def test_relationship_add_defaults_to_lover(run, db_path):
    run("init")
    out = run("relationship", "add", "Alex")
    assert "kind: LOVER" in out


def test_relationship_set_changes_kind(run, seeded):
    assert "Set kind MENTOR for R001" in run(
        "relationship", "set", "R001", "--kind", "MENTOR"
    )
    assert "MENTOR" in run("list")


def test_relationship_set_rejects_unknown_relationship(run, db_path):
    run("init")
    with pytest.raises(SystemExit) as exc:
        run("relationship", "set", "R999", "--kind", "MENTOR")
    assert "relationship not found" in str(exc.value)


def test_status_shows_kind_without_context_for_default(run, seeded):
    out = run("status", "Alex")
    assert "Kind             LOVER" in out
    assert "Context" not in out


def test_status_shows_ordinal_context_for_non_default_kind(run, seeded):
    run("relationship", "set", "R001", "--kind", "BOSS")
    out = run("status", "Alex")
    assert "Kind             BOSS" in out
    assert "power asymmetry: HIGH" in out
    assert "exit cost: HIGH" in out
    assert "verify promises before escalating" in out


def test_status_context_line_omits_empty_voice(run, seeded):
    """A non-default profile with no voice text must not print a trailing '|'."""
    run("relationship", "set", "R001", "--kind", "FRIEND")
    out = run("status", "Alex")
    assert "Context          power asymmetry: LOW | exit cost: LOW" in out


# ---------------------------------------------------------------------------
# promise expiry (relationship-kinds proposal, S2)
# ---------------------------------------------------------------------------


def _days_ago_iso(days: int) -> str:
    from datetime import UTC, datetime, timedelta

    return (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="seconds")


def _patch_clock(monkeypatch, days: int) -> None:
    """Stamp subsequent observations `days` in the past.

    `observe` timestamps via `storage.database._now`; the promise detector
    reads the real clock, so this makes promise ages CLI-controllable.
    """
    import love_risk_engine.storage.database as database

    monkeypatch.setattr(database, "_now", lambda: _days_ago_iso(days))


def test_status_shows_promise_section_for_windowed_kind(run, seeded, monkeypatch):
    run("relationship", "set", "R001", "--kind", "MENTOR")
    _patch_clock(monkeypatch, 100)
    run(
        "observe",
        "Alex",
        "--observation",
        "promised funding",
        "--claim",
        "funding=will fund the project",
    )
    _patch_clock(monkeypatch, 10)
    run(
        "observe",
        "Alex",
        "--observation",
        "promised a rec letter",
        "--claim",
        "rec=will recommend me",
    )
    out = run("status", "Alex")
    assert "Promises (window: 90d)" in out
    assert "rec='will recommend me'" in out
    assert "Older promises (1):" in out
    assert "lre promises" in out


def test_status_omits_promise_section_for_lover_kind(run, seeded, monkeypatch):
    _patch_clock(monkeypatch, 100)
    run(
        "observe",
        "Alex",
        "--observation",
        "promised funding",
        "--claim",
        "funding=will fund the project",
    )
    out = run("status", "Alex")
    assert "Promises (window" not in out


def test_status_promise_section_within_only(run, seeded, monkeypatch):
    """Only in-window promises: section renders, no 'Older promises' line."""
    run("relationship", "set", "R001", "--kind", "MENTOR")
    _patch_clock(monkeypatch, 10)
    run(
        "observe",
        "Alex",
        "--observation",
        "promised a rec letter",
        "--claim",
        "rec=will recommend me",
    )
    out = run("status", "Alex")
    assert "Promises (window: 90d)" in out
    assert "Older promises" not in out


def test_promises_command_lists_within_and_expired(run, seeded, monkeypatch):
    run("relationship", "set", "R001", "--kind", "BOSS")
    _patch_clock(monkeypatch, 100)
    run(
        "observe",
        "Alex",
        "--observation",
        "old promise",
        "--claim",
        "funding=will fund",
    )
    _patch_clock(monkeypatch, 10)
    run(
        "observe",
        "Alex",
        "--observation",
        "fresh promise",
        "--claim",
        "rec=will recommend",
    )
    out = run("promises", "Alex")
    assert "Promises for R001 (window: 90d):" in out
    assert "Within window:" in out
    assert "rec='will recommend'" in out
    assert "Expired (1):" in out
    assert "funding='will fund'" in out


def test_promises_command_reports_no_window_kind(run, seeded):
    out = run("promises", "Alex")
    assert "Kind LOVER does not track a promise window." in out


def test_promises_command_reports_empty(run, seeded):
    run("relationship", "set", "R001", "--kind", "MENTOR")
    out = run("promises", "Alex")
    assert "No promise claims recorded." in out


def test_promises_command_within_only(run, seeded, monkeypatch):
    run("relationship", "set", "R001", "--kind", "BOSS")
    _patch_clock(monkeypatch, 10)
    run(
        "observe",
        "Alex",
        "--observation",
        "fresh promise",
        "--claim",
        "rec=will recommend",
    )
    out = run("promises", "Alex")
    assert "Within window:" in out
    assert "Expired" not in out


def test_promises_command_expired_only(run, seeded, monkeypatch):
    run("relationship", "set", "R001", "--kind", "BOSS")
    _patch_clock(monkeypatch, 100)
    run(
        "observe",
        "Alex",
        "--observation",
        "old promise",
        "--claim",
        "funding=will fund",
    )
    out = run("promises", "Alex")
    assert "Expired (1):" in out
    assert "Within window:" not in out


def test_review_fires_promise_expiry_for_mentor(run, seeded, monkeypatch):
    run("relationship", "set", "R001", "--kind", "MENTOR")
    _patch_clock(monkeypatch, 100)
    run(
        "observe",
        "Alex",
        "--observation",
        "old promise",
        "--claim",
        "funding=will fund",
    )
    out = run("review", "Alex")
    assert "promise_expiry" in out


def test_review_does_not_fire_promise_expiry_for_lover(run, seeded, monkeypatch):
    _patch_clock(monkeypatch, 100)
    run(
        "observe",
        "Alex",
        "--observation",
        "old promise",
        "--claim",
        "funding=will fund",
    )
    out = run("review", "Alex")
    assert "promise_expiry" not in out


# ---------------------------------------------------------------------------
# repeated re-promises (phase 2)
# ---------------------------------------------------------------------------


def test_review_fires_repeated_repromises_for_mentor(run, seeded, monkeypatch):
    run("relationship", "set", "R001", "--kind", "MENTOR")
    for days in (5, 4, 3):
        _patch_clock(monkeypatch, days)
        run(
            "observe",
            "Alex",
            "--observation",
            "promised again",
            "--claim",
            "funding=will fund",
        )
    out = run("review", "Alex")
    assert "repeated_repromises" in out


def test_review_does_not_fire_repeated_repromises_for_lover(run, seeded, monkeypatch):
    for days in (5, 4, 3):
        _patch_clock(monkeypatch, days)
        run(
            "observe",
            "Alex",
            "--observation",
            "promised again",
            "--claim",
            "funding=will fund",
        )
    out = run("review", "Alex")
    assert "repeated_repromises" not in out


# ---------------------------------------------------------------------------
# counterfactual review (roadmap #2, architecture phase 2)
# ---------------------------------------------------------------------------


def test_counterfactual_reports_no_reviews(run, seeded):
    out = run("counterfactual", "Alex")
    assert "No reviews recorded" in out


def test_counterfactual_lists_reviews(run, seeded):
    run("review", "Alex")
    out = run("counterfactual", "Alex")
    assert "Reviews for R001:" in out
    assert "RV001" in out
    assert "Re-run one with" in out


def test_counterfactual_reruns_and_reports_match(run, seeded, monkeypatch):
    run("relationship", "set", "R001", "--kind", "MENTOR")
    _patch_clock(monkeypatch, 100)
    run(
        "observe",
        "Alex",
        "--observation",
        "old promise",
        "--claim",
        "funding=will fund",
    )
    review_out = run("review", "Alex")
    review_id = _first_id(review_out, "RV")
    out = run("counterfactual", "Alex", "--review", review_id)
    assert "Counterfactual review of" in out
    assert "Recomputed with today's rules" in out
    assert "MATCHED" in out


def test_counterfactual_reruns_and_reports_difference(run, seeded, monkeypatch):
    _patch_clock(monkeypatch, 100)
    run(
        "observe",
        "Alex",
        "--observation",
        "old promise",
        "--claim",
        "funding=will fund",
    )
    review_out = run("review", "Alex")  # LOVER: promise hooks off
    review_id = _first_id(review_out, "RV")
    run("relationship", "set", "R001", "--kind", "MENTOR")
    out = run("counterfactual", "Alex", "--review", review_id)
    assert "DIFFERENT" in out
    assert "promise_expiry" in out


def test_counterfactual_unknown_review_exits(run, seeded):
    with pytest.raises(SystemExit) as exc:
        run("counterfactual", "Alex", "--review", "RV999")
    assert "not found" in str(exc.value)


def test_counterfactual_omits_findings_line_when_empty(run, seeded, monkeypatch):
    """Unreachable via `main()`: run_hooks always returns >=1 finding."""
    import love_risk_engine.cli as cli
    from love_risk_engine.core.counterfactual import FrozenEvidence
    from love_risk_engine.services.counterfactual import CounterfactualResult

    run("review", "Alex")
    fake = CounterfactualResult(
        review_id="RV001",
        as_of="2026-09-01T00:00:00+00:00",
        original_recommendation="CONTINUE_OBSERVING",
        recomputed_recommendation="CONTINUE_OBSERVING",
        matched=True,
        fired_rule_ids=(),
        evidence=FrozenEvidence(
            "RV001", "2026-09-01T00:00:00+00:00", 0, 0, 0, 0.0, 0.0, 0.0, 0.0, "NEUTRAL"
        ),
    )
    monkeypatch.setattr(cli, "run_counterfactual", lambda db, rid, review_id: fake)
    out = run("counterfactual", "Alex", "--review", "RV001")
    assert "findings at that time" not in out


# ---------------------------------------------------------------------------
# mutual verification checklist (roadmap #3, architecture phase 2)
# ---------------------------------------------------------------------------


def test_verify_roundtrip_add_list_check_fail(run, seeded):
    run("verify", "add", "Alex", "--item", "introduced me to their friends")
    run("verify", "add", "Alex", "--item", "met them at work")
    out = run("verify", "list", "Alex")
    assert "[unverified] introduced me to their friends" in out
    run("verify", "check", "V001")
    run("verify", "fail", "V002", "--note", "their workplace said no")
    out = run("verify", "list", "Alex")
    assert "[verified] introduced me to their friends" in out
    assert "[failed] met them at work" in out


def test_verify_list_reports_empty(run, seeded):
    out = run("verify", "list", "Alex")
    assert "No verification items for R001." in out


def test_verify_check_unknown_id_exits(run, seeded):
    with pytest.raises(SystemExit) as exc:
        run("verify", "check", "V999")
    assert "not found" in str(exc.value)


def test_verify_fail_unknown_id_exits(run, seeded):
    with pytest.raises(SystemExit) as exc:
        run("verify", "fail", "V999")
    assert "not found" in str(exc.value)


def test_status_shows_verified_facts_when_present(run, seeded):
    run("verify", "add", "Alex", "--item", "introduced me to their friends")
    run("verify", "check", "V001")
    out = run("status", "Alex")
    assert "Verified facts: 1 of 1" in out


def test_status_omits_verified_facts_when_absent(run, seeded):
    out = run("status", "Alex")
    assert "Verified facts" not in out


# ---------------------------------------------------------------------------
# shell completion (architecture phase 3, E3)
# ---------------------------------------------------------------------------


def test_completion_prints_bash_template(run, seeded):
    out = run("completion", "bash")
    assert "complete -F _lre_completion lre" in out
    assert "lre _complete" in out


def test_internal_complete_prints_candidates(run, seeded):
    out = run("_complete", "rel")
    assert "relationship" in out


def test_internal_complete_never_lists_itself(run, seeded):
    out = run("_complete", "")
    assert "_complete" not in out


# ---------------------------------------------------------------------------
# i18n (localization phase)
# ---------------------------------------------------------------------------


def test_english_is_default_and_unchanged(run, seeded):
    out = run("status", "Alex")
    assert "Recommendation:" in out
    assert "Warnings:" in out
    assert "Relationship:" in out


def test_status_labels_localize_to_chinese(run, seeded, monkeypatch):
    monkeypatch.setenv("LRE_LANG", "zh")
    out = run("status", "Alex")
    assert "建议：" in out
    assert "警告" in out
    assert "关系：" in out


def test_help_localizes_to_chinese(run, seeded, monkeypatch, capsys):
    monkeypatch.setenv("LRE_LANG", "zh")
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    assert "用法" in out


def test_review_warning_localizes_to_chinese(run, seeded, monkeypatch):
    monkeypatch.setenv("LRE_LANG", "zh")
    run("state", "set", "Alex", "--attraction", "9", "--trust", "2")
    out = run("review", "Alex")
    assert "吸引力" in out  # the attraction-vs-trust warning in Chinese
    assert "建议：" in out


# ---------------------------------------------------------------------------
# rich optional presentation (localization phase, part 2)
# ---------------------------------------------------------------------------


def test_rich_panel_preserves_content(monkeypatch):
    import love_risk_engine.cli as cli

    captured: dict[str, str] = {}

    class FakeConsole:
        is_terminal = True

        def print(self, obj, **kwargs):
            captured["text"] = str(obj)

    class FakePanel:
        def __init__(self, content, title=None, border_style=None):
            captured["content"] = str(content)
            captured["title"] = str(title) if title else ""

    monkeypatch.setattr(
        cli, "_rich_console", type("M", (), {"Console": lambda: FakeConsole()})
    )
    monkeypatch.setattr(cli, "_rich_panel", type("M", (), {"Panel": FakePanel}))

    cli.print_output("Line one\nLine two\n", title="T")
    assert "Line one" in captured["content"]
    assert "Line two" in captured["content"]
    assert captured["title"] == "T"


def test_rich_fallback_prints_plain(monkeypatch, capsys):
    import love_risk_engine.cli as cli

    monkeypatch.setattr(cli, "_rich_console", None)
    cli.print_output("plain text\n", title="ignored")
    assert capsys.readouterr().out.startswith("plain text")


# ---------------------------------------------------------------------------
# sensitivity direction, boundary seeds, review context (S3)
# ---------------------------------------------------------------------------


def test_boss_status_fires_earlier_attraction_warning(run, seeded):
    run("state", "set", "Alex", "--attraction", "8.5", "--trust", "6")
    run("observe", "Alex", "--observation", "first date went well")
    out = run("status", "Alex")
    assert "exit-cost sensitive" not in out  # LOVER: gap 2.5 < 3.0 -> silent

    run("relationship", "set", "R001", "--kind", "BOSS")
    out = run("status", "Alex")
    assert "exit-cost sensitive" in out
    assert "gap threshold 2.0" in out


def test_review_prints_context_line_for_non_default_kind(run, seeded):
    out = run("review", "Alex")
    assert "Context" not in out  # LOVER stays quiet

    run("relationship", "set", "R001", "--kind", "BOSS")
    out = run("review", "Alex")
    assert "Context: power asymmetry: HIGH | exit cost: HIGH" in out
    assert "verify promises before escalating" in out


def test_relationship_add_suggests_seed_boundaries(run, db_path):
    run("init")
    out = run("relationship", "add", "Mom", "--kind", "PARENT")
    assert "Suggested boundaries for this kind" in out
    assert "respects my decisions about my own life" in out

    out = run("relationship", "add", "Alex")
    assert "Suggested boundaries" not in out


# ---------------------------------------------------------------------------
# state/exposure change history (roadmap item #1)
# ---------------------------------------------------------------------------


def test_history_command_lists_changes_with_deltas(run, seeded):
    run("state", "set", "Alex", "--attraction", "7.5", "--trust", "4")
    run("state", "set", "Alex", "--attraction", "8.5")
    run("exposure", "set", "Alex", "--time", "1", "--emotional", "2")
    run("exposure", "set", "Alex", "--time", "3")
    out = run("history", "Alex")
    assert "History for R001:" in out
    assert "[STATE]" in out
    assert "baseline: attraction 7.5" in out
    assert "attraction 7.5 -> 8.5" in out
    assert "[EXPOSURE]" in out
    assert "total 3.0 -> 5.0" in out


def test_history_command_reports_empty(run, seeded):
    out = run("history", "Alex")
    assert "No state or exposure changes recorded yet." in out


def test_timeline_includes_state_and_exposure_events(run, seeded):
    run("state", "set", "Alex", "--attraction", "7.5")
    run("state", "set", "Alex", "--attraction", "8.5")
    run("exposure", "set", "Alex", "--time", "2")
    out = run("timeline", "Alex")
    assert "[state]" in out
    assert "[exposure]" in out
    assert "attraction 7.5 -> 8.5" in out


# ---------------------------------------------------------------------------
# rapid exposure escalation (roadmap #1 follow-up)
# ---------------------------------------------------------------------------


def test_status_warns_on_rapid_exposure_without_evidence(run, seeded):
    run("exposure", "set", "Alex", "--time", "1")
    run("exposure", "set", "Alex", "--time", "4")
    out = run("status", "Alex")
    assert "Exposure grew 3.0 points in the last 2 days (1.0 -> 4.0)" in out
    assert "no new observations recorded" in out


def test_review_fires_rapid_exposure_escalation(run, seeded):
    run("exposure", "set", "Alex", "--time", "1")
    run("exposure", "set", "Alex", "--time", "4")
    out = run("review", "Alex")
    assert "rapid_exposure_escalation" in out


# ---------------------------------------------------------------------------
# data safety (architecture phase 1)
# ---------------------------------------------------------------------------


def test_export_and_restore_cli_roundtrip(run, seeded, tmp_path):
    run("state", "set", "Alex", "--attraction", "7.5")
    run("observe", "Alex", "--observation", "original observation")
    bundle = str(tmp_path / "backup.json")
    assert "Exported" in run("export", bundle)

    run("observe", "Alex", "--observation", "post-export mutation")
    assert "post-export mutation" in run("timeline", "Alex")

    assert "Restored" in run("restore", bundle)
    out = run("timeline", "Alex")
    assert "original observation" in out
    assert "post-export mutation" not in out


def test_export_refuses_existing_file(run, seeded, tmp_path):
    bundle = tmp_path / "backup.json"
    bundle.write_text("do not clobber", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        run("export", str(bundle))
    assert "already exists" in str(exc.value)


def test_restore_rejects_corrupt_file(run, seeded, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"format": "loverisk-bundle", "version": 1}', encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        run("restore", str(bad))
    assert "checksum" in str(exc.value)


def test_db_check_reports_ok(run, seeded):
    out = run("db", "check")
    assert "Database OK" in out


def test_db_check_reports_foreign_key_violation(run, seeded, db_path, capsys):
    """A damaged/hand-edited database must fail loudly, never pass silently."""
    import sqlite3

    # Plant a violation with FK enforcement off (production always has it on).
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        "INSERT INTO observation_claims(observation_id, attribute, value, idx) "
        "VALUES ('O999', 'k', 'v', 0)"
    )
    conn.commit()
    conn.close()

    with pytest.raises(SystemExit) as exc:
        main(["db", "check"])
    out = capsys.readouterr().out
    assert "foreign-key violation" in out
    assert "integrity check failed" in str(exc.value)
