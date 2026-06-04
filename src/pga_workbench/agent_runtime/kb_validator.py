from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import yaml

from ..exceptions import WorkbenchException

KB_VALIDATION_ERROR = "KB_VALIDATION_ERROR"


def validate_knowledge_base(kb_root: Path, schema_dir: Path) -> dict[str, Any]:
    kb_root = Path(kb_root)
    schema_dir = Path(schema_dir)
    manifest_path = kb_root / "MANIFEST.yaml"
    schema_path = schema_dir / "knowledge_base_entry.schema.json"

    if not manifest_path.exists():
        raise WorkbenchException(KB_VALIDATION_ERROR, f"Knowledge base manifest missing: {manifest_path}")
    if not schema_path.exists():
        raise WorkbenchException(KB_VALIDATION_ERROR, f"Knowledge base schema missing: {schema_path}")

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(manifest), key=lambda error: error.path)
    if errors:
        first = errors[0]
        path_label = ".".join(str(part) for part in first.path)
        suffix = f" at {path_label}" if path_label else ""
        raise WorkbenchException(KB_VALIDATION_ERROR, f"{manifest_path}{suffix}: {first.message}")

    missing_entries = []
    for entry in manifest.get("entries") or []:
        relative_path = entry.get("path")
        if not relative_path or not (kb_root / relative_path).exists():
            missing_entries.append(str(relative_path))
    if missing_entries:
        raise WorkbenchException(KB_VALIDATION_ERROR, f"Knowledge base entries missing: {missing_entries}")

    return {"manifest": str(manifest_path), "entries": len(manifest.get("entries") or [])}
