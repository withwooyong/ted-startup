# ted-signal-backend (Python)

Spring Boot → Python 이전 대상(Phase 1 스캐폴딩 시점). 상세 계획은 `docs/migration/java-to-python-plan.md`.

## 요구사항
- Python 3.12+
- uv (패키지 매니저): `curl -LsSf https://astral.sh/uv/install.sh | sh`

## 로컬 실행

```bash
cd src/backend_py
uv sync --extra dev            # 의존성 설치 (venv 자동 생성)
uv run uvicorn app.main:app --reload --port 8000
```

- 헬스체크: http://127.0.0.1:8000/health
- Prometheus 메트릭: http://127.0.0.1:8000/metrics
- OpenAPI: http://127.0.0.1:8000/docs

## 테스트

```bash
uv run pytest
```

## 린트 / 타입

```bash
uv run ruff check .
uv run ruff format .
uv run mypy app
```

## 구조 (Hexagonal)

```
app/
  api/            # FastAPI 라우터 모음(얇은 adapter)
  adapter/
    in/           # inbound adapter (HTTP/CLI/Scheduler)
    out/          # outbound adapter (DB/외부 API/Telegram)
  application/    # UseCase 구현, 서비스, port 인터페이스(Protocol)
  domain/         # Entity·Value Object·Enum (프레임워크 미의존)
  config/         # 설정·DI·로깅·시크릿
  batch/          # APScheduler 잡 정의
tests/            # pytest
```
