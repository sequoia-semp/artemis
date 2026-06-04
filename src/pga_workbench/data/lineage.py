from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LineageRef:
    source: str
    lineage_id: str
    raw_reference: str
