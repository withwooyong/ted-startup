FROM python:3.12-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# uv 바이너리는 digest 로 고정해 공급망 공격(태그 재지정) 방어.
# 업그레이드 시 `docker buildx imagetools inspect ghcr.io/astral-sh/uv:<ver>` 로
# Index digest 를 확인해 교체한다. 이 digest 는 multi-arch index 이므로 amd64/arm64
# 모두 검증된 단일 매니페스트를 가리킨다.
COPY --from=ghcr.io/astral-sh/uv:0.11@sha256:240fb85ab0f263ef12f492d8476aa3a2e4e1e333f7d67fbdd923d00a506a516a /uv /usr/local/bin/uv

WORKDIR /app

# 의존성만 먼저 설치(캐시 활용). uv.lock이 있어야 재현성 보장 — frozen 강제.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY app ./app
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
COPY scripts ./scripts
COPY README.md ./
RUN uv sync --frozen --no-dev

# ---- Runtime stage ----
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# 애플리케이션은 Python 만 실행. 인터랙티브 셸 진입 경로를 원천 차단하기 위해
# 로그인 셸을 /usr/sbin/nologin 으로 설정. 컨테이너 내부 진단은
# `docker compose exec -u root backend /bin/sh` 로 root 진입 후 수행.
RUN useradd --create-home --shell /usr/sbin/nologin --uid 1001 appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,sys; r=urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3); sys.exit(0 if r.status==200 else 1)"

# Alembic 선실행 후 uvicorn 기동 — 레거시 Java 스키마와의 호환 처리 포함.
CMD ["python", "scripts/entrypoint.py"]
