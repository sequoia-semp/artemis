from __future__ import annotations

from pathlib import Path

from pga_workbench.agent_runtime.context_audit import _audit_prompt_text, audit_context_surfaces


ROOT = Path(__file__).resolve().parents[1]


def _codes(text: str) -> set[str]:
    return {item.code for item in _audit_prompt_text(ROOT, ".opencode/agents/fixture.md", text)}


def test_context_audit_passes_current_active_surfaces():
    result = audit_context_surfaces(ROOT)

    assert result["passed"] is True
    assert result["findings"] == []


def test_context_audit_flags_archive_authority():
    text = "Read `docs/archive/wrappers/AGENT_KB_SKILL_RELEASE_LOOP.md` before editing."

    assert "archive_authority_reference" in _codes(text)


def test_context_audit_allows_historical_archive_mentions():
    text = "Historical non-authoritative reference: `docs/archive/wrappers/AGENT_KB_SKILL_RELEASE_LOOP.md`."

    assert "archive_authority_reference" not in _codes(text)


def test_context_audit_flags_duplicate_conventions_and_blank_args():
    text = "Check basis orientation.\n```bash\nartemis validate --strict --ticket\n```"
    codes = _codes(text)

    assert "duplicated_convention_authority" in codes
    assert "blank_required_argument" in codes


def test_context_audit_flags_unknown_artemis_permission_command():
    text = 'permission:\n  bash:\n    "artemis missing command*": allow\n'

    assert "unknown_artemis_permission_command" in _codes(text)
