from __future__ import annotations

from pathlib import Path

from pga_workbench.cli import artemis_main, main
from pga_workbench.models import PriceSurfacePoint
from pga_workbench.serialization import read_json, write_json
from pga_workbench.services.heatmap import build_forward_price_heatmap, validate_forward_price_heatmap


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
