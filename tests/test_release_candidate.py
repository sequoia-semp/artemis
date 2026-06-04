from __future__ import annotations

from pathlib import Path

from pga_workbench.dev.release import build_release_candidate


ROOT = Path(__file__).resolve().parents[1]


def test_release_candidate_schema_validates():
    candidate = build_release_candidate(ROOT, "T-0018")

    assert candidate["id"] == "RC-0.2.0-T-0018"
    assert candidate["source_branch"]
    assert candidate["requires_human_review"] is True
    assert candidate["approved"] is False
