from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_governance_docs_exist():
    for relative in [
        "Makefile",
        "artemis.yaml",
        "scripts/bootstrap_dev.sh",
        "scripts/dev_env.sh",
        "docs/README.md",
        "docs/user/setup.md",
        "local/.env.example",
        "docs/VCS_POLICY.md",
        "docs/WORK_MANAGEMENT.md",
        "docs/RELEASE_PROCESS.md",
        "docs/CODEX_WORKFLOW.md",
        "docs/archive/wrappers/LOCAL_LLM.md",
        "docs/archive/wrappers/OPENCODE_SETUP.md",
        "docs/archive/wrappers/AGENT_KB_SKILL_RELEASE_LOOP.md",
        "docs/archive/wrappers/AGENT_WRAPPER_EVALUATION.md",
        "docs/archive/wrappers/WRAPPER_ABSTRACTION_POLICY.md",
        "docs/archive/wrappers/AGENT_MODES.md",
        "planning/merge_intake.md",
        "docs/archive/pjm_workbench_mvp_agent_spec.md",
        "work/backlog/pjm_workbench_mvp_backlog.yaml",
    ]:
        assert (ROOT / relative).exists()


def test_no_docs_claim_paid_github_is_required():
    for path in [ROOT / "docs/VCS_POLICY.md", ROOT / "docs/WORK_MANAGEMENT.md", ROOT / "docs/archive/wrappers/LOCAL_LLM.md"]:
        text = path.read_text(encoding="utf-8").lower()
        assert "paid github" not in text.replace("no paid github", "")
        assert "not required" in text or "no paid" in text or "without paid" in text


def test_gas_point25d_convention_remains_visible():
    locked = (ROOT / "docs/CONVENTIONS_LOCKED_v0.1.md").read_text(encoding="utf-8")
    assert "0.25/d" in locked
    assert "2,500 MMBtu/day" in locked
    for relative_path in ["README.md", "AGENTS.md", "llms.txt"]:
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "0.25/d" not in text
        assert "2,500 MMBtu/day" not in text


def test_github_templates_point_to_local_canonical_files():
    for path in (ROOT / ".github").glob("**/*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert "Local" in text or "local" in text


def test_opencode_config_keeps_mutations_approval_gated():
    text = (ROOT / "opencode.jsonc").read_text(encoding="utf-8")
    assert '"*": "ask"' in text
    assert '"git push*": "ask"' in text
    assert '"git tag*": "ask"' in text
    assert '"pga validate-work-items": "allow"' in text
    assert '"model"' not in text
    assert '"provider"' not in text


def test_agent_release_docs_preserve_deterministic_authority():
    release_loop = (ROOT / "docs/archive/wrappers/AGENT_KB_SKILL_RELEASE_LOOP.md").read_text(encoding="utf-8")
    wrapper_eval = (ROOT / "docs/archive/wrappers/AGENT_WRAPPER_EVALUATION.md").read_text(encoding="utf-8")
    assert "Prompt-only analytics are not authoritative" in release_loop
    assert "not as the source of analytics truth" in wrapper_eval


def test_readme_includes_local_agent_integration_steps():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "# Artemis" in readme
    assert "make validate" in readme
    assert "artemis capabilities" in readme
    assert "docs/user/setup.md" in readme
    assert "artemis dev context --ticket T-0019" in readme
    assert "pga work-context --ticket T-0019" in readme
    assert "Prompt-only analytics are not authoritative" in readme


def test_primary_navigation_does_not_route_through_legacy_build_packet():
    primary_paths = [
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "llms.txt",
        ROOT / "docs/README.md",
    ]
    for path in primary_paths:
        text = path.read_text(encoding="utf-8")
        assert "artemis.yaml" in text
        assert "local/llm_config.example.yaml" not in text
    assert "Historical build-packet" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_setup_doc_covers_local_llm_env_and_file_sources():
    text = (ROOT / "docs/user/setup.md").read_text(encoding="utf-8")
    assert "ollama pull" in text
    assert "opencode" in text.lower()
    assert "local/.env" in text
    assert "ARTEMIS_MARKS_ROOT" in text
    assert "ARTEMIS_POSITIONS_ROOT" in text


def test_root_markdown_files_are_limited_to_navigation_and_legacy_pointers():
    root_markdown = {path.name for path in ROOT.glob("*.md")}
    assert root_markdown <= {
        "README.md",
        "AGENTS.md",
    }
    assert len(root_markdown) <= 2


def test_make_validate_includes_artemis_artifacts():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "ARTEMIS ?= $(VENV)/bin/artemis" in makefile
    assert "validate-artemis:" in makefile
    assert "$(ARTEMIS) config validate" in makefile
    assert "$(ARTEMIS) skill validate" in makefile
    assert "$(ARTEMIS) views validate" in makefile
    assert "$(ARTEMIS) data-sources validate" in makefile
    assert "$(ARTEMIS) capabilities" in makefile


def test_vcs_policy_standardizes_local_venv_and_merge_flow():
    policy = (ROOT / "docs/VCS_POLICY.md").read_text(encoding="utf-8")
    assert "make bootstrap" in policy
    assert "make validate" in policy
    assert "make release-check" in (ROOT / "docs/RELEASE_PROCESS.md").read_text(encoding="utf-8")
    assert "pga vcs-ready --ticket T-####" in policy
    assert "git push -u origin codex/T-####-slug" in policy
