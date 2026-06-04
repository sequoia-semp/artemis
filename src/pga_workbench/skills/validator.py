from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique
from ..tools.registry import load_tool_registry, registered_tool_ids

SKILL_VALIDATION_ERROR = "SKILL_VALIDATION_ERROR"


def load_skill_ids(skills_root: Path) -> set[str]:
    manifest_path = Path(skills_root) / "manifest.yaml"
    manifest = load_yaml_unique(manifest_path)
    return {str(item.get("id")) for item in manifest.get("skills") or []}


def _validate(schema: dict[str, Any], payload: dict[str, Any], label: str) -> None:
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: error.path)
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.path)
        suffix = f" at {path}" if path else ""
        raise WorkbenchException(SKILL_VALIDATION_ERROR, f"{label}{suffix}: {first.message}")


def validate_skill_manifest(repo_root: Path, schema_dir: Path) -> dict[str, Any]:
    repo_root = Path(repo_root)
    schema_dir = Path(schema_dir)
    skills_root = repo_root / "skills"
    manifest_path = skills_root / "manifest.yaml"
    manifest = load_yaml_unique(manifest_path)
    if not isinstance(manifest, dict):
        raise WorkbenchException(SKILL_VALIDATION_ERROR, f"Skill manifest must be a mapping: {manifest_path}")
    schema = load_yaml_unique(schema_dir / "skill.schema.json")
    tools = load_tool_registry(repo_root / "registries" / "tools.yaml", schema_dir)
    tool_ids = registered_tool_ids(tools)
    seen: set[str] = set()
    validated: list[str] = []
    for item in manifest.get("skills") or []:
        skill_id = str(item.get("id"))
        if skill_id in seen:
            raise WorkbenchException(SKILL_VALIDATION_ERROR, f"Duplicate skill id: {skill_id}")
        seen.add(skill_id)
        path = skills_root / str(item.get("path"))
        if not path.exists():
            raise WorkbenchException(SKILL_VALIDATION_ERROR, f"Skill descriptor missing: {path}")
        descriptor = load_yaml_unique(path)
        _validate(schema, descriptor, str(path))
        if descriptor.get("id") != skill_id:
            raise WorkbenchException(SKILL_VALIDATION_ERROR, f"Skill manifest id mismatch: {skill_id}")
        for tool_id in descriptor.get("tools") or []:
            if tool_id not in tool_ids:
                raise WorkbenchException(SKILL_VALIDATION_ERROR, f"Skill {skill_id} references unknown tool {tool_id}")
        validated.append(str(path))
    return {"manifest": str(manifest_path), "skills": len(validated), "validated": validated}
