from __future__ import annotations

from pathlib import Path

from pga_workbench.cli import main
from pga_workbench.dev.coding_backend import validate_coding_backends
from pga_workbench.dev.patch_context import collect_development_context
from pga_workbench.dev.self_improvement import repo_mutation_requires_ticket


ROOT = Path(__file__).resolve().parents[1]


def test_development_context_is_backend_neutral():
    context = collect_development_context(ROOT, "T-0020")

    assert context["mode"] == "development"
    assert context["context_version"] == "artemis.development.v1"
    assert context["ticket"]["id"] == "T-0020"
    assert context["artemis_config"] == "artemis.yaml"
    assert context["authority_ladder"]["root_contract"] == "AGENTS.md"
    assert "repo_patch" in context["tool_policy"]
    assert set(context["backend_options"]) == {"external_harness", "human", "opencode"}
    assert "python -m pytest -q" in context["release_validation_commands"]
    assert context["missing_affected_files"] == []
    assert {item["path"] for item in context["files"]} >= {"AGENTS.md", "artemis.yaml", "docs/README.md"}


def test_development_context_default_does_not_depend_on_legacy_llm_config():
    source = (ROOT / "src/pga_workbench/dev/patch_context.py").read_text(encoding="utf-8")
    assert "llm_config.example.yaml" not in source


def test_backend_descriptors_are_optional_and_non_authoritative():
    result = validate_coding_backends(ROOT)

    assert result["backends"] == 3
    assert set(result["ids"]) == {"external_harness", "human", "opencode"}
    assert repo_mutation_requires_ticket() is True


def test_pga_work_context_compatibility_uses_artemis_shape(tmp_path):
    output = tmp_path / "context.json"
    assert main(["work-context", "--ticket", "T-0018", "--output", str(output)]) == 0
    import json

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["context_version"] == "artemis.development.v1"
    assert payload["compatibility_command"] == "pga work-context"
    assert payload["artemis_config"] == "artemis.yaml"
