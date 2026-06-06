from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pga_workbench.cli import artemis_main, build_artemis_parser, main
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.registry import load_yaml_unique, validate_registries
from pga_workbench.serialization import read_json
from pga_workbench.services.power_system_operational_events import (
    POWER_SYSTEM_OPERATIONAL_EVENT_ERROR,
    approved_operational_event_feeds,
    build_operational_event_candidate_plan,
    load_power_system_operational_event_feeds,
    validate_operational_event_candidate_plan,
)
from pga_workbench.services.power_system_operators import validate_power_system_operator_references
from pga_workbench.services.power_system_sources import (
    POWER_SYSTEM_SOURCE_ERROR,
    validate_power_system_source_catalog_references,
)


ROOT = Path(__file__).resolve().parents[1]


def test_power_system_operational_event_feed_registry_validates_without_warnings():
    result = validate_registries(ROOT / "registries", ROOT / "schemas")
    feeds = load_power_system_operational_event_feeds(ROOT / "registries")

    assert "power_system_operational_event_feeds.yaml" in result.validated_files
    assert result.warnings == []
    assert set(feeds) == {
        "PJM_FRCSTD_GEN_OUTAGES",
        "PJM_DA_TRANSCONSTRAINTS",
        "PJM_RT_TRANSN_CONSTRAINTS",
    }
    assert {record["status"] for record in feeds.values()} == {"candidate"}
    assert {record["topology_linkage"] for record in feeds.values()} == {"not_approved"}


def test_operational_event_source_catalog_references_resolve_to_candidate_descriptors():
    resolved = validate_power_system_source_catalog_references(ROOT / "registries")
    operator_refs = validate_power_system_operator_references(ROOT / "registries")

    assert resolved["PJM_DATAMINER_OUTAGES"] == ["PJM_FRCSTD_GEN_OUTAGES"]
    assert resolved["PJM_DATAMINER_TRANSMISSION_CONSTRAINTS"] == [
        "PJM_DA_TRANSCONSTRAINTS",
        "PJM_RT_TRANSN_CONSTRAINTS",
    ]
    assert "power_system_operational_event_feeds.yaml:PJM_FRCSTD_GEN_OUTAGES" in operator_refs["PJM"]


def test_operational_event_feeds_have_no_approved_normalized_products():
    assert approved_operational_event_feeds(ROOT / "registries") == {}


def test_operational_event_candidate_plan_reports_blockers_without_publish_authority():
    plan = build_operational_event_candidate_plan(ROOT / "registries")

    validate_operational_event_candidate_plan(plan, ROOT / "schemas")
    assert plan["approved"] is False
    assert plan["publication_count"] == 2
    assert plan["feed_count"] == 3
    by_publication = {item["publication_id"]: item for item in plan["publications"]}
    outages = by_publication["PJM_DATAMINER_OUTAGES"]
    assert outages["authoritative_use"] == "candidate_not_publishable"
    assert "source_publication_not_approved_core" in outages["blockers"]
    assert "source_publication_not_authoritative" in outages["blockers"]
    assert outages["feeds"][0]["feed_id"] == "PJM_FRCSTD_GEN_OUTAGES"
    assert "timestamp_policy_pending" in outages["feeds"][0]["blockers"]
    assert "topology_linkage_not_approved" in outages["feeds"][0]["blockers"]
    constraints = by_publication["PJM_DATAMINER_TRANSMISSION_CONSTRAINTS"]
    assert {item["feed_id"] for item in constraints["feeds"]} == {
        "PJM_DA_TRANSCONSTRAINTS",
        "PJM_RT_TRANSN_CONSTRAINTS",
    }


def test_operational_event_source_catalog_unknown_descriptor_fails_closed(tmp_path):
    registry_dir = tmp_path / "registries"
    registry_dir.mkdir()
    for name in [
        "pjm_fundamental_feeds.yaml",
        "power_system_price_feeds.yaml",
        "power_generation_mix_feeds.yaml",
        "power_system_operational_event_feeds.yaml",
        "power_system_source_catalog.yaml",
    ]:
        (registry_dir / name).write_text((ROOT / "registries" / name).read_text(encoding="utf-8"), encoding="utf-8")

    catalog = load_yaml_unique(registry_dir / "power_system_source_catalog.yaml")
    catalog["PJM_DATAMINER_OUTAGES"]["registry_feed_ids"] = ["PJM_UNKNOWN_OPERATIONAL_EVENT"]
    (registry_dir / "power_system_source_catalog.yaml").write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_source_catalog_references(registry_dir)

    assert exc.value.code == POWER_SYSTEM_SOURCE_ERROR
    assert "PJM_UNKNOWN_OPERATIONAL_EVENT" in exc.value.message


def test_operational_event_approved_status_requires_approved_normalization(tmp_path):
    registry_dir = tmp_path / "registries"
    registry_dir.mkdir()
    (registry_dir / "power_system_operational_event_feeds.yaml").write_text(
        (ROOT / "registries" / "power_system_operational_event_feeds.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    feeds = load_yaml_unique(registry_dir / "power_system_operational_event_feeds.yaml")
    feeds["PJM_FRCSTD_GEN_OUTAGES"]["status"] = "approved_core"
    (registry_dir / "power_system_operational_event_feeds.yaml").write_text(yaml.safe_dump(feeds, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        approved_operational_event_feeds(registry_dir)

    assert exc.value.code == POWER_SYSTEM_OPERATIONAL_EVENT_ERROR
    assert "approved normalization status" in exc.value.message


def test_pjm_operational_event_plan_cli_writes_validated_candidate_report(tmp_path):
    output = tmp_path / "operational_event_plan.json"

    assert main(["pjm-operational-event-plan", "--output", str(output)]) == 0

    plan = read_json(output)
    validate_operational_event_candidate_plan(plan, ROOT / "schemas")
    assert plan["operator_id"] == "PJM"
    assert plan["approved"] is False
    assert plan["contains_secret_values"] is False
    assert plan["publication_count"] == 2


def test_pjm_operational_event_plan_cli_can_require_approval(tmp_path):
    output = tmp_path / "operational_event_plan.json"

    assert main(["pjm-operational-event-plan", "--output", str(output), "--require-approved"]) == 1
    assert read_json(output)["approved"] is False


def test_artemis_parser_exposes_pjm_operational_event_plan():
    parser = build_artemis_parser()
    args = parser.parse_args(["data-sources", "pjm-operational-event-plan"])

    assert args.func.__name__ == "_cmd_pjm_operational_event_candidate_plan"


def test_artemis_pjm_operational_event_plan_cli_smoke(tmp_path):
    output = tmp_path / "artemis_operational_event_plan.json"

    assert artemis_main(["data-sources", "pjm-operational-event-plan", "--output", str(output)]) == 0
    assert read_json(output)["feed_count"] == 3
