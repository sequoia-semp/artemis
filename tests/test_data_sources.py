from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.data.contracts import FIXTURE_DATA_NOT_ALLOWED, assert_data_environment_allowed
from pga_workbench.data.sources import credential_env_names, validate_data_sources
from pga_workbench.exceptions import WorkbenchException


ROOT = Path(__file__).resolve().parents[1]


def test_data_source_registry_validates_without_credentials():
    payload = validate_data_sources(ROOT / "registries/data_sources.yaml", ROOT / "schemas")

    assert set(payload["data_sources"]) == {"file_drop", "vendor_api", "iso_api", "pjm_dataminer", "ice_exchange"}
    assert credential_env_names(payload) == ["ARTEMIS_VENDOR_API_KEY", "ARTEMIS_PJM_API_KEY", "ARTEMIS_ICE_API_KEY"]


def test_fixture_data_blocked_in_normal_analyst_mode():
    with pytest.raises(WorkbenchException) as exc:
        assert_data_environment_allowed("analyst", "fixture")

    assert exc.value.code == FIXTURE_DATA_NOT_ALLOWED


def test_fixture_data_allowed_when_explicit():
    assert_data_environment_allowed("analyst", "fixture", allow_fixture=True)
