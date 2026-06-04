#!/usr/bin/env bash
set -euo pipefail

echo "[post-agent] running tests"
python -m pytest -q

echo "[post-agent] changed files"
git status --short

echo "[post-agent] diff summary"
git diff --stat
