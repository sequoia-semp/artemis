from __future__ import annotations

from pathlib import Path
from datetime import date

import pytest

from pga_workbench.cli import artemis_main, build_artemis_parser, build_parser, main


ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_exposes_artemis_console_script_alias():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'pga = "pga_workbench.cli:main"' in text
    assert 'artemis = "pga_workbench.cli:artemis_main"' in text
    assert 'version = "0.2.0"' in text


def test_cli_parses_artemis_style_commands():
    parser = build_parser()
    args = parser.parse_args(["config", "validate"])
    assert args.func.__name__ == "_cmd_artemis_config_validate"

    args = parser.parse_args(["analyst", "view", "build", "--template", "current-day", "--input", "in.json", "--output", "out.json"])
    assert args.template == "current-day"


def test_artemis_config_validate_cli_smoke():
    assert artemis_main(["config", "validate"]) == 0


def test_existing_pga_parse_period_command_still_works():
    assert main(["parse-period", "N26", "--commodity", "power"]) == 0


def test_artemis_parser_excludes_lower_level_state_publish_commands():
    parser = build_artemis_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["build-state-pack", "--publish"])


def test_artemis_release_check_json_serializes_yaml_dates(monkeypatch, capsys):
    monkeypatch.setattr(
        "pga_workbench.cli.collect_release_readiness",
        lambda *args, **kwargs: {
            "package": {"name": "pga-workbench", "version": "0.2.0", "requires_python": ">=3.11"},
            "ticket": {"id": "T-0036", "created_at": date(2026, 6, 5)},
            "ready_for_release_prep": False,
            "blockers": ["dry_run"],
            "warnings": [],
            "validation_skipped": True,
            "validation_passed": False,
        },
    )

    assert artemis_main(["release", "check", "--ticket", "T-0036", "--json"]) == 1
    assert '"created_at": "2026-06-05"' in capsys.readouterr().out
