from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceRef:
    source: str
    description: str
    lineage_id: str | None = None
