from __future__ import annotations

from pga_workbench.cli import artemis_main, build_artemis_parser


def test_work_cli_parses_show_validate_and_transition():
    parser = build_artemis_parser()

    assert parser.parse_args(["work", "show", "T-0030"]).func.__name__ == "_cmd_work_show"
    assert parser.parse_args(["work", "validate"]).func.__name__ == "_cmd_work_validate"
    args = parser.parse_args(["work", "transition", "T-0040", "implemented"])
    assert args.status == "implemented"


def test_work_show_cli_smoke():
    assert artemis_main(["work", "show", "T-0030"]) == 0
