from __future__ import annotations

from pathlib import Path

import yaml
import pytest

from pga_workbench.agent.modes import AgentMode, mode_can_modify_repo, mode_requires_ticket
from pga_workbench.agent.runtime import collect_artemis_capabilities, load_artemis_config, validate_artemis_config
from pga_workbench.exceptions import WorkbenchException


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
    env_text = (ROOT / "local/.env.example").read_text(encoding="utf-8")

    assert "ARTEMIS_VENDOR_API_KEY" in env_text
    assert "ARTEMIS_ICE_API_KEY" in env_text
    assert "api_key_env" in text
    assert "sk-" not in text + env_text
    assert "profiles" not in payload
    assert payload["providers"]["profiles"]["local_ollama"]["kind"] == "openai_compatible"
    assert payload["backends"]["coding"]["default"] == "human"


def test_capabilities_report_tool_policy_and_optional_providers():
    capabilities = collect_artemis_capabilities(ROOT, check_network=False)

    assert capabilities["name"] == "artemis"
    assert capabilities["providers"]["determinism"]["default_profile"] == "deterministic_only"
    assert capabilities["providers"]["determinism"]["deterministic"] is True
    assert capabilities["providers"]["determinism"]["model_calls"] is False
    assert capabilities["providers"]["profiles"]["local_ollama"]["required"] is False
    assert capabilities["file_sources"]["marks_root_env"]["env"] == "ARTEMIS_MARKS_ROOT"
    assert capabilities["policies"]["cache"] == "configs/cache_policy.yaml"
    assert capabilities["tools"]["policy"]["repo_patch"]["can_modify_repo"] is True
    assert capabilities["tools"]["policy"]["repo_patch"]["requires_ticket"] is True
    assert capabilities["tools"]["policy"]["analyst_view_build"]["can_modify_repo"] is False
    assert capabilities["tools"]["policy"]["forward_price_heatmap"]["risk"] == "workspace_write"
    assert capabilities["tools"]["policy"]["validate_repo"]["authority"] == "deterministic_service"
    assert capabilities["tools"]["policy"]["repo_patch"]["authority"] == "candidate_only"


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


def test_artemis_config_rejects_stale_root_profiles_shape(tmp_path):
    stale = tmp_path / "stale.yaml"
    stale.write_text(yaml.safe_dump({"profiles": {"local_ollama": {"kind": "openai_compatible"}}}), encoding="utf-8")

    with pytest.raises(WorkbenchException):
        validate_artemis_config(ROOT, config_path=stale)


def test_artemis_config_rejects_nondeterministic_default_provider(tmp_path):
    overlay = tmp_path / "nondeterministic_provider.yaml"
    overlay.write_text(yaml.safe_dump({"providers": {"default_profile": "local_ollama"}}), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_artemis_config(ROOT, config_path=overlay)

    assert exc.value.code == "ARTEMIS_CONFIG_ERROR"
    assert "not marked deterministic" in exc.value.message


def test_artemis_config_accepts_guaranteed_seeded_deterministic_provider(tmp_path):
    overlay = tmp_path / "deterministic_provider.yaml"
    overlay.write_text(
        yaml.safe_dump(
            {
                "providers": {
                    "default_profile": "seeded_model",
                    "profiles": {
                        "seeded_model": {
                            "kind": "openai_compatible",
                            "required": False,
                            "descriptor": "integrations/providers/openai_compatible.example.yaml",
                            "model": "deterministic-fixture",
                            "parameters": {"temperature": 0, "seed": 1234},
                            "determinism": {
                                "profile": "deterministic",
                                "guaranteed": True,
                                "supports_seed": True,
                            },
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    config = validate_artemis_config(ROOT, config_path=overlay)

    assert config["providers"]["default_profile"] == "seeded_model"


def test_artemis_config_rejects_deterministic_provider_without_seed(tmp_path):
    overlay = tmp_path / "missing_seed_provider.yaml"
    overlay.write_text(
        yaml.safe_dump(
            {
                "providers": {
                    "default_profile": "missing_seed",
                    "profiles": {
                        "missing_seed": {
                            "kind": "openai_compatible",
                            "required": False,
                            "descriptor": "integrations/providers/openai_compatible.example.yaml",
                            "model": "deterministic-fixture",
                            "parameters": {"temperature": 0},
                            "determinism": {
                                "profile": "deterministic",
                                "guaranteed": True,
                                "supports_seed": True,
                            },
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(WorkbenchException) as exc:
        validate_artemis_config(ROOT, config_path=overlay)

    assert "must pin seed" in exc.value.message


def test_artemis_config_rejects_missing_default_tool(tmp_path):
    overlay = tmp_path / "missing_tool.yaml"
    overlay.write_text(yaml.safe_dump({"modes": {"analyst": {"default_tools": ["__missing_tool__"]}}}), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_artemis_config(ROOT, config_path=overlay)
    assert "Default tool registry mismatch" in exc.value.message
    assert "__missing_tool__" in exc.value.message


def test_artemis_config_rejects_mode_incompatible_default_tool(tmp_path):
    overlay = tmp_path / "wrong_mode.yaml"
    overlay.write_text(yaml.safe_dump({"modes": {"analyst": {"default_tools": ["validate_repo"]}}}), encoding="utf-8")

    with pytest.raises(WorkbenchException) as exc:
        validate_artemis_config(ROOT, config_path=overlay)
    assert "validate_repo" in exc.value.message


def test_artemis_env_file_loads_file_source_roots(monkeypatch, tmp_path):
    monkeypatch.delenv("ARTEMIS_MARKS_ROOT", raising=False)
    env_file = tmp_path / "artemis.env"
    env_file.write_text("ARTEMIS_MARKS_ROOT=/tmp/artemis-marks\n", encoding="utf-8")
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text(yaml.safe_dump({"runtime": {"env_files": [str(env_file)]}}), encoding="utf-8")

    capabilities = collect_artemis_capabilities(ROOT, config_path=overlay)

    assert capabilities["file_sources"]["marks_root_env"]["configured"] is True
    assert capabilities["file_sources"]["marks_root_env"]["path"] == "/tmp/artemis-marks"
