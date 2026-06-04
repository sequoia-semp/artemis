#!/usr/bin/env sh
set -eu

VENV="${VENV:-.venv}"
BOOTSTRAP_PYTHON="${BOOTSTRAP_PYTHON:-python3}"

if [ ! -x "$VENV/bin/python" ]; then
  "$BOOTSTRAP_PYTHON" -m venv "$VENV"
fi

if ! "$VENV/bin/python" -m pip --version >/dev/null 2>&1; then
  "$VENV/bin/python" -m ensurepip --upgrade
fi

"$VENV/bin/python" -m pip install -e '.[dev]'
