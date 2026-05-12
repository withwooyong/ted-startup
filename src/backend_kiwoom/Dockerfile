# ---- builder ----
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_COMPILE_BYTECODE=1

# uv 최신 안정 (latest tag)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# 1) 의존성 layer 캐시 — pyproject + uv.lock 만 먼저 복사 (frozen)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen --no-install-project

# 2) 앱 소스 복사 (코드 변경에도 1) layer 캐시 hit)
COPY app/ ./app/
COPY alembic.ini ./
COPY migrations/ ./migrations/
COPY scripts/ ./scripts/
COPY README.md ./

# 3) 프로젝트 자체 설치 (editable — hatchling 가 README.md 요구)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen

# ---- runtime ----
FROM python:3.12-slim AS runtime

# 런타임 OS 의존성 — tzdata (KST cron 정확성 필수)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/Asia/Seoul /etc/localtime \
    && echo Asia/Seoul > /etc/timezone

ENV TZ=Asia/Seoul \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

RUN useradd --uid 1001 --no-create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app && chown appuser:appuser /app

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app /app

USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=3)" || exit 1

# entrypoint — alembic upgrade head 후 uvicorn 단일 worker (APScheduler 중복 발화 방지)
CMD ["python", "scripts/entrypoint.py"]
