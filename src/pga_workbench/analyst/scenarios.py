from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioDraft:
    id: str
    description: str
    mutates_authoritative_state: bool = False
