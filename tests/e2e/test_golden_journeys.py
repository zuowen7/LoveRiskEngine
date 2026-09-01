"""Installed-CLI golden journeys over a real temporary SQLite database."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


@dataclass(frozen=True)
class DatabaseSnapshot:
    user_version: int
    tables: dict[str, tuple[str, ...]]


def _snapshot(path: Path) -> DatabaseSnapshot:
    assert path.is_file(), f"database does not exist: {path}"
    conn = sqlite3.connect(path)
    try:
        conn.row_factory = sqlite3.Row
        user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        names = [
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        tables: dict[str, tuple[str, ...]] = {}
        for name in names:
            quoted = '"' + name.replace('"', '""') + '"'
            records = conn.execute(f"SELECT * FROM {quoted}").fetchall()
            tables[name] = tuple(
                sorted(
                    json.dumps(
                        dict(record),
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    for record in records
                )
            )
    finally:
        conn.close()
    return DatabaseSnapshot(user_version=user_version, tables=tables)


def _rows(snapshot: DatabaseSnapshot, table: str) -> list[dict[str, object]]:
    return [json.loads(record) for record in snapshot.tables[table]]


def _first_id(output: str, prefix: str) -> str:
    match = re.search(rf"\b{prefix}\d+\b", output)
    assert match is not None, f"no {prefix} id in output:\n{output}"
    return match.group(0)


def test_fresh_user_reaches_first_review(installed_cli) -> None:
    cli = installed_cli
    invalid = cli.run("not-a-command", expected_code=2)
    assert "invalid choice" in invalid.stderr
    assert invalid.stdout == "" and not cli.db_path.exists()
    assert "Initialized LoveRiskEngine database" in cli.run("init").stdout
    assert "Created relationship R001" in cli.run("relationship", "add", "Alice").stdout
    assert (
        "Recorded observation O001"
        in cli.run(
            "observe",
            "Alice",
            "--observation",
            "Alice followed through on the agreed plan",
            "--interpretation",
            "She is reliable",
            "--alternative",
            "The plan may simply have been easy to keep",
            "--signal-type",
            "COSTLY",
        ).stdout
    )
    cli.run(
        "state",
        "set",
        "Alice",
        "--attraction",
        "6",
        "--trust",
        "5",
        "--uncertainty",
        "4",
        "--emotional",
        "CALM",
    )
    cli.run("exposure", "set", "Alice", "--time", "1", "--emotional", "1")

    review = cli.run("review", "Alice")
    assert "Review RV001 for R001" in review.stdout
    assert "Recommendation:" in review.stdout
    timeline = cli.run("timeline", "Alice")
    assert "Timeline for R001" in timeline.stdout
    assert "O001" in timeline.stdout and "RV001" in timeline.stdout
    status = cli.run("status", "Alice")
    assert "Relationship: R001" in status.stdout
    assert "Trust            5.0 / 10" in status.stdout

    snapshot = _snapshot(cli.db_path)
    assert len(_rows(snapshot, "relationships")) == 1
    assert len(_rows(snapshot, "observations")) == 1
    assert len(_rows(snapshot, "relationship_state")) == 1
    assert len(_rows(snapshot, "exposure")) == 1
    assert len(_rows(snapshot, "reviews")) == 1


def test_risk_escalation_reaches_exit_from_hard_boundary(installed_cli) -> None:
    cli = installed_cli
    cli.run("init")
    cli.run("relationship", "add", "Alice")
    cli.run(
        "observe",
        "Alice",
        "--observation",
        "Alice cancelled dinner at short notice",
    )
    cli.run(
        "inconsistency",
        "add",
        "Alice",
        "--description",
        "The explanation changed twice",
    )
    boundary = cli.run(
        "boundary",
        "add",
        "--description",
        "No threats",
        "--severity",
        "HARD",
    )
    boundary_id = _first_id(boundary.stdout, "B")
    cli.run(
        "boundary",
        "hit",
        boundary_id,
        "--relationship",
        "Alice",
        "--evidence",
        "A direct threat was recorded in the conversation",
    )

    review = cli.run("review", "Alice")
    assert "Recommendation: EXIT" in review.stdout
    assert "Cooldown C001 started" in review.stdout

    snapshot = _snapshot(cli.db_path)
    assert len(_rows(snapshot, "observations")) == 1
    assert len(_rows(snapshot, "inconsistencies")) == 1
    assert len(_rows(snapshot, "boundary_hits")) == 1
    assert _rows(snapshot, "reviews")[0]["recommendation"] == "EXIT"
    assert _rows(snapshot, "cooldowns")[0]["decision"] == "EXIT"


def test_cooldown_block_override_and_audit_trail(installed_cli) -> None:
    cli = installed_cli
    cli.run("init")
    cli.run("relationship", "add", "Alice")
    cli.run("exposure", "set", "Alice", "--time", "1", "--emotional", "1")
    boundary = cli.run(
        "boundary",
        "add",
        "--description",
        "No threats",
        "--severity",
        "HARD",
    )
    cli.run(
        "boundary",
        "hit",
        _first_id(boundary.stdout, "B"),
        "--relationship",
        "Alice",
        "--evidence",
        "A direct threat was recorded",
    )
    cli.run("review", "Alice")

    blocked = cli.run("exposure", "set", "Alice", "--time", "5", expected_code=1)
    assert "BLOCKED: an active cooldown prevents raising exposure." in blocked.stdout
    assert blocked.stderr == ""
    assert _rows(_snapshot(cli.db_path), "exposure")[0]["time"] == 1.0

    overridden = cli.run(
        "exposure",
        "set",
        "Alice",
        "--time",
        "5",
        "--override",
        "--reason",
        "Verified an immediate safety plan",
    )
    assert "OVERRIDE logged" in overridden.stdout
    snapshot = _snapshot(cli.db_path)
    assert _rows(snapshot, "exposure")[0]["time"] == 5.0
    overrides = _rows(snapshot, "override_log")
    assert len(overrides) == 1
    assert overrides[0]["cooldown_id"] == "C001"
    assert overrides[0]["reason"] == "Verified an immediate safety plan"
    cooldown = cli.run("cooldown", "Alice")
    assert "Override history (1):" in cooldown.stdout
    assert "Verified an immediate safety plan" in cooldown.stdout


def test_chat_import_surfaces_claims_contradiction_and_promise(
    installed_cli, tmp_path: Path
) -> None:
    cli = installed_cli
    cli.run("init")
    cli.run("relationship", "add", "Alice", "--kind", "BOSS")
    start = datetime.now(UTC) - timedelta(days=1)
    messages = [
        {
            "timestamp": (start + timedelta(minutes=index)).isoformat(),
            "speaker": "Alice",
            "text": text,
        }
        for index, text in enumerate(
            ("status=single", "status=married", "plan=I will move next month")
        )
    ]
    chat_path = tmp_path / "chat.jsonl"
    chat_path.write_text(
        "\n".join(json.dumps(message) for message in messages), encoding="utf-8"
    )
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(
        json.dumps(
            [
                {
                    "attribute": "relationship_status",
                    "pattern": r"status=(single|married)",
                },
                {"attribute": "future_plan", "pattern": r"plan=(.+)"},
            ]
        ),
        encoding="utf-8",
    )

    imported = cli.run(
        "chat",
        "import",
        "Alice",
        "--file",
        str(chat_path),
        "--rules",
        str(rules_path),
    )
    assert "Imported 3 observation(s)" in imported.stdout
    assert "Extracted 3 structured claim(s) via 2 rule(s)." in imported.stdout
    assert "Detected 1 potential contradiction(s)" in imported.stdout
    contradictions = cli.run("contradictions", "Alice", "--save")
    assert "Saved 1 new contradiction(s)" in contradictions.stdout
    promises = cli.run("promises", "Alice")
    assert "Promises for R001 (window: 90d):" in promises.stdout
    assert "future_plan='I will move next month'" in promises.stdout
    timeline = cli.run("timeline", "Alice")
    assert "status=single" in timeline.stdout
    assert "status=married" in timeline.stdout
    assert "I001" in timeline.stdout

    snapshot = _snapshot(cli.db_path)
    assert len(_rows(snapshot, "observations")) == 3
    assert len(_rows(snapshot, "observation_claims")) == 3
    assert len(_rows(snapshot, "inconsistencies")) == 1


def test_disaster_recovery_is_semantically_lossless(installed_cli) -> None:
    cli = installed_cli
    cli.run("init")
    cli.run("relationship", "add", "Alice")
    cli.run(
        "observe",
        "Alice",
        "--observation",
        "Alice said she was single",
        "--claim",
        "relationship_status=single",
        "--signal-type",
        "CHEAP",
    )
    cli.run("state", "set", "Alice", "--trust", "4", "--uncertainty", "6")
    cli.run("exposure", "set", "Alice", "--time", "1", "--privacy", "1")
    boundary = cli.run(
        "boundary",
        "add",
        "--description",
        "No threats",
        "--severity",
        "HARD",
    )
    cli.run(
        "boundary",
        "hit",
        _first_id(boundary.stdout, "B"),
        "--relationship",
        "Alice",
        "--evidence",
        "A direct threat was recorded",
    )
    cli.run("inconsistency", "add", "Alice", "--description", "Two accounts differ")
    verification = cli.run(
        "verify", "add", "Alice", "--item", "Confirm relationship status"
    )
    cli.run("verify", "check", _first_id(verification.stdout, "V"))
    review = cli.run("review", "Alice")
    review_id = _first_id(review.stdout, "RV")
    cli.run(
        "exposure",
        "set",
        "Alice",
        "--time",
        "2",
        "--override",
        "--reason",
        "Documented recovery test override",
    )
    cli.run(
        "evaluate",
        review_id,
        "--outcome",
        "bad",
        "--note",
        "Retrospective label for recovery test",
    )

    before = _snapshot(cli.db_path)
    assert all(before.tables.values()), {
        name for name, records in before.tables.items() if not records
    }
    backup = cli.workdir / "backup.json"
    exported = cli.run("export", str(backup))
    assert "Exported" in exported.stdout and backup.is_file()

    cli.db_path.unlink()
    assert not cli.db_path.exists()
    assert "Restored" in cli.run("restore", str(backup)).stdout
    assert "Database OK" in cli.run("db", "check").stdout
    assert "Relationship: R001" in cli.run("status", "Alice").stdout
    assert "RV001" in cli.run("timeline", "Alice").stdout

    after = _snapshot(cli.db_path)
    assert after == before
