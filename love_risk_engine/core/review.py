"""Review domain model.

The output of a full review run. `save_review` / `list_reviews` return these,
not raw rows. `cooldown_id` is optional: set only when this review created a
cooldown (the column is not yet in the schema, so it is always "" on read).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Review:
    id: str
    relationship_id: str
    timestamp: str
    triggered_hooks: list[str]
    unresolved_inconsistencies: int
    recommendation: str
    notes: str
    cooldown_id: str = ""
