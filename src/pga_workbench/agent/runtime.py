from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import yaml

from ..agent_runtime.capabilities import collect_agent_capabilities
from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique
from ..tools.permissions import load_tool_permissions, summarize_tool_policy
from ..tools.registry import load_tool_registry

ARTEMIS_CONFIG_ERROR = "ARTEMIS_CONFIG_ERROR"


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_config_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise WorkbenchException(ARTEMIS_CONFIG_ERROR, f"Artemis config missing: {path}")
    payload = load_yaml_unique(path)
    if not isinstance(payload, dict):
        raise WorkbenchException(ARTEMIS_CONFIG_ERROR, f"Artemis config must be a mapping: {path}")
    return payload


def load_artemis_config(repo_root: Path, config_path: Path | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root)
    config = _load_config_file(repo_root / "artemis.yaml")
    candidates = [
        ("local", os.environ.get("ARTEMIS_LOCAL_CONFIG") or str(repo_root / "local" / "artemis.local.yaml"), bool(os.environ.get("ARTEMIS_LOCAL_CONFIG"))),
        ("env", os.environ.get("ARTEMIS_CONFIG"), bool(os.environ.get("ARTEMIS_CONFIG"))),
        ("cli", str(config_path) if config_path else None, config_path is not None),
    ]
    for label, candidate, required in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if not path.is_absolute():
            path = repo_root / path
        if path.exists():
            config = _deep_merge(config, _load_config_file(path))
        elif required:
            raise WorkbenchException(ARTEMIS_CONFIG_ERROR, f"{label} Artemis config override missing: {path}")
    return config


def validate_artemis_config(repo_root: Path, config_path: Path | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root)
    config = load_artemis_config(repo_root, config_path=config_path)
    schema = load_yaml_unique(repo_root / "schemas" / "artemis_config.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(config), key=lambda error: error.path)
    if errors:
        first = errors[0]
        path_label = ".".join(str(part) for part in first.path)
        suffix = f" at {path_label}" if path_label else ""
        raise WorkbenchException(ARTEMIS_CONFIG_ERROR, f"artemis.yaml{suffix}: {first.message}")

    missing_paths = []
    for relative_path in [
        config["authority"]["root_contract"],
        config["authority"]["change_policy"],
        config["tools"]["registry"],
        config["tools"]["permissions"],
        config["knowledge"]["manifest"],
        config["skills"]["manifest"],
        config["views"]["manifest"],
        config["data_sources"]["registry"],
    ]:
        if not (repo_root / relative_path).exists():
            missing_paths.append(relative_path)
    if missing_paths:
        raise WorkbenchException(ARTEMIS_CONFIG_ERROR, f"Config references missing paths: {missing_paths}")
    return config


def config_for_display(config: dict[str, Any]) -> dict[str, Any]:
    """Return config with secret-bearing values still represented only by env names."""
    return dict(config)


def collect_artemis_capabilities(repo_root: Path, check_network: bool = False, config_path: Path | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root)
    config = validate_artemis_config(repo_root, config_path=config_path)
    agent_capabilities = collect_agent_capabilities(repo_root, check_network=check_network)
    tools = load_tool_registry(repo_root / config["tools"]["registry"], repo_root / "schemas")
    permissions = load_tool_permissions(repo_root / config["tools"]["permissions"], repo_root / "schemas")

    providers = config.get("providers") or {}
    profiles = providers.get("profiles") or {}
    optional_profiles = {
        name: {
            "kind": item.get("kind"),
            "required": bool(item.get("required")),
            "configured_by_env": item.get("api_key_env"),
        }
        for name, item in profiles.items()
    }

    return {
        "name": config.get("name"),
        "version": config.get("version"),
        "package": config.get("package"),
        "modes": config.get("modes") or {},
        "roles": config.get("roles") or {},
        "providers": {
            "default_profile": providers.get("default_profile"),
            "profiles": optional_profiles,
        },
        "tools": {
            "count": len(tools.get("tools") or {}),
            "policy": summarize_tool_policy(tools, permissions),
        },
        "core": agent_capabilities.get("core") or {},
        "wrappers": agent_capabilities.get("wrappers") or {},
        "recommended_mode": agent_capabilities.get("recommended_mode"),
    }


def dump_config_yaml(config: dict[str, Any]) -> str:
    return yaml.safe_dump(config_for_display(config), sort_keys=False)
