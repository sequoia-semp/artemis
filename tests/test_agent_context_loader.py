from __future__ import annotations

from pathlib import Path

import pytest

from pga_workbench.agent_runtime.context_loader import CONTEXT_FILE_MISSING, collect_context
from pga_workbench.exceptions import WorkbenchException


ROOT = Path(__file__).resolve().parents[1]


def test_context_loader_loads_required_startup_files_and_ticket():
    context = collect_context(ROOT, "T-0001", ROOT / "tests/fixtures/legacy_llm_config.example.yaml")
    paths = {item["path"] for item in context["files"]}
    assert "AGENTS.md" in paths
    assert "llms.txt" in paths
    assert "docs/CONVENTIONS_LOCKED_v0.1.md" in paths
    assert context["ticket"]["id"] == "T-0001"
    assert context["active_profile"] == "deterministic_only"
    assert context["profile"]["provider_kind"] == "none"
    assert context["provider"] is None


def test_context_loader_loads_affected_files_when_present():
    context = collect_context(ROOT, "T-0002", ROOT / "tests/fixtures/legacy_llm_config.example.yaml")
    paths = {item["path"] for item in context["files"]}
    assert "docs/VCS_POLICY.md" in paths
    assert "docs/RELEASE_PROCESS.md" in paths


def test_t0006_onboarding_context_is_executable():
    context = collect_context(ROOT, "T-0006", ROOT / "tests/fixtures/legacy_llm_config.example.yaml")
    paths = {item["path"] for item in context["files"]}
    assert context["ticket"]["id"] == "T-0006"
    assert "AGENTS.md" in paths
    assert "llms.txt" in paths
    assert "docs/CONVENTIONS_LOCKED_v0.1.md" in paths
    assert "docs/archive/wrappers/OPENCODE_SETUP.md" in paths


def test_context_loader_missing_required_file_fails_closed(tmp_path):
    config = tmp_path / "llm_config.yaml"
    config.write_text(
        "provider: ollama\n"
        "context:\n"
        "  always_load:\n"
        "    - missing.md\n"
        "  work_item_root: work/\n"
        "  max_file_bytes: 200000\n",
        encoding="utf-8",
    )
    with pytest.raises(WorkbenchException) as exc:
        collect_context(ROOT, "T-0001", config)
    assert exc.value.code == CONTEXT_FILE_MISSING


def test_context_loader_does_not_call_external_model():
    context = collect_context(ROOT, "T-0004", ROOT / "tests/fixtures/legacy_llm_config.example.yaml")
    assert "files" in context
    assert "ticket" in context
    assert "model_response" not in context


def test_context_loader_preserves_old_flat_config_shape(tmp_path):
    config = tmp_path / "llm_config.yaml"
    config.write_text(
        "provider: ollama\n"
        "ollama:\n"
        "  base_url: http://localhost:11434\n"
        "  default_model: qwen3-coder:30b\n"
        "context:\n"
        "  always_load:\n"
        "    - AGENTS.md\n"
        "  work_item_root: work/\n"
        "  max_file_bytes: 200000\n",
        encoding="utf-8",
    )
    context = collect_context(ROOT, "T-0001", config)
    assert context["active_profile"] == "ollama"
    assert context["provider"] == "ollama"
    assert context["profile"]["provider_kind"] == "openai_compatible"
