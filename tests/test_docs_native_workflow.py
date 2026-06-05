from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_native_workflow_docs_exist_and_name_required_commands():
    paths = [
        ROOT / "docs" / "developer" / "native_workflow.md",
        ROOT / "docs" / "developer" / "local_agent_loop.md",
        ROOT / "docs" / "user" / "setup.md",
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "artemis validate" in text


def test_docs_state_github_is_remote_only():
    text = (ROOT / "docs" / "developer" / "native_workflow.md").read_text(encoding="utf-8")

    assert "GitHub is a plain remote" in text
    assert "GitHub Actions, Issues, Projects, or PR" in text
    assert ".github/workflows" not in text
