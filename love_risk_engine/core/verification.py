"""Mutual verification checklist (roadmap #3).

User-curated verifiable facts whose costly-signal status can be confirmed —
the sharp end of the cheap-talk/costly-signal boundary. Three states:
unverified (default), verified, failed. The engine never auto-verifies:
confirming is always the user's action. Items are append-only — status
transitions are allowed, deletion is not.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass(frozen=True)
class VerificationItem:
    id: str
    relationship_id: str
    item: str
    status: str
    note: str
    created_at: str
    verified_at: str | None
