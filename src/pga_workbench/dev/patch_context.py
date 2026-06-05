from __future__ import annotations

from pathlib import Path
from typing import Any

from ..agent.runtime import load_artemis_config
from ..exceptions import WorkbenchException
from ..tools.permissions import load_tool_permissions, summarize_tool_policy
from ..tools.registry import load_tool_registry
from .coding_backend import load_coding_backend_descriptors
from .tickets import load_development_ticket

CONTEXT_FILE_MISSING = "CONTEXT_FILE_MISSING"
CONTEXT_FILE_TOO_LARGE = "CONTEXT_FILE_TOO_LARGE"
CONTEXT_PROFILE_INVALID = "CONTEXT_PROFILE_INVALID"


PRIMARY_CONTEXT_FILES = [
    "AGENTS.md",
    "artemis.yaml",
    "README.md",
    "llms.txt",
    "docs/README.md",
    "docs/CONVENTIONS_LOCKED_v0.1.md",
    "development/CHANGE_POLICY.md",
]


def _load_text(repo_root: Path, relative_path: str, max_file_bytes: int) -> dict[str, str]:
    path = repo_root / relative_path
    if not path.exists():
        raise WorkbenchException(CONTEXT_FILE_MISSING, f"Required context file missing: {relative_path}")
    if not path.is_file():
        raise WorkbenchException(CONTEXT_FILE_MISSING, f"Required context path is not a file: {relative_path}")
    size = path.stat().st_size
    if size > max_file_bytes:
        raise WorkbenchException(CONTEXT_FILE_TOO_LARGE, f"Context file too large: {relative_path}")
    return {"path": relative_path, "content": path.read_text(encoding="utf-8")}


def _configured_profile_files(repo_root: Path, config: dict[str, Any], ticket: dict[str, Any]) -> tuple[str, list[str]]:
    context_cfg = config.get("context") or {}
    profiles = context_cfg.get("profiles") or {}
    profile_id = str(ticket.get("context_profile") or "default")
    if profile_id not in profiles:
        raise WorkbenchException(CONTEXT_PROFILE_INVALID, f"Unknown context_profile: {profile_id}")
    files: list[str] = []
    for item in profiles.get(profile_id, {}).get("files") or []:
        relative_path = str(item)
        path = repo_root / relative_path
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file():
                    files.append(str(child.relative_to(repo_root)))
        else:
            files.append(relative_path)
    return profile_id, files


def _affected_file_status(repo_root: Path, ticket: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    statuses: list[dict[str, Any]] = []
    missing: list[str] = []
    for relative_path in ticket.get("affected_files") or []:
        path = repo_root / str(relative_path)
        status = {
            "path": str(relative_path),
            "exists": path.exists(),
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
        }
        statuses.append(status)
        if not path.exists():
            missing.append(str(relative_path))
    return statuses, missing


def collect_development_context(repo_root: Path, ticket_id: str, config_path: Path | None = None) -> dict[str, Any]:
    repo_root = Path(repo_root)
    config = load_artemis_config(repo_root, config_path=config_path)
    ticket = load_development_ticket(repo_root, ticket_id)
    max_file_bytes = int((config.get("context") or {}).get("max_file_bytes") or 200000)
    affected_files, missing_affected_files = _affected_file_status(repo_root, ticket)

    files = [_load_text(repo_root, relative_path, max_file_bytes) for relative_path in PRIMARY_CONTEXT_FILES]
    loaded_paths = {item["path"] for item in files}
    context_profile, profile_files = _configured_profile_files(repo_root, config, ticket)
    for relative_path in profile_files:
        if relative_path not in loaded_paths:
            files.append(_load_text(repo_root, relative_path, max_file_bytes))
            loaded_paths.add(relative_path)
    for item in affected_files:
        if item["exists"] and item["is_file"] and item["path"] not in loaded_paths:
            files.append(_load_text(repo_root, item["path"], max_file_bytes))
            loaded_paths.add(item["path"])

    tools = load_tool_registry(repo_root / str(config["tools"]["registry"]), repo_root / "schemas")
    permissions = load_tool_permissions(repo_root / str(config["tools"]["permissions"]), repo_root / "schemas")
    backend_descriptors = load_coding_backend_descriptors(repo_root / "integrations" / "coding_backends")

    providers = config.get("providers") or {}
    profile_id = str(providers.get("default_profile") or "deterministic_only")
    profile = (providers.get("profiles") or {}).get(profile_id) or {"kind": "none", "required": False}
    coding_config = (config.get("backends") or {}).get("coding") or {}
    active_backend = str(coding_config.get("default") or "human")
    if active_backend not in backend_descriptors:
        raise WorkbenchException("CODING_BACKEND_INVALID", f"Unknown coding backend: {active_backend}")

    return {
        "mode": "development",
        "context_version": "artemis.development.v1",
        "artemis_config": "artemis.yaml",
        "context_profile": context_profile,
        "active_profile": profile_id,
        "profile": profile,
        "provider": None if profile.get("kind") in {None, "none", "deterministic_only"} else profile.get("kind"),
        "active_backend": active_backend,
        "authority_ladder": {
            "root_contract": config["authority"]["root_contract"],
            "canonical_domain": config["authority"]["canonical_domain"],
            "change_policy": config["authority"]["change_policy"],
            "deterministic_core": config["authority"]["deterministic_core"],
        },
        "ticket": ticket,
        "affected_files": affected_files,
        "missing_affected_files": missing_affected_files,
        "tool_policy": summarize_tool_policy(tools, permissions),
        "backend_options": {
            backend_id: {
                "kind": descriptor.get("kind"),
                "required": bool(descriptor.get("required")),
                "authoritative": bool(descriptor.get("authoritative")),
                "capabilities": descriptor.get("capabilities") or {},
            }
            for backend_id, descriptor in sorted(backend_descriptors.items())
        },
        "release_validation_commands": list((config.get("release") or {}).get("validation_commands") or []),
        "files": files,
    }
