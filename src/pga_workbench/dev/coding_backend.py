from __future__ import annotations

from pathlib import Path
from typing import Any

from ..exceptions import WorkbenchException
from ..registry import load_yaml_unique

CODING_BACKEND_ERROR = "CODING_BACKEND_ERROR"


def load_coding_backend_descriptors(root: Path) -> dict[str, dict[str, Any]]:
    root = Path(root)
    descriptors: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*.yaml")):
        payload = load_yaml_unique(path)
        if not isinstance(payload, dict):
            raise WorkbenchException(CODING_BACKEND_ERROR, f"Backend descriptor must be a mapping: {path}")
        backend_id = str(payload.get("id") or path.stem)
        descriptors[backend_id] = payload
    return descriptors


def validate_coding_backends(repo_root: Path) -> dict[str, Any]:
    descriptors = load_coding_backend_descriptors(Path(repo_root) / "integrations" / "coding_backends")
    authoritative = [backend_id for backend_id, item in descriptors.items() if bool(item.get("authoritative"))]
    if authoritative:
        raise WorkbenchException(CODING_BACKEND_ERROR, f"Coding backends cannot be authoritative: {authoritative}")
    return {"backends": len(descriptors), "ids": sorted(descriptors)}
