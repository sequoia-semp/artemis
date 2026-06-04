from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..exceptions import WorkbenchException
from .work_item_loader import load_ticket

CONTEXT_FILE_MISSING = "CONTEXT_FILE_MISSING"
CONTEXT_FILE_TOO_LARGE = "CONTEXT_FILE_TOO_LARGE"
CONTEXT_PROFILE_INVALID = "CONTEXT_PROFILE_INVALID"


def load_config(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise WorkbenchException(CONTEXT_FILE_MISSING, f"Config not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise WorkbenchException("CONTEXT_CONFIG_INVALID", f"Config must be a mapping: {path}")
    return payload


def _load_text(repo_root: Path, relative_path: str, max_file_bytes: int) -> dict[str, str]:
    path = repo_root / relative_path
    if not path.exists():
        raise WorkbenchException(CONTEXT_FILE_MISSING, f"Required context file missing: {relative_path}")
    size = path.stat().st_size
    if size > max_file_bytes:
        raise WorkbenchException(CONTEXT_FILE_TOO_LARGE, f"Context file too large: {relative_path}")
    return {"path": relative_path, "content": path.read_text(encoding="utf-8")}


def _resolve_profile(config: dict[str, Any]) -> tuple[str, dict[str, Any], str | None]:
    profiles = config.get("profiles")
    if isinstance(profiles, dict):
        active_profile = str(config.get("active_profile") or "deterministic_only")
        profile = profiles.get(active_profile)
        if not isinstance(profile, dict):
            raise WorkbenchException(CONTEXT_PROFILE_INVALID, f"Unknown local LLM profile: {active_profile}")
        provider = profile.get("provider") or profile.get("provider_kind")
        if provider == "none":
            provider = None
        return active_profile, dict(profile), provider

    # Backward compatibility for the original flat local/llm_config.example.yaml shape.
    provider = config.get("provider")
    active_profile = str(config.get("active_profile") or provider or "deterministic_only")
    profile: dict[str, Any] = {}
    if provider == "ollama":
        profile = {"provider_kind": "openai_compatible", **(config.get("ollama") or {})}
    elif provider:
        profile = {"provider_kind": provider}
    else:
        profile = {"provider_kind": "none", "required": False}
    return active_profile, profile, provider


def collect_context(repo_root: Path, ticket_id: str, config_path: Path) -> dict[str, Any]:
    repo_root = Path(repo_root)
    config = load_config(config_path)
    active_profile, profile, provider = _resolve_profile(config)
    context_cfg = config.get("context") or {}
    max_file_bytes = int(context_cfg.get("max_file_bytes") or 200000)
    work_root = repo_root / str(context_cfg.get("work_item_root") or "work/")
    ticket = load_ticket(work_root, ticket_id)

    files = []
    for relative_path in context_cfg.get("always_load") or []:
        files.append(_load_text(repo_root, relative_path, max_file_bytes))
    for relative_path in ticket.get("affected_files") or []:
        if (repo_root / relative_path).is_file():
            files.append(_load_text(repo_root, relative_path, max_file_bytes))

    return {
        "active_profile": active_profile,
        "profile": profile,
        "provider": provider,
        "safety": config.get("safety") or {},
        "ticket": ticket,
        "files": files,
    }
