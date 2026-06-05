from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ValidationStatus = Literal["passed", "failed", "skipped", "error"]


@dataclass(frozen=True)
class CommandResult:
    command: str
    returncode: int | None
    status: ValidationStatus
    duration_seconds: float | None = None
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CommandResult":
        return cls(**payload)


@dataclass(frozen=True)
class ValidationCheckResult:
    check_id: str
    label: str
    status: ValidationStatus
    required: bool
    duration_seconds: float | None
    summary: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ValidationCheckResult":
        return cls(**payload)


@dataclass(frozen=True)
class ValidationReport:
    report_id: str
    generated_at: str
    repo_root: str
    ticket_id: str | None
    strict: bool
    overall_status: ValidationStatus
    skipped: bool
    checks: list[ValidationCheckResult]
    changed_files_snapshot: list[str] | None = None
    command_results: list[CommandResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    affected_files_snapshot: list[dict[str, Any]] = field(default_factory=list)
    branch: str | None = None
    commit: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "repo_root": self.repo_root,
            "ticket_id": self.ticket_id,
            "strict": self.strict,
            "overall_status": self.overall_status,
            "skipped": self.skipped,
            "checks": [item.to_dict() for item in self.checks],
            "changed_files_snapshot": self.changed_files_snapshot,
            "command_results": [item.to_dict() for item in self.command_results],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "affected_files_snapshot": list(self.affected_files_snapshot),
            "branch": self.branch,
            "commit": self.commit,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ValidationReport":
        data = dict(payload)
        data["checks"] = [ValidationCheckResult.from_dict(item) for item in data.get("checks") or []]
        data["command_results"] = [CommandResult.from_dict(item) for item in data.get("command_results") or []]
        return cls(**data)
