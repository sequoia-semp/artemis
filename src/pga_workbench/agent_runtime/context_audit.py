from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any

from ..agent.runtime import load_artemis_config
from ..exceptions import WorkbenchException
from ..tools.registry import load_tool_registry, registered_tool_ids

CONTEXT_AUDIT_ERROR = "CONTEXT_AUDIT_ERROR"

ACTIVE_PROMPT_ROOTS = (
    ".opencode/agents",
    ".opencode/commands",
)

ACTIVE_DOC_RE = re.compile(r"(?P<path>(?:docs|development|work|registries|schemas|skills|\.agents|\.opencode)/[A-Za-z0-9_./-]+\.md)")
STALE_VALIDATION_COMMANDS = (
    "python -m pytest -q",
    "pga validate-registries",
    "pga validate-work-items",
)


@dataclass(frozen=True)
class ContextAuditFinding:
    severity: str
    code: str
    surface: str
    path: str
    message: str
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _active_prompt_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for root in ACTIVE_PROMPT_ROOTS:
        path = repo_root / root
        if path.exists():
            files.extend(sorted(item for item in path.rglob("*.md") if item.is_file()))
    return files


def _rel(repo_root: Path, path: Path) -> str:
    return str(path.relative_to(repo_root))


def _audit_default_tools(repo_root: Path) -> list[ContextAuditFinding]:
    findings: list[ContextAuditFinding] = []
    try:
        config = load_artemis_config(repo_root)
        registry = load_tool_registry(repo_root / str(config["tools"]["registry"]), repo_root / "schemas")
    except WorkbenchException as exc:
        return [
            ContextAuditFinding(
                severity="blocker",
                code="config_load_failed",
                surface="artemis_config",
                path="artemis.yaml",
                message=f"{exc.code}: {exc.message}",
                remediation="Fix Artemis config and tool registry loading before auditing context.",
            )
        ]
    tool_ids = registered_tool_ids(registry)
    tools = registry.get("tools") or {}
    for mode_name, mode in sorted((config.get("modes") or {}).items()):
        for tool_id in mode.get("default_tools") or []:
            if tool_id not in tool_ids:
                findings.append(
                    ContextAuditFinding(
                        severity="blocker",
                        code="missing_default_tool",
                        surface="artemis_config",
                        path="artemis.yaml",
                        message=f"{mode_name} default tool is not registered: {tool_id}",
                        remediation="Register the tool in registries/tools.yaml or remove it from mode defaults.",
                    )
                )
                continue
            modes = set((tools.get(tool_id) or {}).get("modes") or [])
            if mode_name not in modes:
                findings.append(
                    ContextAuditFinding(
                        severity="blocker",
                        code="mode_incompatible_default_tool",
                        surface="artemis_config",
                        path="artemis.yaml",
                        message=f"{mode_name} default tool {tool_id} is registered only for {sorted(modes)}",
                        remediation="Update the tool modes or remove the default from this mode.",
                    )
                )
    return findings


def _audit_active_prompt_paths(repo_root: Path) -> list[ContextAuditFinding]:
    findings: list[ContextAuditFinding] = []
    for path in _active_prompt_files(repo_root):
        relative_path = _rel(repo_root, path)
        text = path.read_text(encoding="utf-8")
        if "docs/BUILD_PACKET" in text or "docs/archive/build_packet" in text:
            findings.append(
                ContextAuditFinding(
                    severity="blocker",
                    code="stale_build_packet_reference",
                    surface="wrapper_prompt",
                    path=relative_path,
                    message="Active wrapper prompt references build-packet context.",
                    remediation="Use AGENTS.md, artemis.yaml, docs/README.md, and artemis dev context instead.",
                )
            )
        if "pga work-context" in text:
            findings.append(
                ContextAuditFinding(
                    severity="blocker",
                    code="legacy_work_context_in_active_wrapper",
                    surface="wrapper_prompt",
                    path=relative_path,
                    message="Active wrapper prompt uses pga work-context.",
                    remediation="Use artemis dev context; keep pga work-context only as a labeled compatibility alias.",
                )
            )
        for command in STALE_VALIDATION_COMMANDS:
            if command in text:
                findings.append(
                    ContextAuditFinding(
                        severity="blocker",
                        code="stale_validation_command",
                        surface="wrapper_prompt",
                        path=relative_path,
                        message=f"Active wrapper hard-codes stale validation command: {command}",
                        remediation="Use artemis validate --strict or artemis release check as the canonical validation surface.",
                    )
                )
        for match in ACTIVE_DOC_RE.finditer(text):
            referenced = match.group("path").rstrip("`.,)")
            if referenced.startswith("docs/archive/"):
                continue
            if not (repo_root / referenced).exists():
                findings.append(
                    ContextAuditFinding(
                        severity="blocker",
                        code="missing_active_reference",
                        surface="wrapper_prompt",
                        path=relative_path,
                        message=f"Active wrapper references missing path: {referenced}",
                        remediation="Create the canonical file, point to an existing active file, or move the reference to an archive-only record.",
                    )
                )
    return findings


def audit_context_surfaces(repo_root: Path) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    findings = [*_audit_default_tools(repo_root), *_audit_active_prompt_paths(repo_root)]
    blockers = [item for item in findings if item.severity == "blocker"]
    return {
        "passed": not blockers,
        "findings": [item.to_dict() for item in findings],
        "counts": {
            "findings": len(findings),
            "blockers": len(blockers),
        },
    }
