from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.cli import artemis_main, main
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.models import PriceSurfacePoint
from pga_workbench.models import RunManifest
from pga_workbench.serialization import read_json, to_plain, write_json
from pga_workbench.services.heatmap import _history_days_from_retention_policy, build_forward_price_heatmap, validate_forward_price_heatmap
from pga_workbench.state.packs import build_candidate_state_pack, publish_candidate_state_pack


ROOT = Path(__file__).resolve().parents[1]


def _point(as_of: str, price: float) -> PriceSurfacePoint:
    return PriceSurfacePoint(
        as_of=as_of,
        index_id="PJM.WH.RT.FULL_LMP.ATC.N26",
        location_id="WH",
        commodity="power",
        period_id="N26",
        price=price,
        quote_unit="USD_per_MWh",
        source="test_marks",
        source_role="authoritative_input",
    )


def test_forward_price_heatmap_computes_standard_history_deltas():
    report = build_forward_price_heatmap(
        [
            _point("2026-05-05T12:00:00Z", 35),
            _point("2026-05-25T12:00:00Z", 45),
            _point("2026-05-30T12:00:00Z", 50),
            _point("2026-06-03T12:00:00Z", 54),
            _point("2026-06-04T12:00:00Z", 55),
        ],
        "2026-06-04",
    )
    validate_forward_price_heatmap(report, ROOT / "schemas")

    cell = report.cells[0]
    assert cell["current_price"] == 55
    assert cell["history"]["1d"]["delta"] == 1
    assert cell["history"]["5d"]["delta"] == 5
    assert cell["history"]["10d"]["delta"] == 10
    assert cell["history"]["30d"]["delta"] == 20


def test_forward_price_heatmap_history_days_can_come_from_retention_policy():
    report = build_forward_price_heatmap(
        [
            _point("2026-05-05T12:00:00Z", 35),
            _point("2026-06-04T12:00:00Z", 55),
        ],
        "2026-06-04",
        registry_dir=ROOT / "registries",
    )

    assert report.history_days == _history_days_from_retention_policy(ROOT / "registries", "pjm_power_prices")
    assert report.history_days == [1, 5, 10, 30]


def test_forward_price_heatmap_cli_paths_write_schema_valid_output(tmp_path):
    points = [
        _point("2026-06-03T12:00:00Z", 54),
        _point("2026-06-04T12:00:00Z", 55),
    ]
    input_path = tmp_path / "prices.json"
    pga_output = tmp_path / "pga_heatmap.json"
    artemis_output = tmp_path / "artemis_heatmap.json"
    write_json(input_path, points)

    assert main(["build-forward-price-heatmap", "--input", str(input_path), "--as-of", "2026-06-04", "--output", str(pga_output), "--schemas", str(ROOT / "schemas")]) == 0
    assert artemis_main(["analyst", "heatmap", "build", "--input", str(input_path), "--as-of", "2026-06-04", "--output", str(artemis_output), "--schemas", str(ROOT / "schemas")]) == 0

    assert read_json(pga_output)["cells"][0]["history"]["1d"]["delta"] == 1
    assert read_json(artemis_output)["cells"][0]["history"]["1d"]["delta"] == 1


def test_forward_price_heatmap_cli_can_read_price_points_from_hot_state(tmp_path):
    manifest = RunManifest(run_id="heatmap-state", created_at="2026-06-04T12:00:00Z", agent_pack_version="0.1.0")
    artifacts = {
        "price_surface_points": [
            to_plain(_point("2026-06-03T12:00:00Z", 54)),
            to_plain(_point("2026-06-04T12:00:00Z", 55)),
        ],
    }
    build_candidate_state_pack(tmp_path, "heatmap-state", "2026-06-04T12:00:00Z", artifacts, manifest)
    publish_candidate_state_pack(tmp_path, "heatmap-state")
    output = tmp_path / "heatmap.json"

    assert artemis_main(
        [
            "analyst",
            "heatmap",
            "build",
            "--state-root",
            str(tmp_path),
            "--as-of",
            "2026-06-04",
            "--output",
            str(output),
            "--schemas",
            str(ROOT / "schemas"),
        ]
    ) == 0

    payload = read_json(output)
    assert payload["cells"][0]["current_price"] == 55
    assert payload["cells"][0]["history"]["1d"]["delta"] == 1


def test_forward_price_heatmap_cli_requires_input_or_hot_state(tmp_path):
    with pytest.raises(WorkbenchException) as exc:
        main(["build-forward-price-heatmap", "--as-of", "2026-06-04", "--output", str(tmp_path / "heatmap.json")])

    assert exc.value.code == "HEATMAP_INPUT_REQUIRED"


def test_forward_price_heatmap_cli_parses_retention_registry_flag():
    from pga_workbench.cli import build_artemis_parser

    args = build_artemis_parser().parse_args(
        [
            "analyst",
            "heatmap",
            "build",
            "--input",
            "/tmp/prices.json",
            "--state-root",
            "/tmp/state",
            "--as-of",
            "2026-06-04",
            "--output",
            "/tmp/heatmap.json",
            "--registries",
            "registries",
        ]
    )

    assert args.registries == "registries"
    assert args.state_root == "/tmp/state"
