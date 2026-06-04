from __future__ import annotations

from .base import ProviderProfile


def profile() -> ProviderProfile:
    return ProviderProfile(id="deterministic_only", kind="deterministic_only", required=False, authoritative=True)
