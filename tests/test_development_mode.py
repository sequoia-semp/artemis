from __future__ import annotations

from pathlib import Path
import pytest

from pga_workbench.cli import main
from pga_workbench.dev.coding_backend import validate_coding_backends
from pga_workbench.dev.patch_context import collect_development_context
from pga_workbench.dev.self_improvement import repo_mutation_requires_ticket
from pga_workbench.exceptions import WorkbenchException


ROOT = Path(__file__).resolve().parents[1]


def test_development_context_is_backend_neutral():
    context = collect_development_context(ROOT, "T-0020")

    assert context["mode"] == "development"
    assert context["context_version"] == "artemis.development.v1"
    assert context["ticket"]["id"] == "T-0020"
    assert context["artemis_config"] == "artemis.yaml"
    assert context["active_backend"] == "human"
    assert context["authority_ladder"]["root_contract"] == "AGENTS.md"
    assert "repo_patch" in context["tool_policy"]
    assert set(context["backend_options"]) == {"external_harness", "human", "opencode"}
    assert context["release_validation_commands"] == ["artemis validate --strict"]
    assert context["missing_affected_files"] == []
    assert {item["path"] for item in context["files"]} >= {"AGENTS.md", "artemis.yaml", "docs/README.md"}
    assert context["context_profile"] == "default"


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


def test_development_context_honors_ticket_context_profile():
    context = collect_development_context(ROOT, "T-context-profiles")
    paths = {item["path"] for item in context["files"]}

    assert context["context_profile"] == "wrapper"
    assert ".opencode/commands/artemis-context.md" in paths
    assert "registries/tools.yaml" in paths


def test_development_context_rejects_unknown_context_profile(monkeypatch):
    monkeypatch.setattr(
        "pga_workbench.dev.patch_context.load_development_ticket",
        lambda repo_root, ticket_id: {
            "id": ticket_id,
            "type": "ticket",
            "status": "proposed",
            "title": "Bad profile",
            "risk": "medium",
            "affected_files": [],
            "context_profile": "__missing__",
        },
    )

    with pytest.raises(WorkbenchException) as exc:
        collect_development_context(ROOT, "T-bad-profile")
    assert "Unknown context_profile" in exc.value.message


def test_development_context_profile_fixtures(monkeypatch):
    def fake_ticket(repo_root, ticket_id):
        profile = ticket_id.replace("T-profile-", "")
        ticket = {
            "id": ticket_id,
            "type": "ticket",
            "status": "proposed",
            "title": "Profile fixture",
            "risk": "medium",
            "affected_files": [],
        }
        if profile != "default":
            ticket["context_profile"] = profile
        return ticket

    monkeypatch.setattr("pga_workbench.dev.patch_context.load_development_ticket", fake_ticket)

    default_paths = {item["path"] for item in collect_development_context(ROOT, "T-profile-default")["files"]}
    wrapper_paths = {item["path"] for item in collect_development_context(ROOT, "T-profile-wrapper")["files"]}
    trading_paths = {item["path"] for item in collect_development_context(ROOT, "T-profile-trading_domain")["files"]}
    behavioral_paths = {item["path"] for item in collect_development_context(ROOT, "T-profile-behavioral")["files"]}

    assert ".opencode/agents/build.md" not in default_paths
    assert ".opencode/agents/build.md" in wrapper_paths
    assert "docs/CONVENTIONS_LOCKED_v0.1.md" in trading_paths
    assert "domain/source_policy.md" in trading_paths
    assert "domain/market_index_model.md" in trading_paths
    assert "domain/period_grammar.md" in trading_paths
    assert "domain/units_and_quantities.md" in trading_paths
    assert any(path.startswith("registries/") for path in trading_paths)
    assert any(path.startswith("schemas/") for path in trading_paths)
    assert any(path.startswith("tests/") for path in trading_paths)
    assert "development/CHANGE_POLICY.md" in behavioral_paths
    assert any(path.startswith("domain/") for path in behavioral_paths)
