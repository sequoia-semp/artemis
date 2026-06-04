from __future__ import annotations

from pathlib import Path

from pga_workbench.agent_runtime.capabilities import (
    check_command_available,
    collect_agent_capabilities,
    load_capability_registry,
    recommend_agent_mode,
)


ROOT = Path(__file__).resolve().parents[1]


def test_capability_registry_loads_optional_wrappers():
    registry = load_capability_registry(ROOT / "integrations/capability_registry.yaml")
    assert registry["core"]["pga"]["required"] is True
    assert registry["wrappers"]["opencode"]["required"] is False
    assert registry["wrappers"]["ollama"]["required"] is False
    assert registry["wrappers"]["openclaw"]["required"] is False


def test_missing_optional_command_does_not_raise():
    result = check_command_available("__artemis_missing_wrapper__ --version")
    assert result["available"] is False
    assert result["executable"] == "__artemis_missing_wrapper__"


def test_collect_agent_capabilities_keeps_optional_wrappers_optional():
    capabilities = collect_agent_capabilities(ROOT, check_network=False)
    assert capabilities["core"]["pga"]["available"] is True
    assert capabilities["wrappers"]["ollama"]["required"] is False
    assert capabilities["wrappers"]["ollama"]["reachable"] is False
    assert capabilities["wrappers"]["ollama"]["network_check_skipped"] is True
    assert capabilities["recommended_mode"] in {"context_bundle_manual", "opencode_external_model"}


def test_recommend_agent_mode_falls_back_to_context_bundle_manual():
    capabilities = {
        "wrappers": {
            "opencode": {"available": False},
            "ollama": {"reachable": False},
        }
    }
    assert recommend_agent_mode(capabilities) == "context_bundle_manual"


def test_cli_exposes_vcs_ready_command():
    from pga_workbench.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["vcs-ready", "--ticket", "T-0010", "--skip-tests"])
    assert args.ticket == "T-0010"
    assert args.skip_tests is True
