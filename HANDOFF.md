# Session Handoff

> Last updated: 2026-05-12 (KST, /handoff) — Docker 컨테이너 배포 (kiwoom-app, ADR § 38).
> Branch: `master`
> Latest commit: `550bee5` (Docker 배포 — Dockerfile / entrypoint / uv.lock / compose / ADR § 38)
> 미푸시 commit: **3 건** (`00ac3b0` 5-11 NXT 보완 + `bdc6aef` 메타 해시 + `550bee5` Docker 배포 — 사용자 명시 요청 시 push)

## Current Status

**kiwoom-app 컨테이너 운영 진입** — § 36 scheduler 활성 후 사용자 앱 재시작 필요했으나 backend_kiwoom 의 운영 인프라가 미완성 상태였음. 본 chunk 에서 Dockerfile + entrypoint + uv.lock + compose service 일괄 구축 + 빌드 + 기동 검증.

**현재 상태**:
- kiwoom-app container: **Up (healthy)** / 이미지 264MB
- 8 scheduler 활성 (sector / stock_master / fundamental / ohlcv_daily / daily_flow / weekly / monthly / yearly) — cron 시각 모두 정확
- /health: `{"status":"ok"}` / TZ: Asia/Seoul (KST 정확)
- **5-13 (수) 06:00 KST OhlcvDaily 첫 발화 예정**

## Completed This Session

| # | Task | 결과 | Files |
|---|------|------|-------|
| 1 | 5-11 NXT 보완 백필 + 검증 + ADR § 37 + commit | NXT 74 → 628 / 0 failed / 21m 6s | 4 / `00ac3b0` + `bdc6aef` |
| 2 | 다음작업 분석 → 앱 재시작 → Docker 인프라 결정 (옵션 C) | 7 follow-up 옵션 비교 + 컨테이너 인프라 chunk 선택 | 0 |
| 3 | Phase 1 — 사전 분석 + plan doc | pyproject 의존성 / lifespan / Settings env_file / DB hostname 영향 면 | 1 (plan doc) |
| 4 | Phase 2 — Dockerfile + .dockerignore + entrypoint + uv.lock + compose | multi-stage builder+runtime / non-root / tzdata / SCHEDULER_* env override | 5 |
| 5 | Phase 3 — 빌드 hang 2건 진단 + 해결 + 기동 + 검증 | credsStore osxkeychain fix / syntax directive 제거 / README COPY 추가 / 264MB / 8 scheduler 활성 | 2 ($HOME/.docker/config.json 외) |
| 6 | Phase 4 — ADR § 38 + STATUS § 0/§ 4/§ 6 + CHANGELOG + HANDOFF + commit | 본 commit | 4 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| **1** | **(5-13 06:00 발화 직후) cron 발화 결과 즉시 검증** | **다음 chunk 1순위** | `docker compose logs kiwoom-app` + DB SQL — 5-13 NXT trading_date row count 등 |
| **2** | **노출된 secret 4건 회전** | **전체 개발 완료 후** | API_KEY/SECRET revoke + Fernet 마스터키 회전 + DB 재암호화 + Docker Hub PAT revoke (ADR § 38.8 #6/#7). **시점 연기**: 2026-05-12 사용자 결정 — `.env.prod` / DB 재암호화 영향이 커서 개발/테스트/검증 종결 후 일괄. **절차서**: [`docs/ops/secret-rotation-2026-05-12.md`](docs/ops/secret-rotation-2026-05-12.md) |
| **3** | `.env.prod` 의 `KIWOOM_SCHEDULER_*` 9 env 정리 | 사용자 직접 | compose env override 로 우회 완료. .env.prod 정리는 별도 |
| **4** | (5-19 이후) § 36.5 1주 모니터 측정 채움 | 대기 | 컨테이너 로그 기반 cron elapsed / NXT 정상 / failed / 알람 |
| **5** | Mac 절전 시 컨테이너 중단 → cron 누락 위험 | 사용자 환경 결정 | 절전 차단 또는 서버 이전 (ADR § 38.8 #1) |
| 6 | Phase D — ka10080 분봉 / ka20006 업종일봉 | 대기 | 대용량 파티션 결정 선행 |
| 7 | 공휴일 calendar / NXT scheduler 분리 | 대기 | 1주 모니터 후 |
| 8 | §11 포트폴리오·AI 리포트 (P10~P15) | 대기 | CLAUDE.md next priority |

## Key Decisions Made

1. **Docker 인프라 신규 구축 (옵션 C)** — 단순 "재시작" 이 아니라 backend_kiwoom 앱 운영 인프라 신규 구축. plan doc + Dockerfile + entrypoint + uv.lock + compose service + README 전부 작성.
2. **builder + runtime 2-stage Dockerfile** — python:3.12-slim + uv `--frozen` + non-root uid 1001 + tzdata Asia/Seoul. 이미지 264MB.
3. **자동 alembic 마이그레이션 (entrypoint)** — 014 까지 idempotent + 비파괴 → 기동마다 자동 적용 안전. destructive migration 도입 시 분리 (§ 38.8 #2).
4. **uvicorn `--workers 1`** — APScheduler 중복 발화 방지. 처리량 한계 도달 시 외부 scheduler 별도 chunk.
5. **DB hostname compose environment override** — `.env.prod` 의 `localhost:5433` 은 호스트 스크립트용 유지 + 컨테이너는 `kiwoom-db:5432` override. pydantic-settings 우선순위 (OS env > .env > .env.prod) 활용.
6. **credsStore osxkeychain** — Docker Desktop credential helper hang 회피. 사용자 `~/.docker/config.json` 갱신.
7. **`.env.prod` env_prefix 불일치 우회** — compose `environment:` 에 `SCHEDULER_*` 8 env 명시. `.env.prod` 의 잘못된 `KIWOOM_SCHEDULER_*` 9 env 는 `extra="ignore"` 로 무시. 사용자 정리는 별도 (§ 38.8 #5).

## Known Issues

| # | 항목 | 출처 | 결정 |
|---|------|------|------|
| 13 | 일간 cron 실측 (운영 cron elapsed) | dry-run § 20.4 → § 36 / § 38 | 🔄 활성 완료 — 5-13 첫 발화 / 5-19 이후 측정 |
| 20 | NXT 우선주 sentinel 빈 row 1개 detection | § 32.3 + § 33.6 | LOW — 운영 영향 0 |
| ~~21~~ | ~~5-11 NXT 74 rows 보완~~ | § 35.8 | ✅ 해소 (`00ac3b0`) |
| **22** | `.env.prod` 의 `KIWOOM_SCHEDULER_*` 9 env 잘못된 prefix | § 38.6.2' | 사용자 직접 (compose env override 로 우회) |
| **23** | 노출된 secret 4건 회전 | § 38.8 #6/#7 | **전체 개발 완료 후** (5-12 사용자 결정) — 절차서 [`docs/ops/secret-rotation-2026-05-12.md`](docs/ops/secret-rotation-2026-05-12.md) 작성됨 |
| **24** | Mac 절전 시 컨테이너 중단 → cron 누락 | § 38.8 #1 | 사용자 환경 결정 |

## Context for Next Session

### 다음 세션 진입 (5-13 06:30 KST 이후) 시 즉시 할 일

```bash
# 1) cron 발화 확인 — OhlcvDaily (06:00) + DailyFlow (06:30) 5-13 화 첫 발화
docker compose logs kiwoom-app 2>&1 | grep -E "sync cron 시작|sync 완료|실패율 과다|콜백 예외"

# 2) DB 적재 확인 — 5-12 (화) 데이터가 5-13 (수) 06:00 cron 으로 적재됨 (base_date previous_business_day)
psql -h localhost -p 5433 -U kiwoom -d kiwoom_db -c "
SELECT trading_date, count(*) FROM kiwoom.stock_price_krx WHERE trading_date >= DATE '2026-05-12' GROUP BY trading_date ORDER BY trading_date;
SELECT trading_date, count(*) FROM kiwoom.stock_price_nxt WHERE trading_date >= DATE '2026-05-12' GROUP BY trading_date ORDER BY trading_date;
"

# 3) 컨테이너 상태 + 메모리
docker compose ps
docker stats kiwoom-app --no-stream
```

기대:
- KRX 5-12 row count ~4370 / NXT 5-12 row count ~628 (5-11 보완 패턴과 일관)
- failed 0 / WARN/ERROR 0
- 컨테이너 메모리 안정 (~300MB 이하)

이상 발견 시 (`failed > 0` / row count anomaly / OOM 등) 즉시 분석 + ADR 새 § 추가.

### 사용자의 의도 (본 세션)

"앱 재시작" → 실제로는 "신규 인프라 구축" 발견. "운영 정합성 우선: A (지금 chunk 진행). 5-13 cron 발화 + § 36.5 측정 본 사이클 진행이 ADR § 36 결정과 정합. 1.5시간 투자." — 1.5시간 chunk 예상이 실제로는 ~3시간 (credsStore hang 1시간 + 재빌드 1시간 + 진단/fix). 빌드 hang 2건 + env_prefix 1건 추가 발견 + 해결로 본 chunk 깊이 더 커짐.

### 채택한 접근

1. **plan doc 사전** — Docker 인프라 결정 사항 명시 (DB hostname / alembic / single worker / env_file 처리)
2. **multi-stage Dockerfile** — builder + runtime 분리. 빌드 캐시 효율 + 이미지 264MB slim
3. **uv.lock 신규** — 결정론적 빌드. `--frozen` 으로 호스트/컨테이너 동일 버전
4. **빌드 hang 2건 fix 후 진행** — credsStore osxkeychain (CRITICAL) + syntax directive 제거. 두 번째 fix 후 정상 빌드
5. **env_prefix 불일치 compose override** — `.env.prod` 수정 없이 compose `environment:` 8 env. 사용자 .env.prod 정리는 별도 (§ 38.8 #5)
6. **단일 commit** — 본 chunk 전체 + ADR § 38 + STATUS + CHANGELOG + HANDOFF

### 운영 위험 / 주의

- **5-13 06:00 첫 cron 발화 ETA**: 17시간 후. 그동안 Mac 절전 차단 필요. 노트북 마감 시 컨테이너 중단 → 발화 누락
- **secret 4건 노출**: 대화 로그 영구 기록. 사용자 즉시 회전 필수
- **`.env.prod` 정리 안 하면 다음 운영자 혼란**: 잘못된 9 env 그대로 두면 의미 없는 환경변수가 .env.prod 에 남음. follow-up 정리 권장
- **`uv.lock` 첫 generation**: 87 packages. 향후 의존성 변경 시 `uv lock` + `docker compose build` 재실행 필요

## Files Modified This Session

### 5 신규
- `src/backend_kiwoom/scripts/entrypoint.py`
- `src/backend_kiwoom/uv.lock`
- `src/backend_kiwoom/docs/plans/phase-c-docker-deploy.md`
- (commit 외부) `~/.docker/config.json` credsStore 변경

### 5 갱신
- `src/backend_kiwoom/Dockerfile`
- `src/backend_kiwoom/.dockerignore`
- `src/backend_kiwoom/docker-compose.yml`
- `src/backend_kiwoom/README.md`
- `docs/adr/ADR-0001-backend-kiwoom-foundation.md` § 38 신규
- `src/backend_kiwoom/STATUS.md` § 0 / § 4 / § 6
- `CHANGELOG.md` prepend
- `HANDOFF.md` (본 파일)

### Verification

- 빌드 PASS — 이미지 264MB
- alembic 자동 마이그레이션 — 014 까지 적용
- 8 scheduler 활성 — cron 시각 모두 정확
- /health — `{"status":"ok"}`
- 컨테이너 TZ — KST 정확
- 컨테이너 상태 — Up (healthy)
- 앱 코드 변경 0 — 1059 tests 그대로

---

_Docker 컨테이너 운영 진입 chunk 종결. 5-13 06:00 첫 cron 발화 후 검증 chunk → 5-19 이후 § 36.5 측정 → Phase D._
