from __future__ import annotations

from pathlib import Path

from pga_workbench.dev.coding_backend import validate_coding_backends
from pga_workbench.dev.patch_context import collect_development_context
from pga_workbench.dev.self_improvement import repo_mutation_requires_ticket


ROOT = Path(__file__).resolve().parents[1]


def test_development_context_is_backend_neutral():
    context = collect_development_context(ROOT, "T-0018")

    assert context["mode"] == "development"
    assert context["ticket"]["id"] == "T-0018"
    assert context["artemis_config"] == "artemis.yaml"


def test_backend_descriptors_are_optional_and_non_authoritative():
    result = validate_coding_backends(ROOT)

    assert result["backends"] == 3
    assert set(result["ids"]) == {"external_harness", "human", "opencode"}
    assert repo_mutation_requires_ticket() is True
