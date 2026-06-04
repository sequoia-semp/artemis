from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_llm_config_is_minimal_stub():
    config = yaml.safe_load((ROOT / "local/llm_config.example.yaml").read_text(encoding="utf-8"))
    assert config["legacy"] is True
    assert config["legacy_replacement"] == "local/artemis.local.example.yaml"
    assert "profiles" not in config
    assert "context" not in config
    assert "safety" not in config


def test_artemis_local_config_is_primary_local_template():
    config = yaml.safe_load((ROOT / "local/artemis.local.example.yaml").read_text(encoding="utf-8"))
    assert config["profiles"]["deterministic_only"]["role_bindings"]["analyst_llm"]["kind"] == "none"
    assert config["data_sources"]["example_ice"]["credentials"]["required_env"] == ["ARTEMIS_ICE_API_KEY"]
