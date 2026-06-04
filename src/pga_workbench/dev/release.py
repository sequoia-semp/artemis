from __future__ import annotations

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


def build_release_candidate(repo_root: Path, ticket_id: str, target_version: str = "0.2.0") -> dict[str, Any]:
    repo_root = Path(repo_root)
    readiness = collect_release_readiness(repo_root, ticket_id=ticket_id, skip_tests=True)
    source_branch = _git_value(repo_root, ["git", "branch", "--show-current"]) or "unknown"
    commit = _git_value(repo_root, ["git", "rev-parse", "HEAD"])
    ticket = readiness.get("ticket") or {}
    candidate = {
        "id": f"RC-{target_version}-{ticket_id}",
        "target_version": target_version,
        "base_branch": "main",
        "source_branch": source_branch,
        "commit": commit,
        "created_at": utc_now_iso(),
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
        "validation": {
            "pytest": "pending",
            "validate_registries": "pending",
            "validate_work_items": "pending",
            "validate_kb": "pending",
            "validate_skills": "pending",
            "validate_views": "pending",
            "validate_data_sources": "pending",
        },
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
