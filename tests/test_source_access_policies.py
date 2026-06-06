from __future__ import annotations

from pathlib import Path

from pga_workbench.data.connectors.pjm_dataminer import (
    PJM_DATAMINER_CONNECTION_LIMITS_PER_MINUTE,
    PJM_DATAMINER_DEFAULT_MAX_PAGES,
    PJM_DATAMINER_MAX_ROW_COUNT,
)
from pga_workbench.registry import validate_registries
from pga_workbench.services.source_access_policies import source_access_policy_for_surface


ROOT = Path(__file__).resolve().parents[1]


def test_source_access_policy_registry_validates_without_warnings():
    result = validate_registries(ROOT / "registries", ROOT / "schemas")

    assert "power_system_source_access_policies.yaml" in result.validated_files
    assert result.warnings == []


def test_pjm_dataminer_access_policy_matches_connector_guardrails():
    policy = source_access_policy_for_surface(ROOT / "registries", "pjm_data_miner_api")

    assert policy["row_count"]["maximum"] == PJM_DATAMINER_MAX_ROW_COUNT
    assert policy["row_count"]["default"] == PJM_DATAMINER_MAX_ROW_COUNT
    assert policy["pagination"]["default_max_pages"] == PJM_DATAMINER_DEFAULT_MAX_PAGES
    assert policy["pagination"]["allow_unbounded"] is False
    assert {
        account_class: record["max_connections_per_minute"]
        for account_class, record in policy["account_classes"].items()
    } == PJM_DATAMINER_CONNECTION_LIMITS_PER_MINUTE
