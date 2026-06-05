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
    procedural = _validate_procedural_manifest(repo_root, skills_root)
    return {"manifest": str(manifest_path), "skills": len(validated), "validated": validated, **procedural}


def _validate_procedural_manifest(repo_root: Path, skills_root: Path) -> dict[str, Any]:
    manifest_path = skills_root / "procedural_manifest.yaml"
    if not manifest_path.exists():
        return {"procedural_manifest": None, "procedural_skills": 0, "procedural_validated": []}
    manifest = load_yaml_unique(manifest_path)
    if not isinstance(manifest, dict):
        raise WorkbenchException(SKILL_VALIDATION_ERROR, f"Procedural skill manifest must be a mapping: {manifest_path}")
    seen: set[str] = set()
    validated: list[str] = []
    declared_shims: set[str] = set()
    for item in manifest.get("procedural_skills") or []:
        skill_id = str(item.get("id") or "")
        if not skill_id:
            raise WorkbenchException(SKILL_VALIDATION_ERROR, "Procedural skill is missing id")
        if skill_id in seen:
            raise WorkbenchException(SKILL_VALIDATION_ERROR, f"Duplicate procedural skill id: {skill_id}")
        seen.add(skill_id)
        path = skills_root / str(item.get("path") or "")
        if not path.exists() or not path.is_file():
            raise WorkbenchException(SKILL_VALIDATION_ERROR, f"Procedural skill markdown missing: {path}")
        authority = str(item.get("authority") or "")
        if authority not in {"deterministic_services_only", "candidate_only"}:
            raise WorkbenchException(SKILL_VALIDATION_ERROR, f"Procedural skill {skill_id} has invalid authority: {authority}")
        if item.get("analytics_impact") and authority != "deterministic_services_only":
            raise WorkbenchException(SKILL_VALIDATION_ERROR, f"Procedural skill {skill_id} affects analytics but is not deterministic-authority bounded")
        for field in ["deterministic_dependencies", "inputs", "outputs", "tests"]:
            if not item.get(field):
                raise WorkbenchException(SKILL_VALIDATION_ERROR, f"Procedural skill {skill_id} lacks {field}")
        text = path.read_text(encoding="utf-8")
        if "# Skill:" not in text or "## Purpose" not in text:
            raise WorkbenchException(SKILL_VALIDATION_ERROR, f"Procedural skill {skill_id} lacks required markdown headings")
        for shim in item.get("shims") or []:
            shim_path = repo_root / str(shim)
            if not shim_path.exists() or not shim_path.is_file():
                raise WorkbenchException(SKILL_VALIDATION_ERROR, f"Procedural skill {skill_id} shim missing: {shim}")
            declared_shims.add(str(shim))
        validated.append(str(path))

    active_shims = {str(path.relative_to(repo_root)) for path in sorted((repo_root / ".agents" / "skills").glob("*/SKILL.md"))}
    unmanifested = sorted(active_shims - declared_shims)
    if unmanifested:
        raise WorkbenchException(SKILL_VALIDATION_ERROR, f"Unmanifested active skill shims: {unmanifested}")
    return {
        "procedural_manifest": str(manifest_path),
        "procedural_skills": len(validated),
        "procedural_validated": validated,
    }
