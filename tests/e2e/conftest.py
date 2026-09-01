"""Black-box fixtures for the installed ``lre`` console script.

This module intentionally imports nothing from ``love_risk_engine``.  The
system under test is the installed process boundary, not an in-process Python
API.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class InstalledCli:
    def __init__(self, executable: Path, workdir: Path) -> None:
        self.executable = executable
        self.workdir = workdir
        self.db_path = workdir / "test.db"

    def run(self, *args: str, expected_code: int = 0) -> CommandResult:
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env.update(
            {
                "LRE_DB_PATH": str(self.db_path),
                "LRE_LANG": "en",
                "NO_COLOR": "1",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
                "TERM": "dumb",
            }
        )
        env.pop("LRE_COOLDOWN_HOURS", None)
        completed = subprocess.run(
            [str(self.executable), *args],
            cwd=self.workdir,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )
        result = CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        assert result.returncode == expected_code, (
            f"command: lre {' '.join(args)}\n"
            f"expected exit: {expected_code}; actual: {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        return result


@pytest.fixture
def installed_cli(tmp_path: Path) -> InstalledCli:
    configured = os.environ.get("LRE_E2E_BIN")
    located = configured or shutil.which("lre")
    if located is None:
        pytest.fail(
            "installed `lre` executable not found; install the project first "
            "or set LRE_E2E_BIN"
        )
    executable = Path(located).resolve()
    if not executable.is_file() or executable.name.lower() not in {"lre", "lre.exe"}:
        pytest.fail(f"LRE_E2E_BIN is not an installed lre executable: {executable}")
    return InstalledCli(executable, tmp_path)
