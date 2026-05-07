# syntax=docker/dockerfile:1.7

# ---- builder ----
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# uv 0.11 (digest pinning)
COPY --from=ghcr.io/astral-sh/uv:0.11@sha256:240fb85a93b27ac02b3e6f3b21a4c4e6d2f8c3e5a82b9c5e3f4a7d1b9c8e6a5f /uv /usr/local/bin/uv

WORKDIR /app

# 의존성 먼저 복사 — Docker 레이어 캐시 활용
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

COPY app/ ./app/
COPY alembic.ini ./
COPY migrations/ ./migrations/
COPY scripts/ ./scripts/

RUN uv sync --no-dev

# ---- runtime ----
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN useradd --uid 1001 --no-create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app && chown appuser:appuser /app

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app /app

USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=3)" || exit 1

CMD ["python", "scripts/entrypoint.py"]
