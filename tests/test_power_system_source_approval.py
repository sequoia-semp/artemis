from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pga_workbench.exceptions import WorkbenchException
from pga_workbench.registry import load_yaml_unique
from pga_workbench.services.power_system_source_approval import (
    POWER_SYSTEM_SOURCE_APPROVAL_ERROR,
    build_pjm_load_actual_feed_approval_report,
    validate_source_feed_approval_report,
)


ROOT = Path(__file__).resolve().parents[1]


def _metadata_report(*feed_ids: str) -> dict:
    return {
        "operator_id": "PJM",
        "source_system": "pjm_data_miner_api",
        "verified_feed_count": len(feed_ids),
        "verified_feeds": [
            {
                "registry_feed_id": feed_id,
                "data_miner_feed": feed_id,
                "required_field_count": 1,
                "observed_field_count": 1,
                "missing_fields": [],
            }
            for feed_id in feed_ids
        ],
        "include_candidate": True,
        "contains_secret_values": False,
    }


def _readiness_report(**row_counts: int) -> dict:
    return {
        "operator_id": "PJM",
        "source_system": "pjm_data_miner_api",
        "ready": True,
        "blockers": [],
        "source_fetches": [
            {
                "status": "success",
                "product_family": "load",
                "registry_feed_id": feed_id,
                "data_miner_feed": feed_id,
                "row_count": row_count,
                "page_count": 1,
                "truncated_by_max_pages": False,
            }
            for feed_id, row_count in row_counts.items()
        ],
        "fetch_source_rows": True,
        "contains_secret_values": False,
    }


def _approval_registry(tmp_path: Path) -> Path:
    registry_dir = tmp_path / "registries"
    registry_dir.mkdir()
    for name in ["pjm_fundamental_feeds.yaml", "power_system_source_catalog.yaml"]:
        (registry_dir / name).write_text((ROOT / "registries" / name).read_text(encoding="utf-8"), encoding="utf-8")
    feeds = load_yaml_unique(registry_dir / "pjm_fundamental_feeds.yaml")
    for feed_id in ["hrl_load_metered", "hrl_load_prelim"]:
        feeds[feed_id]["status"] = "approved_core"
        feeds[feed_id]["verification_status"] = "official_pjm_documented"
    (registry_dir / "pjm_fundamental_feeds.yaml").write_text(yaml.safe_dump(feeds, sort_keys=False), encoding="utf-8")
    catalog = load_yaml_unique(registry_dir / "power_system_source_catalog.yaml")
    catalog["PJM_DATAMINER_LOAD_ACTUALS"]["status"] = "approved_core"
    catalog["PJM_DATAMINER_LOAD_ACTUALS"]["publication_lifecycle"]["authoritative_use"] = "approved_source_surface"
    catalog["PJM_DATAMINER_LOAD_ACTUALS"]["publication_lifecycle"]["publication_finality"] = "mixed"
    (registry_dir / "power_system_source_catalog.yaml").write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
    return registry_dir


def test_pjm_load_actual_approval_report_blocks_current_candidate_feeds():
    report = build_pjm_load_actual_feed_approval_report(
        ROOT / "registries",
        metadata_verification_report=_metadata_report("hrl_load_metered", "hrl_load_prelim"),
        source_readiness_report=_readiness_report(hrl_load_metered=1, hrl_load_prelim=1),
    )

    validate_source_feed_approval_report(report, ROOT / "schemas")
    assert report["approved"] is False
    by_feed = {item["feed_id"]: item for item in report["feed_assessments"]}
    assert by_feed["hrl_load_metered"]["metadata_verified"] is True
    assert by_feed["hrl_load_metered"]["source_row_count"] == 1
    assert "feed_descriptor_not_approved_core" in by_feed["hrl_load_metered"]["blockers"]
    assert "source_publication_not_approved_core" in by_feed["hrl_load_metered"]["blockers"]
    assert "source_publication_not_authoritative" in by_feed["hrl_load_prelim"]["blockers"]


def test_pjm_load_actual_approval_report_distinguishes_metadata_from_source_rows():
    report = build_pjm_load_actual_feed_approval_report(
        ROOT / "registries",
        metadata_verification_report=_metadata_report("hrl_load_prelim"),
        source_readiness_report=_readiness_report(hrl_load_prelim=0),
        feed_ids=["hrl_load_prelim"],
    )

    assessment = report["feed_assessments"][0]
    assert assessment["metadata_verified"] is True
    assert assessment["source_row_count"] == 0
    assert "source_row_evidence_missing" in assessment["blockers"]


def test_pjm_load_actual_approval_report_can_pass_when_all_evidence_is_approved(tmp_path):
    registry_dir = _approval_registry(tmp_path)
    report = build_pjm_load_actual_feed_approval_report(
        registry_dir,
        metadata_verification_report=_metadata_report("hrl_load_metered", "hrl_load_prelim"),
        source_readiness_report=_readiness_report(hrl_load_metered=1, hrl_load_prelim=1),
    )

    validate_source_feed_approval_report(report, ROOT / "schemas")
    assert report["approved"] is True
    assert all(item["approved"] for item in report["feed_assessments"])
    assert all(item["blockers"] == [] for item in report["feed_assessments"])


def test_source_feed_approval_rejects_unredacted_evidence():
    with pytest.raises(WorkbenchException) as exc:
        build_pjm_load_actual_feed_approval_report(
            ROOT / "registries",
            metadata_verification_report={"contains_secret_values": True, "verified_feeds": []},
            source_readiness_report=_readiness_report(hrl_load_metered=1),
        )

    assert exc.value.code == POWER_SYSTEM_SOURCE_APPROVAL_ERROR
    assert "redacted" in exc.value.message
