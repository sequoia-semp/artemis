from __future__ import annotations

from pathlib import Path

from pga_workbench.agent_runtime.release_workflow import collect_release_readiness
from pga_workbench.cli import build_parser, main


ROOT = Path(__file__).resolve().parents[1]


def test_release_readiness_reports_package_and_planning_bridge():
    result = collect_release_readiness(ROOT, ticket_id="T-0017", skip_tests=True)

    assert result["package"]["name"] == "pga-workbench"
    assert result["package"]["version"] == "0.2.0"
    assert result["package"]["requires_python"] == ">=3.11"
    assert result["ticket"]["id"] == "T-0017"
    assert result["planning_bridge"]["docs/archive/pjm_workbench_mvp_agent_spec.md"] is True
    assert result["planning_bridge"]["work/backlog/pjm_workbench_mvp_backlog.yaml"] is True
    assert "artemis capabilities" in result["validation_commands"]
    assert all(item["skipped"] for item in result["validation_results"])
    assert result["validation_skipped"] is True
    assert result["validation_passed"] is False
    assert "tests run" in result["required_release_note_fields"]
    assert result["ready_for_release_prep"] is False


def test_cli_exposes_release_check_command():
    parser = build_parser()
    args = parser.parse_args(["release-check", "--ticket", "T-0017", "--skip-tests"])
    assert args.ticket == "T-0017"
    assert args.skip_tests is True


def test_release_check_cli_smoke():
    assert main(["release-check", "--ticket", "T-0017", "--skip-tests"]) == 0
