"""Architecture invariant guards (ARCHITECTURE_AND_PLAN.md §1).

These are executable invariants: the build fails if the package ever starts
doing something the architecture forbids. A network import now requires
amending this test *and* invariant #1 — the drift cannot be accidental.
"""

from __future__ import annotations

import ast
from pathlib import Path

_FORBIDDEN_NETWORK_MODULES = {
    "aiohttp",
    "ftplib",
    "http",
    "httpx",
    "requests",
    "smtplib",
    "socket",
    "telnetlib",
    "urllib",
    "urllib3",
}


def test_package_has_no_network_imports():
    package = Path(__file__).resolve().parent.parent / "love_risk_engine"
    offenders: list[str] = []
    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                names = [node.module]
            for name in names:
                root = name.split(".")[0]
                if root in _FORBIDDEN_NETWORK_MODULES:
                    offenders.append(f"{path.relative_to(package)} imports {root}")
    assert not offenders, (
        f"network import detected — invariant #1 (local-only). Offenders: {offenders}"
    )
