from __future__ import annotations

from .base import ProviderProfile


def profile(profile_id: str = "external_harness") -> ProviderProfile:
    return ProviderProfile(id=profile_id, kind="external_harness", required=False, authoritative=False)
