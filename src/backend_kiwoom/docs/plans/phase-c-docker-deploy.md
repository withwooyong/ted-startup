# Phase C — Docker 컨테이너 배포 (kiwoom-app service)

> 작성: 2026-05-12 KST / 후속: ADR § 38

## 1. 배경

§ 36 scheduler 활성 (`.env.prod` 9 env) 후 사용자 앱 재시작이 필요했으나, 현재 backend_kiwoom 은:

- ❌ Dockerfile 없음
- ❌ docker-compose 에 앱 service 정의 없음 (`kiwoom-db` 만 있음)
- ❌ uvicorn 프로세스 실행 안 됨
- ❌ systemd / launchd 정의 없음

즉 "재시작" 이 아니라 **앱 운영 인프라 신규 구축** 이 필요한 상태. 사용자 결정 (2026-05-12) — docker-compose 새 service 추가 후 컨테이너 운영 (옵션 C).

## 2. 목표

5-13 (수) 06:00 KST OhlcvDaily cron 발화 전 backend_kiwoom 앱을 docker-compose 컨테이너로 안정 기동. ADR § 36.5 1주 모니터 chunk 의 정합성 보장.

## 3. 산출물

| 파일 | 동작 |
|------|------|
| `src/backend_kiwoom/Dockerfile` | **신규** — Python 3.14-slim + uv 멀티스테이지 빌드 + non-root |
| `src/backend_kiwoom/.dockerignore` | **신규** — .venv / __pycache__ / logs / .env / tests / docs 제외 |
| `src/backend_kiwoom/docker-compose.yml` | **갱신** — `kiwoom-app` service 추가 (env_file / depends_on / healthcheck / restart=unless-stopped) |
| `src/backend_kiwoom/uv.lock` | **신규** — `uv lock` 결정론적 의존성 |
| `src/backend_kiwoom/README.md` | **갱신** — `## Docker 운영` 섹션 추가 |

## 4. 핵심 설계 결정

### 4.1 멀티스테이지 빌드 (builder + runtime)

- **builder** — `python:3.14-slim-bookworm` + uv + `uv sync --no-dev --frozen` (`/opt/venv` 격리)
- **runtime** — `python:3.14-slim-bookworm` + venv 복사 + curl (healthcheck) + tzdata (Asia/Seoul) + non-root user (uid 1000)
- 빌드 캐시 layer: `pyproject.toml + uv.lock` → 의존성 layer (코드 변경에도 캐시 hit)

### 4.2 DB hostname 처리 — compose environment override

- `.env.prod` 의 `KIWOOM_DATABASE_URL` = `localhost:5433` (호스트에서 스크립트 직접 실행용 — 유지)
- 컨테이너 안에서는 compose `environment:` 의 `KIWOOM_DATABASE_URL=kiwoom-db:5432` 로 override
- pydantic-settings 우선순위 (OS env > .env > .env.prod) 활용 — `.env.prod` 수정 없이 두 모드 공존

### 4.3 alembic 자동 마이그레이션 (entrypoint)

- CMD = `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 1`
- backend_kiwoom Migration 014 까지 모두 idempotent + 비파괴 → 컨테이너 기동마다 자동 적용 안전
- 운영 위험: 미래 destructive migration 도입 시 본 entrypoint 우회 필요. ADR § 38.8 follow-up 명시

### 4.4 단일 worker (uvicorn `--workers 1`)

- APScheduler 가 1 프로세스에서만 실행되어야 — 다중 worker 시 cron 중복 발화 위험
- 처리량 부족 시 별도 chunk 에서 멀티 worker + 외부 scheduler (Celery / Redis lock) 분리 검토

### 4.5 .env.prod 처리

- `.env.prod` 는 compose `env_file:` 로 변수만 주입 (마운트 없음, 이미지에 포함 없음)
- 보안 — Dockerfile / 이미지에는 `.env.prod` 없음. `.dockerignore` 에서 명시적 제외

### 4.6 healthcheck

- `curl -fsS http://localhost:8001/health` (또는 라우터 root)
- interval 30s / timeout 5s / retries 5 / start_period 30s (lifespan + alembic 시간 고려)

### 4.7 비-root user

- `useradd -m -u 1000 appuser` + 모든 앱 경로 chown
- 컨테이너 내부 escalation 방어

## 5. 변경 면

### 5.1 신규 파일

#### `Dockerfile` (~50줄)

builder → runtime 멀티스테이지. 캐시 layer 분리. non-root + tzdata Asia/Seoul + uvicorn 1 worker.

#### `.dockerignore` (~20줄)

`.venv` / `__pycache__` / `.pytest_cache` / `.mypy_cache` / `.ruff_cache` / `htmlcov` / `.coverage` / `logs/` / `.env*` / `tests/` / `docs/` / `*.md` / `.git`

#### `uv.lock` (생성)

`uv lock` 1회 실행 → 결정론적 의존성. 향후 `uv sync --frozen` 에서 사용.

### 5.2 갱신 파일

#### `docker-compose.yml` — `kiwoom-app` service 추가

```yaml
services:
  kiwoom-db:
    # (기존 유지)

  kiwoom-app:
    build:
      context: .
      dockerfile: Dockerfile
    image: kiwoom-app:latest
    container_name: kiwoom-app
    env_file:
      - .env.prod
    environment:
      KIWOOM_DATABASE_URL: "postgresql+asyncpg://kiwoom:kiwoom@kiwoom-db:5432/kiwoom_db"
      KIWOOM_DEFAULT_ENV: prod
      KIWOOM_SCHEDULER_ENABLED: "true"
      TZ: Asia/Seoul
    depends_on:
      kiwoom-db:
        condition: service_healthy
    ports:
      - "8001:8001"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8001/health || exit 1"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 30s
```

#### `README.md` — `## Docker 운영` 섹션 추가

```markdown
## Docker 운영

```bash
cd src/backend_kiwoom
docker compose build kiwoom-app
docker compose up -d kiwoom-app
docker compose logs -f kiwoom-app  # lifespan + scheduler 활성 확인
```

기동 검증:
- `docker compose ps` — kiwoom-app Up (healthy)
- `docker compose logs kiwoom-app | grep scheduler` — 8 scheduler 활성 로그
- `curl http://localhost:8001/health` — 200 OK
```

## 6. 위험 분석

| # | 위험 | 영향 | 완화 |
|---|------|------|------|
| 1 | uv.lock 생성 시 의존성 해결 차이 | 호스트 vs 컨테이너 버전 불일치 | 호스트에서 `uv lock` 1회 실행 후 git 커밋. 향후 동일 lock 사용 |
| 2 | alembic 자동 마이그레이션 destructive migration 시 데이터 손실 | DB 손상 | 014 까지 모두 idempotent + 비파괴. 미래 migration 도입 시 entrypoint 검토 (§ 38.8) |
| 3 | 다중 worker 시 APScheduler 중복 발화 | cron 2회 발화 | `--workers 1` 명시. 처리량 부족 시 별도 chunk 에서 외부 scheduler |
| 4 | container DB 접근 시 호스트 직접 접근과 충돌 | 동시 운영 시 락 충돌 | 호스트 스크립트 직접 실행은 백필 등 ad-hoc 작업에만 — 운영 cron 은 컨테이너만 |
| 5 | 5-13 06:00 cron 발화 전 컨테이너 기동 실패 | 첫 발화 누락 → § 36.5 측정 일자 1일 이월 | Phase 3 검증에서 lifespan + scheduler 활성 확인. 실패 시 즉시 디버그 |
| 6 | Mac 절전 시 컨테이너 중단 | cron 발화 누락 | 운영 PC 절전 차단 또는 서버 이전. 본 chunk 범위 외 (§ 38.8) |

## 7. DoD (Definition of Done)

- [ ] `Dockerfile` + `.dockerignore` + `uv.lock` 신규
- [ ] `docker-compose.yml` 에 `kiwoom-app` service 추가
- [ ] `docker compose build kiwoom-app` 성공 (이미지 빌드 PASS)
- [ ] `docker compose up -d kiwoom-app` 성공 (컨테이너 Up healthy)
- [ ] lifespan fail-fast 통과 로그 확인 (8 scheduler 활성)
- [ ] `curl http://localhost:8001/health` (또는 라우터) 응답 OK
- [ ] `docker compose logs kiwoom-app | grep scheduler` — 8 scheduler 등록 확인
- [ ] README.md `## Docker 운영` 섹션 추가
- [ ] ADR § 38 작성
- [ ] STATUS § 0 / § 4 / § 6 갱신
- [ ] CHANGELOG prepend
- [ ] HANDOFF overwrite
- [ ] commit (push 는 사용자 명시 요청 시)

## 8. 다음 chunk

1. **(다음 영업일 ~ 1주 모니터)** 컨테이너 운영 안정성 관찰. 자동 재시작 / 메모리 누수 / 로그 누적 검사
2. **(5-19 이후)** § 36.5 1주 모니터 측정 결과 채움 — 컨테이너 로그 기반 cron elapsed 추출
3. **Mac 절전 정책 / 서버 이전** — 본 chunk follow-up. 24/7 cron 안정성 위함
4. **destructive migration 도입 시 entrypoint 분리** — 자동 마이그레이션 정책 재검토
