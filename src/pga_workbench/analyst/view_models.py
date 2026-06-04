from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Stance:
    direction: str = "mixed"
    strength: str = "low"
    summary: str = "Insufficient supplied inputs for an authoritative stance."


@dataclass(frozen=True)
class DataQuality:
    missing_required_inputs: list[str] = field(default_factory=list)
    stale_inputs: list[dict[str, Any]] = field(default_factory=list)
    fixture_mode: bool = False
    data_environment: str = "development"


def empty_section_for(view_type: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    prior = {} if view_type == "prior_day_retrospective" else None
    current = {} if view_type in {"current_day", "eastern_power_market", "gas_basis_market"} else None
    fourteen = {} if view_type == "fourteen_day_fundamentals" else None
    return prior, current, fourteen
