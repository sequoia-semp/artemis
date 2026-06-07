from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.cli import artemis_main, main
from pga_workbench.exceptions import WorkbenchException
from pga_workbench.registry import validate_registries
from pga_workbench.serialization import read_json
from pga_workbench.services.ports import QuantLibBlack76PricingPort, valuation_port_catalog


ROOT = Path(__file__).resolve().parents[1]


def test_valuation_port_catalog_reports_builtins_and_optional_oss_candidates():
    catalog = valuation_port_catalog()

    builtins = {item["port_id"]: item for item in catalog["builtins"]}
    optional = {item["port_id"]: item for item in catalog["optional_oss_candidates"]}

    assert builtins["pricing.black76_builtin"]["available"] is True
    assert builtins["pricing.black76_builtin"]["authoritative"] is True
    assert builtins["risk.historical_var_builtin"]["available"] is True
    assert builtins["risk.historical_var_builtin"]["authoritative"] is True
    assert set(optional) == {
        "pricing.quantlib_black76_candidate",
        "risk.riskfolio_candidate",
        "risk.cvxportfolio_candidate",
        "risk.skfolio_candidate",
    }
    assert all(item["authoritative"] is False for item in optional.values())
    assert catalog["policy"]["optional_adapter_rule"].startswith("candidate adapters must be installed")


def test_quantlib_candidate_adapter_fails_closed_when_unavailable_or_unvalidated():
    port = QuantLibBlack76PricingPort()

    with pytest.raises(WorkbenchException) as exc:
        port.option_greeks([])

    assert exc.value.code in {"OSS_ADAPTER_UNAVAILABLE", "OSS_ADAPTER_NOT_VALIDATED"}
    assert "pricing.quantlib_black76_candidate" in exc.value.message


def test_valuation_adapter_catalog_cli_outputs_json(tmp_path: Path):
    output = tmp_path / "valuation_adapters.json"

    assert main(["valuation-adapters", "--output", str(output)]) == 0
    payload = read_json(output)
    assert payload["builtins"][0]["port_id"] == "pricing.black76_builtin"

    analyst_output = tmp_path / "analyst_valuation_adapters.json"
    assert artemis_main(["analyst", "valuation-adapters", "--output", str(analyst_output)]) == 0
    analyst_payload = read_json(analyst_output)
    assert analyst_payload["optional_oss_candidates"][0]["authoritative"] is False


def test_valuation_adapter_tool_registry_validates():
    result = validate_registries(ROOT / "registries", ROOT / "schemas")

    assert "tools.yaml" in result.validated_files
