from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import yaml

from ..registry import validate_registries
from .kb_validator import validate_knowledge_base
from .work_item_loader import validate_work_items


def load_capability_registry(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {"version": "missing", "core": {}, "wrappers": {}}
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        return {"version": "invalid", "core": {}, "wrappers": {}}
    return payload


def check_command_available(command: str) -> dict[str, Any]:
    parts = shlex.split(command)
    executable = parts[0] if parts else ""
    path = shutil.which(executable) if executable else None
    return {
        "command": command,
        "executable": executable,
        "available": path is not None,
        "path": path,
    }


def check_http_available(url: str, timeout: float = 0.5) -> dict[str, Any]:
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return {"url": url, "reachable": True, "status": response.status}
    except (TimeoutError, URLError, OSError) as exc:
        return {"url": url, "reachable": False, "error": exc.__class__.__name__}


def recommend_agent_mode(capabilities: dict[str, Any]) -> str:
    wrappers = capabilities.get("wrappers") or {}
    opencode = wrappers.get("opencode") or {}
    ollama = wrappers.get("ollama") or {}
    if opencode.get("available") and ollama.get("reachable"):
        return "opencode_ollama"
    if opencode.get("available"):
        return "opencode_external_model"
    return "context_bundle_manual"


def collect_agent_capabilities(repo_root: Path, check_network: bool = False) -> dict[str, Any]:
    repo_root = Path(repo_root)
    registry = load_capability_registry(repo_root / "integrations" / "capability_registry.yaml")
    core: dict[str, Any] = {}
    wrappers: dict[str, Any] = {}

    for name, item in (registry.get("core") or {}).items():
        detection = item.get("detection") or {}
        command = detection.get("command") or name
        result = check_command_available(str(command))
        if name == "pga" and not result["available"]:
            result["available"] = (repo_root / "src" / "pga_workbench" / "cli.py").exists()
            result["path"] = result["path"] or "src/pga_workbench/cli.py"
            result["note"] = "pga console script not on PATH; package CLI source is present"
        result["required"] = bool(item.get("required"))
        result["purpose"] = item.get("purpose")
        core[name] = result

    for name, item in (registry.get("wrappers") or {}).items():
        detection = item.get("detection") or {}
        result: dict[str, Any] = {
            "required": bool(item.get("required")),
            "purpose": item.get("purpose"),
            "authoritative": bool(item.get("authoritative")),
        }
        if "command" in detection:
            result.update(check_command_available(str(detection["command"])))
        else:
            path = shutil.which(name)
            result.update({"executable": name, "available": path is not None, "path": path})
        if "http" in detection:
            result["http"] = detection["http"]
            if check_network:
                http_result = check_http_available(str(detection["http"]))
                result.update(http_result)
            else:
                result["reachable"] = False
                result["network_check_skipped"] = True
        wrappers[name] = result

    capabilities = {
        "core": core,
        "wrappers": wrappers,
    }
    capabilities["recommended_mode"] = recommend_agent_mode(capabilities)
    return capabilities


def _run_check(name: str, command: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    return {
        "name": name,
        "command": " ".join(command),
        "passed": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def collect_agent_doctor(repo_root: Path, check_network: bool = False, skip_tests: bool = False) -> dict[str, Any]:
    repo_root = Path(repo_root)
    checks: list[dict[str, Any]] = []

    if skip_tests:
        checks.append({"name": "pytest", "skipped": True, "passed": True})
    else:
        checks.append(_run_check("pytest", [sys.executable, "-m", "pytest", "-q"], repo_root))

    try:
        result = validate_registries(repo_root / "registries", repo_root / "schemas")
        checks.append(
            {
                "name": "validate-registries",
                "passed": True,
                "validated_files": len(result.validated_files),
                "checked_records": result.checked_records,
                "warnings": result.warnings,
            }
        )
    except Exception as exc:
        checks.append({"name": "validate-registries", "passed": False, "error": str(exc)})

    try:
        validated = validate_work_items(repo_root / "work", repo_root / "schemas")
        checks.append({"name": "validate-work-items", "passed": True, "validated": len(validated)})
    except Exception as exc:
        checks.append({"name": "validate-work-items", "passed": False, "error": str(exc)})

    kb_root = repo_root / "knowledge_base"
    if kb_root.exists():
        try:
            result = validate_knowledge_base(kb_root, repo_root / "schemas")
            checks.append({"name": "validate-kb", "passed": True, "entries": result["entries"]})
        except Exception as exc:
            checks.append({"name": "validate-kb", "passed": False, "error": str(exc)})

    capabilities = collect_agent_capabilities(repo_root, check_network=check_network)
    checks.append(
        {
            "name": "agent-capabilities",
            "passed": bool((capabilities.get("core") or {}).get("pga", {}).get("available")),
            "recommended_mode": capabilities.get("recommended_mode"),
        }
    )

    return {
        "checks": checks,
        "capabilities": capabilities,
        "passed": all(check.get("passed") for check in checks),
    }
