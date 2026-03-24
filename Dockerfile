FROM python:3.12-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock alembic.ini README.md ./
COPY alembic ./alembic
COPY src ./src
COPY scripts ./scripts
COPY docker/backend/entrypoint.sh /app/docker/backend/entrypoint.sh

RUN uv sync --frozen --no-dev

RUN chmod +x /app/docker/backend/entrypoint.sh

ENV PYTHONPATH=/app/src \
    DEBUG=false \
    APP_PORT=8000

EXPOSE 8000

CMD ["/app/docker/backend/entrypoint.sh"]
