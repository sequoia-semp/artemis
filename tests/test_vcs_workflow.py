from __future__ import annotations

from pathlib import Path

from pga_workbench.agent_runtime.vcs_workflow import collect_vcs_readiness, standard_branch_name


ROOT = Path(__file__).resolve().parents[1]


def test_standard_branch_name_uses_codex_ticket_prefix():
    ticket = {"id": "T-0010", "title": "Standardize local dev environment and VCS readiness workflow"}
    assert standard_branch_name(ticket) == "codex/T-0010-standardize-local-dev-environment-and-vcs-readiness-workflow"


def test_vcs_readiness_reports_ticket_branch_and_standard_commands():
    readiness = collect_vcs_readiness(ROOT, "T-0010", skip_tests=True)
    assert readiness["ticket_id"] == "T-0010"
    assert readiness["target_branch"] == "main"
    assert "T-0010" in readiness["expected_branch"]
    assert readiness["doctor"]["passed"] is True
    assert any(command == "make validate" for command in readiness["standard_commands"])
    assert any(command.startswith("git push -u origin") for command in readiness["standard_commands"])
