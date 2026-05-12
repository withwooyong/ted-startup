# Session Handoff

> Last updated: 2026-05-12 (KST) — Phase D-1 ka20006 풀 구현 완료 + 푸시 (`3954185` HEAD).
> Branch: `master` → `origin/master` 동기화 완료
> Latest commit: `3954185` (메타 해시 채움 + master.md sector_id FK 현행화)
> 미푸시 commit: **0 건** — 본 세션 4 commit (`39ca7a3` / `a1e20e0` / `249c277` / `3954185`) 모두 push 완료

## Current Status

**Phase D-1 ka20006 풀 구현 완료** — ted-run 풀 파이프라인 적용 (TDD 38 신규 → 구현 10 파일 → 1R CONDITIONAL → PASS (CRITICAL 3 + HIGH 2 fix) → Verification 5관문 PASS → ADR § 39). 컨테이너 재배포 후 9 scheduler 활성 (sector_daily mon-fri 07:00 KST 신규) / alembic 014 → 015 자동 적용 / sector_price_daily 테이블 생성 / /health OK.

**현재 상태**:
- kiwoom-app container: **Up (healthy)** / 이미지 재빌드 (Migration 015 + 신규 라우터 + 9 scheduler)
- 5-13 (수) 06:00 OhlcvDaily + 06:30 DailyFlow + **07:00 SectorDaily** 첫 발화 예정
- 테스트 1097 cases (1059 + 38 신규) / coverage **90%** / ruff PASS / mypy strict PASS
- **12 / 25 endpoint (48%)** — Phase D 진입 + D-1 종결

## Completed This Session

| # | Task | 결과 | Files |
|---|------|------|-------|
| 1 | 5-11 NXT 보완 백필 + 검증 + ADR § 37 + commit | NXT 74 → 628 / 0 failed / 21m 6s | 4 / `00ac3b0` + `bdc6aef` |
| 2 | Docker 컨테이너 배포 (kiwoom-app) — Dockerfile/entrypoint/uv.lock/compose/README + ADR § 38 | 이미지 264MB / 8 scheduler 활성 / /health OK / 5-13 06:00 첫 발화 준비 | 7 / `550bee5` |
| 3 | 5-12 검증 chunk (docker logs + DB row count) | 컨테이너 healthy / 0 ERROR / 5-12 row=0 (cron 미발화 expected — § 35 새벽 cron 정책) | 0 (검증만) |
| 4 | secret 회전 절차서 작성 + 회전 시점 = 전체 개발 완료 후 (사용자 결정) | 230줄 절차서 + ADR § 38.8 #6/#7 시점 통일 + HANDOFF Pending #2 갱신 | 4 / `39ca7a3` |
| 5 | 작업 방향 재정렬 (§11 정의 명확화) — 사용자 피드백 수용 후 기존 작업방식 유지 결정 | 메모리 3건 추가 (운영 변경 후행/추천 자제/기존 방식 유지) | 0 (메모리만) |
| 6 | Phase D-1 ka20006 plan doc § 12 작성 + STATUS/HANDOFF 갱신 + commit | Migration 015 + 인프라 + 자동화 통합 chunk § (9 결정 + 13 self-check + DoD 10 코드 6 테스트) | 3 / `a1e20e0` |
| 7 | **Phase D-1 ka20006 풀 구현 (ted-run)** — TDD 38 신규 / 구현 10 파일 / 1R CONDITIONAL → PASS / Verification 5관문 PASS / 컨테이너 재배포 / ADR § 39 / 메타 갱신 | 1097 tests / coverage 90% / 9 scheduler 활성 / 12/25 endpoint | 16 / `249c277` |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| **1** | **(5-13 06:00 발화 직후) cron 첫 발화 검증 + § 39.7 운영 모니터** | **다음 chunk 1순위** | OhlcvDaily 06:00 + DailyFlow 06:30 + **SectorDaily 07:00** 5-13 화 첫 발화. § 39.7: sector_daily 첫 호출 + 100배 값 검증 + 페이지네이션 정량화 |
| **2** | Phase E 진입 — ka10014 (공매도) / ka10068 (대차) / ka20068 (대차 종목별) wave | D-2 분봉이 마지막으로 연기 → Phase E 가 다음 endpoint wave | 3 endpoint × Phase B/C 패턴 |
| **3** | **노출된 secret 4건 회전** | **전체 개발 완료 후** | API_KEY/SECRET revoke + Fernet 마스터키 회전 + DB 재암호화 + Docker Hub PAT revoke (ADR § 38.8 #6/#7). 시점 연기: 5-12 사용자 결정. **절차서**: [`docs/ops/secret-rotation-2026-05-12.md`](docs/ops/secret-rotation-2026-05-12.md) |
| **4** | `.env.prod` 의 `KIWOOM_SCHEDULER_*` 9 env 정리 + `SCHEDULER_SECTOR_DAILY_SYNC_ALIAS` 추가 | 전체 개발 완료 후 | compose env override 로 우회 완료. `.env.prod` 편집은 secret 회전 chunk 와 동일 시점 일괄 |
| **5** | (5-19 이후) § 36.5 1주 모니터 측정 채움 | 대기 | 컨테이너 로그 기반 9 scheduler elapsed / NXT 정상 / failed / 알람 |
| **6** | Mac 절전 시 컨테이너 중단 → cron 누락 위험 | 사용자 환경 결정 | 절전 차단 또는 서버 이전 (ADR § 38.8 #1) |
| 7 | D-1 follow-up: inds_cd echo 검증 / close_index Decimal 통일 / `backfill_sector` CLI | ADR § 39.8 | 운영 첫 호출 후 결정 |
| 8 | Phase F / G / H (순위/투자자별/통합) | 대기 | 신규 endpoint wave |
| 9 | Phase D-2 ka10080 분봉 (**마지막 endpoint**) | 대기 | 사용자 결정 (5-12) — 데이터량 부담. 대용량 파티션 결정 동반 |
| 10 | §11 포트폴리오·AI 리포트 (P10~P15) | 대기 | CLAUDE.md next priority — KIS + DART + OpenAI 기반. backend_kiwoom 25 endpoint 완주 후 |

## Key Decisions Made

1. **secret 회전 시점 = 전체 개발 완료 후** (5-12 사용자 결정) — `.env.prod` 편집 + Fernet 마스터키 교체 + DB 재암호화 + 컨테이너 재기동 운영 영향 큼. 절차서 작성 후 연기. [[feedback-ops-changes-after-dev]] 첫 적용.
2. **기존 작업 방식 유지** (5-12 사용자 결정) — backend_kiwoom 25 endpoint 풀 카탈로그 + ted-run 풀 파이프라인 + ADR/STATUS/HANDOFF/CHANGELOG 3종 갱신. 사용자 답답함 표현 후에도 "느리더라도 이대로". [[feedback-keep-existing-workflow]]
3. **Phase D-2 ka10080 분봉 = 마지막 endpoint** (5-12 사용자 결정) — 데이터량 부담 (1100종목 × 380분 = 38만+ rows/일). Phase E/F/G/H 의 모든 endpoint 완주 후 마지막에. 대용량 파티션 결정 동반 chunk 로 분리.
4. **Phase D 첫 endpoint = ka20006 (가장 가벼움)** — 50~80 sector × 1 일봉. ka10081/82/83/94 chart 패턴 1:1 응용 + sector_id FK + NXT skip 단순화.
5. **ka20006 9개 결정** (plan doc § 12.2) — Migration 015 / sector_id FK BIGINT (UNIQUE = `(market_code, sector_code)` 페어 발견 + 1R HIGH #4 INTEGER → BIGINT fix) / centi BIGINT / NXT skip / sector_master_missing 가드 / cron mon-fri 07:00 KST (§ 35 새벽 cron 일관) / 백필 3년 / UseCase 입력 sector_id / chart.py 통합.
6. **1R 추가 결정** — CRITICAL 3건 (main.py 통합 라우터/factory/scheduler/alias 누락) + HIGH 2건 (sector_id BIGINT 통일 / SectorBulkSyncResult.skipped 분리 — sector_inactive 가 failed 로 집계되어 허위 경보 방지) 모두 fix.
7. **D-2 분봉 마지막 연기 유지** — Phase E (공매도/대차) 가 다음 endpoint wave.

## Known Issues

| # | 항목 | 출처 | 결정 |
|---|------|------|------|
| 13 | 일간 cron 실측 (운영 cron elapsed) | dry-run § 20.4 → § 36 / § 38 | 🔄 활성 완료 — 5-13 첫 발화 / 5-19 이후 측정 |
| 20 | NXT 우선주 sentinel 빈 row 1개 detection | § 32.3 + § 33.6 | LOW — 운영 영향 0 |
| ~~21~~ | ~~5-11 NXT 74 rows 보완~~ | § 35.8 | ✅ 해소 (`00ac3b0`) |
| **22** | `.env.prod` 의 `KIWOOM_SCHEDULER_*` 9 env 잘못된 prefix | § 38.6.2' | **전체 개발 완료 후** (5-12) — secret 회전 chunk 와 동일 시점 일괄 (`.env.prod` 편집 운영 영향) |
| **23** | 노출된 secret 4건 회전 | § 38.8 #6/#7 | **전체 개발 완료 후** (5-12 사용자 결정) — 절차서 [`docs/ops/secret-rotation-2026-05-12.md`](docs/ops/secret-rotation-2026-05-12.md) 작성됨 |
| **24** | Mac 절전 시 컨테이너 중단 → cron 누락 | § 38.8 #1 | 사용자 환경 결정 |
| **25** | ka20006 cron 07:00 KST vs 06:30 daily_flow KRX rate limit 경합 | D-1 plan doc § 12.4 H-5 | ted-run 시 기존 KRX lock 으로 직렬화 안전 가정. 운영 첫 발화 시 elapsed 실측 후 재검토 |
| **26** | ka20006 100배 값 가정 운영 검증 미완 | D-1 plan doc § 12.4 H-2 + § 11.2 | ted-run 후 첫 호출 시 KOSPI 종합 응답값 / 100 ≈ 실제 KOSPI 지수 일치 확인. ADR § 39 운영 결과 § 에 기록 |

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
