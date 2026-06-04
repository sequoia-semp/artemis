from __future__ import annotations

from pathlib import Path

import yaml

from pga_workbench.agent_runtime.context_loader import collect_context


ROOT = Path(__file__).resolve().parents[1]


def test_local_llm_config_uses_optional_profiles():
    config = yaml.safe_load((ROOT / "local/llm_config.example.yaml").read_text(encoding="utf-8"))
    assert config["legacy"] is True
    assert config["legacy_replacement"] == "local/artemis.local.example.yaml"
    profiles = config["profiles"]
    assert config["active_profile"] == "deterministic_only"
    assert profiles["deterministic_only"]["required"] is False
    assert profiles["local_ollama"]["required"] is False
    assert profiles["external_harness"]["required"] is False
    assert all(profile["required"] is False for profile in profiles.values())
    assert profiles["external_harness"]["provider_kind"] == "external"


def test_profile_config_keeps_required_context_files():
    config = yaml.safe_load((ROOT / "local/llm_config.example.yaml").read_text(encoding="utf-8"))
    always_load = set(config["context"]["always_load"])
    assert "AGENTS.md" in always_load
    assert "docs/CONVENTIONS_LOCKED_v0.1.md" in always_load
    assert "development/CHANGE_POLICY.md" in always_load


def test_artemis_local_config_is_primary_local_template():
    config = yaml.safe_load((ROOT / "local/artemis.local.example.yaml").read_text(encoding="utf-8"))
    assert config["profiles"]["deterministic_only"]["role_bindings"]["analyst_llm"]["kind"] == "none"
    assert config["data_sources"]["example_ice"]["credentials"]["required_env"] == ["ARTEMIS_ICE_API_KEY"]


def test_collect_context_loads_profile_config_for_wrapper_ticket():
    context = collect_context(ROOT, "T-0009", ROOT / "local/llm_config.example.yaml")
    assert context["ticket"]["id"] == "T-0009"
    assert context["active_profile"] == "deterministic_only"
    assert context["profile"]["provider_kind"] == "none"
    assert context["provider"] is None
    assert "model_response" not in context
