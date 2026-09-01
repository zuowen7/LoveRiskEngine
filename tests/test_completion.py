"""Shell completion engine tests (architecture phase 3, E3).

Written test-first per docs/proposals/PLAN_phase3_ux.md: these fail until the
completion engine exists in cli.py, then pin argparse-tree walking, partial
filtering, and the hidden-command hygiene.
"""

from __future__ import annotations

from love_risk_engine.cli import completion_candidates


def test_root_candidates_list_subcommands():
    candidates = completion_candidates([""])
    assert "observe" in candidates
    assert "relationship" in candidates
    assert "verify" in candidates
    # hidden plumbing must never surface
    assert "_complete" not in candidates


def test_descends_into_subcommands():
    candidates = completion_candidates(["relationship", ""])
    # argparse auto-adds -h/--help; the subcommands are what matter here
    assert "add" in candidates
    assert "set" in candidates


def test_positional_choices_surface():
    # `lre relationship add Alex --kind <TAB>` -> the seven kinds
    candidates = completion_candidates(["relationship", "add", "Alex", "--kind", ""])
    for kind in ("LOVER", "BOSS", "MENTOR", "COLLEAGUE", "STRANGER"):
        assert kind in candidates


def test_partial_prefix_filters():
    candidates = completion_candidates(["relationship", "add", "Alex", "--ki"])
    assert candidates == ["--kind"]


def test_option_values_are_skipped():
    # `--claim k=v` consumes its value; the next token is a fresh option
    candidates = completion_candidates(["observe", "Alex", "--claim", "k=v", "--si"])
    assert "--signal-type" in candidates


def test_unknown_tokens_do_not_crash():
    candidates = completion_candidates(["nonsense", "tokens", "--zzz", ""])
    assert isinstance(candidates, list)  # safe fallback, never raises


def test_positional_choices_in_general_path():
    # `lre completion <TAB>` -> the shell names
    candidates = completion_candidates(["completion", ""])
    for shell in ("bash", "zsh", "fish", "powershell"):
        assert shell in candidates


def test_trailing_option_without_choices_falls_back():
    # `verify add Alex --item <TAB>`: --item takes free text, so the general
    # candidate set surfaces instead of nothing.
    candidates = completion_candidates(["verify", "add", "Alex", "--item", ""])
    assert "--item" in candidates
