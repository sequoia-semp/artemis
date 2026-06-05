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
    assert config["providers"]["default_profile"] == "deterministic_only"
    assert config["providers"]["profiles"]["local_ollama"]["kind"] == "openai_compatible"
    assert config["backends"]["coding"]["default"] == "human"


def test_local_env_example_contains_credentials_and_file_roots():
    text = (ROOT / "local/.env.example").read_text(encoding="utf-8")
    assert "ARTEMIS_ICE_API_KEY=" in text
    assert "ARTEMIS_MARKS_ROOT=" in text
    assert "ARTEMIS_POSITIONS_ROOT=" in text
