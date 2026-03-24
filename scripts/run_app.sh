#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UVICORN_BIN="$ROOT_DIR/.venv/bin/uvicorn"

if [[ ! -x "$UVICORN_BIN" ]]; then
  echo "Uvicorn executable not found: $UVICORN_BIN" >&2
  exit 1
fi

cd "$ROOT_DIR"
export PYTHONPATH=src
export DEBUG="${DEBUG:-false}"

"$UVICORN_BIN" app.main:app --host 0.0.0.0 --port "${APP_PORT:-8000}" --reload
