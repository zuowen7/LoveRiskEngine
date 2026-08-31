"""Exposure model.

Design principle #3 (Exposure must not outrun Evidence):
  Five independent exposure axes are tracked separately so the user can see
  exactly where risk is concentrated. `total` is a simple sum used by the
  bias detector's exposure-vs-evidence heuristic (which is intentionally
  uncalibrated in v0.1).
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_EXPOSURE = 10.0


@dataclass
class Exposure:
    relationship_id: str
    time: float = 0.0
    emotional: float = 0.0
    privacy: float = 0.0
    financial: float = 0.0
    life_decision: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.time
            + self.emotional
            + self.privacy
            + self.financial
            + self.life_decision
        )

    def clamp(self) -> None:
        for field_name in (
            "time",
            "emotional",
            "privacy",
            "financial",
            "life_decision",
        ):
            value = float(getattr(self, field_name))
            setattr(self, field_name, max(0.0, min(MAX_EXPOSURE, value)))
