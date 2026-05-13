# Session Handoff

> Last updated: 2026-05-13 (KST) — 5-13 dead 가설 반증 + 신규 인시던트 3건 진단 + Phase D-1 follow-up plan doc § 13 추가 / 세션 종료.
> Branch: `master`
> Latest commit: `1d7759e` (5-12 D-1 백필 partial 결과 + ka20006 60% 실패 발견 메타 갱신)
> 미푸시: 본 세션 진단 + plan doc § 13 + 메타 갱신 commit 1건 예정 — 사용자 push 명시 요청

## Current Status

**5-13 17:30 / 18:00 자연 cron 정상 발화 → scheduler dead 가설 반증** ✅. 그러나 진단 중 **신규 인시던트 3건 발견** + **Phase D-1 follow-up plan doc § 13 작성 완료**. 코드 변경 0, plan doc 2개 갱신만.

### 1. dead 가설 반증 (1순위 종결)

| cron | 시각 | 결과 |
|------|------|------|
| `stock_master` | 17:30:00 KST 정상 발화 | fetched=4788 upserted=4788 deactivated=2 nxt_enabled=634 (1.4초) |
| `stock_fundamental` | 18:00:00 KST 정상 발화 | total=4379 success=4063 failed=316 ratio=0.07 (17분) |

→ 5-13 06:00/06:30/07:00 의 dead 는 **자연 재현 안 됨**. 컨테이너 재배포 직후 일회성 가설로 정리. `/admin/scheduler/diag` endpoint 는 유지 (운영 가시화 가치).

### 2. 신규 인시던트 3건 진단

| # | 인시던트 | 실제 예외 | 카운트 | 근본 원인 | fix chunk |
|---|---------|---------|--------|----------|-----------|
| A | ka20006 sector_daily MaxPages | `KiwoomMaxPagesExceededError` (`SECTOR_DAILY_MAX_PAGES=10`) | 56 / 124 (45%) | 추정값 "1 page ~600 거래일" 틀림 — ka10086 실측 (1 page ~22 거래일) 패턴이면 3년=34 page → 10 부족 | **E** (endpoint-13 § 13) |
| B | ka20006 sector_daily InterfaceError | `asyncpg.exceptions._base.InterfaceError: the number of query arguments cannot exceed 32767` (sector_id 29/57/102/103/105-108) | 8 / 124 | PostgreSQL wire protocol int16 한도 — bulk insert row × column > 32767 | **E** (endpoint-13 § 13) |
| C | ka10086 KOSDAQ MaxPages | `KiwoomMaxPagesExceededError` (`DAILY_MARKET_MAX_PAGES=40`) | 다수 (KRX ~1814 누락) | 40 cap 부족 — 일부 KOSDAQ 종목 page > 40 | **E** (endpoint-10 § 14 cross-ref) |
| D | ka10001 stock_fundamental NUMERIC overflow | `asyncpg.exceptions.NumericValueOutOfRangeError: precision 8 scale 4 must < 10^4` (468760/474930/0070X0 등) | 11 / 316 | NUMERIC(8,4) 컬럼 overflow — Migration 신규 필요 | **F** (별도 chunk) |
| E | ka10001 stock_fundamental sentinel 거부 | `_validate_stk_cd_for_lookup` (stkinfo.py:249) — 0000D0/0000H0/0000Y0/0000Z0/0007F0/... | 2+ / 316 | sentinel 종목이 ERROR 로 분류 → 실패율에 오집계 | **F** (별도 chunk) |

### 3. Phase D-1 follow-up plan doc § 13 작성

**산출물**:
- `docs/plans/endpoint-13-ka20006.md` § 13 신규 (Phase D-1 follow-up — MaxPages cap 상향 + bulk insert 32767 chunk 분할)
  - 13.1 배경 (인시던트 트리 + ka10001 F 분리 정당성)
  - 13.2 결정 10건 (ADR § 42 신규 예정)
  - 13.3 영향 범위 (6 코드 + 5 테스트)
  - 13.4 self-check (H-1 ~ H-10)
  - 13.5 DoD
  - 13.6 다음 chunk
  - 13.7 운영 모니터
- `docs/plans/endpoint-10-ka10086.md` § 14 cross-ref 추가 (Phase D-1 follow-up → endpoint-13 § 13 참조)

**핵심 fix**:
1. `SECTOR_DAILY_MAX_PAGES = 10 → 40` (chart.py L350)
2. `DAILY_MARKET_MAX_PAGES = 40 → 60` (mrkcond.py L53)
3. `_chunked_upsert(session, model, rows, *, chunk_size=1000)` helper 신규 (Repository 공통)
4. `sector_daily` / `daily_flow` Repository 의 `upsert_many` → `_chunked_upsert` 호출
5. `KiwoomMaxPagesExceededError(page, cap)` 시그니처 (운영 가시화)

**ted-run 진입 가정**: 1R+2R 이중 리뷰 + Verification 5관문 — 풀 사이클 ~3-5 시간 견적 (Phase E ~6-10h 의 절반).

### 4. 현재 상태

- kiwoom-app container: 12 scheduler 활성 (15 시간 healthy)
- 5-12 D-1 적재 (22:30 KST 시점): KRX 2559 / NXT 632 / daily_flow 1038 (백그라운드 계속 진행) / sector_daily 59
- 테스트 1186 / coverage 86.30% (코드 변경 0 — 본 chunk plan doc 2 갱신만)
- 15 / 25 endpoint (60%) 그대로

## Completed This Session

| # | Task | 결과 | Files |
|---|------|------|-------|
| 1 | 1순위 dead 재현 검증 (17:30/18:00 자연 cron 모니터) | ✅ 가설 반증 — 17:30 stock_master + 18:00 stock_fundamental 정상 발화 | 0 (검증만) |
| 2 | A. stock_fundamental ASYNCPG 16% 진단 (Explore agent) | 코드 흐름 + 동시성 + pool 패턴 + 가설 1·2·3 | 0 (read-only) |
| 3 | B. daily_flow 적재 + 5-12 KRX 1814 누락 확인 (Bash 직접) | 테이블명 `stock_daily_flow` / 5-12 1038 진행 중 / mrkt_tp=10 KOSDAQ MaxPages 다수 | 0 (DB query 만) |
| 4 | C. ka20006 sector_daily 60% follow-up 분석 (Explore agent) | session 패턴 + max_pages 가설 + ADR § 39 검토 | 0 (read-only) |
| 5 | E1. 페이지 수 + InterfaceError 실측 (Bash 직접) | InterfaceError 실 메시지 = **`cannot exceed 32767`** (PostgreSQL int16 한도) + ka10001 ASYNCPG 실 type = **`NumericValueOutOfRangeError precision 8 scale 4`** + ka10086 cap=40 / ka20006 cap=10 / sentinel break 코드 존재 확인 | 0 (read-only) |
| 6 | E2. Phase D-1 follow-up plan doc § 13 작성 | endpoint-13 § 13 신규 (10 결정 + 10 self-check + DoD) + endpoint-10 § 14 cross-ref | 2 / `<pending commit>` |
| 7 | D. 종합 + HANDOFF/STATUS 갱신 | STATUS § 0/§ 4 #26~29/§ 5/§ 6 + HANDOFF (본 파일) + CHANGELOG prepend | 3 / `<pending commit>` |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| **1** | **(E3) Phase D-1 follow-up ted-run 풀 파이프라인** | **다음 세션 1순위** | endpoint-13 § 13 input. TDD + 구현 6 코드 + 5 테스트 + 1R+2R 이중 리뷰 + Verification 5관문 + ADR § 42 / 메타 3종. 풀 사이클 ~3-5 시간 견적 |
| **2** | **(E4) 컨테이너 재배포 + 5-12 운영 백필 재호출** | E3 머지 후 | sector_daily 64 sector + KOSDAQ ~1814 종목 재호출 → 0 MaxPages / 0 InterfaceError 검증. ADR § 42 운영 결과 채움 |
| **3** | **F chunk — ka10001 NUMERIC overflow + sentinel WARN/skipped 분리** | E 머지 후 별도 ted-run | Migration 신규 (NUMERIC(8,4) precision 확대 — overflow 종목 값 분석 선행) + WARN/skipped 분리 + result.errors 의 full exception type/메시지 로그 보강 (ka20006 1R HIGH #5 패턴 동일) |
| ~~**Pending #1 (이전)**~~ | ~~5-13 17:30 dead 재현 모니터~~ | ~~본 chunk 종결 ✅~~ | 자연 발화 정상 — dead 가설 반증 |
| ~~**Pending #2 (이전)**~~ | ~~5-12 D-1 백필 완료 확인 + OHLCV 1814 재호출~~ | ~~본 chunk 진단 → E3/E4 chunk 로 이관~~ | E 머지 후 운영 재호출 |
| ~~**Pending #3 (이전)**~~ | ~~ka20006 60% 실패 follow-up~~ | ~~본 chunk plan doc § 13 작성 ✅~~ | E3 ted-run 진입 가능 상태 |
| **4** | **노출된 secret 4건 회전** | **전체 개발 완료 후** | API_KEY/SECRET revoke + Fernet 마스터키 회전 + DB 재암호화 + Docker Hub PAT revoke (ADR § 38.8 #6/#7). 절차서: [`docs/ops/secret-rotation-2026-05-12.md`](docs/ops/secret-rotation-2026-05-12.md) |
| **5** | `.env.prod` 의 `KIWOOM_SCHEDULER_*` 9 env 정리 + alias 추가 | 전체 개발 완료 후 | compose env override 로 우회 완료 |
| **6** | (5-19 이후) § 36.5 1주 모니터 측정 채움 | 대기 | 컨테이너 로그 기반 12 scheduler elapsed |
| **7** | Mac 절전 시 컨테이너 중단 → cron 누락 위험 | 사용자 환경 결정 | 절전 차단 또는 서버 이전 (ADR § 38.8 #1) |
| **8** | scheduler dead 진단 endpoint 정리 (`/admin/scheduler/diag` 유지/제거) | dead 가설 자연 재현 반증 후 | 운영 가치 (cron 상태 가시화) 평가 + ADR § 41 신규 § 후보 (코드 변경 0) |
| 9 | D-1 follow-up: inds_cd echo 검증 / close_index Decimal 통일 / `backfill_sector` CLI | ADR § 39.8 | 운영 첫 호출 후 결정 |
| 10 | Phase F / G / H (순위/투자자별/통합) | 대기 | 신규 endpoint wave |
| 11 | Phase D-2 ka10080 분봉 (**마지막 endpoint**) | 대기 | 사용자 결정 (5-12) — 데이터량 부담. 대용량 파티션 결정 동반 |
| 12 | §11 포트폴리오·AI 리포트 (P10~P15) | 대기 | CLAUDE.md next priority — KIS + DART + OpenAI 기반. backend_kiwoom 25 endpoint 완주 후 |

## Key Decisions Made

1. **dead 가설 반증** (5-13 17:30 검증) — 06:00 dead 는 일회성 가능성 ↑. `/admin/scheduler/diag` 유지. ADR § 41 신규 § 후보 (별도, 코드 변경 0).
2. **E (D-1 follow-up) + F (ka10001) 분리** — E 는 MaxPages cap + 32767 chunk (코드 6 + 테스트 5 / Migration 0). F 는 Migration 신규 (NUMERIC precision 확대) + WARN/skipped 분리. 두 chunk 원인 / 영향 범위 완전 독립.
3. **`SECTOR_DAILY_MAX_PAGES = 10 → 40`** — ka10086 실측 패턴 (1 page ~22 거래일) 차용. 3년 = ~34 page + 안전 마진 6. 실측은 ted-run TDD + 운영 검증에 위임.
4. **`DAILY_MARKET_MAX_PAGES = 40 → 60`** — 5-12 KOSDAQ 1814 누락 = 일부 종목 page > 40. 60 (안전 마진 26) 으로 상향.
5. **bulk insert chunk_size = 1000** — 32767 / 평균 13 col ≈ 2520 안전. 1000 보수치. sector_daily / daily_flow 두 Repository 적용.
6. **`_chunked_upsert(session, model, rows, *, chunk_size=1000)` helper 표준화** — Repository 공통. 미래 endpoint 즉시 적용 가능 (Phase E short_selling / lending 은 row 추정 작음 → 의무 적용 X, 향후 폭증 시 동일 helper 호출).
7. **`KiwoomMaxPagesExceededError(page, cap)` 시그니처 확장** — 운영 가시화 (어느 cap 이 얼마나 부족했는지 즉시 판단). 기존 raise/except 호환 (default kw).
8. **본 chunk 코드 변경 0** — plan doc 2 갱신 + 메타 3종 (STATUS/HANDOFF/CHANGELOG) 만. 1186 tests 그대로. ted-run 풀 파이프라인은 다음 세션 (E3).

## Known Issues

| # | 항목 | 출처 | 결정 |
|---|------|------|------|
| 13 | 일간 cron 실측 (운영 cron elapsed) | dry-run § 20.4 → § 36 / § 38 | 🔄 5-19 이후 측정 |
| 20 | NXT 우선주 sentinel 빈 row 1개 detection | § 32.3 + § 33.6 | LOW |
| **22** | `.env.prod` 의 `KIWOOM_SCHEDULER_*` 9 env 정리 | § 38.6.2' | **전체 개발 완료 후** |
| **23** | 노출된 secret 4건 회전 | § 38.8 #6/#7 | **전체 개발 완료 후** |
| **24** | Mac 절전 시 컨테이너 중단 → cron 누락 | § 38.8 #1 | 사용자 환경 결정 |
| ~~**26**~~ | ~~5-13 06:00/06:30/07:00 cron dead~~ | 5-13 17:30 재현 모니터 | ✅ **자연 재현 반증** — 17:30/18:00 정상 발화. 06:00 일회성 추정. `/admin/scheduler/diag` 유지 |
| ~~**27**~~ | ~~ka20006 sector_daily 60% 실패~~ | 본 chunk 진단 종결 | ✅ **원인 명확화** — MaxPages 56 + 32767 InterfaceError 8. endpoint-13 § 13 follow-up. ted-run 다음 세션 |
| **28** | ka10086 KOSDAQ 1814 누락 (5-12) | 본 chunk 진단 | E (endpoint-13 § 13 통합). fix = cap 40→60 + `_chunked_upsert` |
| **29** | ka10001 stock_fundamental 7.2% 실패 (5-13 18:00) | 본 chunk 진단 | **F chunk 별도** — Migration 신규 + sentinel WARN/skipped 분리. E 와 독립 |

## Context for Next Session

### 다음 세션 진입 (E3 ted-run) 시 즉시 할 일

```bash
# 1) plan doc § 13 confirm
cat docs/plans/endpoint-13-ka20006.md | sed -n '/^## 13/,/^---$/p' | head -250

# 2) 컨테이너 상태 + 백필 진행
docker compose ps
docker compose logs kiwoom-app --since 1h 2>&1 | grep -E "ka10086|daily_flow" | tail -10

# 3) DB row count (5-12 누락분)
PGPASSWORD=kiwoom psql -h localhost -p 5433 -U kiwoom -d kiwoom_db -c "
SELECT trading_date, count(*) FROM kiwoom.stock_price_krx WHERE trading_date >= DATE '2026-05-11' GROUP BY trading_date ORDER BY trading_date;
SELECT trading_date, count(*) FROM kiwoom.stock_daily_flow WHERE trading_date >= DATE '2026-05-11' GROUP BY trading_date ORDER BY trading_date;
SELECT trading_date, count(*) FROM kiwoom.sector_price_daily WHERE trading_date >= DATE '2026-05-11' GROUP BY trading_date ORDER BY trading_date;
"

# 4) ted-run 진입
# /ted-run endpoint-13-ka20006.md § 13 Phase D-1 follow-up
```

기대:
- 5-12 KRX row count: 2559 그대로 (재호출은 E4)
- 5-12 daily_flow: 1500+ (백그라운드 진행)
- 5-12 sector_daily: 59 그대로

### 사용자의 의도 (본 세션)

"다음 작업 알려줘" → 1순위 dead 모니터 진행 요청 → "병렬로 한꺼번에 진행 가능?" → A/B/C/D 병렬 실행 → 진단 결과 받고 E (D-1 follow-up #3+#4 묶음) 선택 → 측정 chunk (E1) + plan doc (E2) + 종합 (D) 본 세션 진행 / ted-run (E3) + 운영 재호출 (E4) 다음 세션 분기.

### 채택한 접근

1. **dead 재현 검증 = 자연 cron 발화 모니터** (사용자 결정 — diag 호출 vs 자연 모니터. 결과 = 자연 발화 정상)
2. **병렬 진단** — A/C 는 Explore agent + B/E1 은 Bash 직접
3. **인시던트 분리** — E (cap + 32767) vs F (NUMERIC + sentinel) 원인 / 영향 범위 완전 독립
4. **plan doc § 13 통합** — endpoint-13 메인 + endpoint-10 cross-ref. ka10086 의 fix 도 ka20006 가 진앙
5. **본 chunk 코드 변경 0** — plan doc + 메타만. ted-run 진입은 다음 세션

### 운영 위험 / 주의

- **5-12 백필 partial 적재 유지**: 본 chunk 코드 변경 0 — 운영 데이터 보존. E3 ted-run 머지 + E4 재호출 시 0 MaxPages / 0 InterfaceError 검증
- **컨테이너 백그라운드 daily_flow 진행 중**: 5-13 22:30 KST 시점 1038 row. ka10086 cap=40 부족 종목은 계속 fail. E3 cap=60 적용 후 재호출 필요
- **Mac 절전 차단 유지**: Pending #7. 절전 시 컨테이너 중단 → cron 누락

## Files Modified This Session

### 0 신규 코드
- (본 chunk 코드 변경 0)

### 2 plan doc 갱신
- `src/backend_kiwoom/docs/plans/endpoint-13-ka20006.md` § 13 신규 (Phase D-1 follow-up)
- `src/backend_kiwoom/docs/plans/endpoint-10-ka10086.md` § 14 cross-ref 추가

### 3 메타 갱신
- `src/backend_kiwoom/STATUS.md` § 0 / § 4 #26~29 / § 5 / § 6
- `HANDOFF.md` (본 파일)
- `CHANGELOG.md` prepend

### Verification

- 코드 변경 0 → 테스트 / lint / type 검증 불필요 (1186 tests 그대로)
- plan doc 자기 일관성 검증 (§ 13.2 결정 ↔ § 13.3 영향 범위 ↔ § 13.5 DoD)
- 인시던트 트리 ↔ fix 매핑 검증 (A/B/C/D/E 각 인시던트 → E or F chunk 명시)

---

_본 세션 = dead 가설 반증 (운영 가설 막힘 해소) + 신규 인시던트 3건 원인 명확화 + Phase D-1 follow-up plan doc § 13 작성. 다음 세션 = E3 ted-run 진입 (TDD → 구현 → 1R+2R → Verification → ADR § 42 → 메타 3종)._
