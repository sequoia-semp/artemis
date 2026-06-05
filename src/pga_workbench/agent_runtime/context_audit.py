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
ARGUMENT_PLACEHOLDER_RE = re.compile(r"--(?P<arg>ticket|validation-report|input|output)\s*(?:$|\n)")
STALE_VALIDATION_COMMANDS = (
    "python -m pytest -q",
    "pga validate-registries",
    "pga validate-work-items",
)
CONVENTION_KEYWORDS = (
    "basis orientation",
    "full-lmp",
    "da/rt",
    "default-to-gdd",
    "0.25/d",
    "atc equal-mw",
    "period grammar correctness",
    "vol mvp",
)
ALLOWED_ARTEMIS_PERMISSION_COMMANDS = {
    "artemis capabilities",
    "artemis validate",
    "artemis validate report",
    "artemis context audit",
    "artemis dev context",
    "artemis release candidate",
    "artemis skill validate",
    "artemis release check",
    "artemis config validate",
    "artemis work show",
    "artemis work validate",
}
PERMISSION_ARTEMIS_COMMAND_RE = re.compile(r"""^['"]?(artemis(?:\s+[A-Za-z0-9_-]+){1,})(?:\*)?['"]?\s*:""")


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
        findings.extend(_audit_prompt_text(repo_root, relative_path, text))
    return findings


def _audit_prompt_text(repo_root: Path, relative_path: str, text: str) -> list[ContextAuditFinding]:
    findings: list[ContextAuditFinding] = []
    lower = text.lower()
    if "docs/build_packet" in lower or "docs/archive/build_packet" in lower:
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
    for match in ARGUMENT_PLACEHOLDER_RE.finditer(text):
        findings.append(
            ContextAuditFinding(
                severity="blocker",
                code="blank_required_argument",
                surface="wrapper_prompt",
                path=relative_path,
                message=f"Active wrapper contains --{match.group('arg')} without a value.",
                remediation="Use <ticket>, $ARGUMENTS, or a named shell variable for required arguments.",
            )
        )
    for keyword in CONVENTION_KEYWORDS:
        if keyword in lower:
            findings.append(
                ContextAuditFinding(
                    severity="blocker",
                    code="duplicated_convention_authority",
                    surface="wrapper_prompt",
                    path=relative_path,
                    message=f"Active wrapper restates convention authority: {keyword}",
                    remediation="Load locked conventions through Artemis context and cite canonical files instead of restating rules.",
                )
            )
    for command in _permission_artemis_commands(text):
        if command not in ALLOWED_ARTEMIS_PERMISSION_COMMANDS:
            findings.append(
                ContextAuditFinding(
                    severity="blocker",
                    code="unknown_artemis_permission_command",
                    surface="wrapper_prompt",
                    path=relative_path,
                    message=f"Wrapper permission allows an Artemis command that is not exposed: {command}",
                    remediation="Remove the permission or use an exposed Artemis command.",
                )
            )
    for line in text.splitlines():
        for match in ACTIVE_DOC_RE.finditer(line):
            referenced = match.group("path").rstrip("`.,)")
            if referenced.startswith("docs/archive/"):
                if not _archive_reference_is_historical(line):
                    findings.append(
                        ContextAuditFinding(
                            severity="blocker",
                            code="archive_authority_reference",
                            surface="wrapper_prompt",
                            path=relative_path,
                            message=f"Active wrapper treats archive path as authority: {referenced}",
                            remediation="Promote still-current guidance to an active doc or label the archive mention as historical/non-authoritative.",
                        )
                    )
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


def _archive_reference_is_historical(line: str) -> bool:
    lowered = line.lower()
    return "historical" in lowered or "non-authoritative" in lowered or "archive/design record" in lowered


def _permission_artemis_commands(text: str) -> set[str]:
    commands: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = PERMISSION_ARTEMIS_COMMAND_RE.match(line)
        if not match:
            continue
        command = match.group(1).rstrip("*").strip()
        words = command.split()
        if len(words) >= 3 and words[:2] == ["artemis", "context"]:
            commands.add(" ".join(words[:3]))
        elif len(words) >= 3 and words[:2] == ["artemis", "dev"]:
            commands.add(" ".join(words[:3]))
        elif len(words) >= 3 and words[:2] == ["artemis", "work"]:
            commands.add(" ".join(words[:3]))
        elif len(words) >= 3 and tuple(words[:2]) in {("artemis", "skill"), ("artemis", "release"), ("artemis", "config"), ("artemis", "validate")}:
            commands.add(" ".join(words[:3]))
        elif len(words) >= 2:
            commands.add(" ".join(words[:2]))
    return commands


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
