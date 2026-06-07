from __future__ import annotations

from typing import Any

from ..exceptions import WorkbenchException

PROVIDER_PROFILE_ERROR = "PROVIDER_PROFILE_ERROR"


def validate_provider_profiles(config: dict[str, Any], *, error_code: str = PROVIDER_PROFILE_ERROR) -> dict[str, Any]:
    providers = config.get("providers") or {}
    profiles = providers.get("profiles") or {}
    if not isinstance(profiles, dict):
        raise WorkbenchException(error_code, "Provider profiles must be a mapping")
    default_profile = str(providers.get("default_profile") or "")
    if not default_profile:
        raise WorkbenchException(error_code, "providers.default_profile is required")
    default = profiles.get(default_profile)
    if not isinstance(default, dict):
        raise WorkbenchException(error_code, f"providers.default_profile references unknown profile: {default_profile}")

    kind = str(default.get("kind") or "")
    if kind == "deterministic_only":
        return {
            "default_profile": default_profile,
            "kind": kind,
            "deterministic": True,
            "model_calls": False,
            "parameters": {},
        }

    determinism = default.get("determinism") or {}
    if not isinstance(determinism, dict):
        raise WorkbenchException(error_code, f"Provider profile {default_profile} determinism must be a mapping")
    if determinism.get("profile") != "deterministic" and default.get("deterministic_profile") is not True:
        raise WorkbenchException(error_code, f"Default provider profile {default_profile} is not marked deterministic")
    if determinism.get("guaranteed") is not True:
        raise WorkbenchException(error_code, f"Default provider profile {default_profile} cannot guarantee determinism")

    parameters = _provider_parameters(default)
    if parameters.get("temperature") not in {0, 0.0}:
        raise WorkbenchException(error_code, f"Default provider profile {default_profile} must pin temperature to 0")
    if determinism.get("supports_seed", True) is not False and "seed" not in parameters:
        raise WorkbenchException(error_code, f"Default provider profile {default_profile} must pin seed when supported")
    return {
        "default_profile": default_profile,
        "kind": kind,
        "deterministic": True,
        "model_calls": True,
        "parameters": parameters,
    }


def _provider_parameters(profile: dict[str, Any]) -> dict[str, Any]:
    parameters = dict(profile.get("parameters") or {})
    for key in ["temperature", "seed", "top_p"]:
        if key in profile and key not in parameters:
            parameters[key] = profile[key]
    return parameters
