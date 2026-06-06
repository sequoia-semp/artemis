from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from pga_workbench.cache.hot_state import HotState
from pga_workbench.cli import _fetch_live_pjm_lmp, _pjm_pnode_ids_for_args, artemis_main, main
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.models import RunManifest
from pga_workbench.registry import load_yaml_unique, validate_registries
from pga_workbench.serialization import read_json
from pga_workbench.services.power_prices import (
    build_pjm_power_price_artifacts,
    normalize_pjm_lmp_records,
    normalize_pjm_pnode_records,
    pjm_lmp_observations_to_price_surface_points,
    validate_power_system_price_feed_contracts,
    validate_power_price_state,
    verify_pjm_location_pnodes,
)
from pga_workbench.services.power_system_locations import approved_pjm_location_pnode_ids, validate_power_location_source_identity_references
from pga_workbench.state.packs import build_candidate_state_pack, publish_candidate_state_pack


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "pjm_lmp_prices_minimal.json"
PNODE_FIXTURE = ROOT / "tests" / "fixtures" / "pjm_pnodes_wh_ad_ni.json"


def _load_normalized():
    payload = read_json(FIXTURE)
    feeds = payload["feeds"]
    pnodes = normalize_pjm_pnode_records(feeds["pnode"], ROOT / "registries")
    observations = []
    observations.extend(normalize_pjm_lmp_records("PJM_DA_HOURLY_LMP", feeds["da_hrl_lmps"], ROOT / "registries", as_of="2026-06-01"))
    observations.extend(normalize_pjm_lmp_records("PJM_RT_HOURLY_LMP", feeds["rt_hrl_lmps"], ROOT / "registries", as_of="2026-06-01"))
    return pnodes, observations


def test_power_system_price_feed_registry_validates():
    result = validate_registries(ROOT / "registries", ROOT / "schemas")

    assert "power_system_price_feeds.yaml" in result.validated_files
    assert result.warnings == []
    feeds = load_yaml_unique(ROOT / "registries" / "power_system_price_feeds.yaml")
    assert set(feeds) >= {"PJM_PNODE", "PJM_DA_HOURLY_LMP", "PJM_RT_HOURLY_LMP"}
    assert feeds["PJM_DA_HOURLY_LMP"]["supported_price_components"] == ["FULL_LMP", "CONGESTION", "MARGINAL_LOSS", "SYSTEM_ENERGY"]
    assert feeds["PJM_RT_HOURLY_LMP"]["supported_price_components"] == ["FULL_LMP", "CONGESTION", "MARGINAL_LOSS", "SYSTEM_ENERGY"]
    assert feeds["PJM_DA_HOURLY_LMP"]["source_components"] == ["FULL_LMP", "CONGESTION", "MARGINAL_LOSS", "SYSTEM_ENERGY"]
    assert feeds["PJM_DA_HOURLY_LMP"]["source_product_contract"]["version_policy"] == "current_row_filter_required"
    assert feeds["PJM_RT_FIVE_MINUTE_LMP"]["status"] == "candidate"
    assert feeds["PJM_RT_FIVE_MINUTE_LMP"]["granularity"] == "five_minute"
    assert feeds["PJM_RT_FIVE_MINUTE_LMP"]["source_product_contract"]["canonical_promotion_policy"] == "candidate_not_promotable"


def _copy_price_contract_registries(tmp_path: Path) -> Path:
    registry_dir = tmp_path / "registries"
    registry_dir.mkdir()
    for name in ["power_system_price_feeds.yaml", "power_locations.yaml"]:
        (registry_dir / name).write_text((ROOT / "registries" / name).read_text(encoding="utf-8"), encoding="utf-8")
    return registry_dir


def test_power_system_price_feed_contracts_validate():
    result = validate_power_system_price_feed_contracts(ROOT / "registries")

    assert result["metadata_feeds"] == ["PJM_PNODE"]
    assert result["approved_lmp_feeds"] == ["PJM_DA_HOURLY_LMP", "PJM_RT_HOURLY_LMP"]


def test_power_location_source_identity_references_validate_approved_pjm_pnodes():
    resolved = validate_power_location_source_identity_references(ROOT / "registries")

    assert resolved["WH"] == {
        "operator_id": "PJM",
        "source_identity_policy": "official_pjm_data_miner_pnode_required",
        "pnode_id": 51288,
        "pnode_name": "WESTERN HUB",
        "pnode_type": "HUB",
        "pnode_source_status": "official_pjm_data_miner_verified",
    }
    assert {key for key in resolved} >= {"WH", "AD", "NI"}


def test_approved_pjm_location_pnode_ids_resolve_for_live_price_queries():
    approved = approved_pjm_location_pnode_ids(ROOT / "registries")

    assert approved[51288] == "WH"
    assert approved[34497127] == "AD"
    assert approved[33092315] == "NI"


def _copy_power_location_registries(tmp_path: Path) -> Path:
    registry_dir = tmp_path / "registries"
    registry_dir.mkdir()
    (registry_dir / "power_locations.yaml").write_text((ROOT / "registries" / "power_locations.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    return registry_dir


def test_approved_pjm_power_location_without_verified_pnode_status_fails_closed(tmp_path):
    registry_dir = _copy_power_location_registries(tmp_path)
    locations = load_yaml_unique(registry_dir / "power_locations.yaml")
    locations["WH"]["pnode_source_status"] = "candidate"
    (registry_dir / "power_locations.yaml").write_text(yaml.safe_dump(locations, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_location_source_identity_references(registry_dir)

    assert exc.value.code == "POWER_SYSTEM_LOCATION_ERROR"
    assert "official_pjm_data_miner_verified" in exc.value.message


def test_duplicate_approved_pjm_power_location_pnode_mapping_fails_closed(tmp_path):
    registry_dir = _copy_power_location_registries(tmp_path)
    locations = load_yaml_unique(registry_dir / "power_locations.yaml")
    locations["AD"]["pjm_pnode_id"] = locations["WH"]["pjm_pnode_id"]
    (registry_dir / "power_locations.yaml").write_text(yaml.safe_dump(locations, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_location_source_identity_references(registry_dir)

    assert exc.value.code == "POWER_SYSTEM_LOCATION_ERROR"
    assert "maps to multiple approved power locations" in exc.value.message


def test_approved_lmp_feed_without_current_row_filter_fails_closed(tmp_path):
    registry_dir = _copy_price_contract_registries(tmp_path)
    feeds = load_yaml_unique(registry_dir / "power_system_price_feeds.yaml")
    feeds["PJM_DA_HOURLY_LMP"]["required_filters"].pop("row_is_current")
    (registry_dir / "power_system_price_feeds.yaml").write_text(yaml.safe_dump(feeds, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_price_feed_contracts(registry_dir)

    assert exc.value.code == "POWER_PRICE_ERROR"
    assert "row_is_current required filter" in exc.value.message


def test_approved_lmp_feed_without_component_contract_fails_closed(tmp_path):
    registry_dir = _copy_price_contract_registries(tmp_path)
    feeds = load_yaml_unique(registry_dir / "power_system_price_feeds.yaml")
    feeds["PJM_RT_HOURLY_LMP"]["source_product_contract"]["component_policy"] = "not_applicable"
    (registry_dir / "power_system_price_feeds.yaml").write_text(yaml.safe_dump(feeds, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_price_feed_contracts(registry_dir)

    assert exc.value.code == "POWER_PRICE_ERROR"
    assert "component_policy" in exc.value.message


def test_approved_lmp_feed_without_full_component_columns_fails_closed(tmp_path):
    registry_dir = _copy_price_contract_registries(tmp_path)
    feeds = load_yaml_unique(registry_dir / "power_system_price_feeds.yaml")
    feeds["PJM_DA_HOURLY_LMP"]["source_components"].remove("SYSTEM_ENERGY")
    (registry_dir / "power_system_price_feeds.yaml").write_text(yaml.safe_dump(feeds, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_price_feed_contracts(registry_dir)

    assert exc.value.code == "POWER_PRICE_ERROR"
    assert "full source component coverage" in exc.value.message


def test_pjm_pnode_fixture_verifies_existing_power_location_mapping():
    pnodes, _observations = _load_normalized()
    verified = verify_pjm_location_pnodes(pnodes, ROOT / "registries", as_of="2026-06-01")

    assert verified["WH"]["pnode_id"] == 51288
    assert verified["WH"]["pnode_subtype"] == "HUB"
    assert verified["WH"]["effective_as_of"] == "2026-06-01T00:00:00Z"
    assert verified["WH"]["verification_status"] == "official_pjm_data_miner_verified"


def test_pjm_pnode_fixture_verifies_all_approved_power_locations():
    payload = read_json(PNODE_FIXTURE)
    pnodes = normalize_pjm_pnode_records(payload["feeds"]["pnode"], ROOT / "registries")
    verified = verify_pjm_location_pnodes(pnodes, ROOT / "registries", as_of="2026-06-01")
    locations = load_yaml_unique(ROOT / "registries" / "power_locations.yaml")

    assert {
        location_id: (record["pnode_id"], record["pnode_name"], record["pnode_subtype"])
        for location_id, record in verified.items()
    } == {
        "WH": (51288, "WESTERN HUB", "HUB"),
        "AD": (34497127, "AEP-DAYTON HUB", "HUB"),
        "NI": (33092315, "N ILLINOIS HUB", "HUB"),
    }
    assert {locations[key]["pnode_source_status"] for key in ["WH", "AD", "NI"]} == {"official_pjm_data_miner_verified"}


def test_pjm_pnode_effective_date_must_cover_price_state_as_of():
    pnodes, observations = _load_normalized()
    expired = [replace(pnodes[0], effective_end="2020-01-01T00:00:00Z")]

    with pytest.raises(WorkbenchException) as exc:
        build_pjm_power_price_artifacts(expired, observations, "2026-06-01", ROOT / "registries")

    assert exc.value.code == "POWER_PRICE_ERROR"
    assert "not effective" in exc.value.message


def test_pjm_lmp_rows_normalize_to_source_observations_and_hourly_full_lmp_points():
    _pnodes, observations = _load_normalized()

    assert {item.market_run for item in observations} == {"DA", "RT"}
    assert all(item.delivery_start == "2026-06-01T04:00:00Z" for item in observations)
    assert all(item.delivery_end == "2026-06-01T05:00:00Z" for item in observations)
    da = next(item for item in observations if item.market_run == "DA")
    assert da.total_lmp == 23.620301
    assert da.congestion_price == -0.644396

    points = pjm_lmp_observations_to_price_surface_points(observations, ROOT / "registries")
    assert {point.index_id for point in points} == {
        "PJM.WH.DA.FULL_LMP.HOURLY.HOUR_20260601T040000Z",
        "PJM.WH.DA.CONGESTION.HOURLY.HOUR_20260601T040000Z",
        "PJM.WH.DA.MARGINAL_LOSS.HOURLY.HOUR_20260601T040000Z",
        "PJM.WH.DA.SYSTEM_ENERGY.HOURLY.HOUR_20260601T040000Z",
        "PJM.WH.RT.FULL_LMP.HOURLY.HOUR_20260601T040000Z",
        "PJM.WH.RT.CONGESTION.HOURLY.HOUR_20260601T040000Z",
        "PJM.WH.RT.MARGINAL_LOSS.HOURLY.HOUR_20260601T040000Z",
        "PJM.WH.RT.SYSTEM_ENERGY.HOURLY.HOUR_20260601T040000Z",
    }
    assert all(point.source_role == "authoritative_iso_publication" for point in points)
    components = {point.lineage["price_component"]: point.price for point in points if point.index_id.startswith("PJM.WH.DA.")}
    assert components == {
        "FULL_LMP": 23.620301,
        "CONGESTION": -0.644396,
        "MARGINAL_LOSS": 0.424697,
        "SYSTEM_ENERGY": 23.84,
    }
    assert all(point.lineage["source_component_values"]["FULL_LMP"] is not None for point in points)


def test_pjm_lmp_delivery_start_must_align_to_utc_hour():
    payload = read_json(FIXTURE)
    row = dict(payload["feeds"]["da_hrl_lmps"][0])
    row["datetime_beginning_utc"] = "2026-06-01T04:30:00"

    with pytest.raises(WorkbenchException) as exc:
        normalize_pjm_lmp_records("PJM_DA_HOURLY_LMP", [row], ROOT / "registries", as_of="2026-06-01")

    assert exc.value.code == "POWER_PRICE_ERROR"
    assert "exact UTC hour" in exc.value.message


def test_pjm_lmp_delivery_start_ept_must_match_utc_instant():
    payload = read_json(FIXTURE)
    row = dict(payload["feeds"]["da_hrl_lmps"][0])
    row["datetime_beginning_ept"] = "2026-06-01T01:00:00"

    with pytest.raises(WorkbenchException) as exc:
        normalize_pjm_lmp_records("PJM_DA_HOURLY_LMP", [row], ROOT / "registries", as_of="2026-06-01")

    assert exc.value.code == "POWER_PRICE_ERROR"
    assert "does not match PJM EPT timestamp" in exc.value.message


def test_pjm_lmp_delivery_start_ept_matches_winter_utc_offset():
    payload = read_json(FIXTURE)
    row = dict(payload["feeds"]["rt_hrl_lmps"][0])
    row["datetime_beginning_utc"] = "2026-01-15T05:00:00"
    row["datetime_beginning_ept"] = "2026-01-15T00:00:00"

    observations = normalize_pjm_lmp_records("PJM_RT_HOURLY_LMP", [row], ROOT / "registries", as_of="2026-01-15")

    assert observations[0].delivery_start == "2026-01-15T05:00:00Z"
    assert observations[0].lineage["delivery_start_ept"] == "2026-01-15T00:00:00"


def test_pjm_lmp_non_current_rows_fail_closed():
    payload = read_json(FIXTURE)
    row = dict(payload["feeds"]["da_hrl_lmps"][0])
    row["row_is_current"] = False

    with pytest.raises(WorkbenchException) as exc:
        normalize_pjm_lmp_records("PJM_DA_HOURLY_LMP", [row], ROOT / "registries", as_of="2026-06-01")

    assert exc.value.code == "POWER_PRICE_ERROR"


def test_candidate_five_minute_lmp_feed_cannot_be_normalized():
    payload = read_json(FIXTURE)
    row = dict(payload["feeds"]["rt_hrl_lmps"][0])

    with pytest.raises(WorkbenchException) as exc:
        normalize_pjm_lmp_records("PJM_RT_FIVE_MINUTE_LMP", [row], ROOT / "registries", as_of="2026-06-01")

    assert exc.value.code == "POWER_PRICE_ERROR"
    assert "not approved" in exc.value.message


def test_supported_lmp_component_missing_value_fails_closed():
    payload = read_json(FIXTURE)
    row = dict(payload["feeds"]["da_hrl_lmps"][0])
    row["congestion_price_da"] = ""
    observations = normalize_pjm_lmp_records("PJM_DA_HOURLY_LMP", [row], ROOT / "registries", as_of="2026-06-01")

    with pytest.raises(WorkbenchException) as exc:
        pjm_lmp_observations_to_price_surface_points(observations, ROOT / "registries")

    assert exc.value.code == "POWER_PRICE_ERROR"
    assert "CONGESTION" in exc.value.message


def test_unknown_pjm_pnode_cannot_be_promoted_to_canonical_price_surface():
    _pnodes, observations = _load_normalized()
    unsupported = [replace(observations[0], pnode_id=999999)]

    with pytest.raises(WorkbenchException) as exc:
        pjm_lmp_observations_to_price_surface_points(unsupported, ROOT / "registries")

    assert exc.value.code == "UNKNOWN_PJM_PNODE"


def test_pjm_power_price_artifacts_validate_and_publish_to_hot_state(tmp_path):
    pnodes, observations = _load_normalized()
    artifacts = build_pjm_power_price_artifacts(pnodes, observations, "2026-06-01", ROOT / "registries", run_id="pjm-prices-test")

    validate_power_price_state(artifacts["pjm_power_prices"], ROOT / "schemas")
    assert len(artifacts["price_surface_points"]) == 8
    assert artifacts["pjm_power_prices"]["lineage"]["pnode_verifications"]["WH"]["pnode_id"] == 51288

    manifest = RunManifest(run_id="pjm-prices-test", created_at="2026-06-01T12:00:00Z", agent_pack_version="0.1.0")
    build_candidate_state_pack(tmp_path, "pjm-prices-test", "2026-06-01T12:00:00Z", artifacts, manifest)
    publish_candidate_state_pack(tmp_path, "pjm-prices-test")

    hot = HotState(tmp_path).artifacts()
    assert hot["price_surface_points"][0]["source"] == "PJM Data Miner"
    assert hot["pjm_power_prices"]["lineage"]["price_surface_point_count"] == 8


def test_pjm_lmp_cli_builds_artifacts_from_fixture(tmp_path):
    output = tmp_path / "pjm_prices.json"

    assert main(
        [
            "build-pjm-lmp-prices",
            "--input",
            str(FIXTURE),
            "--as-of",
            "2026-06-01",
            "--start",
            "2026-06-01",
            "--end",
            "2026-06-01",
            "--output",
            str(output),
        ]
    ) == 0

    assert read_json(output)["pjm_power_prices"]["lineage"]["price_surface_point_count"] == 8


def test_artemis_pjm_lmp_cli_alias_and_bounded_live_flags_parse(tmp_path):
    output = tmp_path / "pjm_prices.json"

    assert artemis_main(
        [
            "analyst",
            "prices",
            "build-pjm-lmp",
            "--input",
            str(FIXTURE),
            "--as-of",
            "2026-06-01",
            "--start",
            "2026-06-01",
            "--end",
            "2026-06-01",
            "--output",
            str(output),
        ]
    ) == 0

    from pga_workbench.cli import build_artemis_parser

    parser = build_artemis_parser()
    args = parser.parse_args(
        [
            "analyst",
            "prices",
            "build-pjm-lmp",
            "--live",
            "--location",
            "WH",
            "--feed",
            "PJM_RT_HOURLY_LMP",
            "--as-of",
            "2026-06-01",
            "--start",
            "2026-06-01",
            "--end",
            "2026-06-01",
            "--output",
            "/tmp/pjm_prices.json",
            "--row-count",
            "24",
            "--max-pages",
            "1",
            "--no-paginate",
        ]
    )

    assert args.location == ["WH"]
    assert args.feed == ["PJM_RT_HOURLY_LMP"]
    assert args.row_count == 24
    assert args.no_paginate is True


def test_live_pjm_lmp_fetch_uses_daily_query_plan(monkeypatch):
    from argparse import Namespace
    from pga_workbench.data.contracts import DataResult

    seen = []

    def fake_fetch(self, request):
        seen.append(dict(request.parameters))
        feed = request.parameters["feed"]
        if feed == "pnode":
            return DataResult(
                source="PJM Data Miner",
                contract="pnode",
                data_environment="test",
                records=read_json(PNODE_FIXTURE)["feeds"]["pnode"][:1],
                lineage={},
            )
        return DataResult(source="PJM Data Miner", contract=str(feed), data_environment="test", records=[], lineage={})

    monkeypatch.setattr("pga_workbench.cli.load_artemis_config", lambda *_args, **_kwargs: object())
    monkeypatch.setattr("pga_workbench.cli.PjmDataMinerConnector.fetch", fake_fetch)

    args = Namespace(
        repo_root=".",
        base_url="https://example.test",
        as_of="2026-06-01",
        start="2026-06-01",
        end="2026-06-02",
        location=["WH"],
        pnode_id=[],
        feed=["PJM_RT_HOURLY_LMP"],
        row_count=24,
        no_paginate=True,
        max_pages=1,
    )

    _pnodes, observations = _fetch_live_pjm_lmp(args, ROOT / "registries")

    lmp_queries = [item["query"] for item in seen if item["feed"] == "rt_hrl_lmps"]
    assert observations == []
    assert len(lmp_queries) == 2
    assert [query["datetime_beginning_utc"] for query in lmp_queries] == [
        "2026-06-01 00:00:00 to 2026-06-01 23:59:59",
        "2026-06-02 00:00:00 to 2026-06-02 23:59:59",
    ]
    assert all(item["query_plan"]["plan_id"] == "PJM_DATAMINER_HOURLY_LMP_DAILY_CHUNKS" for item in seen if item["feed"] == "rt_hrl_lmps")
    assert [item["query_request"]["request_id"] for item in seen if item["feed"] == "rt_hrl_lmps"] == [
        "PJM_DATAMINER_HOURLY_LMP_DAILY_CHUNKS.PJM_RT_HOURLY_LMP.51288.2026-06-01",
        "PJM_DATAMINER_HOURLY_LMP_DAILY_CHUNKS.PJM_RT_HOURLY_LMP.51288.2026-06-02",
    ]
    assert all(item["query_execution_summary"]["contains_secret_values"] is False for item in seen)


def test_live_pjm_lmp_fetch_rejects_over_budget_non_member_plan(monkeypatch):
    from argparse import Namespace

    monkeypatch.setattr("pga_workbench.cli.load_artemis_config", lambda *_args, **_kwargs: object())

    args = Namespace(
        repo_root=".",
        base_url="https://example.test",
        as_of="2026-06-01",
        start="2026-06-01",
        end="2026-06-03",
        location=["WH"],
        pnode_id=[],
        feed=["PJM_DA_HOURLY_LMP", "PJM_RT_HOURLY_LMP"],
        row_count=24,
        no_paginate=True,
        max_pages=1,
    )

    with pytest.raises(WorkbenchException) as exc:
        _fetch_live_pjm_lmp(args, ROOT / "registries")

    assert exc.value.code == "SOURCE_QUERY_PLAN_ERROR"


def test_live_pjm_lmp_raw_pnode_ids_must_be_approved_power_locations():
    from argparse import Namespace

    args = Namespace(pnode_id=["999999"], location=[])

    with pytest.raises(WorkbenchException) as exc:
        _pjm_pnode_ids_for_args(args, ROOT / "registries")

    assert exc.value.code == "UNKNOWN_PJM_PNODE"


def test_live_pjm_lmp_raw_approved_pnode_ids_are_allowed():
    from argparse import Namespace

    args = Namespace(pnode_id=["51288"], location=[])

    assert _pjm_pnode_ids_for_args(args, ROOT / "registries") == [51288]
