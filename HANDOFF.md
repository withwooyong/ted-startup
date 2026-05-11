# Session Handoff

> Last updated: 2026-05-11 (KST, /handoff) — chart 영숫자 stk_cd 가드 완화 (옵션 c-A) Chunk 1 dry-run + Chunk 2 구현 완료.
> Branch: `master`
> Latest commit: `ef7d598` (Chunk 2 구현 / 1046 tests / coverage 91% / ADR § 33)
> 미푸시 commit: **2 건** (`a14bb10` Chunk 1 + `ef7d598` Chunk 2 — 이전 commits 는 push 완료)

## Current Status

Phase C 사실상 종결 — chart endpoint (ka10081/82/83/94 + ka10086) 가 우선주 `*K` / 영숫자 ETF 호환. STATUS § 5 #1 의 "ETF/ETN OHLCV 별도 endpoint (옵션 c)" 의 사용자 분기 **옵션 A (가드 완화만)** 채택. 2단계 진행 — Chunk 1 = 운영 dry-run (코드 0), Chunk 2 = `STK_CD_CHART_PATTERN` 신규 + chart 계열 11곳 가드 교체. lookup 계열 (ka10100/ka10001) 은 Excel R22 ASCII 제약 그대로 유지. 1037→1046 tests / coverage 81%→91%. ADR § 32 + § 33 신규.

## Completed This Session

| # | Task | 결과 | Files |
|---|------|------|-------|
| 1 | 다음 chunk 선택 분기 — 옵션 c-A (우선주 가드 완화만) 합의 | 사용자 결정 / plan doc 신규 | 0 |
| 2 | plan doc 작성 — Chunk 1/2 2단계 진행 명세 | `phase-c-chart-alphanumeric-guard.md` (~410줄) | 1 |
| 3 | dry-run 스크립트 작성 — build_stk_cd 우회, 단건 캡처, verdict 자동 분류 | `dry_run_chart_alphanumeric.py` (~320줄) | 1 |
| 4 | env 변수명 fallback fix — `KIWOOM_API_KEY` ↔ `KIWOOM_APPKEY` legacy 호환 | 사용자 dry-run 실행 차단 해소 | 1 (in-place edit) |
| 5 | Chunk 1 dry-run 실행 + 결과 분석 (12 호출) | `a14bb10` / KRX 6/6 SUCCESS + NXT 6/6 empty / ADR § 32 / 코드 0줄 | 6 |
| 6 | Chunk 2 구현 — `STK_CD_CHART_PATTERN` 신규 + chart 11곳 가드 교체 | `ef7d598` / 1046 tests / coverage 91% / ADR § 33 | 21 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| **1** | **영숫자 295 종목 백필** | **다음 chunk 1순위** | Chunk 2 머지 후 cron 자연 수집 또는 `backfill_ohlcv.py --resume` 별도 chunk. ~200K rows 추가 |
| 2 | KOSCOM cross-check 수동 | 대기 | 가설 B 최종 확정 |
| 3 | Phase D — ka10080 분봉 / ka20006 업종일봉 | 대기 | 대용량 파티션 결정 선행 |
| 4 | Phase E (공매도/대차) / F (순위) / G (투자자별) | 대기 | 신규 endpoint wave |
| **최종** | **scheduler_enabled 일괄 활성 + 1주 모니터** | 사용자 결정 보류 | 모든 작업 완료 후 활성. 측정 #13 일간 cron elapsed + 신규 #19 영숫자 +10분 |

## Key Decisions Made

1. **옵션 c-A 채택 (우선주 가드 완화만)** — ETF 시장 (`market_code=8`) 신규 수집은 `master.md` § 0.3 ("ETF/ELW/금현물 제외") 결정 유지. 영숫자 코드의 실제 분포는 우선주 (`*K` suffix) dominant — 가드만 풀어도 195~295 종목 추가 적재 가능
2. **2단계 진행 — Chunk 1 dry-run 절대 선행** — 키움 chart endpoint 가 영숫자 stk_cd 수용한다는 가정이 docs 부재. 1~3건 운영 호출 검증 없이 진입 시 295 종목 fail 누적 위험. plan doc § 5 H-1 명시
3. **LOOKUP/CHART 패턴 분리** — Excel R22 ASCII 제약 (ka10100 R22 "Length=6 ASCII 0-9 only") 은 그대로 유지. chart 계열만 `^[0-9A-Z]{6}$` 로 분리. 단일 source `STK_CD_LOOKUP_PATTERN` 의 보수적 재사용을 의도적으로 깨고 두 패턴 공존
4. **lowercase 거부 유지** — CHART 패턴 (`^[0-9A-Z]{6}$`) 이 영문 대문자만 허용. 키움 응답/마스터 모두 uppercase 만 관찰 — lowercase 입력은 mock/test 사고로 간주
5. **NXT 우선주 미지원 확정** — Chunk 1 dry-run 에서 NXT 6/6 empty (sentinel 빈 row 1 / row 0). 기존 `stock.nxt_enable=False` 정책이 자연 차단 — Chunk 2 의 NXT 처리 변경 0
6. **테스트 의미 반전 + 신규 보호 단언** — chart 계열 기존 거부 단언 6건이 영숫자 허용으로 의미 반전 (testcontainers 자동 발견). lookup 계열에는 신규 보호 단언 추가 (`test_validate_stk_cd_for_lookup_still_rejects_alphanumeric`) — 향후 chart 패턴이 lookup 으로 잘못 전이되는 회귀 방지

## Known Issues

| # | 항목 | 출처 | 결정 |
|---|------|------|------|
| **19** | 영숫자 295 종목 추가로 cron elapsed +10분 추정 | ADR § 33.6 | scheduler_enabled 활성화 chunk + 첫 영업일 모니터에서 정량화 |
| **20** | NXT 우선주 sentinel 빈 row 1개 detection | ADR § 32.3 + § 33.6 | LOW priority — 운영 영향 0 (`nxt_enable=False` 자연 차단). 미래 chunk 에서 `if not <list> or all(not row.<key>): break` 패턴 검토 |
| **13** | 일간 cron 실측 (운영 cron elapsed) | dry-run § 20.4 | scheduler_enabled 활성화 chunk |

> 13/19 는 scheduler 활성화 chunk 에서 통합 측정. 20 은 LOW — 운영 차단 없음.

## Context for Next Session

### 사용자의 의도

세션 시작 시 "다음작업 알려줘" 요청. STATUS § 5 의 우선순위 후보 중 **#1 ETF/ETN OHLCV 별도 endpoint (옵션 c)** 선택 → 내부 분기에서 **옵션 A (우선주 가드 완화만)** 선택. ETF 시장 신규 수집은 master.md 결정 (§ 0.3) 유지 의지 명확.

### 채택한 접근

1. **plan doc 우선 작성** — `src/backend_kiwoom/docs/plans/phase-c-chart-alphanumeric-guard.md` 신규. 메타 / 범위 / Chunk 1+2 DoD / 적대적 self-check H-1~10 / 다음 chunk
2. **Chunk 1 dry-run** — 임시 스크립트 `dry_run_chart_alphanumeric.py` 로 `build_stk_cd` 가드 우회. 단건 캡처 + verdict 자동 분류 + JSON 캡처 (gitignored)
3. **Chunk 2 구현** — `STK_CD_CHART_PATTERN` 신규 + `_validate_stk_cd_for_chart` 함수 + chart 5 router 7 path + 3 UseCase `_KA*_COMPATIBLE_RE` 교체. lookup 5곳 무변

### 사용자 환경 제약

- DB는 docker-compose `kiwoom-db` 컨테이너 (포트 5433 / kiwoom/kiwoom/kiwoom_db / schema `kiwoom`). DataGrip 직접 접속
- 자격증명은 `.env.prod` 의 `KIWOOM_API_KEY` / `KIWOOM_API_SECRET` (legacy `KIWOOM_APPKEY` / `KIWOOM_SECRETKEY` 도 fallback 호환)
- captures/ 는 .gitignore (운영 데이터 보호)

### 다음 세션 진입 시점 결정 필요

| 옵션 | 설명 | 비용 |
|------|------|------|
| **A. 영숫자 295 종목 백필** | `backfill_ohlcv.py --resume` 별도 chunk. ~200K rows 추가 적재. KRX 만 (NXT 우선주 미지원) | 30분~수시간 |
| B. scheduler_enabled 활성 | 운영 cron 일괄 활성 + 1주 모니터. 측정 #13/#19 정량화 | 1주 모니터링 |
| C. Phase D 진입 | ka10080 분봉 / ka20006 업종일봉. 대용량 파티션 결정 선행 | 신규 도메인 + 파티션 |
| D. KOSCOM cross-check | 수동 1~2건 가설 B 확정 | 수동 |

권장: **A → B → C** 순서 (Phase C 백필 마무리 → 운영 검증 → Phase D 진입). 단 사용자 결정.

### 운영 위험

- Chunk 2 머지 후 첫 cron 실행에서 영숫자 종목 ~295 건 추가 호출 시작 — KiwoomBusinessError 1~5건 가능 (Chunk 1 dry-run 은 3건만 검증). router 의 KiwoomError 5종 핸들러 (R2 E-1 완료) 가 보호. 사후 모니터링 필요
- OHLCV daily cron elapsed 34분 → ~44분 추정 (2초 rate limit 직렬 × 295)

## Files Modified This Session

### Chunk 1 (`a14bb10`) — 6 files
- 신규 `src/backend_kiwoom/docs/plans/phase-c-chart-alphanumeric-guard.md` (~410줄)
- 신규 `src/backend_kiwoom/scripts/dry_run_chart_alphanumeric.py` (~320줄)
- 신규 `src/backend_kiwoom/docs/operations/dry-run-chart-alphanumeric-results.md`
- 갱신 `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` (§ 32)
- 갱신 `src/backend_kiwoom/STATUS.md` (§ 0 + § 5 #1 + § 6)
- 갱신 `CHANGELOG.md` (prepend)

### Chunk 2 (`ef7d598`) — 21 files
- 코드 (8): `stkinfo.py` + `chart.py` + `mrkcond.py` + 3 router (`ohlcv.py` / `ohlcv_periodic.py` / `daily_flow.py`) + 3 service (`ohlcv_daily_service.py` / `ohlcv_periodic_service.py` / `daily_flow_service.py`)
- 테스트 (8): `test_exchange_type.py` + `test_kiwoom_chart_client.py` + `test_kiwoom_mrkcond_client.py` + `test_kiwoom_stkinfo_basic_info.py` (+4 신규) + 3 service test (의미 반전) + 2 router test (`test_ohlcv_router.py` / `test_daily_flow_router.py`, +2 신규)
- 문서 (3): `ADR-0001-backend-kiwoom-foundation.md` (§ 33) / `STATUS.md` / `CHANGELOG.md`

### Verification

- ruff All checks passed
- mypy --strict Success
- pytest 1046 PASS / coverage 91%

---

_Phase C 사실상 종결 (chart endpoint 영숫자 호환성 확장). 다음은 영숫자 백필 / scheduler 활성 / Phase D 중 사용자 결정 대기._
