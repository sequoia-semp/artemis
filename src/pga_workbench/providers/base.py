from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderProfile:
    id: str
    kind: str
    required: bool = False
    authoritative: bool = False


@dataclass(frozen=True)
class ProviderRole:
    id: str
    required: bool
    accepted_kinds: tuple[str, ...]
