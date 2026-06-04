from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_governance_docs_exist():
    for relative in [
        "Makefile",
        "scripts/bootstrap_dev.sh",
        "scripts/dev_env.sh",
        "docs/VCS_POLICY.md",
        "docs/WORK_MANAGEMENT.md",
        "docs/RELEASE_PROCESS.md",
        "docs/LOCAL_LLM.md",
        "docs/CODEX_WORKFLOW.md",
        "docs/OPENCODE_SETUP.md",
        "docs/AGENT_KB_SKILL_RELEASE_LOOP.md",
        "docs/AGENT_WRAPPER_EVALUATION.md",
        "docs/WRAPPER_ABSTRACTION_POLICY.md",
        "docs/AGENT_MODES.md",
        "planning/merge_intake.md",
        "pjm_workbench_mvp_agent_spec.md",
        "pjm_workbench_mvp_backlog.yaml",
    ]:
        assert (ROOT / relative).exists()


def test_no_docs_claim_paid_github_is_required():
    for path in [ROOT / "docs/VCS_POLICY.md", ROOT / "docs/WORK_MANAGEMENT.md", ROOT / "docs/LOCAL_LLM.md"]:
        text = path.read_text(encoding="utf-8").lower()
        assert "paid github" not in text.replace("no paid github", "")
        assert "not required" in text or "no paid" in text or "without paid" in text


def test_gas_point25d_convention_remains_visible():
    locked = (ROOT / "docs/CONVENTIONS_LOCKED_v0.1.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "0.25/d" in locked
    assert "2,500 MMBtu/day" in locked
    assert "0.25/d" in readme
    assert "2,500 MMBtu/day" in readme


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


def test_agent_release_docs_preserve_deterministic_authority():
    release_loop = (ROOT / "docs/AGENT_KB_SKILL_RELEASE_LOOP.md").read_text(encoding="utf-8")
    wrapper_eval = (ROOT / "docs/AGENT_WRAPPER_EVALUATION.md").read_text(encoding="utf-8")
    assert "Prompt-only analytics are not authoritative" in release_loop
    assert "not as the source of analytics truth" in wrapper_eval


def test_readme_includes_local_agent_integration_steps():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Local agent integration" in readme
    assert "make validate" in readme
    assert "make work-context TICKET=T-0006" in readme
    assert "pga agent-capabilities" in readme
    assert "pga vcs-ready --ticket T-####" in readme
    assert "docs/WRAPPER_ABSTRACTION_POLICY.md" in readme
    assert "integrations/" in readme
    assert "Prompt-only analytics are not authoritative" in readme


def test_vcs_policy_standardizes_local_venv_and_merge_flow():
    policy = (ROOT / "docs/VCS_POLICY.md").read_text(encoding="utf-8")
    assert "make bootstrap" in policy
    assert "make validate" in policy
    assert "make release-check" in (ROOT / "docs/RELEASE_PROCESS.md").read_text(encoding="utf-8")
    assert "pga vcs-ready --ticket T-####" in policy
    assert "git push -u origin codex/T-####-slug" in policy
