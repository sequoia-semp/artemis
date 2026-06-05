from __future__ import annotations

from pathlib import Path

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
