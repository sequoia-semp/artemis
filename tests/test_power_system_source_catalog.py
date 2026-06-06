from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pga_workbench.exceptions import WorkbenchException
from pga_workbench.registry import load_yaml_unique, validate_registries
from pga_workbench.services.power_system_sources import (
    POWER_SYSTEM_SOURCE_ERROR,
    load_power_system_source_catalog,
    source_publication_lifecycle_summary,
    validate_power_system_source_catalog_references,
)


ROOT = Path(__file__).resolve().parents[1]


def test_power_system_source_catalog_validates_without_warnings():
    result = validate_registries(ROOT / "registries", ROOT / "schemas")

    assert "power_system_source_catalog.yaml" in result.validated_files
    assert result.warnings == []


def test_pjm_source_catalog_separates_approved_core_from_candidate_expansion():
    catalog = load_power_system_source_catalog(ROOT / "registries")

    assert catalog["PJM_DATAMINER_HOURLY_LMP_CORE"]["status"] == "approved_core"
    assert catalog["PJM_DATAMINER_HOURLY_LMP_CORE"]["registry_feed_ids"] == [
        "PJM_PNODE",
        "PJM_DA_HOURLY_LMP",
        "PJM_RT_HOURLY_LMP",
    ]
    assert catalog["PJM_DATAMINER_HOURLY_LMP_CORE"]["query_planning"]["archive_policy"] == "archive_aware_required"
    assert catalog["PJM_DATAMINER_HOURLY_LMP_CORE"]["publication_lifecycle"]["revision_policy"] == "row_version_current_filter_required"
    assert catalog["PJM_DATAMINER_FIVE_MINUTE_RT_LMP"]["status"] == "candidate"
    assert catalog["PJM_DATAMINER_FIVE_MINUTE_RT_LMP"]["registry_feed_ids"] == ["PJM_RT_FIVE_MINUTE_LMP"]
    assert catalog["PJM_DATAMINER_FIVE_MINUTE_RT_LMP"]["publication_lifecycle"]["authoritative_use"] == "candidate_metadata_only"
    assert "candidate_expansion" in catalog["PJM_DATAMINER_TRANSMISSION_CONSTRAINTS"]["canonical_roles"]


def test_approved_power_source_publications_reference_existing_feed_descriptors():
    resolved = validate_power_system_source_catalog_references(ROOT / "registries")

    assert resolved["PJM_DATAMINER_LOAD_FORECASTS"] == ["load_frcstd_7_day", "load_frcstd_hist"]
    assert resolved["PJM_DATAMINER_HOURLY_LMP_CORE"] == ["PJM_PNODE", "PJM_DA_HOURLY_LMP", "PJM_RT_HOURLY_LMP"]
    assert resolved["PJM_DATAMINER_GENERATION_BY_FUEL"] == ["PJM_GEN_BY_FUEL"]


def test_power_source_publication_lifecycle_summary_separates_authoritative_and_candidate_use():
    summary = source_publication_lifecycle_summary(ROOT / "registries")

    assert summary["PJM_DATAMINER_LOAD_FORECASTS"]["authoritative_use"] == "approved_source_surface"
    assert summary["PJM_DATAMINER_LOAD_FORECASTS"]["revision_policy"] == "latest_and_revision_history_separate"
    assert summary["PJM_DATAMINER_TRANSMISSION_CONSTRAINTS"]["authoritative_use"] == "candidate_not_publishable"
    assert summary["PJM_DATAMINER_TRANSMISSION_CONSTRAINTS"]["retention_alignment"] == "candidate_only"


def test_power_source_catalog_preserves_pjm_terms_for_all_dataminer_publications():
    catalog = load_yaml_unique(ROOT / "registries" / "power_system_source_catalog.yaml")

    assert catalog
    for publication_id, record in catalog.items():
        assert publication_id.startswith("PJM_DATAMINER_")
        assert record["terms"]["internal_use_only"] is True
        assert record["terms"]["redistribution_requires_license"] is True
        assert "limit connections" in record["terms"]["rate_limit_notes"]


def test_approved_source_publication_without_feed_descriptor_fails_closed(tmp_path):
    registry_dir = tmp_path / "registries"
    registry_dir.mkdir()
    for name in ["pjm_fundamental_feeds.yaml", "power_system_price_feeds.yaml", "power_generation_mix_feeds.yaml", "power_system_source_catalog.yaml"]:
        (registry_dir / name).write_text((ROOT / "registries" / name).read_text(encoding="utf-8"), encoding="utf-8")

    catalog = yaml.safe_load((registry_dir / "power_system_source_catalog.yaml").read_text(encoding="utf-8"))
    catalog["PJM_DATAMINER_HOURLY_LMP_CORE"]["registry_feed_ids"].append("PJM_UNKNOWN_PRICE_FEED")
    (registry_dir / "power_system_source_catalog.yaml").write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_source_catalog_references(registry_dir)

    assert exc.value.code == POWER_SYSTEM_SOURCE_ERROR
    assert "PJM_UNKNOWN_PRICE_FEED" in exc.value.message


def test_approved_source_publication_with_pending_lifecycle_fails_closed(tmp_path):
    registry_dir = tmp_path / "registries"
    registry_dir.mkdir()
    for name in ["pjm_fundamental_feeds.yaml", "power_system_price_feeds.yaml", "power_generation_mix_feeds.yaml", "power_system_source_catalog.yaml"]:
        (registry_dir / name).write_text((ROOT / "registries" / name).read_text(encoding="utf-8"), encoding="utf-8")

    catalog = yaml.safe_load((registry_dir / "power_system_source_catalog.yaml").read_text(encoding="utf-8"))
    catalog["PJM_DATAMINER_HOURLY_LMP_CORE"]["publication_lifecycle"]["revision_policy"] = "source_specific_pending"
    (registry_dir / "power_system_source_catalog.yaml").write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_power_system_source_catalog_references(registry_dir)

    assert exc.value.code == POWER_SYSTEM_SOURCE_ERROR
    assert "unresolved lifecycle fields" in exc.value.message
    assert "revision_policy" in exc.value.message
