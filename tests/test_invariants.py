"""Architecture invariant guards (ARCHITECTURE_AND_PLAN.md §1).

These are executable invariants: the build fails if the package ever starts
doing something the architecture forbids. A network import now requires
amending this test *and* invariant #1 — the drift cannot be accidental.

Layer boundary matrix (lower layer may not import a higher one):

    core      -> (nothing below; pure domain)
    storage   -> core only
    services  -> core, storage
    cli       -> core, storage, services  (top of stack, free)

Every forbidden pair below the diagonal has a dedicated test. Adding a new
layer or relaxing a boundary means editing this matrix *and* the canonical
architecture doc — the drift cannot be accidental.
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

# Layer boundary matrix: which roots each layer is forbidden from importing.
# A layer may import its own package and any layer *above* it in the stack
# (core < storage < services < cli), never one below.
_LAYER_FORBIDDEN_IMPORTS: dict[str, frozenset[str]] = {
    "love_risk_engine.core": frozenset(
        {
            "love_risk_engine.storage",
            "love_risk_engine.services",
            "love_risk_engine.cli",
        }
    ),
    "love_risk_engine.storage": frozenset(
        {"love_risk_engine.services", "love_risk_engine.cli"}
    ),
    "love_risk_engine.services": frozenset({"love_risk_engine.cli"}),
    # cli is the top of the stack — nothing is forbidden there.
}

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "love_risk_engine"


def test_package_has_no_network_imports():
    """Invariant #1 (local-only): no module under love_risk_engine may import
    a network library. The engine runs local-only by contract; a network
    import is the seed of every surveillance / exfiltration defect this
    project exists to avoid.
    """
    offenders: list[str] = []
    for path in sorted(_PACKAGE_ROOT.rglob("*.py")):
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
                    rel = path.relative_to(_PACKAGE_ROOT)
                    offenders.append(f"{rel} imports {root}")
    assert not offenders, (
        f"network import detected — invariant #1 (local-only). Offenders: {offenders}"
    )


def _resolve_relative_import(node: ast.ImportFrom, current_package: str) -> str:
    """Resolve a ``from ... import`` to its absolute module path.

    ``current_package`` is the package the source file lives in (e.g.
    ``love_risk_engine.core``). Relative levels count up from there:
    level 1 = ``current_package``, level 2 = its parent, etc.
    """
    if node.level == 0:
        return node.module or ""
    parts = current_package.split(".")
    # level 1 = current_package (drop 0 trailing parts), level 2 = drop 1, ...
    drop = node.level - 1
    if drop > len(parts):
        return node.module or ""
    base = ".".join(parts[: len(parts) - drop])
    if node.module:
        return f"{base}.{node.module}" if base else node.module
    return base


def _matches_forbidden(name: str, forbidden_roots: frozenset[str]) -> bool:
    """True if ``name`` is or descends into any forbidden root."""
    return any(name == root or name.startswith(root + ".") for root in forbidden_roots)


def _scan_layer_for_forbidden_imports(
    layer_dir: Path,
    layer_package: str,
    forbidden_roots: frozenset[str],
) -> list[str]:
    """Scan every .py under ``layer_dir`` for imports of ``forbidden_roots``.

    Catches ``import X``, ``from X import Y`` (incl. relative), and the
    alias-name escape hatch ``from love_risk_engine import storage`` where
    the forbidden name lives in the aliases, not the module path.
    """
    offenders: list[str] = []
    for path in sorted(layer_dir.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _matches_forbidden(alias.name, forbidden_roots):
                        offenders.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                resolved = _resolve_relative_import(node, layer_package)
                if _matches_forbidden(resolved, forbidden_roots):
                    offenders.append(f"{path.name}: from {resolved}")
                    # Module path already matched — the alias check below would
                    # only double-report the same statement (e.g. `from
                    # love_risk_engine.cli import main` flags both the module
                    # path and `main`). Skip it; one offender per statement.
                    continue
                # Catch `from love_risk_engine import storage` — the forbidden
                # name lives in the aliases, not the module path. Only worth
                # running when the module path itself did NOT match (otherwise
                # it's the redundant case above).
                for alias in node.names:
                    full = f"{resolved}.{alias.name}" if resolved else alias.name
                    if _matches_forbidden(full, forbidden_roots):
                        offenders.append(
                            f"{path.name}: from {resolved} import {alias.name}"
                        )
    return offenders


def test_core_does_not_import_storage_services_cli():
    """Invariant #1 (layer boundary): core/ must not import storage, services
    or cli. core/ is the pure domain layer; reaching below it couples the
    domain to a persistence/transport choice and breaks the adapter boundary.
    """
    offenders = _scan_layer_for_forbidden_imports(
        layer_dir=_PACKAGE_ROOT / "core",
        layer_package="love_risk_engine.core",
        forbidden_roots=_LAYER_FORBIDDEN_IMPORTS["love_risk_engine.core"],
    )
    assert not offenders, (
        "invariant #1 (boundary) violated — core/ imports a forbidden layer "
        f"(storage/services/cli). Offenders: {offenders}"
    )


def test_storage_does_not_import_services_or_cli():
    """Invariant #1 (layer boundary): storage/ may import core/ only.
    storage/ is the persistence adapter; reaching into services/ or cli/
    inverts the dependency direction and turns the adapter into an
    orchestrator. The DB layer must stay a dumb sink.
    """
    offenders = _scan_layer_for_forbidden_imports(
        layer_dir=_PACKAGE_ROOT / "storage",
        layer_package="love_risk_engine.storage",
        forbidden_roots=_LAYER_FORBIDDEN_IMPORTS["love_risk_engine.storage"],
    )
    assert not offenders, (
        "invariant #1 (boundary) violated — storage/ imports a forbidden "
        f"layer (services/cli). Offenders: {offenders}"
    )


def test_services_does_not_import_cli():
    """Invariant #1 (layer boundary): services/ may import core/ and storage/
    only. Reaching into cli/ couples orchestration to a presentation choice
    (argv parsing, stdout formatting, i18n chrome), which makes the service
    untestable without a CLI harness and blocks future alternate frontends.
    """
    offenders = _scan_layer_for_forbidden_imports(
        layer_dir=_PACKAGE_ROOT / "services",
        layer_package="love_risk_engine.services",
        forbidden_roots=_LAYER_FORBIDDEN_IMPORTS["love_risk_engine.services"],
    )
    assert not offenders, (
        "invariant #1 (boundary) violated — services/ imports cli/. "
        f"Offenders: {offenders}"
    )


def test_scanner_actually_catches_a_forbidden_import(tmp_path):
    """Meta-guard: the layer scanner must FAIL when a forbidden import is
    present. A guard that can't fail is decoration. This injects each of the
    four import shapes the scanner claims to handle — `import X`, `from X
    import Y`, relative `from . import X`, and the alias escape hatch
    `from love_risk_engine import cli` — and asserts every one is reported.
    """
    fake_layer = tmp_path / "fake_layer"
    fake_layer.mkdir()
    (fake_layer / "direct_import.py").write_text(
        "import love_risk_engine.cli\n", encoding="utf-8"
    )
    (fake_layer / "from_import.py").write_text(
        "from love_risk_engine.cli import main\n", encoding="utf-8"
    )
    (fake_layer / "relative_import.py").write_text(
        "from ... import cli\n", encoding="utf-8"
    )
    (fake_layer / "alias_escape.py").write_text(
        "from love_risk_engine import cli\n", encoding="utf-8"
    )
    offenders = _scan_layer_for_forbidden_imports(
        layer_dir=fake_layer,
        layer_package="love_risk_engine.core.fake_layer",
        forbidden_roots=frozenset({"love_risk_engine.cli"}),
    )
    # Every shape must be caught — and the alias escape hatch is the one
    # most scanners silently miss, so it gets its own assertion.
    assert len(offenders) == 4, (
        f"scanner missed a shape — expected 4 offenders, got {offenders!r}"
    )
    assert any("alias_escape" in o and "import cli" in o for o in offenders), (
        f"alias escape hatch not caught: {offenders!r}"
    )
