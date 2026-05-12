# Changelog

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/).

## [Unreleased]

---

## [2026-05-12] docs(plan): Phase D-1 ka20006 plan doc § 12 + STATUS/HANDOFF 갱신 (ted-run 대기)

§ 38 Docker 배포 + § 39-prep secret 회전 절차서 작성 후 Phase D 진입. ka10080 분봉은 사용자 결정 (5-12) 으로 마지막 endpoint 로 연기 → ka20006 업종일봉 (가장 가벼운 endpoint) 이 Phase D 첫 chunk. 본 chunk 는 ted-run 진입 전 plan doc § 12 작성 + STATUS/HANDOFF 갱신.

### 1. 신규 / 갱신 파일

- **갱신** `src/backend_kiwoom/docs/plans/endpoint-13-ka20006.md` — § 12 신규 (Migration 015 + 인프라 + 자동화 통합 chunk). 953 → ~1160줄. 9 결정 + 13 self-check + DoD 10 코드 6 테스트 + 다음 chunk + 운영 모니터
- **갱신** `src/backend_kiwoom/STATUS.md` — § 0 (Phase D 진입 / 마지막 chunk / 다음 chunk) / § 1 (Phase D 진척 🔄 + D-1 plan doc ✅) / § 2.2 (ka20006 진행중 1건 추가) / § 2.3 (ka10080 연기 표기) / § 5 (D-1 ted-run 1순위) / § 6 (chunk 2건 추가 — secret 회전 절차서 + 본 plan doc)
- **갱신** `HANDOFF.md` — Last updated / Current Status (Phase D 진입) / Completed 6건 (5-11 NXT 보완 / Docker 배포 / 5-12 검증 / secret 절차서 / 방향 재정렬 / 본 chunk) / Pending 9건 재구성 (D-1 ted-run 1순위) / Key Decisions 5건 / Known Issues 2건 추가 (#25 KRX rate limit 경합 / #26 100배 값 가정)

### 2. 핵심 결정 9건 (plan doc § 12.2)

| # | 결정 |
|---|------|
| 1 | Migration **015** (`015_sector_price_daily`, 22 chars) |
| 2 | sector 매핑 = **`sector_id` FK** (sector.py L31 의 UNIQUE `(market_code, sector_code)` 페어 발견 → `inds_cd` 단독 lookup 불가) |
| 3 | 100배 값 = **centi BIGINT** + read property (KRX 정수 단위 일관) |
| 4 | NXT 호출 = **skip** (`nxt_sector_not_supported`) |
| 5 | sector_master_missing 가드 (gap-filler 미적용) |
| 6 | 응답 7 필드 (pred_pre / pred_pre_sig / trde_tern_rt 부재 → None 영속화) |
| 7 | cron = **mon-fri 07:00 KST** (§ 35 새벽 cron 정책 일관, ohlcv_daily 06:00 + daily_flow 06:30 직후) |
| 8 | 백필 윈도 = **3년** (`scripts/backfill_sector.py` CLI 신규) |
| 9 | UseCase 입력 = **sector_id** (PK) — sector_code 단독 충돌 가능성 차단 |

### 3. 적대적 self-check 13건 (plan doc § 12.4)

H-1 sector 매핑 정확성 / H-2 100배 값 가정 운영 미검증 / H-3 list key `inds_dt_pole_qry` 미검증 / H-4 upd_stkpc_tp 부재 자체 보정 가정 / H-5 cron 07:00 KRX rate limit 경합 / H-6 sector_master_missing 가드 / H-7 NXT skip 정책 정확성 / H-8 페이지네이션 미정량화 / H-9 inds_cd length 응답 vs 요청 / H-10 거래대금 단위 백만원 가정 / H-11 scheduler_enabled 정책 일관성 / H-12 Migration 015 비파괴 / H-13 chart.py 통합 vs sect.py 분리

### 4. 영향

- 코드 변경 0 (plan doc / 갱신 문서만)
- 테스트 1059 그대로 / coverage 91% 그대로
- 다음 chunk = D-1 ted-run 풀 파이프라인 (TDD → 구현 → 1R → Verification → ADR § 39 → 커밋)

---

## [2026-05-12] docs(ops): secret 회전 절차서 + 회전 시점 = 전체 개발 완료 후 (사용자 결정)

§ 38 Docker 배포 후 새벽 검증 전 chunk 결정. ADR § 38.8 #6 (노출 secret 4건) + #7 (Docker Hub PAT) 의 회전 절차서를 작성하면서, 회전 실행 시점은 사용자 결정에 따라 "전체 개발 / 테스트 / 검증 종료 후" 로 연기.

### 1. 신규 / 갱신 파일

- **신규** `docs/ops/secret-rotation-2026-05-12.md` — 230줄. 배경 / 회전 순서 / 사전 준비 / 단계별 회전 (Docker PAT → KIWOOM_*KEY → Fernet 마스터키 → ACCOUNT_NO) / 검증 / 롤백 / 완료 체크리스트 / 보안 권고 / 의존성 다이어그램
- **갱신** `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` — § 38.8 #6/#7 결정 시점 "사용자 즉시" → "전체 개발 완료 후 (2026-05-12 사용자 결정)" + 절차서 링크 추가
- **갱신** `HANDOFF.md` — Pending #2 / Known Issues #23 시점 변경 + 절차서 링크 추가

### 2. 사용자 결정 (2026-05-12)

`.env.prod` 편집 + Fernet 마스터키 교체 + DB 재암호화 + 컨테이너 재기동은 운영 영향이 크고 비가역. 개발 chunk 중간에 회전하면 후속 개발이 회전된 환경에 영향받음 → 디버깅 복잡도 ↑. 노출 위험은 존재하나 실제 침해 정황은 없음 → 회전 시점이 오면 본 절차서를 그대로 따라 수행.

### 3. 절차서 핵심 설계

- **회전 순서 의존성 다이어그램** — Docker PAT (독립) → KIWOOM_APPKEY/SECRETKEY (키움 콘솔) → Fernet 마스터키 (KIWOOM_*KEY 회전 직후 = 동일 plaintext 재암호화 1회) → ACCOUNT_NO (선택)
- **재암호화 단순화** — DB row 가 `alias=prod` 1개뿐이라 `register_credential.py` 재호출 (upsert) 로 회전 마이그레이션 스크립트 부재 (ADR § 3.4) 우회
- **secret 값 비기록 원칙** — 실제 값은 사용자 shell / `.env.prod` 에만 존재. 절차서엔 변수명/구조/명령만
- **롤백 가능 시점** — Fernet 회전 단계 완료 전까지. 백업 SQL 경유 복원 가능

### 4. 영향

- 코드 변경 0 (운영 절차서 chunk)
- 테스트 1059 그대로 / coverage 91% 그대로
- backend_kiwoom STATUS.md § 0~6 어떤 섹션도 직접 변경 없음 (§ 1.5 예외 — 단순 운영 절차서)

---

## [2026-05-12] ops(kiwoom): Docker 컨테이너 배포 — kiwoom-app service (ADR § 38)

§ 36 scheduler 활성 후 사용자 앱 재시작이 필요했으나 backend_kiwoom 의 운영 인프라 자체가 미완성 (Dockerfile 5/7 작성 후 entrypoint 누락, compose 에 앱 service 없음). 사용자 결정 (옵션 C) — docker-compose 새 service 추가 + 컨테이너 운영. 5-13 06:00 KST 첫 cron 발화 전 완성.

### 1. 신규 / 갱신 파일

- **신규** `scripts/entrypoint.py` — `alembic upgrade head` → `os.execvp uvicorn` (workers=1)
- **신규** `uv.lock` — 87 packages frozen
- **신규** `docs/plans/phase-c-docker-deploy.md`
- **갱신** `Dockerfile` — syntax directive 제거 / uv:latest / `--frozen` 추가 / tzdata Asia/Seoul / `COPY README.md`
- **갱신** `.dockerignore` — .venv / __pycache__ / logs / .env* / tests / docs / *.md 제외 (`!README.md` 예외)
- **갱신** `docker-compose.yml` — `kiwoom-app` service 추가 (env_file=`../../.env.prod` / `SCHEDULER_*` 8 env override / depends_on kiwoom-db healthy / restart=unless-stopped / ports 8001)
- **갱신** `README.md` — `## Docker 운영` 섹션 5단계 명령 + 운영 메모
- **갱신** `~/.docker/config.json` — credsStore `desktop` → `osxkeychain` (빌드 hang fix)

### 2. 빌드 / 기동 결과

- 이미지 264MB / 빌드 PASS (sha256:90629d12dc3b...)
- alembic 자동 마이그레이션 (Migration 012→013→014 첫 적용)
- 8 scheduler 활성 — cron 시각 모두 정확:
  - sector: 일 03:00 / stock_master: mon-fri 17:30 / fundamental: mon-fri 18:00
  - **ohlcv_daily: mon-fri 06:00** / **daily_flow: mon-fri 06:30** (5-13 수 첫 발화)
  - weekly: sat 07:00 / monthly: 매월 1일 03:00 / yearly: 매년 1월 5일 03:00
- /health: `{"status":"ok"}` / 컨테이너 TZ: `Tue May 12 15:30 KST 2026`

### 3. 해결된 critical 이슈 2건

#### 3.1 빌드 hang — credentials helper

- `~/.docker/config.json` 의 `credsStore: "desktop"` 가 docker-credential-desktop helper hang (47분 + 1시간 두 번 발생)
- `docker-credential-osxkeychain` 은 정상 응답 확인 (5초)
- fix: `credsStore: "osxkeychain"` 변경 → pull 정상

#### 3.2 env_prefix 불일치 — scheduler 미활성

- `.env.prod` 의 `KIWOOM_SCHEDULER_*` 9 env 가 Settings 필드 `scheduler_*` 와 매칭 실패
- pydantic-settings 매칭은 필드명 그대로 case-insensitive — `kiwoom_database_url` ↔ `KIWOOM_DATABASE_URL` 매칭하지만 `scheduler_enabled` ↔ `SCHEDULER_ENABLED` 기대
- fix: compose `environment:` 에 `SCHEDULER_*` 8 env 명시 (KIWOOM_ prefix 없이). `.env.prod` 의 잘못된 9 env 는 `extra="ignore"` 로 무시
- 재기동 후 `scheduler_enabled=True` / 8 scheduler 정상 활성 확인

### 4. 보안 노출 발견 (사용자 회수 필요)

| # | 항목 | 위험 |
|---|------|------|
| 1 | `KIWOOM_CREDENTIAL_MASTER_KEY` (Fernet 마스터키) | CRITICAL — DB 자격증명 복호화 가능 |
| 2 | `KIWOOM_API_KEY` / `KIWOOM_API_SECRET` | HIGH — 키움 OpenAPI 호출 가능 |
| 3 | `KIWOOM_ACCOUNT_NO=35324811` | LOW — 식별자 |
| 4 | Docker Hub PAT `dckr_pat_...` | HIGH — Docker Hub push 가능 |

진단 명령 출력 시 평문 노출 → 대화 로그 영구 기록. 사용자 직접 회수 + 재발급 필요 (ADR § 38.8 #6/#7).

### 5. 변경 0 / 그대로 유지

- 앱 코드 (app/) — 변경 없음
- 테스트 — 1059 그대로 (인프라 chunk)
- DB schema — 변경 없음 (Migration 014 까지 그대로, 컨테이너 기동 시 자동 적용만)

---

## [2026-05-12] fix(kiwoom): 5-11 NXT 74 rows 보완 — daily 백필 + 검증 (ADR § 37)

§ 35.8 의 별도 chunk — § 35 cron 시간 NXT 마감 후 새벽 이동 결정의 데이터 측면 정합성 확정. 5-11 NXT 적재 12% (74 / 정상 ~630) anomaly 보완. § 36 scheduler 활성 직후 5-13 첫 OhlcvDaily cron 발화 전 NXT 데이터 표 깨끗화.

### 1. 백필 실행 — `--resume` 미사용 의도적

```bash
nohup uv run python scripts/backfill_ohlcv.py --period daily \
  --start-date 2026-05-11 --end-date 2026-05-11 --alias prod \
  > logs/backfill-nxt-2026-05-11.log 2>&1 &
# PID 57104 / 시작 10:15:18 ~ 종료 10:36:24 KST / 21m 6s
```

gap detection 이 KRX 만 본다 (`d43d956`). KRX UPSERT idempotent + NXT 만 실질 보완.

### 2. 결과

| 항목 | 값 |
|------|-----|
| total | 4373 종목 |
| success_krx | 4373 / DB 적재 4370 (5-7/8 대비 -2 = 5-11 자체 신규/정지 종목 차이 — 회귀 0) |
| **success_nxt** | **630 / DB 적재 628** (정상 ~630 대비 99.7%) |
| failed | 0 (0.00%) |
| elapsed | 21m 6s (추정 36m 의 60% — 영숫자 `nxt_enable=false` 호출 skip 덕) |
| 실제 호출 수 | 5003 / 8746 dry-run 추정 (57%) |
| 실제 ERROR/WARNING/429 | **0** (grep false positive 4건 = timestamp `.429` ms + Summary `failed:` 키워드) |

### 3. 검증 SQL 4건 — 모두 PASS

- NXT 5-11: 628 rows (이전 74 → +554)
- KRX 5-11: 4370 rows (회귀 0)
- NXT 분포 5-7/8/11: 630 / 630 / 628 (anomaly 해소)
- KRX 분포 5-7/8/11: 4372 / 4372 / 4370 (idempotent UPSERT 정상)

### 4. 의미

- **§ 35.8 anomaly 완전 해소** — 12% → 99.7%
- **§ 36.5.2 1주 모니터 SQL 깨끗** — 5-13 ~ 5-19 NXT 표가 5-11 부터 ~630 균일로 시작
- **§ 36.9 Phase C 완료 선언 1보 진전** — 본 chunk + 5-19 § 36.5 측정 = Phase C 100%
- **`--resume` 미사용 패턴 검증** — KRX UPSERT idempotent 동작 사후 확인

### 5. 파일 — 코드 변경 0

- 갱신 `docs/adr/ADR-0001-backend-kiwoom-foundation.md` § 37 신규 + § 35.8 cross-ref + § 36.7 #1 해소
- 갱신 `src/backend_kiwoom/STATUS.md` — § 0 / § 4 #21 해소 / § 6 chunk 추가
- 갱신 `HANDOFF.md`
- 본 prepend
- 신규 (commit 외부) `src/backend_kiwoom/logs/backfill-nxt-2026-05-11.log`

---

## [2026-05-12] ops(kiwoom): scheduler_enabled 활성 + 1주 모니터 (ADR § 36)

Phase C 의 마지막 chunk — 운영 본격 진입. § 35 cron 시간 fix 후 8 cron scheduler 의 default disabled 상태 해소.

### 1. .env.prod 9 env 추가 (commit 외부 — .gitignore)

- `KIWOOM_SCHEDULER_ENABLED=true`
- 8 alias 모두 `prod` (DB 등록 자격증명) — sector / stock_master / fundamental / ohlcv_daily / daily_flow / weekly / monthly / yearly

### 2. lifespan fail-fast 가드 통과

`app/main.py:126-144` — 8 alias 비어있지 않은지 검증. env 9건 추가로 통과.

### 3. 첫 발화 시점 (앱 재시작 후, KST)

- StockMaster 17:30 / Fundamental 18:00 (2026-05-12 화 — 앱 재시작 시점 의존)
- OhlcvDaily 06:00 / DailyFlow 06:30 (2026-05-13 수)
- Weekly sat 07:00 (2026-05-16)
- Sector sun 03:00 (2026-05-17)
- Monthly 매월 1일 03:00 (2026-06-01)

base_date = `previous_kst_business_day(today)` 자동 전달 (§ 35).

### 4. 1주 후 측정은 별도 chunk

사용자 결정 — 본 chunk 는 활성 + 모니터링 가이드 + ADR § 36 placeholder. 2026-05-19 mon 이후 사용자 요청 시 측정 chunk:
- 일간 cron elapsed 정량화 (§ 26.5 / § 34.6 정정)
- NXT 정상 적재 (5-13~5-19 trading_date 별 row 검증)
- failed / 알람 / 부작용 정리

### 5. 코드 변경 0

본 chunk 는 .env.prod (commit 외부) + plan doc + 4 문서 (ADR/STATUS/HANDOFF/CHANGELOG) 만. 테스트 변경 없음 — 1059 tests 그대로.

### 6. 파일

신규: `src/backend_kiwoom/docs/plans/phase-c-scheduler-enable.md`
갱신: `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 36 / `src/backend_kiwoom/STATUS.md` / `HANDOFF.md`

---

## [2026-05-12] fix(kiwoom): cron 시간 NXT 마감 후 새벽으로 이동 + base_date 명시 전달 (ADR § 35)

사용자 발견 (2026-05-11) — "NXT 20시 마감 후 연동" 도메인 사실. DB 실측 5-11 NXT 74 rows (정상 630 의 12%) 정황 증거 — 21:00 백필도 키움 NXT EOD 정산 batch 미완료.

### 1. cron 시간 변경 (3 곳)

| Scheduler | Before | After |
|-----------|--------|-------|
| OhlcvDaily | mon-fri 18:30 | **mon-fri 06:00** |
| DailyFlow | mon-fri 19:00 | **mon-fri 06:30** (OHLCV 30분 stagger 유지) |
| Weekly | fri 19:30 | **sat 07:00** (daily/flow 종료 후 1h stagger) |

master/fundamental/sector/monthly/yearly 무변 — NXT 무관 또는 거래 없는 시점.

### 2. base_date 명시 전달

`UseCase.execute()` default `base_date = date.today()` 가 06:00 cron (장 시작 09:00 전) 과 충돌 — `fire_*_job` 에서 `base_date=previous_kst_business_day(date.today())` 명시 전달. UseCase default 그대로 (router manual sync 의도 분리).

### 3. 신규 helper

`app/batch/business_day.py` — `previous_kst_business_day(today)`:
- Monday → today - 3d (last Friday, 주말 skip)
- Tue~Fri → today - 1d
- Saturday → today - 1d (Friday, Weekly cron sat 발화)
- Sunday → today - 2d (안전망)

공휴일 무시 — 키움 API 빈 응답 → success 0 / UPSERT idempotent / `72dbe69` sentinel fix 자연 처리.

### 4. 테스트 (1046 → 1059, +13)

- 신규 `tests/test_business_day.py` — 7 parametrize (요일 경계) + 3 추가 (monday 3일 skip / saturday→friday / pure function) = **10건**
- `tests/test_ohlcv_daily_scheduler.py` cron 단언 갱신 + 신규 `test_fire_ohlcv_daily_sync_passes_previous_business_day_as_base_date` (+1)
- `tests/test_daily_flow_scheduler.py` 동일 패턴 (+1)
- `tests/test_weekly_monthly_ohlcv_scheduler.py` 동일 패턴 + 충돌 단언 갱신 (+1)

### 5. 5-11 NXT 보완 (본 chunk 와 별개)

사용자 수동 실행 — `backfill_ohlcv.py --start-date 2026-05-11 --end-date 2026-05-11 --alias prod` (--resume 미사용).

### 6. Verification

- ruff All checks passed / mypy --strict Success / pytest 1059 PASS / 29.84s

### 7. 파일

신규: `app/batch/business_day.py` / `tests/test_business_day.py` / `src/backend_kiwoom/docs/plans/phase-c-cron-shift-to-morning.md`
갱신: `app/scheduler.py` / `app/batch/{ohlcv_daily,daily_flow,weekly_ohlcv}_job.py` / 3 scheduler test / `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 35 / `src/backend_kiwoom/STATUS.md` / `HANDOFF.md`

---

## [2026-05-11] feat(kiwoom): 영숫자 종목 OHLCV 3 period 백필 — Phase C 데이터 측면 종결 (ADR § 34)

§ 33 chart 가드 완화 (`STK_CD_CHART_PATTERN`) 머지 후 historical 3년 백필. plan doc `phase-c-alphanumeric-backfill.md` § 3 Stage 1/2/3 전 단계 완료. **코드 변경 0 — DB 데이터만 적재**.

### 1. Stage 1 (dry-run) — 영숫자 295 / 대상 1108/4373/4373

- 영숫자 active = 295 (KOSPI 249 + KOSDAQ 44 + 기타 2 / 우선주 `*K` 20 + ETF/회사채액티브 등 275)
- daily 백필 대상 1108 (영숫자 295 + 비영숫자 gap 813 — full backfill `12f0daf` 후 신규상장/거래정지 해제) / weekly·monthly 영업일 ∅ 첫 적재 → 4373 전체
- dry-run estimated 91m 20s (rate_limit 0.25s × 21,924 calls)

### 2. Stage 2 (실 백필) — 3 period 0 failure / 47m 33s (추정 52%)

| period | total | success_krx | success_nxt | failed | elapsed |
|--------|-------|-------------|-------------|--------|---------|
| daily | 1108 | 1108 | 75 | 0 | 5m 48s |
| weekly | 4373 | 4373 | 630 | 0 | 20m 55s |
| monthly | 4373 | 4373 | 630 | 0 | 20m 50s |

### 3. Stage 3 (검증) — 영숫자 75,149 rows / anomaly 0건

- daily 영숫자 58,909 / weekly 12,983 / monthly 3,257 = **75,149 rows** (영숫자 295 모두 distinct loaded)
- NUMERIC(8,4) magnitude max 3049~3445 (cap 9999.9999 < 35%) — 안전 / 마이그레이션 불필요
- F6 (since_date edge) / F7 (turnover_rate 음수) / F8 (SPAC 0-row) anomaly **모두 0건** — 영숫자 종목군 데이터 일관성 양호

### 4. 사전 추정 정정

- plan doc § 1.3 "+200K rows" → 실측 **75K (37%)**. 영숫자 종목 평균 row 가 비영숫자의 30% (ETF/회사채 최근 상장 / SPAC / 거래 zero 일자)
- ADR § 33.6 #1 운영 cron "+10분" → 실측 295 × 0.3s = **~1.5분** (이전 추정의 15%)

### 5. Phase C 종결

본 chunk 가 Phase C 의 **데이터 측면 마지막 chunk**. 모든 chart endpoint (ka10081/82/83/94/86) 가 영숫자 종목 포함 historical 3년 적재 완성. 다음: scheduler 활성 / Phase D 진입 / Phase E~G wave.

### 6. 파일

- 신규: `src/backend_kiwoom/docs/plans/phase-c-alphanumeric-backfill.md`
- 갱신: `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 34 / `src/backend_kiwoom/STATUS.md` / `HANDOFF.md` / `CHANGELOG.md`

---

## [2026-05-11] feat(kiwoom): chart stk_cd 영숫자 가드 완화 Chunk 2 — STK_CD_CHART_PATTERN 신규 (옵션 c-A, ADR § 33)

§ 32 Chunk 1 dry-run (KRX 6/6 SUCCESS) 결과를 근거로 가드 분리 구현. plan doc `phase-c-chart-alphanumeric-guard.md` § 4 범위 그대로.

### 1. 핵심 변경

- **`stkinfo.py`**: `STK_CD_CHART_PATTERN = ^[0-9A-Z]{6}$` 상수 신규 + `_STK_CD_CHART_RE` 컴파일 + `_validate_stk_cd_for_chart` 검증 함수 신규 (A-L1 메시지 cap 정책 일관)
- **`build_stk_cd`**: `_validate_stk_cd_for_lookup` → `_validate_stk_cd_for_chart` 교체. docstring 갱신 (6자리 ASCII → 6자리 영숫자 대문자)
- **chart adapter** (`chart.py` / `mrkcond.py`): 모듈 docstring 갱신 — "CHART 패턴 (STK_CD_CHART_PATTERN, ADR § 32)" 명시
- **chart 5 router 7 path**: `ohlcv.py` (ka10081 sync/refresh) / `ohlcv_periodic.py` (ka10082/83/94 sync/refresh/get) / `daily_flow.py` (ka10086 sync/refresh) 가 `STK_CD_LOOKUP_PATTERN` → `STK_CD_CHART_PATTERN`
- **3 UseCase**: `ohlcv_daily_service` / `ohlcv_periodic_service` / `daily_flow_service` 의 `_KA*_COMPATIBLE_RE` 가 LOOKUP → CHART
- **lookup 계열 5곳 무변**: `stocks.py` (ka10100) / `fundamentals.py` (ka10001) / `stkinfo._validate_stk_cd_for_lookup` 그대로 — Excel R22 ASCII 명시 제약 유지

### 2. 테스트 (1037 → 1046, +9)

- **신규 5**: `test_validate_stk_cd_for_chart_accepts_alphanumeric_uppercase` / `..._rejects_invalid_format` / `..._message_capped_at_50_chars` / `test_validate_stk_cd_for_lookup_still_rejects_alphanumeric` (lookup 보호 단언) / `test_build_stk_cd_accepts_alphanumeric_uppercase`
- **회귀 갱신 6→4**: `test_build_stk_cd_rejects_invalid_format` / `test_fetch_daily_rejects_invalid_stock_code` / `test_fetch_daily_market_rejects_invalid_stock_code` / `test_get_ohlcv_rejects_invalid_stock_code` / `test_get_daily_flow_rejects_invalid_stock_code` — invalid set 에서 `ABC123` 제거 + `0000d0` / `00ABC!` 추가
- **의미 반전**: `test_execute_skips_alpha_stock_codes` → `test_execute_accepts_alphanumeric_uppercase_stock_codes` (3 UseCase 모두) + 신규 거부 케이스 (`test_execute_skips_incompatible_stock_codes`)
- **신규 chart 라우터 영숫자 통과 단언**: `test_get_ohlcv_accepts_alphanumeric_uppercase_stock_code` / `test_get_daily_flow_accepts_alphanumeric_uppercase_stock_code`

### 3. Verification 가 잡은 회귀 6건

testcontainers 가 자동 발견 — chart 계열 거부 단언이 영숫자에서 의도와 반대로 작동. plan doc § 4.6 의 예측 적중. 6건 모두 의미 반전 또는 invalid set 갱신으로 해소.

### 4. 외부 contract 영향

chart 계열 endpoint 의 호출 대상 stock 범위가 영숫자 (`*K` 우선주 + 영숫자 ETF) 까지 확장 — 운영 cron 실행 시 ~295 종목 추가 호출. OHLCV daily cron elapsed 34분 → ~44분 추정 (2초 rate limit 직렬화). STATUS § 4 신규 항목 #19 로 추적.

### 5. Verification

- ruff All checks passed / mypy --strict Success / pytest 1046 PASS / coverage 91% (이전 81%)

### 6. 결과 / 산출물

- 코드 변경 5 파일 (stkinfo / chart / mrkcond + 3 router + 3 service = 8 파일이지만 일부 import 만)
- 테스트 변경 7 파일 (단위 3 + 서비스 3 + 라우터 2 + stkinfo 1)
- ADR § 33 신규 / STATUS § 0 + § 4 #19/#20 + § 5 #1 변경 + § 6 누적

---

## [2026-05-11] docs(kiwoom): chart 영숫자 stk_cd 가드 완화 — Chunk 1 dry-run (옵션 c-A, ADR § 32)

§ 31.6 #1 "ETF/ETN OHLCV 별도 endpoint (옵션 c)" 의 사용자 분기 — **옵션 A (우선주/특수 종목 가드 완화)** 채택. 2단계 진행의 Chunk 1 = 운영 dry-run (코드 0줄).

### 1. dry-run 결과 (12 호출)

대형그룹사 우선주 3건 (`03473K` SK우 / `02826K` 삼성물산우B / `00499K` 롯데지주우) × KRX/NXT × ka10081/ka10086.

- **KRX**: 6/6 호출 `return_code=0` + 충분한 row (ka10081 600 / ka10086 20). `KiwoomMaxPagesExceededError` 는 `--max-pages=1` cap 효과 — wire-level SUCCESS
- **NXT**: 6/6 호출 empty (ka10081 sentinel 빈 row 1 / ka10086 row 0). 우선주 NXT 미상장 확정

### 2. 핵심 발견

- **KRX chart endpoint 가 `^[0-9A-Z]{6}$` 수용** — `STK_CD_LOOKUP_PATTERN = ^[0-9]{6}$` 의 보수적 재사용은 ka10100 R22 Excel ASCII 제약에서 유래. chart 는 더 관대
- **영숫자 stk_cd = 우선주** — listed_date 보유 영숫자 active 10건 모두 `*우`/`*우B` 패턴 (`*K` suffix)
- **NXT 우선주 미지원** — 기존 `nxt_enable=False` 가 자연 차단. Chunk 2 의 NXT 처리 변경 0

### 3. 산출물

- `src/backend_kiwoom/docs/plans/phase-c-chart-alphanumeric-guard.md` (Chunk 1/2 plan, ~410줄)
- `src/backend_kiwoom/scripts/dry_run_chart_alphanumeric.py` (`build_stk_cd` 우회, 단건 캡처, verdict 분류, ~310줄). 변수명 fallback (`KIWOOM_API_KEY` ↔ `KIWOOM_APPKEY` legacy)
- `src/backend_kiwoom/docs/operations/dry-run-chart-alphanumeric-results.md` (결과 표 + verdict 재해석 + 결정)
- `src/backend_kiwoom/captures/dry-run-alphanumeric-20260511.json` (raw 응답 + 분석)
- ADR § 32 신규 / STATUS § 5 #1 갱신 + § 6 누적

### 4. Chunk 2 진입 결정

- Chunk 2 진행 ✅ — `STK_CD_CHART_PATTERN = ^[0-9A-Z]{6}$` 신규 + chart 계열 11곳 가드 교체
- Chunk 2 범위 변경 0 — plan doc § 4 그대로
- 위험 H-1 (chart 영숫자 수용) / H-4 (NXT 우선주) 둘 다 해소

---

## [2026-05-11] docs(kiwoom): follow-up F6/F7/F8 + daily_flow 빈 응답 통합 분석 (4건 모두 NO-FIX, ADR § 31)

STATUS § 4 의 LOW 4건 일괄 분석 + 정책 결정. **코드 변경 0줄** (분석 + 문서 chunk).

### 1. 4건 검증 결과

- **F6** (since_date guard edge, 2 종목 / 0.13%) — 1980s 상장 종목 (`002690` 동일제강 / `004440` 삼일씨엔에스), page 단위 break 의 row 잔존. **NO-FIX** (데이터 가치 ≥ 비용)
- **F7** (turnover_rate min -57.32 음수, 0.0009%) — 키움 raw 응답 그대로 보존 (정직성). **NO-FIX** (분석 layer 책임)
- **F8** (OHLCV 1 종목 row 0) — DB SELECT 식별: **`452980` 신한제11호스팩** (KOSDAQ SPAC, 2026-05-09 등록, 신규 상장 직후). sentinel 가드 정상 동작. **NO-FIX**
- **daily_flow 빈 응답** — F8 와 **동일 종목 (`452980`)**. **NO-FIX**

### 2. 식별 SQL (ADR § 31.3)

```sql
SELECT s.stock_code, s.stock_name, s.market_code, s.created_at::date
FROM kiwoom.stock s
WHERE s.is_active = true
  AND s.stock_code ~ '^[0-9]{6}$'
  AND s.id NOT IN (SELECT DISTINCT stock_id FROM kiwoom.stock_price_krx)
ORDER BY s.stock_code;
-- → 452980 신한제11호스팩 (1 row, F8 + daily_flow 동일)
```

### 3. 권고 미래 follow-up

- F6: 운영 1주~1개월 후 재평가 — 1980s 상장 종목 증가 시 row 단위 fragment 제거 chunk 검토
- F7: 분석 코드 (백테스팅 layer) 에서 turnover_rate 0/NaN 처리 정책 명시 (DB 정규화 거부)
- F8 / daily_flow: 다음 cron 실행 후 신한제11호스팩 row 추가 확인. row 0 종목이 다른 신규 상장 SPAC 으로 늘어나면 별도 대응

### 4. 다음 chunk 후보

1. ETF/ETN OHLCV 별도 endpoint (옵션 c)
2. Phase D — ka10080 분봉 / ka20006 업종일봉
3. Phase E/F/G wave
4. (최종) scheduler_enabled 일괄 활성 + 1주 모니터
5. KOSCOM cross-check 수동

---

## [2026-05-11] refactor(kiwoom): Phase C-R2 — 1R Defer 5건 일괄 정리 (L-2 / E-1 / M-3 / E-2 / gap detection)

ADR § 24.5 / § 25.6 의 1R Defer 5건 일괄 정리. 외부 API contract 무변. C-4 (`b75334c`) 가 L-2 의 전제 조건을 변경 (YEARLY 활성 → 핸들러 dead branch) — stale docstring 정리로 축소 (사용자 결정 옵션 A). /ted-run 풀 파이프라인 (TDD → 구현 → 1R sonnet → Verification 4관문 → ADR § 30).

### 1. 변경 범위 (8 코드 + 4 테스트)

**코드**:
- `app/application/service/ohlcv_periodic_service.py` (L-2 — module docstring + execute/refresh_one Raises 절 + `_validate_period` 정리)
- `app/adapter/web/routers/ohlcv_periodic.py` (L-2 — module docstring)
- `app/adapter/web/routers/ohlcv.py` (E-1 — `sync_ohlcv_daily` KiwoomError 5종 핸들러 추가, ~35 line)
- `app/adapter/out/persistence/repositories/stock_price.py` (M-3 — `typing.cast` import + cast 적용)
- `app/adapter/out/persistence/repositories/stock_price_periodic.py` (M-3 — 6-way Union cast)
- `app/adapter/web/_deps.py` (E-2 — 7 reset_*_factory docstring `"테스트 전용"` → `"lifespan teardown + 테스트"`)
- `scripts/backfill_ohlcv.py` (gap — should_skip_resume 폐기 + compute_resume_remaining_codes 시그니처 + 영업일 차집합 + caller + help/log)
- `scripts/backfill_daily_flow.py` (gap — 동일 변경. 단일 테이블 + `exchange = 'KRX'` 필터 양쪽 SQL)

**테스트** (1035 → **1037**, net +2 / coverage 81.15%):
- `tests/test_ohlcv_router.py` (E-1 5 신규 — sync_* KiwoomError 5종 응답 단언)
- `tests/test_backfill_ohlcv_cli.py` (gap 3 신규 — no_business_days / skips_fully_loaded / includes_partial_loaded_with_gap. should_skip_resume 4건 폐기)
- `tests/test_backfill_daily_flow_cli.py` (동일 패턴)
- `tests/test_ohlcv_periodic_service.py` (C-4 잔존 stale — `YearlyChartRow` forward ref + 함수 내부 import → 모듈 top-level import)

### 2. 1차 리뷰 결과 (sonnet sub-agent)

- CRITICAL 0 / HIGH 0
- MEDIUM 3: M-1 (gap detection 영업일 SQL 의 exchange 필터 차이 의도 주석) + M-2 (test 섹션 빈 헤더 제거) + M-3 (sync_ohlcv_daily `detail=str(exc)` echo — refresh/_do_sync 동일 패턴, 본 chunk 범위 외 / 기록만)
- LOW 3: L-1 (`_validate_period` defense-in-depth 위치 주석) + 2 (이슈 없음)
- → M-1/M-2/L-1 즉시 fix → PASS

### 3. 사용자 결정 3건 (R2 진입 시)

- **L-2 처리** = 옵션 A (폐기 + stale docstring 5곳 정리). C-4 가 YEARLY 활성 → 핸들러 추가는 dead branch. `_ingest_one:392` 의 dead branch 가드는 defense-in-depth 로 유지
- **gap detection 범위** = `compute_resume_remaining_codes` 일자별 검사로 디폴트 변경. CLI 디폴트 동작 변경 (R1 의 max-based 검사 폐기)
- **영업일 calendar source** = DB 내 `SELECT DISTINCT trading_date` union (외부 패키지 의존성 0). 시장 전체 종목이 한 번이라도 거래한 일자 = 영업일

### 4. 운영 영향 (회귀 위험)

- `/ohlcv/daily/sync` status code: 본 chunk 전 FastAPI 디폴트 500 → 본 chunk 후 명시 매핑 (400 / 503 / 502). 운영 알람 임계가 5xx 기반이면 KiwoomBusinessError → 400 누락 가능. **운영팀 공유 권고**
- CLI `--resume` 동작: 부분 적재 (gap) 종목이 R1 에서 skip → R2 에서 진행. 정확도 향상 (사용자 의도)

### 5. ADR § 24.5 / § 25.6 Defer 5건 해소 매핑

| 출처 § | 항목 | 해소 |
|---|---|---|
| § 24.5 | L-2 | ✅ 폐기 + stale docstring 5곳 정리 |
| § 24.5 | E-1 | ✅ sync_ohlcv_daily KiwoomError 5종 핸들러 추가 |
| § 24.5 | E-2 | ✅ 7 reset_*_factory docstring 정정 (reset_token_manager 정직성 유지) |
| § 23.6 | M-3 | ✅ 2 Repository typing.cast 적용 |
| § 25.6 | gap detection | ✅ 2 CLI 일자별 차집합 검사 (DB union 영업일) |

### 6. 다음 chunk 후보

1. follow-up F6/F7/F8 + daily_flow 빈 응답 1건 통합 (LOW / 0.5일)
2. ETF/ETN OHLCV 별도 endpoint (옵션 c)
3. Phase D — ka10080 분봉 / ka20006 업종일봉 (대용량 파티션 결정 선행)
4. Phase E/F/G wave (공매도/대차/순위/투자자별)
5. (최종) scheduler_enabled 일괄 활성 + 1주 모니터 — 사용자 결정 (모든 작업 완료 후)
6. KOSCOM cross-check 수동 — 가설 B 최종 확정

---

## [2026-05-11] feat(kiwoom): Phase C-4 — ka10094 년봉 OHLCV (Migration 014, KRX only NXT skip, 11/25 endpoint)

C-3α/β 의 `IngestPeriodicOhlcvUseCase` YEARLY 분기 NotImplementedError 가드 → 활성화. 응답 7 필드 + NXT skip 정책 + 매년 1월 5일 KST 03:00 cron 차이만 핵심. Phase C chart 카테고리 (일/주/월/년봉) 종결. /ted-run 풀 파이프라인 (TDD → 구현 → 1R → Verification Loop → ADR § 29).

### 1. 변경 범위 (11 코드 + 6 테스트)

**코드** (10 신규/수정):
- `migrations/versions/014_stock_price_yearly.py` (신규, revision id 22 chars)
- `app/adapter/out/persistence/models/stock_price_periodic.py` (StockPriceYearly{Krx,Nxt} 2 클래스 + mixin 재사용)
- `app/adapter/out/persistence/models/__init__.py` (export 2)
- `app/adapter/out/kiwoom/chart.py` (YearlyChartRow + YearlyChartResponse 7 필드 + fetch_yearly + sentinel break)
- `app/adapter/out/persistence/repositories/stock_price_periodic.py` (YEARLY dispatch table 등록, PeriodicModel union 확장)
- `app/application/service/ohlcv_periodic_service.py` (`_validate_period` NotImplementedError 제거 / `_ingest_one` YEARLY 분기 + fetch_yearly / `_api_id_for` YEARLY → ka10094 / NXT skip 가드)
- `app/adapter/web/routers/ohlcv_periodic.py` (yearly sync + refresh 2 path / `_api_id_for` 모듈 헬퍼)
- `app/batch/yearly_ohlcv_job.py` (신규, monthly 패턴 1:1)
- `app/scheduler.py` (YearlyOhlcvScheduler + YEARLY_OHLCV_SYNC_JOB_ID + CronTrigger month=1 day=5 hour=3)
- `app/config/settings.py` (`scheduler_yearly_ohlcv_sync_alias` 추가)
- `app/main.py` (lifespan alias fail-fast + YearlyOhlcvScheduler 등록/shutdown)

**테스트** (1030 → **1035**, +5 cases):
- `tests/test_migration_014.py` (신규 5 cases — yearly 2 테이블 / UNIQUE / 인덱스 / FK CASCADE / downgrade 가드 / 라운드트립)
- `tests/test_stock_price_periodic_repository.py` (3 stale yearly raises → YEARLY 활성 검증)
- `tests/test_ohlcv_periodic_service.py` (2 stale NotImplementedError → YEARLY KRX-only 성공 + NXT skip)
- `tests/test_skip_base_date_validation.py` (1 stale NotImplementedError → YEARLY skip-validation 정상)
- `tests/test_scheduler.py` + `test_stock_master_scheduler.py` (SCHEDULER_YEARLY_OHLCV_SYNC_ALIAS env 추가)
- `tests/test_migration_013.py` (downgrade 가드 단언 정정 — 014 head 후 transactional rollback)

### 2. Verification Loop 가 잡은 5건

정적 분석 (ruff PASS) 으로 못 잡고 mypy + testcontainers 가 발견:

1. **mypy `--strict` invariant list 거부** — `rows: list[DailyChartRow] | list[YearlyChartRow]` (variant) → `list[DailyChartRow | YearlyChartRow]` (covariant). WeeklyChartRow/MonthlyChartRow 의 DailyChartRow 상속과 YearlyChartRow 별도 정의 차이가 type system 노출
2. **`_page_reached_since` / `_row_on_or_after` helper signature 확장** — `Sequence[DailyChartRow]` → `Sequence[DailyChartRow | YearlyChartRow]`
3. **C-3α stale 가드 단언 6건** — repository 3건 + service 2건 + skip_base_date 1건. plan doc § 12.3 미명시 — testcontainers 자동 발견 (C-2δ test_008 패턴 재현)
4. **테스트 env alias 누락 2건** — test_scheduler.py + test_stock_master_scheduler.py 의 lifespan fail-fast 테스트가 SCHEDULER_YEARLY_OHLCV_SYNC_ALIAS 누락
5. **test_migration_013 단언 정정** — 014 head 진입 후 command.downgrade(012) 가 014 → 013 다단계, 단일 transaction rollback 으로 014 head 유지. 양성 단언 → downgrade target 미도달 단언으로 정정

### 3. 결정

- **응답 7 필드** — YearlyChartRow 별도 정의 (DailyChartRow 상속 불가). `to_normalized` 에서 prev_compare_amount/sign/turnover_rate=None → DB NULL 영속
- **NXT skip** — UseCase execute/refresh_one 의 NXT 가드에 `or period is Period.YEARLY` 추가. fetch_yearly 자체는 호출 안 됨
- **테이블 KRX/NXT 분리** — Migration 014 가 두 테이블 신규. dispatch table 도 둘 다 등록. 향후 NXT skip 해제 chunk 시 활용
- **revision id 22 chars** — C-2δ VARCHAR(32) 학습 후 안전 마진 10 chars 확보
- **scheduler_enabled 보류** — 사용자 결정 (모든 작업 완료 후 활성). 코드 등록까지만

### 4. Phase C 종결

| API | 명 | cron | 상태 |
|-----|----|----- |------|
| ka10081 | 일봉 | 평일 18:30 | ✅ |
| ka10082 | 주봉 | 금 19:30 | ✅ |
| ka10083 | 월봉 | 매월 1일 03:00 | ✅ |
| ka10094 | **년봉** | **매년 1월 5일 03:00** | ✅ **본 chunk** |
| ka10086 | 일별 수급 | 평일 19:00 | ✅ |

### 5. 다음 chunk 후보

1. **refactor R2 (1R Defer 일괄 정리)** (LOW / 1일)
2. follow-up F6/F7/F8 + daily_flow 빈 응답 1건 (LOW / 0.5일)
3. ETF/ETN OHLCV 별도 endpoint (옵션 c)
4. Phase D 진입 — ka10080 분봉 / ka20006 업종일봉
5. Phase E/F/G (공매도/대차/순위/투자자별 wave)
6. **(최종) scheduler_enabled 일괄 활성** — 사용자 결정

---

## [2026-05-11] refactor(kiwoom): Phase C-2δ — Migration 013 (C/E 중복 2 컬럼 DROP, 10→8 도메인)

운영 실측 § 5.6 IS DISTINCT FROM 검증 (2.88M rows / `credit_diff=0` / `foreign_diff=0`) 으로 확정된 C/E 중복 2 컬럼 (`credit_balance_rate` / `foreign_weight`) DROP. C-2γ Migration 008 (D-E 중복 3 컬럼 DROP) 패턴 1:1 응용. /ted-run 풀 파이프라인 (TDD → 구현 → 1R PASS → Verification Loop → ADR/STATUS/HANDOFF/CHANGELOG).

### 1. 변경 범위 (6 코드 + 4 테스트 + 1 운영 doc + 4 doc)

**코드**:
- `migrations/versions/013_drop_daily_flow_dup_2.py` (신규) — UPGRADE DROP × 2 / DOWNGRADE 데이터 가드 + ADD NUMERIC(8,4) × 2
- `app/adapter/out/persistence/models/stock_daily_flow.py` — Mapped 2 제거 (10 → 8 도메인)
- `app/adapter/out/persistence/repositories/stock_daily_flow.py` — `_payload` + `excluded` 4줄 제거
- `app/adapter/out/kiwoom/_records.py` — `NormalizedDailyFlow` 2 필드 + `to_normalized` 2 매핑 제거 (raw DailyMarketRow.crd_remn_rt/for_wght 는 vendor 응답 유지)
- `app/adapter/web/routers/daily_flow.py` — `DailyFlowRowOut` 2 필드 제거 (응답 DTO breaking, 운영 미가동)
- `scripts/dry_run_ka10086_capture.py` — 2 line 제거 (plan doc § 13.5 H-5)

**테스트** (1026 → **1030**, +4 cases):
- `tests/test_migration_013.py` (신규 4 cases) — 008 패턴 1:1
- `tests/test_migration_007.py` — NUMERIC 4→2 + DROP 부재 단언
- `tests/test_migration_008.py` — `expected_remaining` 10→8 + 라운드트립 카운트 18→16 (Verification 가 발견, plan doc § 13.3 미명시)
- `test_stock_daily_flow_repository.py` / `test_daily_flow_router.py` / `test_kiwoom_mrkcond_client.py` — stale kwarg/assertion 제거 + 부재 단언 추가

**운영 doc**:
- `docs/operations/backfill-daily-flow-runbook.md` § 7 NUMERIC SQL inline 주석 (Migration 013 후 비활성)

**문서**:
- ADR § 28 (C-2δ 결과) — 28.1~28.7
- plan doc § 13 (사전 작성된 chunk § — 영향 범위 / self-check H-1~H-8 / DoD)
- STATUS.md / HANDOFF.md

### 2. Verification Loop 가 잡은 2건

정적 분석 (ruff/mypy) 으로 못 잡고 testcontainers 통합 test 가 발견:

1. **VARCHAR(32) revision id truncation** — `013_drop_daily_flow_dup_columns_2` 33 chars > `alembic_version.version_num` VARCHAR(32) → `psycopg2.errors.StringDataRightTruncation`. `013_drop_daily_flow_dup_2` (25 chars) 로 단축. 008 (`008_drop_daily_flow_dup_columns` 31 chars) 답습 + `_2` 접미사 위험. 향후 chunk 메모.
2. **`test_migration_008.py` hard-coded 카운트** — `expected_remaining` set 에 `credit_balance_rate`/`foreign_weight` 잔존 + `len(cols_after_upgrade) == 18` 가 013 적용 후 head 상태 미반영. H-8 (test_007 NUMERIC 4 hard-code) 패턴이 동일 적용 필요했으나 plan doc § 13.3 영향 범위 누락 — testcontainers 가 자동 발견.

### 3. 결정

- **응답 DTO breaking 수용** — 운영 미가동 + master 외 deploy 0 / scheduler_enabled=false 라 downstream 영향 0
- **raw DailyMarketRow 필드 유지** — vendor 응답 모델은 그대로 보존 (C-2γ 와 동일 정책)
- **NXT row mirror 정책 영향 없음** — KRX/NXT 둘 다 동일 raw 동일값
- **운영 검증 SQL § inline 주석** — Migration 013 후 컬럼 부재로 실행 불가 (검증 완료 명시)

### 4. 다음 chunk 후보

1. **scheduler_enabled 운영 cron 활성 + 1주 모니터** (MEDIUM) — 측정 #4 (일간 cron elapsed) / OHLCV + daily_flow 통합
2. follow-up F6/F7/F8 + daily_flow 빈 응답 1건 통합 (LOW)
3. refactor R2 (LOW)
4. ka10094 (P2)

---

## [2026-05-11] docs(kiwoom): failed 166 NXT resume PASS + 컬럼 동일값 확정 — Migration 013 DROP chunk 진입

`72dbe69` (NXT sentinel break fix) 후 failed 166 NXT 종목 `--only-stock-codes` 명시 resume + 컬럼 동일값 SQL 검증. **코드 변경 0** — 측정 + 검증 결과 documentation.

### 1. Resume 결과 (failed 166 NXT)

| 항목 | 값 |
|------|-----|
| 명령어 | `--years 3 --alias prod --only-stock-codes <166 CSV>` |
| total / success_krx / success_nxt / failed | **166 / 166 / 10 / 0** |
| elapsed | **21m 33s** (avg 7.8s/stock) |

**해석**: success_nxt=10 — 166 중 NXT 활성 10 종목만 신규 적재. 나머지 156 은 KRX-only (이미 첫 full 에서 적재됨). 첫 full 의 `failed=166` 은 (stock × NXT exchange) 단위 카운트로 NXT 시도 실패만 표시.

### 2. 최종 DB 상태 — OHLCV 일치 ✅

| exchange | stocks | rows | oldest | newest |
|----------|--------|------|--------|--------|
| KRX | **4077** | 2,727,337 | 2023-05-11 | 2026-05-08 |
| NXT | **626** | 152,163 | 2025-03-17 | 2026-05-08 |
| **total** | — | **2,879,500** | — | — |

stocks (KRX 4077 / NXT 626) OHLCV full backfill 결과와 **정확히 일치**.

### 3. 컬럼 동일값 검증 — ✅ **확정 (100% 동일)**

```sql
SELECT
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE credit_rate IS DISTINCT FROM credit_balance_rate) AS credit_diff,
    COUNT(*) FILTER (WHERE foreign_rate IS DISTINCT FROM foreign_weight) AS foreign_diff
FROM kiwoom.stock_daily_flow;
-- total=2,879,500 / credit_diff=0 / foreign_diff=0
```

**결과**: 2,879,500 rows 전체에서 두 쌍 컬럼 모두 0건 차이 (NULL 포함 `IS DISTINCT FROM` 비교 정확).

**의미**: ka10086 응답이 두 필드를 동일값으로 채움 (또는 어댑터 매핑이 동일 source 를 두 컬럼에 적재). C-2γ Migration 008 의 D-E 중복 3 컬럼 DROP 패턴 응용 가능.

### Changed

- `src/backend_kiwoom/docs/operations/backfill-daily-flow-results.md` § 0 / § 2.4 (resume + 최종 DB) / § 5.6 (컬럼 동일값 확정) / § 9 #1 #2 해소 / § 11 우선순위 / § 14 timeline 추가
- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 27 헤더 / § 27.5 #3 (컬럼 동일값 확정 → Migration 013) / chunk 산출 갱신
- `src/backend_kiwoom/STATUS.md` § 0 / § 3 sub-chunk 추가 / § 4 #16 해소 / § 5 우선순위 (Migration 013 1순위) / § 6

### 운영 검증

- 코드 변경 0 — 1026 tests 그대로
- DB 적재 KRX 4077 + NXT 626 = OHLCV 결과와 일치 (cross-check PASS)

### 다음 chunk

**Migration 013 — `credit_balance_rate` + `foreign_weight` DROP** (C-2γ Migration 008 패턴 응용):
- ORM `StockDailyFlow` 2 컬럼 제거
- 어댑터 (mrkcond.py / daily_flow_service.py) 매핑 정리
- 통합 / 단위 테스트
- 운영 검증

---

## [2026-05-11] fix(kiwoom): NXT 빈 응답 sentinel 무한 루프 fix — mrkcond + chart 4곳 `if not <list>: break`

`4e75dd3` full backfill 결과 NXT 166 fail (활성 626 의 26.5%) 의 근본 원인 분석 + 즉시 fix. 키움 서버가 NXT 출범 (2025-03-04) 이전 base_dt 요청 시 빈 응답 + cont-yn=Y + next-key sentinel 후 page 1 next-key 로 되돌아가는 **무한 루프** 발견. `_page_reached_since` 가 빈 rows 시 False 반환이라 break 안 됨.

### 근본 원인 (NXT 010950 ka10086 3년 reproduce)

next-key 추적:
- p1~p14: 정상 데이터 (resp-cnt=20)
- p15: NXT 출범 직전 마지막 row (resp-cnt=10)
- **p16: resp-cnt=0 + next-key=`A010950_NX20260511000000-1`** (sentinel)
- **p17~: next-key=`A010950_NX2026051120260409` (p1 next-key) — page 1 부터 반복**

`max_pages=40` 도달 fail. 1년 백필은 since_date 가 page 1~13 안에서 break 라 PASS, 3년 백필만 NXT 출범 이전 base_dt 진입 → 무한 루프.

### 변경 요약

| # | 영역 | 변경 |
|---|------|------|
| 1 | `app/adapter/out/kiwoom/mrkcond.py` `fetch_daily_market` | `if not parsed.daly_stkpc: break` 추가 — since_date guard 이전 |
| 2 | `app/adapter/out/kiwoom/chart.py` `fetch_daily` | `if not parsed.stk_dt_pole_chart_qry: break` 추가 |
| 3 | `app/adapter/out/kiwoom/chart.py` `fetch_weekly` | `if not parsed.stk_stk_pole_chart_qry: break` 추가 |
| 4 | `app/adapter/out/kiwoom/chart.py` `fetch_monthly` | `if not parsed.stk_mth_pole_chart_qry: break` 추가 |
| 5 | tests +2 cases | mrkcond + chart daily 빈 응답 + cont-yn=Y break 검증 |

### chart.py 적용 이유

OHLCV ka10081 도 동일 패턴 잠재 위험 (저거래 종목 / 장기 휴장 / NXT 출범 이전 base_dt). 현재 page row 수 ~600 이라 fail 안 했지만 patten 일관성 + 잠재 위험 방어.

### 운영 검증

- ruff PASS / mypy --strict PASS / **1026 tests** PASS (1024 → +2)
- 010950 3년 reproduce fix 후: total 1 / success_krx 1 / success_nxt 1 / failed 0 / **13s** (이전 19s + fail)

### Backwards 호환

- since_date=None (운영 cron) 호환 — 정상 응답에서는 빈 응답 발생 안 함
- 빈 응답 + cont-yn=N 인 정상 종료 case 도 동일하게 break (영향 없음)
- 첫 page 빈 응답 (활성도 없는 종목 / 휴장 base_dt) 시 cont-yn 무시하고 break — 안전한 동작

### 다음 chunk

failed 166 NXT 종목 resume 재시도 (`--resume` ~36분 추정) → 컬럼 동일값 검증 (LOW)

---

## [2026-05-11] docs(kiwoom): daily_flow Stage 0~3 + NUMERIC SQL 측정 완료 — full 9h 53m / NXT 166 fail / 마이그레이션 불필요

`scripts/backfill_daily_flow.py` 운영 실측 measurement chunk. Stage 0 dry-run → Stage 1 smoke (fix 후 재시도 PASS) → Stage 2 mid → Stage 3 full → NUMERIC SQL 4 컬럼 → since_date edge cross-check 모두 완료. **코드 변경 0** — 측정 결과 documentation.

### 운영 실측 결과 요약

| Stage | 명령어 요지 | total | success | failed | elapsed |
|-------|------------|-------|---------|--------|---------|
| smoke | KOSPI 10 / 1y (재시도) | 6 | 6 KRX / 2 NXT | 0 | 25s |
| mid | KOSPI 100 / 3y | 78 | 78 KRX / 21 NXT | 0 | 13m 8s |
| **full** | active 4078 / 3y | **4078** | **3922 KRX / 616 NXT** | **166** (NXT only) | **9h 53m 34s** |

### 측정 결과 정량화 (ADR § 27.4 운영 미해결 4건)

- **#1 페이지네이션 빈도**: 1 page ≈ 22 거래일 (실측, 가설 "~300 거래일" 13배 틀림). 3년 = 평균 ~32 page
- **#2 3년 백필 elapsed**: 9h 53m 34s (avg 8.7s/stock — OHLCV 0.5s 의 17.4배). 페이지 수 차이가 원인
- **#3 NUMERIC(8,4) 4 컬럼**: max 16.39 (`credit_*`) / 100.00 (`foreign_*`) — cap 1% 이내, gt_100/gt_1000 모두 0 → **마이그레이션 불필요**
- **#4 일간 cron elapsed**: 본 chunk 미수행 (scheduler_enabled 활성화 chunk 대기)

### 신규 발견 (본 chunk)

| # | 항목 | 심각도 | 후속 chunk |
|---|------|--------|-----------|
| 1 | **NXT 166 종목 max_pages=40 도 부족** (활성 626 의 26.5%) | **MEDIUM** | NXT 응답 패턴 분석 chunk |
| 2 | **컬럼 동일값 의심** (`credit_rate ≡ credit_balance_rate`, `foreign_rate ≡ foreign_weight` — min/max/p01/p99 모두 일치) | LOW | `<>` 검증 → 동일 시 Migration DROP (C-2γ 패턴) |
| 3 | KRX 빈 응답 1 종목 (success_krx=3922 vs DISTINCT=3921) | LOW | OHLCV F8 통합 |
| 4 | KRX 적재 -156 stocks vs OHLCV 4077 | LOW | item 1 과 통합 분석 |

### since_date guard cross-check (OHLCV F6 비교)

- **0 rows** since_date 미만 적재 (OHLCV 의 002690/004440 같은 edge case 없음)
- **결론**: daily_flow `_page_reached_since_market` 가 OHLCV `chart.py` 보다 **정확**. F6 edge case 별도 분석 우선순위 ↓

### Changed

- `src/backend_kiwoom/docs/operations/backfill-daily-flow-results.md` — § 0~14 모두 채움 (TBD 제거)
- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 27 — 헤더 라벨 + § 27.5 표 (Stage 2/3 + NUMERIC + 컬럼 동일값 + since_date edge) + 신규 발견 3건
- `src/backend_kiwoom/STATUS.md` § 0 / § 3 / § 4 / § 5 / § 6 — measurement chunk 완료 / 신규 이슈 #15 (NXT) #16 (컬럼 동일값) / 다음 chunk 우선순위 재조정

### 운영 검증

- 코드 변경 0 — 1024 tests 그대로
- KRX 적재: 2,636,175 rows / DISTINCT 3921 stocks / 2023-05-11 ~ 2026-05-08
- NXT 적재: 149,262 rows / DISTINCT 616 stocks / 2025-03-17 ~ 2026-05-08

### 다음 chunk

1. NXT 166 fail 분석 (MEDIUM) → 운영 cron 영향 검증
2. 컬럼 동일값 검증 (LOW) → Migration DROP 결정

---

## [2026-05-10] fix(kiwoom): daily_flow smoke 첫 호출 운영 차단 fix — DAILY_MARKET_MAX_PAGES 10 → 40

`scripts/backfill_daily_flow.py` smoke 첫 호출 (KOSPI 10 / 1년) 에서 `KiwoomMaxPagesExceededError` 8건 발견. mrkcond.py:50 의 가설 "1 page ~300 거래일" 가 실측 13배 틀림 (실측 ~22 거래일/page) — `DAILY_MARKET_MAX_PAGES = 10` 부족.

### 변경 요약

| # | 영역 | 변경 |
|---|------|------|
| 1 | `app/adapter/out/kiwoom/mrkcond.py:50` | `DAILY_MARKET_MAX_PAGES = 10 → 40` + 주석 갱신 (실측 1 page ~22 거래일 / 3년 ~32 page / 안전 마진 8) |
| 2 | `docs/operations/backfill-daily-flow-results.md` § 0 / § 2.2 | smoke 첫 시도 차단 발견 + 즉시 fix + 재시도 PASS 기록 (6/2/0 / 25s) |
| 3 | ADR § 27 헤더 + § 27.5 | 상태 라벨 + 측정 결과 표 + ka10086 vs ka10081 1 page row 수 차이 분석 (~22 vs ~600) |
| 4 | STATUS.md § 0 / § 3 / § 4 / § 5 / § 6 | C-flow-MAX_PAGES fix sub-chunk 추가 + 알려진 이슈 #14 해소 |

### 근본 원인 분석

next-key 헤더 추적:
- p1 next=20260108 → p2 base 2026-01-08 (1 page ≈ 80 거래일, 첫 page 만 광범위)
- p2~p7 next-key: 20251208 → 20251110 → 20251013 → 20250908 → 20250810 → 20250713
- p2~ 평균 1 page ≈ **22 거래일** (월 단위)
- 1년 (250 거래일) 도달 = 약 12 page 필요 → max_pages=10 부족

원인 가설 — ka10086 응답 22 필드 (신용 + 투자자별 + 외인) 의 row 가 base_dt 기준 약 1개월 단위로 잘림 (키움 서버 측 로직). 첫 page 만 ~80 거래일 (4개월) 다른 패턴은 추후 follow-up.

### fix 패턴 사전 적용 검증 부분 결과 (ADR § 27.6 cross-check)

| # | 운영 차단 | OHLCV fix commit | daily_flow smoke 검증 |
|---|----------|-----------------|---------------------|
| 1 | since_date guard | `d60a9b3` | ⚠ logic 정상이지만 max_pages=10 한계로 도달 전 abort → 본 fix 로 해소 |
| 2 | `--max-stocks` CLI | `76b3a4a` | ✅ 정상 작동 (raw 10 → 호환 6, active 전체 호출 안 됨) |
| 3 | ETF/ETN 호환 가드 | `c75ede6` | ✅ 정상 작동 (`_KA10086_COMPATIBLE_RE` 4 종목 skip + sample 로깅) |

mock 테스트 한계 (`12f0daf` HANDOFF) 재확인 — page row 수 가정 (mrkcond:50 의 ~300 거래일 가설) 은 운영 호출에서만 검증 가능. `since_date_breaks_pagination` 같은 mock 테스트는 since_date 의 break 조건만 검증, page row 수 자체는 검증 못 함.

### 운영 검증

- ruff PASS / mypy --strict PASS / 1024 tests PASS (mrkcond 17 cases, 상수값 변경만이라 영향 없음)
- smoke 재시도 (KOSPI 10 / 1년): total 6 / failed 0 / 25s — since_date guard 정상 작동

### Backwards 호환

- 운영 cron (since_date=None 디폴트) 호환 — max_pages 만 상향, break 조건 변경 없음
- 라우터 (`/api/kiwoom/daily-flow/sync`, 1년 cap) 호환 — 1년 = 12 page < 40 안전

### 다음 단계

Stage 2 mid (KOSPI 100 / 3년) → Stage 3 full (active 4078 / 3년) → NUMERIC SQL 4 컬럼 → ADR § 27.5 결과 표 채움.

---

## [2026-05-10] docs(kiwoom): daily_flow 운영 실측 가이드 신규 — runbook + results doc (코드 0 변경)

`scripts/backfill_daily_flow.py` (ka10086) 운영 실측을 위한 단계별 절차 + 결과 양식 신규. OHLCV § 26 (`backfill-measurement-runbook.md` / `backfill-measurement-results.md`) 패턴 1:1 복제 후 ka10086 차이만 반영. ADR § 27 헤더에 doc 참조 추가 + § 27.5 측정 자리 명시.

### 신규 산출물

| # | 파일 | 역할 |
|---|------|------|
| 1 | `src/backend_kiwoom/docs/operations/backfill-daily-flow-runbook.md` (12 §) | 사전 조건 / dry-run / smoke / mid / full / NUMERIC SQL 4 컬럼 / 일간 cron / 트러블슈팅 / 안전 장치 / OHLCV cross-check |
| 2 | `src/backend_kiwoom/docs/operations/backfill-daily-flow-results.md` (13 §) | 측정 후 채울 양식 — 단계별 실측 / NUMERIC 4 컬럼 분포 / since_date edge case cross-check / 결정 / 후속 chunk |

### OHLCV runbook 대비 차이 (ka10086 특화)

- `--period` 분기 없음 (단일 endpoint) → § 6 (weekly/monthly) 생략
- `--indc-mode {quantity,amount}` 옵션 추가 (디폴트 quantity — 시그널 단위 일관)
- NUMERIC 측정 4 컬럼: `credit_rate` / `credit_balance_rate` / `foreign_rate` / `foreign_weight` (OHLCV 의 `turnover_rate` 와 별도 도메인)
- resume 테이블: `kiwoom.stock_daily_flow` (KRX/NXT 단일 테이블 + exchange 컬럼)
- § 12 OHLCV 백필 결과 cross-check 신규 — 4 가설 검증 자리 (페이지 빈도 / since_date edge / ETF skip 비율 / NUMERIC 분포)
- § 13 (results.md) 운영 차단 fix 패턴 사전 적용 검증 — OHLCV 에서 발견된 3건이 daily_flow 에서 사전 적용된 효과 검증

### Changed

- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 27 헤더 — runbook + results doc 참조 추가, 상태 라벨 갱신 (코드/테스트 + 실측 가이드 완료)
- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 27.5 — 측정 절차 가이드 자리 명시 (results.md 채움 후 핵심 결정 표 옮김)
- `src/backend_kiwoom/STATUS.md` § 0 / § 3 / § 5 / § 6 — C-flow-실측 준비 chunk 추가, 다음 chunk = 사용자 수동 측정으로 갱신

### 운영 검증

- 코드 변경 0 — 1024 tests 그대로 (이전 chunk `23f601b` 동일)
- ruff / mypy 영향 없음
- 다음 단계: 사용자가 runbook § 1~5 따라 실측 → results.md 채움 → ADR § 27.5 갱신 chunk

---

## [2026-05-10] feat(kiwoom): daily_flow (ka10086) 백필 CLI 신규 — OHLCV 운영 차단 fix 3건 사전 적용

`scripts/backfill_daily_flow.py` 신규 + `IngestDailyFlowUseCase` 확장. OHLCV 백필 (§ 26) 운영 실측에서 발견된 차단 fix 3건 (since_date guard / `--max-stocks` 정상 적용 / ETF 호환 가드) 을 처음부터 패턴 그대로 내장 — mock 테스트가 못 잡는 운영 edge case 사전 방어.

### 변경 요약

| # | 영역 | 변경 |
|---|------|------|
| 1 | `scripts/backfill_daily_flow.py` 신규 | argparse + `--indc-mode {quantity,amount}` + `--years/--start-date/--end-date/--resume/--max-stocks/--dry-run` + `_build_use_case` lifespan 외부 + try/finally graceful close |
| 2 | `app/adapter/out/kiwoom/mrkcond.py` | `fetch_daily_market` 에 `since_date: date \| None` 신규 + `_page_reached_since` / `_row_on_or_after` 헬퍼 (chart.py 패턴 1:1 응용) |
| 3 | `app/application/service/daily_flow_service.py` | `_KA10086_COMPATIBLE_RE` ETF 가드 + `execute(only_stock_codes=, _skip_base_date_validation=, since_date=)` 확장 + `refresh_one(_skip_base_date_validation=)` + `_validate_base_date(skip_past_cap=)` 분기. 모든 신규 파라미터 디폴트값 — router/cron 호환 |
| 4 | 신규 plan doc `docs/plans/phase-c-backfill-daily-flow.md` | chunk DoD / 영향 범위 / self-check / 운영 미해결 4건 |
| 5 | ADR § 27 신규 | 결정 / 변경 범위 / 측정 대상 4건 / 운영 차단 fix 패턴 일관성 검증 |
| 6 | 테스트 +31 cases | mrkcond +2 (since_date 페이지네이션 + None 호환) / daily_flow_service +5 (ETF/ETN/since_date 전파/skip_base_date/only_stock_codes) / backfill_daily_flow_cli +24 |

### Backwards 호환

- `IngestDailyFlowUseCase.execute` / `refresh_one` 신규 파라미터 모두 디폴트값 — 기존 router (`app/adapter/web/routers/daily_flow.py`) / cron (`app/batch/daily_flow_job.py`) 호출 호환
- `KiwoomMarketCondClient.fetch_daily_market(since_date=None)` 디폴트 — 운영 cron 기존 동작 유지

### 운영 검증

- 단위 + 통합: **1024 tests passed** (993 → +31), coverage 95% (threshold 80%)
- ruff + mypy --strict: PASS
- 운영 실측 (smoke → mid → full): **본 chunk 범위 외** — 사용자 수동 실행 후 별도 measurement chunk (OHLCV 패턴 동일)

---

## [2026-05-10] docs(kiwoom): 운영 실측 measurement 완료 — full 3년 백필 34분 / failed 0 / NUMERIC 안전

`backfill_ohlcv.py` smoke → mid → full 3 단계 측정 완료. ADR § 26.5 + results.md 채움. **코드 변경 0** — 측정 결과 documentation.

### 운영 실측 결과 요약

| Stage | 명령어 요지 | total | success | failed | elapsed |
|-------|------------|-------|---------|--------|---------|
| smoke | KOSPI 10 / 1y | 6 (raw 10 → ETF 4 skip) | 6 KRX / 2 NXT | 0 | 1s |
| mid | KOSPI 100 / 3y | 78 (raw 100 → ETF 22 skip) | 78 KRX / 21 NXT | 0 | 44s |
| **full** | active 4373 / 3y | **4078** (ETF 295 skip) | **4078 KRX / 626 NXT** | **0** | **34분** |

### 운영 미해결 정량화

- **#1 페이지네이션 빈도**: 1년 daily 종목당 1 page / 3년 daily 1~2 page (since_date guard 작동)
- **#2 3년 백필 elapsed**: dry-run 추정 1h 13m → 실측 34분 (NXT 활성 15% / since_date guard 영향)
- **#3 NUMERIC(8,4) `turnover_rate`**: max 3,257.80 (cap ±9999.9999 의 33%) / ABS>1000 = 24 rows (0.0009%) → **마이그레이션 불필요**
- #4 일간 cron elapsed: 본 chunk 미측정 (scheduler_enabled 활성화 chunk 대기)
- `change_rate` / `foreign_holding_ratio` / `credit_ratio`: ka10086 daily_flow 백필 chunk 에서 측정

### Changed

- **`docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 26.5** — 측정값 4건 채움 + 신규 발견 3건 (since_date / max-stocks / ETF guard) + follow-up F6 (since_date edge case 0.13% 영향) + KRX/NXT 적재 통계
- **`src/backend_kiwoom/docs/operations/backfill-measurement-results.md`** — 빈 양식 → 측정값 전 항목 채움. TL;DR / Stage 0~3 / 측정 #1~#3 / 위험 5건 / 결정 4건 / 다음 chunk 우선순위 갱신

### Verification

- 코드 변경 0. pytest 993 cases 그대로
- DB 적재: KRX 2,732,031 rows / DISTINCT stock 4,077 / NXT 152,152 rows / DISTINCT stock 626

### follow-up 발견 (LOW 4건)

| # | 항목 | 영향 |
|---|------|------|
| F6 | since_date guard edge case (2 종목 더 과거 적재) | 0.13% rows |
| F7 | turnover_rate min -57.32 (음수 anomaly) | 키움 데이터 특성 |
| F8 | 1 종목 빈 응답 (4078 fetch / 4077 적재) | 1/4078 = 0.025% |
| (옵션 c) | ETF/ETN 자체 OHLCV 별도 endpoint | 백테스팅 가치 |

---

## [2026-05-10] feat(kiwoom): ka10081/82/83 호환 stock_code 사전 가드 + smoke 통과 검증

`backfill_ohlcv.py` smoke 운영 발견 — `kiwoom.stock` 의 active 약 6.7% (KOSPI 12%) 가 ETF/ETN/우선주 (영문 포함 코드, 예: `0000D0`, `00088K`). build_stk_cd 의 6자리 ASCII 숫자 검증에서 ValueError → errors 누적되던 것을 UseCase 가드로 사전 skip + 가시성 로깅.

### Added

- **`app/application/service/ohlcv_daily_service.py`** — `IngestDailyOhlcvUseCase.execute` active stock 조회 후 `_KA10081_COMPATIBLE_RE` (`STK_CD_LOOKUP_PATTERN` 재사용) 패턴 fullmatch 종목만 keep. skip 종목 수 + sample 5개 logger.info — 운영 가시성. 정책 옵션 (a) UseCase 가드 채택 (사용자 결정 — Migration 0, 즉시 적용, ETF OHLCV 는 향후 별도 chunk)
- **`app/application/service/ohlcv_periodic_service.py`** — `IngestPeriodicOhlcvUseCase.execute` 동일 가드 (ka10082/83 도 chart.py build_stk_cd 공유)
- 단위 테스트 +2 cases — `tests/test_ingest_daily_ohlcv_service.py::test_execute_skips_alpha_stock_codes` / `tests/test_ohlcv_periodic_service.py::test_execute_weekly_skips_alpha_stock_codes`. ETF `0000D0` + 우선주 `00088K` 사전 skip 검증 (호출 자체 차단)

### Verification

- pytest: 991 → **993 cases (+2)** / All passed (회귀 0)
- mypy --strict: app/ 72 files / 0 errors
- ruff check: All passed
- 실 운영 smoke 통과: `--period daily --years 1 --only-market-codes 0 --max-stocks 10`
  - `active 10 중 4 종목 skip (ETF/ETN/우선주 추정), sample=['0000D0', '0000H0', '0000J0', '0000Y0']`
  - `total: 6 / success_krx: 6 / success_nxt: 2 / failed: 0 / elapsed: 1s`
  - **3 fix (since_date / max-stocks / ETF guard) 모두 함께 작동 검증**

### 운영 미해결 #9 해소

- ETF/ETN stock_code ValueError 12% → **0건** (사전 가드 차단). ETF/ETN 자체 OHLCV 는 향후 별도 chunk (옵션 c)

---

## [2026-05-10] fix(kiwoom): backfill_ohlcv `--max-stocks` 가 실 백필에서 무시되던 CLI bug fix

직전 since_date guard chunk 의 smoke 검증 중 발견된 **CLI 사용성 차단 bug** 즉시 수정.

### Fixed

- **`scripts/backfill_ohlcv.py`** `async_main` — `--max-stocks N` 인자가 `_count_active_stocks` (dry-run 추정) 만 적용되고 실 백필 호출 시 `effective_stock_codes=None` 으로 치환되어 active 전체 처리되던 bug. 직전 smoke 가 `--max-stocks 10` 의도로 KOSPI 2031 종목 mid-scale 가 됨. resume 분기와 동일하게 `_list_active_stock_codes` 호출해 explicit 종목 list 를 UseCase 에 전달하도록 수정. 변수명 `resume_only_codes` → `explicit_stock_codes` (resume / max_stocks 단독 모두 채우는 의미 명확)

### Added

- 단위 테스트 +1 case — `tests/test_backfill_ohlcv_cli.py::test_list_active_stock_codes_applies_max_stocks_limit`. `_count_active_stocks` + `_list_active_stock_codes` 가 동일 max_stocks 적용 검증 (DB 통합 테스트, testcontainers 활용)

### Verification

- pytest: 990 → **991 cases (+1)** / All passed (회귀 0)
- mypy --strict: scripts/backfill_ohlcv.py / 0 errors
- ruff check: All passed

---

## [2026-05-10] fix(kiwoom): backfill_ohlcv 페이지네이션 종료 조건 신규 + dotenv autoload 보강

`backfill_ohlcv.py --period daily --years 1 --alias prod` smoke 첫 실 호출에서 발견된 운영 차단 버그 1건 즉시 수정 + dotenv autoload 누락 보완.

### Fixed (운영 차단 버그)

- **`app/adapter/out/kiwoom/chart.py`** — `KiwoomChartClient.fetch_daily/weekly/monthly` 에 `since_date` 파라미터 신규. 페이지의 가장 오래된 row date <= since_date 면 다음 page 요청 중단 + 결과 list 에서 since_date 미만 row 제거. **운영 차단** (ka10081 은 base_dt 만 받고 종료 범위가 없어 종목 상장일까지 무한 페이징 → max_pages 도달로 fail). KOSPI 1980년대 상장 종목 (예: `002810`) 이 직접적 영향. mock 테스트는 cont-yn=N 으로 짧게 종료해서 발견 못 함

### Changed

- **`app/application/service/ohlcv_daily_service.py`** — `IngestDailyOhlcvUseCase.execute` / `_ingest_one` 에 `since_date` 옵션 전파. 디폴트 None → 운영 cron 기존 동작 호환
- **`app/application/service/ohlcv_periodic_service.py`** — 동일 (주/월봉 ka10082/83)
- **`scripts/backfill_ohlcv.py`** — `since_date=start_date` 전달 (`--years` / `--start-date` 가 실질적 페이지네이션 cap 으로 작동). dotenv autoload 추가 (register/sync 와 동일 패턴 — 직전 세션 누락분 보완)
- 단위 테스트 +2 cases — `test_kiwoom_chart_client.py` since_date page break / since_date=None 기존 동작 유지

### Verification

- pytest: 988 → **990 cases (+2)** / All passed (회귀 0)
- mypy --strict: app/ 72 files / scripts/backfill_ohlcv.py 1 file / 0 errors
- ruff check: All passed
- 실 운영: `--period daily --years 1 --only-market-codes 0` (KOSPI) — 2031 종목 / **1782 success_krx / 354 success_nxt / 251 ValueError (ETF/ETN stock_code 영문)** / 0 KiwoomMaxPagesExceededError / **8m 55s** (avg 0.3s/stock — since_date guard 1 page 종료 검증)

### 운영 미해결 #1 정량화 (since_date guard 적용 후)

- **ka10081 페이지네이션 빈도** (1년 daily): 종목당 **1 page** (since_date 가 page 1 안에서 break). ADR § 26.5 갱신 대상

### 신규 발견 (다음 chunk 분리)

- **CLI bug**: `--max-stocks 10` 가 dry-run 만 적용. 실 백필은 active 전체 처리 (smoke 가 mid-scale 가 됨). `effective_stock_codes` 계산 시 max_stocks 미반영
- **ETF/ETN stock_code 호환성**: 251 종목 (12.36%) ValueError — `0000D0`, `0001P0` 같은 영문 포함 코드. ka10081 호환성 가정 (모든 active stock = 6자리 ASCII 숫자) 검증 누락. ka10099 sync 가 ETF/ETN 도 stock 테이블에 적재하므로 별도 가드 필요

---

## [2026-05-10] fix(kiwoom): 운영 검증 도구 보강 + 실 호출에서 발견된 2 차단 버그 fix

ka10099 첫 실 호출 (`sync_stock_master.py --alias prod`) 에서 발견된 운영 차단 버그 2건 즉시 수정. 동시에 admin 도구 사용성 보강 (.env 자동 로드 + 명명 호환). **5 시장 / 4373 active stock / 630 NXT 적재 성공** (1.7s).

### Fixed (운영 차단 버그)

- **`app/adapter/out/kiwoom/_client.py`** (line 216, 299) — `next-key: ''` (빈 문자열) 을 형식 오류로 reject 하던 정규식 검증을 빈값 허용으로 수정. **전체 키움 API 차단** 이슈 (모든 자동 cron + 모든 endpoint 영향). 실 응답: `cont-yn=N + next-key=""` (페이지네이션 종료 신호) — mock 테스트는 빈값 사용 안 했어서 발견 못 함
- **`app/adapter/out/persistence/repositories/stock.py`** — `upsert_many` 가 asyncpg bind parameter 한도 (32767) 초과. KOSPI 2440 × 14 컬럼 = 34160 → `InterfaceError`. 1000/batch chunk 분할 (`_UPSERT_BATCH=1000`) 로 한 batch 14000 < 한도

### Added

- **`docs/operations/credential-master-key-guide.md`** (신규, ~250줄) — 마스터키 운영 가이드 (왜 필요한가 / 무엇이 아닌가 / 생성·보관·회전·분실)
- 단위 테스트 +5 cases — `test_kiwoom_client.py` 빈 next-key 2 / `test_stock_repository.py` 2500 row chunking 1 / `test_register_credential_cli.py` API_KEY fallback + precedence 2

### Changed

- **`scripts/register_credential.py`** — `python-dotenv` autoload (backend_kiwoom/.env.prod → 루트 ../../.env.prod 순서). `KIWOOM_API_KEY/SECRET` (키움 공식 명명) fallback 추가. docstring 갱신
- **`scripts/sync_stock_master.py`** — dotenv autoload 동일 적용
- STATUS / HANDOFF 갱신

### Verification

- pytest: 985 → **988 cases (+3)** / All passed (회귀 0)
- mypy --strict: 76 files / 0 errors
- ruff check: All passed
- 실 운영: ka10099 5 시장 / 4373 stock / 1.7s elapsed / all_succeeded=True

### 운영 미해결 #1 검증 (부분)

- **ka10099 페이지네이션 빈도**: **단일 호출** (cont-yn=N, 페이지 없음). 4782 종목 1회 응답. ADR § 26.5 갱신 대상

---

## [2026-05-09] refactor(kiwoom): DATABASE_URL → KIWOOM_DATABASE_URL rename (다른 프로젝트 격리)

루트의 다른 프로젝트 (signal 등) DATABASE_URL 과 격리. backend_kiwoom 만의 namespace 명시.

### Changed

- `app/config/settings.py` — 필드 `database_url` → `kiwoom_database_url` (env: `KIWOOM_DATABASE_URL`)
- `app/adapter/out/persistence/session.py` — `settings.database_url` → `settings.kiwoom_database_url`
- `migrations/env.py` — 동일
- `tests/conftest.py` — testcontainers URL 을 `KIWOOM_DATABASE_URL` env 로 export
- `tests/test_settings.py` — default 검증 env 이름 변경
- `docs/operations/backfill-measurement-runbook.md` — 환경변수 표 + 마스터키 설명 강화 (계좌번호와 무관 명시)
- `scripts/register_credential.py` / `sync_stock_master.py` — docstring 의 export 예시 변경

### Verification

- pytest: 983 cases / All passed (회귀 0)
- mypy --strict: 76 files / 0 errors
- ruff check: All passed
- 실 환경 검증: `KIWOOM_DATABASE_URL` env → alembic current = head / backfill_ohlcv.py dry-run = active 0 분기 정상

---

## [2026-05-09] chore(kiwoom): backend_kiwoom 전용 docker-compose 신규 + runbook 실 환경 값 채움

`62079f1` 의 후속 보강 — runbook 의 placeholder 값 (`postgresql+asyncpg://user:pass@host:5432/...`) 을 실제 docker-compose 기준 값으로 채우고 도커로 직접 검증.

### Added

- `src/backend_kiwoom/docker-compose.yml` (신규) — postgres:16-alpine + kiwoom_db (kiwoom/kiwoom). 호스트 5433:5432 매핑 (signal-db 5432 충돌 회피). volume + healthcheck (pg_isready)

### Changed

- `docs/operations/backfill-measurement-runbook.md` § 1.1~1.5 — 도커 컨테이너 기동 + 실 환경 값 (`postgresql+asyncpg://kiwoom:kiwoom@localhost:5433/kiwoom_db`) + ERD 위치 안내 (migrations/versions/*.py 가 진실 출처)

### Verification

- docker compose up -d → healthy (postgres 16.13)
- alembic upgrade head → 12 마이그레이션 (001~012) 모두 적용
- backfill_ohlcv.py dry-run × daily/weekly/monthly × NXT on/off 정상

---

## [2026-05-09] feat(kiwoom): 자격증명 등록 + 종목 마스터 sync admin CLI 신규 (ka10099 sync 진입 도구)

운영 실측의 선행 단계 (kiwoom.stock 채우기) 자동화. uvicorn 기동 + curl 흐름 대신 단일 명령어로 진입 가능. 운영 라우터 `POST /api/kiwoom/stocks/sync` 와 동일 효과.

### Added

- **`scripts/register_credential.py`** (신규, ~120줄) — 키움 자격증명 등록/갱신 admin 도구
  - argparse: `--alias` (필수), `--env {prod|mock}` (필수)
  - env: `KIWOOM_APPKEY`, `KIWOOM_SECRETKEY`, `KIWOOM_CREDENTIAL_MASTER_KEY` 필수
  - 동작: Fernet 암호화 → `kiwoom.kiwoom_credential` upsert. 마스킹된 appkey 출력
  - exit code: 0 success / 2 env 누락 / 3 마스터키 형식 오류 + DB 예외
- **`scripts/sync_stock_master.py`** (신규, ~150줄) — ka10099 1회 sync admin 도구
  - argparse: `--alias` (필수)
  - 동작: TokenManager + KiwoomClient + KiwoomStkInfoClient + SyncStockMasterUseCase (main.py 의 sync_stock factory 패턴 재사용). 5 시장 격리 sync
  - 출력: `format_summary` (5 시장 outcome + 합계 + elapsed)
  - exit code: 0 success / 1 partial (한 시장 이상 error) / 2 alias 미등록·비활성·한도 / 3 시스템
- **`tests/test_register_credential_cli.py`** (신규, 7 cases) — argparse 3 + env 검증 4
- **`tests/test_sync_stock_master_cli.py`** (신규, 4 cases) — argparse 2 + format_summary 2

### Changed

- `docs/operations/backfill-measurement-runbook.md` — § 1.4 alias 등록 (register_credential.py 명령어 + 보안 주의), § 1.5 종목 마스터 sync (sync_stock_master.py 명령어 + 출력 예시) 갱신

### Verification

- pytest: **972 → 983 cases** (+11) / All passed
- mypy --strict: **76 files / 0 errors** (74 → 76)
- ruff check + format: All passed
- coverage: 본 chunk 측정 생략 (admin 도구 — 사용자 환경 전용)

---

## [2026-05-09] docs(kiwoom): 운영 실측 사전 준비 — runbook + 결과 템플릿 + ADR § 26 (코드 변경 0)

**Phase C-운영실측 사전 준비** — 다음 chunk (사용자 수동 운영 실측) 에 필요한 문서 일괄 정비. C-backfill CLI 로 운영 미해결 4건 (페이지네이션/3년 시간/NUMERIC magnitude/sync) 을 정량화하기 위한 단계별 가이드. 코드 변경 0, 문서 3 신규 + 3 갱신.

### Added

- **`src/backend_kiwoom/docs/operations/backfill-measurement-runbook.md`** (신규) — 환경변수 / 4단계 명령어 시퀀스 (dry-run → smoke 10 → mid 100 → full 3000) / NUMERIC 분포 SQL / 트러블슈팅 / 안전 장치
- **`src/backend_kiwoom/docs/operations/backfill-measurement-results.md`** (신규) — 사용자가 측정 후 채울 양식. 운영 미해결 4건 정량화 표 + 새 위험 수집 + 다음 chunk 우선순위 갱신 자리
- ADR-0001 § 26 — 운영 실측 가이드 + 결과 자리 (사용자 측정 후 § 26.5 표 채움)

### Changed

- STATUS.md § 4 / § 5 — 운영 실측 후 정량화될 항목 표시 (변경 없음, 출처만 명시)
- HANDOFF.md / CHANGELOG.md / STATUS.md 갱신

### Verification

- 코드 변경 0 — pytest / mypy / ruff 모두 직전 commit (`055e81e`) 그대로 (972 tests / 96% coverage / 74 files 0 mypy errors)

---

## [2026-05-09] feat(kiwoom): Phase C-backfill — OHLCV 통합 백필 CLI (daily/weekly/monthly period dispatch + dry-run + resume) — 1R CONDITIONAL → PASS, 972 tests / 96% coverage

**Phase C-backfill** — `scripts/backfill_ohlcv.py` 신규 CLI. Phase C 의 daily/weekly/monthly OHLCV 통합 처리. 운영 라우터의 1년 cap 우회를 위해 UseCase 시그니쳐에 `_skip_base_date_validation` 키워드 옵션 추가 (디폴트 False — R1 invariant 유지). 운영 미해결 4건 (페이지네이션/3년 시간/NUMERIC magnitude/sync 시간) 정량화 측정 도구. **Phase C 90% → 95%**.

### Added

- **`scripts/backfill_ohlcv.py`** (신규, ~480줄) — OHLCV 통합 백필 CLI:
  - argparse — `--period {daily|weekly|monthly}` (필수) + `--alias` (필수) + `--years N` (기본 3) + `--start-date` / `--end-date` / `--only-market-codes` / `--only-stock-codes` / `--dry-run` / `--resume` / `--max-stocks` / `--log-level`
  - period dispatch — daily → IngestDailyOhlcvUseCase / weekly,monthly → IngestPeriodicOhlcvUseCase
  - dry-run mode — 종목 수 + 추정 페이지 + 추정 시간 (lower-bound, ±50% margin) 출력. DB 미적재
  - resume mode — `compute_resume_remaining_codes` 가 KRX 테이블의 max(trading_date) per stock 조회 → 미적재 종목만 진행 (gap detection 별도 chunk)
  - exit code 4 분기 — 0 success / 1 partial (failed > 0) / 2 args / 3 system
  - `_build_use_case` async context manager — try/finally 로 KiwoomClient.close + engine.dispose 보장
- **`tests/test_backfill_ohlcv_cli.py`** (신규, 25 cases) — argparse / period dispatch / dry-run / resume / exit code / DB 통합
- **`tests/test_skip_base_date_validation.py`** (신규, 8 cases) — UseCase 시그니쳐 확장 — default behavior + skip behavior 양쪽 검증
- `docs/plans/phase-c-backfill-ohlcv.md` (신규) — chunk plan doc

### Changed

- **`app/application/service/ohlcv_daily_service.py`** — `execute` / `refresh_one` 에 `_skip_base_date_validation` 키워드 옵션 추가 (디폴트 False) + `only_stock_codes` 인자 추가. `_validate_base_date` 에 `skip_past_cap` 옵션 추가 (미래 가드는 항상 유지)
- **`app/application/service/ohlcv_periodic_service.py`** — 동일 옵션 추가. period 검증은 `skip_past_cap` 와 무관 (YEARLY 항상 NotImplementedError)
- `scripts/dry_run_ka10086_capture.py` (E-3 기존 코드 fix) — Migration 008 (C-2γ) 에서 DROP 된 `foreign/institutional/individual_net_purchase` 컬럼 출력 제거. 작은 fix 라 본 chunk 에 합침

### Fixed (1차 리뷰 적용)

- **HIGH H-1**: `--resume` flag dead 문제 — `compute_resume_remaining_codes` 헬퍼 추가 + `async_main` 에서 호출. KRX 테이블의 max(trading_date) per stock 조회 → 미적재 종목만 `only_stock_codes` 로 UseCase 에 전달
- **MEDIUM M-1**: `--only-stock-codes` UseCase 미전달 — UseCase 2개에 `only_stock_codes` 인자 추가 + CLI 의 `effective_stock_codes` 로 resume + only-stock-codes 통합 처리

### Verification

- mypy --strict: 74 source files / 0 errors
- ruff check + format: All passed
- pytest: **939 → 972 cases** (+33) / coverage **97% → 96%** (CLI 신규 ~480줄로 분모 증가, 신규 코드 80%+ 커버)
- 자동 분류 = 일반 기능 (general) → 2b 적대적 / 3-4 보안 / 3-5 런타임 / 4 E2E 자동 생략

### R1 invariant 유지 검증

| 항목 | 결과 |
|------|------|
| `_skip_base_date_validation` 디폴트 False — 양 UseCase 모두 | PASS |
| 운영 라우터 호출 경로 변경 없음 (파라미터 추가만) | PASS |
| 미래 가드 항상 유지 (`skip_past_cap=True` 여도 미래 ValueError) | PASS — 단위 검증 |
| CLI 에서만 `_skip_base_date_validation=True` 전달 | PASS |
| `only_stock_codes` 디폴트 None — UseCase 의 `if only_*_codes:` 분기와 일관 | PASS |

### Defer (다음 chunk)

- **운영 실측 (사용자 수동)** — 100 종목 → active 3000 실측. 운영 미해결 4건 정량화. 결과 → ADR § 26 (또는 후속) + STATUS § 4 해소
- **gap detection** — 일자별 missing detection (resume 정확도 향상)
- **daily_flow (ka10086) 백필** — `scripts/backfill_daily_flow.py` (OHLCV 와 구조 다름)
- **L-2 / E-1 / E-2 / M-3 refactor R2** — 일괄 정리

---

## [2026-05-09] feat(kiwoom): Phase C-3β — ka10082/83 주/월봉 OHLCV 자동화 (UseCase + Router 4 path + Scheduler 2 job) — 1R CONDITIONAL → PASS, 939 tests / 97% coverage

**Phase C-3β** — C-3α 인프라 위에 자동화 마무리. ka10082 (주봉) + ka10083 (월봉) endpoint 2건 완료 (production-ready). ka10081 IngestDailyOhlcvUseCase 패턴 ~95% 복제 + period dispatch + R1 정착 패턴 5종 전면 적용. **25 endpoint 진행: 8 → 10 (40%)**.

### Added

- **`IngestPeriodicOhlcvUseCase`** in `app/application/service/ohlcv_periodic_service.py` (신규) — period dispatch (WEEKLY/MONTHLY). `execute(*, period, base_date, only_market_codes)` + `refresh_one(stock_code, *, period, base_date)`. `_validate_period` 가 YEARLY → NotImplementedError (P2 chunk). per-stock per-exchange try/except + KRX→NXT 순서 + R1 L-5 NXT Exception 격리. 17 cases (test_ohlcv_periodic_service)
- **`routers/ohlcv_periodic.py`** (신규, 4 path) — `POST /api/kiwoom/ohlcv/{weekly,monthly}/sync` + `POST /api/kiwoom/stocks/{code}/ohlcv/{weekly,monthly}/refresh`. 공용 핸들러 `_do_sync` / `_do_refresh` (period 만 caller 결정). DTO `OhlcvPeriodicSyncResultOut` (R1 errors tuple). 10 cases (test_ohlcv_router_periodic)
- **`WeeklyOhlcvScheduler` + `MonthlyOhlcvScheduler`** in `app/scheduler.py` — OhlcvDailyScheduler 패턴 ~95% 복제. cron: weekly = **금 KST 19:30** (H-7 — daily_flow 19:00 후 30분 / 30분 간격 일관) / monthly = **매월 1일 KST 03:00**. 11 cases (test_weekly_monthly_ohlcv_scheduler)
- **`fire_weekly_ohlcv_sync` + `fire_monthly_ohlcv_sync`** in `app/batch/{weekly,monthly}_ohlcv_job.py` — fire 콜백 (실패율 알람 / 예외 swallow). ohlcv_daily_job 패턴 일관
- **`IngestPeriodicOhlcvUseCaseFactory`** in `app/adapter/web/_deps.py` — get/set/reset (4 cases / test_ohlcv_periodic_deps)
- **`scheduler_weekly_ohlcv_sync_alias` + `scheduler_monthly_ohlcv_sync_alias`** in `app/config/settings.py` — alias fail-fast 검증 추가

### Changed

- `app/main.py` — lifespan factory `_ingest_periodic_ohlcv_factory` 등록 + WeeklyOhlcvScheduler + MonthlyOhlcvScheduler 시작/종료 (LIFO order — 신규가 먼저 reset). alias fail-fast 목록에 weekly/monthly 추가. `ohlcv_periodic_router` include
- `tests/test_scheduler.py` + `tests/test_stock_master_scheduler.py` — 신규 alias env 추가 (lifespan smoke test 호환)
- `app/adapter/web/_deps.py` — IngestPeriodicOhlcvUseCase import + 5 reset 함수 갱신 (LIFO)

### Fixed (1차 리뷰 적용)

- **HIGH H-1**: `_do_sync` 에 KiwoomError 계열 5 except 블록 추가 (KiwoomBusinessError 400 + msg echo 차단 / KiwoomCredentialRejectedError 400 / KiwoomRateLimitedError 503 / KiwoomUpstreamError·KiwoomResponseValidationError 502 / KiwoomError fallback 502). `_do_refresh` 와 대칭
- **MEDIUM M-1**: `_validate_period` 의 `period.value == "daily"` dead code 제거 (Period enum DAILY 미존재). docstring 갱신 — "Period.DAILY 가 추가되는 시점에 ValueError 분기 추가"
- **MEDIUM M-2**: service docstring "재사용" → "동일 구조 복제 (공통 추출은 별도 refactor chunk 로 연기)" 명확화
- **LOW L-1**: `MonthlyOhlcvScheduler.start()` docstring 추가 (5 sibling scheduler 와 대칭성 회복)
- **LOW L-3**: `_do_refresh` 의 KiwoomBusinessError 로그에 `msg=exc.message` 포함 (운영 디버그 정보)

### Verification

- mypy --strict: 72 source files / 0 errors
- ruff check + format: All passed
- pytest: **897 → 939 cases** (+42) / coverage **97% 유지**
- 자동 분류 = 계약 변경 → 2b 적대적 / 3-4 보안 / 4 E2E 자동 생략 (백엔드 전용)

### H-7 cron 충돌 검증

| 시각 | cron | 비고 |
|------|------|------|
| 17:30 mon-fri | stock_master_sync | 기존 |
| 18:00 mon-fri | stock_fundamental_sync | 기존 |
| 18:30 mon-fri | ohlcv_daily_sync | 기존 |
| 19:00 mon-fri | daily_flow_sync | 기존 |
| **19:30 fri** | **weekly_ohlcv_sync (신규)** | daily_flow 19:00 후 30분 (mon-fri 19:00 와 무충돌) |
| **매월 1일 03:00** | **monthly_ohlcv_sync (신규)** | 다른 cron 없는 새벽 |
| 일 03:00 | sector_sync_weekly | 기존 (sun 03:00 — monthly 와 다른 day) |

### Defer (다음 chunk)

- **C-backfill** — `scripts/backfill_ohlcv.py --period {daily|weekly|monthly}` CLI + 3년 백필 실측 (운영 미해결 4건 일괄 해소)
- **운영 first-call 검증** — `dt` 의미 / 응답 list 키 명 / 일봉 vs 키움 주월봉 cross-check (Phase H)
- **L-2 / E-1 / E-2 + M-3** — refactor R2 chunk (NotImplementedError 핸들러 / ka10081 sync KiwoomError 핸들러 / `# type: ignore` → `cast()` / reset_* docstring)
- **ka10094 (년봉, P2)** — Migration 1 + UseCase YEARLY 분기 활성화

---

## [2026-05-09] feat(kiwoom): Phase C-3α — ka10082/83 주/월봉 OHLCV 인프라 (Migration 009-012 + Period enum + Periodic Repository) — 1R PASS, 897 tests / 97% coverage

**Phase C-3α** — ka10082 (주봉) + ka10083 (월봉) **인프라 레이어** 일괄 도입. ka10081 (일봉) 패턴 ~95% 복제 + R1 정착 패턴 (`fetched_at` non-Optional / Mixin 재사용 / Repository dispatch) 사전 적용. 자동화 (UseCase + Router + Scheduler) 는 C-3β.

### Added

- **Migration 009-012** — `kiwoom.stock_price_weekly_krx` / `weekly_nxt` / `monthly_krx` / `monthly_nxt` 4 테이블. `_DailyOhlcvMixin` 컬럼 구조 100% 동일. UNIQUE(stock_id, trading_date, adjusted) + FK CASCADE + 인덱스 2 each. C-1α (005/006) 패턴 일관 직선 체인. testcontainers 26 cases (test_migration_009_012)
- **`Period(StrEnum)`** in `app/application/constants.py` — WEEKLY/MONTHLY/YEARLY 3값. DAILY 는 IngestDailyOhlcvUseCase 별도 처리 (hot path). YEARLY 는 enum 노출하되 Migration/Repository 미구현 (P2). 8 cases (test_period_enum)
- **`StockPriceWeeklyKrx`/`Nxt` + `StockPriceMonthlyKrx`/`Nxt` ORM** in `app/adapter/out/persistence/models/stock_price_periodic.py` — `_DailyOhlcvMixin` 재사용 (계획서 H-2). 4 모델 모두 `models/__init__.py` 에 re-export
- **`StockPricePeriodicRepository`** in `app/adapter/out/persistence/repositories/stock_price_periodic.py` — `_MODEL_BY_PERIOD_AND_EXCHANGE` dict 4 매핑 (period+exchange dispatch). `upsert_many` (ON CONFLICT DO UPDATE, B-γ-1 명시 update_set 패턴) + `find_range` (start>end ValueError). YEARLY/SOR 호출 시 ValueError. NormalizedDailyOhlcv 재사용 (period 무관). 18 cases (test_stock_price_periodic_repository)
- **`KiwoomChartClient.fetch_weekly` + `fetch_monthly`** in `app/adapter/out/kiwoom/chart.py` — fetch_daily 패턴 복제 (cont-yn 페이지네이션 + stk_cd 메아리 검증 + flag-then-raise). list 키 분기: weekly = `stk_stk_pole_chart_qry` / monthly = `stk_mth_pole_chart_qry`. 클래스 상수 `WEEKLY_API_ID`/`MONTHLY_API_ID`/`*_MAX_PAGES` 추가. fetch_daily 변경 0줄 (계획서 H-6)
- **`WeeklyChartRow` / `MonthlyChartRow` + Response 4 Pydantic** — DailyChartRow 상속 (필드 동일, `to_normalized` 부모 메서드 재사용). 23 cases (test_kiwoom_chart_client_periodic)
- `docs/plans/phase-c-3-weekly-monthly-ohlcv.md` (신규) — chunk 단위 plan doc (영향 범위 + self-check H-1~H-7 + DoD α/β 분리). R1 plan doc 패턴 복제

### Changed

- `app/adapter/out/persistence/models/__init__.py` — Weekly/Monthly 4 모델 re-export 추가
- `tests/test_migration_008.py` — `head_rev == "008_..."` 단언을 동적 단언 (`head_rev != downgrade_target`) 으로 견고화. 본 chunk 의 9-12 마이그레이션이 head 위에 추가되면서 transactional DDL 환경의 단일 트랜잭션 rollback 영향. 다음 chunk 마이그레이션 추가에도 영향 없게 보정

### Fixed

- 1차 리뷰 (sonnet) 적용:
  - **M-1**: `StockPricePeriodicRepository.upsert_many` docstring — "NormalizedDailyOhlcv 의 Daily 접두는 도메인 출처 표시, 컬럼 구조 period 무관" 명시
  - **L-1**: Migration 010/012 (NXT) 의 `trading_date` / `prev_compare_amount` / `prev_compare_sign` COMMENT 추가 — KRX/NXT 대칭성 회복
  - **L-2**: `update_set` 위 주석 추가 — ON CONFLICT key 컬럼 (stock_id, trading_date, adjusted) 의도적 제외 + 미래 컬럼 추가 시 silent contract change 차단

### Verification

- mypy --strict: 68 source files / 0 errors
- ruff check + format: All passed
- pytest: **822 → 897 cases** (+75) / coverage **92.86% → 97%** (신규 코드 100%)
- testcontainers up→down(008)→up(head) 사이클 PASS (Migration 멱등성 + H-1 검증)

### Defer (다음 chunk)

- **C-3β** — UseCase + Router + Scheduler. R1 패턴 5종 전면 적용 (errors tuple / StockMasterNotFoundError / fetched_at non-Optional / max_length=2 / NXT Exception 격리)
- 운영 검증 — `dt` 의미 (주/달 시작 vs 종료) / 응답 list 키 명 검증 / 일봉 vs 키움 주월봉 cross-check (Phase H)
- M-3 (`# type: ignore` → `cast()`) — 기존 일봉 Repository 패턴과 함께 별도 refactor chunk

---

## [2026-05-09] refactor(kiwoom): Phase C R1 — 3 도메인 일관 개선 (errors→tuple / StockMasterNotFoundError / LOW 3건) — 1R PASS, 822 tests / 92.86%

**Phase C R1 (Refactor 1)** — ADR-0001 § 19.5 (C-2β Defer 5건) + B-γ-2 동일 패턴을 3 도메인 (fundamental / OHLCV / daily_flow) 횡단 일관 정리. 외부 API contract 무변, 내부 타입·예외 안전성 강화. 다음 chunk (C-3 / Phase D) 진입 전 베이스 정착.

### Added

- `src/backend_kiwoom/app/application/exceptions.py` (신규): 공유 예외 모듈 — `StockMasterNotFoundError(ValueError)` + `__slots__ = ("stock_code",)` + 안정 메시지 형식 (`stock master not found: <code>`). domain-specific 예외는 service inline 패턴 유지 (token_service 일관)
- `src/backend_kiwoom/tests/test_application_exceptions.py` (신규, +6 cases): subclass 보증 / stock_code 노출 / except ValueError 호환 / pytest.raises 패턴 / except 순서 역방향 invariant 회귀 (M-2 / H-3 단위 증명)

### Changed — 3 service (fundamental / OHLCV / daily_flow)

- `errors: list[Outcome] = field(default_factory=list)` → `errors: tuple[Outcome, ...] = field(default_factory=tuple)` (frozen dataclass 일관)
- 내부 build local list → return 시 `tuple(errors)` 변환 (B-γ-1 frozen 강화)
- `raise ValueError("stock master not found: ...")` → `raise StockMasterNotFoundError(stock_code)` (3 raise)
- `refresh_one` NXT path: `except KiwoomError` 만 격리 → `except Exception` 추가 (R1 L-5, `execute()` 와 일관 partial-failure 모델). KRX 적재 후 NXT 실패는 응답 200 + failed=1 + errors[NXT] (전체 500 대신). fundamental 은 KRX-only 라 N/A

### Changed — 3 router (fundamentals / ohlcv / daily_flow)

- `errors: list[OutcomeOut]` → `errors: tuple[OutcomeOut, ...]` (DTO + return 변환). Pydantic v2 가 tuple 도 JSON array 로 직렬화 → wire format 무변
- `only_market_codes max_length=4 → 2` (R1 L-1) — pattern={1,2} 와 일치, dead validator 제거
- `*RowOut.fetched_at: datetime | None = None → datetime` (R1 L-2) — ORM NOT NULL + server_default 라 항상 값. test_fundamental_router fixture 1 갱신 (`fetched_at=datetime(...)` 명시)
- `if "stock master not found" in msg:` 메시지 검색 → `except StockMasterNotFoundError` 분기 (R1 M-2). subclass first 순서로 ValueError 분기 위에 배치
- `fundamentals.py:325` exchange max_length=4 주석 추가 (only_market_codes 와 다른 파라미터, R1 L-3)
- `refresh_fundamental` 의 `except ValueError` 분기 의도적 생략 명시 주석 (base_date 파라미터 없음, R1 L-4)

### Changed — 6 테스트 갱신

- `test_*_service.py` (3): `pytest.raises(ValueError, match="stock master not found")` → `pytest.raises(StockMasterNotFoundError)`
- `test_*_router.py` (3): `AsyncMock(side_effect=ValueError(...))` → `AsyncMock(side_effect=StockMasterNotFoundError(...))`. 404 status 단언 그대로
- 7개소 `Result(... errors=[])` → `errors=()` (R1 1R M-1, mypy strict + tuple 필드 일치)

### Added — ADR-0001 § 22 (R1 결과)

- 핵심 설계 결정 7건 (공유 예외 모듈 / errors tuple / DTO tuple / except StockMasterNotFoundError / NXT Exception 격리 / max_length / fetched_at non-Optional)
- 1차 리뷰 결과 (M-1 + L-1~L-4 전건 적용 후 PASS)
- ADR § 19.5 / § 17.4 Defer 해소 매핑 (5/5 ✅)
- 결과: 816 → **822 cases / 92.86% coverage** (+6) / mypy --strict 66 files 0 errors / ruff PASS

### Changed — 진척 추적 + plan doc

- `src/backend_kiwoom/STATUS.md` 갱신 — Phase C 70% → 75% / chunk 19 누적 / § 4 알려진 이슈 1건 해소
- `src/backend_kiwoom/docs/plans/phase-c-refactor-r1-error-handling.md` (신규) — R1 작업계획서 (영향 범위 / 사전 self-check H-1~H-7 / DoD)

### 검증 결과 (Quality-First)

- **0. TDD**: red 확인 (exceptions 모듈 부재 → ModuleNotFoundError)
- **1. 구현**: 신규 2 + 수정 11
- **2a. 1차 리뷰** (sonnet): MEDIUM 1 + LOW 4 권고 → 전건 적용 → PASS
- **2b. 적대적 리뷰**: 자동 분류 (계약 변경, refactor fallback) 로 생략. plan § 4 사전 self-check H-1~H-7 7 위험 모두 코드 반영
- **3. Verification 5관문**: mypy 0 / ruff PASS / pytest 822 cases / 92.86% coverage. 3-4 보안 자동 생략, 3-5 런타임은 testcontainers integration test 가 대체
- **4. E2E**: UI 변경 없음 자동 생략

---

## [2026-05-09] refactor(kiwoom): Phase C-2γ — Migration 008 (D-E 중복 컬럼 3개 DROP, 13→10) — 1R PASS, 816 tests / 93.11%

**Phase C-2γ — D-E 중복 컬럼 정리** (운영 dry-run § 20.2 #1 결정 즉시 반영). `stock_daily_flow` 의 `individual_net_purchase` / `institutional_net_purchase` / `foreign_net_purchase` 3 컬럼을 영구 DROP — D 카테고리 (`individual_net` / `institutional_net` / `foreign_volume`) 와 100% 동일값 (1,200/1,200 row 검증). 스토리지 ~23% 절감 (운영 가동 전).

### Added — Migration 008

- `migrations/versions/008_drop_daily_flow_dup_columns.py` (신규):
  - UPGRADE: `DROP COLUMN IF EXISTS` × 3
  - DOWNGRADE: 데이터 가드 (007 동일 패턴, COUNT > 0 → RAISE EXCEPTION) + `ADD COLUMN BIGINT` × 3 (NULL 복원)
- `tests/test_migration_008.py` (신규, +4 cases):
  - DROP 컬럼 부재 단언 / D 카테고리 6 유지 단언 / DOWNGRADE 가드 + alembic_version 격리 검증 / 라운드트립 컬럼 카운트 + BIGINT 타입 단언

### Changed — 5 코드 파일 (영속 레이어 → 응답 DTO 단일 진실 출처)

- `app/adapter/out/persistence/models/stock_daily_flow.py`: `Mapped[int | None]` 3 필드 정의 제거 (10 도메인)
- `app/adapter/out/persistence/repositories/stock_daily_flow.py`:
  - upsert `_payload` 3 매핑 + `update_set` 3 매핑 제거 (B-γ-1 2R B-H3 패턴 유지)
  - `created_at intentionally excluded (preserve insert timestamp)` 주석 추가 (M-4)
- `app/adapter/out/kiwoom/_records.py`:
  - `NormalizedDailyFlow` dataclass 3 필드 제거
  - `DailyMarketRow.to_normalized` 3 매핑 제거 + raw 필드 (`for_netprps` 등) 유지 정책 주석
- `app/adapter/web/routers/daily_flow.py`: `DailyFlowRowOut` 3 필드 제거 (응답 DTO breaking — 운영 미가동, downstream 0)

### Changed — 4 테스트 갱신

- `tests/test_migration_007.py`: BIGINT 9→6 (008 적용 후 head 검증) + DROP 3 부재 단언 추가
- `tests/test_stock_daily_flow_repository.py`: 2 fixture 의 3 kwarg + 1 assertion 제거
- `tests/test_daily_flow_router.py`: 1 fixture 의 3 kwarg 제거 + 응답 body 부재 단언 3 추가
- `tests/test_kiwoom_mrkcond_client.py`: 3 assertion → `dataclasses.fields()` 부재 단언 (slots 환경 오타 방어, L-1)

### Added — ADR-0001 § 21 (C-2γ 결과)

- 핵심 설계 결정 (마이그레이션 방향, DOWNGRADE 가드, raw 필드 처리, dataclass 갱신, 응답 DTO breaking, upsert update_set, test_migration_007 정정)
- 1차 리뷰 결과 (M-1 ~ M-4 + L-1 ~ L-2 모두 적용 후 PASS)
- 결과: 812 → **816 cases / 93.11% coverage** (+4) / mypy --strict 65 files 0 errors / ruff PASS

### Changed — 진척 추적 + plan doc

- `src/backend_kiwoom/STATUS.md` 갱신 (CLAUDE.md 자동 갱신 규칙 첫 적용 사례) — Phase C 진척 60% → 70% / endpoint 8/25 그대로 / chunk 18 누적
- `src/backend_kiwoom/docs/plans/endpoint-10-ka10086.md` § 12 갱신 — § 12.3 `test_migration_007` 정정 / § 12.5 H-4 정정 / § 12.6 DoD / § 12.8 운영 모니터 추가 (M-3)

### 검증 결과 (Quality-First)

- **0. TDD**: red 확인 후 진행 (Migration 008 부재 → DROP 컬럼 잔존 단언 실패)
- **1. 구현**: 5 코드 파일 변경 + Migration 008 신규
- **2a. 1차 리뷰** (sonnet): MEDIUM 4 + LOW 2 권고 → 전건 적용 → PASS
- **2b. 적대적 리뷰**: 자동 분류 (계약 변경) 로 생략. plan § 12.5 사전 self-check H-1~H-6 6 위험 모두 코드 반영
- **3. Verification 5관문**: 3-1 mypy / 3-2 ruff / 3-3 pytest+coverage 모두 통과. 3-4 보안 스캔 자동 생략. 3-5 런타임은 testcontainers + alembic head 통합 테스트로 대체
- **4. E2E**: UI 변경 없음 자동 생략

---

## [2026-05-09] docs(kiwoom): 운영 dry-run § ka10086 가설 B 확정 + D-E 중복 발견 + NXT mirror 검증 (ADR-0001 § 19/20)

**ka10086 운영 dry-run 1회차 완료** — 1,200 row 샘플 (3 종목 × KRX/NXT × 2026-05-08) 캡처 후 5종 분석. 코드 변경 없음, 산출물은 `scripts/dry_run_ka10086_capture.py` + ADR § 19/20 기록 + `.gitignore` 의 `captures/` 추가.

### Added — dry-run capture 스크립트

- `src/backend_kiwoom/scripts/dry_run_ka10086_capture.py` (신규, ~530 lines):
  - env appkey/secretkey 직접 사용 (DB / TokenManager 우회)
  - `KiwoomClient.call_paginated` 직접 호출 + `--max-rows`/`--max-pages` early termination (KiwoomMaxPagesExceededError 회피)
  - 5종 분석: fill_rate / sign_patterns / nxt_mirror / partial_mirror_breakdown / d_vs_e_equality / for_qty_invariant
  - `--analyze-only <json>` 재분석 모드 (API 재호출 없음)
  - 안전: DB write 0 (read-only) / 토큰 출력 미포함 / 앱키·시크릿키는 env 만

### Added — ADR-0001 § 19 (Phase C-2β 자동화 결정 기록)

- C-1β 패턴 mechanical 차용 / indc_mode QUANTITY 디폴트 / cron 19:00 KST / GET range cap 400일
- 1R 적대적 이중 리뷰 매핑 + Defer 5건 (C-1β 일관 개선 chunk 대기)
- 다음 chunk: § 20 결정 반영 → C-2γ Migration 008

### Added — ADR-0001 § 20 (운영 dry-run 결과)

**발견 사항 3건**:
1. **D 카테고리 ↔ E 카테고리 100% 중복** — `ind ≡ ind_netprps`, `orgn ≡ orgn_netprps`, `for_qty ≡ for_netprps` (1200/1200 row 동일). frgn ≠ for_netprps (외국계 brokerage 별개)
2. **NXT 분리 row 의미 살아있음** — 외인 컬럼 (for_qty, for_netprps) 100% mirror, 나머지 6개 0% mirror (개인/기관/외국계/프로그램/orgn_netprps/ind_netprps 분리 집계)
3. **가설 B 강력 지지** — `--XXX` 4,454건 vs `++XXX` 0건 + mixed 0건. 단방향 음수 prefix 중복

**결정 (사용자 승인)**:
- D-E 중복 3개 컬럼 → Migration 008 DROP (별도 chunk C-2γ)
- NXT 외인 mirror → 현 상태 유지 (KRX 중복 적재)
- 가설 B → 운영 채택 확정 (KOSCOM cross-check 1~2건 권고)

**미해결 (Defer)**: KOSCOM 공시 수동 cross-check / indc_tp=1 단위 mismatch / OHLCV cross-check (Phase H) / 페이지네이션 빈도 / 3년 백필 시간 / NUMERIC magnitude 분포

### Changed — .gitignore

- `src/backend_kiwoom/.gitignore` — `captures/` 추가. vendor raw 응답 (Kiwoom 제공 데이터) 외부 노출 차단. 분석 결과는 ADR / CHANGELOG 요약으로만 보관

---

## [2026-05-09] feat(kiwoom): Phase C-2β — ka10086 일별 수급 자동화 (UseCase + Router + Scheduler + Lifespan, 이중 리뷰 1R PASS, 812 tests / 93.13%)

**Phase C 네 번째 chunk** — ka10086 자동화 레이어 (UseCase + Router + Scheduler + Lifespan). C-2α 인프라 위에 자동화만 얹는 구조. C-1β (ka10081 자동화) 패턴을 daily_flow 도메인으로 mechanical 차용.

자동 분류: **계약 변경 (contract)** + `--force-2b` 적대적 리뷰 강제. 1R PASS (2a sonnet + 2b opus 모두 CRITICAL/HIGH 0). MEDIUM 2건은 C-1β 동일 패턴이라 본 chunk 범위 외로 보류.

### Decisions

- **C-1β 패턴 mechanical 차용** — UseCase / Router / Scheduler / Lifespan / Settings 시그니처 그대로 daily_flow 로 치환
- **indc_mode 프로세스당 단일 정책** — lifespan factory 가 `DailyMarketDisplayMode.QUANTITY` 하드코딩 주입 (백테스팅 시그널 단위 일관성, 계획서 § 2.3 권장)
- **cron = KST mon-fri 19:00** (ohlcv 18:30 + 30분 후) — ohlcv 적재 완료 후 수급 적재 시점에 stock master / OHLCV 모두 최신화 보장
- **backfill 스크립트 보류** — C-1β 동일 방식, 별도 chunk (운영 정책 확정 후)

### Added — IngestDailyFlowUseCase + Outcome/Result

- `app/application/service/daily_flow_service.py` (신규) — `IngestDailyFlowUseCase`:
  - 두 진입점: `execute(*, base_date, only_market_codes)` + `refresh_one(stock_code, *, base_date)`
  - per-(stock, exchange) try/except — KiwoomError + Exception 안전망 (C-1β 일관)
  - KRX/NXT 분리 ingest — `nxt_collection_enabled` settings flag + `stock.nxt_enable` 이중 게이팅
  - `refresh_one` NXT 격리 (KRX 성공 후 NXT 실패 시 errors 격리, 전체 raise 안 함 — C-1β 2a-M1/2b-L3 일관)
  - `_validate_base_date` (today - 365 ~ today) + `_validate_market_codes` (StockListMarketType 화이트리스트, silent no-op 차단)
  - `DailyFlowSyncOutcome` / `DailyFlowSyncResult` slots dataclass (error_class 만 echo, vendor 응답 차단)

### Added — POST/GET /api/kiwoom/daily-flow* 라우터

- `app/adapter/web/routers/daily_flow.py` (신규):
  - POST `/daily-flow/sync` (admin, body: base_date + only_market_codes)
  - POST `/stocks/{code}/daily-flow/refresh` (admin, query: alias + base_date)
  - GET `/stocks/{code}/daily-flow?start=&end=&exchange=` (DB only, KRX/NXT pattern, 400일 cap)
  - KiwoomError 5계층 매핑 — business→400 / credential→400 / rate→503 / upstream/validation→502 / fallback→502
  - KiwoomBusinessError.message 응답 echo 차단 (logger 만 기록, detail 은 비식별 메타)
  - `DailyFlowRowOut` Pydantic (13 영속 필드 + indc_mode + 메타)

### Added — fire_daily_flow_sync 콜백 + DailyFlowScheduler

- `app/batch/daily_flow_job.py` (신규) — `fire_daily_flow_sync`:
  - 모든 예외 swallow (cron 연속성)
  - 실패율 > 10% → logger.error (oncall 알람) + sample[:10] (vendor string echo 없음)
  - failed > 0 + ratio ≤ 10% → logger.warning (부분 실패)
- `app/scheduler.py` (확장) — `DailyFlowScheduler`:
  - `DAILY_FLOW_SYNC_JOB_ID = "daily_flow_sync_daily"`
  - cron mon-fri 19:00 KST + max_instances=1 + coalesce=True + replace_existing=True
  - start 멱등성 + shutdown wait=True 안전 + enabled=False 시 no-op

### Added — IngestDailyFlowUseCaseFactory + lifespan 통합

- `app/adapter/web/_deps.py` (확장) — `IngestDailyFlowUseCaseFactory` 타입 + get/set/reset_ingest_daily_flow_factory + reset_token_manager 일괄 unset
- `app/config/settings.py` (확장) — `scheduler_daily_flow_sync_alias: str = ""` 필드 + lifespan fail-fast 검증 대상 추가
- `app/main.py` (확장):
  - `_ingest_daily_flow_factory` lifespan factory — KiwoomClient + KiwoomMarketCondClient 빌드 + close 보장
  - `daily_flow_indc_mode = DailyMarketDisplayMode.QUANTITY` 하드코딩 (프로세스당 단일 정책)
  - `DailyFlowScheduler.start` startup + `shutdown(wait=True)` teardown 역순 (daily_flow → ohlcv → fundamental → stock → sector)
  - `reset_ingest_daily_flow_factory()` teardown 시 호출 (1R 2b M4 fail-closed)
  - `daily_flow_router` include

### Added — 52 신규 테스트 (812 / 93.13%)

- `tests/test_ingest_daily_flow_service.py` (20 cases) — KRX-only / KRX+NXT / NXT skip / 부분 실패 / boundary date / refresh_one / inactive skip / indc_mode 전달 + 디폴트 / 빈 응답 / 적재 검증 / 화이트리스트 / cross-stock 회귀
- `tests/test_daily_flow_router.py` (17 cases) — admin 401 / KiwoomError 5계층 매핑 / message echo 차단 회귀 / GET range cap / SOR 차단 / inverted window / 3 시나리오 단일 lifetime
- `tests/test_daily_flow_scheduler.py` (9 cases) — 콜백 logger 4종 + scheduler 5종 (멱등성 + cron field 19:00 KST mon-fri)
- `tests/test_daily_flow_deps.py` (4 cases) — get 503 / set-then-get / reset_token_manager 일괄 / 단독 reset
- `tests/test_scheduler.py` + `tests/test_stock_master_scheduler.py` (회귀 1줄씩) — `SCHEDULER_DAILY_FLOW_SYNC_ALIAS` 환경변수 추가

### Added — DoD § 10 체크리스트 갱신

- `src/backend_kiwoom/docs/plans/endpoint-10-ka10086.md` § 10.1 / 10.2 — C-2β 코드 7개 / 테스트 5 카테고리 모두 [x] 마킹

### Verified — 이중 리뷰 1R PASS (CRITICAL/HIGH 0)

- **2a 일반 품질 (Sonnet)**: PASS, MEDIUM 2건 (errors mutable list / ValueError 메시지 검색 — 둘 다 C-1β 동일 패턴, 본 chunk 범위 외)
- **2b 적대적 보안 (Opus)**: PASS, C-1β 9개 핵심 보안 패턴 일관 검증 (vendor echo 차단 / admin guard / KiwoomError 매핑 / per-(stock,exchange) outcome / only_market_codes 화이트리스트 / GET range cap / cross-stock pollution / factory unset / fail-fast 순서)

### Known Issues (이번 세션 한정)

- **MEDIUM 2 (C-1β 상속)**: `errors: list` mutable + `"stock master not found" in msg` 문자열 검색 — 다음 chunk 에서 일관 개선 권고 (errors → tuple / StockMasterNotFoundError 전용 예외)
- **LOW 5 (C-1β 상속)**: only_market_codes max_length=4 vs pattern={1,2} dead constraint / DailyFlowRowOut.fetched_at None 타입 / CredentialNotFoundError·Inactive·CapacityExceeded 라우터 테스트 미커버 / GET exchange=NXT DB 분기 테스트 미커버 / refresh_one NXT 비-Kiwoom Exception 전파
- **운영 검증 대기**: 가설 B (`--714`→-714) 정확성 / R15 단위 (외인 순매수 indc_tp 무시 항상 수량 가정) / NXT 가 KRX mirror 인지 cross-check / 페이지네이션 빈도 / active 3000 + NXT 1500 sync 실측 시간

---

## [2026-05-09] feat(kiwoom): Phase C-2α — ka10086 일별 수급 인프라 (Migration 007 + ORM + Repository + Adapter + helpers, 이중 리뷰 1R PASS, 760 tests / 93.43%)

**Phase C 세 번째 chunk** — ka10086 (일별주가요청) 의 인프라 (Migration + ORM + Repository + Adapter + helpers). ka10081 의 짝꿍 — 백테스팅 시그널 보강 (투자자별/외인/신용). UseCase + Router + Scheduler 는 C-2β 에서.

자동 분류: **계약 변경 (contract)** + `--force-2b` 적대적 리뷰 강제. 1R HIGH 0 / MEDIUM 3 (2a 1 + 2b 2) / LOW 9 → 3건 즉시 적용 + 회귀 4 추가 → **2R 진입 없이 PASS** (CRITICAL/HIGH 0).

### Decisions (사용자 승인)

- **chunk 분할** — C-2α (인프라) + C-2β (자동화) (B-γ-1/2, C-1α/β 패턴 일관)
- **이중 부호 처리 = 가설 B** (`--714` → -714) — 운영 dry-run 후 raw 응답 + KOSCOM 공시 cross-check 확정 예정
- **indc_mode 디폴트 = QUANTITY (수량)** — 백테스팅 시그널 다른 종목 비교 안정적
- **OHLCV 중복 적재 안 함** — ka10081 stock_price_krx/nxt 정답. ka10086 의 OHLCV 8 필드 미적재
- **cron = KST mon-fri 19:00** (ka10081 18:30 + 30분) — C-2β 에서 적용

### Added — DailyMarketDisplayMode StrEnum + ExchangeType 길이 invariant

- `app/application/constants.py` (확장) — `DailyMarketDisplayMode` (QUANTITY="0" / AMOUNT="1") + `EXCHANGE_TYPE_MAX_LENGTH=4` Final + import 시점 fail-fast (2b-M2)

### Added — Migration 007 + ORM (KRX/NXT 분리 영속화)

- `migrations/versions/007_kiwoom_stock_daily_flow.py` (신규) — `stock_daily_flow` 테이블 + UNIQUE(stock_id, trading_date, exchange) + FK CASCADE + 인덱스 3개 (trading_date / stock_id / exchange) + downgrade 가드 (데이터 0 일 때만)
- `app/adapter/out/persistence/models/stock_daily_flow.py` (신규) — `StockDailyFlow` ORM (13 도메인 + 메타 4 + 타임스탬프 3)
- `app/adapter/out/persistence/models/__init__.py` (수정) — export 추가

### Added — `_records.py` (Pydantic + 정규화 + 이중 부호 헬퍼)

- `app/adapter/out/kiwoom/_records.py` (신규):
  - `DailyMarketRow` Pydantic 22 필드 (max_length=32 강제, B-γ-1 2R A-H1)
  - `DailyMarketResponse` wrapper (`stk_cd` 메아리 + `daly_stkpc` list)
  - `NormalizedDailyFlow` slots dataclass (OHLCV 8 무시, 13 도메인 + 메타)
  - `_strip_double_sign_int` 가설 B 헬퍼 (`--714` → -714, `_to_int` BIGINT 가드 위임)

### Added — KiwoomMarketCondClient adapter

- `app/adapter/out/kiwoom/mrkcond.py` (신규) — `KiwoomMarketCondClient.fetch_daily_market`:
  - C-1α 2R H-1 패턴 차용 (페이지 응답 stk_cd 메아리 base code 비교 → cross-stock pollution 차단)
  - flag-then-raise-outside-except (B-β 1R 2b-H2)
  - response message echo 차단 (B-α/B-β M-2 — 비식별 메타만)
  - cont-yn 페이지네이션 자동

### Added — StockDailyFlowRepository (SOR 차단 적용)

- `app/adapter/out/persistence/repositories/stock_daily_flow.py` (신규) — `StockDailyFlowRepository`:
  - `_SUPPORTED_EXCHANGES = {KRX, NXT}` 화이트리스트 (2b-M1 — Phase D 까지 SOR silent merge 차단)
  - `upsert_many` ON CONFLICT (stock_id, trading_date, exchange) DO UPDATE
  - `trading_date == date.min` 빈 응답 자동 skip
  - 명시 update_set 16 항목 (B-γ-1 2R B-H3 패턴)
  - `find_range(stock_id, *, exchange, start, end)` — exchange 필터 + asc 정렬 + start>end / SOR → ValueError

### Added — 1R 회귀 테스트 (이중 리뷰 발견 사항)

- `test_stock_daily_flow_repository.py` 보강:
  - `test_upsert_many_rejects_sor_exchange` (2b-M1)
  - `test_upsert_many_rejects_mixed_with_sor` (2b-M1)
  - `test_find_range_rejects_sor_exchange` (2b-M1)
- `test_daily_market_display_mode.py` 보강 — `test_exchange_type_values_within_varchar4_limit` (2b-M2)

### Added — 신규 테스트 5 파일 / 66 cases

- `tests/test_daily_market_display_mode.py` (7 — 6 신규 + 1 회귀)
- `tests/test_strip_double_sign_int.py` (23 — 가설 B + BIGINT overflow + 혼합/이중 부호)
- `tests/test_migration_007.py` (8 — 테이블/UNIQUE/FK/인덱스/컬럼 타입/server_default/CASCADE/downgrade 멱등)
- `tests/test_stock_daily_flow_repository.py` (13 — 10 신규 + 3 회귀)
- `tests/test_kiwoom_mrkcond_client.py` (15 — 정상/exchange suffix/페이지네이션/business error/검증/indc_mode/빈 응답/정규화/cross-stock pollution)

### Defer (C-2β / 운영 dry-run / Phase F)

- 가설 B 정확성 / R15 단위 / OHLCV cross-check (ka10081 vs ka10086) — 운영 dry-run 후 확정
- NUMERIC(8,4) magnitude 가드 / `idx_daily_flow_exchange` cardinality / KRX/NXT 트랜잭션 deadlock — 후속 chunk
- C-1α 에서 상속된 알려진 이슈 (NUMERIC magnitude / list cap / MappingProxyType / chart.py private import / GET 라우터 익명 공개)

---

## [2026-05-08] feat(kiwoom): Phase C-1β — ka10081 OHLCV 자동화 (UseCase + Router + Scheduler, 이중 리뷰 1R PASS, 694 tests / 93.08%)

**Phase C 두 번째 chunk** — C-1α 인프라 위에 자동화 (IngestDailyOhlcvUseCase + 라우터 3종 + OhlcvDailyScheduler) 추가. 백테스팅 OHLCV 의 자동 적재 파이프라인 완성.

자동 분류: **계약 변경 (contract)** + `--force-2b` 적대적 리뷰 강제. 1R HIGH 0 / MEDIUM 6 (2a 3 + 2b 3) / LOW 6 → 5건 즉시 적용 + 회귀 4 추가 → **2R 진입 없이 PASS** (CRITICAL/HIGH 0).

### Decisions (사용자 승인)

- **nxt_collection_enabled 디폴트 OFF** (settings flag) — 운영 전환 전 안전판. 이중 게이팅 (settings AND stock.nxt_enable)
- **target_date_range = today - 365 ~ today** — admin 호출 base_date 1년 cap, ValueError → 400
- **Cron = KST mon-fri 18:30** — fundamental 18:00 의 30분 후 (master 17:30 → fundamental 18:00 → ohlcv 18:30 직렬화)

### Added — IngestDailyOhlcvUseCase (KRX/NXT 분리 ingest + per-(stock,exchange) 격리)

- `app/application/service/ohlcv_daily_service.py` (신규) — `IngestDailyOhlcvUseCase.execute / refresh_one`, `OhlcvSyncResult / OhlcvSyncOutcome` (frozen slots, response echo 차단)
- per-(stock, exchange) try/except — KRX 실패 → NXT 시도 (계획서 § 4.2 (a) 독립 호출)
- `_validate_base_date` (today ± 365) + `_validate_market_codes` (StockListMarketType 화이트리스트, 2b-M2)
- `refresh_one` — KRX raise propagate, NXT 실패 시 errors 격리 (KRX 이미 적재됨, 2a-M1 / 2b-L3)

### Added — Router (POST sync + POST refresh + GET range)

- `app/adapter/web/routers/ohlcv.py` (신규):
  - `POST /api/kiwoom/ohlcv/daily/sync?alias=` (admin) — 전체 active stock 동기화
  - `POST /api/kiwoom/stocks/{code}/ohlcv/daily/refresh?alias=&base_date=` (admin) — 단건 새로고침
  - `GET /api/kiwoom/stocks/{code}/ohlcv/daily?start=&end=&exchange=` — DB only 시계열 조회
- KiwoomError 매핑 (B-γ-2 패턴 일관): business→400 (message echo 차단) / credential→400 / rate→503 / upstream/validation→502
- ValueError 매핑: "stock master not found" → 404, base_date 범위 → 400
- **GET range cap = 400일** (2b-M1 DoS amplification 차단)

### Added — Scheduler + Batch Job (KST mon-fri 18:30)

- `app/scheduler.py` (확장) — `OhlcvDailyScheduler` + `OHLCV_DAILY_SYNC_JOB_ID` (StockFundamentalScheduler 패턴 일관)
- `app/batch/ohlcv_daily_job.py` (신규) — `fire_ohlcv_daily_sync` callback, 실패율 10% 임계 alert (logger.error / warning / info 분기)

### Added — Settings + Lifespan 통합

- `app/config/settings.py` (수정) — `nxt_collection_enabled` 디폴트 **False** 로 변경 + `scheduler_ohlcv_daily_sync_alias` 추가
- `app/adapter/web/_deps.py` (확장) — `IngestDailyOhlcvUseCaseFactory` + get/set/reset 패턴 (B-γ-2 일관) + `reset_token_manager` 일괄 unset 에 추가
- `app/main.py` (수정) — `_ingest_ohlcv_factory` 등록 + `OhlcvDailyScheduler` start/shutdown + `ohlcv_router` 포함 + fail-fast alias 검증에 `scheduler_ohlcv_daily_sync_alias` 추가

### Added — Repository 확장

- `app/adapter/out/persistence/repositories/stock_price.py` (수정) — `find_range(stock_id, *, exchange, start, end)` 추가. start <= trading_date <= end, asc 정렬, start>end → ValueError, SOR → ValueError

### Added — 1R 회귀 테스트 (이중 리뷰 발견 사항)

- `test_ingest_daily_ohlcv_service.py` 보강:
  - `test_refresh_one_propagates_krx_kiwoom_error` (2a-M2)
  - `test_refresh_one_isolates_nxt_failure_after_krx_success` (2a-M1 / 2b-L3)
  - `test_execute_rejects_unknown_market_code` + `test_execute_accepts_known_market_codes` (2b-M2)
- `test_ohlcv_daily_scheduler.py` 보강 — `fire_ohlcv_daily_sync` 4 cases (정상 / 예외 swallow / 실패율 error / 부분 실패 warning, 2a-M3)
- `test_ohlcv_router.py` 보강 — `test_get_ohlcv_rejects_oversized_range` (2b-M1)

### Added — 신규 테스트 5 파일 / 55 cases

- `tests/test_ingest_daily_ohlcv_service.py` (16 + 5 신규/회귀)
- `tests/test_stock_price_repository_find_range.py` (6)
- `tests/test_ohlcv_router.py` (15 + 1 회귀)
- `tests/test_ohlcv_daily_scheduler.py` (5 + 4 콜백 회귀)
- `tests/test_ohlcv_daily_deps.py` (4)

### Changed — 기존 테스트 회귀 픽스 (4 cases)

- `tests/test_settings.py` — nxt_collection_enabled 디폴트 False 반영
- `tests/test_scheduler.py::test_lifespan_startup_and_shutdown_cycle_with_scheduler_enabled` — `SCHEDULER_OHLCV_DAILY_SYNC_ALIAS` env 추가
- `tests/test_stock_master_scheduler.py::test_lifespan_starts_both_schedulers_with_valid_aliases` — 동일

### Defer (Phase D / 운영 검증)

- GET 라우터 admin guard (현재 DB-only 공개) — internet-facing 배포 시 정책 결정
- date.today() KST 명시 (`datetime.now(KST).date()`) — cron 영향 없음, admin 호출 안전
- find_range adjusted 필터 / OhlcvDailyRowOut.updated_at — 비교 검증 / 캐시 결정 시점

---

## [2026-05-08] feat(kiwoom): Phase C-1α — ka10081 일봉 OHLCV 인프라 (Migration 005/006 + ORM + Repository + Adapter + ExchangeType enum, 이중 리뷰 1R + 2R, 639 tests / 93.44%) — Phase C 진입

**Phase C 진입 첫 chunk** — 백테스팅 OHLCV 코어 인프라. ka10081 (주식일봉차트, P0) 의 Migration + ORM + Repository + Adapter + ExchangeType enum 도입. UseCase + Router + Scheduler 는 C-1β 에서.

자동 분류: **계약 변경 (contract)** + `--force-2b` 적대적 리뷰 강제. 1R HIGH 1 + MEDIUM 3 + LOW 2 → 2R 1 + sonnet M-1/M-2 적용 + 회귀 4 → 2R PASS (CRITICAL/HIGH 0).

### Decisions (사용자 승인)

- **lazy fetch RPS 보호 = (c) batch + fail-closed** (ADR § 13.4.1 deferred 해소) — Phase C 적재 시 미지 종목 logger.warning + skip. C-1β UseCase 에서 적용
- **chunk 분할 — C-1α (인프라) + C-1β (자동화)** (B-γ-1/B-γ-2 패턴 일관)

### Added — ExchangeType enum + build_stk_cd 헬퍼 (Phase C 첫 도입)

- `app/application/constants.py` (확장) — `ExchangeType` StrEnum (KRX/NXT/SOR). B-γ-1 ADR § 14.5 deferred 결정 해소
- `app/adapter/out/kiwoom/stkinfo.py` (확장) — `build_stk_cd(stock_code, exchange)` 헬퍼. `_validate_stk_cd_for_lookup` (B-β 6자리 ASCII) 재사용 + suffix 합성 (KRX → 005930 / NXT → 005930_NX / SOR → 005930_AL)

### Added — Migration 005 + 006 (KRX/NXT 물리 분리)

- `migrations/versions/005_kiwoom_stock_price_krx.py` (신규) — `stock_price_krx` 테이블 + UNIQUE(stock_id, trading_date, adjusted) + FK CASCADE + 2 인덱스
- `migrations/versions/006_kiwoom_stock_price_nxt.py` (신규) — `stock_price_nxt` 테이블 (같은 컬럼 구조, 분리 마이그레이션 — 운영 중 NXT 토글 가능)
- KRX/NXT 가격이 같은 종목·같은 날도 다를 수 있음 (master.md § 3.1 / 계획서 § 4.2)
- `adjusted` boolean PK 일부 — upd_stkpc_tp=1 (수정주가, 백테스팅 디폴트) + =0 (raw 비교 검증) 두 row 동시 보유 가능

### Added — ORM + Repository

- `app/adapter/out/persistence/models/stock_price.py` (신규) — `_DailyOhlcvMixin` (KRX/NXT 공통 컬럼) + `StockPriceKrx` + `StockPriceNxt`
- `app/adapter/out/persistence/models/__init__.py` (수정) — export 추가
- `app/adapter/out/persistence/repositories/stock_price.py` (신규) — `StockPriceRepository`:
  - `_MODEL_BY_EXCHANGE` 분기 (KRX/NXT — SOR 은 ValueError, Phase D 결정)
  - `upsert_many` ON CONFLICT (stock_id, trading_date, adjusted) DO UPDATE
  - `trading_date == date.min` 빈 응답 row 자동 skip
  - 명시 update_set 11 항목 (B-γ-1 2R B-H3 패턴 일관, schema-drift 차단)

### Added — KiwoomChartClient (chart.py)

- `app/adapter/out/kiwoom/chart.py` (신규):
  - `KiwoomChartClient.fetch_daily(stock_code, *, base_date, exchange=KRX, adjusted=True, max_pages=10)` — cont-yn 자동 페이지네이션, build_stk_cd 사전 검증, return_code != 0 → KiwoomBusinessError, flag-then-raise-outside-except (`__context__` 차단)
  - `DailyChartRow` Pydantic — 모든 string 필드 max_length 강제 (B-γ-1 2R A-H1 패턴 / `dt:8`, `pred_pre_sig:1`, 숫자 `:32`, `stk_cd:20`, `return_msg:200`)
  - `DailyChartResponse` (stk_cd 메아리 + stk_dt_pole_chart_qry list)
  - `NormalizedDailyOhlcv` slots dataclass (stock_id + trading_date + exchange + adjusted + 9 OHLCV 필드)
  - `to_normalized` — `_to_int`/`_to_decimal`/`_parse_yyyymmdd` 재사용 (B-γ-1 BIGINT/NaN/Infinity 가드 자동 적용)
- **2R H-1 — 페이지네이션 cross-stock pollution 차단**: `strip_kiwoom_suffix` 기반 base code 비교. page N 응답 stk_cd base ≠ 요청 base → KiwoomResponseValidationError. base 비교 정책 — suffix stripped/동봉 양쪽 수용 (계획서 § 4.3 운영 미검증)

### Added — 신규 테스트 4 파일 / 50 cases

- `tests/test_exchange_type.py` (7) — ExchangeType StrEnum + build_stk_cd 합성/거부
- `tests/test_kiwoom_chart_client.py` (20) — fetch_daily + KRX/NXT/SOR + 페이지네이션 + 정규화 + 2R 회귀 4 (cross-stock pollution / 빈 stk_cd / NXT base 매칭 stripped/full suffix)
- `tests/test_stock_price_repository.py` (8) — KRX/NXT 분기 + upsert_many + 멱등 + raw vs adjusted + date.min skip + 다중 stock
- `tests/test_migration_005_006.py` (15 — parametrize) — 두 마이그레이션 통합 검증

### Documentation

- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 16 신규 — C-1α 결정 + 1R/2R 매핑 + Defer 6 + C-1β 진입 결정 사항
- 학습 패턴: H-1 페이지네이션 cross-stock pollution (base code 비교 정책)

### Quality Gates

- 테스트 **639 passed / coverage 93.44%** (이전 589 + 신규 50 / 회귀 0)
- mypy --strict ✅ / ruff ✅ / FastAPI app create + ExchangeType + build_stk_cd 검증
- 2R PASS — 1R HIGH 1 + sonnet MEDIUM 2 모두 적용, 신규 회귀 0, 학습 위협 회귀 0

### 다음

**Phase C-1β** — IngestDailyOhlcvUseCase + 라우터 (sync/refresh/조회) + OhlcvDailyScheduler (KST mon-fri 18:30) + lazy fetch (c) batch fail-closed 적용. 후속: C-2 (ka10086 일별 보강), C-3 (ka10082/83 주봉/월봉).

---

## [2026-05-08] feat(kiwoom): Phase B-γ-2 — ka10001 펀더멘털 자동화 (UseCase + Router + Scheduler + Lifespan, 이중 리뷰 1R + 2R, 589 tests / 93.24%) — Phase B 마무리

Phase B-γ-1 인프라 위에 비즈니스 로직 + 운영 자동화 layer 추가. **Phase B 마무리** — 이후 Phase C (OHLCV 백테스팅) 진입 가능.

자동 분류: **계약 변경 (contract)** + `--force-2b` 적대적 리뷰 강제. 1R HIGH 1 + MEDIUM 4 + LOW 3 → 2R 5 적용 + 회귀 5 → 2R PASS (CRITICAL/HIGH 0). + ruff E402 후속 정정.

### Decisions (사용자 승인)

- **Partial-failure 정책 = (a) per-stock skip + counter** — 한 종목 KiwoomError 발생 시 try/except 후 success/failed counter 누적, 다음 종목 진행 (B-α 패턴 일관). ADR § 14.6 deferred 결정 / 2R C-M3 해소
- **`ensure_exists` 미사용** — active stock 만 대상. 신규 상장 종목은 다음날 ka10099 sync 에서 자동 등장 (KISS + RPS 보존)

### Added — UseCase + Result dataclass

- `app/application/service/stock_fundamental_service.py` (신규) — `SyncStockFundamentalUseCase`:
  - `execute(target_date=None, only_market_codes=None)` — active stock 순회 + per-stock try/except + KiwoomError catch + Exception fallback. 응답 본문 echo 차단 (B-α/B-β M-2 패턴 일관)
  - `refresh_one(stock_code)` — Stock 마스터 active 검증 → 없으면 ValueError → 라우터 404. KiwoomError 그대로 전파
  - `_sync_one_stock` 헬퍼 — 키움 호출 (트랜잭션 외) → normalize → mismatch alert → upsert with `expected_stock_code` cross-check (B-γ-1 invariant 활용)
- `FundamentalSyncResult` (asof_date, total, success, failed, errors[]) + `FundamentalSyncOutcome` (stock_code, error_class)
- **2R M-1 — `_safe_for_log()` helper**: vendor 응답 stk_nm 의 control char (`\r\n\t\x00\x1b`) strip + 길이 cap. mismatch alert sink injection 차단 (Sentry/CloudWatch line 분리/색상 spoof 방어)

### Added — Router

- `app/adapter/web/routers/fundamentals.py` (신규):
  - `POST /api/kiwoom/fundamentals/sync?alias=` (admin) + `FundamentalSyncRequestIn` (target_date, only_market_codes 옵션)
  - `POST /api/kiwoom/stocks/{stock_code}/fundamental/refresh?alias=` (admin) — KiwoomBusinessError → 400 + detail{return_code, error="KiwoomBusinessError"} (message echo 차단)
  - `GET /api/kiwoom/stocks/{stock_code}/fundamental/latest?exchange=KRX|NXT|SOR` — DB only
  - `StockFundamentalOut` (45 필드 from_attributes), `FundamentalSyncResultOut`, `FundamentalSyncOutcomeOut`
  - 예외 매핑: business→400 / credential→400 / rate→503 / upstream/validation→502 / KiwoomError fallback→502 (B-β M-5 패턴) / ValueError→404

### Added — Scheduler + Batch

- `app/scheduler.py` (확장) — `StockFundamentalScheduler` 클래스 (KST mon-fri 18:00 cron, ka10099 17:30 의 30분 후) + `STOCK_FUNDAMENTAL_SYNC_JOB_ID = "stock_fundamental_sync_daily"`
- `app/batch/stock_fundamental_job.py` (신규) — `fire_stock_fundamental_sync` callback:
  - `failure_ratio > 0.10` 시 logger.error + sample_failed 10건 cap (작업계획서 § 11.1 #7 임계)
  - partial 실패 시 logger.warning / 모든 정상 시 logger.info
  - 모든 예외 swallow (다음 cron tick 정상 동작 보장)

### Added — DI / Lifespan

- `app/adapter/web/_deps.py` (확장) — `SyncStockFundamentalUseCaseFactory` 타입 + `_sync_fundamental_factory` 싱글톤 + get/set/reset 3 함수 + `reset_token_manager` 일괄 unset 추가
- `app/main.py` (확장) — lifespan `_sync_fundamental_factory` (sync_stock factory 패턴 일관, KRX-only 라 mock_env 무관) + `StockFundamentalScheduler.start/shutdown` + `fundamentals_router` 등록 + teardown 순서 fundamental → stock → sector → reset_*_factory 4개 → revoke → engine.dispose
- `app/config/settings.py` (확장) — `scheduler_fundamental_sync_alias` Field

### Fixed — 2R H-1: lifespan fail-fast cleanup 우회 차단

- `app/main.py` — alias 미설정 검증을 `set_token_manager` / `set_revoke_use_case` / `set_*_factory` 6개 호출 **앞으로** 이동. 새 message 형식 (list — 모든 missing alias 표시). 기존 set 후 검증 (line 246-253 구) 제거. cleanup (reset_*_factory + revoke + engine.dispose) 우회 차단

### Added — 신규 테스트 4 파일 / 39 cases

- `tests/test_stock_fundamental_service.py` (16 cases) — UseCase + per-stock skip + mismatch + only_market_codes + target_date + refresh_one + 2R 회귀 3 (control char strip + _safe_for_log 단위 + 길이 cap)
- `tests/test_fundamental_router.py` (14 cases) — `_make_app` + `dependency_overrides` 패턴 (lifespan 진입 안 함, B-α `test_stock_router` 일관) + KiwoomError 6종 매핑
- `tests/test_stock_fundamental_scheduler.py` (5 cases) — KST 18:00 cron + 멱등성
- `tests/test_stock_fundamental_deps.py` (4 cases) — factory get/set/reset

### Changed — 기존 테스트 갱신

- `tests/test_scheduler.py` + `tests/test_stock_master_scheduler.py` — `SCHEDULER_FUNDAMENTAL_SYNC_ALIAS` env 추가, fail-fast match pattern 갱신 (substring 형식)

### Documentation

- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 15 신규 — B-γ-2 결정 + 1R/2R 이슈 매핑 + Phase B 회고 (CRITICAL 6 + HIGH 25 누적 적용) + Defer 8 + Phase C 진입 결정 사항
- B-γ-2 패턴 학습 — `_safe_for_log` log injection 방어, lifespan fail-fast cleanup 우회 차단

### Quality Gates

- 테스트 **589 passed / coverage 93.24%** (이전 550 + B-γ-1 36 + B-γ-2 39 / 회귀 0)
- mypy --strict ✅ / ruff ✅ / FastAPI app create + `/api/kiwoom/fundamentals/sync` 라우트 등록 검증
- 2R PASS — 1R HIGH 1 + MEDIUM 1 + LOW 1 + 1R sonnet M-1 모두 적용 검증, 신규 회귀 LOW 2 (charset 부분 커버 / cosmetic) defer

### 다음

**Phase C 진입** — OHLCV 시계열 + 백테스팅 본체. 진입 전 결정 필수: lazy fetch RPS 보호 옵션 (a/b/c — ADR § 13.4.1) + 운영 dry-run 통합 (DoD § 10.3).

---

## [2026-05-08] feat(kiwoom): Phase B-γ-1 — ka10001 펀더멘털 인프라 (Migration 004 + ORM + Repository + Adapter, 이중 리뷰 1R + 2R, 550 tests / 94.28%)

Phase B-γ 1,164줄 작업계획서를 **B-γ-1 (인프라) + B-γ-2 (UseCase/Router/Scheduler)** 두 chunk 로 분할 (사용자 승인). 본 chunk 는 인프라만 — 백테스팅 진입점에 펀더멘털 (PER/EPS/ROE/PBR/EV/BPS + 시총/외인/250일통계/일중시세 45 필드) 일별 스냅샷 적재 인프라.

자동 분류: **계약 변경 (contract)** — Migration 신규 + Pydantic Response 45 필드. `--force-2b` 적대적 리뷰 강제 실행. 1R CRITICAL 2 + HIGH 4 + MEDIUM 5 + LOW 5 → 2R 12개 적용 + 회귀 테스트 16 → 2R PASS (CRITICAL/HIGH 0).

거래소 정책: **(a) KRX only** (계획서 § 4.3 권장) — NXT/SOR 추가는 Phase C 후. 일 1회 cron 시간: **18:00 KST** (ka10099 stock master 직후, B-γ-2 에서 코드화).

### Added — Migration 004 + ORM

- `migrations/versions/004_kiwoom_stock_fundamental.py` (신규) — `kiwoom.stock_fundamental` 테이블 + UNIQUE(stock_id, asof_date, exchange) + FK ON DELETE CASCADE + 2 인덱스 (`asof_date`, `stock_id`). 5 카테고리 컬럼 (A 기본 / B 자본·시총·외인 / C 재무비율 / D 250일통계 / E 일중시세) + `fundamental_hash` CHAR(32) + 타임스탬프
- `app/adapter/out/persistence/models/stock_fundamental.py` (신규) — `StockFundamental` ORM (45 매핑 + CHAR(2)/CHAR(1)/CHAR(32) 타입 sync, 2R L-2)

### Added — Repository

- `app/adapter/out/persistence/repositories/stock_fundamental.py` (신규) — `StockFundamentalRepository`:
  - `upsert_one(row, *, stock_id, expected_stock_code=None)` — ON CONFLICT (stock_id, asof_date, exchange) DO UPDATE RETURNING + populate_existing. **2R B-H2** caller 가 `expected_stock_code` 명시 시 row 와 cross-check (orphaned/cross-link row 차단). **2R B-H3** 명시 update_set 46 항목 (Stock repository 패턴 일관, schema-drift 차단)
  - `find_latest(stock_id, *, exchange="KRX")` — 가장 최근 asof_date row
  - `find_by_stock_and_date(...)` — backfill 멱등성 검증용
  - `compute_fundamental_hash(row)` — PER/EPS/ROE/PBR/EV/BPS 6 필드 MD5. `Decimal.normalize() + format("f")` (지수 표기 위험 방지, 2R M-1)

### Added — Adapter (KiwoomStkInfoClient.fetch_basic_info)

- `app/adapter/out/kiwoom/stkinfo.py` (확장) — ka10001 섹션 신규:
  - `_to_int(value)` — zero-padded · 부호 · 콤마 → int | None. **2R A-C1** BIGINT 경계 가드 (`_BIGINT_MIN`/`_BIGINT_MAX`) — DataError 트랜잭션 abort 차단
  - `_to_decimal(value)` — string → Decimal | None. **2R A-C2/A-H4** `is_finite()` 가드 (NaN/Infinity/sNaN 거부). **2R M-2** `replace(",", "")` 추가 (`_to_int` 비대칭 해소)
  - `strip_kiwoom_suffix(stk_cd)` — `"005930_NX" → "005930"` (응답 메아리 방어)
  - `StockBasicInfoRequest` — Pydantic Request (`STK_CD_LOOKUP_PATTERN` 재사용, ka10100 패턴 일관)
  - `StockBasicInfoResponse` — 45 필드 + `250hgst` alias + `extra="ignore"`. **2R A-H1** 모든 string 필드 `Field(max_length=N)` 강제 (DB CHAR/VARCHAR sync, vendor 거대 string DataError 차단)
  - `NormalizedFundamental` (slots dataclass) — 45 필드 + `exchange="KRX"` 고정
  - `normalize_basic_info(response, *, asof_date, exchange="KRX")` — **2R C-M4** kwarg BC 보존 (Phase C NXT 진입 시 시그니처 변경 0)
  - `KiwoomStkInfoClient.fetch_basic_info(stock_code)` — `_validate_stk_cd_for_lookup` 재사용 (ka10100 패턴) + flag-then-raise-outside-except (B-β 1R 2b-H2 회귀 방어). **2R A-L1** `stk_cd[:50]!r` 메시지 cap

### Added — 신규 테스트 3 파일 / 52 cases

- `tests/test_migration_004.py` (8 cases) — 스키마 / UNIQUE 복합키 / FK CASCADE / 5 카테고리 컬럼 타입 / server_default / downgrade 멱등성
- `tests/test_kiwoom_stkinfo_basic_info.py` (33 cases) — 어댑터 + Pydantic + 정규화 + 2R 회귀 14 (BIGINT overflow / NaN / Infinity / sNaN / 쉼표 / Pydantic max_length 4 / repr cap / exchange kwarg)
- `tests/test_stock_fundamental_repository.py` (14 cases) — upsert_one + find_latest + fundamental_hash + 2R 회귀 3 (B-H2 mismatch / matching / legacy)

### Changed — 기존 파일 갱신

- `app/adapter/out/persistence/models/__init__.py` — StockFundamental export 추가
- `app/adapter/out/kiwoom/stkinfo.py` — 모듈 docstring 갱신 (ka10001 (B-γ-1 KRX-only) 추가, 2R L-1)

### Documentation

- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 14 신규 — B-γ-1 결정 + 2R 이슈 매핑 12 + Defer 5 (B-M1 vendor metric / C-M3 partial-failure / 단위 검증 / `_parse_yyyymmdd` 알림 / `replace(",")` 의도)
- B-γ-2 진입 전 결정 사항 명시 (partial-failure / stock_id resolution invariant / mismatch alert / lookup 의존)

### Quality Gates

- 테스트 **550 passed / coverage 94.28%** (이전 498 + 36 Step 1 + 16 2R 회귀 / 회귀 0)
- mypy --strict ✅ / ruff ✅ / Alembic upgrade head testcontainers ✅ / FastAPI app create ✅
- 2R PASS — 1R CRITICAL/HIGH 12개 모두 적용 검증 + 신규 회귀 위협 0건

### 다음 chunk

**Phase B-γ-2** — `SyncStockFundamentalUseCase` + 라우터 (sync 전체 / refresh 단건) + `StockFundamentalScheduler` (KST 18:00 평일).

---

## [2026-05-08] feat(kiwoom): Phase B-β — ka10100 단건 종목 조회 (gap-filler / lazy fetch, 이중 리뷰 1R, 498 tests / 93.73%) — `abce7e0`

Phase B 의 두 번째 chunk — ka10099 (bulk sync) 의 gap-filler. ka10100 (단건 종목 조회) endpoint 의 어댑터·Repository.upsert_one·LookupStockUseCase·라우터·lifespan 통합. Phase C OHLCV 적재가 stock 마스터 미스 시 호출할 lazy fetch 진입점 (`ensure_exists`) 마련.

자동 분류: **계약 변경 (contract)** — admin endpoint 신설로 `--force-2b` 적대적 리뷰 강제 실행. 1R HIGH 4 + MEDIUM 9 + LOW 6 → HIGH 4 + MEDIUM 4 적용 후 2R PASS (CRITICAL/HIGH 0).

### Added — ka10100 어댑터 (단건 조회)

- `app/adapter/out/kiwoom/stkinfo.py` (확장) — `STK_CD_LOOKUP_PATTERN` 정규식 단일 source (`r"^[0-9]{6}$"`, ASCII only) + `_validate_stk_cd_for_lookup` + `StockLookupResponse` (14 필드 + return_code/msg + `to_normalized()`) + `StockLookupRequest` (Pydantic 검증) + `KiwoomStkInfoClient.lookup_stock` (단건 호출, ValidationError flag-then-raise-outside-except 패턴)

### Added — Repository / UseCase

- `app/adapter/out/persistence/repositories/stock.py` (확장) — `upsert_one(row: NormalizedStock) -> Stock` (RETURNING + populate_existing 으로 session identity map stale 방어)
- `app/application/service/stock_master_service.py` (확장) — `LookupStockUseCase`:
  - `execute(stock_code)` — 키움 호출 + DB upsert + 갱신된 Stock 반환. 정규화 실패 ValueError → KiwoomResponseValidationError 매핑 (1R 2b-H2)
  - `ensure_exists(stock_code)` — DB hit (active) 캐시 / DB miss/inactive 키움 재호출 (Phase C lazy fetch 진입점)

### Added — 라우터 + DI

- `app/adapter/web/routers/stocks.py` (확장) — `GET /api/kiwoom/stocks/{stock_code}` (DB only, 404 if missing) + `POST /api/kiwoom/stocks/{stock_code}/refresh?alias=` (admin, ka10100 호출 + upsert) + KiwoomError 6 종 매핑
- `app/adapter/web/_deps.py` (확장) — `LookupStockUseCaseFactory` 싱글톤 + `get_/set_/reset_lookup_stock_factory` + `reset_token_manager` 확장

### Added — Lifespan 통합

- `app/main.py` (확장) — lifespan 에 `_lookup_stock_factory` (sync_stock factory 와 동일 패턴, mock_env 일관) + teardown finally 에 `reset_*_factory` 3개 호출 (1R 2b-M4: close 후 stale factory 노출 차단)

### Changed — 1R 적대적 이중 리뷰 적용

- **2a-H1**: `_STK_CD_PATTERN = (6, 6)` 미사용 상수 → 정규식 단일 source `STK_CD_LOOKUP_PATTERN` (어댑터 validator + Pydantic Request + 라우터 Path 세 곳 모두 참조)
- **2a-H2**: `ensure_exists` TOCTOU docstring 명시 (race 시 두 코루틴 모두 execute 진입, ON CONFLICT 흡수, 키움 호출 중복 가능, Phase C 결정)
- **2b-H1**: `KiwoomBusinessError.message` (= 키움 `return_msg`) admin 응답 echo 차단 — B-α M-2 정책 백포트. detail 에 `return_code` + `error="KiwoomBusinessError"` 만, 본문은 logger 경로로만
- **2b-H2**: raw `ValueError` (정규화 실패) → `KiwoomResponseValidationError` 매핑 (flag-then-raise-outside-except 패턴, B-α `fetch_stock_list` 일관, `__cause__/__context__` None)
- **2a-M2**: `ensure_exists` 의 `is_active=False` row 자동 재조회 + 활성 복원
- **2b-M2**: `ensure_exists` 진입 시 `_validate_stk_cd_for_lookup` 호출 (DB hit 분기 stk_cd 검증 우회 차단)
- **2b-M5**: `KiwoomError` fallback 에 `logger.warning("ka10100 fallback %s", type(exc).__name__)` (운영 가시성, 메시지 echo 안 함)

### Tests +55 (443 → 498)

- `test_kiwoom_stkinfo_lookup.py` (17) — 어댑터 단건 + nxtEnable Y/N/빈값 정규화 + ValueError 우회 차단 + Pydantic 응답 검증 + zero-padded 정규화 + extra 필드 무시 + mock_env
- `test_lookup_stock_service.py` (14) — UseCase 통합 (testcontainers) — INSERT/UPDATE/재활성화 + ensure_exists hit/miss + race + business error + 1R 회귀 가드 (정규화 매핑 / 비활성 재조회 / stk_cd 사전 검증)
- `test_stock_lookup_router.py` (18) — 라우터 단건 + admin guard + KiwoomError 6 매핑 + alias 분기 + Path validation + 1R 회귀 가드 (return_msg echo 차단 / 502 매핑)
- `test_stock_repository_upsert_one.py` (5) — INSERT id 채움 / UPDATE 같은 id / 활성 복원 / idempotent / 14 필드 영속화
- `test_lookup_stock_deps.py` (5) — DI factory get/set/reset/independence

### Documentation

- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` — § 13 추가 (7 결정, 1R 4HIGH 적용 매핑, Phase C deferred 항목)

### 누적

- **498 tests passed / coverage 93.73%** (B-β 신규 모듈 86-100%)
- 적대적 이중 리뷰 누적 발견: CRITICAL 4 + HIGH 20 — 전부 적용 → PASS
- ADR-0001 § 3·6·7·8·9·10·11·12·13 결정 기록 완료

---

## [2026-05-08] feat(kiwoom): Phase B-α — ka10099 종목 마스터 + StockMasterScheduler (이중 리뷰 1R, 443 tests / 93.38%) — `bf9956a`

Phase B 의 첫 chunk — 백테스팅 진입점인 종목 마스터 적재 인프라 완성. ka10099 (종목정보 리스트) endpoint 의 어댑터·도메인·라우터·일간 cron 통합. sector 도메인 (ka10101) 패턴을 차용하면서 stock 특이사항 (zero-padded 정규화, nxt_enable, 14필드 응답, mock 환경 안전판, UNIQUE(stock_code) 단일키) 반영.

자동 분류: **계약 변경 (contract)** — admin/cron 영향으로 `--force-2b` 적대적 리뷰 강제 실행. 1R HIGH 2 + MEDIUM 5 + LOW 5 → 전부 수정. 2R PASS (CRITICAL/HIGH 0).

### Added — Stock 도메인

- `app/application/constants.py` (신규) — `StockListMarketType` StrEnum 16종 + `STOCK_SYNC_DEFAULT_MARKETS` (KOSPI 0 / KOSDAQ 10 / KONEX 50 / ETN 60 / REIT 6)
- `app/adapter/out/kiwoom/stkinfo.py` (확장) — `fetch_stock_list` (페이지네이션 max_pages=100) + `StockListRow` (14 필드) + `NormalizedStock` dataclass + `StockListResponse` (alias `list`→`items`) + `StockListRequest` (Pydantic 검증) + `_parse_yyyymmdd` + `_parse_zero_padded_int`
- `app/adapter/out/persistence/models/stock.py` (신규) — `Stock` ORM (UNIQUE stock_code 단일키)
- `app/adapter/out/persistence/repositories/stock.py` (신규) — `StockRepository` (list_by_filters / list_nxt_enabled / find_by_code / upsert_many / deactivate_missing)
- `app/application/service/stock_master_service.py` (신규) — `SyncStockMasterUseCase` (5 시장 격리 + 빈 응답 deactivate skip + mock_env 안전판) + `MarketStockOutcome` + `StockMasterSyncResult`
- `app/adapter/web/routers/stocks.py` (신규) — GET `/api/kiwoom/stocks` (필터: market_code/nxt_enable/only_active) + GET `/stocks/nxt-eligible` (Phase C 큐 source) + POST `/stocks/sync?alias=` (admin) + F3 max_pages hint 헤더

### Added — Scheduler / 배치

- `app/batch/stock_master_job.py` (신규) — `fire_stock_master_sync` (예외 swallow + 부분 실패 warning + nxt_enabled 로그)
- `app/scheduler.py` (확장) — `StockMasterScheduler` (AsyncIOScheduler + CronTrigger KST mon-fri 17:30, sector scheduler 와 lifecycle 분리)
- `app/main.py` (확장) — lifespan 에 stock factory + StockMasterScheduler 통합 (sector 와 동일 graceful shutdown 순서: stock_scheduler → sector_scheduler → revoke → dispose)

### Added — Settings / 의존성

- `Settings.scheduler_stock_sync_alias: str` — 일간 stock cron 자격증명 alias (fail-fast 가드 추가)
- `app/adapter/web/_deps.py` (확장) — `SyncStockMasterUseCaseFactory` 싱글톤 + `set_/get_/reset_sync_stock_factory`

### Added — Migration / DB

- `migrations/versions/003_kiwoom_stock.py` (신규) — `kiwoom.stock` 테이블 (18 컬럼) + 4 인덱스 (market_code / nxt_enable partial / is_active partial / up_name partial) + 양방향 idempotent

### Changed — sector 도메인 백포트 (1R M-2)

- `app/application/service/sector_service.py` — `outcome.error` 클래스명 only (응답 본문 echo 차단). 메시지는 logger 경로로만 노출.

### Changed — 1R 적용

- **H1**: `to_normalized.market_code = requested_market_code` 항상 사용 (응답 marketCode 영속화 안 함) — cross-market zombie row 방지 + sector 패턴 일관 + deactivate_missing 격리 보장
- **H-1**: mock_env 가 lifespan 1회 결정 (프로세스당 단일 env 운영 가정) — ADR 주석 명시
- **M-1**: state VARCHAR(120) → VARCHAR(255) — 키움 다중값 (`"증거금20%|담보대출|..."`) 안전 마진
- **L1**: `StockListRequest` Pydantic 모델 — wire 직전 검증 (sector 패턴 일관)
- **L2**: `SectorSyncScheduler` docstring — B-α 후 코멘트 갱신

### Tests +99 (444 → 443)

- `test_kiwoom_stkinfo_stock_list.py` (36) — 어댑터 파싱·페이지네이션·정규화·mock_env·Pydantic 단위
- `test_stock_repository.py` (17) — CRUD·디액티베이션·시장 격리·NXT 큐·중복 stock_code overwrite
- `test_stock_master_service.py` (14) — 시장 단위 격리·멱등성·폐지/재등장·mock_env·빈 응답·비숫자 ValidationError
- `test_stock_router.py` (12) — admin guard·F3 hint·DTO·예외 매핑·alias query
- `test_stock_router_integration.py` (1) — 라우터 → 실 UseCase → MockTransport → DB 풀 체인 회귀
- `test_migration_003.py` (7) — UNIQUE/4 인덱스/partial WHERE/타입/server_default/멱등성
- `test_stock_master_scheduler.py` (11) — fire 콜백 + 등록·idempotent·shutdown + lifespan fail-fast
- (기존 `test_kiwoom_stkinfo_stock_list.py` 의 2개 case 1개 함수로 합쳐 -1)

### Documentation

- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` — § 12 추가 (10 결정, 1R 조치 매핑, dry-run 항목)
- `docs/research/kiwoom-rest-feasibility.md` — § 10.5 진행 상태 표 + § 10.6 다음 작업 갱신

### 누적

- **443 tests passed / coverage 93.38%** (B-α 신규 모듈 95-100%)
- 적대적 이중 리뷰 누적 발견: CRITICAL 4 + HIGH 16 — 전부 적용 → PASS
- ADR-0001 § 3·6·7·8·9·10·11·12 결정 기록 완료

---

## [2026-05-08] feat(kiwoom): Phase A3-γ — APScheduler weekly cron + lifespan 통합 (단일 리뷰, 345 tests / 93%)

ka10101 sector sync 의 자동 트리거 — 일요일 KST 03:00 cron 1개 등록. AsyncIOScheduler 를 lifespan 에 통합하되 graceful shutdown 순서를 명확히 정의: scheduler 먼저 정지 → token revoke → engine.dispose. 운영 실수 방어를 위한 fail-fast 가드 (`scheduler_enabled=True + alias=""` → startup RuntimeError).

자동 분류: **일반 기능 (general)** — 보안 표면 변경 없음. 이중 리뷰 2b 자동 생략. 1차 리뷰 PASS.

### Added — Scheduler 모듈

- `app/scheduler.py` — `SectorSyncScheduler` (AsyncIOScheduler + CronTrigger 일 03:00 KST + `max_instances=1` + `coalesce=True` + `replace_existing=True`)
  - `start()` 멱등성 — `_started` 플래그 가드 + scheduler_enabled=False 시 no-op
  - `shutdown(wait=True)` — 진행 중 cron 완료 대기, 미기동 상태에서도 안전
  - `is_running = _started AND scheduler.running` — AsyncIOScheduler.shutdown(wait=False) 의 비동기 cleanup race 회피
- `app/batch/sector_sync_job.py` — `fire_sector_sync` 콜백
  - 모든 예외 swallow (logger.exception) — 다음 cron tick 보장
  - 정상 완료: logger.info / 부분 실패: logger.warning (운영 oncall hint)

### Added — Lifespan 통합

- `app/main.py` — lifespan 확장:
  - startup: SectorSyncScheduler 생성 + start (settings.scheduler_enabled=True 일 때만 실제 등록)
  - shutdown 순서: `scheduler.shutdown(wait=True)` → graceful token revoke → `engine.dispose`
  - **fail-fast 가드**: `scheduler_enabled=True + scheduler_sector_sync_alias=""` → RuntimeError (운영 실수 방어)

### Added — Settings

- `Settings.scheduler_sector_sync_alias: str = ""` — 주간 cron 이 사용할 자격증명 alias

### Added — 의존성 / mypy

- `pyproject.toml` — `[[tool.mypy.overrides]]` 추가: `apscheduler.*` ignore_missing_imports (3.x stubs 미제공)

### Tests +13

- `tests/test_scheduler.py` (신규):
  - fire_sector_sync 정상 / 예외 swallow / 부분 실패 (3 — monkeypatch 로 logger mock, caplog 회피)
  - SectorSyncScheduler disabled / enabled+cron 등록 / idempotent / shutdown / 미기동 shutdown / disabled+shutdown (6)
  - 수동 job 호출 (1)
  - lifespan fail-fast 가드 + startup·shutdown 사이클 enabled/disabled (3 — 3-5 런타임 smoke)

### 검증

- 345 passed (이전 332, +13) / coverage **93%** (+1%)
- 핵심 파일: scheduler.py 96% / sector_sync_job.py 100% / main.py 75%
- ruff check 0 / format 0 / mypy strict 0 (41 source files) / bandit 0
- 5관문 모두 통과 — 3-5 런타임 smoke (lifespan startup→shutdown 사이클 enabled/disabled 양방향)

### 문서

- ADR-0001 § 11 추가 (12 결정 + 결과 + 운영 dry-run 보류 + 다음 chunk)

### 다음 chunk

운영 dry-run (DoD § 10.3) — α + β + A3-α + F1 + A3-β + A3-γ 통합 검증. 그 다음 Phase B (ka10099/ka10100/ka10001).

---

## [2026-05-08] feat(kiwoom): Phase A3-β — sector 도메인 영속화 + UseCase + 라우터 (이중 리뷰 1R, 332 tests / 91%)

ka10101 의 도메인 풀 체인 단일 PR. `KiwoomStkInfoClient.fetch_sectors` (A3-α 완료) → `SyncSectorMasterUseCase` (시장 단위 격리) → `SectorRepository` (PG ON CONFLICT upsert + 디액티베이션 정책 B) → DB. 라우터 `GET/POST /api/kiwoom/sectors` 까지 포함. APScheduler weekly 는 A3-γ 로 분리.

이중 리뷰 1R — **CRITICAL 0 / HIGH 0 / MEDIUM 3 PASS** (모두 정합성 OK, 추가 적용 없음).

### Added — Migration

- `migrations/versions/002_kiwoom_sector.py` — `kiwoom.sector` 테이블 (id/market_code/sector_code/sector_name/group_no/is_active/fetched_at/created_at/updated_at)
  - `UNIQUE(market_code, sector_code)` — upsert 키
  - `CHECK(market_code IN ('0','1','2','4','7'))` — 무효값 차단
  - `idx_sector_market` + `idx_sector_active` (partial WHERE is_active=TRUE)
  - downgrade 안전가드 — sector 데이터 있으면 차단

### Added — ORM / Repository

- `app/adapter/out/persistence/models/sector.py` — Sector ORM (BigInteger id, String(2/10/100/10), Boolean, TZ-aware DateTime, TimestampMixin)
- `app/adapter/out/persistence/repositories/sector.py` — SectorRepository:
  - `list_by_market(market_code, only_active)` — populate_existing=True 로 stale 객체 회피
  - `list_all(only_active)` — 5 시장 통합 + (market_code, sector_code) 정렬
  - `upsert_many(rows)` — PG ON CONFLICT (market_code, sector_code) → set sector_name / group_no / is_active=TRUE / fetched_at / updated_at
  - `deactivate_missing(market_code, present_codes)` — 시장 단위 격리 (다른 시장 row 영향 없음). 빈 set 시 그 시장 전체 비활성화 (안전장치)

### Added — UseCase / DTO

- `app/application/service/sector_service.py`:
  - `SyncSectorMasterUseCase` — 5 시장 순회 + 시장 단위 트랜잭션 (`session_provider` 패턴, TokenManager 와 일관)
  - `MarketSyncOutcome` (frozen + slots) — `succeeded` property
  - `SectorSyncResult` (frozen + slots) — `all_succeeded` property
  - `MarketCode = Literal["0","1","2","4","7"]` + `SUPPORTED_MARKETS: tuple[MarketCode, ...]` mypy strict 정합

### Added — 라우터 / DTO

- `app/adapter/web/routers/sectors.py`:
  - GET `/api/kiwoom/sectors?market_code=&only_active=` — DB read only (admin 불필요), Literal 422 차단
  - POST `/api/kiwoom/sectors/sync?alias=` — admin only, KiwoomClient sync 마다 close 보장
  - F3 통합 — outcome.error 에 "MaxPages" 흔적 시 응답 헤더 `Retry-After: 60` (모니터링 hint)
  - SectorOut / MarketSyncOutcomeOut / SectorSyncResultOut Pydantic (from_attributes=True)
- `app/adapter/web/_deps.py` 확장 — `SyncSectorUseCaseFactory` (alias → AsyncContextManager[UseCase]) + getter/setter
- `app/main.py` 확장 — sector router include + lifespan 의 sync_sector_factory 등록 (KiwoomClient 빌드 + close 보장)

### Tests +47 — 5 신규 파일 + test_models.py 확장

- `tests/test_migration_002.py` (6 케이스) — 테이블 / UNIQUE / CHECK / 인덱스 / 컬럼 타입 / downgrade-upgrade 멱등성
- `tests/test_models.py` (+5 케이스) — Sector ORM CRUD / UNIQUE / CHECK / 시장별 동일 sector_code 허용 / group_no nullable
- `tests/test_sector_repository.py` (13 케이스) — upsert / list / deactivate_missing 시장 격리 / 멱등성 / 재등장 복원
- `tests/test_sector_service.py` (11 케이스) — 5 시장 정상 / Upstream 격리 / Credential 격리 / Business 격리 / 모두 실패 / 멱등성 / 폐지 / 재등장 / 시장명 변경 / DTO property
- `tests/test_sector_router.py` (11 케이스) — admin guard 3 / 부분 성공 / F3 hint 헤더 / 4xx 매핑
- `tests/test_sector_router_integration.py` (1 케이스) — 라우터 → 실 UseCase factory → MockTransport → testcontainers DB 풀 체인

### 검증

- 332 passed (이전 285, +47) / coverage **91%** (이전 91% — 신규 코드 91% 유지)
- 핵심 파일: sector_service 94% / sector_router 95% / sector_repository 100% / sector_model 100%
- ruff check 0 / format 0 / mypy strict 0 (38 source files) / bandit 0

### 문서

- ADR-0001 § 10 추가 (16 결정 + 결과 + 운영 dry-run 보류 + 후속 PR)

### 다음 chunk

A3-γ — APScheduler weekly cron (KST 일 03:00) + scheduler 모듈 + lifespan 통합 (β graceful shutdown 충돌 검증).

---

## [2026-05-07] security(kiwoom): F1 — auth.py `__context__` leak 백포트 (이중 리뷰 1R, 285 tests / 91.0%)

`backend_kiwoom` A3-α C-1 발견 (`__context__` leak via `from None`) 의 동일 패턴을 **`KiwoomAuthClient`** (au10001 / au10002) 에 백포트. 9개 raise site (`_do_issue_token` 4 + `expires_at_kst` 1 + `revoke_token` 4) 를 변수 캡처 + except 밖 raise 패턴으로 리팩토링. 보안 일관성 — backend_kiwoom 의 모든 외부 호출 어댑터 (`auth.py`, `_client.py`, `stkinfo.py`) 가 단일 예외 chain 정책으로 수렴.

이중 리뷰 1R — **CRITICAL 0 / HIGH 0 PASS** (변경 범위 작음 — 패턴 백포트만, 새 로직 X).

### Changed — `app/adapter/out/kiwoom/auth.py`

- **`_do_issue_token`** (au10001) 4개 `from None` → 변수 캡처 + except 밖 raise:
  - `request_validation_failed` — TokenIssueRequest Pydantic 검증
  - `network_error_type` + `resp_or_none` — httpx.HTTPError / OSError 네트워크 오류
  - `json_parse_error_type` + `body_json` (try-else 안 dict guard 보너스 추가) — resp.json() ValueError
  - `response_validation_failed` + `validated` — TokenIssueResponse Pydantic 검증 (input 에 토큰 평문, H5 핵심)
- **`TokenIssueResponse.expires_at_kst()`** — strptime ValueError → `parse_failed` 변수 캡처 패턴
- **`revoke_token`** (au10002) 4개 `from None` — `_do_issue_token` 과 동일 패턴 (request 검증 / 네트워크 / JSON 파싱 / 응답 검증)
- **JSON dict guard 보너스** — `try-except-else: if not isinstance(parsed, dict): raise KiwoomUpstreamError("응답이 dict 아님")` 추가 (`_client.py:271-279` 일관)
- 모듈 docstring 갱신 — F1 백포트 정책 명시 (`__context__` 와 `__cause__` 둘 다 None 보장)

### Added — `tests/test_kiwoom_auth_client.py` (회귀 테스트 +8)

`__context__` leak 회귀 차단 — `from None` 으로 회귀 시 `__context__ != None` 으로 즉시 fail:

1. `test_issue_token_network_error_context_is_cleared` — au10001 httpx.ConnectError
2. `test_issue_token_401_context_is_cleared` — au10001 401 응답
3. `test_issue_token_json_parse_error_context_is_cleared` — au10001 JSON 파싱 실패
4. `test_issue_token_pydantic_validation_error_context_is_cleared` — au10001 Pydantic 검증 실패 (input 에 토큰 평문)
5. `test_expires_at_kst_invalid_date_context_is_cleared` — strptime ValueError 매핑
6. `test_revoke_token_network_error_context_is_cleared` — au10002 네트워크 오류
7. `test_revoke_token_401_context_is_cleared` — au10002 401 응답
8. `test_revoke_token_json_parse_error_context_is_cleared` — au10002 JSON 파싱 실패

각 테스트가 `assert err.__cause__ is None` + `assert err.__context__ is None` 검증.

### Added — `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 9

- § 9.1 ~ 9.5 (5 결정 + 결과 + 보안 일관성 종결 섹션)
- § 8.4 의 F1 상태를 "다음 PR" → "✅ 적용" 으로 갱신

### 검증

- 285 passed (이전 277, +8) / coverage **91.0%** (이전 90.36%, +0.64%)
- ruff check 0 / ruff format 0 / mypy strict 0 / bandit 0
- `auth.py` 자체 커버리지 91% (이전 ~88%)
- 보안 일관성 종결: backend_kiwoom 의 `from None` 0건 (코드) — A3-α 4건 + F1 8건 = **12 회귀 테스트** 가 패턴 회귀 시 즉시 fail

---

## [2026-05-07] feat(kiwoom): Phase A3-α — KiwoomClient 공통 트랜스포트 + ka10101 어댑터 (이중 리뷰 1R, 277 tests / 90.36%)

`backend_kiwoom` Phase A3 의 첫 chunk (α). **KiwoomClient 공통 트랜스포트** (모든 후속 endpoint B~G 22개의 기반) + KiwoomStkInfoClient.fetch_sectors (ka10101) + 단위 테스트만. β (Migration 002 + Repository + UseCase + 라우터) / γ (APScheduler weekly) 별도 PR.

ted-run 풀 파이프라인 + 적대적 이중 리뷰 1R. **CRITICAL 1 (C-1: `__context__` 토큰 leak) + HIGH 4 (token / 헤더 인젝션 / Semaphore-Lock 직렬화 / AsyncGenerator break 계약) + MEDIUM 7** 발견 → 전부 적용 → CRITICAL/HIGH 0 PASS.

### Added — `app/adapter/out/kiwoom/_client.py` (신규)

- **`KiwoomClient`** 공통 트랜스포트 — httpx + tenacity + Semaphore + paginated
  - `token_provider: Callable[[], Awaitable[str]]` 의존성 주입 (캐시는 provider 책임 = TokenManager)
  - tenacity AsyncRetrying — `KiwoomUpstreamError` + `KiwoomRateLimitedError` 만 재시도 (α 정책 일관)
  - `_throttle()` H-2 보강 — `_next_slot_ts` lock 안에서 atomic 갱신, sleep 은 lock 밖 → 4 코루틴이 0/250/500/750ms 분산 sleep (의도된 동시성 + RPS)
  - **C-1 토큰 헤더 인젝션 차단** — `_VALID_TOKEN_PATTERN` (`^[A-Za-z0-9._\-+/=]+$`) wire 전 정규식 검증
  - **C-1 `__context__` leak 차단** — `raise` 를 `except` 블록 밖에서 실행 (변수 캡처 패턴). `from None` 은 `__suppress_context__=True` 만 set, `__context__` 는 살아있어 Sentry/structlog `walk_tb` leak 가능
  - **H-1 페이지네이션 헤더 인젝션 차단** — `cont_yn` 화이트리스트 (`Y/N`) + `next_key` 정규식 검증 (request + response 양쪽)
  - 응답 본문 어떤 경로로도 logger / 예외 메시지에 미포함 (α 정책 일관)
- **`call_paginated`** AsyncGenerator — `cont-yn=Y` 동안 반복, `max_pages` hard cap → `KiwoomMaxPagesExceededError`
- **`KiwoomResponse`** dataclass (frozen + slots) — body + cont_yn + next_key + status_code
- **`KiwoomMaxPagesExceededError`** — 무한 cont-yn=Y DoS 방어

### Added — `app/adapter/out/kiwoom/stkinfo.py` (신규)

- **`KiwoomStkInfoClient.fetch_sectors`** (ka10101) — 단일 시장 업종 리스트 + 페이지네이션 자동 합쳐짐
  - **M-2 mrkt_tp 시그니처** `Literal["0","1","2","4","7"]` — mypy strict 가 caller 까지 강제. 런타임 가드 belt-and-suspenders 유지
  - SectorListRequest Pydantic — wire 직전 검증
  - SectorListResponse Pydantic — `items` attribute + `list` alias (builtin shadowing 회피)
  - SectorRow Pydantic — camelCase 유지 (키움 응답 그대로, `# noqa: N815`)
  - max_pages=20 (어댑터 보수적 cap)

### Tests — 신규 2 파일 / +38 케이스

- `tests/test_kiwoom_client.py` (신규) — 24 케이스
  - 정상 호출 + 헤더 자동 설정 (api-id / authorization / Content-Type)
  - cont_yn / next_key 응답 헤더 추출 (KiwoomResponse)
  - 페이지네이션 헤더 caller 전달 / 미전달 / 응답 헤더 None 처리
  - token_provider 매 호출 시 호출 (3회 → 3 token)
  - 401/403 재시도 0회 / 429 tenacity 재시도 / 5xx 재시도 / 네트워크 재시도
  - JSON 파싱 실패 → KiwoomUpstreamError
  - return_code != 0 → KiwoomBusinessError
  - call_paginated — 단일 / 다중 / max_pages 한도 초과
  - 응답 본문 (Kiwoom 평문 토큰 모양) 어떤 경로로도 로그 미노출
  - **C-1 회귀 4건** — 토큰 \r\n / control char reject / `__context__` None on network error / `__context__` None on 401
  - **H-1 회귀 3건** — caller cont_yn invalid / next_key \r\n / 응답 cont-yn invalid
  - **M2 회귀** — KiwoomClient max_pages=2 동작 검증
- `tests/test_kiwoom_stkinfo_client.py` (신규) — 14 케이스
  - 정상 호출 (Excel 11 rows) / 페이지네이션 합쳐짐 / 빈 list / Pydantic 검증 누락
  - mrkt_tp 사전 검증 (5 invalid + non-digit) — Literal 우회 (`cast(Any, ...)`) 안전망 검증
  - business / credential rejected 전파
  - SectorListResponse alias `list` 양방향
  - **M2 회귀** — 어댑터 max_pages=20 hard cap 도달
  - **C-1 회귀** — Pydantic ValidationError 시 `__context__` None

### Verification

```
Tests:     277 passed (이전 239 → +38)
Coverage:  90.36% (목표 80% 초과; _client.py 96%, stkinfo.py 97%)
Lint:      ruff 0 / mypy strict 0 (app 34 files + new tests 2 files)
Security:  bandit 0 (B101 assert 제거 — explicit raise 패턴) / pip-audit 0 CVE
Compile:   py_compile clean
Runtime:   KiwoomClient + KiwoomStkInfoClient 인스턴스 smoke OK
Reviews:   1R 이중 리뷰 (sonnet + opus 병렬 독립) — CRITICAL 1 + HIGH 4 + MEDIUM 7 → 전부 적용
```

### A3-α follow-up (별도 PR)

- **F1 (다음 PR — 보안 일관성)**: auth.py (α/β) 의 동일 `__context__` leak 백포트 — 모든 `from None` 패턴을 변수-캡처 except 밖 raise 로 리팩토링
- F2: `KiwoomBusinessError.message` scrub 적용
- F3: `KiwoomMaxPagesExceededError` 라우터 매핑 (503 + Retry-After) — A3-β
- F4: KiwoomClient instance 단일성 강제 — Phase D
- F5: next-key 없이 cont-yn=Y edge case — 운영 검증 후

### 다음 chunk

A3-β: Migration 002 (sector 테이블) + Sector ORM + SectorRepository + SyncSectorMasterUseCase + GET/POST `/api/kiwoom/sectors` + GET `/api/kiwoom/sectors/sync` (admin) + 통합 테스트.

---

## [2026-05-07] feat(kiwoom): Phase A2-β — au10002 폐기 + lifespan graceful shutdown (이중 리뷰 1R, 239 tests / 89.95%)

`backend_kiwoom` Phase A2 의 두 번째 chunk (β). au10002 접근토큰 폐기 + RevokeKiwoomTokenUseCase + TokenManager 확장 (peek/invalidate_all/alias_keys) + DELETE/revoke-raw 라우터 + FastAPI lifespan graceful shutdown. 외부 호출 0 — `httpx.MockTransport` + testcontainers PG16. 운영 dry-run (α+β 일괄)은 코드 완료 후 보류.

ted-run 풀 파이프라인 + 적대적 이중 리뷰 1R. **CRITICAL 1 + HIGH 4 + MEDIUM 5** 발견 → 전부 적용 → CRITICAL/HIGH 0 PASS.

가장 위협적이었던 것 (CRITICAL C-1): `/revoke-raw` 422 응답이 raw_token 평문을 `errors[].input` 으로 echo. β 의 핵심 위협 모델 (body plaintext 비누설) 을 정확히 깨는 이슈. `RequestValidationError` 핸들러로 sensitive paths 화이트리스트에서 input/ctx 필드 제거.

### Added — `app/adapter/out/kiwoom/auth.py`

- **`revoke_token()`** — au10002 어댑터 메서드 (재시도 0회 — best-effort)
  - 401/403 → `KiwoomCredentialRejectedError` (UseCase 가 idempotent 변환)
  - 429 → `KiwoomRateLimitedError` (재시도 금지, α H3 일관)
  - 5xx/네트워크/파싱 → `KiwoomUpstreamError` (재시도 없음)
  - body 에 `appkey + secretkey + token` **3개 평문** — 어떤 경로로도 logger/예외 메시지에 미포함
- **`TokenRevokeRequest`** Pydantic 모델 — `__repr__` 가 secretkey/token 마스킹
- **`TokenRevokeResponse`** Pydantic 모델 — `succeeded` property

### Added — `app/application/service/token_service.py`

- **`RevokeKiwoomTokenUseCase`** (신규)
  - `revoke_by_alias(alias)` — 캐시 hit 시 키움 폐기 + 캐시 무효화. miss 시 `cache-miss` 멱등 응답
  - `revoke_by_raw_token(alias, raw_token)` — 외부 토큰 명시 폐기 (운영 사고 대응)
  - 401/403 → `RevokeResult(revoked=False, reason='already-expired')` (`already-expired-raw` for raw)
  - 5xx/business → 캐시 무효화 후 caller 에 전파
  - revoke_by_raw_token: M-1 적대적 리뷰 — invalidate 를 method 시작 직후로 이동 (decrypt 실패해도 캐시 비움)
- **`RevokeResult`** dataclass — alias / revoked / reason
- **`TokenManager` 확장**: `peek` (만료 무관 캐시 조회) / `alias_keys` (snapshot tuple) / `invalidate_all` (전체 비움)
- **`revoke_all_aliases_best_effort(manager, revoke_use_case)`** — 함수형 shutdown helper. KiwoomError + Exception 모두 swallow + invalidate_all 보장

### Added — `app/adapter/web/_deps.py`

- `get_revoke_use_case` / `set_revoke_use_case` 싱글톤 패턴 (TokenManager 와 동일)
- `reset_token_manager` 가 `_revoke_use_case_singleton` 도 함께 리셋

### Added — `app/adapter/web/routers/auth.py`

- **`DELETE /api/kiwoom/auth/tokens/{alias}`** (admin only) — 캐시 토큰 폐기. 응답에 token 평문 미포함
- **`POST /api/kiwoom/auth/tokens/revoke-raw`** (admin only) — 외부 토큰 명시 폐기. body 의 raw_token 응답 미반환
- **`RevokeTokenResponse`** / **`RevokeRawTokenRequest`** Pydantic 모델 (`extra='forbid'` + token 길이 검증)
- **`_map_revoke_exception`** helper — 6개 도메인 예외 명시 매핑 + fallback 500
- α 라우터 (`POST /tokens`) 에도 `KiwoomRateLimitedError` 매핑 추가 (H-1 적대적 리뷰 — α 부터 누락된 회귀)

### Added — `app/main.py`

- **lifespan graceful shutdown** — `revoke_all_aliases_best_effort` + `asyncio.wait_for(timeout=20s)`
  - timeout / `CancelledError` / 일반 Exception 모두 swallow → 무조건 `manager.invalidate_all()` + `engine.dispose()` 도달 보장 (H-3 적대적 리뷰)
  - finally 분리 — revoke hang/cancel 시에도 engine 자원 정리 보장
- **`RequestValidationError` 핸들러** — `/revoke-raw` 등 sensitive paths 에서 422 응답 input/ctx 필드 제거 (**C-1 적대적 리뷰**: token 평문 echo 차단)
- `_SENSITIVE_VALIDATION_PATHS` 모듈 상수 — frozenset 화이트리스트
- `SHUTDOWN_REVOKE_TIMEOUT_SECONDS = 20.0` 모듈 상수

### Tests — 신규 1 파일 + 확장 3 파일 / +35 케이스

- `tests/test_lifespan.py` (신규) — 3 케이스
  - 활성 alias 3개 모두 폐기 시도 + 캐시 비워짐
  - alias B 폐기 5xx 실패 시 A/C 진행 + 캐시 모두 비워짐 (best-effort)
  - 캐시 비어있을 때 폐기 시도 0회 — no-op
- `tests/test_kiwoom_auth_client.py` (확장) — +8 케이스
  - revoke 정상 200 / 401·403 재시도 0회 / 500 재시도 0회 (best-effort)
  - return_code != 0 → KiwoomBusinessError + message attribute only
  - 응답 본문 (Kiwoom 평문 토큰 모양) 어떤 경로로도 로그 미노출
  - 네트워크 오류 → KiwoomUpstreamError 재시도 없음
  - TokenRevokeRequest `__repr__` secretkey/token 마스킹
- `tests/test_token_service.py` (확장) — +12 케이스
  - peek 캐시 only / 만료 무관 / alias_keys / invalidate_all
  - revoke_by_alias 정상 (cache hit) / cache-miss 멱등 / 401 idempotent / cred 미등록
  - revoke_by_raw_token 정상 + 캐시 무효화 (시작 직후)
  - shutdown — 한 alias 실패해도 나머지 진행
- `tests/test_kiwoom_auth_router.py` (확장) — +12 케이스
  - DELETE admin guard / cache hit / cache-miss / cred 미등록 (alias 평문 미포함)
  - POST revoke-raw admin guard / 정상 / cred 미등록 / 422 short token
  - **C-1 회귀 3건** — alias 빈 문자열 / token list-wrap / extra field 시 422 응답에 valid token 평문 미포함
  - **H-1 회귀 2건** — issue 라우터 + revoke 라우터 모두 429 → 503 매핑
  - **H-2/M-5 회귀** — revoke_by_raw_token 401 → 200 idempotent (`already-expired-raw`)

### Verification

```
Tests:     239 passed (이전 204 → +35)
Coverage:  89.95% (목표 80% 초과; token_service 99%, auth 91%, routers 83%)
Lint:      ruff 0 / mypy strict 0 (app 32 files + new tests 4 files)
Security:  bandit 0 / pip-audit 0 CVE
Compile:   py_compile clean
Runtime:   FastAPI 라우트 등록 + RequestValidationError 핸들러 등록 확인
Reviews:   1R 이중 리뷰 — CRITICAL 1 (C-1) + HIGH 4 (H-1/H-2/H-3 + 1차 RateLimited) + MEDIUM 5 → 전부 적용
```

### 운영 dry-run 보류 (DoD §10.3 일괄)

α + β 합쳐 전체 토큰 라이프사이클 검증 — 운영 키움 자격증명 1쌍 등록 후 별도 작업:
1. `expires_dt` timezone (KST/UTC)
2. `authorization` 헤더 빈 문자열 vs 생략 (au10001)
3. 같은 토큰 2회 폐기 응답 패턴 (200 / 401 / return_code)
4. authorization 헤더 + body token 중복 허용 여부 (au10002)
5. JWT/hex/Kiwoom 평문 토큰 마스킹 회귀

### 별도 후속 PR (β follow-up 5건)

- F1: pre-commit grep — `model_dump` + `logger` 같은 줄 금지
- F2: `/revoke-raw` rate-limiting (`slowapi`)
- F3: `TokenManager.frozen` shutdown 중 신규 발급 차단
- F4: `RevokeRawTokenRequest.token` Field pattern 검증
- F5: shutdown metric

### 다음 chunk

A3 — KiwoomStkInfoClient (ka10101) + Migration 002 (sector 테이블) + SectorRepository + SyncSectorMasterUseCase + APScheduler weekly job.

---

## [2026-05-07] feat(kiwoom): Phase A2-α — au10001 KiwoomAuthClient 발급 경로 (이중 리뷰 1R / 204 tests / 88.07%)

`backend_kiwoom` Phase A2 의 첫 chunk (α). au10001 접근토큰 발급 + KiwoomAuthClient + IssueKiwoomTokenUseCase + TokenManager + admin POST 라우터 + FastAPI 진입점. β chunk (au10002 폐기 + lifespan graceful shutdown) 는 별도 PR. 외부 호출 0 — `httpx.MockTransport` + testcontainers PG16. 운영 dry-run (DoD §10.3) 은 β 와 일괄.

ted-run 풀 파이프라인 + 적대적 이중 리뷰. 1R 에서 CRITICAL/HIGH 4 + MEDIUM 5 (세션 누수 / lock 폭증 / ValidationError 토큰 누설 / 429 timing oracle / 이중 SELECT 등) → 전부 수정 후 CRITICAL/HIGH 0 PASS.

### Added — `app/adapter/out/kiwoom/`

- **`_exceptions.py`** (신규) — 5개 도메인 예외 + 베이스
  - `KiwoomError` 베이스 / `KiwoomUpstreamError` (5xx · 네트워크 · 파싱) / `KiwoomCredentialRejectedError` (401/403) / `KiwoomBusinessError` (api_id+return_code, message attribute only — M1 적대적 리뷰) / `KiwoomRateLimitedError` (429) / `KiwoomResponseValidationError` (Pydantic)
- **`auth.py`** (신규) — `KiwoomAuthClient` + `TokenIssueRequest`/`TokenIssueResponse` Pydantic 모델
  - `httpx.AsyncClient` + tenacity `AsyncRetrying` (KiwoomUpstreamError 만 재시도 — 401/403/429/Pydantic 4xx 즉시 fail-fast)
  - `expires_at_kst()` strptime ValueError 도메인 매핑 (M2)
  - Pydantic `ValidationError` cause chain 차단 (`from None`) — `ValidationError.input` 에 토큰 평문 보존 (H5 적대적 리뷰)
  - 응답 본문 어떤 경로로도 logger/예외 메시지에 미포함 — Kiwoom 평문 토큰은 패턴 매칭 마스킹 미보장
  - `OSError` 포함 broader exception catch — ssl.SSLError 등 (M4)
  - 테스트용 `max_attempts` / `retry_min_wait` / `retry_max_wait` 인자 (속도)

### Added — `app/application/service/`

- **`token_service.py`** (신규)
  - `IssueKiwoomTokenUseCase.execute(alias)` — `find_by_alias` + `decrypt_row` 1쿼리 (이중 SELECT 회귀 차단, HIGH 1차 리뷰)
  - `TokenManager.get(alias)` — alias 별 `asyncio.Lock` + `dict.setdefault` atomic + double-check pattern
  - `TokenManager` `session_provider` 주입 — 매 발급마다 `async with session_provider() as session` 세션 lifecycle 보장 (H4 적대적 리뷰: DB 풀 누수 차단)
  - `max_aliases` (default 1024) 캡 — alias 폭증 lock proliferation DoS 방어 (H1)
  - 무효 alias (`CredentialNotFoundError`) 발생 시 `_locks.pop(alias)` 정리 (H1)
  - `CredentialNotFoundError` / `CredentialInactiveError` / `AliasCapacityExceededError` 도메인 예외

### Added — `app/adapter/web/`

- **`_deps.py`** (신규) — admin guard + TokenManager 싱글톤
  - `require_admin_key` — `hmac.compare_digest` timing-safe + `admin_api_key=""` fail-closed (401)
  - `get_token_manager` / `set_token_manager` / `reset_token_manager`
- **`routers/auth.py`** (신규) — `POST /api/kiwoom/auth/tokens` (admin only)
  - `IssueTokenResponse` — 평문 토큰 미반환 (`mask_token` tail 6, 25% cap — L1)
  - `expires_at` 분 단위 절단 — fingerprint 차단 (M5)
  - HTTPException detail 비식별화 — alias / `return_msg` / appkey 평문 미포함 (M1)

### Added — `app/main.py` (신규, α 최소 스켈레톤)

- FastAPI `lifespan` — `setup_logging` + `KiwoomCredentialCipher` + `TokenManager` 싱글톤 등록 + engine dispose
- session_provider 패턴 — `async_sessionmaker()` 호출이 AsyncSession 자체 async context manager 반환
- `/health` 엔드포인트 + auth_router 등록
- β 에서 graceful shutdown hook 추가 예정

### Added — `app/application/dto/kiwoom_auth.py`

- `mask_token(token, tail=6)` — 25% 자동 축소로 짧은 opaque 토큰 fallback 안전 (L1)

### Added — `app/adapter/out/persistence/repositories/kiwoom_credential.py`

- `decrypt_row(row)` — 이미 fetch 된 row 를 sync 복호화. 추가 DB 쿼리 회피 (HIGH 1차 리뷰)

### Tests — 신규 4 파일 / +43 케이스

- `tests/test_kiwoom_auth_client.py` (신규) — 14 케이스
  - 정상 발급 / return_code != 0 / 빈 토큰 / expires_dt 형식 오류
  - 401·403 재시도 금지 (1회만 호출 검증)
  - 429 재시도 금지 검증 (H3 회귀)
  - 5xx · 네트워크 오류 tenacity 3회 재시도
  - 응답 본문 (Kiwoom 평문 토큰 모양) 어떤 경로로도 로그 미노출 (F3)
  - `KiwoomBusinessError.__str__` attacker-influenced message 미포함 (M1)
  - `expires_at_kst` 잘못된 날짜 → 도메인 예외 (M2)
- `tests/test_token_service.py` (신규) — 12 케이스
  - UseCase 정상 / 미등록 / 비활성 / 401 전파 / prod URL / 단일 SELECT 회귀
  - TokenManager 캐시 hit / 만료 재발급 / 동시 5코루틴 → 1회 합체 (real async yield, H2)
  - invalidate / 다중 alias 격리
  - `max_aliases=2` capacity 초과 시 `AliasCapacityExceededError`
  - 무효 alias 10회 후 `_locks` 정리 검증 (H1)
- `tests/test_kiwoom_auth_router.py` (신규) — 10 케이스
  - admin key 미지정 / 잘못 / 미설정 시 401 (fail-closed, monkeypatch fixture — M3)
  - 정상 발급 — 응답에 토큰 평문 미포함 + expires_at 분 단위 절단 검증
  - 404 alias 평문 detail 미포함
  - 비활성 400 / 자격증명 거부 400 / 강제 갱신 (매번 invalidate)
  - F5 회귀 — 응답에 appkey/secretkey 평문 미노출
  - F5 회귀 — KiwoomBusinessError 시 `return_msg` 평문 detail 미포함
- `tests/test_logging_masking.py` (확장) — au10001 회귀 3건
  - 응답 dict token 키 [MASKED]
  - 응답 본문 string interpolated JWT 자동 마스킹
  - 요청 body appkey/secretkey 키 [MASKED]

### Verification

```
Tests:     204 passed (이전 161 → +43)
Coverage:  88.07% (목표 80% 초과; token_service 100%, _exceptions 100%, auth 91%)
Lint:      ruff 0 / mypy strict 0 (app 32 files + new tests 4 files)
Security:  bandit 0 issues (B105 nosec 1 기존) / pip-audit 0 CVE
Compile:   py_compile 32 files clean
Runtime:   uvicorn 기동 smoke OK — /health 200 + admin guard 401
Reviews:   1R 이중 리뷰 (sonnet python-reviewer + opus security-reviewer 병렬 독립) — CRITICAL/HIGH 모두 적용
```

### β chunk 작업 (다음 PR)

au10002 폐기 + lifespan graceful shutdown + `RevokeKiwoomTokenUseCase` + `TokenManager.peek/invalidate_all/alias_keys` + DELETE/POST 폐기 라우터 + revoke-by-raw-token + 운영 dry-run (DoD §10.3 일괄 검증).

---

## [2026-05-07] security(kiwoom): Phase A2 사전 보안 PR — ADR-0001 § 3 #1·#2·#3 적용 (3-Round 이중 리뷰)

`backend_kiwoom` Phase A2 (KiwoomAuthClient) 진입 전 보안 사각지대 차단. ADR-0001 § 3 미적용 4건 중 3건 (#1 정규식 보강 / #2 DTO 직렬화 차단 / #3 raw_response 토큰 scrub) 사전 적용. #4 마스터키 회전 자동화는 Phase B 후반 지연. 외부 호출 0.

ted-run 풀 파이프라인 + 3-Round 적대적 이중 리뷰 사이클. R1 에서 CRITICAL 3 + HIGH 4 발견 → R2 에서 5건 수정 + HIGH-A (정규식 운영 식별자 false positive) 신규 발견 → R3 에서 prefix-aware 정규식으로 수정 → CRITICAL/HIGH 0건 PASS.

### Added — `app/security/scrub.py` (신규)

- **`scrub_token_fields(payload, api_id) → dict`** helper
  - 화이트리스트 기반: `au10001` → `{token, expires_dt}` / `au10002` → `{token, appkey, secretkey}`
  - api_id `.strip().lower()` 정규화 + 인증 endpoint(`au*`) 미등록 시 ValueError fail-closed
  - 비인증 endpoint(`ka*` 등) 통과
  - key 매칭 case-insensitive (`Token`/`TOKEN` 우회 방어)
  - 원본 dict 보존 — 새 dict 반환 (caller 가 token 다른 경로 사용 가능)
  - `[SCRUBBED]` 치환 (필드 삭제 X)

### Changed — `app/observability/logging.py`

- **`_KIWOOM_SECRET_PATTERN`** prefix-aware 정규식 도입 (R3)
  - Before: 부재 → After: `(\b(?:secretkey|secret_key|secret|appkey|app_key|access_token|refresh_token|token|password)\s*[:=]\s*)[A-Za-z0-9+/]{16,1024}\b` (re.IGNORECASE)
  - `_scrub_string` 적용 순서: JWT → HEX → 키움 prefix-aware secret/token
  - group 1 (prefix+separator) 보존 + value 만 `[MASKED_SECRET]` 치환
  - 운영 식별자 (trace_id / correlation_id / PascalCase 클래스명 / build_id) 보존
- `_MASKED_SECRET = "[MASKED_SECRET]"` 추가 (`# nosec B105` — 마스킹 라벨)

### Changed — `app/application/dto/kiwoom_auth.py`

- **`KiwoomCredentials` 직렬화 차단** (다층 방어)
  - `__reduce__` / `__reduce_ex__(protocol: SupportsIndex)` raise — pickle 직접 차단
  - `__getstate__` / `__setstate__` raise — Python 3.10+ slots dataclass 자동 생성 우회 차단 (jsonpickle/dill/cloudpickle)
  - `__copy__` / `__deepcopy__` 명시 정의 — 도메인 내부 복제 허용 (`memo[id(self)] = result`)
- Known limitation: `copyreg.dispatch_table[KiwoomCredentials]` 등록 시 type-level 우회 가능 (Python 본질). 회귀 표시 테스트로 명시.

### Tests — +44 케이스 (총 161 passed / coverage 94.94%)

- `tests/test_scrub.py` (신규) — 16 케이스 (au10001/au10002 normal + edge + 정규화 + case-insensitive + fail-closed)
- `tests/test_kiwoom_auth_dto.py` — pickle/asdict→logger/copy/json/vars/getstate/setstate/copyreg 회귀 6 케이스 추가
- `tests/test_logging_masking.py` — prefix-aware 매칭 14 케이스 + 운영 식별자 보존 6 케이스 추가

### Verification (5관문)

- 3-1 컴파일 import smoke OK
- 3-2 ruff 0 / mypy strict 0
- 3-3 161 passed / coverage 94.94% (목표 80% 초과)
- 3-4 bandit 0 (B105 nosec) / pip-audit 0 CVE
- 3-5 마이그레이션 변경 없음 (skip)

### Known Limitations (별도 후속 PR)

- `_KIWOOM_SECRET_PATTERN` 화이트리스트 확장 (`client_secret`/`bearer`/`apikey`/`private_key`)
- `_TOKEN_FIELDS_BY_API` allow-list 전환 (R1 HIGH-4)
- SQLAlchemy `before_insert` event listener 로 raw_response scrub 자동 적용
- CI grep 룰 — f-string 내 평문 secret/token 삽입 PR 차단
- `_capture_stdlib_log` 헬퍼 IndexError 가드, deepcopy memo 변조 방어, `expires_dt` 마스킹

---

## [2026-05-07] feat(kiwoom): Phase A1 — 기반 인프라 코드화 첫 chunk

`backend_kiwoom` Phase A 의 A1 chunk (기반 인프라) 코드화. 외부 키움 API 호출 0 — Settings + Fernet Cipher + structlog 마스킹 + Migration 001 (3 테이블) + Repository + 117 테스트. 25 endpoint 계획서 완성 후 첫 코드. ADR-0001 기록.

### Added — backend_kiwoom 신규 프로젝트

- **프로젝트 골격**
  - `pyproject.toml` (uv lock 기반, Python 3.12+, ruff + mypy strict + pytest + bandit)
  - `Dockerfile` (multi-stage builder/runtime, uv 0.11 digest pin, appuser uid 1001)
  - `alembic.ini` (path_separator=os, version_table_schema=kiwoom)
  - `.env.example` (8 env field)
  - `README.md` (상태 + 디렉토리 + 보안 원칙)
- **Settings** (`app/config/settings.py`)
  - Pydantic v2 BaseSettings — 8 KIWOOM_* 필드
  - `kiwoom_default_env: Literal["prod", "mock"]`
  - `kiwoom_credential_master_key` 빈 값 → fail-fast 로 cipher 초기화 차단
- **KiwoomCredentialCipher** (`app/security/kiwoom_credential_cipher.py`)
  - Fernet (AES-128-CBC + HMAC-SHA256) 대칭 암호화
  - `key_version` 다중 관리 — 회전 대비
  - 4 예외 계층: `KiwoomCredentialCipherError` / `MasterKeyNotConfiguredError` / `UnknownKeyVersionError` / `DecryptionFailedError`
  - 외부 `InvalidToken` 누출 차단 (메시지에 ciphertext/plaintext 미포함)
- **structlog 마스킹** (`app/observability/logging.py`)
  - 2층 방어: 키 매칭 (SENSITIVE_KEYS 17개 + SUFFIXES 19개) + JWT/40+hex 정규식 scrub
  - `_scan` 재귀: dict/list/tuple/**set/frozenset**/str
  - stdlib `logging` 통합 — `logger.info()` 호출도 자동 마스킹
- **DTO** (`app/application/dto/kiwoom_auth.py`)
  - `KiwoomCredentials` (frozen, secretkey `__repr__` 마스킹)
  - `IssuedToken` (`__post_init__` tz-aware 강제 — KST 응답 파싱 시 9시간 오차 차단)
  - `MaskedKiwoomCredentialView` (외부 응답용)
  - `mask_appkey` (tail 4자 노출) / `mask_secretkey` (전체 마스킹 16자 고정)
- **ORM 모델** (`app/adapter/out/persistence/models/`)
  - `KiwoomCredential` (alias UNIQUE, env CHECK ('prod'|'mock'), BYTEA cipher 컬럼, key_version)
  - `KiwoomToken` (credential_id UNIQUE → 자격증명당 1, BYTEA token_cipher, expires_at TZ)
  - `RawResponse` (api_id/request_hash 인덱스, JSONB request/response_payload)
- **Repository** (`app/adapter/out/persistence/repositories/kiwoom_credential.py`)
  - `upsert(*, alias, env: Literal["prod", "mock"], credentials)` — ON CONFLICT DO UPDATE + `func.now()` (excluded.updated_at NULL 주입 방어)
  - `find_by_alias` / `get_decrypted` / `get_masked_view` / `delete`
  - `deactivate(alias)` — 소프트 비활성화 + 멱등성 (`is_active.is_(True)` 필터)
  - `list_active_by_env(env)` — 배치/스케줄러용
  - `_helpers.rowcount_of()` — `result.rowcount` mypy attr-defined 우회
- **Migration 001** (`migrations/versions/001_init_kiwoom_schema.py`)
  - `CREATE SCHEMA IF NOT EXISTS kiwoom`
  - 3 테이블 + 인덱스 6개 + UNIQUE/CHECK 제약
  - `migrations/env.py` — asyncpg → psycopg2 URL 자동 치환
  - downgrade 안전판: `kiwoom_credential` row 0 보장. 데이터 있으면 `RAISE EXCEPTION`

### Added — 테스트 (117 passed / coverage 94.61%)

- `tests/conftest.py` — testcontainers PG16 세션 픽스처 + master_key + 트랜잭션 격리 session
- `tests/test_kiwoom_credential_cipher.py` (12) — round-trip + 회전 + 빈/잘못된 마스터키 + 누출 검증
- `tests/test_settings.py` (9) — Literal 검증 + env override + 환경 격리 monkeypatch
- `tests/test_logging_masking.py` (53) — _scan / _scrub_string / mask_sensitive / setup_logging stdlib 통합 + set/frozenset 추가
- `tests/test_kiwoom_auth_dto.py` (14) — IssuedToken tz-aware + mask_appkey/secretkey + KiwoomCredentials repr
- `tests/test_models.py` (7) — ORM schema + UNIQUE/CHECK 제약 + JSONB
- `tests/test_kiwoom_credential_repository.py` (15) — upsert/find/get_decrypted/masked_view/delete/deactivate/list_active_by_env
- `tests/test_migration_001.py` (7) — schema/테이블/인덱스/BYTEA/JSONB + upgrade/downgrade 멱등성

### Quality — ted-run 풀 파이프라인 검증

- **Step 0 TDD**: 8 파일 / 117 테스트 작성 (red 확인)
- **Step 1 구현**: 38 파일 / ~1,500줄
- **Step 2a 1차 리뷰** (sonnet): HIGH 1건 (`excluded.updated_at` NULL) + MEDIUM 5건 → 즉시 수정 + 재리뷰 PASS
- **Step 2b 적대적 리뷰** (opus, 보안 민감 분류): CRITICAL/HIGH 0건 PASS
- **Step 3 Verification**: ruff 0 / mypy strict 0 / pytest 117 passed / coverage 94.61% / bandit 0 / pip-audit 0 CVE / alembic 양방향 OK
- **Step 4 E2E**: 자동 생략 (UI 변경 없음)

### Decision Records

- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` — 스택/구조/보안 결정 + Phase B 진입 전 결정 4건 명시 (secretkey 정규식 보강 / DTO 직렬화 우회 방어 / raw_response 토큰 평문 차단 / 마스터키 회전 자동화)

### Pending — A2 (인증 클라이언트) 진입 시 처리

ADR-0001 § 3 의 4건은 A2 코드 작성 **직전** 결정 권고:

1. secretkey 정규식 보강 (logging.py) — 키움 자격증명 형식 매칭 가능한 패턴 추가
2. KiwoomCredentials 직렬화 차단 (`__reduce__`/SecretStr) — DTO 사용처 늘기 전 가드
3. raw_response 의 au10001 응답 토큰 필드 제거 정책 — UseCase 레이어 분기
4. 마스터키 회전 자동화 (`scripts/rotate_master_key.py`) — Settings 다중 키 필드

---

## [2026-05-07] docs(kiwoom): Phase E·F·G 계획서 11건 — 25 endpoint 100% 완성 (uncommitted)

`backend_kiwoom` Phase E (시그널 보강 — 공매도/대차) 3건 + Phase F (순위 — 5종) 5건 + Phase G (투자자별 매매) 3건 = **11 endpoint 계획서** 일괄 완성. 본 세션도 **계획서만 작성** (코드 0줄). **25 endpoint 계획서 100% 완성** (~25,500줄 누적). 다음 단계는 Phase A 부터 코드화 착수.

### Added — Phase E (시그널 보강 — 3건)

- `endpoint-15-ka10014.md` — **공매도 추이 (P1, Phase E reference, 1,069줄)**
  - URL `/api/dostk/shsa` — 공매도 카테고리 첫 endpoint
  - 11 필드 (shrts_qty / ovr_shrts_qty / trde_wght / shrts_avg_pric)
  - `tm_tp` (시작일/기간) 의미 운영 검증 1순위
  - `short_selling_kw` 테이블 + partial index (매매비중 상위 시그널)
  - KRX/NXT 동시 호출 (NXT 공매도 미지원 가능성)
  - `_strip_double_sign_int` helper 재사용 (ka10086 패턴)
  - cron mon-fri 19:45 KST + 1주 윈도 default
- `endpoint-16-ka10068.md` — 대차거래 추이 (P1, 시장 단위, 700줄)
  - URL `/api/dostk/slb` — 대차 카테고리 첫 endpoint
  - **시장 전체** (stk_cd 없음, all_tp=1)
  - 6 필드: 체결주수 / 상환주수 / 증감 / 잔고주수 / 잔고금액
  - `lending_balance_kw` 테이블 + **partial unique index** (scope=MARKET vs STOCK 분리)
  - cron 20:00 KST + 단일 호출 (RPS 부담 없음)
- `endpoint-17-ka20068.md` — 대차거래 추이 (P2, 종목별, 672줄)
  - 같은 URL `/api/dostk/slb` + stk_cd Length=6 (NXT 미지원 가능)
  - ka10068 의 종목별 분리 — 같은 응답 schema, 같은 테이블 (scope=STOCK)
  - cron 20:30 KST + 3000 종목 30~60분

### Added — Phase F (순위 — 5건)

- `endpoint-18-ka10027.md` — **전일대비 등락률 상위 (P2, Phase F reference, 979줄)**
  - URL `/api/dostk/rkinfo` — 5 ranking endpoint 공유 첫 endpoint
  - **`ranking_snapshot` 통합 테이블 + JSONB payload** 패턴 정의 — 5 endpoint 가변 schema 흡수
  - `KiwoomRkInfoClient` 단일 클래스 (5 메서드)
  - `RankingType` enum (FLU_RT/TODAY_VOLUME/PRED_VOLUME/TRDE_PRICA/VOLUME_SDNIN)
  - `mrkt_tp` 의미 4번째 정의 (000/001/101 — ka10099/10101 와 다름)
  - `stex_tp` (1:KRX/2:NXT/3:통합) — 5 ranking endpoint 공통
  - 12 응답 필드 + Body 9 필터
  - cron 19:30 KST
- `endpoint-19-ka10030.md` — 당일 거래량 상위 (P2, 23 필드 wide, 574줄)
  - 응답 필드 23개 (장중/장후/장전 거래량 분리)
  - **★ `returnCode/returnMsg` camelCase 응답** (Excel 표기 — 운영 검증 1순위, Pydantic alias 로 흡수)
  - `MarketOpenType` enum (장중/장후/장전 분기)
  - `primary_metric_of_today_volume` sort_tp 별 분기 (volume/turnover/amount)
  - cron 19:35 KST
- `endpoint-20-ka10031.md` — 전일 거래량 상위 (P3, 가장 단순 6 필드, 398줄)
  - 응답 필드 6개 (5 ranking 중 가장 단순)
  - **`rank_strt`/`rank_end` 페이지네이션** — cont-yn 미사용 (0~100 분할 호출)
  - `qry_tp` 2종 (전일거래량/전일거래대금)
  - cron 19:40 KST
- `endpoint-21-ka10032.md` — 거래대금 상위 (P2, now_rank/pred_rank, 388줄)
  - **Body 가장 단순 (3 필드)** — sort_tp 없음 (단일 정렬)
  - **`now_rank`/`pred_rank` 직접 응답** — 순위 변동 시그널의 raw input
  - 호가 정보 (`sel_bid`/`buy_bid`) 응답 포함
  - effective_rank = now_rank 우선 (응답 list 순서와 다를 가능성)
  - cron 19:50 KST
- `endpoint-22-ka10023.md` — 거래량 급증 (P2, sdnin spike, 442줄)
  - 응답 필드 10 (sdnin_qty / sdnin_rt 시그널)
  - **`tm_tp`/`tm` (분/전일)** + 합성 sort_tp 키 (composite="1_2_5")
  - sort_tp 4종 (급증량/률/감량/감률)
  - DECREASE (3/4) 시 음수 sdnin_qty 정렬
  - cron 19:55 KST (Phase F 마지막)

### Added — Phase G (투자자별 매매 — 3건)

- `endpoint-23-ka10058.md` — **투자자별 일별 매매 종목 (P2, Phase G reference, 920줄)**
  - URL `/api/dostk/stkinfo`
  - **(투자자, 매매구분, 시장, 거래소) → 종목 ranking** (long format)
  - 12 `invsr_tp` 카테고리 (개인/외국인/기관계/금융투자/투신/사모/기타금융/은행/보험/연기금/국가/기타법인)
  - 11 필드 (netslmt_qty/_amt/prsm_avg_pric/avg_pric_pre)
  - `mrkt_tp=001/101` (5번째 정의 — ka10027 의 000 없음)
  - `investor_flow_daily` 테이블 + 운영 default 12 호출 (3 inv × 2 mkt × 2 trde)
  - 이중 부호 (`--335`) 처리 (ka10086 helper 재사용)
  - cron 20:00 KST
- `endpoint-24-ka10059.md` — 종목별 투자자/기관별 wide (P2, 657줄)
  - 같은 URL `/api/dostk/stkinfo`
  - **wide format 20 필드** (12 투자자 카테고리 + OHLCV)
  - **`amt_qty_tp` 의미 ka10131 과 반대** (1=금액, 2=수량 vs 0=금액, 1=수량)
  - `flu_rt` 표기 "우측 2자리 소수점" (`+698` = +6.98%, ka10058 와 다름)
  - `stock_investor_breakdown` 별도 테이블 (long format ka10058 와 분리)
  - 운영 default = (수량, 순매수, 천주, 통합) × 3000 종목 = 30~60분 sync
  - cron 20:30 KST
- `endpoint-25-ka10131.md` — 기관/외국인 연속매매 (P2, 697줄)
  - URL `/api/dostk/frgnistt` (다른 카테고리)
  - **연속순매수 일수 시그널** (`orgn_cont_dys` / `frgnr_cont_dys` / `tot_cont_dys`)
  - 19 필드 (3 카테고리 × 5 메트릭 + period_stkpc_flu_rt)
  - `dt` (기간) = LATEST/3/5/10/20/120 일 / PERIOD (strt~end)
  - `netslmt_tp=2` 고정 (순매수만)
  - **`amt_qty_tp` 의미 ka10059 와 반대** (0=금액, 1=수량)
  - `frgn_orgn_consecutive` 테이블 + total_cont_days 시그널 인덱스
  - cron 21:00 KST (25 endpoint 의 마지막 cron)

### Phase E·F·G 핵심 설계 결정

- **`ranking_snapshot` 통합 테이블 + JSONB payload (Phase F)**: 5 ranking endpoint 의 가변 schema 를 단일 테이블로 흡수. UNIQUE 키 6개 (snapshot_date/time, ranking_type, sort_tp, market_type, exchange_type, rank). GIN 인덱스로 ad-hoc 쿼리 가속. 새 ranking endpoint 추가 시 enum + UseCase 만 작성
- **`investor_flow_daily` (long) vs `stock_investor_breakdown` (wide) 분리 (Phase G)**: ka10058 의 ranking 추출과 ka10059 의 종목 단위 12 투자자 wide breakdown 의 책임 분리. 두 테이블 같은 마이그레이션 (008) + 같은 service 모듈
- **`lending_balance_kw` partial unique index (Phase E)**: ka10068 (시장) + ka20068 (종목별) 같은 테이블 + scope 컬럼 분기. PostgreSQL partial index 로 (scope=MARKET, trading_date) 와 (scope=STOCK, stock_id, trading_date) 두 UNIQUE 키 분리
- **`mrkt_tp` 4번째 + 5번째 의미 정의**: ka10099 (0/10/30/...) → ka10101 (0/1/2/4/7) → ka10027 (000/001/101) → ka10058 (001/101) → ka10131 (001/101). 5 카테고리 별 enum 분리 (`SectorMarketType`, `StockListMarketType`, `RankingMarketType`, `InvestorMarketType`)
- **`stex_tp` 통합 (Phase F + G 일부)**: 5 ranking + ka10058 + ka10131 모두 `1`:KRX / `2`:NXT / `3`:통합. master.md § 11.3 의 `RankingExchangeType` enum 재사용
- **camelCase 응답 흡수 (ka10030)**: Pydantic `Field(alias="returnCode")` + `populate_by_name=True` — Excel 표기와 실제 응답 차이를 안전망으로 흡수
- **연속 일수 시그널 (ka10131)**: total_cont_days desc 정렬 + DESC NULLS LAST partial index — 강한 추세 종목 추출 1순위 쿼리
- **합성 sort_tp 키 (ka10023)**: `composite="{sort_tp}_{tm_tp}_{tm}"` — 같은 시점에 다른 윈도 호출 분리. ranking_snapshot 의 UNIQUE 키 확장 없이 구현
- **이중 부호 (`--335`/`--714`) 처리 일반화**: ka10086 의 `_strip_double_sign_int` helper 가 Phase E (ka10014/10068/20068), Phase G (ka10058/10059/10131) 6 endpoint 에서 재사용. 단일 helper 로 통일된 부호 처리
- **cron chain 19~21시 분할**: 18:30 일봉 → 19:00 ka10086 → 19:15 ka20006 → 19:30~19:55 Phase F (5종) → 20:00 ka10058 → 20:30 ka10059 → 21:00 ka10131. 각 5~30분 간격으로 Semaphore 충돌 회피

### 25 endpoint 누적 통계

| Phase | endpoint | 줄수 | 누적 줄수 |
|-------|----------|------|-----------|
| A (au10001/au10002/ka10101) | 3 | ~3,200 | ~3,200 |
| B (ka10099/100/ka10001) | 3 | ~2,400 | ~5,600 |
| C (ka10081~94/ka10086) | 5 | ~3,170 | ~8,770 |
| D (ka10079/80/ka20006) | 3 | ~3,220 | ~11,990 |
| **E (ka10014/10068/20068)** | **3** | **~2,440** | **~14,430** |
| **F (ka10027/30/31/32/23)** | **5** | **~2,780** | **~17,210** |
| **G (ka10058/59/131)** | **3** | **~2,275** | **~19,485** |
| master.md | — | 653 | **~20,140** |

→ **25 endpoint × 평균 780줄 = ~20,140줄 계획서**. 본 세션 (E+F+G) **+7,496줄** 추가.

### 25 endpoint 코드화 진입 준비 완료

Phase A·B·C·D·E·F·G **모두 계획서 완성** (코드 0줄). master.md § 11 권고에 따라 다음 세션은 Phase A 부터 순차 코드화 착수:

1. **Phase A** (인증 + sector 마스터, 3 endpoint) — pyproject.toml + Dockerfile + Alembic 001 + KiwoomClient 공통 트랜스포트
2. **Phase B** (종목 마스터, 3 endpoint) — Alembic 002 + LookupStockUseCase
3. **Phase C** (백테스팅 OHLCV, 5 endpoint) — Alembic 003/004/005 + 백테스팅 엔진 즉시 검증
4. **Phase D** (보강 시계열, 3 endpoint)
5. **Phase E** (시그널 보강, 3 endpoint)
6. **Phase F** (순위, 5 endpoint)
7. **Phase G** (투자자별, 3 endpoint)
8. **Phase H** (통합) — 백테스팅 view, 데이터 품질 리포트, retention drop

### Phase E·F·G 운영 검증 우선순위 (DoD § 10.3 모음)

| Endpoint | 항목 | 영향 |
|----------|------|------|
| ka10014 | **`tm_tp` (시작일/기간) 의미** | 응답 row 분포 |
| ka10014 | NXT 공매도 응답 가능 여부 | partial 실패율 |
| ka10068 | 시장 분리 응답 가능 여부 (KOSPI/KOSDAQ) | 별도 호출 필요성 |
| ka10068 | `rmnd` 누적 vs 일별 변동 의미 | derived feature 정합성 |
| ka20068 | NXT 호출 가능 여부 (stk_cd Length=6) | NXT 시계열 가능성 |
| ka10027 | `stk_cls`/`cntr_str`/`cnt` 의미 | payload 활용 |
| ka10030 | **`returnCode/returnMsg` camelCase 응답 확정** | 5 endpoint 일관성 |
| ka10030 | 장중/장후/장전 분리값 발효 시점 | mrkt_open_tp 활용 |
| ka10031 | qry_tp=1 vs 2 응답 정렬 의미 | trde_qty 가 거래대금 대체? |
| ka10032 | `now_rank` vs list 순서 일치 | rank 컬럼 의미 |
| ka10023 | `tm_tp=1` + `tm="5"` 의미 | 분 단위 시그널 시점 |
| ka10058 | **`netslmt_qty/_amt` 부호 의미** (trde_tp=2 시) | 부호 처리 |
| ka10058 | 이중 부호 (`--335`) 빈도 | 정규화 helper 적용 |
| ka10059 | **`flu_rt` 표기 (`+698` = 6.98%)** | 정규화 / 100 |
| ka10059 | `orgn = 12 sub-카테고리 합` 정합성 | wide row 검증 |
| ka10059 | `natfor` (내외국인) 의미 | 컬럼 활용 |
| ka10131 | **`amt_qty_tp` (0=금액, 1=수량) — ka10059 와 반대** | 단위 mismatch 위험 |
| ka10131 | `cont_netprps_dys` 산식 (orgn + frgnr = total?) | 시그널 정합성 |
| ka10131 | 응답 stk_cd Length=6 (NXT 처리) | NXT 시그널 |

---

## [2026-05-07] docs(kiwoom): Phase D 계획서 3건 — 보강 시계열 (틱·분봉·업종) (uncommitted)

`backend_kiwoom` Phase D (보강 시계열) 계획서 3건 완성. 본 세션도 **계획서만 작성** (코드 0줄). Phase A(3) + B(3) + C(5) + D(3) = 14 endpoint 계획서 누적, 약 ~12,200줄 문서. 25 endpoint 중 14 완성 (56%).

### Added — Phase D endpoint 계획서

- `src/backend_kiwoom/docs/plans/endpoint-11-ka10079.md` — **주식틱차트 (P3, 화이트리스트 + 옵션)**
  - 1,100줄 — 데이터 폭증 정책이 본 endpoint 의 핵심 설계
  - **화이트리스트 필수** — 액티브 50 종목 × tic_scope=1 × 정규장 = 일 ~500만 row × 거래소
  - `TickWhitelist` 테이블 + 운영자 명시 등록 — 자동 추가 안 함
  - `KiwoomChartClient.fetch_tick` + `IngestTickUseCase` + `IngestTickWhitelistUseCase`
  - `cntr_tm` 14자리 (`YYYYMMDDHHMMSS` KST) → `executed_at` TIMESTAMPTZ
  - **같은 cntr_tm 내 다중 체결**: `sequence_no` UNIQUE 컬럼으로 분리
  - `tic_scope` 1/3/5/10/30 (분봉과 다름) → `TickScope` enum 분리
  - **base_dt 파라미터 부재** → 백필 불가, forward-only ingest
  - `stock_tick_price` 월별 파티션 + retention 30일 권장
  - `tick_collection_enabled: bool = False` 토글 — 기본 OFF
  - cron KST mon-fri 19:30 (선택, ka10080 와 시간 분리 필요)
- `src/backend_kiwoom/docs/plans/endpoint-12-ka10080.md` — **주식분봉차트 (P2, normal-path)**
  - 1,167줄 — Phase D 의 normal-path. 종목 OHLCV 의 일중 보강
  - `tic_scope` 1/3/5/10/15/30/45/60 분 (틱과 다름 — 15·45 추가) → `MinuteScope` enum 분리
  - **`base_dt` optional** — 백필 가능 (틱은 불가). `BackfillMinuteUseCase` 점진 과거 호출
  - **`acc_trde_qty` (누적 거래량)** — Excel 스펙 표 누락 + 예시 등장. 운영 검증 1순위
  - KRX/NXT 동시 호출 (NXT enable 만) — 분봉은 ka10079 와 달리 전체 active 종목 default
  - `KiwoomChartClient.fetch_minute` + `IngestMinuteUseCase` + `IngestMinuteBulkUseCase`
  - `stock_minute_price` 월별 파티션 — Migration 005 (ka10079 와 같은 마이그레이션)
  - 운영 default `MinuteScope.MIN_5` (5분봉) — 1분봉은 P0 종목 화이트리스트만
  - active 3000 × 2 거래소 = 4500 호출, 30~60분 sync 추정
  - cron KST mon-fri 19:30 (틱과 시간 충돌 — 분봉 19:30, 틱 20:00 등 분리 필요)
- `src/backend_kiwoom/docs/plans/endpoint-13-ka20006.md` — 업종일봉 (P2, 가벼움)
  - 953줄 — Phase D 의 가장 가벼운 endpoint
  - **★ 100배 값 정규화**: "지수 값은 소수점 제거 후 100배 값으로 반환" — 응답 252127 = 2521.27
  - `close_index_centi` BIGINT 컬럼 + `close_index` Decimal property (centi/100)
  - **NXT 미지원** — 업종 지수는 거래소 통합 카테고리. 단일 호출
  - `inds_cd` 3자리 (ka10101 의 sector_code 와 직접 호환) — Phase A sector 마스터 의존
  - 응답 7 필드 (ka10081 의 10필드보다 3개 적음 — pred_pre/pred_pre_sig/trde_tern_rt 없음)
  - `KiwoomChartClient.fetch_sector_daily` + `IngestSectorDailyUseCase` + `IngestSectorDailyBulkUseCase`
  - `sector_price_daily` 단일 테이블 — Migration 008 (Phase A 의 002 와 분리, 활성화 토글 가능)
  - active 50~80 업종 × 1 호출 = 50~80 호출, 1~5분 sync 추정 (가장 가벼움)
  - cron KST mon-fri 19:15 (ka10081 18:30 → ka10086 19:00 → ka20006 19:15 → ka10080 19:30 chain)

### Phase D 의 핵심 설계 결정

- **`TickScope` vs `MinuteScope` enum 분리**: ka10079 는 1/3/5/10/30 (5종), ka10080 은 1/3/5/10/15/30/45/60 (8종) — 같은 `tic_scope` 파라미터 이름의 다른 의미. 잘못 매핑하면 분봉 호출에 틱 enum 사용 가능 → 컴파일 시점 차단
- **틱 화이트리스트 정책**: 자동 등록 없음, 운영자 명시 추가만. 데이터 폭증 통제의 1차 안전판. `tick_collection_enabled` 토글로 2차 안전판
- **`stock_tick_price` 월별 파티션 필수**: 50 종목 × tic_scope=1 × 정규장 = 월 1.5억 row. 단일 테이블이면 PG 인스턴스 부담 폭발 — 월별 파티션 + retention 30일 운영 default
- **`acc_trde_qty` Excel 표기 모순**: ka10080 스펙 표 누락 + 예시 포함. 운영 첫 호출 raw 측정으로 결정 — 응답에 없으면 cumulative_volume NULL, 시그널 활용 보류
- **분봉 base_dt optional 활용**: ka10081 일봉은 required, ka10080 만 선택. 미지정 시 키움이 최신일 응답 추정. 백필 시 점진적 과거 base_dt 사용
- **업종 지수 100배 값 → centi BIGINT**: 정수 산술이 빠르고 정확. NUMERIC(12,2) 변환 후 저장 안 함. read property 로 / 100 변환 노출
- **ka20006 NXT 미지원**: 업종 지수는 거래소 통합 카테고리. master.md § 3 의 "물리 분리" 대상 아님. 단, NXT 자체 지수 산출 가능성은 운영 검증 후 결정
- **cron 19시대 chain 분리**: 18:30 일봉 → 19:00 ka10086 → 19:15 ka20006 업종 → 19:30 ka10080 분봉. 각 15~30분 간격으로 Semaphore 충돌 회피
- **2 endpoint = 1 마이그레이션 (Migration 005 intraday)**: ka10079 + ka10080 두 테이블 동시 생성 — 인트라데이 적재의 토글 단위 통합
- **3 endpoint = 3 마이그레이션 (003/004/005/008 분리)**: 운영 중 단계별 활성화 가능. ka20006 의 008 은 Phase A 의 002 sector 마스터와 분리 — Phase D 도입 시점 결정

### Phase D 의 운영 검증 핵심 (DoD § 10.3 모음)

| Endpoint | 미확정 항목 | 영향 |
|----------|------------|------|
| ka10079 | **`last_tic_cnt` 의미** (빈 문자열 / 페이지 종료 / 다음 키) | 페이지네이션 동작의 1순위 unknown |
| ka10079 | **`pred_pre` 부호** (Excel `"500"` 부호 누락) | ka10080 (`"-600"`) 과 다른 표현 — 부호 처리 일관성 |
| ka10079 | 1 페이지 row 수 (액티브 vs 비액티브) | 페이지네이션 빈도 + max_pages 추정 |
| ka10079 | 키움이 응답하는 기간 (당일만? 직전 N분?) | 백필 가능성 결정 |
| ka10079 | tic_scope=1 vs 30 의 row 수 비율 (이론 30:1) | 데이터 부담 추정 |
| ka10080 | **`acc_trde_qty` 응답 여부** (Excel 스펙 누락 + 예시 등장) | cumulative_volume 컬럼의 활용 가능 여부 |
| ka10080 | `cntr_tm` 분봉 의미 (시작 시각? 종료 시각?) | 백테스팅 진입 시점 1분 lag 가능성 |
| ka10080 | base_date 미지정 응답 범위 | 백필 전략 |
| ka10080 | 1 페이지 row 수 (5분봉 ~80, 1분봉 ~390 추정) | 페이지네이션 빈도 |
| ka10080 | NXT 응답 시간 범위 (8:00~20:00 추정) | NXT 데이터의 시간 분포 |
| ka20006 | **100배 값 가정 실증** (KOSPI 응답값 / 100 ≈ 실제 KOSPI) | 모든 백테스팅 시장 비교의 정확도 |
| ka20006 | `inds_cd` 응답 length (스펙 20 vs 실제 3~4 추정) | 컬럼 폭 결정 |
| ka20006 | **(market_code, sector_code) UNIQUE vs sector_code 만 UNIQUE** | sector 마스터 매핑 정책 |
| ka20006 | NXT 거래소 별도 지수 응답 가능 여부 | NXT 시장 분석 가능성 |

### Phase D 가 끝나면 가능한 것

- 종목 분봉 (5분봉) 전체 active × 1년 = ~60M row 적재 (월별 파티션) — 백테스팅 v2 의 분봉 입력
- 업종 일봉 50~80 × 3년 = ~60K row — 시장 비교 / 베타 / 섹터 회전 시그널
- 화이트리스트 50 종목 × 30틱 × 30일 = ~5M row — 슬리피지 시뮬 + 분봉 합성 검증
- KRX/NXT 분봉 분리 — 정규장 외 시간대 가격 발견 패턴 분석
- 종목 일봉 (Phase C) + 분봉 (Phase D) cross-check — 어느 source 가 정답인지 데이터 품질 리포트

### Phase D 누적 통계

- **계획서 라인**: 1,100 (ka10079) + 1,167 (ka10080) + 953 (ka20006) = **3,220줄**
- **Phase A+B+C+D = 14 endpoint × 평균 870줄** = ~12,200줄 + master.md 653줄 = ~12,800줄 계획서
- **25 endpoint 중 14 완성** = **56%**
- **누적 코드 변경**: 0 (계획서 단계)

---

## [2026-05-07] docs(kiwoom): Phase C 계획서 5건 — 백테스팅 OHLCV + 일별 수급 (committed: de6d109)

`backend_kiwoom` Phase C (백테스팅 본체) 계획서 5건 완성. 본 세션은 **계획서만 작성** (코드 0줄). Phase A(3) + Phase B(3) + Phase C(5) = 11 endpoint 계획서 누적, 약 ~8,400줄 문서. 25 endpoint 중 11 완성 (44%).

### Added — Phase C endpoint 계획서

- `src/backend_kiwoom/docs/plans/endpoint-06-ka10081.md` — **주식일봉차트 (★ 백테스팅 코어, P0)**
  - reference 계획서 (1,172줄) — Phase C 의 다른 chart endpoint 가 본 패턴 복제
  - **KRX/NXT 동시 호출** + `stock_price_krx` / `stock_price_nxt` 물리 분리 적재
  - `_DailyOhlcvMixin` SQLAlchemy mixin — 4 (일/주/월/년) × 2 (KRX/NXT) = 8 테이블 컬럼 공유
  - `KiwoomChartClient.fetch_daily` + `IngestDailyOhlcvUseCase` + `IngestDailyOhlcvBulkUseCase` + `BackfillDailyOhlcvUseCase`
  - `upd_stkpc_tp=1` 수정주가 모드 — 백테스팅 액면분할/배당락 자동 보정
  - active 3000 + NXT 1500 = 4500 호출, 30~60분 sync 추정 (Semaphore=4 + 250ms interval)
  - cron KST mon-fri 18:30 (장 마감 + 청산 + 펀더멘털 후 안정 시점)
  - bulk batch 50 commit + SAVEPOINT 시장 격리 + lazy fetch (LookupStockUseCase.ensure_exists) 의존성
- `src/backend_kiwoom/docs/plans/endpoint-07-ka10082.md` — 주식주봉차트 (P1)
  - ka10081 패턴 복제 — 응답 list 키만 다름 (`stk_stk_pole_chart_qry`)
  - `StockPricePeriodicRepository` + `IngestPeriodicOhlcvUseCase` 통합 (주/월/년봉 공유)
  - `Period` StrEnum 분기 (WEEKLY/MONTHLY/YEARLY)
  - cron 금 KST 19:00 (주 마감 후)
  - 백필 1 페이지로 충분 (~156 주봉)
- `src/backend_kiwoom/docs/plans/endpoint-08-ka10083.md` — 주식월봉차트 (P1)
  - ka10081/82 패턴 복제 — list 키 `stk_mth_pole_chart_qry`
  - cron 매월 1일 KST 03:00
  - `dt` 의미: 달의 첫 거래일 (운영 검증)
- `src/backend_kiwoom/docs/plans/endpoint-09-ka10094.md` — 주식년봉차트 (P2)
  - ka10081 패턴 복제 + **응답 7 필드만** (pred_pre/pred_pre_sig/trde_tern_rt 누락)
  - **NXT 호출 skip 정책** — 부분 년 데이터 의미 약 (NXT 운영 ~2025-03 시작 가정)
  - cron 매년 1월 5일 KST 03:00
  - 30년 백필도 1 페이지 (~30 row)
- `src/backend_kiwoom/docs/plans/endpoint-10-ka10086.md` — **일별주가 (★ 시그널, P0, 22 필드)**
  - URL **`/api/dostk/mrkcond`** (chart 가 아님!) — 별도 카테고리
  - 22 필드 5 카테고리 분해: A.시점(1) / B.OHLCV(8) / C.신용(2) / D.투자자별(4) / E.외인+순매수(7)
  - **OHLCV 중복 적재 안 함** — ka10081 가 정답. 본 endpoint 는 C+D+E = 13 필드만 영속화
  - `KiwoomMarketCondClient.fetch_daily_market` + `stock_daily_flow` 별도 테이블 (Migration 005)
  - **이중 부호 처리** (`--714`): `_strip_double_sign_int` helper. Excel 예시상 모호 → 운영 검증 필수
  - **외인순매수 단위 mismatch**: Excel R15 "외국인순매수는 indc_tp 무시 항상 수량" → 컬럼 분리 + 정규화 무시
  - `indc_tp` 기본 = QUANTITY (백테스팅 시그널 단위 일관성)
  - cron KST mon-fri 19:00 (ka10081 18:30 직후, OHLCV 적재 후 cross-check 가능)

### Phase C 의 핵심 설계 결정

- **물리 분리 OHLCV 테이블 8개**: stock_price_{krx,nxt} × {daily, weekly, monthly, yearly} — `_DailyOhlcvMixin` 으로 컬럼 공유, ON CONFLICT 정책 통일
- **Migration 003 (KRX OHLCV) / 004 (NXT OHLCV) 분리 적용**: 운영 중 NXT 활성화 토글 가능
- **Migration 005 (stock_daily_flow)**: ka10086 만의 별도 마이그레이션. OHLCV 와 수급 데이터의 책임 분리
- **NXT 년봉 호출 skip**: 부분 년 데이터의 의미 약 + RPS 절약 — Phase D 후반에 운영 1년 후 재검토
- **OHLCV 중복 처리 정책**: ka10081 = 정답, ka10086 의 OHLCV = 적재 안 함. cross-check 는 raw_response 테이블에 보관된 JSON 으로
- **수정주가 강제** (`upd_stkpc_tp=1`): 백테스팅 일관성 — raw 모드는 비교 검증용
- **bulk batch 50 commit**: SAVEPOINT 패턴 + 50건 단위 commit — 중간 오류 격리
- **`indc_mode=QUANTITY` 기본**: 다른 종목 비교 시 가격 변동 무관, 시그널 단위 일관성

### Phase C 코드 공유 비율

| 자산 | 4 chart endpoint 공유 | ka10086 | 누적 줄수 |
|------|----------------------|---------|-----------|
| `KiwoomChartClient` 클래스 | reference + 메서드 4개 | (별도 `KiwoomMarketCondClient`) | ~600 |
| `_DailyOhlcvMixin` ORM mixin | 8 테이블 공유 | (사용 안 함) | ~80 |
| `NormalizedDailyOhlcv` dataclass | 4 endpoint 공유 | (별도 `NormalizedDailyFlow`) | ~30 |
| `_to_int` / `_to_decimal` / `_parse_yyyymmdd` | (Phase B helper 재사용) | 동일 | 0 |
| `IngestPeriodicOhlcvUseCase` | 3 endpoint 공유 (W/M/Y) | (별도 `IngestDailyFlowUseCase`) | ~250 |
| Repository | StockPriceRepository (일봉 hot) + StockPricePeriodicRepository (주/월/년) | StockDailyFlowRepository | ~400 |

→ Phase C 의 chart 4 endpoint **실제 구현 줄수**는 ka10081 reference (~700줄) + 나머지 3 endpoint 합쳐 ~300줄 = ~1,000줄. ka10086 별도 ~700줄. **Phase C 전체 코드 ~1,700줄 추정**.

### Decided

- **이중 부호 (`--714`) 처리 가설 B 채택** (현재): `--` prefix 1개 제거 후 `_to_int`. 운영 첫 호출 raw 측정 후 가설 수정 가능 (master.md § 12 승격 후보)
- **외인순매수 단위 항상 수량** (Excel R15 가정): `indc_tp` 무시. R15 가정이 틀리면 수십% 시그널 오차 → 운영 검증 1순위
- **Phase C 호출 큐 의존성**: ka10099 응답의 `nxt_enable=true` 종목만 NXT 호출 큐. Phase B 가 끝나야 Phase C 진입 가능
- **trading_date timezone 가정**: KST 거래일. DATE 컬럼 timezone-naive — UTC 변환 안 함
- **백필 페이지네이션**: 일봉 3년 = 1~12 페이지, 주/월/년봉은 1 페이지 충분. 운영 측정 후 master.md § 12 에 페이지 row 수 기록

### Documentation

- ka10081 reference (1,172줄) + 짧은 형식 3건 (415/324/413줄, ka10081 패턴 복제로 차이점만) + ka10086 (847줄, 별도 카테고리)
- 각 계획서 11 섹션 (Excel R20~R56 명세 그대로 + Pydantic/ORM/UseCase/Repository + DB schema + 테스트 + DoD + 위험 메모)
- §11.3 endpoint 간 비교 표 — 4 chart endpoint 공유 / ka10086 와 ka10081 의 책임 분리
- §11.4 향후 확장 — 데이터 품질 리포트 (Phase H), 분봉/틱 (Phase D), 백테스팅 read API 의 batch read

### Uncommitted

본 세션은 커밋 없음. 추가된 untracked:
- `src/backend_kiwoom/docs/plans/endpoint-06-ka10081.md`
- `src/backend_kiwoom/docs/plans/endpoint-07-ka10082.md`
- `src/backend_kiwoom/docs/plans/endpoint-08-ka10083.md`
- `src/backend_kiwoom/docs/plans/endpoint-09-ka10094.md`
- `src/backend_kiwoom/docs/plans/endpoint-10-ka10086.md`

추천 커밋 메시지: `docs(kiwoom): Phase C 5건 — 백테스팅 OHLCV (KRX/NXT 분리) + 일별 수급 시그널`

---

## [2026-05-07] docs(kiwoom): Phase B 계획서 3건 — 종목 마스터 + 펀더멘털 (uncommitted)

`backend_kiwoom` Phase B (종목 마스터 — NXT enable 게이팅의 source) 계획서 3건 완성. 본 세션은 **계획서만 작성** (코드 0줄). Phase A(3건) + Phase B(3건) = 6 endpoint 계획서 누적, 총 ~5,200줄 문서.

### Added — Phase B endpoint 계획서

- `src/backend_kiwoom/docs/plans/endpoint-03-ka10099.md` — 종목정보 리스트 (P0, 백테스팅 진입점)
  - **NXT 게이팅 source**: 응답 `nxtEnable="Y"` 필터로 Phase C `_NX` 호출 큐 생성
  - 16종 `mrkt_tp` enum 분리 (`StockListMarketType` — 코스피/코스닥/K-OTC/코넥스/ETN/REIT/...)
  - Phase B 수집 범위 5시장 (KOSPI/KOSDAQ/KONEX/ETN/REIT) 권장
  - 시장 단위 트랜잭션 격리 (`begin_nested` SAVEPOINT) — 한 시장 실패가 다른 시장 적재를 막지 않음
  - 디액티베이션 정책: **같은 market_code 범위 내** `is_active=false` 마킹 (KOSPI sync 가 KOSDAQ 종목 비활성화 차단)
  - mock 환경 안전판: `nxtEnable` 응답 무시 강제 false
  - zero-padded string (`listCount="0000000123759593"`) → BIGINT 정규화 + 부호 처리
  - 단위 테스트 11 시나리오 + 통합 테스트 10 시나리오
- `src/backend_kiwoom/docs/plans/endpoint-04-ka10100.md` — 종목정보 조회 단건 (P0, gap-filler)
  - **stk_cd Length=6 강제** — `_NX`/`_AL` suffix 거부 (ka10001 과 다름)
  - `LookupStockUseCase.ensure_exists` — DB miss 시 lazy fetch (Phase C 가 미지 종목 만났을 때 안전망)
  - ka10099 의 `NormalizedStock` / `Stock` ORM 100% 공유, 단건 응답 Pydantic 모델만 분리
  - INSERT/UPDATE 멱등성 — ON CONFLICT(stock_code) DO UPDATE
  - 디액티베이션 안 함 (단건은 활성화만 — 디액티베이션은 ka10099 책임)
  - race condition 흡수 — 동시 ensure_exists 호출 시 ON CONFLICT 가 처리
- `src/backend_kiwoom/docs/plans/endpoint-05-ka10001.md` — 주식기본정보요청 펀더멘털 (P1, 45 필드)
  - **stk_cd Length=20 + `_NX`/`_AL` 허용** — `ExchangeType` enum + `build_stk_cd` helper
  - 응답 4 카테고리 분해: A.기본(3) / B.자본·시총(11) / C.펀더멘털(9) / D.250일통계(8) / E.일중시세(14)
  - **외부 벤더 PER/ROE 주 1회 갱신** (Excel R41/R43) — `fundamental_hash` 컬럼으로 변경 감지
  - Phase B 권장: KRX only 호출 (NXT 시세는 Phase C 의 ka10086 위임)
  - `stock_fundamental` 테이블 — `(stock_id, asof_date, exchange)` UNIQUE 일별 스냅샷
  - 부호 포함 string 처리 (`crd_rt="+0.08"`, `oyr_lwst="-91200"` → `_to_int`/`_to_decimal`)
  - Pydantic alias 매핑 — `250hgst` 같은 비-식별자 키 처리 (`populate_by_name=True`)
  - active 3000 종목 sync 추정 5~12분 (Semaphore=4 + 250ms interval)
  - partial 실패 정책: < 1% 정상 / 1~10% warning / > 10% error+자격증명 점검

### Phase B 의 핵심 설계 결정

- **NXT 호출 큐 = `SELECT FROM stock WHERE nxt_enable=true AND is_active=true`** — 본 Phase 가 끝나면 Phase C 의 ka10081 NXT 수집이 즉시 시작 가능
- **mrkt_tp 의미 분리 enum**: ka10099(시장) / ka10101(업종/지수) / ka10027(거래소) 의미 완전히 다름 → 3개 StrEnum 분리 (`StockListMarketType` / `SectorMarketType` / `RankingExchangeType`)
- **단위 모호성**: `mac` (시가총액), `cap` (자본금), `flo_stk` (상장주식), `dstr_stk` (유통주식) 단위 (백만원/억원/천주) 운영 검증 필수 — DoD § 10.3 명시
- **`stock_fundamental.fundamental_hash`**: PER/EPS/ROE/PBR/EV/BPS 6 필드 MD5 — 외부 벤더 갱신일 감지에 활용 (Phase F 시그널 단계)
- **종목 코드 base 추출**: `strip_kiwoom_suffix("005930_NX") → "005930"` — 응답 `stk_cd` 가 suffix 보존/제거 어떤 형태로 와도 base FK 매핑 안전

### Decided

- **Phase B 수집 시장**: KOSPI(0) / KOSDAQ(10) / KONEX(50) / ETN(60) / REIT(6) — 5종 (P0+P1). ETF(8)/금현물(80)/ELW(3) 등 보류
- **펀더멘털 호출 정책**: KRX only (Phase B). NXT 시세는 ka10086 (Phase C) 의 책임 — 펀더멘털 데이터(C카테고리)는 거래소 무관 외부 벤더 데이터
- **lazy fetch**: ka10100 의 `ensure_exists` 가 Phase C 시계열 수집의 안전망 — 신규 상장 종목 무중단 흡수
- **mock 환경 nxt_enable**: 응답값 무시 강제 false (mockapi.kiwoom.com 은 KRX 전용)
- **디액티베이션 같은 market_code 한정**: 시장 단위 sync 가 다른 시장 종목을 비활성화하지 않도록 격리
- **stock_fundamental 일별 스냅샷**: PER/ROE 가 외부 벤더 주 1회 갱신이라 같은 값 며칠 반복되더라도 일별 row 적재 (Phase F 의 hash 변경 감지에 활용)

### Documentation

- 각 계획서 11 섹션 (Excel R20~R76 명세 그대로 반영 + Pydantic/ORM/UseCase/Repository 코드 + DB schema + 테스트 시나리오 + DoD + 위험 메모)
- §11.1 결정 필요 항목 표 + §11.2 알려진 위험 표 — 운영 검증 시점에 master.md § 12 결정 기록으로 승격 예정
- §11.3 endpoint 간 비교 표 — ka10099 vs ka10100 vs ka10001 의 스키마/책임 분담
- 각 계획서 600~1100줄 — Phase A 와 동일 깊이 유지

### Uncommitted

본 세션은 커밋 없음. 추가된 untracked:
- `src/backend_kiwoom/docs/plans/endpoint-03-ka10099.md`
- `src/backend_kiwoom/docs/plans/endpoint-04-ka10100.md`
- `src/backend_kiwoom/docs/plans/endpoint-05-ka10001.md`

이전 세션 untracked 누적 (커밋 대기):
- `src/backend_kiwoom/docs/plans/master.md` + Phase A 3건 (`endpoint-01/02/14`)
- `src/backend_py/SPEC.md`
- `docs/research/kiwoom-rest-feasibility.md` (M)
- 이전 세션 v1.2 Cp 2β: `src/frontend/src/components/charts/IndicatorParametersDrawer.tsx` 외 4건

추천 커밋 분할:
1. `docs(kiwoom): backend_kiwoom 통합 계획서 + Phase A·B 6건 + backend_py SPEC.md`
2. (별도) v1.2 Cp 2β — `feat(v1.2): IndicatorParametersDrawer (편집 UI)`

---

## [2026-05-07] docs(kiwoom): 신규 독립 프로젝트 `backend_kiwoom` 착수 — 통합 계획서 + Phase A 3건 (uncommitted)

키움 REST API 25 endpoint 로 백테스팅 데이터를 적재하는 신규 독립 백엔드 프로젝트 `src/backend_kiwoom/` 착수. 본 세션은 **계획서만 작성** (코드 0줄). 다음 세션부터 Phase B (NXT 종목 마스터) 진행 예정.

### Added — 신규 프로젝트 디렉토리
- `src/backend_kiwoom/docs/plans/master.md` (653줄) — 통합 작업 계획서 12 섹션
  - 25 endpoint 카탈로그 (Tier 1~7, P0/P1/P2/P3 우선순위, 의존성)
  - NXT 수집 전략 — KRX/NXT 물리 분리 테이블 + application 레이어 view 합성
  - DB 스키마 초안 (별도 schema `kiwoom`, Alembic 8 migration 분할)
  - Phase A~H 분할 (총 19~22일 추정)
  - KiwoomClient 공통 트랜스포트 설계 (httpx + tenacity + Semaphore(4) + 250ms 인터벌)
  - Per-Endpoint 계획서 11 섹션 템플릿
- `src/backend_kiwoom/docs/plans/endpoint-01-au10001.md` (626줄) — 토큰 발급
  - `KiwoomAuthClient.issue_token`, `IssueKiwoomTokenUseCase`, `TokenManager` (asyncio.Lock 중복 발급 합체)
  - Fernet 자격증명 암호화 (`kiwoom_credential.appkey_cipher` BYTEA)
  - structlog 마스킹 검증 시나리오 (appkey/secretkey/token 자동 스크럽)
- `src/backend_kiwoom/docs/plans/endpoint-02-au10002.md` (586줄) — 토큰 폐기
  - `revoke_by_alias` (캐시 hit 시) + `revoke_by_raw_token` (운영 사고 대응)
  - Graceful shutdown hook — 활성 alias 전체 폐기 best-effort
  - 멱등성 정책: 401/403 응답 → `RevokeResult(reason='already-expired')` 변환
- `src/backend_kiwoom/docs/plans/endpoint-14-ka10101.md` (668줄) — 업종코드 리스트
  - 5개 시장(`mrkt_tp` 0/1/2/4/7) 순회 + 시장별 트랜잭션 격리
  - `is_active=false` 디액티베이션 정책 (hard delete 회피, FK 안전)
  - 페이지네이션·재시도·로깅 마스킹의 첫 e2e 검증 케이스
- `src/backend_py/SPEC.md` (885줄) — 기존 backend_py 종합 기술 명세서 (8 섹션 + 3 부록)

### Changed
- `docs/research/kiwoom-rest-feasibility.md` — §10 "2026-05-07 업데이트 — 결정 번복" 섹션 추가
  - §1 결론 ("MVP 단계 미구현") 번복 — 데이터 품질 사유로 착수
  - §2.3 미해결 항목 7건 해소 표 (Excel 명세서 입수로)
  - §7 Go 조건 vs 현재 결정 비교 (3/3 미충족이지만 다른 동기로 착수)
  - 신규 프로젝트 범위·의존성·산출물 메모

### NXT 데이터 위치 확정 (Q&A)
- **NXT 거래 가능 종목**: `ka10099`/`ka10100` 응답의 `nxtEnable` 필드 (`Y`=가능)
- **NXT OHLCV**: 차트 API (`ka10079~ka10094`) + `ka10086` 의 `stk_cd` 에 `_NX` suffix (예: `005930_NX`)
- **모의투자 한계**: `mockapi.kiwoom.com` 은 KRX 만 — NXT 데이터 수집은 운영 도메인 필수

### Decided
- **범위**: MVP 8 + 보조 6 + 분석/순위 11 = **25 endpoint** (ETF/ELW/금현물/주문/실시간웹소켓 제외)
- **스택**: backend_py 동일 (FastAPI + SQLAlchemy 2.0 async + uv + Alembic + structlog + Fernet + APScheduler)
- **코드 의존성**: `backend_py.app.*` 0 import — 패턴(structlog 마스킹 / Fernet / Hexagonal) 만 복제
- **DB**: 별도 schema `kiwoom`, KRX/NXT 물리 분리 테이블 (`stock_price_krx`, `stock_price_nxt`)
- **SOR `_AL`**: 정기 수집 안 함, 비교 PoC 만
- **자격증명**: Fernet 암호화 후 `kiwoom_credential` BYTEA 저장 (운영 키는 DB only, Settings 미사용)
- **RPS**: 초당 4회 + 250ms 인터벌 (공식 5회 안전 마진)

### Uncommitted
본 세션은 커밋 없음. untracked 항목:
- `src/backend_kiwoom/` (디렉토리 전체 — 4 파일)
- `src/backend_py/SPEC.md`
- `src/backend_py/키움 REST API 문서.xlsx` (참조용, gitignore 검토 필요)

기존 untracked (이전 세션 v1.2 작업):
- `src/frontend/src/components/charts/IndicatorParametersDrawer.tsx` 외 2건 — Cp 2β 진행 중

---

## [2026-04-24] feat(v1.2): Cp 2α — `useIndicatorPreferences` v2 스키마 + 파라미터 end-to-end 배선 (`45837fd`)

v1.2 체크포인트 2α. 훅 전면 재작성 + v1→v2 자동 마이그레이션 + MA4/RSI/MACD/BB 파라미터를 사용자 편집 대상으로 전환. 편집 UI 는 Cp 2β 에서 별도 커밋으로.

### Added
- `IndicatorPrefs` v2 스키마 — `{ schema_version: 2, toggles, params }` 구조
- `IndicatorParams` — `ma: [n,n,n,n]`, `rsi: {period, overbought, oversold}`, `macd: {fast, slow, signal}`, `bb: {period, k}`
- `isValidPrefsV2` 수동 엄격 가드 (중첩 필드 전체 검증 — RSI overbought>oversold, MACD fast<slow 교차검증 포함)
- `migrateV1ToV2` — v1 flat 7-boolean → v2 toggles + DEFAULT_PARAMS
- `__resetForTesting__` — 모듈 스코프 캐시/subscriber 리셋
- `src/frontend/src/lib/hooks/useIndicatorPreferences.test.ts` — 35 케이스, 훅 coverage **100%/100%/100%/100%**
- 페이지 모듈 스코프 상수 `MA_COLORS` / `MA_TOGGLE_KEYS`

### Changed
- 훅 API: `{ prefs, setPref }` → `{ prefs, setToggle, setParams, setPrefs }`
  - `setPrefs` 는 v1.2 Cp 3 DB 어댑터가 서버 페이로드 일괄 주입에 사용
- snapshot 캐시 키를 `${source}:${raw}` 조합으로 확장 (v2 우선, v1 fallback)
- `IndicatorTogglePanel` props `{ prefs, onToggle }` → `{ toggles, onToggle }`
- `PriceAreaChart` `RSISeriesProp` 에 `overbought` / `oversold` 추가, 가이드 라인 70/30 하드코딩 제거
- `StockChartAccessibilityTable` props `ma5/ma20` 고정 → `{ ma1, ma2 }` + `rsiPeriod` 동적 레이블 (`MA{window}`, `RSI({period})`)
- `stocks/[code]/page.tsx` — 하드코딩 파라미터 (5/20/60/120, 14, 12/26/9, 20/2) 전면 제거, `prefs.params.*` 사용
- `vitest.config.ts` — coverage include 에 `src/lib/hooks/**/*.ts` 추가, `useIndicatorPreferences.ts` 100% 임계 활성

### Verified
- npm test: 8 files / **94 tests PASS**
- npm run test:ci: 전체 Lines 100%, indicators+hooks 임계 전부 통과
- npm run type-check: clean
- npm run build: Next 16 Turbopack 성공, 7 static pages 무회귀
- typescript-reviewer: APPROVE (CRITICAL/HIGH 0, MEDIUM 2 반영)

### Migration Notes
- v1 키 `stock-chart-indicators:v1` 는 첫 `setToggle`/`setParams` 시 v2 저장 후 자동 삭제 (1 회성 정리)
- 기존 사용자 토글 상태 전부 유지, 파라미터는 DEFAULT_PARAMS 로 초기화 (v1 에는 파라미터 개념 자체가 없었음)

---

## [2026-04-24] feat(v1.2): Cp 1 — Bollinger Bands 유틸 + 차트 overlay + 토글 통합 (`8ece65c`)

v1.2 체크포인트 1. BB 지표 라인업 완성. lightweight-charts v5 의 band 채움 미지원 확인 (AreaSeries/BaselineSeries 는 baseline-relative 단일 그라데이션) → v1.2 MVP 는 3 LineSeries only, 채움은 v1.3 custom primitive 과제로 이월.

### Added
- `src/frontend/src/lib/indicators/bb.ts` — Bollinger Bands `(values, period=20, k=2)` → `{upper, middle, lower}[]`
  - SMA 중앙선 + 표본 표준편차(Bessel 보정) O(n) 슬라이딩 윈도우
  - sum / sumSq 롤링, variance 음수 방어 클램프
  - KRW 스케일 정밀도 한계 주석 (리뷰 MEDIUM 1 반영)
- `src/frontend/src/lib/indicators/bb.test.ts` — 12 케이스 (입력 검증 / 경계 / known sample / 대칭성 / k 선형 스케일 / 슬라이딩 vs slice 일치)
- `PriceAreaChart.tsx` `BBSeriesProp` export + 가격 페인 오버레이 useEffect (MA 패턴 상속, 3 LineSeries)
- `IndicatorTogglePanel.tsx` `bb` 토글 (label 'BB(20,2)', 색 `#6FD4D4`)
- `useIndicatorPreferences` `IndicatorPrefs` 에 `bb: boolean`, `DEFAULT_PREFS.bb = false`
- `stocks/[code]/page.tsx` `bbSeries` useMemo + `!prefs.bb || closes.length === 0` 단락 (리뷰 MEDIUM 3 반영)

### Changed
- 스켈레톤 토글 placeholder 수 `7 → 8` (BB 반영, 리뷰 INFO 4)
- middle 선만 dashed (`lineStyle: 2`) — upper/lower(실선) 과 시각 구분

### Verified
- npm test: 7 files / 51 tests PASS (+12 bb tests)
- npm run test:ci: indicators 99.37%/97.56%/100%/100% (임계 90% 유지)
- npm run type-check: clean
- npm run build: 성공, 7 static pages 무회귀
- typescript-reviewer: APPROVE (CRITICAL/HIGH 0)

### Decided
- **lightweight-charts v5 band 채움 미지원**: typings.d.ts PoC 로 확인 (AreaSeries/BaselineSeries 는 baseline-relative 단일 그라데이션만). v1.2 MVP 는 3 LineSeries, 채움은 v1.3 custom primitive 로 이월
- **v1 localStorage 호환**: bb 필드 없으면 `coerceFromStored` 가 `false` 로 보정 → 기존 사용자 토글 유실 0

---

## [2026-04-24] feat(v1.2): Discovery + Cp 0 Vitest 하네스 — 테스트 기반 선행 (`e13e0e2`)

v1.2 착수. 옵션 β (biz+pm+judge) 로 Discovery 6 산출물 생성 (Judge PASS 9.05). 사전 스파이크로 실스택 교정 — 카카오 OAuth 미구현 확인, NotificationPreference 싱글톤 id=1 패턴 상속 결정. 이어서 Cp 0 (Vitest 하네스) 선행 구축.

### Added (Discovery v1.2)
- `pipeline/artifacts/00-input/user-request-v1.2-chart-params-db-vitest.md` — BB + 파라미터 편집 UI + DB 영속화 + Vitest 하네스
- `pipeline/artifacts/01-requirements/requirements-v1.2-chart-params-db-vitest.md` — US 12 / FR 16 / NFR 10 / Risk 7
- `pipeline/artifacts/02-prd/prd-v1.2-chart-params-db-vitest.md`
- `pipeline/artifacts/02-prd/roadmap-v1.2-chart-params-db-vitest.md` (v1.1 대비 delta 포함)
- `pipeline/artifacts/02-prd/sprint-plan-v1.2-chart-params-db-vitest.md` — 체크포인트 5 개 (Cp 0~4), 공수 10.5d
- `pipeline/decisions/discovery-v1.2-judge.md` — PASS 9.05 / 10
- `pipeline/state/current-state.json` `iterations.v1.2-chart-params-db-vitest` 블록 신설

### Added (Cp 0 — Vitest 하네스)
- `src/frontend/vitest.config.ts` — jsdom + `@vitejs/plugin-react` + `vite-tsconfig-paths` + coverage v8
- `src/frontend/src/test-setup.ts` — `@testing-library/jest-dom/vitest` matchers + MSW 라이프사이클
- `src/frontend/src/test/msw/{handlers,server,msw-smoke.test}.ts` — `/api/admin/indicator-preferences` GET/PUT + errorHandlers (400/500/network)
- `src/frontend/src/lib/indicators/{sma,rsi,macd,aggregate,index}.test.ts` — 39 케이스
- `package.json` scripts: `test`, `test:ci`
- devDep 10 종: vitest@^4, @vitejs/plugin-react@^6, @testing-library/{react,dom,jest-dom,user-event}, jsdom@^29, msw@^2, @vitest/coverage-v8@^4, vite-tsconfig-paths@^6

### Verified
- npm test: 6 files / 39 tests PASS (701ms)
- npm run test:ci: indicators 99.25%/97.05%/100%/100% (임계 90% 통과)
- npm run type-check: clean
- npm run build: Next 16 Turbopack 성공
- typescript-reviewer: APPROVE (CRITICAL/HIGH 0, LOW 1 반영)

### Decided
- **auth 체계 교정**: CLAUDE.md 의 "카카오 OAuth 2.0" 언급은 로드맵 레벨 — 실구현은 미완. 백엔드는 `X-API-Key` (ADMIN_API_KEY) 어드민 단일 인증. v1.2 DB 영속화는 `NotificationPreference` 싱글톤 id=1 패턴 상속
- **Judge 권고 #1 (Cp 2 분리)**: 3-split (2a/2b/2c) 원안 대신 **2-split** 채택 — 2α (훅 v2 + 배선) / 2β (편집 UI). 2a 단독 상태가 dead code 가 되는 문제 회피

---

## [2026-04-23] fix(chart): `useIndicatorPreferences` 무한 루프 해소 — snapshot 캐싱 (`669d9e8`)

### Fixed
- `useSyncExternalStore` 의 `getSnapshot()` 이 매 호출마다 `JSON.parse` 로 새 객체를 반환 → `Object.is` 비교가 항상 실패 → **React #185 Maximum update depth exceeded** 무한 루프
- 모듈 스코프 `cachedRaw` / `cachedSnapshot` 을 두고 localStorage raw 문자열이 동일하면 이전 스냅샷 객체를 그대로 반환하는 표준 패턴 적용

### Verified
- `yarn tsc --noEmit` + `yarn lint` 통과
- docker compose up -d --build frontend 로 컨테이너 recreate (image sha `a489402037b6...`)
- 브라우저 hard reload 후 런타임 에러 없음 확인

---

## [2026-04-23] feat(chart): v1.1 Sprint B 체크포인트 4 — sr-only 테이블 + aria 정리 + Sprint B 완주

### Added
- `src/frontend/src/components/charts/StockChartAccessibilityTable.tsx` — sr-only 대체 테이블
  - 최근 30 거래일 OHLCV + MA5 / MA20 / RSI(14) / MACD 10 컬럼
  - `aria-label` + `<caption>` + `scope="col"` / `scope="row"` 로 SR 네비게이션 지원

### Changed
- `PriceAreaChart.tsx` — container div `aria-hidden="true"` → `role="img" + aria-label` (aria-hidden 내부 focusable 룰 충돌 해소)
- `page.tsx` — back 버튼 `text-[#6B7A90]` → `text-[#7A8699]` (AA 4.43:1 → 4.86:1)
- `page.tsx` — loading skeleton 을 실제 DOM 과 정확히 일치 (기간 버튼 3 개, 토글 패널 placeholder 7 개, 차트 카드 outer+inner 구조)
- `globals.css` — `.aurora` / `.aurora .blob` 에 `contain: layout paint` 추가, `aurora-drift-*` keyframes 에서 `scale()` 제거 (Chrome CLS 오검출 회피 시도)

### Verified
- `yarn tsc --noEmit` + `yarn lint` 통과
- `/stocks/005930` — Perf **80** / **A11y 100** / BP **100** / SEO **100**

### Known Issue (후속)
- **Perf 95 → 80 회귀** — aurora blob transform 애니메이션이 Chrome Lighthouse 에서 CLS culprit 으로 계상 (실측 `div.blob` 단일 소스로 CLS 0.393). 여러 차례 완화 시도 (`contain: layout paint` × 2, keyframe scale 제거) 효과 미미. Sprint B 기능 자체는 무회귀 (A11y/BP/SEO 모두 100). **실기기 체감 성능 확인 후 aurora 애니메이션 정적화 여부 별도 디자인 PR** 권장.

### Sprint B 완주 요약
- B0 봉 주기 (1D/1W/1M) + OHLC 재집계 ✅
- B1 + B2 RSI(14) / MACD(12,26,9) 유틸 ✅
- B3 + B4 RSI/MACD pane (동적 생성·제거) ✅
- B5 IndicatorTogglePanel ✅
- B6 useIndicatorPreferences (useSyncExternalStore + localStorage) ✅
- B7 StockChartAccessibilityTable (sr-only) ✅
- B8 모바일 breakpoint 기본값 차등 — DEFAULT_PREFS 자체가 이미 "MA5/MA20/Volume 만 ON" 이라 별도 breakpoint 로직 불필요 ✅
- B9 + B10 회귀 + QA ✅ (Perf 회귀 1 건 Known Issue)
- 시그널 마커 grade 색 구분 (사용자 요청) ✅

---

## [2026-04-23] feat(chart): v1.1 Sprint B 체크포인트 3 — 토글 UI + RSI/MACD pane + localStorage

### Added
- `src/lib/hooks/useIndicatorPreferences.ts` — SSR-safe 로컬 저장 훅
  - `useSyncExternalStore` 기반 (Next 16 `react-hooks/set-state-in-effect` 규칙 회피)
  - 인메모리 subscribers 로 같은 탭 내 변경 즉시 반영
  - 수동 타입 가드 (`isValidPrefs`) — zod 의존성 없음
  - 기본값: MA5/MA20/Volume ON, MA60/MA120/RSI/MACD OFF
- `src/components/charts/IndicatorTogglePanel.tsx` — 7 개 토글 (MA4 + 거래량 + RSI + MACD)
  - `aria-pressed` + `focus-visible:ring` + 색칩 + 키보드 접근

### Changed
- `PriceAreaChart.tsx` — RSI/MACD pane 동적 생성·제거 로직
  - `chart.removePane(paneIndex())` 로 토글 OFF 시 pane 완전 제거 (공간 차지 없음)
  - Volume pane 도 동일 패턴으로 통일 (기존 `setData([])` → `removePane`)
  - RSI: 과매수 70 / 과매도 30 가이드 라인 점선
  - MACD: MACD 라인 + Signal 라인 + Histogram (양/음 색 분리)
  - 마커 grade 색 테이블 (체크포인트 1 에서 추가) 유지
- `page.tsx` — `useIndicatorPreferences` wire, `IndicatorTogglePanel` 삽입, `rsiSeries` / `macdSeries` props 전달
  - `closes` 별도 useMemo 로 MA/RSI/MACD 공통 입력 공유
  - `volumeProp` 은 `prefs.volume` 에 따라 전달/미전달

### Verified
- `yarn tsc --noEmit` + `yarn lint` 통과
- `/stocks/005930` Lighthouse Perf **96** (↑1) / A11y 100 / BP 100 / SEO 100
  - 기본 prefs 에서 MA60/120/RSI/MACD OFF → 초기 시리즈 감소로 Perf 개선

### Next (Sprint B 잔여)
- 체크포인트 4 — sr-only 대체 테이블 + 모바일 breakpoint 토글 기본 차등 + 최종 회귀 + HANDOFF 업데이트

---

## [2026-04-23] feat(indicators): v1.1 Sprint B 체크포인트 2 — RSI(14) + MACD(12,26,9) 유틸

### Added
- `src/lib/indicators/rsi.ts` — Wilder's RSI
  - 초기 period 구간 SMA seed → 이후 `(prev*(p-1) + curr)/p` 스무딩
  - `avgLoss === 0` 구간은 RSI = 100
- `src/lib/indicators/macd.ts` — MACD line + Signal line + Histogram
  - `emaSeriesSmaSeed` helper (SMA seed → EMA 전개)
  - 파라미터 기본: fast=12, slow=26, signal=9

> 차트 pane/UI wiring 은 체크포인트 3 (토글 UI + localStorage 영속화) 에서 함께 처리.
> 지금은 순수 유틸 모듈만 추가 → 번들 영향 ~0 (미사용).

### Verified
- `yarn tsc --noEmit` + `yarn lint` 통과

---

## [2026-04-23] feat(chart): v1.1 Sprint B 체크포인트 1 — 봉 주기(1D/1W/1M) + 시그널 grade 색 구분

### Changed
- 기간 버튼 의미 재정의: 표시 기간(1M/3M/6M/1Y) → **봉 주기(1D 일봉 / 1W 주봉 / 1M 월봉)**
  - `page.tsx` `PeriodKey` `'day'|'week'|'month'`, fetch monthsFetch 3/12/36
  - `chartData`/`volumeData` 는 집계 결과에서 파생 (일봉일 때 집계 없음)
- 시그널 마커 색 grade 별 차등: 기존 전부 `#FFCC00` → **A 노랑 / B 녹색 / C 오렌지 / D 회색**
  - `enums.py` `SignalGrade.from_score` 기준 동기 (A ≥ 80, B ≥ 60, C ≥ 40, D < 40)

### Added
- `src/lib/indicators/aggregate.ts` — `aggregateWeekly` / `aggregateMonthly`
  - 집계 규칙: `first.open`, `max.high`, `min.low`, `last.close`, `sum.volume`, `date = group 시작일`
  - 주봉 키는 ISO 8601 week, 월봉 키는 `YYYY-MM`

### Verified
- `yarn tsc --noEmit` + `yarn lint` 통과 (warning 0)
- `/stocks/005930` Lighthouse Perf 95 / A11y 100 / BP 100 / SEO 100 (무회귀)

### Next (Sprint B 잔여)
- 체크포인트 2 — RSI(14) + MACD(12,26,9) 페인
- 체크포인트 3 — IndicatorTogglePanel + localStorage 영속화
- 체크포인트 4 — sr-only 테이블 + 모바일 breakpoint + 회귀

---

## [2026-04-23] feat(chart): v1.1 Sprint A — 캔들 + MA + Volume + 줌/팬 + OHLCV 툴팁

v1.1 `/stocks/[code]` 차트 고도화 Sprint A (A1~A8) 일괄 완료. `/plan` 으로 Discovery 수행 후 A1 PoC 로 2대 리스크 해소 → A2~A7 구현 → A8 회귀 검증까지 한 세션 완주.

### Pipeline 산출물 (신규)
- `pipeline/artifacts/00-input/user-request-v1.1-chart-upgrade.md` — (C) 풀 스택 범위 확정
- `pipeline/artifacts/01-requirements/requirements-v1.1-chart-upgrade.md` — US 12 + FR 12 + NFR 8 + Risk 5
- `pipeline/artifacts/02-prd/prd-v1.1-chart-upgrade.md` — PRD 8 섹션
- `pipeline/artifacts/02-prd/roadmap-v1.1-chart-upgrade.md` — 3/6/12 개월
- `pipeline/artifacts/02-prd/sprint-plan-v1.1-chart-upgrade.md` — RICE + 2 Sprint 분해
- `pipeline/decisions/discovery-v1.1-judge.md` — Judge **PASS 9.20**

### PoC 결과 (RISK 해소)
- **RISK-C01** (KRX 실데이터) — 005930 753 거래일 100% OHLC + 최근 90일 62/62 확인 (2026-04-20 1건만 0값 → 방어 필터)
- **RISK-C02** (v5 multi-pane API) — `typings.d.ts:1689,1932` 의 `addPane` + `IPane.setHeight` 확인, JSDoc 3-pane 예시 (`:2002-2004`)

### Added
- `src/frontend/src/lib/indicators/sma.ts` — Simple Moving Average, O(n) 슬라이딩 윈도우, NaN 구간 자동 생략
- `src/frontend/src/lib/indicators/index.ts` — barrel export

### Changed
- `src/frontend/src/components/charts/PriceAreaChart.tsx` — 전면 재구성
  - **A2** AreaSeries → **CandlestickSeries** (한국 증시 색: 상승 `#FF4D6A` / 하락 `#6395FF`)
  - **A4** MA(5/20/60/120) LineSeries 4개 오버레이 (색 팔레트: 노랑/오렌지/녹색/보라), window 별 `Map` 관리
  - **A5** Volume HistogramSeries — `chart.addPane()` + `IPane.setHeight(96px)`, 반투명 상승/하락 색
  - **A6** 줌/팬 활성화 (`handleScroll: true`, `handleScale: true`)
  - **A7** OHLCV 툴팁 — `subscribeCrosshairMove` + React state 오버레이 (우상단, `pointer-events-none`, `aria-live="polite"`)
  - 시그널 마커 `inBar → aboveBar` (캔들 바디와 겹치지 않도록), 색 `#FFCC00`
- `src/frontend/src/app/stocks/[code]/page.tsx` — `chartData`/`volumeData` 단일 패스 병합 계산 (0값/null 레코드 사전 제거), MA 4개 lines useMemo 추가
- `docs/lighthouse-scores.md` — Sprint A 완료 측정 prepend

### Verified
- `yarn tsc --noEmit` + `yarn lint` 통과 (warning 0)
- prod docker 스택 재빌드 + caddy self-signed HTTPS 경유 측정
- `/stocks/005930` — **Perf 95 / A11y 100 / BP 100 / SEO 100** (무회귀, Sprint A 전체 투입에도 동일 스코어)

### Scope Kept (Sprint B 이월)
- RSI(14) / MACD(12,26,9) 페인
- 지표 on/off 토글 UI (`IndicatorTogglePanel`)
- localStorage 영속화 (`useIndicatorPreferences`)
- sr-only 접근성 테이블
- 모바일 breakpoint 기본 토글 집합 차등

### Known — 수동 확인 필요
- 모바일 실기기 (iPhone SE / Galaxy S8) 터치 핀치 줌/팬 UX 확인

---

## [2026-04-23] fix(scripts): `docker-rebuild.sh` prod 모드 `--env-file` 자동 주입

A11y 재측정을 위해 `./scripts/docker-rebuild.sh prod` 실행 시 compose 변수 interpolation 이 안 되어 POSTGRES/ADMIN 등이 blank 로 기동되고 backend 가 unhealthy 로 실패하던 버그 수정.

- prod 모드 기본값 `ENV_FILE=.env.prod` 도입 (override: `ENV_FILE=<path>` 환경변수)
- `.env.prod` 미존재 시 prod 에서는 치명 에러로 fail-loud
- dev 모드는 `.env` 가 있으면 사용, 없으면 compose 파일 내부 `env_file` 지시어에 위임
- `docker compose` 호출 4곳(down / build / build service / up) 모두 `--env-file` 자동 전달

`bash -n` 문법 OK. 실제 검증은 직전 수동 명령(동일 로직) 성공으로 대체.

---

## [2026-04-23] fix(frontend): /stocks/005930 색 대비 잔존 2건 수정 — **A11y 100 달성**

직전 커밋(`4e660a9`)으로 `#3D4A5C` 위반을 해소한 뒤 Lighthouse 재측정에서 같은 color-contrast 감사에 묶여있던 2건이 추가로 드러남. 스팟 수정으로 `/stocks/005930` A11y 95 → **100** 달성.

### Changed
- `src/frontend/src/app/stocks/[code]/page.tsx:135` — 전일비 중립값 색 `'#6B7A90'` → `'#7A8699'` (4.1:1 → 4.86:1)
- `src/frontend/src/app/stocks/[code]/page.tsx:207` — 기간 선택 active 버튼 `text-white` → `text-[#0B0E11] font-semibold` (2.88:1 → 7.27:1)

### Verified
- `yarn tsc --noEmit` + `yarn lint` 통과
- prod docker 스택 (caddy self-signed HTTPS) 재빌드 후 Lighthouse 재측정:
  - `/stocks/005930` — Perf **95** · A11y **100** · BP **100** · SEO **100**

### Scope Kept
- 글로벌 accent `#6395FF` 및 secondary `#6B7A90` 토큰은 건드리지 않음 — 다른 페이지 영향 0
- 스팟 수정 1개 파일 2 라인

---

## [2026-04-23] fix(frontend): WCAG AA 색 대비 — muted 토큰 `#3D4A5C → #7A8699` 전역 교체

Lighthouse A11y 감사에서 `/stocks/005930` 헤더 카드의 `#3D4A5C` on `#131720` 색 대비가 **1.99:1** (WCAG AA 기준 4.5:1 미달) 로 측정되어 A11y 96 → 95 감점. 해당 색상이 frontend 전역에 하드코딩되어 있어 디자인 토큰 수준으로 일괄 교체.

### Changed
- `src/frontend/src/app/globals.css` — `--color-text-muted: #3D4A5C` → `#7A8699`
- TSX 12개 파일의 `text-[#3D4A5C]` / `placeholder-[#3D4A5C]` → `text-[#7A8699]` / `placeholder-[#7A8699]` 일괄 치환 (총 41건)
  - `app/page.tsx`, `app/layout.tsx`, `app/stocks/[code]/page.tsx`, `app/backtest/page.tsx`, `app/portfolio/page.tsx`, `app/portfolio/[accountId]/alignment/page.tsx`, `app/reports/[stockCode]/page.tsx`, `app/settings/page.tsx`, `components/NavHeader.tsx`, `components/features/SignalCard.tsx`, `components/features/ExcelImportPanel.tsx`, `components/features/RealAccountSection.tsx`

### Kept (의도적 유지)
- `app/settings/page.tsx:164` — `bg-[#3D4A5C]` 토글 OFF 상태 배경 (텍스트 아님)
- `components/charts/PriceAreaChart.tsx:90-91` — TradingView 차트 크로스헤어 gridline (장식)

### Contrast
- 이전: `#3D4A5C` on `#131720` = **1.99:1** (AA 4.5:1 ✗)
- 이후: `#7A8699` on `#131720` = **4.86:1** (AA 4.5:1 ✓, 여유 ~0.36)
- Hue 유지 (블루-그레이 HSL ~215°)

### Verified
- `yarn tsc --noEmit` 통과
- `yarn lint` 통과
- typescript-reviewer 에이전트 리뷰 CRITICAL/HIGH 0건

### Known Trade-off
- 계층 역전: 새 muted `#7A8699`가 기존 secondary `#6B7A90` 보다 밝음. `#131720` 배경에서 WCAG AA 통과하려면 L≥~0.21 필요 → muted 가 secondary 보다 밝은 구조 불가피. secondary 는 현재 4.11:1 로 경계선 미달이지만 본 PR 범위 외 (별도 디자인 결정 필요).

### Pending
- Lighthouse 재측정으로 `/stocks/005930` A11y 95 → **96** 복귀 확인 필요 (`./scripts/lighthouse-mobile.sh`).

---

## [2026-04-23] chore(scripts): docker 빌드/정리 자동화 스크립트 추가 (세션 마감 커밋 예정)

docker compose 재빌드를 반복할 때 누적되는 dangling 이미지/BuildKit 캐시를 **매번 자동 회수**하는 스크립트 한 쌍 추가. 볼륨(DB/Caddy 인증서)은 의도적으로 건드리지 않음.

### Added
- `scripts/docker-rebuild.sh` (0755) — compose up 래퍼. [1] down (볼륨 보존) → [2] build → [3] dangling 이미지 제거 + BuildKit 캐시 `KEEP_CACHE_GB`(기본 5GB) 상한 유지 → [4] up -d. `dev`/`prod` 모드 + 특정 서비스 인자 지원.
- `scripts/docker-clean.sh` (0755) — 주기적 수동 정리. 기본 안전 모드(dangling 만), `--deep` 시 참조 없는 모든 이미지까지 제거 (인터랙티브 확인).

### Verified
- dev 테스트: `./scripts/docker-rebuild.sh dev` → 4단계 모두 성공. `signal-db` healthy, `pg_isready` OK, `ted-startup_signal-data` 볼륨 보존 확인.
- 디스크 회수 실측: **Build Cache 11.73GB → 6.31GB (−5.42GB)**, dangling 이미지 8개 제거.
- `bash -n` 문법 검증 ✅

### Decisions
- **`--volumes` 플래그 의도적 제외**: DB 데이터 / Caddy 인증서 보호. `docker-clean.sh` 도 동일 원칙.
- **BuildKit 캐시는 `prune` 이 아닌 `--keep-storage` 로 관리**: 캐시 재사용 이득을 잃지 않으면서 상한만 유지. `KEEP_CACHE_GB` 환경변수로 조절.
- **dev/prod compose 파일 인자로 분리**: `docker-compose.yml`(로컬 DB 단일)과 `docker-compose.prod.yml`(4 서비스 스택) 경계 명확.

---

## [2026-04-23] chore(frontend): recharts 의존성 제거 + Gate 3 최종 재측정 (`507bd54`, PR #41, 머지 완료)

TradingView 전환 3-PR 시리즈의 **마지막**. PR #39/#40 로 recharts 사용처가 0 이 된 상태에서 의존성 자체를 완전 제거 + dead code 정리 + Gate 3 전 페이지 최종 재측정으로 7/7 확정.

### Removed
- `recharts@^3.8.1` 의존성 — `npm uninstall recharts`. package.json + package-lock.json 에서 recharts + 간접 deps 전부 삭제 (-385 줄).
- `src/frontend/src/lib/hooks/useMediaQuery.ts` — Phase D 에서 차트 aspect 분기용으로 도입됐으나 CSS aspect-ratio 로 대체돼 사용처 0.

### Changed
- `docs/lighthouse-scores.md` — "TradingView 차트 전환 완료 후" 최종 7페이지 표 섹션 + PR #39/#40/#41 해결 이력 3건 + 변경 이력 3행 추가.

### Verified
- `grep -rn recharts src tests` → 매칭 0 · `grep -rn useMediaQuery src tests` → 매칭 0
- `npm run lint` ✅ / `npm run type-check` ✅
- docker 재빌드 + healthcheck 통과
- Lighthouse 전 7페이지: /:99/96/100/100, /portfolio:94/97/100/100, /stocks/005930:**95**/95/100/100, /reports/005930:99/96/100/100, /portfolio/1/alignment:100/100/100/100, /backtest:**99**/100/100/100, /settings:99/96/100/100 — **7/7 통과**

### Decisions
- **번들 감소 추정 ~150KB gzipped**: recharts 제거(~200KB gzipped) − lightweight-charts 추가(~50KB gzipped). pure SVG GroupedBarChart 는 의존성 순증 0.
- **useMediaQuery 삭제**: React 19 `useSyncExternalStore` 기반 SSR-safe 훅이었으나 CSS aspect-ratio 로 충분. `react-hooks/refs` 규칙 우려도 함께 해소.

---

## [2026-04-23] feat(frontend): /backtest 차트 recharts → pure SVG GroupedBarChart (`0ff61f7`, PR #40, 머지 완료)

TradingView 전환 시리즈 2/3. `/backtest` 는 카테고리형 그룹 막대 차트라 lightweight-charts(시계열 전용) 로 매핑 불가 → pure SVG + Tailwind 로 자작해 외부 의존성 순증 0.

### Added
- `src/frontend/src/components/charts/GroupedBarChart.tsx` — pure SVG 그룹 막대 차트 (~275 줄). `ResizeObserver` 로 부모 픽셀 측정 → 정확한 viewBox 렌더링. `niceStep` + `buildTicks` 자동 y축 눈금. Legend 는 라벨 길이 기반 간격. hover 시 값 라벨 표시 (경계 clamp). **sr-only `<table>` 백업** 으로 스크린리더 접근성 보장 (SVG 는 `aria-hidden="true"`).

### Changed
- `src/frontend/src/app/backtest/page.tsx` — recharts 전체 제거 (BarChart/Bar/XAxis/YAxis/CartesianGrid/Tooltip/Legend/ResponsiveContainer). `useMediaQuery` 제거 후 `aspect-[1.4/1] sm:aspect-[2.2/1]` CSS 로 대체. chartData → `CategoryRow[]` 구조 재구성 + useMemo. `RETURN_SERIES` 상수 + `returnFormatter` 분리.

### Verified
- `npm run lint` ✅ / `npm run type-check` ✅
- Lighthouse 재측정 (`/backtest`): Perf 97 → **99**, A11y **100**, BP 100, SEO 100, LCP 1899ms (Good), TBT 38ms (Good), CLS 0.058 (Good), Console errors 0

### Decisions
- **B3 (pure SVG 자작) 채택**: 입력 규모 작음 (전략 3 × 5/10/20일 = 9 막대). chart.js ~230KB 순증 불필요. SVG 150줄 내 마무리 가능.
- **sr-only 테이블 백업**: SVG `<title>` 요소는 VoiceOver/NVDA 호환성 불일치 → 시각 SVG 와 의미 `<table>` 분리, SVG 는 `aria-hidden`.
- **호버 라벨 경계 clamp**: 가장자리 bar 의 값 라벨이 차트 영역 밖으로 흘러나가지 않도록 `Math.min/max` 로 plot 경계 제한.

---

## [2026-04-23] feat(frontend): /stocks/[code] 차트 recharts → TradingView Lightweight Charts v5 전환 (`6957e00`, PR #39, 머지 완료)

모바일 반응형 마감 후속 — recharts 를 TradingView Lightweight Charts v5 (Apache-2.0) 로 전환하는 3-PR 시리즈의 첫 번째.

### Added
- `src/frontend/src/components/charts/PriceAreaChart.tsx` (~140 줄) — 공통 Area 차트 컴포넌트. lightweight-charts v5 신 API (`createChart` + `chart.addSeries(AreaSeries, ...)` + `createSeriesMarkers(series, ...)` plugin). 다크 테마 프리셋 (#6395FF line + rgba(99,149,255,0.2) area fill). ResizeObserver 반응형. 입력 date 포맷 사전 검증 (`toTime()` 헬퍼). `clientHeight=0` 방어 fallback.
- `lightweight-charts@^5.1.0` 의존성 (npm install, Apache-2.0, TradingView Inc.).

### Changed
- `src/frontend/src/app/stocks/[code]/page.tsx`
  - recharts 전체 제거 (ComposedChart/Area/ReferenceDot/ResponsiveContainer/XAxis/YAxis/Tooltip/Legend/CartesianGrid).
  - `dynamic(() => import('@/components/charts/PriceAreaChart'), { ssr: false })` 로 SSR 제외 (Next 16 Client Component 내부 규칙 준수).
  - `chartData` 에서 `trading_date.slice(5)` 제거 → 'YYYY-MM-DD' 유지.
  - `signalMarkers` useMemo 신설 — signal_date ↔ close_price 매핑, price 누락 skip.
  - `useMemo` 호출을 early return 앞으로 이동 → rules-of-hooks 준수.

### Verified
- `npm run lint` / `npm run type-check` ✅
- Lighthouse 재측정 (`/stocks/005930`): Perf 92 → **95**, LCP 2557 → **1902ms** (Good 구간), TBT 119 → **44ms** (−63%), Speed Index 1128 → 964ms, CLS 0.123 유지, Console errors 0. A11y 96 → 95 는 기존 헤더 카드 color-contrast 이슈 (별건).

### Decisions
- **v5 신 API 채택**: `addSeries` + `createSeriesMarkers` plugin. v4 `addAreaSeries` / `series.setMarkers` 는 deprecated.
- **SSR 제외 필수**: lightweight-charts 는 `window`/`canvas` 의존. Next 16 은 Client Component 내부에서만 `{ ssr: false }` 허용 (확인).
- **Setup + update effect 분리**: Strict Mode remount 시 update effect 가 deps 보존으로 재실행돼 새 chart 에 데이터 재주입. 별도 ref 동기화 불필요.
- **입력 date 런타임 검증**: `/^\d{4}-\d{2}-\d{2}$/` 사전 검증 → 백엔드 계약 이탈 시 조용한 실패 대신 명시적 throw.
- **TradingView 로고 자동 표시**: 우측 하단 배지 유지 (Apache-2.0 + TradingView 상표 정책).

---

## [2026-04-23] fix(frontend): /stocks/005930 CLS 0.36→0.12 · Perf 80→92 — footer shift 제거 + 차트 aspect CSS 이관 (`037f675`, PR #38, 머지 완료)

> **PR 번호 정정**: 원 PR #36 은 base 브랜치 삭제로 auto-closed 되어 동일 내용을 master 기반으로 재생성 — **PR #38** 로 머지됨 (`037f675`).

Gate 3 1차 측정(PR #35)에서 유일하게 목표 미달(Perf 80 < 85)이던 `/stocks/005930` 의 실제 원인 진단 + 수정.

### Fixed
- `src/frontend/src/app/stocks/[code]/page.tsx` — CLS 0.362 → 0.123, Perf 80 → 92
  - `useMediaQuery` 제거 → 차트 aspect 를 Tailwind CSS (`aspect-[1.4/1] sm:aspect-[2/1]`) 로 이관. recharts `ResponsiveContainer` 는 `width="100%" height="100%"` 로 부모 CSS aspect-ratio 상속. hydration 시점 재배치 소거
  - loading/error/loaded 세 상태의 `<main>` 에 `min-h-[calc(100dvh-8rem)]` 추가 → footer 를 뷰포트 하단에 고정. 스켈레톤 ↔ 실콘텐츠 전환 시 footer shift 0 건
  - 스켈레톤을 실제 구조(back 버튼 + 2 카드 + 기간 선택기 + 차트) 에 맞춰 세분화 → 세로 높이 격차 축소

### Changed
- `docs/lighthouse-scores.md` — 1차 측정 결과 표의 `/stocks/005930` 행 갱신 (80 → 92, CLS 주석 추가) + "해결 이력" 섹션 신설로 "실패 항목" → 사후 분석 전환

### Verified
- `yarn lint --quiet` ✅ / `yarn type-check` ✅
- 프론트엔드 단일 서비스 재빌드 (`docker compose up -d --build frontend`) healthcheck 통과
- Lighthouse 재측정: CLS 0.123 / Perf 92 / A11y 96 / BP 100 / SEO 100

### Decisions
- **초기 가설(recharts dynamic import for TBT) 반증**: JSON audit 로 TBT 48ms (이미 "Good") 확인 → 실제 병목은 CLS (layout shift on footer). JSON 분석 없이 상용 가설만으로 움직였으면 잘못된 최적화에 시간 허비했을 것
- **남은 CLS 0.123 (header card 내부) 은 닫음**: Gate 3 목표(Perf 85+) 통과 + "Needs Improvement" 범위(0.1~0.25) → 효용 낮음

---

## [2026-04-23] docs(mobile): Gate 3 Lighthouse 1차 측정 — 7페이지 중 6통과 · /stocks/005930 Perf 80 미달 (`b9a8ec7`, PR #35, 머지 완료)

PR #34 의 Gate 3 증빙 인프라를 이용해 **실제 측정 수행**. prod docker 스택(`docker compose -f docker-compose.prod.yml`) 을 master 최신으로 재빌드 후 caddy self-signed HTTPS 를 통해 7 페이지 측정.

### Added
- `docs/lighthouse-scores.md` §측정 결과 표 — 1차 측정값 기록 (`/` 99/96/100/100, `/portfolio` 94/97/100/100, `/stocks/005930` **80**/96/100/100, `/reports/005930` 99/96/100/100, `/portfolio/1/alignment` 100/100/100/100, `/backtest` 97/100/100/100, `/settings` 99/96/100/100)
- §실패 항목 → `/stocks/005930` Perf 80 의 초기 가설(추후 PR #36 에서 반증) 기록
- §변경 이력 — 1차 측정 기록 추가

### Changed
- `scripts/lighthouse-mobile.sh` — chrome-flags 에 `--ignore-certificate-errors` 추가해 prod docker 스택(caddy self-signed HTTPS) 측정 지원. 헤더 주석에 dev(A) / prod docker(B) 두 모드 사용법 병기
- `docs/lighthouse-scores.md` §측정 절차 — A(dev uvicorn+yarn) / B(prod docker caddy HTTPS) 병기

### Decisions
- **prod docker 스택 경유 측정 채택**: dev 서버(`uvicorn` + `yarn dev`) 대비 실제 배포 구성(캐싱, 번들 분할, caddy 압축) 과 동일해 점수 신뢰도 ↑. 단점인 self-signed 인증서는 chrome-flags 로 해결
- **비로그인 상태 측정 한계 명시**: `/portfolio`, `/settings`, `/portfolio/1/alignment` 는 로그인 리다이렉트 셸 기준으로 측정됨 → 실데이터 상태 재측정은 DevTools 수동 절차(§B) 로 보완 예정

---

## [2026-04-23] docs(mobile): Gate 3 Lighthouse 증빙 인프라 — 자동 스크립트 + 결과 템플릿 (`62a7361`, PR #34, 머지 완료)

모바일 반응형 작업계획서 §8 **Gate 3** (Lighthouse 스코어 증빙) 의 수동 측정 인프라. 실제 스코어는 사용자 로컬 backend+frontend 기동 후 채워짐.

### Added
- `scripts/lighthouse-mobile.sh` (실행권한 0755) — `npx lighthouse` 로 기본 7 페이지(대시보드·포트폴리오·종목·AI리포트·정합도·백테스트·설정) 모바일 프로필 측정
  - 4 카테고리(Perf/A11y/BP/SEO) JSON 파싱 → `lighthouse-reports/summary.md` 에 paste-ready 표 누적
  - 헤드리스 Chrome (`--headless=new --no-sandbox`) 로 CI/로컬 공통 실행
  - 인자로 일부 페이지만 측정 가능 (`./lighthouse-mobile.sh / /backtest`)
- `docs/lighthouse-scores.md` 신규 — 목표치(Perf 85+, A11y/BP 90+) + D1·D3·D4 개선 근거 매핑, 자동 + DevTools 2 경로 절차, 결과 표 빈 칸 초기화, 측정 체크리스트, `@lhci/cli` 자동화 이관 계획

### Changed
- `docs/mobile-responsive-plan.md` §10 단축 → `lighthouse-scores.md` 링크 위임. §9 변경 이력 업데이트.
- `.gitignore` — `lighthouse-reports/` 제외 (JSON/HTML 리포트 커밋 금지)

### Verified
- `bash -n scripts/lighthouse-mobile.sh` ✅
- `npx tsc --noEmit` (frontend 회귀 없음) ✅

### Decisions
- **Gate 3 는 수동 측정으로 닫음**: lhci 자동화는 staging 환경(로그인 세션 시드) 전제라 현재 scope 제외. 수동 절차 표준화 + 스크립트 제공으로 재현성 확보.
- **로그인 세션 이슈 명시**: 자동 스크립트는 비로그인 쉘 페이지만 측정됨. portfolio/settings 정확 측정은 DevTools 로 보완 — scores.md §측정 방법 B 에 명시.

### Known Issues
- 로컬 `credential.helper` 가 `aws codecommit credential-helper` 였음 → GitHub 푸시 실패. repo 단위로 `gh auth git-credential` 로 overlay 해 해결. 전역·다른 AWS 리포엔 영향 없음.

---

## [2026-04-23] test(frontend): 모바일 반응형 Phase E1 — mobile.spec.ts + desktop 스펙 프로필 분리 (`be6a5f8`, PR #32)

모바일 반응형 작업계획서 §4 Phase E1 (Playwright 모바일 스크린샷 회귀) 구현. Phase B/C/D 가 기존 desktop E2E 를 깨지 않도록 selector 프로필 분리도 함께 수행.

### Added
- `src/frontend/tests/e2e/mobile.spec.ts` (+171) — 모바일 프로필(`mobile-safari`/`mobile-chrome`) 전용 8 케이스
  - 대시보드 필터 버튼 `boundingBox.height >= 44` (D1 터치 타깃)
  - NavHeader `v1.0` 배지 `toBeHidden()` (B2)
  - 포트폴리오 `<table>` 숨김 + `data-testid="holding-row"` 카드 LI 태그 렌더 (B1)
  - sync 버튼 `innerText` "모의 sync"/"실계좌 sync" (C4)
  - 종목상세/리포트/정합도/백테스트 수평 스크롤 0 + 스크린샷 수집
  - 설정 페이지 RealAccountSection 카드 세로 배치 box height (B3)
  - 모든 페이지 `page.screenshot({ path: 'test-results/mobile/*.png', fullPage: true })` 증빙 수집

### Changed
- `src/frontend/tests/e2e/pages/PortfolioPage.ts` (+17/-5) — `holdingRow` 를 `page.getByTestId('holding-row').filter({ hasText, visible: true })` 로 전환 (뷰포트 독립). `kisSyncButton` name regex 확장 (`/KIS 모의 동기화|모의 sync|KIS 실계좌 동기화|실계좌 sync/`). `holdingsTable` 에 desktop 전용 JSDoc 경고.
- `src/frontend/tests/e2e/holdings.spec.ts` + `actions.spec.ts` — `test.beforeEach` 에서 `testInfo.project.name !== 'chromium'` 일 때 skip. 데스크톱 테이블 전제 스펙 보호.
- `docs/mobile-responsive-plan.md` §4 Phase E1 체크 완료 표시.

### Fixed
- **strict mode 위반** (CI 첫 회차 실패): `hidden sm:block` / `sm:hidden` 으로 `<tr>` + `<li>` 가 DOM 에 공존해 `getByTestId('holding-row')` 가 2 매치 → `filter({ visible: true })` 로 현재 뷰포트에서 실제 렌더된 노드만 선택. 이 수정이 `c3b8911` fix 커밋에 squash.

### Verified
- `npx tsc --noEmit` ✅ / `npx eslint` ✅ / `next build` ✅ 5.0s
- CI 6/6 green (2차 실행에서 pass)

---

## [2026-04-22] feat(frontend): 모바일 반응형 Phase D — P2 마감 (useMediaQuery + 터치 타깃 + aurora) (`9e02890`, PR #31)

### Added
- `src/frontend/src/lib/hooks/useMediaQuery.ts` (+23) — `useSyncExternalStore` 기반 SSR-safe 훅. React 19 `react-hooks/set-state-in-effect` 룰 준수. 서버 스냅샷 `false` 고정으로 hydration mismatch 회피.

### Changed
- `stocks/[code]/page.tsx` + `backtest/page.tsx` — recharts `aspect` 모바일 분기 (stocks: 2→1.4, backtest: 2.2→1.4). 375px 뷰포트 XAxis 틱 겹침 완화.
- `app/page.tsx` 대시보드 — 필터 버튼 + 정렬 select 에 `min-h-[44px] sm:min-h-0` (iOS HIG 44px). 버튼에 `inline-flex items-center justify-center` 추가로 텍스트 세로 정렬 유지.
- `globals.css` aurora blob — 모바일(`max-width: 639px`) 전용 미디어 쿼리 `blur 90px → 50px`, `opacity 0.35 → 0.25`. 저사양 GPU composite 비용 경감.

### Decisions
- **useState+useEffect → useSyncExternalStore**: React 19 신규 린트 룰 대응 + SSR-safe 외부 스토어 구독 공식 패턴. 첫 프레임 데스크톱 비율 → hydration 후 모바일 비율 전환은 작업계획서 §6 risk 에서 허용.
- **D2(푸터 `<details>`) 스킵 유지**: 실제 3줄 짧은 문구라 과장된 claim. 작업계획서 §9 변경이력 참조.

---

## [2026-04-22] feat(frontend): 모바일 반응형 Phase C — P1 가독성 (stocks/reports/alignment/portfolio) (`589a7e6`, PR #33)

원래 PR #30 이었으나 Phase B 머지 시 `--delete-branch` 로 base 소실 → 자동 closed → **#33 로 대체 생성**.

### Changed
- **C1** `stocks/[code]/page.tsx` 헤더 카드 grid-cols-3 — 라벨 `text-[0.6rem] sm:text-[0.7rem]`, 숫자 `text-base sm:text-xl`, `tabular-nums` 추가. Score 카드 `tracking-tighter` 제거.
- **C2** `reports/[stockCode]/page.tsx` `SourceRow` — 모바일 2줄(메타 위/라벨 아래) / 데스크톱 `sm:contents` 1줄 flatten. order-1/order-2 로 재배치.
- **C3** `portfolio/[accountId]/alignment/page.tsx` — 시그널 chip 모바일 3개 제한 (`idx >= 3 ? hidden sm:flex : flex`) + "+N개" 오버플로우 배지 (CSS-only, hydration 안전).
- **C4** `portfolio/page.tsx` — KIS sync 버튼 라벨 `<span className="sm:hidden">`/`<span className="hidden sm:inline">` 분기. 모바일 "실계좌 sync"/"모의 sync" → 데스크톱 "KIS 실계좌 동기화"/"KIS 모의 동기화".

---

## [2026-04-22] feat(frontend): 모바일 반응형 Phase B — 포트폴리오 카드 + NavHeader + 실계좌 행 (`bd65cb3`, PR #29)

### Added
- **B1** `portfolio/page.tsx` — 데스크톱 `<table>` `hidden sm:block` + 모바일 `<ul className="sm:hidden space-y-3">` 카드 리스트 이중 렌더링. 카드 구조: 종목명·코드 헤더 + 수량/평단/매입원가 3×1 `<dl>` + AI 리포트 링크. `data-testid="holding-row"` 를 `<tr>`/`<li>` 양쪽에 공통 부여 (뷰포트별 하나만 렌더).

### Changed
- **B2** `components/NavHeader.tsx` — 로고 우측 `v1.0` 배지 `hidden sm:inline`. 모바일 로고 공간 확보.
- **B3** `components/features/RealAccountSection.tsx` — 계좌 행 `flex-col ... sm:flex-row sm:items-center sm:justify-between`. 버튼 그룹 `flex-wrap gap-2 sm:shrink-0 sm:flex-nowrap` 로 좁은 화면 2줄 wrap 허용. 3개 버튼 `aria-disabled` 추가, masked credential `break-all`, `data-testid="real-account-row"` 신규 (Phase E1 mobile.spec.ts 용).

---

## [2026-04-22] feat(frontend): 모바일 반응형 Phase A — viewport 메타 + Playwright 모바일 프로필 (`0070f97`, PR #28)

`docs/mobile-responsive-plan.md` Phase A (Gate 1 스코프) 구현. 3.5~4 man-day 모바일 반응형 refactor 의 첫 단계로 "설정 도입" 까지만 범위. 모바일 전용 스펙은 Phase B~E 에서 햄버거 드로어/카드 레이아웃과 함께 추가 예정.

### Added
- `src/frontend/src/app/layout.tsx` 에 Next.js 16 `export const viewport` 추가
  - `width: "device-width"` / `initialScale: 1` / `maximumScale: 5` — 확대 접근성 유지
  - 기존 `metadata` export 와 별개로 동작 (Next.js 14+ 권장 분리)
- `src/frontend/playwright.config.ts` 에 모바일 프로필 2개 추가
  - `mobile-safari` (iPhone 13, WebKit)
  - `mobile-chrome` (Galaxy S8, Chromium)
  - 기존 40 개 E2E 스펙이 모바일 프로필에서도 자동 수집 (42 tests × 3 projects)
- `src/frontend/tests/e2e/mobile-viewport.spec.ts` 신규 (+2 tests)
  - viewport meta content 정규식 검증
  - 홈 페이지 모바일 뷰포트 가로 스크롤 없음 검증 (`scrollWidth − clientWidth <= 1`)

### Fixed
- `.github/workflows/e2e.yml` 의 `Run Playwright E2E` 스텝에 `--project=chromium` 명시
  - 모바일 프로필 도입 후 기본 실행이 3 projects 전체로 확장되며 햄버거 드로어 미대응 데스크톱 스펙 45개가 모바일에서 timeout → CI fail. Phase A 스코프를 "설정 도입" 으로 유지하기 위해 CI 는 chromium 만 게이트하도록 고정.

### Verified
- `npm run type-check` (tsc --noEmit) ✅
- `npm run lint` (eslint) ✅
- `npm run build` (Next.js 16 Turbopack) ✅ 2.0s compile
- `npx playwright test --list --project=mobile-safari` ✅ 42 tests enumerated
- CI 6/6 green (backend-lint / frontend-lint / backend-test / frontend-build / docker-build / e2e(chromium))

### Decisions
- **Gate 1 스코프 준수**: 계획서 §8 의 "viewport + 모바일 E2E 프로필 동작 확인" 범위 외 일절 손대지 않음. Phase B (포트폴리오 테이블→카드 + RealAccountSection 3버튼) 는 별도 PR.
- **모바일 E2E 회귀 자동화는 Phase B 이후**: 기존 스펙이 햄버거 드로어를 열지 않아 모바일에서 실패. Phase B 에서 NavHeader 드로어 오픈 로직을 spec 공통 util 로 분리한 뒤 CI 에 모바일 프로젝트 추가.
- **접근성 우선**: `maximumScale: 5` 로 사용자 확대 허용. 계획서 §6 위험 "iOS 기존 동작 변경" 완화.
- **단일 PR #28 의 원자성**: Phase A 구현(`6c9a995`) + CI 수정(`53a7f75`) 2 커밋을 squash merge — "mobile 프로필 추가" 와 "CI 가 그 프로필을 돌리지 않게 한다" 는 서로를 해명하므로 분리하지 않음.

### Known Issues (남은 부채)
- 모바일 프로필 E2E 가 실제로 돌지 않음 → Phase B 에서 햄버거 드로어 공통 helper 추가 후 활성화
- 계획서 §2 item 5 (alignment chip wrap) / item 8 (터치 타깃 44px) 등 P1~P2 미착수
- HANDOFF.md 의 "5→6 PR" 단순 문구 갱신은 Phase A 세션이 7 PR 로 마감되면서 무효화 — 이번 세션 마감 핸드오프로 overwrite

---

## [2026-04-22] chore: CI 에 frontend-lint 게이트 추가 — eslint + tsc --noEmit (`5c0b305`, PR #26)

모바일 반응형 refactor(3.5~4 man-day) 착수 전 안전망. 백엔드 `backend-lint` (PR #22) 와 대칭.

**이전 상태**: `frontend-build` job 의 `Lint` 스텝이 `npm run lint --if-present` + `continue-on-error: true` — lint 실패가 CI 를 막지 않음. `next build` 가 타입 체크를 포함하지만 `// @ts-ignore` 등은 silent.

### Added
- `.github/workflows/ci.yml` 에 **`frontend-lint`** job 신설
  - `npm run lint` (eslint) — 이제 실패 시 CI red
  - `npm run type-check` (`tsc --noEmit`) — 독립 타입 체크 스텝
- `src/frontend/package.json` 에 `"type-check": "tsc --noEmit"` 스크립트 추가

### Changed
- `frontend-build` job 을 `needs: [frontend-lint]` 로 의존 — lint 실패 시 풀 `next build` (~2분) 스킵해 자원 절감
- 기존 `frontend-build` 안의 `Lint` 스텝 제거 (신규 job 으로 이관)

### Verified
- `npm run lint` ✅ (로컬 silent success, 기존 코드 이미 clean)
- `npm run type-check` ✅ (로컬 silent success)
- `next build` 경로 변경 없음 — `frontend-lint` 가 먼저 실행될 뿐

### Decisions
- **lint job 을 build 앞에**: `backend-test needs backend-lint` 와 동일 패턴. 1~2분 내 빠른 실패 신호.
- **`eslint` / `tsc` 별도 스텝**: 에러 표면 구분. CI 로그에서 "lint 실패" vs "type 실패" 즉시 식별.
- **기존 코드 clean 이라 fix 불필요**: 백엔드 PR #22 (98 파일 ruff format) 와 달리 프론트는 이미 eslint + tsc 통과 상태. 이 PR 은 순수 게이트 추가.

---

## [2026-04-22] refactor: KIS Hexagonal DIP 완성 + Router account 단일 로드 (`597d5e8`, PR #25)

/review 세션 감사에서 발견된 HIGH 2건을 단일 "아키텍처 정돈 PR" 로 통합 해소.

**이전 상태**:
- `portfolio_service.py` 가 `from app.adapter.out.external import KisClient, KisClientError, KisCredentialRejectedError, KisCredentials, KisHoldingRow` 로 **application → infra 직접 참조**. PR #23 에서 `MaskedCredentialView` 만 dto 로 이동했고 KIS 관련은 잔존.
- `sync_from_kis` router 가 account 선로드 후 UseCase 내부에서 `_ensure_kis_real_account` 가 재조회. Repository.get 이 내부적으로 `session.get` (identity map 캐시) 이라 실제 DB round-trip 은 1회이지만, 리뷰 독자에게 자명하지 않음.

### Added
- **`app/application/dto/kis.py`** (신규) — `KisCredentials`, `KisHoldingRow`, `KisEnvironment` 이동. Hexagonal 경계 정합 (application layer 가 DTO 소유).
- **`app/application/port/out/kis_port.py`** (신규) — KIS 잔고 조회 port:
  - `KisHoldingsFetcher` Protocol (structural typing) — `KisClient` 가 명시 상속 없이 자동 만족
  - `KisUpstreamError` (포트 최상위) + `KisCredentialRejectedError` (401/403 전용 서브) — port 레벨 예외 계층
  - `KisRealFetcherFactory = Callable[[KisCredentials], KisHoldingsFetcher]` 타입 별칭

### Changed
- `app/adapter/out/external/kis_client.py`: DTO 정의 제거, port 예외 직접 raise. adapter-internal `KisClientError`/`KisAuthError`/`KisCredentialRejectedError` 삭제 (port 예외로 수렴).
- `app/adapter/out/external/__init__.py`: DTO/port 예외를 `app.adapter.out.external` 네임스페이스에서 re-export (배선·테스트 편의, 기존 호출부 backward-compat).
- `app/adapter/web/_deps.py`: DTO import 경로를 `app.application.dto.kis` 로. `get_kis_real_client_factory` 반환 타입을 `KisRealFetcherFactory` (port 타입) 로.
- `app/application/service/portfolio_service.py`: `from app.adapter.out.external import ...` **완전 제거**. port/dto 만 참조. `_ensure_kis_real_account` + 3 UseCase(`Mock`/`Real`/`TestConnection`) `execute()` 에 optional `account: BrokerageAccount | None = None` 파라미터 추가 — 라우터가 선로드한 account 를 명시 전달 가능.
- `app/adapter/web/routers/portfolio.py`: `sync_from_kis` 의 UseCase 호출이 `account=loaded_account` 를 명시 전달. 시그니처가 `KisHoldingsFetcher` Protocol 참조로 DIP 준수.

### Fixed
- 리뷰 HIGH: `KisNotConfiguredError` 를 `Exception` 직계로 분리 (이전 `KisUpstreamError` 상속) — 서버 설정 오류를 UseCase `except KisUpstreamError` 가 삼켜 `SyncError` → 502 로 오진단하는 경로 차단. 이제 설정 오류는 FastAPI 기본 500 으로 전파.
- 리뷰 MEDIUM: `kis_client.py` `test_connection` docstring 의 삭제된 `KisAuthError` 이름 잔존 → `KisCredentialRejectedError` / `KisUpstreamError` 로 현행화.

### Not Done (intentional)
- **R-03 이름 중복 완화**: port `KisCredentialRejectedError` vs domain `CredentialRejectedError`. `Kis` prefix 로 구분. ruff N818(Error suffix) 때문에 suffix 유지 필요 → 리네이밍은 별도 PR 후보.
- **다른 서비스 DIP 확장**: `notification_service`(TelegramClient), `market_data_service`(KrxClient), `analysis_report_service` 도 adapter 직접 참조 잔존. 본 PR 은 KIS 영역 leading example, 추후 PR 로 확장.
- **Adapter __init__ re-export 제거**: 테스트·배선·기존 호출부 backward-compat 유지. application layer 는 직접 port/dto 경로로만 import 하므로 DIP 훼손 없음.

### Verified
- `uv run ruff check .` ✅
- `uv run ruff format --check .` ✅ 126 files already formatted
- `uv run mypy app` ✅ **83 source files** (신규 2 포함), no issues
- `uv run pytest -q` ✅ **303 passed, 1 deselected** — 회귀 0건

### Decisions
- **Structural typing 우선**: `KisClient` 가 Protocol 을 명시 상속하지 않음. mypy strict 가 `KisClient` → `KisHoldingsFetcher` 할당 지점에서 검증 (factory 반환 경로).
- **Protocol 에 `__aenter__`/`__aexit__` 포함**: "이 port 는 context manager 로만 사용한다" 계약 명시. `typing.AsyncContextManager` 상속 대신 explicit 선언이 가독성 우수.
- **Optional account 파라미터 하위 호환**: `execute(*, account_id, account=None)` — 기존 호출부 수정 불필요. Router 만 명시 전달.
- **`KisRealClientFactory` alias 유지**: `KisRealFetcherFactory` 의 하위 호환 alias, 외부 참조 없음 확인 후 다음 클린업 PR 에서 제거.

---

## [2026-04-22] refactor: KisAuthError 401/5xx 분리 — credential 거부 vs 업스트림 장애 (`77903d9`, PR #24)

**이전 상태**: PR 5 (#16) 리뷰 이월 MEDIUM. KIS 토큰 발급/잔고조회가 HTTP 401/403 (credential 거부) 이든 5xx/네트워크 (업스트림 장애) 이든 모두 `KisAuthError`/`KisClientError` → UseCase 가 `SyncError` 로 래핑 → 라우터에서 **일괄 502** 응답. 사용자가 "KIS 자격증명 틀림" 과 "KIS 서버 다운" 을 구분 못 함.

### Added
- **`KisCredentialRejectedError(KisAuthError)` 서브클래스** — HTTP 401/403 전용. 토큰 발급 + 잔고조회 두 경로 모두 raise.
- **`CredentialRejectedError(PortfolioError)` 도메인 예외** — UseCase 가 `KisCredentialRejectedError` 를 catch 해 도메인 계층으로 승격. 4xx 매핑 대상.
- 테스트 8건 추가:
  - `test_kis_client.py`: 토큰 401/403 파라메트라이즈, 토큰 500 → base KisAuthError (서브클래스 아님 단언), 잔고 401/403 파라메트라이즈
  - `test_kis_real_sync.py`: UseCase 레벨 401/403 → CredentialRejectedError, 500 → SyncError, endpoint 400/502 분리

### Changed
- `SyncPortfolioFromKisMockUseCase` / `SyncPortfolioFromKisRealUseCase` / `TestKisConnectionUseCase` 세 UseCase 의 except 순서: `except KisCredentialRejectedError` 를 `except KisClientError` **앞** 에 배치. 서브클래스가 먼저 잡혀 도메인 `CredentialRejectedError` 로 승격.
- Router `_credential_error_to_http`: `CredentialRejectedError` → **HTTP 400** 분기 추가 (SyncError → 502 분기 앞).
- 기존 `test_connection_token_failure_wrapped_as_sync_error` (401 → SyncError) → `test_connection_credential_reject_raises_credential_rejected` (401/403 → CredentialRejectedError) 로 교체. 기존 `test_endpoint_test_connection_token_failure_502` (401 → HTTP 502) → `_credential_rejected_400` / `_upstream_failure_502` 두 케이스로 분리.

### Fixed
- PR 5 이월 MEDIUM (4xx/5xx 분리) 해소.
- 리뷰 MEDIUM #1 (예외 메시지의 `body=...` HTTP response detail 노출) 예방 — `body=` 제거 후 DEBUG 로그로 분리. PR #20 의 마스킹 파이프라인을 거치도록 해 JWT/hex 패턴 자동 스크럽.

### Verified
- `uv run ruff check .` ✅
- `uv run ruff format --check .` ✅ 124 files already formatted
- `uv run mypy app` ✅ 81 source files, no issues
- `uv run pytest -q` ✅ **303 passed, 1 deselected** — +8 신규, 회귀 0건

### Decisions
- **HTTP 400 (401 아님)**: 서버 인증 실패가 아니라 KIS 업스트림이 credential 거부. 401 은 FE 가 "우리 admin API 인증 실패" 로 오해 유도. 422 Unprocessable Content 도 고려했으나 이 경우 request body 자체는 valid 라 422 semantics 와 안 맞음. 400 + 구체 메시지가 적절.
- **`status_code` 속성 안 추가**: `KisCredentialRejectedError` 는 타입만으로 분기. 인스턴스에 status_code 필드를 얹지 않음 — 도메인 로직이 값 검사 안 함. 단순성 우선.
- **CredentialRejectedError 는 SyncError 의 sibling**: 둘 다 `PortfolioError` 직속 서브클래스. Router `isinstance` 분기가 독립적으로 작동.
- **MOCK 경로도 승격**: 흔치 않지만 고정 mock key 만료 케이스 커버. 메시지에 "서버 env 점검 필요" 문구로 operator 안내.
- **리뷰 MEDIUM 2·3 스킵**: (2) 계층 간 유사 이름 부담 — follow-up 후보. (3) MOCK 401 을 사용자 응답으로 노출 — 메시지 텍스트로 operator 안내로 충분.

---

## [2026-04-22] refactor: Hexagonal 경계 + Sync UseCase mock/real 분리 (`576e9f2`, PR #23)

**이전 상태**: PR 5 (#16) 리뷰에서 HIGH 2건 carry-over.
1. `MaskedCredentialView` 가 `app/adapter/out/persistence/repositories/brokerage_credential.py` 에 정의되고 `portfolio_service` 가 re-export — application → infra 역방향 의존.
2. `SyncPortfolioFromKisUseCase.__init__` 가 `kis_client | None`, `credential_repo | None`, `real_client_factory | None` 세 Optional 로 받아 runtime `RuntimeError` 로 검증 — 타입 안전성 없음.

### Changed
- **`MaskedCredentialView` → `app/application/dto/credential.py` 신규 파일로 이동**. Hexagonal 경계 준수 (application layer 가 DTO 를 소유, infra 가 import 해서 반환).
- **`SyncPortfolioFromKisUseCase` 를 두 UseCase 로 분리**:
  - `SyncPortfolioFromKisMockUseCase` — `kis_client: KisClient` 필수 (non-Optional)
  - `SyncPortfolioFromKisRealUseCase` — `credential_repo: BrokerageAccountCredentialRepository` + `real_client_factory: KisRealClientFactory` 필수 (둘 다 non-Optional)
- **공통 로직 → `_apply_kis_holdings()` 모듈 헬퍼**. holding upsert 루프만 공유, 분기별 fetch 로직은 각 UseCase 에 집중.
- **Router `sync_from_kis` 디스패치**: `account.connection_type` 으로 분기해 적절한 UseCase 선택. 로드된 account 는 동일 세션 내 재조회 (race 안전, 캐시 히트).
- `KisConnectionType = Literal["kis_rest_mock", "kis_rest_real"]` 타입 별칭 도입 — `_apply_kis_holdings` 가 임의 문자열을 `SyncResult.connection_type` 에 흘리지 않도록 타입으로 좁힘.

### Fixed
- PR 5 이월 HIGH #1 (Hexagonal 레이어 위반) 해소
- PR 5 이월 HIGH #2 (Optional 파라미터 퇴화) 해소
- `test_sync_kis_rest_real_requires_real_environment`: 기존 테스트는 mock UseCase 로 `kis_rest_real` 계좌를 검증해 `UnsupportedConnectionError` 가 먼저 터져 실제로는 environment 검증을 테스트하지 못함. 신규 real UseCase 로 전환해 `_ensure_kis_real_account` 환경 검증에 정상 도달. `credential_repo.get_decrypted` + factory 둘 다 AssertionError 스텁으로 호출되면 실패하도록 해 순서 회귀 감지 강화.

### Verified
- `uv run ruff check .` ✅
- `uv run ruff format --check .` ✅
- `uv run mypy app` ✅ 81 source files, no issues
- `uv run pytest -q` ✅ **295 passed, 1 deselected** — 회귀 0건

### Decisions
- **mock/real UseCase 완전 분리**: 리뷰어가 제시한 단일 UseCase + Protocol/Fetcher 패턴은 간접 층 추가로 판단해 채택 안 함. 클래스 2개 + 공통 헬퍼가 더 직관적.
- **account 이중 로드 허용**: Router 선로드 + UseCase 재검증. 동일 세션 1트랜잭션 범위에서 race-safe, SA identity map 캐시 히트.
- **DB 모델 `connection_type: Mapped[str]` Literal 화 분리**: Router `else` dead-path exhaustive check 가능하려면 SQLAlchemy 모델 타입을 `Literal` 로 좁혀야 하나 DB 계층 광범위 변경이라 별도 PR.

---

## [2026-04-22] chore: CI 에 ruff + mypy strict 게이트 추가 (`3f0061e`, PR #22)

**이전 상태**: CI 가 pytest + next build + docker build 만 검증 — ruff/mypy 는 로컬 전용. 개발자별 환경 편차로 master 에 포매팅 누락·타입 에러 유입 위험.

### Added
- `.github/workflows/ci.yml` 에 **`backend-lint`** job 신설
  - `uv run ruff check .` — lint 룰 (E/W/F/I/B/UP/N/SIM)
  - `uv run ruff format --check .` — 포매팅 강제
  - `uv run mypy app` — strict 타입 검증 (plugins: pydantic.mypy)
- `backend-test` job 을 `needs: [backend-lint]` 로 의존 — lint 실패 시 pytest 스킵하여 자원 절감

### Changed
- **`src/backend_py` 전체 ruff format 일괄 적용** (98 파일 재포매팅, 로직 변경 0건). 본 레포에 ruff format 이 처음 도입된 상태였음
- `app/adapter/web/routers/signals.py`: 리스트 컴프리헨션 내 `stocks.get(sig.stock_id)` 2회 호출 → `for` 루프로 풀어 `stock` 로컬 바인딩. mypy union-attr 2건 (pre-existing 부채) 해소 + 중복 `.get()` 호출 제거

### Fixed
- `scripts/fix_stock_names.py`, `scripts/seed_e2e_accounts.py`: ruff SIM117 (중첩 `async with` 결합) 2건 autofix

### Verified
- `uv run ruff check .` ✅
- `uv run ruff format --check .` ✅ (123 files already formatted)
- `uv run mypy app` ✅ (80 source files, no issues)
- `uv run pytest -q` ✅ **295 passed, 1 deselected** — 회귀 0건

### Decisions
- **mypy 범위 `app/` 만**: tests/scripts 는 strict 미적용. 향후 확대 후보 (별도 PR). 테스트 코드는 mock 객체 다량 — strict 게이트 ROI 낮음
- **단일 PR 통합**: format 98 파일 + lint 2건 + mypy 2건 + CI 변경을 한 PR 로 묶음. 분리 시 format PR 이 머지 전에 다른 PR 과 충돌할 위험 + 차기 작업 차단 최소화
- **PR 5 이월 Hexagonal 부채**: 본 PR 에서 해소하지 않음. CI 게이트 추가는 현상 유지 위에서 게이트를 덮는 변경이므로 리팩터링과 분리

---

## [2026-04-21] docs: 모바일 반응형 계획서 현행화 (`7b11d88`, PR #19)

모바일 반응형 개선 작업계획서(`docs/mobile-responsive-plan.md`)를 **착수 전 현행화** — 작성(2026-04-20) 이후 머지된 PR #12·#15·#16 으로 UI 표면 유입 재진단.

### Changed
- 대상 스택: Next.js 15 → **16.2.4** + React 19.2.4 반영
- 수정 공격 지점: 3군데 → 5군데 확장
- **P1 신규**: RealAccountSection 3-버튼 (연결 테스트·수정·삭제) 모바일 레이아웃 (B3), Portfolio sync 버튼 라벨 확장 (C4)
- **D2 스킵**: 푸터 면책 `<details>` 접기 — 실제 3줄 짧은 문구, 필요성 낮음
- 예상 작업량 3~3.5 → **3.5~4 man-day**
- §9 변경 이력 섹션 신설

---

## [2026-04-21] docs: PIPELINE-GUIDE 현행화 + README 프로미넌트 링크 (`57dd562`, PR #18)

신규 프로젝트 진행 시 가장 중요한 엔트리 문서 현행화.

### Changed
- **README**: 상단 "🚨 필독" call-out 박스 + PIPELINE-GUIDE.md 링크 프로미넌트화. 핵심 문서 섹션에서도 이모지 + "신규 프로젝트 진행 시 가장 먼저 읽을 문서" 명시
- **PIPELINE-GUIDE §2 필수 준비물**: Java 21 → **Python 3.12 + FastAPI + Next.js 16** 반영. `.claude/settings.local.json` · `gh` CLI 언급
- **PIPELINE-GUIDE §8 Q3 코드리뷰**: `java-reviewer` 단독 → **언어별 reviewer 매핑 표** (python/typescript/kotlin/java/go/rust). 병렬 리뷰 실전 패턴 섹션 (본 프로젝트 PR #12~#16 에서 검증)
- **PIPELINE-GUIDE §실전 학습**: 🆕 KIS sync 시리즈 (PR #12~#16) 교훈 11건 추가. Sprint 1~3 Java 시대는 참고용 보존. 공통 워크플로우 섹션 (`/ted-run` · feature branch + squash · CI 4/4 게이트 · `/handoff` · Co-Authored-By) 신설

---

## [2026-04-21] chore: .claude/settings.local.json 을 .gitignore 에 추가 (`2a97e27`, PR #17)

### Added
- `.claude/settings.local.json` — 로컬 개인 설정 오버라이드 (`includeCoAuthoredBy` 등). 관례상 `.local` 접미는 "커밋 제외" 의미 → `.gitignore` 명시
- `.gitignore` 에 `.claude/settings.local.json` 한 줄 추가

---

## [2026-04-21] KIS sync PR 6: 로깅 마스킹 (시리즈 최종) (`1483940`, PR #20)

**KIS sync 시리즈 완결** (6/6). PR 5 에서 실 KIS 외부 호출이 열린 직후 노출된 위험을 처리. structlog 기반 구조화 로깅 + 2층 민감 데이터 방어 (키 기반 `[MASKED]` 치환 + JWT/hex 정규식 scrub). 백엔드 테스트 **239 → 295** (+56). 리뷰 HIGH 3건 + MEDIUM 3건 + LOW 1건 수용.

### Added

- **KIS sync PR 6 — 로깅 마스킹** (시리즈 최종): 설계 문서 § 3.5 보안 하드닝 + § 5 PR 6 + § 6 결정 #4.
  - **`app/observability/` 신규 패키지**: 관측 관심사(로깅·메트릭·트레이싱) 집중. `__init__.py` 선제 import 0 유지 (순환 방지, PR 3 `app/security/` 와 동일 규칙).
  - **`app/observability/logging.py`** (~180 lines):
    - `SENSITIVE_KEYS` frozenset — 표준 OAuth2/JWT 키(`app_key`·`app_secret`·`access_token`·`authorization`) + 프로젝트 특이 env 필드(`openai_api_key`·`dart_api_key`·`telegram_bot_token`·`krx_id`·`krx_pw`·`kis_app_key_mock`) 명시
    - `SENSITIVE_KEY_SUFFIXES` tuple — 신규 env 필드 자동 커버용 접미 일치 (`_api_key`·`_app_secret`·`_bot_token`·`_master_key`·`_credential` 등 14종)
    - `_is_sensitive_key(key)` 헬퍼 — 완전 일치 + 접미 일치 OR 검사, 대소문자 무시
    - `_scan(node)` 재귀 스캔 — dict/list/tuple 의 민감 키 값 `[MASKED]`, string leaf 는 `_scrub_string`
    - `_scrub_string(s)` — `eyJ` 접두 JWT 3-segment (`[MASKED_JWT]`) + 40자 이상 hex (`[MASKED_HEX]`). JOSE 표준 준수 덕에 structlog logger 이름 false positive 차단
    - `mask_sensitive` structlog processor — renderer 직전에 event_dict 전체 재귀 마스킹
    - `setup_logging(log_level, json_output)` — stdlib ↔ structlog `ProcessorFormatter` 브릿지. `_configured` guard 로 **1회만 유효** (재호출 no-op) → pytest `caplog` 외부 핸들러 보존
    - `reset_logging_for_tests()` — 테스트 전용 guard 리셋
  - **`app/main.py`**: `create_app()` 앞단에서 `setup_logging(log_level, json_output=app_env!="local")` 호출. idempotent 라 re-invocation 안전.
  - **`app/config/settings.py`**: `log_level: Literal["DEBUG","INFO","WARNING","ERROR","CRITICAL"]` 필드 추가 — 오타 env var 가 Pydantic 검증에서 즉시 실패.
  - **README**:
    - "**KIS OpenAPI 토큰 revoke 한계**" 섹션 신설 — 24h 고정 TTL, 명시적 폐기 엔드포인트 부재. credential 삭제 시 기존 토큰은 만료까지 유효. 유출 의심 시 KIS 웹사이트에서 `app_key` 재발급(roll) 절차 명시 (결정 #4 반영).
    - "**로깅 민감 데이터 보호**" 섹션 — 2층 방어 메커니즘과 `SENSITIVE_KEYS` 확장 방법 안내.
  - **테스트 56건 추가** (백엔드 **239 → 295**):
    - `_scrub_string` 5건 (JWT eyJ 접두 + hex 40자+ + 한국어 보존 + `eyJ` 없는 dotted 식별자 false positive 방어)
    - `_scan` 9건 (parametrized SENSITIVE_KEYS 26 + 중첩 dict/list + 비민감 키 보존 + None 유지)
    - compound keys via suffix 8건 — `openai_api_key`·`dart_api_key`·`kis_app_key_mock`·`telegram_bot_token`·`krx_pw` 등 실제 env 필드 검증
    - `mask_sensitive` processor 2건
    - 통합 4건 (stdlib logger extra drop + JWT scrub + structlog native bind + idempotent guard 강화 — foreign 핸들러 보존 검증)

### Process Notes

- **리뷰 HIGH 3건 전부 수용**:
  - HIGH #1 JWT 패턴 false positive → `eyJ` 접두 제약으로 Python 식별자 오탐 차단
  - HIGH #2 `_configured` dead code → 실제 early-return guard 로 전환 + `reset_logging_for_tests` 헬퍼 노출. pytest `caplog` 같은 외부 핸들러를 silently 제거하던 문제 해결
  - HIGH #3 SENSITIVE_KEYS 누락 → `SENSITIVE_KEY_SUFFIXES` 도입 + 프로젝트 특이 필드 explicit 목록화로 2층 방어
- **리뷰 MEDIUM 3건 + LOW 1건 수용**: `assert` → 방어적 `if isinstance` 분기 (`-O` 환경 안전), `log_level: Literal[...]` Pydantic enum 좁히기, 테스트 `type: ignore` 제거 + `Callable[[], None]` 타입 힌트.
- **Defer (사유)**: LOW #2 hex 40자 임계값 유지 — 현 KIS 도메인 실문제 없음, 56자 상향은 별도 정책 논의. LOW #3 테스트 격리 — `reset_logging_for_tests` + `autouse` fixture 로 해소됨.

### 🎉 KIS sync 시리즈 완결

6 PR 누적 성과:
- PR #12 (엑셀 import, `6ea71fe`)
- PR #13 (어댑터 분기 스캐폴딩, `269651e`)
- PR #14 (Fernet credential 저장소, `3db778f`)
- PR #15 (등록 API + Settings UI, `d470a73`)
- PR #16 (연결 테스트 + 실 sync wire, `1461582`)
- **PR #N (로깅 마스킹, 본 PR)**

백엔드 테스트: 197 → **295** (+98, smoke 1 deselected). CI 6회 연속 4/4 PASS. 외부 호출 0 에서 출발해 실 KIS 호출 개시 + 민감 데이터 로그 누수 방어까지 완결.

---

## [2026-04-21] KIS sync PR 5: 연결 테스트 + 실 sync wire (`1461582`, PR #16)

1-PR 세션: KIS sync 시리즈 5/6. 본 PR 머지부터 **운영 코드에서 실 KIS 외부 호출이 가능** — CI 는 `@pytest.mark.requires_kis_real_account` 마커 + pyproject `addopts` 로 smoke 1건을 skip, 나머지 real 경로 테스트 11건은 `httpx.MockTransport` 로 실 URL 차단. 백엔드 테스트 **227 → 239** (+12, smoke 1 deselected). 리뷰 HIGH 6건 중 4건 수용, 2건 구조적(Hexagonal 위반·Optional 파라미터 런타임 퇴화) defer.

### Added

- **KIS sync PR 5 — 연결 테스트 + 실 sync wire**: 설계 문서 § 3.4 (3단계 온보딩) + § 5 PR 5.
  - **`KisClient.test_connection()`** (`kis_client.py`): OAuth 토큰 발급만 시도하는 dry-run. 잔고 조회 API 호출 안 함 → 계좌 상태 변경 0. 부수 효과: 토큰 캐시에 저장돼 이어지는 `fetch_balance()` 는 재발급 skip. 재시도 없음 ("빠른 1회 검증" 의미).
  - **`TestKisConnectionUseCase`** (`portfolio_service.py`): `__test__ = False` (pytest auto-collection 제외). credential decrypt → `async with factory(credentials) as client: await client.test_connection()`. 토큰 실패는 `SyncError` 로 감싸 router 가 502 로 변환.
  - **`SyncPortfolioFromKisUseCase` wire**: `credential_repo` + `real_client_factory` 주입받아 `kis_rest_real` 분기 실구현. `_fetch_balance_real` / `_fetch_balance_mock` 서브 메서드로 분리. `KisCredentialsNotWiredError` 예외 클래스 삭제.
  - **`_ensure_kis_real_account` 공통 헬퍼**: 계좌 존재 + `connection_type='kis_rest_real'` + `environment='real'` 검증을 한 곳에 집중. `BrokerageCredentialUseCase` · `TestKisConnectionUseCase` · `SyncPortfolioFromKisUseCase` 모두 이 헬퍼 위임.
  - **`KisRealClientFactory`** 타입 별칭 + **`get_kis_real_client_factory()`** DI (`_deps.py`): 요청 스코프 factory. 각 요청이 credential 별 고유 `KisClient(REAL)` 를 생성, `async with` 로 httpx 커넥션 풀 정리. 테스트는 `dependency_overrides` 로 MockTransport 주입한 factory 로 치환.
  - **HTTP 엔드포인트** `POST /api/portfolio/accounts/{id}/test-connection` → `{account_id, environment, ok}` (200) / 404 (계좌·credential 미등록) / 400 (비 `kis_rest_real`) / 403 (env 불일치) / 502 (KIS 토큰 발급 실패) / 500 (cipher 실패). 기존 `/sync` 는 real 분기 정상 동작 + credential 미등록 시 404.
  - **`_credential_error_to_http` 공통 매퍼**: sync + test-connection + credential CRUD 6개 엔드포인트의 예외 핸들러를 단일 함수로 통합 (`SyncError` → 502 포함). 각 엔드포인트의 try/except 블록이 2줄로 간소화.
  - **pytest marker `requires_kis_real_account`** (`pyproject.toml`): `addopts` 에 `-m "not requires_kis_real_account"` 로 기본 skip, 로컬 개발자는 `pytest -m requires_kis_real_account` 로 오버라이드해 실 KIS 검증. `KIS_REAL_APP_KEY`/`SECRET`/`ACCOUNT_NO` env 가 비어있으면 smoke 내부에서 `pytest.skip()`.
  - **FE `RealAccountSection`**: 각 credential 등록 계좌 행에 **"연결 테스트"** 버튼 추가 (민트/그린 `#65D6A1`). 502 응답은 중립 메시지 ("KIS 업스트림 오류. 잠시 후 재시도하거나 자격증명을 확인해주세요").
  - **FE Portfolio 페이지**: sync 버튼이 `kis_rest_real` 계좌에서도 활성화 (기존은 `kis_rest_mock` 만). 버튼 라벨이 connection_type 에 따라 "KIS 실계좌 동기화" / "KIS 모의 동기화" 분기. 404 응답에 `kis_rest_real` 조합이면 "자격증명 미등록 — 설정에서 등록" 맥락 배너 표시.
  - **FE API 클라이언트**: `testKisConnection(accountId)` 추가. `TestConnectionResponse` 타입은 `{ok: true, environment: 'real'}` 리터럴로 좁혀 성공 경로를 타입 계약으로 강제.
  - **테스트 12건 추가** (백엔드 **227 → 239**, smoke 1 deselected):
    - use case 4건 (토큰 성공·credential 미등록·비 real 계좌 거부·토큰 401 → SyncError)
    - real sync 2건 (MockTransport 로 fetch_balance · upstream 500)
    - HTTP 엔드포인트 5건 (test-connection 성공·404·502·400 + sync real 성공·404)
    - smoke 1건 (`@pytest.mark.requires_kis_real_account`, env 없으면 skip, CI deselected)

### Process Notes

- **리뷰 HIGH 4건 수용**: `_raise_for_credential_error` → `_credential_error_to_http` (raise 아닌 return 의미 반영) + `SyncError` 매퍼 포함, `SyncPortfolioFromKisUseCase.execute` 에서 `_ensure_kis_real_account` 통합 (검증 책임 집중), `_credential_response(view: object)` → `MaskedCredentialView` 로 타입 narrow, `TestConnectionResponse.ok: boolean` → `true` 리터럴 + `environment: 'real'` 리터럴 (dead code 제거).
- **리뷰 MEDIUM/LOW 수용**: `test_connection()` docstring 보강 (부수 효과 + 재시도 없음 명시), 포트폴리오 sync 404 분기 (credential 미등록 맥락 메시지), 502 메시지 중립화, `delete_credential` 불필요 `return None` 제거, pyproject addopts 주석 보강.
- **Defer (사유 `HANDOFF.md` 기록)**: Hexagonal 레이어 위반 (`MaskedCredentialView` re-export — 구조 리팩터 별도 PR), `SyncPortfolioFromKisUseCase.__init__` Optional 파라미터 RuntimeError 퇴화 (mock/real UseCase 분리 필요 — 도메인 재설계), `KisAuthError` 별도 HTTP 매핑 (4xx vs 5xx — KIS 응답 status 검증 테스트 필요), `asyncio_mode=auto` + `@pytest.mark.asyncio` 중복 (프로젝트 전반 마이그레이션), `actionPending` 다른 계좌 disabled 이유 시각화 · `window.prompt` · `title` vs `sr-only` (UX 폴리싱 단계).

---

## [2026-04-21] KIS sync PR 4: 실계정 등록 API + Settings UI (`d470a73`, PR #15)

1-PR 세션: KIS sync 시리즈 4/6. 외부 호출 0 유지 — credential 등록·마스킹·삭제 CRUD 만, 실 KIS 호출은 PR 5. 백엔드 테스트 **213 → 227** (+14), Next.js build PASS, mypy strict 0 (내 파일), ruff 0. 리뷰 HIGH 6건 전부 반영.

### Added

- **KIS sync PR 4 — 실계정 등록 API + Settings UI**: 설계 문서 § 3.4 (2단계 온보딩) + § 5 PR 4.
  - **BE 4 엔드포인트** (`app/adapter/web/routers/portfolio.py`):
    - `POST /api/portfolio/accounts/{id}/credentials` → 201, 이미 있으면 409
    - `PUT /api/portfolio/accounts/{id}/credentials` → 200, 없으면 404
    - `GET /api/portfolio/accounts/{id}/credentials` → 마스킹 뷰 (`app_key_masked` / `account_no_masked` + `key_version`·`created_at`·`updated_at`). `app_secret` 은 어떤 경로로도 노출 0.
    - `DELETE /api/portfolio/accounts/{id}/credentials` → 204, 없으면 404
    - 모든 엔드포인트 `require_admin_key` 보호. 계좌는 `connection_type='kis_rest_real'` + `environment='real'` 조합만 허용 — 위반 시 400/403.
  - **`BrokerageCredentialUseCase`** (`portfolio_service.py`): `create`/`replace`/`get_masked`/`delete` + `_ensure_real_account` 공통 전처리. `_require_view` 로 `assert` 대신 `RuntimeError` loud fail (`python -O` 대응).
  - **`RegisterAccountUseCase` 완화**: `environment='real'` 을 `kis_rest_real` 조합에서 허용. 불일치 조합은 `InvalidRealEnvironmentError` → 403.
  - **예외 추가**: `CredentialAlreadyExistsError` (→ 409), `CredentialNotFoundError` (→ 404). `CredentialCipherError` 계층(`DecryptionFailedError`/`UnknownKeyVersionError`)은 router 에서 별도 catch → 500 + 내부 스택트레이스/예외 타입 미노출 (`_cipher_failure_as_http`).
  - **Repository 확장** (`brokerage_credential.py`): `find_row` (복호화 없이 존재 체크), `get_masked_view` (필요 필드만 복호화 후 마스킹 DTO 반환). `_mask_tail` 헬퍼는 **비례 길이 마스킹** — `len(value) - keep` 만큼 불릿 생성해 "얼마나 가렸는지" 가 시각적으로 드러남.
  - **Pydantic 스키마**: `BrokerageCredentialRequest` (app_key `min_length=16` + `\S+`, app_secret 동일, account_no `^\d{8}-\d{2}$`), `BrokerageCredentialResponse` (`_Base` 상속, `app_secret` 필드 없음). `AccountCreateRequest` 패턴 완화 — `connection_type` 에 `kis_rest_real`, `environment` 에 `real` 추가. 조합 검증은 UseCase 로 이관.
  - **FE `RealAccountSection`** (`components/features/RealAccountSection.tsx`, 신규 ~380 lines): 계좌 목록 + 등록 폼 (별칭 · app_key · app_secret · 계좌번호) + 수정(window.prompt × 3) + 삭제 버튼. 비례 길이 마스킹 뷰. `actionPending` state 로 수정/삭제 버튼 중복 클릭 차단. PUT→POST 폴백 + 409 경합 시 PUT 재시도로 race 자동 해소.
  - **FE Settings 페이지**: 기존 알림 설정 아래에 `<RealAccountSection/>` 섹션 추가. 알림 설정 저장 UI 는 불변.
  - **FE API 클라이언트**: `getCredential/createCredential/replaceCredential/deleteCredential`. DELETE 는 204 No Content 본문 없어서 `adminCall` 대신 direct fetch (`adminCall` 의 `res.json()` 강제 실행 한계 회피).
  - **테스트 14건 추가** (백엔드 **213 → 227**):
    - cipher/repo 단위 2건 (비례 마스킹 정확도·부재 시 None)
    - HTTP 엔드포인트 9건 (admin key 강제, POST 201/409, PUT 200/404, GET 마스킹/404 + DELETE 204 → 후속 GET 404, 비 `kis_rest_real` 거부, account_no 형식 검증, 모든 verb unknown account 404, cipher 실패 → 500 + 내부 예외 타입 응답 미노출)
    - `test_portfolio.py` 3건: PR 4 조합 검증 (mismatched env → 403, 역조합 → 403, 정상 `kis_rest_real` → 201)

### Process Notes

- 리뷰 HIGH 6건(BE 2 + FE 4) 전부 반영: CredentialCipherError catch + 500 변환, `assert` → `RuntimeError`, `_mask_tail` 비례 마스킹, `BrokerageCredentialResponse` `_Base` 상속, `handleCreate` 흐름 재구성 (reload 실패와 폼 클로저 분리), `showForm` 토글 stale closure 함수형 업데이터 내부로, `actionPending` 추가.
- 스킵: MEDIUM `MaskedCredentialView` layer re-export (구조 리팩터 PR 5 때), TOCTOU POST race (Admin + DB UNIQUE 보호), DELETE 의 cipher 주입 필수 (repo 생성자 구조 — PR 5 때 재조직), `adminCall` void 지원 (별도 리팩터), toast 중복 (공용 Context 후보), window.prompt UX (MVP 허용).

---

## [2026-04-21] KIS sync PR 3: `brokerage_account_credential` + Fernet 암호화 (`3db778f`, PR #14)

1-PR 세션: KIS sync 시리즈 3/6. 외부 호출 0, credential 저장소만 — 등록 API/UI 는 PR 4. CI 4/4 PASS × 1회. 백엔드 테스트 **204 → 213** (+9).

### Added
- **KIS sync PR 3 — `brokerage_account_credential` + Fernet 암호화**: 설계 문서 § 3.2 / § 5 PR 3. 외부 호출 0, PR 2 머지 후 다음 단계. credential 저장소만 — 등록 API/UI 는 PR 4.
  - **신규 패키지** `app/security/` — 도메인 중립 보안 프리미티브. `__init__.py` 는 선제 import 0 (순환 방지용).
  - **`CredentialCipher`** (`app/security/credential_cipher.py`): Fernet 래퍼. `encrypt(plain) -> (bytes, key_version)` / `decrypt(cipher, version) -> plain`. `key_version` 다중 저장 dict 로 회전 대비 (현재 v1). 예외 계층:
    - `MasterKeyNotConfiguredError`: 빈 env var 시 생성자 loud fail
    - `UnknownKeyVersionError`: 등록 안 된 key_version 복호화 시도
    - `DecryptionFailedError`: Fernet `InvalidToken` 감싸기 (외부로 cryptography 예외 미노출, 메시지에 plaintext/bytes 없음)
  - **신규 테이블** `brokerage_account_credential` (migration `008_brokerage_credential`): `app_key_cipher`/`app_secret_cipher`/`account_no_cipher` BYTEA + `key_version` + `UNIQUE(account_id)` + FK CASCADE. downgrade 에 `DO $$` PL/pgSQL 가드로 데이터 있을 시 RAISE EXCEPTION (운영 안전망).
  - **`BrokerageAccountCredentialRepository`**: cipher 주입, `upsert`/`get_decrypted`/`delete` async 메서드. `CursorResult` 타입 캐스트로 mypy strict 호환.
  - **`get_credential_cipher()`** DI (`_deps.py`): `lru_cache(maxsize=1)` 싱글톤. `conftest.apply_migrations` 가 `cache_clear()` 호출로 테스트 격리 보장.
  - **`Settings.kis_credential_master_key: str`** env var 매핑, default `""` (빈 값이면 cipher 생성자에서 loud fail).
  - **`cryptography>=43.0`** 의존성 추가.
  - **conftest fixture**: 세션 시작 시 빈 env var 면 `Fernet.generate_key()` 로 더미 마스터키 주입 (CI 실 자격증명 없이 테스트 통과).
  - **테스트 9건 추가** (백엔드 **204 → 213**): cipher 유닛 5건 (왕복·잘못된 키·빈 키·잘못된 형식 키·unknown version) + repo 통합 4건 (upsert→get 왕복·재 upsert update·delete·FK CASCADE).

### Process Notes
- 리뷰 CRITICAL 1 + HIGH 2 + MEDIUM 2 모두 반영 (mypy CursorResult 캐스트, DecryptionFailedError 래퍼, ruff import 정렬, conftest cache_clear, downgrade DO$$ 가드).
- 초기 `app/application/service/credential_cipher.py` 위치 → `service/__init__.py` 가 BacktestEngineService→repositories 체인 유발해 circular import. `app/security/` 신규 패키지로 이동 (도메인 중립, `__init__.py` 순수) 해 해결.

---

## [2026-04-21] KIS sync PR 2: `kis_rest_real` 어댑터 분기 스캐폴딩 (`269651e`, PR #13)

1-PR 세션: KIS sync 시리즈 2/6. 외부 호출 0, credential 저장소(PR 3) 미연결 상태에서 분기 구조만 선제 구축. CI 4/4 PASS × 1회. 백엔드 테스트 **197 → 204** (+7).

### Added
- **KIS sync PR 2 — `kis_rest_real` 어댑터 분기 스캐폴딩**: 설계 문서 `docs/kis-real-account-sync-plan.md` § 5 PR 2. 외부 호출 0, credential 저장소(PR 3) 미연결 상태에서 분기 구조만 선제 구축.
  - `KisEnvironment(StrEnum)`: `MOCK` / `REAL` — OpenAPI 환경 구분.
  - `KisCredentials` DTO (`frozen=True, slots=True`): `app_key`·`app_secret`·`account_no`. `__repr__` 마스킹 (`app_secret`/`account_no` `<masked>`, `app_key` 끝 4자리만 노출).
  - `KisClient.__init__(environment, credentials)` 파라미터 추가. MOCK 경로 100% 하위호환 (credentials 미주입 시 Settings 경로 유지). MOCK `base_url` 은 `_MOCK_BASE_URL` 상수 직접 할당 — Settings 커스터마이징으로 실 URL 을 mock 으로 위장하는 경로 차단.
  - REAL 경로: `_REAL_BASE_URL = "https://openapi.koreainvestment.com:9443"`, 잔고 TR_ID `TTTC8434R` (vs MOCK `VTTC8434R`). credentials 미주입 시 `KisNotConfiguredError`.
  - `VALID_CONNECTION_TYPES` 에 `'kis_rest_real'` 추가 + DB CHECK 마이그레이션 `007_kis_real_connection`.
  - `SyncPortfolioFromKisUseCase` 분기: `kis_rest_real` + `environment='real'` 조합이면 `KisCredentialsNotWiredError` (PR 3 대기용 명시 장벽). 라우터는 **HTTP 501 Not Implemented** 로 매핑 (503 대신 — 의미론상 "기능 미구현" 이 정확).
  - 백엔드 테스트 **197 → 204** (+7: REAL URL/TR_ID 1, REAL credentials 필수 1, MOCK credentials 주입 1, `__repr__` 마스킹 1, use case 분기 2, enum/CHECK 동기화 assert 1).

### Process Notes
- 리뷰 HIGH 1 + MEDIUM 4 중 HIGH 1 (MOCK base_url 상수 직접 할당) + MEDIUM 2 (503→501) + MEDIUM 3 (동기화 assert) 반영. MEDIUM 1 (`__str__` 명시) + MEDIUM 4 (downgrade DO$$ 체크) 는 ROI 낮아 기록만.
- Alembic revision ID `007_portfolio_kis_real_connection` 은 VARCHAR(32) 초과 → `007_kis_real_connection` 으로 단축 (테스트 실패로 발견).

---

## [2026-04-20] KIS sync 설계 + 엑셀 거래내역 import (`6ea71fe`, PR #12)

1-PR 세션: **KIS 실계정 sync 6 PR 시리즈** 설계 확정 + **PR 1 (엑셀 거래내역 import)** 완결. 외부 호출 0, 실 자격증명 없이 동작하는 온보딩 1단계. CI 4/4 PASS × 1회. 백엔드 테스트 **185 → 197** (+12).

### Added
- **설계 문서** `docs/kis-real-account-sync-plan.md`: 6 PR 분할 (엑셀 → 어댑터 분기 → Fernet credential → 등록 UI → 실 sync → 로깅 마스킹), 5개 열린 질문 결정 (env var Fernet, 로컬 단일 사용자, 엑셀 포함, token revoke 한계 수용, CI 더미 Fernet fixture).
- **엑셀 거래내역 import** — 온보딩 1단계 완결:
  - `POST /api/portfolio/accounts/{id}/import/excel` (multipart/form-data) — 10MB/10_000행 가드, 컬럼 alias 매칭, 중복 스킵(account·stock·date·type·qty·price tuple), stock 미등록 시 자동 생성.
  - 신규 모듈 `app/application/service/excel_import_service.py` — 파서(`parse_kis_transaction_xlsx`) + 서비스(`ExcelImportService`) 단일 파일. 실 KIS 샘플 부재라 컬럼 alias `(체결일자/거래일자/…, 종목코드/상품번호/…, 체결수량/거래수량/…)` 로 유연 매칭.
  - 프론트 `<ExcelImportPanel>` (Portfolio 페이지) — 파일 선택 → 업로드 → 실패 행 details 펼치기.
  - Next.js admin 릴레이 라우터에 multipart 경로 분기: `arrayBuffer()` 바이너리 포워드 + multipart 만 10MB 허용 (기존 64KB text 경로 유지).

### Changed
- **`portfolio_transaction.source`** CHECK 제약 확장: `('manual', 'kis_sync', 'excel_import')`. Alembic migration `006_portfolio_excel_source.py` (ALTER DROP/ADD). 기존 행 영향 없음.
- `VALID_SOURCES` (Python) + `TransactionSource` (TypeScript) 에 `'excel_import'` 반영.

### Process Notes
- **리뷰 HIGH 3 + MEDIUM 다수 반영** (python-reviewer + typescript-reviewer 병렬). Python HIGH 2 (iterrows 타입 / except 범위) 반영, HIGH 3 (session.begin 부재) 는 `get_session` 이 요청-스코프 관리 → overcall 판정. TS HIGH (Content-Length 스푸핑) 은 `arrayBuffer().byteLength` 2차 가드로 방어.
- **설계 전제 자체 교정**: 초기 "스케일 보존" 표현이 `round(0.0, 4)=0.0` 로 인해 틀렸음이 테스트 실패로 2분 내 드러남. 회귀 방어선을 재정의하고 테스트 재작성 — 설계안 검증에 코드 실행 루프가 중요함 재확인.

---

## [2026-04-20] _dec 리팩터: or Decimal("0") fallback 제거 + NaN loud fail (`e14a27b`, PR #11)

1-PR 세션: PR #9 리뷰 MEDIUM #2 사전 부채 청산. `_dec` 시그니처 단순화 + 도달불가 fallback 제거 + NaN loud fail. 백엔드 테스트 **183 → 185** (+2). CI 4/4 PASS × 1회.

### Changed
- **`_dec` 리팩터 — 도달불가 fallback 제거 + NaN loud fail** (`src/backend_py/app/application/service/backtest_service.py`): 직전 PR #9 리뷰 MEDIUM #2 사전 부채 청산.
  - 시그니처 `(float | None) -> Decimal | None` → `(float) -> Decimal`. None 반환 경로 제거.
  - L151-152 `_dec(hit_rate) or Decimal("0")` → `_dec(hit_rate)`. 호출 컨텍스트에서 `hit_rate`/`avg_ret` 는 `if observed > 0 else 0.0` guard 로 concrete float 보장이라 `or` fallback 이 도달불가였고, Zero Decimal falsy 특성 때문에 의도를 흐리는 안티패턴이었음.
  - NaN 입력은 `ValueError("_dec requires numeric value; caller must pre-guard None/NaN")` 으로 loud fail. `pd.isna` 대신 `math.isnan` 사용 — 시그니처가 `float` 라 stdlib 가 contract 와 자연스럽게 일치, 배열 입력 함정 회피.

### Added
- **`_dec` 유닛 테스트 1건 + 집계 통합 테스트 1건** (`tests/test_services.py`, 백엔드 **183 → 185**):
  - `test_dec_always_returns_decimal_and_rejects_nan`: float → Decimal 반환, NaN ValueError, `round(float, 4)` 가 입력 자연 스케일 보존 (예: `_dec(0.0) == Decimal('0.0')`, exp=-1) 을 문서화.
  - `test_backtest_aggregation_stores_zero_as_decimal`: 모든 수익률 0 시나리오 → `BacktestResult.hit_rate_5d`/`avg_return_5d` 가 None 이 아닌 `Decimal(0)` 으로 저장. 리팩터 후에도 집계 경로가 nullable 컬럼에 None 을 새지 않음을 고정.

---

## [2026-04-20] I6 설정 저장 toast E2E 2건 (`63e992a`, PR #10)

1-PR 세션: HANDOFF 차기 1순위 "I6 (설정 저장 toast) E2E" 완결. E2E 40 → **42 케이스** (I6-1 성공·I6-2 실패 2건 추가). CI 4/4 PASS × 1회.

### Added
- **I6 설정 저장 toast E2E 2건** (`src/frontend/tests/e2e/settings.spec.ts`, PR #10): `page.route('**/api/admin/notifications/preferences')` 로 PUT 만 인터셉트하고 GET URL(`/api/notifications/preferences`, admin 경로 아님) 은 매칭되지 않아 초기 로딩이 실제 백엔드로 pass-through → `notification_preference` 싱글톤 mutation 0건 보장.
  - **I6-1 (성공 경로)**: `waitForRequest + click` 을 `Promise.all` 로 동기화해 race 제거, `postDataJSON()` 로 form payload 검증 (`daily_summary_enabled`, `min_score`, `signal_types` 포함), `role=status` toast 를 `filter({ hasText: '저장되었습니다' })` 로 정밀 매칭.
  - **I6-2 (실패 경로)**: PUT 500 stub → `filter({ hasText: '서버 오류가 발생했습니다' })` toast 검증.

### Changed
- **`docs/e2e-portfolio-test-plan.md`** I 섹션: I6-1·I6-2 행 추가, 격리 전략 주석 갱신 ("별도 PR" → `page.route` 인터셉트), 상태 라인 "40/40 → **42/42**" 로 갱신.

---

## [2026-04-20] 백테스트 Infinity 버그 수정 + close_price 분모 가드 (`74938cf`)

1-PR 세션: 직전 세션 HANDOFF 1순위 차기 후보였던 **TREND_REVERSAL `avg_return=Infinity` INSERT 실패** 를 `/ted-run` 파이프라인으로 처리. master 에 커밋 **1건** 추가 (PR #9 머지 + delete-branch, CI 4/4 PASS). 백엔드 테스트 181 → **183** (신규 2건: close=0 베이스 / future=0 전손).

### Fixed
- **`BacktestEngineService` Infinity 발생 경로 차단** (`74938cf`, PR #9): 상장폐지/정지 종목의 `close_price=0` 이 분모로 쓰여 `(future/0-1) = Infinity` 가 `series.mean()` 으로 전파 → `BacktestResult.avg_return_Nd` NUMERIC(10,4) 범위 초과 → `NumericValueOutOfRangeError`. 2-layer guard 적용.
  - **Layer 1 (분모 마스킹)**: `price_base = price_wide.where(price_wide > 0)`. 분자는 원본 유지해 `future=0 & base>0` 케이스가 `(0/base-1) = -100%` 라는 유효한 전손 수익률로 기록되게 함. 분자·분모 동시 마스킹 시 -100% 가 `None` 으로 유실돼 집계 왜곡 발생 (리뷰 HIGH #1 지적).
  - **Layer 2 (isfinite 필수 가드)**: `returns = {n: df.where(np.isfinite(df)) for n, df in returns.items()}`. 집계 경로의 `series.dropna().mean()` 은 NaN 만 제거하고 inf 는 남기므로 단일 inf 가 평균을 `Decimal('Infinity')` 로 만듦. "방어선" 이 아니라 **필수** (리뷰 HIGH #2 지적).

### Added
- **회귀 테스트 2건** (`74938cf`, `tests/test_services.py`):
  - `test_backtest_handles_zero_close_price_without_infinity`: 기준일 `close=0` → `signal.return_Nd=None`, `BacktestResult` INSERT 성공 (NumericValueOutOfRangeError 미발생).
  - `test_backtest_preserves_minus_hundred_when_future_close_zero`: `base=10000, future=0` (d+5..d+20) → `return_Nd ≈ -100` 유지. 분모만 마스킹하는 설계가 전손 수익률을 보존함을 고정.

### Process Notes
- **`/ted-run` 파이프라인 첫 실측**: 구현 → 리뷰 → 빌드 → 커밋 4단계 자동 연결. 리뷰 단계에서 HIGH 2건 + MEDIUM 1건 지적받고 즉시 수정 반영. 리뷰어가 uncommitted 변경을 git tree 에서 못 읽는 툴링 제약은 있었지만, 지적 사항이 매우 구체적이라 수정 대조 + 회귀 테스트 통과로 효력 검증 가능했음.
- **리뷰 MEDIUM #2 (`_dec(val) or Decimal("0")` fragile 패턴)**: 사전 부채로 분류, 별도 PR 로 이관 가능.

---

## [2026-04-20] 시그널 튜닝 · 알림 가드 · 설정 페이지 복구 (`e6c4345` · `c344e89` · `6b3b56f`)

3-PR 세션: HANDOFF 1·2·3 순위 연속 완결 + 예상 외 프로덕션 버그 복구.
master 에 커밋 **3건** 추가 (PR #6·#7·#8 모두 머지 + delete-branch, CI 4/4 PASS × 3회).
백엔드 테스트 178 → **181** (신규 6건: NotificationService 필터·실패·no-op 5 + batch Step 3 배선 1,
테스트 스위트 내 기존 카운트 편차는 signal tuning 경계 +1 포함). E2E 31 → **38 케이스**
(A4 + F5 + I1~I5 = 7건 신규, 설정 페이지 E2E 최초 도입).

### Changed
- **시그널 탐지 임계값·가중치 재정비** (`e6c4345`, PR #6): 3년 백필 70,609 건에서 저등급 비중 과다(SHORT_SQUEEZE 81% C-grade, TREND_REVERSAL 22% D-grade, RAPID_DECLINE 62% A-grade 편향) 확인 후 기준치 상향.
  - RAPID_DECLINE: 임계 -10% → **-12%**, base 계수 `abs*3` → `abs*2.5`, 버퍼 `+20` → `+10`
  - TREND_REVERSAL: `score >= 50` 필터 신규 추가 (크로스 감지 후 품질 게이트)
  - SHORT_SQUEEZE: `MIN_SCORE` 40 → **60**
  - 예상 감소율: 70,609 → 30,234 (**-57.2%**). 기존 신호는 append 모델로 보존, 월요일 07:00 KST 스케줄러가 새 기준으로 재탐지하며 자연 검증.
- **설정 페이지 snake_case 통일** (`6b3b56f`, PR #8): `types/notification.ts` 만 camelCase 로 작성돼 있어 프로젝트 컨벤션(snake_case)에서 이탈. 전체 프로젝트와 일관화.
- **`.github/workflows/ci.yml` 에는 변경 없음** — 테스트 개수만 늘었고 워크플로는 기존 그대로 동작.

### Added
- **NotificationService 단위 테스트 5건** (`c344e89`, PR #7, `tests/test_notification_service.py`): `test_min_score_filter_drops_below_threshold` / `test_signal_types_filter_drops_disabled_types` / `test_telegram_disabled_skips_db_access` / `test_partial_send_failure_counts_successes_only` / `test_empty_signals_short_circuits_before_db`. 기존 테스트는 포매팅(N+1 방어 / HTML escape / 한글 라벨) 만 검증해 필터 조건 · 실패 처리 · no-op 경로가 회귀 무방비 상태였음.
- **batch 파이프라인 Step 3 통합 테스트** (`c344e89`, `tests/test_batch.py`): `test_pipeline_step3_dispatches_seeded_signal_to_telegram` — 사전 seed 된 시그널이 KRX 빈 응답 상황에서도 MockTransport 로 Telegram 호출까지 도달하는지 검증. `_notify` 콜백 배선 오류로 `sent=0` 조용히 실패하는 회귀를 감지.
- **RAPID_DECLINE 경계 테스트** (`e6c4345`, `tests/test_services.py`): `test_rapid_decline_ignores_minus_eleven_percent` — 새 -12% 임계에서 -11% 는 더 이상 신호가 아님을 명시적으로 고정.
- **E2E 설정 페이지 섹션 신규** (`6b3b56f`, PR #8, `tests/e2e/settings.spec.ts`): I1~I5 5 케이스 — 진입·채널 스위치 토글·시그널 타입 칩 토글·validation(`disabled` + 경고)·슬라이더 값 라벨 갱신. 저장 경로(I6)는 DB 싱글톤 mutation 격리 전략 확정 후 별도 PR.
- **E2E A4 · F5** (`6b3b56f`): `navigation.spec.ts` 에 NavHeader "설정" 링크 테스트 추가, `stocks.spec.ts` 에 차트 기간 배타 선택(1M/6M `aria-pressed` 상호배타) 검증 추가.
- **HomePage POM 확장**: `settingsLink` / `openSettings()` 추가로 설정 네비게이션 재사용 가능.

### Fixed
- **`/settings` 페이지 런타임 크래시 복구** (`6b3b56f`, PR #8): 백엔드 API 응답이 snake_case 인데 `types/notification.ts` 만 camelCase 로 작성돼 있어 `pref.signalTypes` 가 undefined → `.includes()` 호출 시 크래시. 로딩 스켈레톤 후 Chrome 에러 페이지 "This page couldn't load" 로 전환되던 상태. 타입·페이지·form state 를 전부 snake_case 로 통일해 복구. Next Route Handler(`/api/admin/notifications/preferences/route.ts`) 는 passthrough 라 수정 불필요. 기존 E2E 가 이 페이지를 안 건드려서 감지 못 했던 케이스 — I1~I5 가 이후 회귀 방어.

### Technical Notes
- **승인 루프 준수**: PR #6 은 A/B 옵션 제안 → A 선택 → 구현, PR #8 은 스코프 확장 제안(A/B/C) → A 선택 → 구현. 프로덕션 설정 페이지 버그 발견 시 "E2E 만 하고 덮기" 대신 "같이 수정" 을 사용자 확인 후 진행.
- **격리 전략 일관성**: NotificationService 테스트는 `httpx.MockTransport` + testcontainers + `db_cleaner` TRUNCATE, E2E 설정 테스트는 "로컬 React state 만 조작, 저장 PUT 안 누름" 으로 싱글톤 mutation 회피.
- **로컬 실측**: 각 PR 전 전체 pytest 175/181 pass, 최종 E2E 37/37 (H5 는 로컬 seed 미적용 환경 이슈로 제외, CI 에서는 seed 실행되므로 정상). ruff/mypy/tsc 전부 통과.

---

## [2026-04-20] 백테스트 주간 스케줄러 + E2E 실데이터 전환 (`ce0ecba` · `5ffef6d`)

2-PR 세션: 전 세션 carry-over 1순위였던 `backtest_result` 0건 기술부채 해소.
master 에 커밋 **2건** 추가 (PR #4·#5 모두 머지 + delete-branch, CI 4/4 PASS × 2회).
백엔드 테스트 174 → **178** (신규 4건: 스케줄러 등록 2 + 파이프라인 실적재 2),
E2E 30 → **31 케이스** (H5 실데이터 추가).

### Added
- **백테스트 주간 cron** (`ce0ecba`, PR #4): `app/batch/backtest_job.py` 신규 — `run_backtest_pipeline(period_end, period_years)` 래퍼 + `fire_backtest_pipeline` APScheduler 콜백. `app/batch/scheduler.py` 에 `backtest_enabled=True` 일 때 **월요일 07:00 KST** 트리거 등록 (`market_data` 06:00 배치 1시간 후 주 1회 실행, 직전 3년 재계산).
- **`Settings.backtest_*` 필드 5개** (`ce0ecba`): `backtest_enabled`/`backtest_cron_day_of_week`/`backtest_cron_hour_kst`/`backtest_cron_minute_kst`/`backtest_period_years` (기본 True · mon · 07:00 · 3년). `scheduler_enabled` 와 독립 — 전체 스케줄러는 켠 채 backtest 만 끌 수 있음.
- **`scripts/run_backtest.py` CLI** (`ce0ecba`): one-shot 수동 실행. `--from/--to` 명시 또는 `--years N` 로 직전 N년. 시드·수동 재실행 겸용. 엔진을 직접 호출하는 경로와 래퍼 경유 두 분기 분리.
- **`scripts/seed_backtest_e2e.py`** (`5ffef6d`, PR #5): SignalType 3종 × 삼성전자 기준 signal 1건씩 insert → `run_backtest_pipeline(period_years=1)` 호출. `(stock_id, signal_date, signal_type)` 중복 skip 으로 멱등. 005930 stock 미존재 시 graceful skip.
- **E2E H5 실데이터 케이스** (`5ffef6d`): stub 없이 `/backtest` 방문 → "대차 급감"·"추세 전환"·"숏스퀴즈" 3종 라벨 + "보유기간별 평균 수익률" 차트 h2 렌더 확인. H3/H4 는 미래 회귀 방어선으로 stub 유지.
- **유닛 테스트 4건** (`ce0ecba`): `test_build_scheduler_registers_backtest_cron_when_enabled` / `test_build_scheduler_skips_backtest_when_disabled` / `test_backtest_pipeline_persists_result_rows` (testcontainers + 시그널·가격 시드 → `backtest_result` 적재 검증) / `test_backtest_pipeline_handles_empty_period`.

### Changed
- **`.github/workflows/e2e.yml`** (`5ffef6d`): `Seed E2E accounts` 다음 단계로 `Seed backtest signals + run backtest` 추가. H5 가 이 시드 전제로 동작.
- **`app/main.py` lifespan 로그** (`ce0ecba`): backtest 스케줄(day_of_week/hour/minute) 포함하도록 보강.
- **`tests/test_batch.py`** (`ce0ecba`): 기존 `test_build_scheduler_registers_weekday_cron` 를 `backtest_enabled=False` 명시로 단독 검증 유지. unused import(`Any`, `AsyncMock`) 함께 정리.

### Fixed
- **ruff SIM117** (`5ffef6d` 작업 중): `seed_backtest_e2e.py` 의 중첩 `async with` 를 single 로 병합.

---

## [2026-04-19 → 2026-04-20] E2E · 데이터 버그 체인 · KIS mock · CI 녹색 (`99445b3` … `46f08bb`)

3-PR 세션: 포트폴리오 E2E 도입 → CI 첫 실행 녹색화 → 코드 리뷰 MEDIUM 5 + LOW 4 정리.
master 에 커밋 **21건** 추가 (PR #1·#2·#3 모두 머지 + delete-branch).
백엔드 테스트 158 → **175+** (신규 17건), E2E 0 → **30 케이스** 확보.

### Added
- **Playwright E2E 스위트 30 케이스** (`99445b3` · `eff2d65`): A(내비 3) + B(포트폴리오 리스트 7) + C(쓰기 2) + D(얼라인먼트 6) + E(에러 2) + F(주식 상세 4) + G(AI 리포트 2) + H(백테스트 4). Page Object Model 분리(`HomePage`·`PortfolioPage`·`AlignmentPage`). 3회 연속 로컬 통과 + CI 3회 녹색.
- **`GET /api/signals/latest` 엔드포인트**(`9523ee1`): 가장 최근 `signal_date` 기준 응답. 주말/공휴일 대시보드 빈 상태 회피. `SignalRepository.find_latest_signal_date` 추가.
- **시그널 탐지 백필 스크립트** `scripts/backfill_signal_detection.py`(`8712b3f`): `stock_price` DISTINCT trading_date 기반으로 752영업일 순회. 실측 12분 40초로 `signal` 70,609건 (RAPID 21,056 / TREND 6,242 / SQUEEZE 43,311) 적재.
- **KIS in-memory mock 모드**(`59b2320`): `Settings.kis_use_in_memory_mock=True` 시 `httpx.MockTransport` 자동 주입. KIS sandbox 1분 1회 rate limit 회피. 결정론적 보유 3종(삼성전자/SK하이닉스/NAVER) 반환. 유닛 테스트 2건(+5 기존).
- **E2E 전용 seed 스크립트** `scripts/seed_e2e_accounts.py`(`977ce43`): `brokerage_account`(e2e-manual/e2e-kis) + `portfolio_holding`(005930 10주) + 거래 1건 멱등 시드. CI `.github/workflows/e2e.yml` 의 seed 단계 연결.
- **stock_name 원타임 복구 스크립트** `scripts/fix_stock_names.py`(`b5b5119` · `f651a8d`): `get_market_price_change_by_ticker(market="ALL")` 1회 호출로 전종목 이름 확보. 3,098건 중 2,880건 복구.
- **CI 워크플로 `.github/workflows/e2e.yml`** (`99445b3`): compose up → seed → Caddy internal CA 신뢰 → Playwright → 아티팩트. `KIS_USE_IN_MEMORY_MOCK=true` 주입으로 외부 의존 0.
- **루트 `README.md`**(`99445b3`): 프로젝트 개요 · Quickstart · 파이프라인 커맨드.
- **문서 2건**: `docs/e2e-portfolio-test-plan.md` (테스트 계획서), `docs/data-state.md` (218건 미매칭 stock_name 현상유지 근거, 2026-04-16·17 lending T+1 지연 등 알려진 패턴).
- **유닛 테스트**: `test_market_data_lending_deltas.py` 10건(`177f014`) + `test_kis_client.py` in-memory mock 2건(`59b2320`).
- **`/signals` pagination limit** (`b46371b`): `limit` 쿼리 파라미터(기본 500, 최대 5000). `/signals`·`/signals/latest` 양쪽.

### Changed
- **대시보드 `/` 데이터 소스**(`9523ee1`): `getSignals()` → `getLatestSignals()`. 헤더에 실제 `signal_date` 표시 (오늘이 아니라 최근 탐지일).
- **`ci.yml` Java → Python 이전 반영**(`e7a39ae`): 삭제된 `src/backend/`(Gradle) 참조를 `src/backend_py/`(uv + pytest) 로 교체. `--extra dev`(`e69cfa3`) 로 pytest/testcontainers 설치 보장.
- **lending deltas 헬퍼 모듈 레벨 승격**(`235ab06`, M4+M5): `_fetch_prev_lending` / `_compute_lending_deltas` 를 `MarketDataCollectionService` 에서 모듈 레벨 private 함수로 추출. `prev: object | None` → `LendingBalance | None` 로 타입 정밀화 — `getattr` 우회 제거, mypy strict 가 향후 필드 리네임 감지.
- **`build_stock_name_map` public 승격**(`f651a8d`, M2): 외부 스크립트가 `noqa: SLF001` 로 호출하던 private 메서드를 정식 API 로.
- **E2E D3/D4 실데이터 전제 반영**(`795f3b3`): 시그널 재탐지로 삼성전자에 시그널이 채워짐 → D3 계좌 id=1→2(e2e-kis, 보유 0) 로 전환, D4 초기 empty state 단언 제거.
- **E2E D1 하드코딩 제거**(L3, `ce1044c`): `/portfolio/1/alignment` → `/portfolio/\d+/alignment` 정규식 매칭으로 seed 순서 독립.
- **E2E C2 KIS 응답 stub**(`eff2d65`): 실 sandbox 의존 제거.

### Fixed
- **대차잔고 pykrx 컬럼 오매핑**(`9ed7d86`): `_to_lending_balance_row` 가 `잔고수량`/`BAL_QTY` 만 찾던 것을 **`공매도잔고` / `공매도금액`** 최우선으로 변경. 기존 컬럼명은 fallback 유지. 668,322행이 전부 `balance_quantity=0` 이던 원인 제거.
- **change_rate / change_quantity / consecutive_decrease_days 계산 누락**(`9ed7d86`): `market_data_service` 가 대차잔고 upsert 시 변동률을 계산하지 않던 버그 → `_fetch_prev_lending` + `_compute_lending_deltas` 추가. 3년 재수집 후 `change_rate` 335,863건, RAPID_DECLINE 후보(≤-10%) 21,056건.
- **stock_name 수집 누락**(`b5b5119`): `get_market_ohlcv_by_ticker` 가 종목명 컬럼을 반환하지 않아 α 초기부터 3,093건이 공백이던 문제 → `build_stock_name_map()` 추가 호출로 영구 해결.
- **`_IN_MEMORY_TOKEN` 문서화 주석** (M1, `7e48e01`): 보안 스캐너 false-positive 예방 주석 추가.
- **`backfill_signal_detection.py` 루프 내부 `import json`** (L1, `ce1044c`): 파일 헤더로 이동.
- **`seed_e2e_accounts.py` 경고 메시지 명확화** (L2, `ce1044c`): "보유·거래 시드 모두 skip" 명시.
- **CI `.env.prod` cleanup** (L4, `ce1044c`): Tear down 단계에 `rm -f .env.prod` 추가.

---

## [2026-04-19 — 저녁] E2 + i + 3년 백필 스크립트 (`93a88ec` … `c71a0fc`)

차기 세션 carry-over 2건(DART 단축명 필터 · KRX stock_name/market_type)을 병렬 처리하고, 3년(752영업일) 실데이터 백필 스크립트를 구현·기동. 백필 자체는 백그라운드 약 2시간 실행(완료 보고는 차기 세션). 백엔드 테스트 146 → **158**.

### Added
- **`EXCLUDED_STOCK_CODES` 블랙리스트**(`93a88ec`): `sync_dart_corp_mapping` 에 명시 제외 코드 셋 (`088980` 맥쿼리인프라, `423310` KB발해인프라). DART 단축명이 기존 이름 패턴에 매칭되지 않는 케이스 보완. "인프라" 로 패턴 확장 시 "현대인프라코어" 등 오탐 위험으로 지양.
- **KRX market_type 매핑**(`93a88ec`): `KrxClient._build_market_type_map` 가 KOSPI/KOSDAQ 티커 리스트 2회 조회로 dict 구성. `_to_stock_price_row` 가 market_type 을 주입받아 row 컬럼 미존재 시에도 정확 매핑.
- **`StockRepository.upsert_by_code` 보호 규칙**(`93a88ec`): 빈 `stock_name` 은 기존 row 의 이름을 덮어쓰지 않음. β 가 시드한 5 핵심 종목 이름이 α 재실행으로 공백화되는 회귀 차단.
- **`scripts/backfill_stock_prices.py`**(`c71a0fc`): urllib 기반 CLI. `POST /api/batch/collect?date=...` 를 영업일 역순(오름차순 정렬 후 실행)으로 순회. 기본 752영업일. 중간 실패는 개별 날짜만 기록하고 진행. 배치 내부가 upsert 멱등이라 재실행 안전.
- **테스트 8건**: E2 2건(코드 블랙리스트 경계값) + i 3건(KOSDAQ 매핑·upsert 이름 보존 2종) + 백필 3건(business_days_back) + 기존 KRX 테스트 3건에 `get_market_ticker_list` stub 확장.

### Verified (실측)
- **E2 블랙리스트 동작 확인** — `sync_dart_corp_mapping --dry-run` 재실행 시 DART 기본 3,654 → 3,653 (088980 제거), KRX 교차 후 2,538 → 2,537. 블랙리스트 1건 반영(423310 은 DART corpCode.xml 미등재이거나 KRX 상장 리스트 외로 이미 제거된 상태로 추정).
- **3년 백필 완료** — Bash id `bh6enx6xu`, 총 **752영업일 · 성공 752 · 실패 0 · 소요 125분 38초**. DB 최종 상태: `stock_price` 2,130,316 rows × 752 days (2023-06-01~2026-04-17), `short_selling` 718,997 rows × 752 days, `lending_balance` 668,322 rows × 699 days(공휴일/스키마 이슈 53일 제외), `distinct stock` 3,098 (현재 상장 2,879 + 과거 상장/폐지 219).
- **`lending_balance` 스키마 불일치 범위 축소 관찰** — α 에서 2026-04-17 은 0건이었지만 과거 날짜(2023-11~)는 952건 정상. 즉 pykrx 의 schema drift 가 최근 날짜에 국한되어 과거 시계열에는 영향 없음. carry-over 범위 대폭 축소.

---

## [2026-04-19 — 오후] α 부분 성공 + KRX 어댑터 버그 2건 긴급 수정 (`bb8d2f2`)

α(KRX 실데이터 배치 실행 → stock 마스터 복구) 시도 중 pykrx 1.2.x 와 어댑터 간 스키마 드리프트 2건을 발견·수정. 배치 재실행으로 KOSPI+KOSDAQ stock 마스터 2,879건과 2026-04-17 주가를 실데이터로 적재. 단 `get_market_ohlcv_by_ticker(market=ALL)` 이 종목명·시장구분을 반환하지 않아 2,874건의 `stock_name` 이 공백·`market_type` 이 단일 'KOSPI' 로 저장되는 잔여 이슈 발생(carry-over i). β 재실행으로 5 핵심 종목 이름만 긴급 복구해 UI 회귀는 차단.

### Fixed
- **pykrx 1.2.x 시가총액 컬럼 충돌**(`bb8d2f2`): `fetch_stock_prices` 에서 `get_market_ohlcv_by_ticker` 가 이미 `시가총액` 컬럼을 반환하는 상황에서 `get_market_cap_by_ticker` 결과를 무조건 join 해 `pandas.merge` 가 `ValueError: columns overlap` 으로 실패. `ohlcv.columns` 에 `시가총액` 이 있으면 cap 조회 자체를 건너뛰도록 조건부 분기. HANDOFF carry-over "KRX pykrx 스키마 불일치" 의 일부.
- **KOSDAQ 누락**(`bb8d2f2`): `get_market_ohlcv_by_ticker` 의 `market` 기본값 `"KOSPI"` 때문에 KOSDAQ/KONEX 가 통째로 빠져 `stocks_upserted` 가 949(KOSPI만)에 머물렀음. `market="ALL"` 명시로 2,879건으로 확대.

### Verified (실측)
- **배치 재실행 결과**: `POST /api/batch/collect?date=2026-04-17` HTTP 200. `stocks_upserted=2879 · stock_prices_upserted=2879 · short_selling_upserted=949 · lending_balance_upserted=0 · elapsed_ms=5302`.
- **5 핵심 종목 이름 복구**: β 재실행으로 005930/000660/035420/035720/068270 의 `stock_name` 복구 확인. 나머지 2,874건은 공백 유지.
- **신규 테스트 1건**: inline `시가총액` 케이스에서 `get_market_cap_by_ticker` 호출 0회 확인. KRX 테스트 4 → 5로 확장.

### Known Issues (carry-over)
- **i. stock_name·market_type 대량 누락** — `get_market_ohlcv_by_ticker(market=ALL)` 이 DataFrame 에 종목명/시장구분을 포함하지 않음. `get_market_ticker_list(market=KOSPI|KOSDAQ)` 로 시장별 티커 집합을 얻어 market_type 을 매핑하고, `get_market_ticker_name(ticker)` 루프 또는 batch API 로 이름을 병합해야 한다. 2,874건 영향. 별도 작업으로 이관.

---

## [2026-04-19 — 낮] Z(E 실측) + β(UI 시드) 병렬 수행 — UI 파생 지표 복구 (`a494863`)

직전 커밋에서 구현한 E(KRX 교차 필터)의 실측과, 데이터 부재로 `—` 를 표시하던 포트폴리오 UI 의 수익률/MDD 카드를 복구하기 위한 데모 시드를 병렬로 처리. backend 재빌드 → Z 실측 → β 스크립트 구현 → DB 적재 → 브라우저 확인까지 한 트랙에서 완결.

### Added
- **`scripts/seed_ui_demo.py`**(`a494863`): UI 회귀 검증 전용 CLI. 5개 대표 종목(삼성전자/SK하이닉스/NAVER/카카오/셀트리온) × 최대 90 영업일 OHLCV 를 결정론적 random-walk(seed 고정)로 생성해 `stock_price` 에 upsert. 활성 계좌 × 날짜별 `portfolio_snapshot` 을 현재 보유수량 × 해당일 종가로 재구성. `--wipe` 는 stock 마스터를 건드리지 않고 기간 내 시세/스냅샷만 정리(portfolio_holding 참조 관계 보존).
- **신규 테스트 10건**: `business_days_back` 주말 제외/순서/개수, `generate_price_series` 결정론/시드별 차이/OHLC 불변식/충분한 변동폭, `DEMO_STOCKS` 유효성 등.

### Verified (실측)
- **Z: KRX 교차 필터 실환경 동작** — `scripts.sync_dart_corp_mapping --dry-run` 결과 DART 3,654 → KRX 교집합 **2,538건**(1,116건 축소). pykrx 로그인 성공 로그 확인 (`KRX 로그인 ID: withwooyong` · 만료 1시간).
- **β: 시드 적재 및 UI 복구** — `stock 5 · stock_price 450 · portfolio_snapshot 90` 적재. `https://localhost/portfolio` 에서 누적 수익률(3M) = **+5.31%** (빨강, 한국 관습), MDD(3M) = **-10.23%** (파랑) 정상 렌더링. UI 의 파생 지표 경로(Metric 카드·색상 코딩·포맷팅) 전부 동작 확인.

### Observed (차후 개선)
- **`.env.prod` KRX 크리덴셜 이미 존재** — Z 실측 중 드러남. α 작업이 사실상 즉시 실행 가능 상태이며 stock 마스터를 실데이터로 복구 가능.
- **DART 단축명 매칭 누락** — 필터 패턴 `"인프라투융자회사"` 가 DART 가 저장한 단축명 `"맥쿼리인프라"` 와 매칭 실패. 해당 종목(088980)이 그대로 통과. 패턴에 단축명 추가 필요.
- **wipe 가 stock 마스터 보존해야 하는 제약** — `portfolio_holding.stock_id` FK 때문에 stock 선삭제 불가. 시드 스크립트는 기간 내 `stock_price`/`portfolio_snapshot` 만 정리하고 stock 은 upsert 경로로 덮도록 설계.

---

## [2026-04-19 — 오전] P13-3 AI 리포트 rate limiting + P13-4 KRX 교차 필터 + DB 벌크 upsert 실행 + UI 실측 (`3e44ab6` … `e6d79e6`)

바로 전 세션에서 구현한 P13-1/P13-2 의 실측 검증을 마무리한 뒤, 동일 세션 내에서 **(A) DART 벌크 sync 본실행 → (B) AI 리포트 엔드포인트 slowapi rate limiting → (D) 포트폴리오 UI 실측 → (E) KRX 현재 상장 교차 필터** 4건을 순차·병렬 처리. DB 에 실데이터 3,654건 적재, 백엔드 테스트 131→135건으로 확장.

### Added
- **slowapi rate limiting**(`3e44ab6`): `POST /api/reports/{stock_code}` 에 관리자 키 단위 쿼터(기본 30/min). `app/adapter/web/_rate_limit.py` 의 Limiter 싱글톤은 `X-API-Key` 우선, 부재 시 remote IP fallback. `RateLimitExceeded` → 429 + `Retry-After: 60` 헤더. 설정값 `AI_REPORT_RATE_LIMIT` 로 env override.
- **KRX 현재 상장 교차 필터**(`e6d79e6`): `scripts/sync_dart_corp_mapping.py` 에 `fetch_krx_listed_codes()` 추가 — pykrx 로 KOSPI+KOSDAQ 조회 후 DART 결과와 교집합. `--no-cross-filter-krx` 로 비활성화 가능. pykrx 실패 시 빈 집합 반환 + stderr 경고로 fallback.
- **테스트 5건**: rate limit(1) + KRX 교차·fallback·pykrx 성공·실패(4).

### Verified (실측)
- **A: DART 벌크 sync 본실행** — `docker compose exec backend python -m scripts.sync_dart_corp_mapping` 로 3,654건 upsert 완료. 주요 종목 005930/000660/035420 매핑 확인. 배치 500건 단위 8회 반복, 총 소요 ~30초.
- **D: 포트폴리오 UI** — `https://localhost/portfolio` 접속 → 계좌 탭(`e2e-manual`/`e2e-kis`) 렌더링 · 삼성전자 10주 보유 테이블 정확 · AI 리포트 버튼 동작 → `/reports/005930` 캐시 본문 렌더링 확인. 단 수익률/MDD 카드는 `—` (stock 마스터 0 rows + 주가 시계열 없음 — KRX 익명 차단 carry-over 파급).

### Observed (차후 개선)
- **UI 실측의 데이터 의존 한계** — 라우팅/컴포넌트/상태 층은 UI 만으로 검증 가능하지만, 파생 지표(수익률, MDD, 시그널 정합도, 백테스트)는 stock_price 시계열 필요. 근본 원인은 KRX 익명 차단 2026-04 전면화. 해결 경로: α) KRX 회원 크리덴셜, β) 수동 시드, γ) KIS REST 주가 조회 전환.
- **slowapi 메모리 스토리지** — 단일 uvicorn 프로세스 전제. multi-worker 확장 시 Redis 백엔드 전환 필요.
- **상장폐지 종목 3,654건 혼재** — E 구현으로 해소 가능. 다음 sync 실행 시 KRX 상장 ~2,500건 수준으로 축소 예상(실측은 차기 과제).

---

## [2026-04-18 — 새벽] P13-1 DART 벌크 sync 스크립트 + P13-2 운영 보안 M1~M4 + 실측 검증 (`43f07fd` … `1c27c65`)

수동 시드 3건에 머물던 `dart_corp_mapping` 을 전체 bulk sync 할 수 있는 CLI 스크립트를 구현하고, 이전 세션에서 carry-over 된 운영 보안 4건(M1 /metrics IP 게이팅 · M2 /health 마스킹 · M3 uv digest 고정 · M4 nologin 셸)을 일괄 처리. backend 재빌드 + Caddy reload 후 실 환경에서 **DART API 호출**과 **외부/내부 경로 차단 동작**을 실측 검증 완료.

### Added
- **`DartClient.fetch_corp_code_zip()`**(`43f07fd`): DART `/api/corpCode.xml` ZIP 바이너리 다운로드. `PK\x03\x04` 매직으로 성공 분기, JSON 바디는 `DartUpstreamError` 승격. 읽기 타임아웃 60초(수 MB 전송 고려), tenacity 3회 재시도.
- **`scripts/sync_dart_corp_mapping.py`**(`43f07fd`): CLI 진입점. `--dry-run` / `--batch-size` 옵션. 필터 2단: ① 종목코드 6자리 + 끝자리 `0` (보통주) ② 이름에 스팩·기업인수목적·리츠·부동산투자회사·인프라투융자회사·ETF·ETN·상장지수 미포함. 500건 배치 upsert.
- **`/internal/info` 엔드포인트**(`1c27c65`): app/env 상세 응답. Caddy 에서 `/internal/*` 차단하므로 Docker 네트워크 내부에서만 접근.
- **신규 테스트 31건**(`43f07fd`): 필터 파라미터라이즈 (보통주/우선주/스팩/리츠/ETF 경계값) + ZIP/XML 파싱 + `fetch_corp_code_zip` httpx.MockTransport 3종.

### Changed
- **`/health` 응답 본문 마스킹**(`1c27c65`): `{"status":"UP","app":...,"env":...}` → `{"status":"UP"}` 만. 운영 메타는 `/internal/info` 로 이동.
- **Caddy `/metrics`, `/internal/*` 외부 404**(`1c27c65`): `@blocked` matcher + `handle` 블록. frontend 프록시 경로와 무관하게 defense-in-depth.
- **uv 이미지 digest 고정**(`1c27c65`): `ghcr.io/astral-sh/uv:0.11` → `@sha256:240fb85a…516a` (multi-arch index). 공급망 공격 방어. 업그레이드 절차 주석 명시.
- **appuser 로그인 셸**(`1c27c65`): `/bin/bash` → `/usr/sbin/nologin`. login/su/sshd 경로 차단.

### Verified (실측)
- **E: DART 벌크 sync `--dry-run`** — 실 API 호출 성공. ZIP 3.5 MB · 전체 116,503 법인 → stock_code 보유 3,959건 → 필터 통과 **3,654건**. 샘플 10건 출력에서 과거 상장폐지 종목이 다수 혼재 확인(예상보다 많은 이유: corpCode.xml 이 폐지 이력도 유지).
- **F-1/F-2: 외부 차단** — `curl -k https://localhost/metrics` → HTTP 404 · `/internal/info` → HTTP 404. Caddy `@blocked` matcher 동작 확인.
- **F-3: 내부 응답 분리** — 컨테이너 내부에서 `/health` = `{"status":"UP"}`, `/internal/info` = `{"status":"UP","app":"ted-signal-backend","env":"prod"}` 정상.
- **F-4: nologin 적용 범위** — `/etc/passwd` 에 `/usr/sbin/nologin` 확인. `docker exec backend /bin/bash` 는 여전히 실행됨(설계 범위 밖 — nologin 은 login/su/sshd 경로 차단 전용). MVP 단계 적정.

### Observed (차후 개선)
- **Docker Desktop bind mount 휘발성** — 에디터의 rename-on-save 로 inode 가 바뀌면 컨테이너 mount 가 stale. Caddy reload 전에 **컨테이너 재시작 필수**(`docker compose restart caddy`). Caddyfile 수정 절차에 반영 필요.
- **상장폐지 종목 혼재** — `dart_corp_mapping` 에 과거 폐지 종목도 포함. AI 리포트 대상은 실제 호출자가 현재 상장 종목만 쿼리하므로 실사용 영향 없음. 필요 시 KRX 현재 상장 리스트와 교차 필터 추가 가능.

---

## [2026-04-18 — 심야] 실 E2E 검증 + 3건의 크리티컬/MEDIUM 버그 수정 (`2febdf2` … `510fa1c`)

`.env.prod` 의 실 DART/OpenAI/KIS 모의 키로 `docker compose --env-file .env.prod up -d --build` 풀 재빌드 후 엔드투엔드 검증. 포트폴리오 계좌 생성 → 수동 거래 → KIS 모의 동기화(OAuth+VTTC8434R) → **삼성전자 AI 리포트 실생성 (gpt-4o, 6.3초, 18524/530 토큰, DART 공시 5건 자동 소스 보강)** 까지 풀 체인 성공. 2차 호출 `cache_hit=true` 0.02초. 검증 과정에서 발견한 3건의 실버그를 같은 세션에 수정·검증 완료.

### Fixed
- **CRITICAL: entrypoint.py 레거시 경로가 003/004/005 누락**(`2febdf2`): `alembic_version` 없고 `stock` 있는 레거시 Java Flyway DB 에서 `stamp head` 만 실행 → P10~P13b 의 portfolio_* / dart_corp_mapping / analysis_report 5 테이블이 생성되지 않음. 수정: `stamp 002_notification_preference` (V1+V2 완료 마킹) → `upgrade head` (003/004/005 적용). Phase 7 E2E 테스트(testcontainers fresh DB) 가 stamp 경로를 타지 않아 놓친 사각지대. runbook §2.4 동시 갱신.
- **MEDIUM: `scripts/validate_env.py` KIS 계좌번호 기준 느슨**(`2febdf2`): `acct_digits >= 8` → 8자리도 PASS. 어댑터 실요구는 CANO(8) + ACNT_PRDT_CD(2) = `== 10`. 거짓 음성 버그. 수정: `== 10` 으로 정확히 + 미달/초과별 안내 메시지.
- **CRITICAL: REPORT_JSON_SCHEMA sources.items 의 required 에 `published_at` 누락**(`510fa1c`): OpenAI strict mode 는 `required` 배열에 **모든** properties 키가 포함되어야 함. `/chat/completions` 가 HTTP 400 "Missing 'published_at'" 으로 거부해 리포트 생성 실패. 수정: required 에 published_at 추가 (type: [string, null] 로 이미 nullable 선언).

### Known Outcomes (E2E 검증 통과)
- 관리자 릴레이: `POST /api/admin/portfolio/accounts` 201 (Caddy HTTPS + Next.js Route Handler + backend 경로 전체 동작)
- 포트폴리오 거래 등록: 매수 10주@72000 → `GET /holdings` 200 (평단·수량 정확)
- KIS 모의 동기화: OAuth client_credentials 토큰 발급 → VTTC8434R 잔고 조회 rt_cd=0 → `fetched_count=0` (모의 잔고 없음, 정상 응답)
- AI 리포트 실생성: gpt-4o 모델 · 6.3초 · 토큰 18,524↓/530↑ · opinion=HOLD · sources 7건 전부 Tier1 (DART 공시 5 + 공식 홈페이지) · 자동 소스 보강 검증 · 24h 캐시 2차 호출 0.02s
- 레거시 DB 위에서 entrypoint 자동 마이그레이션 003/004/005 적용 확인

---

## [2026-04-18 — 저녁~밤] Phase 8/9 마무리 + §11 신규 도메인(P10~P15) + 프론트 UI + 리뷰 대응 (`24b43ba` … `7f4f3d1`)

이전 세션에서 Phase 1~7 으로 Java→Python 런타임 이전을 마친 데 이어, 본 세션은 **Phase 8/9 정리 + §11 (포트폴리오·AI 분석 리포트) 신규 도메인 전체 + 프론트 UI + 코드 리뷰 대응** 을 단일 세션에 완결. 커밋 12개 · 약 +7,120 / -5,141 라인 (Java 삭제 4,710 포함) · 백엔드 98/98 PASS · mypy strict 0 · ruff 0 · 프론트 build/tsc/lint clean.

### Removed
- **Phase 8 — Java 스택 물리 제거**(`24b43ba`): `src/backend/` 디렉토리 전량 삭제 (Spring Boot 3.5 + Java 21 + Gradle + 테스트 69개 포함 4,710 라인). 2026-04 Java→Python big-bang 이전 완결. Python 52/52 PASS 로 대체 검증 완료.

### Added
- **Phase 9 — 기술스택 문서/에이전트 Python 전환**(`005011e`): `CLAUDE.md` Tech Stack 표 + Backend Conventions(PEP 8·ruff·mypy strict·Pydantic v2·SQLAlchemy 2.0 async·APScheduler) + Key Design Decisions 전면 재작성. `docs/design/ai-agent-team-master.md` 기술 스택 확정 표 FastAPI/Python 전환 + Part V(부록 I~L, Java 21 Virtual Threads/JPA/QueryDSL) **역사적 기록·비활성** 배너 부착. `agents/08-backend/AGENT.md` 전면 재작성. `pipeline/artifacts/10-deploy-log/runbook.md` 내부 포트 8080→8000, /actuator/health→/health, Flyway→Alembic + entrypoint, KRX_AUTH_KEY→KRX_ID/KRX_PW 등 갱신.
- **P10 — 포트폴리오 도메인**(`97203c2`, +1,439): Alembic 003 (brokerage_account/portfolio_holding/portfolio_transaction/portfolio_snapshot 4 테이블 + UNIQUE/CHECK/인덱스). 모델 4종 + Repository 4종 + UseCase 4종 (RegisterAccount/RecordTransaction(가중평균 평단가)/ComputeSnapshot/ComputePerformance — pandas cummax/pct_change 벡터 연산으로 MDD·Sharpe). FastAPI 라우터 7 엔드포인트. 테스트 11 케이스.
- **P11 — KIS 모의투자 REST 연동**(`c003fc8`, +774): `KisClient` (httpx + OAuth2 `client_credentials` 토큰 캐시·300초 전 자동 재발급, TR_ID VTTC8434R 모의 전용, 실거래 URL 진입 차단, tenacity 재시도). `SyncPortfolioFromKisUseCase` — connection_type='kis_rest_mock' + environment='mock' 이중 검증, 잔고→holding 직접 upsert. Settings 에 KIS_APP_KEY_MOCK/SECRET/ACCOUNT + base_url 하드코드. 테스트 9 케이스.
- **P12 — 포트폴리오↔시그널 정합도 리포트**(`11e80c2`, +343): `SignalRepository.list_by_stocks_between` — IN + 기간 + min_score 복합 쿼리로 N+1 회피. `SignalAlignmentUseCase` — 종목별 max_score·hit_count 집계·정렬. `GET /api/portfolio/accounts/{id}/signal-alignment` 라우터. 테스트 5 케이스.
- **P13a — DART OpenAPI Tier1 어댑터**(`b2c20f4`, +711): Alembic 004 (`dart_corp_mapping` — KRX 6자리↔DART 8자리 매핑). `DartClient` — fetch_company/fetch_disclosures/fetch_financial_summary 3 엔드포인트, status='000'|'013' 만 통과 (그 외 `DartUpstreamError` 승격), 괄호 표기 음수·천단위 쉼표 Decimal 안전 변환, populate_existing upsert 패턴. 테스트 9 케이스.
- **P13b — AI 분석 리포트 파이프라인**(`caf8355`, +1,484): Alembic 005 (`analysis_report` JSONB content/sources, (stock_code, report_date) UNIQUE 로 24h 캐시). `LLMProvider` Protocol (`app/application/port/out/llm_provider.py`) + Tier1/Tier2 dataclass + REPORT_JSON_SCHEMA strict JSON. `OpenAIProvider` (Plan B, httpx `/v1/chat/completions` + `response_format=json_schema`, 역할 분리 시스템 프롬프트 "숫자는 Tier1 만, 정성은 Tier2 만 인용"). `AnalysisReportService` — 24h 캐시 조회 → dart_corp_mapping 해결 → DART 3종(company/disclosures 90d/financials 전년 CFS) + KRX 가격·시그널 Tier1 수집 → provider.analyze → 자동 소스 보강(공식 홈페이지 + 최근 공시 3건) → upsert. `POST /api/reports/{stock_code}` 라우터 (Admin Key 보호, force_refresh 쿼리, 404/400/502 매핑). 테스트 9 케이스.
- **P14 — 프론트 포트폴리오·AI 리포트 UI**(`3cd5c75`, +1,349): Next.js 16 + React 19. `/portfolio` (계좌 스위처 + 4 지표 카드 + 스냅샷/KIS 동기화 액션 + 보유 테이블 + AI 리포트 바로가기), `/portfolio/[accountId]/alignment` (시그널 정합도 상세, 스코어 슬라이더 필터), `/reports/[stockCode]` (AI 리포트 본문 — BUY/HOLD/SELL 컬러 뱃지, 강점/리스크 2열, 출처 Tier1/2 뱃지 + 외부 링크, 재생성 버튼). 제네릭 Route Handler `/api/admin/[...path]` (GET/POST/PUT/DELETE/PATCH, ADMIN_API_KEY 서버 측 부착, 64KB 본문 상한). API 클라이언트 2 (portfolio/reports) + 타입 2 (portfolio/report, snake_case 백엔드 정렬). NavHeader 에 '포트폴리오' 메뉴 추가.
- **P15 — 키움 REST 가용성 조사**(`7f4f3d1`, +177): `docs/research/kiwoom-rest-feasibility.md` — 문서 스파이크 전용 (구현 없음). 2026-04 공식 도메인 `openapi.kiwoom.com`, 모의 `mockapi.kiwoom.com`, Python SDK `kiwoom-rest-api` 0.1.12 미성숙 확인. KIS vs 키움 11항목 비교 매트릭스. **결론: No-Go**. Go 조건 3/3 (개인 키움 계좌 수요 + SDK 0.2+ 성숙 + KIS 어댑터 계약 고정) 충족 시 재평가. 플랜 §11.1 의 `developers.kiwoom.com` 오기 정정.

### Fixed
- **P13b 리뷰 fix**(`185dfaf`): mypy strict HIGH 5 (cast dict[str, Any], list[ReportSource] 제네릭, -> ReportSource 반환 타입) + 보안 MEDIUM 4 (`is_safe_public_url` 유틸로 javascript:/ftp:/file: 스킴 차단, OpenAI 에러 본문 외부 누설 제거 — body 는 logger.warning 만, `openai_base_url` HTTPS 스킴 강제로 SSRF 차단, `<tier1_data>`/`<tier2_data>` XML-like fence 로 프롬프트 인젝션 완화). 테스트 3 케이스 추가.
- **P14 리뷰 fix**(`c008592`): HIGH 3 (릴레이 path 세그먼트 `^[A-Za-z0-9_\-.]+$` allowlist + `.`/`..` 명시 거부 — undici collapse 로 /api/ 스코프 탈출 SSRF 차단, reports 페이지 `cancelled` 플래그 + `refreshTick` idempotent 재생성 패턴으로 race 제거, `SourceRow` `safeHref` 로 javascript: URI 브라우저 실행 차단) + MEDIUM 4 (refreshCurrent 에러 투명 전파, `aria-label` 새 탭 안내, `ADMIN_BASE`/adminCall 공용 헬퍼 추출, accountId NaN 가드).

### Changed
- **cleanup: mypy strict 0 · ruff 0 · frontend 타입 스키마 정합**(`51bfe10`, +332/-232): 백엔드 mypy 23→0, ruff 17→0. `pandas-stubs`/`types-python-dateutil` dev deps. StrEnum 4종 전환. Repository 공용 `rowcount_of()` 헬퍼. 외부 클라이언트 forward-ref 따옴표 제거(UP037). KIS/DART Any 반환 isinstance/cast 좁히기. market_data_job 파라미터 full 타입 힌트. 프론트 `signal.ts`/`SignalCard`/`page.tsx`/`stocks/[code]/page.tsx`/`backtest/page.tsx` snake_case 백엔드 응답과 정렬, `SignalDetail` + `detailNumber()` JSONB 안전 접근, `StockDetail` 가짜 `latestPrice/timeSeries` 구조 → 실제 `stock{}/prices[]` 로 정정, CountUp `queueMicrotask` 로 React 19 린트 해소.

### Known Issues / Follow-up
- `POST /api/reports/{stock_code}?force_refresh=true` 에 rate limiting 없음 — 관리자 키만으로 LLM 호출 폭주 가능. `slowapi` 도입 권고 (리뷰 LOW).
- 실 E2E 검증 미완: `.env.prod` 의 실 DART/OpenAI/KIS 키로 브라우저에서 `/portfolio` → AI 리포트 생성까지 1회 검증 필요.

---

## [2026-04-18 — 오후~저녁] Java→Python 전면 이전 Phase 1~7 일괄 완료 (`c417977` … `610918a`)

본 세션의 주제: **Spring Boot 3.5 + Java 21** 백엔드를 **FastAPI + Python 3.12** 로 전면 이전.
사전-운영 단계라는 결정적 이점으로 big-bang 재작성 경로를 선택. 18 영업일 추정 중 ~7일 분량을 진행.
전체 52/52 PASS · 로컬 Docker 스모크 확인 · 커밋 13회 · 약 7,400+ 라인 신규.

### Added
- **작업계획서 확정**(`f66cfdd`): `docs/migration/java-to-python-plan.md` — 9 결정 잠금, §11 포트폴리오 + AI 분석 스코프, Perplexity+Claude Plan A / OpenAI GPT-5.4 단독 Plan B 구분, DART+KRX+ECOS Tier1 / web_search 화이트리스트 Tier2 신뢰 출처 3-Tier 설계. 루트 `.env.prod.example` DOMAIN/ACME_EMAIL/DART/OPENAI/KIS 변수 확장.
- **환경변수 검증 스크립트**(`cb5bd24`): `scripts/validate_env.py` — `.env.prod` 의 DART/OpenAI/KIS 키를 API 실호출로 검증. 키 값 절대 로그에 노출되지 않도록 pykrx 내부 print 까지 `contextlib.redirect` 로 차폐.
- **KRX 계정 유효성 검증 스크립트**(`127625d`): `scripts/validate_krx.py` — pykrx 로그인 + OHLCV·공매도·대차잔고 수신 실측.
- **픽스처 베이스**(`cb5bd24`): `pipeline/artifacts/fixtures/` — `capture_krx.py` + 합성 JSON 3종 + Telegram 모의본 + KRX 익명 차단 블로커 문서.
- **Phase 1 Python 백엔드 스캐폴딩**(`e669fed`): `src/backend_py/` Hexagonal 구조, uv + FastAPI + pydantic-settings + prometheus-fastapi-instrumentator + structlog + pytest + ruff + mypy strict, Dockerfile (python:3.12-slim 멀티스테이지 + 비루트 uid 1001). Health/CORS 테스트 6종.
- **Phase 2 DB 계층**(`f00b2cf`): SQLAlchemy 2.0 async + asyncpg(런타임) + psycopg2(마이그레이션), Alembic V1/V2 리비전 이식, 모델 7종(Stock/StockPrice/ShortSelling/LendingBalance/Signal/BacktestResult/NotificationPreference) + Repository 7종, testcontainers PG16 통합 테스트 7종, macOS Docker Desktop 소켓 자동 감지.
- **Phase 3 외부 어댑터**(`e9f3c75`): `KrxClient` (pykrx async 래퍼 + asyncio.Lock + 2초 rate limit + stdout 차폐 + tenacity 재시도), `TelegramClient` (httpx AsyncClient + HTML parse_mode + no-op fallback). 어댑터 테스트 8종.
- **Phase 4 UseCase/서비스**(`3724d1e`): `MarketDataCollectionService`, `SignalDetectionService` (pandas rolling MA 벡터화), `BacktestEngineService` (피벗 테이블 + shift(-N) 벡터 리라이트 — Java TreeMap 순회를 행렬 1회 연산으로 대체), `NotificationService`. Port Protocol 정의. pandas/numpy/vectorbt 의존성 추가. 서비스 통합 테스트 5종.
- **Phase 5 API 계층**(`31ea518`): `app/adapter/web/` — FastAPI 라우터 8개(GET `/api/signals`, GET `/api/stocks/{code}`, POST `/api/signals/detect`, GET·POST `/api/backtest`, GET·PUT `/api/notifications/preferences`, POST `/api/batch/collect`), Admin API Key `hmac.compare_digest` timing-safe 검증, RequestValidationError → 400 통일 응답. 라우터 통합 테스트 14종.
- **Phase 6 배치**(`65b4bb6`): `app/batch/trading_day.py` (주말 제외), `market_data_job.py` (3-Step 오케스트레이션 — collect → detect → notify, 각 Step 독립 세션·트랜잭션), `scheduler.py` (AsyncIOScheduler CronTrigger mon-fri KST 06:00, max_instances=1, coalesce=True), FastAPI lifespan 연동. 배치 테스트 7종.
- **Phase 7 컨테이너 전환**(`b5e3cc8`): `scripts/entrypoint.py` — alembic_version/stock 테이블 존재 여부로 `stamp head` vs `upgrade head` 분기 후 `os.execvp` 로 uvicorn 전환(PID 1 유지). E2E 플로우 테스트 2종(`/api/batch/collect` → `/api/signals/detect` → GET `/api/signals` 체인).

### Changed
- **운영 설정 소소한 정리**(`c417977`): `ops/caddy/Caddyfile` X-Forwarded-* header_up 중복 제거, `docker-compose.prod.yml` Caddy 헬스체크 `localhost:2019/config/` 로 단순화, `src/backend/src/main/resources/application.yml` management.endpoint.health.show-details 및 management.prometheus.* 중복 설정 제거.
- **docker-compose.prod.yml Python 전환**(`b5e3cc8`): backend 서비스 build context `./src/backend` → `./src/backend_py`, 환경변수 Spring 계열 제거 + DATABASE_URL(asyncpg DSN) / KRX_ID/KRX_PW / DART/OPENAI/KIS / SCHEDULER_ENABLED=true 추가, healthcheck `/actuator/health` → `/health` 전환(curl 대신 python urllib), frontend BACKEND_INTERNAL_URL 포트 8080→8000, db initdb Java migration mount 제거(Alembic 전담), Caddyfile 주석 포트 8080→8000.
- **CORS 보안 설계**(`e669fed` 이후 유지): 빈 화이트리스트면 미들웨어 미탑재, `"*"` + credentials 조합 코드상 차단.
- **NotificationPreferenceRepository**(`31ea518`): `save()` 이후 `session.refresh()` 로 server_default `updated_at` 동기화 — Pydantic model_validate 중 MissingGreenlet 회피.
- **app/adapter/in/web/** → **app/adapter/web/**(`31ea518`): Python 예약어 `in` 때문에 `from app.adapter.in.web...` 파싱 실패 → 경로 평탄화.

### Fixed
- **코드 리뷰 H1·M1·M4 (Phase 4 후)**(`bda6e42`): NotificationService N+1 쿼리 제거(`StockRepository.list_by_ids` IN 쿼리 1회), SignalDetectionService `_trend_reversal` 의 `is None` 죽은 조건 제거(pd.isna 일원화), Telegram 메시지에 `html.escape` 적용 + 영문 enum → 한글 라벨("대차잔고 급감"/"추세전환"/"숏스퀴즈"). 회귀 테스트 3종 추가.
- **코드 리뷰 M1·M2·M3 (Phase 7 후)**(`610918a`): entrypoint uvicorn `--forwarded-allow-ips "*"` → Docker 사설 대역(127.0.0.1,10/8,172.16/12,192.168/16), `FORWARDED_ALLOW_IPS` env 로 오버라이드 가능. 스케줄러 `date.today()` → `datetime.now(KST).date()` 로 TZ 명시화. market_data_job 의 죽은 코드 `detected_signal_ids` 블록 삭제(DB 쿼리 1회 절감).

### Known Issues (Carry-over)
- **KRX 익명 접근 차단(2026-04 확인)**: `data.krx.co.kr` 가 익명 요청을 `HTTP 400 LOGOUT` 으로 거부. pykrx 도 `KRX_ID/KRX_PW` 요구로 전환 완료. 프로덕션 Java 배치가 수개월간 실제 데이터를 못 가져오고 있었음(DB 3개 테이블 0 rows 로 확인). 사용자가 회원가입 후 `.env.prod` 에 `KRX_ID/KRX_PW` 주입, `scripts/validate_krx.py` 로 OHLCV 2879종목 + 공매도 949종목 수신 확인. 대차잔고는 pykrx 스키마 불일치로 0 rows → Phase 3 어댑터에서 예외 격리 + fallback 경고 로그, 본격 복구는 후속 작업.
- **Phase 8/9 미완**: `src/backend/` Java 스택 물리 제거, `docs/design/ai-agent-team-master.md` 기술스택 표, `CLAUDE.md` Backend Conventions, `agents/08-backend/AGENT.md`, `pipeline/artifacts/10-deploy-log/runbook.md` 갱신이 남아 있음.

---

## [2026-04-18 — 새벽] 로컬 Docker Desktop 첫 배포 스모크 테스트 + runbook 정정 + MCP lockdown (`4a9d448`, `a89c6fe`)

### Added
- `.mcp.json` (신규): 빈 `mcpServers`로 프로젝트 스코프 MCP 기본값 잠금 — 외부 MCP 서버 주입 차단
- `docs/context-budget-report.md` (신규): `/context-budget --verbose` 산출물. 세션 오버헤드 ~24.4K tokens / 1M의 2.4% 집계, Top 1~5 절감안(~4.1K tokens / 17%) 제시

### Changed
- `.claude/settings.json`: `enabledMcpjsonServers: []` + `enableAllProjectMcpServers: false` — 프로젝트 레벨 MCP 자동활성화 차단 (보안 순기능)
- `pipeline/artifacts/10-deploy-log/runbook.md` §2.5 스모크 테스트:
  - test #0 신설: `.env.prod`에서 `ADMIN_API_KEY`를 현재 셸로 `export`하는 절차
  - test #4 GET 공개 읽기(`/api/notifications/preferences`, proxy.ts 경유)로 분리
  - test #5 PUT 쓰기(`/api/admin/notifications/preferences`, Route Handler)로 유효 payload 예시 명시
  - signalTypes 열거값(RAPID_DECLINE/TREND_REVERSAL/SHORT_SQUEEZE), minScore 범위(0~100) 힌트 추가
- `CHANGELOG.md` / `HANDOFF.md`: 세션 운영 현행화

### Fixed
- runbook §2.5 test #4: GET은 Route Handler에서 405 반환 — HTTP method 정정(GET → PUT). 로컬 Docker Desktop 스모크 테스트로 5/5 경로 HTTP 200 확인 후 반영

### Verified (not committed)
- 로컬 Docker Desktop 첫 배포 성공 — 3 컨테이너(db/backend/frontend) 전부 `healthy`
- 스모크 테스트 5종 전부 2xx
  - `GET /` → 200 (16KB SSR HTML)
  - backend `/actuator/health` → `{"status":"UP"}`
  - `GET /api/signals` → 200 (빈 배열, DB 초기 상태)
  - `GET /api/notifications/preferences` → 200 (공개, proxy.ts 경유)
  - `PUT /api/admin/notifications/preferences` → 200 (ADMIN_API_KEY 인증 통과, 값 수정→원복 확인)
- `.env.prod` 로컬 생성 (chmod 600, gitignore 확인) — POSTGRES_PASSWORD/ADMIN_API_KEY 랜덤 생성, Telegram/KRX 실값 주입

---

## [2026-04-17 — 저녁] 코드 리뷰 블로커(H-1) 수정 + Next.js 16 canonical proxy 적용 (`ef8c267`)

### Added
- `src/frontend/src/proxy.ts`: 런타임 `/api/*` → `BACKEND_INTERNAL_URL` 프록시 (Next.js 16 canonical, 구 middleware 대체). `/api/admin/*`는 Route Handler 우선 통과

### Changed
- `src/frontend/next.config.ts`: `rewrites()` 제거 — build time에 routes-manifest.json으로 고정되어 런타임 env 반영 불가. 주석으로 proxy.ts 선택 이유 명시
- `src/frontend/src/lib/api/client.ts`: `NEXT_PUBLIC_API_URL` → `NEXT_PUBLIC_API_BASE_URL` 정합, 기본값 `/api`
- `src/frontend/src/app/api/admin/notifications/preferences/route.ts`: `BACKEND_API_URL` → `BACKEND_INTERNAL_URL` 정합, `/api` path prefix 추가, 16KB body 상한(M-4)
- `src/backend/Dockerfile`: `./gradlew dependencies || true` → `./gradlew dependencies` (M-1, 의존성 해석 실패 은폐 제거)

### Fixed
- **[HIGH H-1]** compose / client.ts / route.ts 간 env 변수명 3중 불일치 — 프로덕션에서 브라우저→proxy→backend 경로가 끊어지는 블로커. `NEXT_PUBLIC_API_BASE_URL` + `BACKEND_INTERNAL_URL` 단일 네임스페이스로 통일

---

## [2026-04-17 — 오후] Phase 4 Verify + Phase 5 Ship + 프로토타입 효과 Next.js 이식 — v1.0 배포 준비 완료

### Added
- 프로토타입 효과 3종 Next.js 이식 (`871ff57`)
  - `src/frontend/src/components/ui/AuroraBackground.tsx`: 4-blob radial-gradient + drift keyframes, pure CSS, 서버 안전
  - `src/frontend/src/components/ui/CountUp.tsx`: rAF 기반 easeOutCubic 카운트업, `prefers-reduced-motion` 가드
  - `src/frontend/src/components/ui/Magnetic.tsx`: 커서 인력 버튼 래퍼, `coarse-pointer`/reduced-motion 가드
  - `src/frontend/src/app/globals.css`: `.aurora` + `@keyframes aurora-drift-1~4` + `.magnetic` 블록 추가
- Phase 4 Verify 산출물 3종 + Judge 평가 (`eb5fc15`)
  - `pipeline/artifacts/07-test-results/qa-report.md` (CONDITIONAL)
  - `pipeline/artifacts/08-review-report/review-report.md` (CONDITIONAL, CRITICAL 1 + HIGH 4)
  - `pipeline/artifacts/09-security-audit/audit-report.md` (CONDITIONAL, HIGH 1)
  - `pipeline/artifacts/07-test-results/verify-judge-evaluation.md` (7.6/10)
- Phase 5 Ship 인프라 (`764d6d3`)
  - `src/backend/Dockerfile` / `src/frontend/Dockerfile` (multi-stage, non-root, healthcheck)
  - `docker-compose.prod.yml` (3 서비스, 내부 네트워크, DB 미노출)
  - `.env.prod.example` + `.gitignore` 갱신
  - `.github/workflows/ci.yml` (backend-test + frontend-build + docker-build with GHA cache)
  - `pipeline/artifacts/10-deploy-log/runbook.md` (배포 / 롤백 / 백업 cron / AWS 5-step 이관)
  - `pipeline/artifacts/11-analytics/launch-report.md` (D+7 Top KPI 3종 + Week 1~4 모니터링)
  - `pipeline/artifacts/10-deploy-log/ship-judge-evaluation.md` (PASS 8.1/10)
- 백엔드 트랜잭션 리팩터
  - `src/backend/.../application/service/MarketDataPersistService.java`: `persistAll` 전담 빈 분리 — Spring AOP 자기호출 프록시 우회 문제 해결
- Admin API 서버 릴레이
  - `src/frontend/src/app/api/admin/notifications/preferences/route.ts`: Next.js Route Handler — 서버 측 `ADMIN_API_KEY`로 backend 프록시

### Changed
- `src/frontend/src/app/layout.tsx`: `<AuroraBackground>` 주입 + 본문 z-index:1 레이어링 + footer backdrop-blur
- `src/frontend/src/app/page.tsx`: metric 카드 값에 `CountUp`, 필터 버튼에 `Magnetic` 래핑, 카드 배경 `bg-[#131720]/85 backdrop-blur`로 전환
- `src/backend/.../MarketDataCollectionService.java`: `persistAll` 로직 제거, `MarketDataPersistService`에 위임
- `src/frontend/src/app/settings/page.tsx`: `NEXT_PUBLIC_ADMIN_API_KEY` 의존 제거, `updateNotificationPreferences(form)`로 간소화
- `src/frontend/src/lib/api/client.ts`: `updateNotificationPreferences` apiKey 인자 제거, `/api/admin/notifications/preferences` Route Handler 호출로 전환
- `pipeline/state/current-state.json`: `status: "deployed"`, `human_approvals #3 passed 7.6`, `ship_artifacts` + `post_ship_recommendations` 추가
- `docs/sprint-4-plan.md`: Phase 4/5 통과 반영

### Fixed
- **[CRITICAL B-C1]** `NEXT_PUBLIC_ADMIN_API_KEY` 브라우저 번들 노출 — Review+Security 공동 지목. Route Handler로 서버 전환, 관리자 API 4개(batch/collect, signals/detect, backtest/run, PUT preferences) 공개 상태 해소
- **[HIGH B-H1]** `MarketDataCollectionService.persistAll` 자기호출로 `@Transactional` 무효 — `MarketDataPersistService` 신규 빈으로 분리해 프록시 정상 적용
- **[HIGH B-H2]** `persistAll` 데드 코드 (`findByStockId(null, date, date)` 미사용 결과) 제거
- **[HIGH B-H3]** 배치 재실행 시 유니크 제약 충돌 — 일자별 기존 `stockId` 집합 1회 조회 후 INSERT skip, 건수 로깅으로 멱등성 확보

---

## [2026-04-17] Sprint 4 Task 4 — 알림 설정 페이지 (백엔드 + 프론트) + 프로토타입 합류본 확정 + 리뷰 반영

### Security / Review Fixes (HIGH 4 + MEDIUM 9)
- **HIGH-1**: `PUT /api/notifications/preferences`에 `X-API-Key` 인증 추가 — 공개 API에서 공격자의 알림 무력화 방지 (Security 리뷰)
- **HIGH-2**: `NotificationPreferenceService.loadOrCreate` race condition — `DataIntegrityViolationException` catch + 재조회 recover 패턴 적용 (Java 리뷰)
- **HIGH-3**: `GlobalExceptionHandler`에서 `IllegalArgumentException` 전역 캐치 제거 — JDK 내부 오류가 400으로 마스킹되던 문제 해소 (Java 리뷰)
- **HIGH-4**: Hexagonal 위반 수정 — `sanitizeSignalTypes` 검증 책임을 Controller에서 `UpdateCommand` compact constructor로 이동, `DomainException(DomainError.InvalidParameter)` 경로 사용 (Java 리뷰)
- **MEDIUM**: `@Size(min=1, max=3)` 제약 추가 (DoS 방지), 에러 메시지 사용자 입력 반사 제거(고정 문자열), `getPreferenceForFiltering`에 `@Transactional(readOnly=true)` 명시, 도메인 `update()` 자체 검증(minScore 범위, 빈 리스트), `sendBatchFailure` 로그에서 `errorMessage` 제거
- **MEDIUM (프론트)**: `aria-valuemin/max/now` 3줄 중복 제거(input[type=range] 자동 제공), `client.ts` `cache: 'no-store'` spread 후위 재명시(caller override 방어), 에러 메시지 직접 노출 → `friendlyError()` 매핑 함수로 status 기반 사용자 메시지 반환
- **테스트**: `NotificationApiIntegrationTest` 9개로 확장 (인증 2 + 업데이트 1 + 400 검증 5 + 기본값 1). 알 수 없는 타입이 응답에 반사되지 않는지 검증 포함
- **부수 개선**: `BacktestController`/`SignalDetectionController`/`BatchController`의 API Key 검증 로직 중복 제거 → 신규 `ApiKeyValidator` 컴포넌트로 추출

### Added
- `src/backend/.../domain/model/NotificationPreference.java`: 싱글 로우 엔티티(id=1 고정) — 4채널 플래그 + `minScore`(0-100) + `signalTypes` JSONB
- `src/backend/.../application/port/in/GetNotificationPreferenceUseCase`, `UpdateNotificationPreferenceUseCase`: 조회/업데이트 유스케이스 포트
- `src/backend/.../application/port/out/NotificationPreferenceRepository`: Spring Data JPA 리포지토리
- `src/backend/.../application/service/NotificationPreferenceService`: `loadOrCreate` 지연 생성 + `getPreferenceForFiltering` 기본값 fallback
- `src/backend/.../adapter/in/web/NotificationPreferenceController`: `GET/PUT /api/notifications/preferences` + Bean Validation(`@Min/@Max/@NotNull`)
- `src/backend/src/main/resources/db/migration/V2__notification_preference.sql`: 테이블 DDL + 기본 row INSERT (Flyway 도입 시 바로 적용 가능, 현재는 참고용)
- `src/backend/src/test/.../NotificationApiIntegrationTest`: 5개 통합 테스트 (기본값 생성 / 전체 업데이트 / minScore 범위 / 알 수 없는 타입 / 필수 필드 누락)
- `src/frontend/src/types/notification.ts`: `NotificationPreference` 타입 + 채널 라벨 상수
- `src/frontend/src/app/settings/page.tsx`: 4개 토글(switch role) + 3개 시그널타입 필터(aria-pressed) + minScore 슬라이더 + 저장 버튼 + 토스트

### Changed
- `src/backend/.../application/service/TelegramNotificationService`: 4개 시나리오 전부 preference 필터 반영
  - `sendDailySummary`: toggle + signalTypes + minScore 삼중 필터
  - `sendUrgentAlerts`: toggle + signalTypes (A등급 자체가 minScore 상회)
  - `sendBatchFailure`, `sendWeeklyReport`: toggle
- `src/backend/.../adapter/in/web/GlobalExceptionHandler`: `@Valid @RequestBody` 검증 실패를 400으로 변환 — `MethodArgumentNotValidException` + `HttpMessageNotReadableException` + `IllegalArgumentException` 핸들러 신규
- `src/frontend/src/lib/api/client.ts`: `fetchApi`에 `RequestInit` 옵션 추가, `getNotificationPreferences` + `updateNotificationPreferences` 노출
- `src/frontend/src/components/NavHeader.tsx`: `/settings` 링크 추가

### Decision
- **D-4.11 알림 설정 = 싱글 로우 패턴**: id=1 고정, 4개 채널 플래그 + minScore + signalTypes JSONB. 사용자/인증 도입 시 user_id FK로 확장 가능
- **D-4.10 프로토타입 합류본 = ambient**: `prototype/index-ambient.html`(1332줄, aurora + skeleton + tilt + magnetic + count-up 누적)을 최종 합류본으로 확정 → `prototype/index.html`에 복사

### Testing
- 백엔드: JUnit 5 + Testcontainers 25개 전체 통과 (기존 20 + 신규 5)
- 프론트: `tsc --noEmit` + `eslint` + `next build` 전부 clean — `/settings` 라우트 정적 생성 확인

---

## [2026-04-17] Sprint 4 Task 5-6 — 프론트엔드 반응형 + ErrorBoundary + 글로벌 네비 + 접근성

### Added
- `src/frontend/src/components/NavHeader.tsx`: 글로벌 네비게이션 — sticky + 햄버거 + ESC + `aria-current` + render-time 리셋 패턴 (`9436772`)
- `src/frontend/src/components/ErrorBoundary.tsx`: class 컴포넌트 + `resetKeys` 자동 복구 + `role="alert"` (`9436772`)

### Changed
- `src/frontend/src/app/layout.tsx`: 글로벌 `<NavHeader />` 삽입 (`9436772`)
- `src/frontend/src/app/page.tsx`: 중복 헤더 제거(sr-only H1), 시그널 리스트 `grid-cols-1 lg:grid-cols-2`, `<ul>/<li>` 시맨틱, 필터 `role="group" + aria-pressed` (`9436772`)
- `src/frontend/src/app/stocks/[code]/page.tsx`: `ResponsiveContainer aspect={2}` 비율 기반 차트, ErrorBoundary 래핑, 기간 버튼 `role="group"`, render-time 상태 리셋 (`9436772`)
- `src/frontend/src/app/backtest/page.tsx`: 모바일 `<dl/dt/dd>` 카드 ↔ 데스크탑 `<table>` 이중 렌더, ErrorBoundary 래핑 (`9436772`)
- `src/frontend/src/components/features/SignalCard.tsx`: `<Link>`가 직접 그리드 컨테이너 (중첩 `<div role="article">` 제거), `aria-label` 상세화 (`9436772`)

### Fixed
- `react-hooks/set-state-in-effect` ESLint 3건(Next 16 신규 룰): `NavHeader.pathname`, `StockDetail.code+period`, `Dashboard` 초기 `setLoading` 중복 → render-time 리셋 패턴 (`9436772`)
- `role="tablist"/"tab"` 스펙 위반 2건 → `role="group" + aria-pressed` (필터, 기간 버튼) (`9436772`)
- ErrorBoundary 재발 루프: `resetKeys` + `componentDidUpdate` 자동 리셋 (리뷰 MEDIUM-1) (`9436772`)
- `role="alert"` + `aria-live="assertive"` 중복 제거 (`9436772`)
- 백테스트 YAxis formatter 음수 처리 (`+-1.5%` → `-1.5%`) (`9436772`)
- `aria-current="page"`는 exact match만, 관련 경로는 시각 강조로 분리 (`9436772`)

### Committed
- Sprint 4 Task 5-6 (`9436772`): 7 files, +330/-73, `tsc + eslint + next build` 전부 ok

### Pending (Task 4 + 프로토타입 선정 다음 세션)
- Task 4: 알림 설정 페이지 (`NotificationPreference` 엔티티 + `/settings` 프론트, 1.5일)
- 프로토타입 5종 중 합류본 선정 → `prototype/index.html`로 통합

---

## [2026-04-17] 프로토타입 UI 실험 5종 + 코드리뷰 보안 패치 전면 적용

### Added
- `prototype/index-before-skeleton.html`: 원본 스냅샷 (baseline, 보안 패치만) (`7a5b750`)
- `prototype/index-tilt-magnetic.html`: 3D 틸트 카드 + 마그네틱 버튼 — `prefers-reduced-motion` + 터치 자동 비활성 (`7a5b750`)
- `prototype/index-counter.html`: 카운트업 애니메이션 32개 카운터 (data 속성 선언형 엔진) (`7a5b750`)
- `prototype/index-ambient.html`: 배경 3층 — Aurora 메시 + 커서 스포트라이트 + 파티클 네트워크 캔버스 (`7a5b750`)

### Changed
- `prototype/index.html`: 스켈레톤 UI 적용 (시그널 리스트/상세 차트/백테스트 차트 로딩 + shimmer, 라이트/다크 대응) (`7a5b750`)

### Fixed
- **[CRITICAL] XSS 싱크 3종 차단**: `escapeHtml()` + `num()` 헬퍼, `onclick` 인라인 → `data-code` + `addEventListener` (`7a5b750`)
- **[HIGH] `showPage()` 허용목록**: `VALID_PAGES = Set` early return (`7a5b750`)
- **[HIGH] DOM 엘리먼트 캐싱**: `cacheEls()` INIT 1회 → `els[id]` 룩업 (`7a5b750`)
- **[MEDIUM] CDN SRI**: Chart.js 4.4.7 / Pretendard 1.3.9 `integrity="sha384-..."` + `crossorigin="anonymous"` (`7a5b750`)
- **[MEDIUM] 스켈레톤 접근성**: `role="list"` + `aria-busy` 토글 + `aria-live="polite"` + 카드 `role="button"` + 키보드 (`7a5b750`)
- **[LOW] matchMedia 동적 리스너**: `prefers-reduced-motion`/`pointer: coarse`에 `change` 리스너 (tilt/counter/ambient 3종) (`7a5b750`)

> 5종 HTML 모두 단독 실행 가능. 코드리뷰 재검증 CRITICAL/HIGH 0건 + 회귀 0건. 다음 세션에서 최종 합류본 결정 → `prototype/index.html` 통합 예정.

---

## [2026-04-17] Sprint 4 Task 1-3 — N+1 쿼리 최적화 + 백테스팅 3년 제한 + CORS X-API-Key

### Added
- `src/backend/src/test/java/com/ted/signal/config/CorsConfigTest.java`: CORS preflight 테스트 1개 신규 (`33b6cf1`)
- `BacktestApiIntegrationTest.runBacktestRejectsPeriodOverThreeYears`: 3년 초과 기간 rejection 테스트 추가 (`33b6cf1`)
- `StockPriceRepository.findAllByStockIdsAndTradingDateBetween`: 종목 IN 절 기반 벌크 주가 조회 (`33b6cf1`)
- `StockPriceRepository.findAllByTradingDate`: 일자별 주가 전체 조회 (JOIN FETCH stock) (`33b6cf1`)
- `ShortSellingRepository.findAllByTradingDate`: 일자별 공매도 전체 조회 (JOIN FETCH stock) (`33b6cf1`)
- `LendingBalanceRepository.findAllByStockIdsAndTradingDateBetween`: 종목 IN 기반 대차잔고 히스토리 (`33b6cf1`)
- `SignalRepository.findBySignalDateWithStockOrderByScoreDesc`: 일자별 시그널 JOIN FETCH 조회 (`33b6cf1`)

### Changed
- `SignalDetectionService.detectAll`: 종목당 7쿼리 × 2500 = 17,500쿼리 → 전체 7쿼리 (활성 종목 1 + 벌크 5 + 기존 시그널 1). 메모리 루프 기반 재작성 (`33b6cf1`)
- `TelegramNotificationService.sendDailySummary`: `findBySignalDateOrderByScoreDesc` → `findBySignalDateWithStockOrderByScoreDesc` (stock LAZY 로딩 N+1 해소) (`33b6cf1`)
- `BacktestController`: 최대 기간 5년 → **3년**, `to` 미래 날짜 차단 검증 추가 (`33b6cf1`)
- `BacktestEngineService`: 종목별 주가 조회 N쿼리 → `findAllByStockIdsAndTradingDateBetween` 단일 쿼리 (`33b6cf1`)
- `WebConfig`: CORS `allowedHeaders`에 `X-API-Key` 추가, `OPTIONS` 메서드, `allowCredentials(true)`, `exposedHeaders` 명시 (`33b6cf1`)
- `SignalDetectionService` detail의 `volumeChangeRate`: 점수(int) 중복 저장 → 실제 거래량 비율(BigDecimal) 저장 (`33b6cf1`)

### Committed
- Sprint 4 Task 1-3 (`33b6cf1`): 성능/보안 HIGH 3건 해소 (11 files, +245/-114, 테스트 20개 전부 통과)

### Pending (Task 4-5 다음 세션 이관)
- Task 4: 알림 설정 페이지 (`NotificationPreference` 엔티티 + 프론트 `/settings`)
- Task 5: 모바일 반응형 + ErrorBoundary + 접근성 감사

---

## [2026-04-17] 모델 운용 전략 전환 — Max 구독자 Opus 4.7 단일 운영

### Changed
- `docs/PIPELINE-GUIDE.md`: "Phase 1~3 Sonnet, Phase 4 Opus" 분기 전략 → **Max 구독자 Opus 4.7 단일 운영**으로 전환. API 종량제 사용자용 Option B 병기 (`d55738d`)
- `docs/design/ai-agent-team-master.md`: §11 "비용 최적화" 섹션을 **Option A (Max 구독) / Option B (API 종량제)** 이원화. Judge 비용 설명 보강 (`d55738d`)
- `.claude/commands/init-agent-team.md`: CLAUDE.md 템플릿에 "모델 운용 전략" 섹션 추가 + 최종 안내 메시지에 구독 유형별 가이드 포함 (`d55738d`)
- `pipeline/decisions/decision-registry.md`: D-0.1 "모델 운용 전략" 의사결정 추가 (23 → 24건) (`d55738d`)

> 근거: Claude Code Max $200 구독 활용 시 모델 분기로 얻는 비용 이득 없음. Sprint 3에서 Opus 4.7이 N+1 쿼리 17,500건 등 HIGH 이슈 7건 포착 → Phase 1~3에서도 Opus 사용 시 품질 우위 확인.

---

## [2026-04-17] 파이프라인 플랫폼 정합화 + 팀 공유 전환 + 문서 현행화

### Added
- `docs/PIPELINE-GUIDE.md`: 개발 플로우 사용설명서 신규 (9개 섹션, 다른 프로젝트 이식 체크리스트 포함) (`cdbacc5`)
- `docs/sprint-4-plan.md`: Sprint 4 작업계획서 (N+1 최적화 + CORS + 알림 설정 페이지 + 모바일 반응형, 4.5일 예상) (`da85ba2`)
- `pipeline/state/current-state.json`: Sprint 3 완료 상태 현행화 (진행 sprint 4종 + 테스트 커버리지 + 알려진 이슈) (`eecdb7c`)
- `pipeline/artifacts/06-code/summary.md`: Sprint 1~3 구현 요약 (Compaction 방어 영속화) (`eecdb7c`)
- `pipeline/decisions/decision-registry.md`: Phase 1~3 의사결정 23개 누적 (Discovery 3, Design 4, Build 15, Sprint 4 계획 1) (`da85ba2`)
- 글로벌 `~/.claude/settings.json` statusLine: 현재 모델 / 비용 / 200k 초과 / CWD 실시간 표시 (Opus→Sonnet fallback 즉시 인지)

### Changed
- `.gitignore`: `pipeline/state/`, `pipeline/artifacts/` 제외 규칙 제거 → 팀 공유 대상화 (`eecdb7c`)
- `CLAUDE.md`: 소규모 스타트업 팀 공유 전제 명시 + PIPELINE-GUIDE.md 참조 추가 + Spring Boot 3.4 → 3.5.0 일관성 (`eecdb7c`, `cdbacc5`)
- `docs/design/ai-agent-team-master.md`: `Opus 4.6` → `Opus 4.7` 14곳 치환 (1M 컨텍스트, 비용, MRCR 설명 전반) (`cdbacc5`)
- `.claude/commands/init-agent-team.md`: 기본 스택 `Spring Boot 3.4` → `3.5.0` (새 프로젝트 scaffolding 현행값) (`cdbacc5`)

### Committed
- Sprint 3 구현 (`022284e`): 백테스팅 엔진 + 텔레그램 알림 + 통합 테스트 (19 files, +1346)
- Sprint 3 핸드오프 (`88aba9a`): CHANGELOG + HANDOFF
- 파이프라인 영속화 (`da85ba2`): decision-registry + sprint-4-plan
- 팀 공유 전환 (`eecdb7c`): pipeline/ 커밋 대상화 (22 files, +2369)
- 문서 업데이트 (`cdbacc5`): Opus 4.7 + Spring Boot 3.5.0 + PIPELINE-GUIDE

---

## [2026-04-17] Phase 3 Build Sprint 3 — 백테스팅 엔진 + 텔레그램 알림 + 통합 테스트

### Added
- BacktestEngineService: 과거 3년 시그널 수익률 계산 + SignalType별 적중률/평균수익률 집계
- RunBacktestUseCase 포트 + POST /api/backtest/run API (API Key 보호, 기본 3년, 최대 5년)
- TelegramClient: RestClient 기반 Telegram Bot API 연동 (환경변수 비활성화 지원)
- TelegramNotificationService: 4가지 알림 시나리오 (일일 요약/A등급 긴급/배치 실패/주간 리포트)
- NotificationScheduler: 08:30 일일 요약 (월~금), 토요일 10:00 주간 리포트
- MarketDataBatchConfig notifyStep: 배치 완료 후 A등급 시그널 긴급 알림 자동 발송
- SignalRepository.findBySignalDateBetweenWithStock: JOIN FETCH 벌크 조회
- Testcontainers PostgreSQL 16 통합 테스트 인프라 (싱글톤 컨테이너 패턴)
- SignalDetectionServiceTest: 시그널 탐지 로직 5개 테스트 (급감/임계값/추세전환/숏스퀴즈/중복방지)
- BacktestEngineServiceTest: 수익률 계산 + 적중률 집계 + 데이터 부족 처리 4개 테스트
- BacktestApiIntegrationTest: API 인증/실행 5개 테스트
- SignalApiIntegrationTest: 시그널 조회/필터/인증 3개 테스트
- application.yml: telegram.bot-token, telegram.chat-id 환경변수 설정

### Changed
- API Key 비교: String.equals → MessageDigest.isEqual 상수 시간 비교 (타이밍 공격 방지, 3개 컨트롤러)
- API Key 미인증 시 403 → 401 UNAUTHORIZED 반환 (3개 컨트롤러)
- @Value 필드 주입 → 생성자 주입 전환 (BacktestController, BatchController, SignalDetectionController)
- BacktestEngineService: save() 루프 → saveAll() 일괄 저장
- MarketDataBatchConfig: SignalRepository 직접 주입 제거 → TelegramNotificationService.sendUrgentAlerts() 위임 (Hexagonal 경계 준수)
- MarketDataScheduler: 배치 실패 시 e.getMessage() 노출 → 클래스명만 텔레그램 발송
- BacktestController: @Validated 추가 + from/to 날짜 범위 검증 (최대 5년)
- TelegramNotificationService.sendBatchFailure: LocalDate → LocalDateTime (시간 정밀도)

---

## [2026-04-16] Phase 3 Build Sprint 2 — 시그널 엔진 + 대시보드

### Added
- SignalDetectionService: 3대 시그널 탐지 엔진 (급감/추세전환/숏스퀴즈) (`7902cfd`)
- POST /api/signals/detect 수동 시그널 탐지 API (`7902cfd`)
- Spring Batch detectStep 추가 (collectStep → detectStep 순차) (`7902cfd`)
- 프론트엔드 대시보드: 메트릭 카드 + 필터 탭 + 시그널 리스트 (`7902cfd`)
- 프론트엔드 종목 상세: 주가/대차잔고 듀얼 축 차트 (Recharts) (`7902cfd`)
- SignalCard 컴포넌트, TypeScript 타입 정의, API 클라이언트 (`7902cfd`)
- BacktestResult Entity + Repository + BacktestQueryService (`63407cd`)
- GET /api/backtest 백테스팅 결과 조회 API (`63407cd`)
- 프론트엔드 /backtest 페이지: 성과 테이블 + 보유기간별 수익률 Bar 차트 (`63407cd`)

### Changed
- 관리자 API 인증: IP allowlist → API Key 헤더(X-API-Key) 전환 (`e6754cb`)
- detail.volumeChangeRate 매핑 오류 수정 (`e6754cb`)
- scoreVolumeChange 음수 방지 Math.max(0, ...) 추가 (`e6754cb`)
- params.code 안전한 타입 처리 (Array.isArray 체크) (`e6754cb`)
- 프론트엔드 API 클라이언트 단일화 (중복 fetch 제거) (`e6754cb`)
- 미사용 변수 signalDates 제거 (`e6754cb`)

---

## [2026-04-16] Phase 3 Build Sprint 1 — 데이터 파이프라인 구축

### Added
- 16개 에이전트 AGENT.md + 공유 프로토콜 + 7개 슬래시 커맨드 scaffolding (`1908310`)
- Phase 1 Discovery 산출물 8건: 요구사항, PRD, 로드맵, 스프린트 플랜, GTM, 경쟁사 분석, 고객여정, 알림 시나리오 (`1908310`)
- Phase 2 Design 산출물 6건: 기능명세, 디자인 토큰, 컴포넌트 명세, ERD, DDL, 쿼리 전략 (`1908310`)
- Spring Boot 3.5.0 + Java 21 백엔드 프로젝트 (Hexagonal Architecture) (`33d7676`)
- Domain Entity 5개: Stock, StockPrice, LendingBalance, ShortSelling, Signal (`33d7676`)
- Repository 5개 (JPA 3단계 쿼리 전략), UseCase 2개, SignalQueryService (`33d7676`)
- REST API: GET /api/signals, GET /api/stocks/{code} (`33d7676`)
- GlobalExceptionHandler + sealed interface DomainError (`33d7676`)
- KRX 크롤러: 공매도/대차잔고/시세 수집 (요청 간격 2초) (`620f2bf`)
- Spring Batch Job + MarketDataScheduler (매일 06:00 스케줄) (`620f2bf`)
- 수동 배치 API: POST /api/batch/collect (localhost 제한) (`620f2bf`)
- docker-compose.yml: PostgreSQL 16 + DDL 자동 적용 (`620f2bf`)
- Next.js 15 + TypeScript 프론트엔드 프로젝트 초기화 (`33d7676`)
- UI/UX 프로토타입: Dark Finance Terminal 디자인 (prototype/index.html) (`33d7676`)
- .env.example (`620f2bf`)

### Changed
- Spring Boot 버전 3.4 → 3.5.0 (Spring Initializr 호환) (`33d7676`)
- JPA ddl-auto: validate → none (파티션 테이블 호환) (`140694b`)
- CORS allowedOrigins → allowedOriginPatterns + 헤더 제한 (`620f2bf`)
- MarketDataCollectionService: HTTP 수집을 트랜잭션 밖으로 분리 (`d710aa1`)
- 대차잔고 전 영업일 계산: minusDays(1) → 주말 건너뛰기 (`d710aa1`)
- 대차잔고 벌크 조회: 종목별 개별 쿼리 → findAllByTradingDate 1회 쿼리 (`d710aa1`)
- saveAll 벌크 저장으로 개별 exists/save 쿼리 제거 (`d710aa1`)
- BatchConfig → BatchConfig + Scheduler 분리 (Job Bean 직접 주입) (`d710aa1`)

---

## [2026-04-16] 프로젝트 초기 설정

### Added
- CLAUDE.md 생성 — 프로젝트 개요, 기술스택, 파이프라인, 에이전트 구조 가이드 (`fd26e75`)
- .gitignore 생성 — 빌드/IDE/환경파일 제외 설정 (`fd26e75`)
- GitHub 저장소 생성 (withwooyong/ted-startup, private) (`fd26e75`)
- AI Agent Team Platform 설계서 및 scaffolding 생성기 커밋 (`fd26e75`)
