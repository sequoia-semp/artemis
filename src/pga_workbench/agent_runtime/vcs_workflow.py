from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from .capabilities import collect_agent_doctor
from .work_item_loader import load_ticket


def _run_git(repo_root: Path, args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True)
    return {
        "command": "git " + " ".join(args),
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "passed": completed.returncode == 0,
    }


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "work"


def standard_branch_name(ticket: dict[str, Any], prefix: str = "codex") -> str:
    title = str(ticket.get("title") or ticket.get("id") or "work")
    return f"{prefix}/{ticket['id']}-{_slugify(title)}"


def standard_vcs_commands(ticket: dict[str, Any], branch: str, target_branch: str, remote: str) -> list[str]:
    ticket_id = str(ticket["id"])
    message = f"{ticket_id}: {ticket.get('title', 'standardized work')}"
    return [
        f"git switch -c {branch}",
        "make validate",
        f"pga vcs-ready --ticket {ticket_id}",
        "git status --short",
        "git add <changed-files>",
        f'git commit -m "{message}"',
        f"git push -u {remote} {branch}",
        f"merge {branch} into {target_branch} after review",
    ]


def collect_vcs_readiness(
    repo_root: Path,
    ticket_id: str,
    target_branch: str = "main",
    remote: str = "origin",
    skip_tests: bool = False,
) -> dict[str, Any]:
    repo_root = Path(repo_root)
    ticket = load_ticket(repo_root / "work", ticket_id)
    expected_branch = str(ticket.get("branch") or standard_branch_name(ticket))

    branch_result = _run_git(repo_root, ["branch", "--show-current"])
    current_branch = branch_result["stdout"] if branch_result["passed"] else ""
    status_result = _run_git(repo_root, ["status", "--short"])
    status_lines = [line for line in status_result["stdout"].splitlines() if line]
    upstream_result = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    remote_result = _run_git(repo_root, ["remote", "get-url", remote])

    doctor = collect_agent_doctor(repo_root, skip_tests=skip_tests)
    on_target_branch = current_branch == target_branch
    branch_has_ticket = ticket_id in current_branch
    expected_branch_match = current_branch == expected_branch
    has_uncommitted_changes = bool(status_lines)
    validation_passed = bool(doctor.get("passed"))
    ready_for_commit = validation_passed and branch_has_ticket and not on_target_branch
    ready_for_merge = ready_for_commit and not has_uncommitted_changes

    warnings: list[str] = []
    if on_target_branch:
        warnings.append(f"current branch is {target_branch}; create a ticket branch before committing")
    if not branch_has_ticket:
        warnings.append(f"current branch does not include ticket id {ticket_id}")
    if has_uncommitted_changes:
        warnings.append("working tree has uncommitted changes; commit before merge")
    if not validation_passed:
        warnings.append("validation checks did not pass")

    return {
        "ticket_id": ticket_id,
        "ticket_status": ticket.get("status"),
        "target_branch": target_branch,
        "remote": remote,
        "remote_url": remote_result["stdout"] if remote_result["passed"] else None,
        "current_branch": current_branch,
        "upstream": upstream_result["stdout"] if upstream_result["passed"] else None,
        "expected_branch": expected_branch,
        "branch_has_ticket": branch_has_ticket,
        "expected_branch_match": expected_branch_match,
        "on_target_branch": on_target_branch,
        "has_uncommitted_changes": has_uncommitted_changes,
        "changed_paths": status_lines,
        "validation_passed": validation_passed,
        "doctor": doctor,
        "ready_for_commit": ready_for_commit,
        "ready_for_merge": ready_for_merge,
        "warnings": warnings,
        "standard_commands": standard_vcs_commands(ticket, expected_branch, target_branch, remote),
    }
