#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
ALEMBIC_BIN="$ROOT_DIR/.venv/bin/alembic"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Python virtualenv not found: $VENV_PYTHON" >&2
  exit 1
fi

if [[ ! -x "$ALEMBIC_BIN" ]]; then
  echo "Alembic executable not found: $ALEMBIC_BIN" >&2
  exit 1
fi

cd "$ROOT_DIR"
export PYTHONPATH=src

"$ALEMBIC_BIN" upgrade head
