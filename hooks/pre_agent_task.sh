#!/usr/bin/env bash
set -euo pipefail

echo "[pre-agent] checking git state"
git status --short

echo "[pre-agent] running baseline tests"
python -m pytest -q
