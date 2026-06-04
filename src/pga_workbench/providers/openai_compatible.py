from __future__ import annotations

from .base import ProviderProfile


def profile(profile_id: str = "openai_compatible") -> ProviderProfile:
    return ProviderProfile(id=profile_id, kind="openai_compatible", required=False, authoritative=False)
