#!/usr/bin/env bash
set -euo pipefail

cd /app

python - <<'PY'
import os
import socket
import time
import urllib.parse


def wait_for_tcp(url_env: str, default_host: str, default_port: int, label: str) -> None:
    raw = os.getenv(url_env, "")
    parsed = urllib.parse.urlparse(raw) if raw else None
    host = parsed.hostname if parsed and parsed.hostname else default_host
    port = parsed.port if parsed and parsed.port else default_port
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"{label} is ready at {host}:{port}")
                return
        except OSError:
            time.sleep(1)
    raise RuntimeError(f"Timed out waiting for {label} at {host}:{port}")


wait_for_tcp("DB_POSTGRES_URL_ASYNC", "postgres", 5432, "PostgreSQL")
wait_for_tcp("S3_ENDPOINT", "minio", 9000, "MinIO")
wait_for_tcp("QDRANT_URL", "qdrant", 6333, "Qdrant")
PY

./.venv/bin/alembic upgrade head
exec ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT:-8000}"
