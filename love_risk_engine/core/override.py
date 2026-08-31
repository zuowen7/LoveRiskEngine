"""Override domain model.

Every time a user raises exposure during an active cooldown (the engine's
precommitment guardrail), the override is logged here for audit. `log_override`
/ `list_overrides` return these, not raw rows.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OverrideLog:
    id: str
    relationship_id: str
    cooldown_id: str | None
    reason: str
    timestamp: str
