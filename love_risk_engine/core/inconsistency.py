"""Inconsistency domain model.

`inconsistencies` can be raised by the user (`kind='manual'`) or auto-detected
from conflicting claims (`kind='detected'`). `list_inconsistencies` /
`list_all_inconsistencies` / `acknowledged_inconsistencies` return these, not
raw rows. Optional fields are None for user-raised items and populated for
detected ones.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Inconsistency:
    id: str
    relationship_id: str
    description: str
    resolved: bool
    created_at: str
    kind: str = "manual"
    attribute: str | None = None
    value_a: str | None = None
    value_b: str | None = None
    obs_a: str | None = None
    obs_b: str | None = None
    resolution: str | None = None
    resolution_note: str = ""
