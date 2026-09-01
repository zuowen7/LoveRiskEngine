"""Lossless export/restore bundle (architecture phase 1, D1).

The bundle is one JSON file holding every table, the schema version, and a
SHA-256 checksum over the canonical payload — readable (pi-style
file-as-truth), verifiable, platform-independent. Export IS the backup: one
mechanism, no second path to maintain.

Restore refuses loudly on: unknown format/version, checksum mismatch
(corruption or tampering), and a schema version that does not match the live
database (cross-version restore is out of scope by decision).
"""

from __future__ import annotations

import hashlib
import json

from ..core.timeutil import utc_now_iso
from ..storage.database import Database
from ..storage.schema import SCHEMA_VERSION

BUNDLE_FORMAT = "loverisk-bundle"
BUNDLE_VERSION = 1


def _canonical(payload: dict[str, object]) -> bytes:
    """Deterministic serialization for the checksum (sorted keys, no spaces)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_bundle(
    tables: dict[str, list[dict[str, object]]],
    schema_version: int = SCHEMA_VERSION,
) -> dict[str, object]:
    """Assemble a bundle and stamp its checksum over the canonical payload."""
    payload: dict[str, object] = {
        "format": BUNDLE_FORMAT,
        "version": BUNDLE_VERSION,
        "schema_version": schema_version,
        "tables": tables,
    }
    payload["sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
    return payload


def save_bundle(db: Database, path: str) -> tuple[dict[str, object], int, int]:
    """Write the current database to `path` as a bundle.

    Returns (bundle, row_count, table_count) for the CLI summary.
    """
    tables = db.export_all_tables()
    bundle = build_bundle(tables)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({**bundle, "exported_at": utc_now_iso()}, f, indent=2)
    rows = sum(len(rows) for rows in tables.values())
    return bundle, rows, len(tables)


def verify_bundle(bundle: dict[str, object]) -> None:
    """Refuse loudly on format/version/checksum/schema mismatches."""
    if bundle.get("format") != BUNDLE_FORMAT:
        raise ValueError(
            f"not a {BUNDLE_FORMAT} file (format={bundle.get('format')!r})"
        )
    if bundle.get("version") != BUNDLE_VERSION:
        raise ValueError(f"unsupported bundle version {bundle.get('version')!r}")
    checksum = bundle.get("sha256")
    if not checksum:
        raise ValueError("bundle has no sha256 checksum")
    payload = {k: v for k, v in bundle.items() if k not in ("sha256", "exported_at")}
    if hashlib.sha256(_canonical(payload)).hexdigest() != checksum:
        raise ValueError("bundle checksum mismatch — corrupted or tampered file")
    schema_version = bundle.get("schema_version")
    if not isinstance(schema_version, int):
        raise ValueError("bundle has no valid schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ValueError(
            f"bundle schema v{schema_version} does not match database "
            f"v{SCHEMA_VERSION}; cross-version restore is not supported"
        )


def load_bundle(path: str) -> dict[str, object]:
    with open(path, encoding="utf-8") as f:
        bundle = json.load(f)
    verify_bundle(bundle)
    return bundle


def restore_bundle(db: Database, path: str) -> int:
    """Restore `path` into `db`, replacing its contents. Returns row count."""
    tables = load_bundle(path).get("tables")
    if not isinstance(tables, dict):
        raise ValueError("bundle has no tables payload")
    return db.restore_all_tables(tables)
