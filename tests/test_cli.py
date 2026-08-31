import pytest
from love_risk_engine.cli import main


def test_cli_smoke(tmp_path, monkeypatch):
    db_path = str(tmp_path / "cli.db")
    monkeypatch.setenv("LRE_DB_PATH", db_path)

    assert main(["init"]) == 0
    assert main(["relationship", "add", "Alex"]) == 0
    assert (
        main(
            [
                "observe",
                "Alex",
                "--category",
                "honesty",
                "--observation",
                "cancelled plans twice",
                "--interpretation",
                "losing interest",
                "--alternative",
                "work deadline",
                "--confidence",
                "4",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "state",
                "set",
                "Alex",
                "--attraction",
                "8.5",
                "--trust",
                "4",
                "--uncertainty",
                "7",
                "--emotional",
                "ANXIOUS",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "exposure",
                "set",
                "Alex",
                "--time",
                "3",
                "--emotional",
                "4",
                "--privacy",
                "1",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "boundary",
                "add",
                "--description",
                "never disrespects my boundaries",
                "--severity",
                "HARD",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "inconsistency",
                "add",
                "Alex",
                "--description",
                "tuesday story differs from wednesday",
            ]
        )
        == 0
    )
    assert main(["status", "Alex"]) == 0
    assert main(["review", "Alex"]) == 0
    assert main(["list"]) == 0

    # unknown relationship should abort with a non-zero exit
    with pytest.raises(SystemExit):
        main(["status", "ghost"])
