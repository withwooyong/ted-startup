# Session Handoff

> Last updated: 2026-05-07 (KST) — **backend_kiwoom Phase C 계획서 5건 완성 (백테스팅 OHLCV + 일별 수급)**
> Branch: `master` (working tree dirty — Phase C 5 계획서 + CHANGELOG/HANDOFF 미커밋)
> Latest commit: `66a5745` — feat(v1.2): Cp 2β — IndicatorParametersDrawer 편집 UI 배선
> 세션 시작점: 위와 동일 (`66a5745`) — 본 세션도 **커밋 0건**

## Current Status

`backend_kiwoom` 의 **Phase A 3건 + Phase B 3건 + Phase C 5건 = 11 endpoint 계획서** 작성 완료. 25 endpoint 중 **11 완성 (44%)**. 코드는 0줄. 다음 세션 Phase D 보강 시계열(분봉/틱/업종) 또는 Phase A·B·C 코드화 착수 결정 필요.

**Phase C 가 끝나면 가능한 것**:
- KRX/NXT 분리 일/주/월/년봉 시계열 (8 테이블) — backtest engine 즉시 진입 가능
- stock_daily_flow 일별 수급 (투자자별 net + 외인 + 신용) — 시그널 보강 입력
- backend_py 의 BacktestEngineService 와 동등한 분석 가능 (KRX 데이터)
- KRX vs NXT 가격 차이 / 거래량 분리 검증 가능

## Completed This Session (Documentation only)

| # | 산출물 | 위치 | 줄수 | 성격 |
|---|--------|------|------|------|
| 1 | endpoint-06-ka10081 | `src/backend_kiwoom/docs/plans/endpoint-06-ka10081.md` | **1,172** | 일봉 ★ 백테스팅 코어 — Phase C reference. KRX/NXT 동시 + Mixin/Repository/UseCase 정의 |
| 2 | endpoint-07-ka10082 | `src/backend_kiwoom/docs/plans/endpoint-07-ka10082.md` | 415 | 주봉 — ka10081 패턴 복제 (차이점만) |
| 3 | endpoint-08-ka10083 | `src/backend_kiwoom/docs/plans/endpoint-08-ka10083.md` | 324 | 월봉 — 동일 |
| 4 | endpoint-09-ka10094 | `src/backend_kiwoom/docs/plans/endpoint-09-ka10094.md` | 413 | 년봉 — 7 필드만 + NXT skip 정책 |
| 5 | endpoint-10-ka10086 | `src/backend_kiwoom/docs/plans/endpoint-10-ka10086.md` | 847 | 일별주가 ★ 시그널 — 22 필드, 투자자별+외인+신용, 별도 URL `/mrkcond` |
| 6 | CHANGELOG.md prepend | `CHANGELOG.md` | +120 | 본 세션 항목 |
| 7 | HANDOFF.md overwrite | `HANDOFF.md` | — | 본 문서 |

**Phase C 5건 = 3,171줄. 코드 변경 0.**

**Phase A + B + C 누적 = 11 endpoint × 평균 760줄 = ~8,400줄 + master.md 653줄 = ~9,000줄 계획서. 25 endpoint 중 11 완성 (44%).**

## In Progress / Pending

| # | 항목 | 상태 | Notes |
|---|------|------|-------|
| 1 | **다음 세션: Phase D 계획서 3건** | 🟢 즉시 가능 | `endpoint-11-ka10079.md`(틱), `endpoint-12-ka10080.md`(분봉), `endpoint-13-ka20006.md`(업종 일봉). 보강 시계열. ka10079 는 데이터 폭증 경고 — 화이트리스트 정책 결정 필요 |
| 2 | **Phase A·B·C 코드화 착수 (대안)** | 🟡 결정 필요 | master.md § 11 권고는 Phase 단위 교차. Phase C 까지 코드화 = stock + stock_fundamental + sector + 8 OHLCV 테이블 + stock_daily_flow 모두 영속화. 백테스팅 엔진 즉시 검증 가능 |
| 3 | **본 세션 결과 커밋** | ⏳ 사용자 대기 | 추천 메시지: `docs(kiwoom): Phase C 5건 — 백테스팅 OHLCV (KRX/NXT 분리) + 일별 수급 시그널` |
| 4 | Phase E~G 계획서 (시그널 보강 / 순위 / 투자자별) | 🟡 후순위 | Phase D 후 진입. 11 endpoint 남음 |

## Key Decisions Made (본 세션)

### Phase C 핵심 설계

1. **물리 분리 OHLCV 테이블 8개**: `stock_price_{krx,nxt}` × `{daily, weekly, monthly, yearly}`. master.md § 3.1 의 KRX/NXT 분리 원칙 구현
2. **`_DailyOhlcvMixin` SQLAlchemy mixin**: 8 테이블 컬럼 공유 (open/high/low/close/volume/amount + prev_compare + turnover_rate). 컬럼 추가/변경 시 한 곳만 수정
3. **Migration 003 (KRX OHLCV) + 004 (NXT OHLCV) 분리**: 운영 중 NXT 활성화 토글 가능 — NXT 거래소 운영 정책 변동에 대응
4. **Migration 005 (stock_daily_flow)**: ka10086 만의 별도 — OHLCV 와 수급 책임 분리
5. **수정주가 강제** (`upd_stkpc_tp=1`): 백테스팅 일관성. raw 모드 (`upd_stkpc_tp=0`) 는 비교 검증용. UseCase 의 `adjusted` 파라미터로 분기
6. **NXT 년봉 호출 skip**: NXT 거래소 ~2025-03 시작 가정 — 부분 년 데이터 의미 약. RPS 절약 효과
7. **bulk batch 50 commit**: ka10081 BulkUseCase. SAVEPOINT 시장 격리 + 50건마다 commit. 중간 오류 격리
8. **`Period` StrEnum + IngestPeriodicOhlcvUseCase**: 주/월/년봉이 같은 UseCase 의 dispatch — 코드 공유. 일봉만 별도 (호출 빈도 + row 수 압도적이라 별도 hot path)

### ka10086 (일별 수급) 핵심

9. **OHLCV 중복 적재 안 함**: ka10081 = 가격 정답, ka10086 = 수급 책임. ka10086 응답의 8 OHLCV 필드는 stock_daily_flow 에 영속화 안 함
10. **이중 부호 처리** (`--714`): `_strip_double_sign_int` helper. Excel 예시 모호 → 가설 B 채택 (`--714` = -714). 운영 첫 호출 raw 측정 후 가설 수정
11. **외인순매수 단위 항상 수량** (Excel R15 주의): `indc_tp` 무시. 거래소가 금액 데이터 제공 안 함. R15 가정이 틀리면 수십% 시그널 오차 → 운영 검증 1순위
12. **`indc_mode=QUANTITY` 기본**: 다른 종목 비교 시 가격 변동 무관, 시그널 단위 일관성 확보. AMOUNT 모드는 별도 row 가능성 — 단위 mismatch 위험으로 권장 안 함
13. **stock_daily_flow UNIQUE = (stock_id, trading_date, exchange)**: KRX/NXT 분리 row. 같은 종목·같은 날 두 거래소 수급 분리 추적
14. **`for_poss` 누적값 raw 적재**: 일별 변화 (외인 매도 시그널) 는 백테스팅 엔진의 derived feature 책임 — 본 endpoint 는 raw 만

### 4 chart endpoint 공유 결정

15. **list 키만 다름** (`stk_dt_pole_chart_qry` / `stk_stk_pole_chart_qry` / `stk_mth_pole_chart_qry` / `stk_yr_pole_chart_qry`)
16. **응답 필드 수**: 일/주/월봉 = 10 필드, 년봉 = 7 필드 (pred_pre/pred_pre_sig/trde_tern_rt 누락)
17. **`KiwoomChartClient` 단일 클래스**: 4 메서드 (fetch_daily/weekly/monthly/yearly). 같은 PATH `/api/dostk/chart` + api_id 만 다름
18. **백필 페이지네이션 빈도**: 일봉 1~12 페이지, 주/월/년봉은 1 페이지 충분 (3년 백필 기준)
19. **cron 분산**: 일봉 매일 18:30 / 주봉 금 19:00 / 월봉 매월 1일 03:00 / 년봉 매년 1월 5일 03:00 / 일별수급 매일 19:00 — 시간대 충돌 회피

## Known Issues

### 운영 검증 미완 (DoD § 10.3 모음 — 실 키움 호출 후 확정)

| Endpoint | 미확정 항목 | 영향 |
|----------|------------|------|
| ka10081 | 1 페이지 응답 row 수 (60? 600?) | 백필 페이지 수 추정 + max_pages 조정 |
| ka10081 | `dt` 정렬 (ASC/DESC) | 백테스팅 엔진의 시계열 가정 |
| ka10081 | `trde_prica` 단위 (백만원 추정) | 컬럼 주석 + 거래대금 시그널 정확도 |
| ka10081 | NXT 응답 stk_cd (`005930_NX` 보존 vs stripped) | strip_kiwoom_suffix 안전망 동작 |
| ka10081 | NXT 운영 시작일 이전 base_dt 응답 패턴 | 백필 가드 결정 |
| ka10081 | `cont-yn` + `next-key` 형식 | 페이지네이션 안전성 |
| ka10081 | 키움 vs pykrx close_price 일치도 (±1 KRW 이내) | 데이터 source 신뢰도 |
| ka10081 | active 3000 + NXT 1500 sync 실측 (30~60분 추정) | cron grace 조정 |
| ka10082 | `dt` 가 주 시작일(월) 인지 종료일(금) 인지 | trading_date 매핑 의미 |
| ka10082 | 응답 list 키 `stk_stk_pole_chart_qry` 정확성 | Pydantic alias 필요 여부 |
| ka10082 | 일봉 합성 vs 키움 주봉 OHLC 일치 | 데이터 정합성 검증 |
| ka10083 | `dt` 가 달의 첫 거래일 인지 | trading_date 매핑 |
| ka10094 | NXT 호출 응답 (2024년 이전 base_dt 시 빈 list?) | NXT skip 정책 검증 |
| ka10094 | 30년 백필 페이지네이션 발생 여부 (1 페이지 가정) | max_pages 조정 |
| ka10094 | 부분 년 OHLC (신규 상장) 응답 패턴 | 적재 정책 결정 |
| **ka10086** | **이중 부호 의미 (`--714` = -714 인지 +714 인지)** | **net 매매 부호 반전 위험 — 백테스팅 시그널 정반대 동작** |
| **ka10086** | **외인/기관/개인 순매수가 indc_tp 무시 항상 수량인지 (R15 검증)** | **단위 mismatch 시 수십% 시그널 오차** |
| ka10086 | `crd_rt` 신용비 정의 (잔고 비율 vs 거래 발생률) | master.md § 12 정의 명시 |
| ka10086 | NXT 의 투자자별 net 이 KRX mirror 인지 분리 집계인지 | NXT 컬럼의 의미 결정 |
| ka10086 | ka10081 vs ka10086 의 같은 날 close_price 일치 | 데이터 source 신뢰도 |
| ka10086 | 1 페이지 row 수 (22 필드라 ka10081 보다 적을 가능성, ~300?) | max_pages 조정 |

### 알려진 위험 (계획 단계, 본 세션 추가)

- **이중 부호 처리가 Phase C 의 단일 가장 큰 unknown**: ka10086 의 `--714` 가설 잘못되면 백테스팅 시그널 정반대. 운영 첫 호출에서 같은 일자 KOSCOM 공시 vs ka10086 응답 비교로 확정 필수
- **외인순매수 단위 R15 가정의 정확성**: indc_tp=1 (금액 모드) 호출해도 외인 net 가 수량인지 운영 검증. 만약 금액으로 오면 stock_daily_flow 의 *_net_purchase 컬럼 의미 변경 + migration 필요
- **OHLCV cross-check ka10081 vs ka10086**: 같은 날 close_price 가 다르면 어느 source 가 정답인가? 키움 내부에서도 chart vs mrkcond 카테고리가 다른 source 를 쓸 가능성 — 의심되면 raw_response 테이블의 JSON 으로 추적
- **NXT 거래소 운영 시작일 미확정**: ~2025-03 가정. 정확한 시작일 알면 ka10094 NXT skip 가드 / 백필 가드 정확화. 운영 검증 1주차에 측정
- **`for_poss` 누적값 vs 일별 변화**: 본 endpoint 는 raw 적재. diff 는 백테스팅 엔진 책임. 단 로직 분산되면 정합성 추적 어려워질 수 있음 — Phase F 에서 trigger 컬럼 검토
- **bulk 4500 호출 30~60분 동안 자격증명 만료**: au10001 토큰 24시간 유효 가정. 만료 시 자동 재발급 (Phase A) 동작 검증 — 1회 sync 중에 만료될 가능성 낮지만 백필은 4시간+ 가능
- **수정주가 보장**: `upd_stkpc_tp=1` 이 정확히 KRX 의 수정주가와 같은지 운영 검증 — `pykrx` close_price 와 ±1 KRW 비교
- **bulk batch commit 중 자격증명/RPS 거부 누적**: 50건 단위 commit 후 다음 batch 진입 불가 시 alert 필요. Phase B 의 partial 실패 정책 (1%/10%) 본 endpoint 도 동일 적용

## Context for Next Session

### 사용자의 원 목적 (본 세션 흐름)

세션 진입 시 사용자가 던진 첫 요청은 "Phase C 계획서 5건(ka10081/82/83/94/86, 백테스팅 본체) 진입". 직전 메시지에서 Phase A·B 6건 + master.md + SPEC.md 일괄 커밋 + v1.2 분리 커밋 + 푸시 (`b3e2546..66a5745`) 완료.

수행 흐름:
1. **Excel 5 시트 정독** — openpyxl 로 ka10081/82/83/94 (각 42~45행) + ka10086 (56행) 풀 dump. 응답 list 키 + 22 필드 + 이중 부호 + R15 주의 발견
2. **endpoint-06-ka10081.md** (1,172줄) — Phase C reference. _DailyOhlcvMixin / KiwoomChartClient / IngestDailyOhlcvUseCase / Bulk + Backfill / KRX-NXT 동시 호출
3. **endpoint-07-ka10082.md** (415줄) — ka10081 패턴 복제. list 키만 다름 + StockPricePeriodicRepository / IngestPeriodicOhlcvUseCase 통합
4. **endpoint-08-ka10083.md** (324줄) — ka10082 와 동일 구조. 매월 1일 cron
5. **endpoint-09-ka10094.md** (413줄) — 7 필드만 + NXT skip 정책
6. **endpoint-10-ka10086.md** (847줄) — 22 필드 5 카테고리 + URL `/mrkcond` + 이중 부호 처리 + stock_daily_flow 별도 테이블
7. **CHANGELOG prepend + HANDOFF overwrite** — 세션 마감

### 선택한 접근과 이유

- **ka10081 reference + 3 endpoint 짧은 형식**: Phase B 의 ka10099/100/001 처럼 첫 endpoint 가 패턴 + 나머지가 차이점만 작성 — 후속 endpoint 600~880줄에서 300~415줄로 축소 가능. 검토 가능성 + 재사용성 ROI 양호
- **ka10086 별도 카테고리로 길게**: URL 다르고 22 필드 + 이중 부호 처리 + 카테고리 분해 (5 카테고리) 가 unique → 짧게 못 씀. ka10081 와 책임 분리 명시 필요
- **Mixin + Periodic Repository 통합**: 4 chart endpoint 의 ORM/Repository/UseCase 가 ~1,000줄 안에 들어오게 설계 — 8 테이블이지만 mixin 으로 컬럼 정의 80줄
- **이중 부호 가설 B 명시 + 운영 검증 1순위 표시**: `_strip_double_sign_int` 의 docstring 에 가설 + DoD § 10.3 + § 11.1 결정 필요 + § 11.2 알려진 위험 4중 명시. 운영 검증 시 forget 방지
- **OHLCV 중복 처리 정책**: ka10081 정답 / ka10086 적재 안 함 — 두 endpoint 의 책임 분리를 master.md § 12 결정 기록 후보로 명시
- **NXT 운영 시작일 가정**: ~2025-03 추정. 운영 1주차 측정 후 정확한 시작일을 master.md § 12 에 기록 — ka10094 NXT skip 정책의 근거

### 사용자 선호·제약 (재확인)

- **한국어 커밋 메시지 + Co-Authored-By** (전역 CLAUDE.md)
- **`git push` 명시 요청 시에만** — 본 세션도 커밋 없음 (사용자가 검토 후 커밋 결정)
- **선택지 제시 후 사용자 결정** — 본 세션은 명시적 명령으로 진입, 추가 분기 없음
- **체크리스트 + 한 줄 현황** (memory: feedback_progress_visibility) — TaskCreate 7건 사용
- **block-no-verify heredoc 오탐지 대응** (memory: project_block_no_verify_heredoc_pitfall) — 직전 세션 커밋에서 `git commit -F <file>` 우회 패턴 사용 (본 세션은 커밋 없음)

### 다음 세션에서 먼저 확인할 것

1. **Phase C 5 endpoint + CHANGELOG/HANDOFF 일괄 커밋 여부** — 추천: `docs(kiwoom): Phase C 5건 — 백테스팅 OHLCV (KRX/NXT 분리) + 일별 수급 시그널`
2. **다음 단계 합의** — 세 옵션:
   - (A) **Phase D 계획서 3건** — `ka10079`(틱) / `ka10080`(분봉) / `ka20006`(업종일봉). 보강 시계열. ka10079 데이터 폭증 정책 결정 필요
   - (B) **Phase A·B·C 코드화 착수** — master.md § 11 권고. 11 endpoint = 가장 큰 마일스톤 (백테스팅 엔진 즉시 검증 가능)
   - (C) **Phase E~G 계속 (계획서만)** — 25 endpoint 중 14 남음. 계획 완료 후 일괄 코드화 옵션
3. **Phase A 코드화 시점 합의** — 위 (A)/(B)/(C) 와 연동
4. **운영 검증 우선순위 정의** — Phase C 코드화 후 첫 호출 시점. master.md § 12 결정 기록 승격 항목 6개 (`dt` 정렬, 단위, 이중 부호, R15, NXT 시작일, OHLCV cross-check)

### Phase D 의 핵심 (다음 세션 준비)

- **ka10079 (틱)**: 응답 row 폭증 — 1초당 수백 건 가능. 화이트리스트 정책 결정 필수 (모든 종목 X, 핵심 종목만)
- **ka10080 (분봉)**: tic_scope 1/3/5/10/30/60분. stock_minute_price 테이블, 월별 파티션 권장
- **ka20006 (업종 일봉)**: ka10081 패턴 복제 + sector 마스터 (ka10101) 참조. sector_price_daily 테이블
- **DB**: Migration 006 (intraday — minute/tick), Migration 007 (sector_price_daily)
- **Phase D 의존**: Phase B 의 stock + sector 마스터, Phase C 의 패턴 (Mixin/Repository)

### 가치 있는 발견 (본 세션)

1. **이중 부호 (`--714`) 의 운영 검증 우선순위**: Excel 예시가 가장 모호한 항목. 가설 잘못되면 백테스팅 시그널 정반대 → 4중 명시 (Pydantic helper / DoD / 결정 표 / 위험 표)
2. **R15 외인순매수 단위 mismatch**: indc_tp 무시 항상 수량 — 키움 명시 주의 사항이 운영 시그널 정확도의 핵심. 컬럼 주석에 명시 + 정규화 로직 분기
3. **OHLCV 책임 분리**: ka10081 (가격) + ka10086 (수급) 의 같은 OHLCV 필드 중복을 "정답 + 보강" 로 분리. 데이터 source 모호성을 명시 결정으로 해소
4. **`_DailyOhlcvMixin` 의 ROI**: 8 테이블 컬럼 공유 80줄로 중복 800줄 절약. SQLAlchemy mixin 의 검증된 패턴
5. **NXT 운영 시작일 가정의 영향**: ka10094 의 NXT skip / 모든 NXT 호출의 백필 가드 / KRX vs NXT mirror 검증 — 한 가정이 5+ 결정에 영향. 운영 1주차 측정으로 확정
6. **Phase C 4 chart endpoint 의 코드 공유**: ka10081 reference 700줄 + 나머지 3 endpoint 합쳐 300줄. ka10082/83/94 가 사실상 dispatch 분기 + ORM 정의만
7. **bulk 4500 호출 sync 의 자격증명 만료 위험**: 30~60분 sync 가 토큰 24시간 만료에 못 미치지만, 4시간+ 백필은 자동 재발급 동작 검증 1순위
8. **stock_daily_flow 의 indc_mode mismatch 위험**: 같은 (stock, date, exchange) 에 0 (수량) 후 1 (금액) 적재 시 단위 섞임. UNIQUE 제약 안에서 단위 가드 필요할 수 있음 — Phase F 단계에서 트리거 추가 검토
9. **bulk SAVEPOINT + 50 batch commit 패턴의 일반화**: ka10099 시장 격리에서 시작 → ka10001 종목 격리 → ka10081 종목+거래소 격리. 모든 bulk endpoint 의 통일 패턴
10. **Phase C 의 `Period` StrEnum dispatch**: 4 chart endpoint 의 UseCase 통합 — 새 period 추가 (예: 분기봉) 시 enum + 메서드 추가만으로 Repository/Migration 재사용

## Files Modified This Session

```
신규 파일 (untracked):
src/backend_kiwoom/docs/plans/
├ endpoint-06-ka10081.md         1,172 줄 신규 ★ Phase C reference
├ endpoint-07-ka10082.md         415 줄 신규
├ endpoint-08-ka10083.md         324 줄 신규
├ endpoint-09-ka10094.md         413 줄 신규
└ endpoint-10-ka10086.md         847 줄 신규 ★ 시그널 보강

기존 파일 갱신:
CHANGELOG.md                     +120 줄 prepend (본 세션 항목)
HANDOFF.md                       overwrite (본 문서)
```

**0 commits, 5 docs new (Phase C) + 2 updated. Phase A·B·C 누적 = 11 endpoint 계획서 + master.md + SPEC.md.**

### Context to Load (다음 세션)

Phase D 계획서 작성 또는 Phase A·B·C 코드화 시 먼저 로드할 파일:

```
src/backend_kiwoom/docs/plans/master.md                    # 25 endpoint 카탈로그 + Phase D 정의 + per-endpoint 템플릿
src/backend_kiwoom/docs/plans/endpoint-06-ka10081.md       # Phase C reference — Mixin/KiwoomChartClient/IngestDailyOhlcvUseCase
src/backend_kiwoom/docs/plans/endpoint-07-ka10082.md       # Phase C 패턴 복제 — Period StrEnum / Periodic Repository
src/backend_kiwoom/docs/plans/endpoint-10-ka10086.md       # Phase C 별도 카테고리 — _strip_double_sign_int / 22 필드 분해
src/backend_kiwoom/docs/plans/endpoint-03-ka10099.md       # Phase B — stock + nxt_enable (Phase D 의 stock 보강 의존)
src/backend_kiwoom/docs/plans/endpoint-14-ka10101.md       # Phase A — sector 마스터 (Phase D ka20006 의존)
src/backend_kiwoom/docs/키움 REST API 문서.xlsx             # ka10079/ka10080/ka20006 시트 정독 (Phase D)
```

다음 세션 첫 명령 추천:
- (A) `Phase D (ka10079/ka10080/ka20006) 계획서 3건 작성해줘` — 보강 시계열
- (B) `Phase C 커밋 후 Phase A 부터 코드화 착수해줘` — master.md § 11 권고
- (C) `Phase E·F·G 계획서 11건 일괄 작성해줘` — 25 계획서 후 일괄 코드화
