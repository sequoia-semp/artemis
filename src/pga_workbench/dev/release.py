from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
from typing import Any

from jsonschema import Draft202012Validator

from ..agent_runtime.release_workflow import collect_release_readiness
from ..core.time import utc_now_iso
from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique

RELEASE_CANDIDATE_ERROR = "RELEASE_CANDIDATE_ERROR"


def _git_value(repo_root: Path, command: list[str]) -> str | None:
    completed = subprocess.run(command, cwd=repo_root, capture_output=True, text=True)
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _file_sha256(repo_root: Path, relative_path: str) -> str | None:
    path = repo_root / relative_path
    if not path.exists() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_release_candidate(repo_root: Path, ticket_id: str, target_version: str = "0.2.0") -> dict[str, Any]:
    repo_root = Path(repo_root)
    readiness = collect_release_readiness(repo_root, ticket_id=ticket_id, skip_tests=True)
    source_branch = _git_value(repo_root, ["git", "branch", "--show-current"]) or "unknown"
    commit = _git_value(repo_root, ["git", "rev-parse", "HEAD"])
    ticket = readiness.get("ticket") or {}
    manifest_paths = [
        "artemis.yaml",
        "registries/tools.yaml",
        "registries/tool_permissions.yaml",
        "registries/data_sources.yaml",
        "skills/manifest.yaml",
        "views/manifest.yaml",
        "schemas/artemis_config.schema.json",
        "schemas/release_candidate.schema.json",
    ]
    candidate = {
        "id": f"RC-{target_version}-{ticket_id}",
        "target_version": target_version,
        "base_branch": "main",
        "source_branch": source_branch,
        "commit": commit,
        "created_at": utc_now_iso(),
        "package_version": str((readiness.get("package") or {}).get("version") or ""),
        "scope": [
            "artemis console script",
            "analyst/development modes",
            "config schema",
            "tool registry",
            "fundamental view skeleton",
            "data source descriptors",
            "release workflow",
        ],
        "changed_artifacts": list(ticket.get("affected_files") or []),
        "validation_commands": list(readiness.get("validation_commands") or []),
        "validation": {
            item["command"]: {
                "status": "skipped" if item.get("skipped") else "passed" if item.get("passed") else "failed",
                "returncode": item.get("returncode"),
            }
            for item in readiness.get("validation_results") or []
        },
        "manifest_hashes": {relative_path: _file_sha256(repo_root, relative_path) for relative_path in manifest_paths},
        "requires_human_review": True,
        "approved": False,
        "notes": ["Generated deterministically; no tag or publish action performed."],
    }
    schema = load_yaml_unique(repo_root / "schemas" / "release_candidate.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(candidate), key=lambda error: error.path)
    if errors:
        first = errors[0]
        path_label = ".".join(str(part) for part in first.path)
        suffix = f" at {path_label}" if path_label else ""
        raise WorkbenchException(RELEASE_CANDIDATE_ERROR, f"release candidate{suffix}: {first.message}")
    return candidate
