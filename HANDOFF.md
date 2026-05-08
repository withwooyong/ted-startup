# Session Handoff

> Last updated: 2026-05-09 08:35 (KST)
> Branch: `master`
> Latest commit: `e442416` — `feat(kiwoom): Phase C-2β — ka10086 일별 수급 자동화 (UseCase + Router + Scheduler + Lifespan, 이중 리뷰 1R PASS, 812 tests / 93.13%)`

## Current Status

backend_kiwoom **Phase C-2β 완료** — ka10086 (일별주가요청, 수급/외인/신용 22 필드) 자동화 레이어 (UseCase + Router + Scheduler + Lifespan) 구현. C-1β 패턴 mechanical 차용. 이중 리뷰 1R PASS, 커밋 완료, 푸시 대기. ka10081 (가격) + ka10086 (수급) 짝꿍이 백테스팅 base 데이터 layer 완성.

## Completed This Session

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Phase C-2β — ka10086 자동화 (UseCase + Router + Scheduler + Lifespan, 52 신규 테스트, 812 / 93.13%) | `e442416` | service/daily_flow_service.py + routers/daily_flow.py + batch/daily_flow_job.py + _deps.py + scheduler.py + settings.py + main.py + 4 신규 test 파일 + 2 회귀 + DoD |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | git push origin master | pending | 사용자 명시 승인 — 본 핸드오프 커밋 후 함께 푸시 |
| 2 | scripts/backfill_daily_flow.py CLI | pending | C-1β 동일 방식 (별도 chunk). 운영 정책 확정 후 (`--start`/`--end`/`--concurrency` + `nxt_collection_enabled` 게이팅) |
| 3 | 운영 dry-run — α/β/A3/B-α/β/γ + C-1α/β + C-2α/β 통합 검증 | pending | 가설 B (`--714`→-714) 정확성 + R15 단위 + NXT mirror cross-check + active 3000 + NXT 1500 sync 실측 시간 측정 |
| 4 | MEDIUM 2 일관 개선 (C-1β/C-2β 동시) | pending | errors → tuple / StockMasterNotFoundError 전용 예외 (다음 chunk 권고) |
| 5 | Phase C-3 (ka10082/83 주봉/월봉, P1) | not started | 같은 chart endpoint, KiwoomChartClient 메서드 추가 |
| 6 | Phase D 진입 후보 (SOR 영속화 정책 확정) | not started | stock_price_krx/nxt + stock_daily_flow 의 SOR 차단 (2b-M1) Phase D 결정 대기 |

## Key Decisions Made

- **C-1β 패턴 mechanical 차용** — UseCase / Router / Scheduler / Lifespan / Settings 시그니처 그대로 daily_flow 로 치환. 일관성으로 리뷰 부담 감소
- **indc_mode 프로세스당 단일 정책** — lifespan factory 가 `DailyMarketDisplayMode.QUANTITY` 하드코딩 주입 (백테스팅 시그널 단위 일관성, 계획서 § 2.3 권장). 향후 setting 으로 전환 시 `daily_flow_indc_mode` 추가
- **cron = KST mon-fri 19:00** (ohlcv 18:30 + 30분 후) — ohlcv 적재 완료 후 수급 적재 시점에 stock master / OHLCV 모두 최신화 보장
- **API 경로 = /api/kiwoom/daily-flow** — C-1β `/ohlcv/daily` 와 평행 명명. POST `/sync` (admin bulk) + POST `/stocks/{code}/daily-flow/refresh` (admin single) + GET `/stocks/{code}/daily-flow` (DB only)
- **GET range cap 400일** (C-1β 2b-M1 일관) — DoS amplification 차단
- **backfill 스크립트 보류** — C-1β 도 미구현 (DoD 미체크). 운영 정책 확정 후 별도 chunk
- **MEDIUM 2 (C-1β 상속) 본 chunk 범위 외** — errors mutable list / ValueError 메시지 검색은 C-1β 의 기존 패턴이므로 본 chunk 에서 손대지 않음. 다음 chunk 에서 일관 개선
- **이중 리뷰 합격 기준 = 2a + 2b 모두 CRITICAL/HIGH 0** — sonnet (1차 일반 품질) + opus (2차 적대적 보안) 독립 검증

## Known Issues

### 본 chunk 산출물 한정 (C-1β 상속)

- **errors mutable list**: `DailyFlowSyncResult.errors: list[...]` 가 frozen dataclass 안에서도 변경 가능. 외부 변형 위험 → 다음 chunk 에서 tuple 일관 개선
- **ValueError 메시지 검색**: `refresh_daily_flow` 의 `"stock master not found" in msg` 문자열 매칭 → 향후 메시지 변경 시 silent regression 위험. 전용 예외 클래스 도입 권고
- **only_market_codes max_length=4 dead constraint**: pattern `^[0-9]{1,2}$` 가 더 강함 → max_length=2 수정 (C-1β 동일)
- **DailyFlowRowOut.fetched_at: datetime | None**: ORM 컬럼은 NOT NULL server_default. 타입 불일치 → 의도 명시 주석 또는 non-Optional 권고
- **refresh_one NXT 비-Kiwoom Exception 전파**: KRX 성공 후 NXT DB 오류 발생 시 라우터에서 500. 의도적 trade-off (C-1β 동일) → ADR 권고

### 운영 검증 대기 (C-2α/β 공통)

- **가설 B 정확성**: `--714` → -714 가설. 운영 첫 호출 raw 응답 + KOSCOM 공시 cross-check 후 확정. 잘못 처리 시 net 매매 부호 반전 → 백테스팅 시그널 정반대 동작
- **R15 외인/기관/개인 순매수 단위**: `for_netprps` / `orgn_netprps` / `ind_netprps` 가 indc_tp 무시 항상 수량인지 검증 필요
- **NXT가 KRX mirror 인지 cross-check**: NXT 거래소가 외인/기관/개인 net 을 별도 집계하는지, 키움이 KRX 와 동일 값을 mirror 하는지. mirror 라면 NXT 컬럼 의미 약함
- **OHLCV cross-check**: ka10081 vs ka10086 의 같은 날 close_price 가 다르면 어느 source 정답? Phase H 데이터 품질 단계
- **active 3000 + NXT 1500 sync 실측 시간**: 30~60분 추정 — 1주 모니터 후 cron 시간 조정 (현재 19:00, 너무 빠르면 19:30)
- **페이지네이션 빈도**: 22 필드라 페이지 row 수 ka10081 보다 적을 가능성 (~300 거래일 추정)
- **NUMERIC magnitude 가드 부재** (C-2α 상속): credit_rate / foreign_rate / foreign_weight 단위 변경 시 트랜잭션 abort cascading 위험
- **idx_daily_flow_exchange cardinality** (C-2α 상속): KRX/NXT 2개 값만 → planner 가 sequential scan 선호 가능성. EXPLAIN 측정 후 Phase F 결정

### 이전 phase 알려진 이슈 상속

- **C-1α/β 알려진 이슈**: NUMERIC magnitude / list cap / MappingProxyType / chart.py private import / GET 라우터 익명 공개 / date.today() KST 명시
- **B-γ-2 알려진 이슈**: target_date 무한 / errors list 무제한 / GET /latest 익명 공개

## Context for Next Session

### 사용자의 원래 의도 / 목표

backend_kiwoom Phase C (백테스팅 코어 데이터) 구축. ka10081 (가격 OHLCV) + ka10086 (수급/외인/신용) 짝꿍 완성으로 백테스팅 base 데이터 layer 완성. Phase F (시그널 / 백테스트 엔진) 진입 전 데이터 품질 / cross-check 확정 필요.

### 선택된 접근 + 이유

- **chunk 분할 + ted-run 풀 파이프라인**: B-γ-1/2, C-1α/β, C-2α/β 패턴 일관. 인프라/자동화 분리로 적대적 리뷰 부담 감소
- **C-1β 패턴 mechanical 차용**: 이미 검증된 9개 핵심 보안 패턴 + 아키텍처를 그대로 daily_flow 도메인으로 치환. 새 설계 도입 안 함
- **2b 적대적 리뷰 (--force-2b)**: contract 분류라 자동 생략 대상이지만 C-1β 일관성 위해 강제. 1R PASS 누적
- **Quality-First** (장애 없이 / 정확한 구조로 / 확장 가능)

### 사용자 제약 / 선호

- 한글 커밋 메시지 (~/.claude/CLAUDE.md 글로벌 규칙)
- 푸시는 명시적 요청 시만 (커밋과 분리, 본 핸드오프는 사용자가 명시 요청)
- 큰 Phase 는 chunk 분할 후 ted-run 풀 파이프라인 (메모리)
- 진행 상황 가시화 — 체크리스트 + 한 줄 현황

### 다음 세션 진입 시 결정 필요

사용자에게 옵션 확인 권장:

1. **운영 dry-run** (권고) — α/β/A3/B-α/β/γ + C-1α/β + C-2α/β 통합 검증. 가설 B 정확성 + R15 단위 + NUMERIC magnitude 분포 + OHLCV cross-check + sync 실측 시간. ka10086 첫 운영 호출에서 raw 응답 측정이 가장 큰 unknown 해소
2. **scripts/backfill_daily_flow.py CLI** — C-1β 동일 방식, Phase C-2 마무리. 3년 백필 (2023-01-01 ~ 2026-05) 시간 측정
3. **Phase C-3 (ka10082/83 주봉/월봉, P1)** — 같은 chart endpoint, KiwoomChartClient 메서드 추가. ka10081 인프라 재사용
4. **MEDIUM 2 일관 개선** — errors → tuple / StockMasterNotFoundError. C-1β + C-2β 동시 적용 (refactor chunk)
5. **Phase D 진입 (SOR 영속화 정책)** — stock_price_krx/nxt + stock_daily_flow 의 SOR 차단 결정 (2b-M1)

## Files Modified This Session (commit `e442416`)

```
src/backend_kiwoom/app/application/service/daily_flow_service.py    (신규, 304 lines)
src/backend_kiwoom/app/adapter/web/routers/daily_flow.py            (신규, 339 lines)
src/backend_kiwoom/app/batch/daily_flow_job.py                      (신규, 75 lines)
src/backend_kiwoom/app/adapter/web/_deps.py                         (확장 — IngestDailyFlowUseCaseFactory)
src/backend_kiwoom/app/scheduler.py                                 (확장 — DailyFlowScheduler + DAILY_FLOW_SYNC_JOB_ID)
src/backend_kiwoom/app/config/settings.py                           (확장 — scheduler_daily_flow_sync_alias)
src/backend_kiwoom/app/main.py                                      (확장 — _ingest_daily_flow_factory + scheduler + router include)
src/backend_kiwoom/tests/test_ingest_daily_flow_service.py          (신규, 20 cases)
src/backend_kiwoom/tests/test_daily_flow_router.py                  (신규, 17 cases)
src/backend_kiwoom/tests/test_daily_flow_scheduler.py               (신규, 9 cases)
src/backend_kiwoom/tests/test_daily_flow_deps.py                    (신규, 4 cases)
src/backend_kiwoom/tests/test_scheduler.py                          (회귀 1줄 — SCHEDULER_DAILY_FLOW_SYNC_ALIAS)
src/backend_kiwoom/tests/test_stock_master_scheduler.py             (회귀 1줄 — SCHEDULER_DAILY_FLOW_SYNC_ALIAS)
src/backend_kiwoom/docs/plans/endpoint-10-ka10086.md                (DoD § 10.1/10.2 갱신)
```

14 files changed, 2436 insertions(+), 12 deletions(-).
