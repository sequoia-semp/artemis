from __future__ import annotations

from pathlib import Path

import yaml

from pga_workbench.agent.modes import AgentMode, mode_can_modify_repo, mode_requires_ticket
from pga_workbench.agent.runtime import collect_artemis_capabilities, load_artemis_config, validate_artemis_config


ROOT = Path(__file__).resolve().parents[1]


def test_artemis_config_validates_and_modes_are_separated():
    config = validate_artemis_config(ROOT)

    assert config["name"] == "artemis"
    assert mode_can_modify_repo(config, AgentMode.ANALYST) is False
    assert mode_can_modify_repo(config, AgentMode.DEVELOPMENT) is True
    assert mode_requires_ticket(config, AgentMode.DEVELOPMENT) is True


def test_local_artemis_example_uses_env_names_not_secrets():
    payload = yaml.safe_load((ROOT / "local/artemis.local.example.yaml").read_text(encoding="utf-8"))
    text = (ROOT / "local/artemis.local.example.yaml").read_text(encoding="utf-8")

    assert "ARTEMIS_VENDOR_API_KEY" in text
    assert "ARTEMIS_ICE_API_KEY" in text
    assert "api_key_env" in text
    assert "sk-" not in text
    assert payload["profiles"]["deterministic_only"]["role_bindings"]["analyst_llm"]["kind"] == "none"


def test_capabilities_report_tool_policy_and_optional_providers():
    capabilities = collect_artemis_capabilities(ROOT, check_network=False)

    assert capabilities["name"] == "artemis"
    assert capabilities["providers"]["profiles"]["local_ollama"]["required"] is False
    assert capabilities["tools"]["policy"]["repo_patch"]["can_modify_repo"] is True
    assert capabilities["tools"]["policy"]["repo_patch"]["requires_ticket"] is True
    assert capabilities["tools"]["policy"]["analyst_view_build"]["can_modify_repo"] is False


def test_artemis_config_resolution_order_cli_over_env(monkeypatch, tmp_path):
    env_overlay = tmp_path / "env.yaml"
    cli_overlay = tmp_path / "cli.yaml"
    env_overlay.write_text(
        yaml.safe_dump({"providers": {"default_profile": "env_profile"}}),
        encoding="utf-8",
    )
    cli_overlay.write_text(
        yaml.safe_dump({"providers": {"default_profile": "cli_profile"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ARTEMIS_CONFIG", str(env_overlay))

    config = load_artemis_config(ROOT, config_path=cli_overlay)

    assert config["providers"]["default_profile"] == "cli_profile"
    assert config["name"] == "artemis"


def test_artemis_config_resolution_reads_env_override(monkeypatch, tmp_path):
    env_overlay = tmp_path / "env.yaml"
    env_overlay.write_text(
        yaml.safe_dump({"providers": {"default_profile": "env_profile"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ARTEMIS_CONFIG", str(env_overlay))

    config = load_artemis_config(ROOT)

    assert config["providers"]["default_profile"] == "env_profile"
