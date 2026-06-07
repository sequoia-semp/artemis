from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import yaml

from ..agent_runtime.capabilities import collect_agent_capabilities
from ..agent_runtime.provider_profiles import validate_provider_profiles
from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique
from ..tools.permissions import load_tool_permissions, summarize_tool_policy
from ..tools.registry import load_tool_registry, registered_tool_ids

ARTEMIS_CONFIG_ERROR = "ARTEMIS_CONFIG_ERROR"


def _load_env_file(path: Path, required: bool = False) -> bool:
    path = Path(path)
    if not path.exists():
        if required:
            raise WorkbenchException(ARTEMIS_CONFIG_ERROR, f"Artemis env file override missing: {path}")
        return False
    if not path.is_file():
        raise WorkbenchException(ARTEMIS_CONFIG_ERROR, f"Artemis env file path is not a file: {path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
    return True


def _load_default_env_files(repo_root: Path) -> None:
    for path in [repo_root / ".env", repo_root / "local" / ".env"]:
        _load_env_file(path, required=False)
    explicit = os.environ.get("ARTEMIS_ENV_FILE")
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = repo_root / path
        _load_env_file(path, required=True)


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
    _load_default_env_files(repo_root)
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
    for relative_path in (config.get("runtime") or {}).get("env_files") or []:
        path = Path(str(relative_path))
        if not path.is_absolute():
            path = repo_root / path
        _load_env_file(path, required=False)
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
        *(([config["skills"]["procedural_manifest"]] if (config.get("skills") or {}).get("procedural_manifest") else [])),
        config["views"]["manifest"],
        config["data_sources"]["registry"],
    ]:
        if not (repo_root / relative_path).exists():
            missing_paths.append(relative_path)
    for relative_path in (config.get("policies") or {}).values():
        if not (repo_root / str(relative_path)).exists():
            missing_paths.append(str(relative_path))
    if missing_paths:
        raise WorkbenchException(ARTEMIS_CONFIG_ERROR, f"Config references missing paths: {missing_paths}")

    tools = load_tool_registry(repo_root / config["tools"]["registry"], repo_root / "schemas")
    tool_ids = registered_tool_ids(tools)
    default_tool_errors: list[str] = []
    for mode_name, mode in sorted((config.get("modes") or {}).items()):
        for tool_id in mode.get("default_tools") or []:
            if tool_id not in tool_ids:
                default_tool_errors.append(f"{mode_name}.{tool_id}: not registered")
                continue
            tool_modes = set(((tools.get("tools") or {}).get(tool_id) or {}).get("modes") or [])
            if mode_name not in tool_modes:
                default_tool_errors.append(f"{mode_name}.{tool_id}: registered for {sorted(tool_modes)}")
    if default_tool_errors:
        raise WorkbenchException(ARTEMIS_CONFIG_ERROR, f"Default tool registry mismatch: {default_tool_errors}")
    validate_provider_profiles(config, error_code=ARTEMIS_CONFIG_ERROR)
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
    provider_determinism = validate_provider_profiles(config, error_code=ARTEMIS_CONFIG_ERROR)
    profiles = providers.get("profiles") or {}
    optional_profiles = {
        name: {
            "kind": item.get("kind"),
            "required": bool(item.get("required")),
            "configured_by_env": item.get("api_key_env"),
        }
        for name, item in profiles.items()
    }
    file_sources = {
        key: {
            "env": env_name,
            "configured": bool(os.environ.get(str(env_name))),
            "path": os.environ.get(str(env_name)),
        }
        for key, env_name in (config.get("file_sources") or {}).items()
    }
    runtime_env_files = []
    for relative_path in (config.get("runtime") or {}).get("env_files") or []:
        path = Path(str(relative_path))
        if not path.is_absolute():
            path = repo_root / path
        runtime_env_files.append({"path": str(relative_path), "exists": path.exists()})

    return {
        "name": config.get("name"),
        "version": config.get("version"),
        "package": config.get("package"),
        "modes": config.get("modes") or {},
        "roles": config.get("roles") or {},
        "providers": {
            "default_profile": providers.get("default_profile"),
            "determinism": provider_determinism,
            "profiles": optional_profiles,
        },
        "runtime": {
            "env_files": runtime_env_files,
        },
        "file_sources": file_sources,
        "policies": config.get("policies") or {},
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
