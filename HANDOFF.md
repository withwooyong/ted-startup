# Session Handoff

> Last updated: 2026-05-07 (KST) — **backend_kiwoom Phase B 계획서 3건 완성 (ka10099/ka10100/ka10001)**
> Branch: `master` (working tree dirty — Phase A·B 6 endpoint 계획서 + master.md + SPEC.md + 이전 세션 v1.2 Cp 2β 누적 untracked)
> Latest commit: `b3e2546` — docs: 세션 마감 핸드오프 — v1.2 Discovery + Cp 0/1/2α 완주 반영
> 세션 시작점: 위와 동일 (`b3e2546`) — 본 세션도 **커밋 0건**

## Current Status

`backend_kiwoom` 의 **Phase A 3건 + Phase B 3건 = 6 endpoint 계획서** + 통합 master.md + backend_py SPEC.md 작성 완료. 코드는 0줄 — 다음 세션 Phase C (백테스팅 OHLCV 본체 5건) 진입 또는 Phase A 코드화 시작 결정 필요.

**Phase B 가 끝나면 가능한 것**:
- `SELECT FROM stock WHERE nxt_enable=true AND is_active=true` → Phase C 의 NXT 호출 큐 즉시 생성
- 종목 마스터(stock) + 일별 펀더멘털(stock_fundamental) + 업종(sector) 모두 적재
- Phase C 의 ka10081 일봉 수집이 종목 큐 + NXT 큐로 즉시 시작 가능

## Completed This Session (Documentation only)

| # | 산출물 | 위치 | 줄수 | 성격 |
|---|--------|------|------|------|
| 1 | endpoint-03-ka10099 | `src/backend_kiwoom/docs/plans/endpoint-03-ka10099.md` | ~720 | 종목 리스트 (mrkt_tp 16종, NXT enable source) |
| 2 | endpoint-04-ka10100 | `src/backend_kiwoom/docs/plans/endpoint-04-ka10100.md` | ~510 | 단건 조회 (gap-filler, lazy fetch) |
| 3 | endpoint-05-ka10001 | `src/backend_kiwoom/docs/plans/endpoint-05-ka10001.md` | ~880 | 펀더멘털 (45 필드, 외부 벤더 PER/ROE) |
| 4 | CHANGELOG.md prepend | `CHANGELOG.md` | +85 | 본 세션 항목 |
| 5 | HANDOFF.md overwrite | `HANDOFF.md` | — | 본 문서 |

**Phase B 3건 = ~2,100줄. 코드 변경 0.**

**Phase A + Phase B 누적 = 6 endpoint × 600~880줄 = ~4,000줄 + master.md 653줄 = ~4,650줄 계획서. 25 endpoint 중 6 완성 (24%).**

## In Progress / Pending

| # | 항목 | 상태 | Notes |
|---|------|------|-------|
| 1 | **다음 세션: Phase C 계획서 5건** | 🟢 즉시 가능 | `endpoint-06-ka10081.md` (일봉, KRX/NXT 동시) → `ka10082`(주봉) → `ka10083`(월봉) → `ka10094`(년봉) → `ka10086`(일별주가+투자자별). **백테스팅 본체** |
| 2 | **Phase A·B 코드화 착수 (대안)** | 🟡 결정 필요 | master.md § 11 권고는 Phase 단위 교차. Phase B 까지 6 endpoint = stock + sector + stock_fundamental 까지 영속화 가능 |
| 3 | **본 세션 + 이전 세션 결과 일괄 커밋** | ⏳ 사용자 대기 | 추천 메시지: `docs(kiwoom): backend_kiwoom 통합 계획서 + Phase A·B 6건 + backend_py SPEC.md` |
| 4 | **`키움 REST API 문서.xlsx` gitignore 결정** | ⏳ 미결 | 710KB. 옵션 (a) 커밋 (b) gitignore + 별도 보관 (c) symlink |
| 5 | **이전 세션 v1.2 Cp 2β 잔존** | ⏳ 사용자 대기 | `IndicatorParametersDrawer.tsx` 외 4건 — 분리 커밋 권장 |
| 6 | Phase D~G 계획서 (보강/시그널/순위/투자자) | 🟡 후순위 | Phase C 후 진입 |

## Key Decisions Made (본 세션)

### Phase B 설계 결정

1. **Phase B 수집 시장 5종**: KOSPI(`0`) / KOSDAQ(`10`) / KONEX(`50`) / ETN(`60`) / REIT(`6`). ETF(`8`)/금현물(`80`)/ELW(`3`) 보류
2. **`StockListMarketType` enum 16종 분리**: 키움 ka10099 의 mrkt_tp 가 다른 endpoint(ka10101/ka10027) 와 의미 완전히 다름 → 3개 enum 분리 확정 (`StockListMarketType` / `SectorMarketType` / `RankingExchangeType`)
3. **디액티베이션 같은 market_code 한정**: KOSPI sync 가 KOSDAQ 종목을 비활성화하지 않도록 시장 단위 격리. `deactivate_missing(market_code, present_codes)` Repository 메서드
4. **시장 단위 SAVEPOINT 격리**: `async with session.begin_nested()` 로 한 시장 호출 실패가 다른 시장 적재를 막지 않음
5. **mock 환경 안전판**: `Settings.kiwoom_default_env="mock"` 일 때 응답 `nxtEnable` 무시하고 강제 false (mockapi.kiwoom.com 은 KRX 전용)
6. **빈 응답 시 디액티베이션 skip**: `present_codes=set()` 이면 `deactivate_missing` 동작 안 함 (보수적)

### ka10100 (단건) 결정

7. **`stk_cd` Length=6 강제**: Excel R22 명시. `_NX`/`_AL` suffix 거부 (Pydantic regex `^\d{6}$`). ka10001(20자) 와 다름
8. **`LookupStockUseCase.ensure_exists`**: Phase C 시계열 수집이 미지 종목 만났을 때 lazy fetch 안전망. ON CONFLICT 가 race 흡수
9. **단건 endpoint 디액티베이션 안 함**: 활성화만 (응답에 등장한 종목 = 살아있음). 디액티베이션은 ka10099 의 시장 sync 책임
10. **NormalizedStock + Stock ORM 100% 공유**: ka10099 가 정의, ka10100 은 추가 메서드만

### ka10001 (펀더멘털) 결정

11. **stk_cd Length=20 + suffix 허용**: Excel R22 "거래소별 종목코드 (KRX:039490,NXT:039490_NX,SOR:039490_AL)" 명시. `ExchangeType` enum + `build_stk_cd` helper
12. **Phase B 호출 정책**: KRX only — 펀더멘털(C카테고리, PER/EPS/ROE) 은 외부 벤더 데이터로 거래소 무관. NXT 시세 분리는 Phase C 의 ka10086 위임
13. **`stock_fundamental` UNIQUE = (stock_id, asof_date, exchange)**: 일별 스냅샷. 같은 날 여러 호출은 마지막 호출로 갱신 (멱등성)
14. **`fundamental_hash` 컬럼 추가**: PER/EPS/ROE/PBR/EV/BPS 6 필드 MD5. 외부 벤더 갱신일 감지에 활용 (Phase F 시그널 단계). 본 Phase 에서는 계산만, 활용 미정
15. **부호 포함 string 처리**: `_to_int("+181400") → 181400`, `_to_int("-91200") → -91200`, `_to_decimal("+0.08") → Decimal("0.08")`
16. **Pydantic alias 매핑**: `250hgst` 같은 비-식별자 키 → `populate_by_name=True` + `Field(alias="250hgst")`
17. **`strip_kiwoom_suffix` helper**: 응답 `stk_cd` 가 `005930_NX` / `005930` 어느 쪽으로 와도 base code 추출 안전망
18. **partial 실패 정책**: < 1% 정상 / 1~10% warning / > 10% error+자격증명 점검 alert
19. **active 3000 종목 sync 시간 추정**: Semaphore=4 + 250ms interval = 이론 3분, 실측 5~12분 추정. cron 17:45 KST + 30분 grace

### Excel 명세서 발견 사항

20. **Excel 응답 예시 의심**: ka10099 R46 의 5 row 가 모두 `code="005930"` + `marketCode="10"` (코스닥) — 요청 mrkt_tp="0"(코스피) 와 불일치. Excel 샘플 단순화 가능성. 운영 첫 호출에서 `marketCode` 응답값과 요청 `mrkt_tp` 일치 여부 검증 필수
21. **단위 모호성** (DoD § 10.3): `mac="24352"`, `cap="1311"`, `flo_stk="25527"`, `dstr_stk` 단위 (백만원/억원/천주) 명시 안 됨. 운영 호출 후 `cur_prc × listed_shares = market_cap` 식으로 단위 도출 필요
22. **부호 의미**: `oyr_hgst="+181400"`, `oyr_lwst="-91200"` 부호가 단순 표기인지 전일 대비인지 불명
23. **외부 벤더 PER/ROE 갱신 주기**: Excel R41/R43 명시 — 주 1회 또는 실적발표 시즌. 일별 적재해도 같은 값 며칠 반복 → `fundamental_hash` 변경 감지가 갱신일 감별
24. **PER/EPS/ROE/PBR/EV/BPS 빈값 가능**: ETF/ETN/ELW 종목은 모든 펀더멘털 빈값 추정 — 컬럼 NULL 허용 필수

## Known Issues

### 운영 검증 미완 (DoD § 10.3 모음 — 실 키움 호출 후 확정)

| Endpoint | 미확정 항목 | 영향 |
|----------|------------|------|
| ka10099 | `marketCode` 응답값 ↔ 요청 `mrkt_tp` 일치 여부 | requested_market_type 컬럼 분리 결정 |
| ka10099 | `code` 6자리 가정의 정확성 (ETF/ELW 자릿수) | stock_code 길이 |
| ka10099 | `listCount` zero-padding 자릿수 (16자 추정) | 파서 보강 필요 여부 |
| ka10099 | `nxtEnable` "Y" 외 다른 값 등장 가능성 | upper() 매칭 충분 여부 |
| ka10099 | 같은 종목이 여러 시장에 등장 시 (ETF) | UNIQUE 제약 위반 → market_code 갱신 정책 |
| ka10099 | KOSPI ~900, KOSDAQ ~1700 추정의 정확성 | max_pages=100 충분 여부 |
| ka10100 | 존재하지 않는 종목 응답 패턴 (return_code != 0 vs 200 빈값 vs 4xx) | 처리 분기 |
| ka10100 | 응답 `code` 빈값 가능성 | min_length=1 검증 약화 필요 여부 |
| ka10100 | mock 도메인 nxtEnable 응답 패턴 | 안전판 동작 검증 |
| ka10001 | mac/cap/flo_stk/dstr_stk 단위 (백만원/억원/천주) | 컬럼 주석 + 백테스팅 계산 정확도 |
| ka10001 | oyr_hgst/oyr_lwst 부호 의미 (단순 표기 vs 전일 대비) | year_high/low 컬럼 의미 |
| ka10001 | 응답 stk_cd 의 suffix 보존/제거 (요청 _NX 시 응답이 어느 쪽) | strip_kiwoom_suffix 안전망 동작 |
| ka10001 | NXT 호출 응답이 KRX 와 펀더멘털(C) 동일한지, 일중시세(E) 분리되는지 | KRX only 정책 검증 |
| ka10001 | active 3000 종목 sync 실측 소요 시간 (5~12분 추정) | cron grace 조정 |
| ka10001 | partial 실패 비율 (1주 모니터) | alert threshold 조정 |
| ka10001 | 키움 과거 일자 펀더멘털 응답 가능성 | 백필 가능 여부 |

### 알려진 위험 (계획 단계, 본 세션 추가)

- **ka10099 페이지네이션 동작**: KOSPI/KOSDAQ 둘 다 페이지네이션 발생 추정. `call_paginated` 의 첫 본격 검증 케이스 — Phase A 의 ka10101 (단일 페이지 가능성 높음) 와 별개
- **race condition** (ka10100): 같은 stock_code 동시 ensure_exists 시 ka10100 중복 호출. 빈도 낮으면 무시, Phase C 트래픽 측정 후 결정
- **ka10001 lazy fetch RPS 폭주**: Phase F 순위 응답에 미지 종목 100건 등장 시 ka10100 100회 연속 호출 → master.md § 6.3 RPS 가드 필수
- **fundamental_hash string 비교**: PER `"15.20"` vs `"15.2"` 면 hash 다름 — 정규화 필요 가능성
- **stock 시간대**: ka10001 응답에 timestamp 없음. 호출 시점 KST 가 asof_date — 자정 직전 호출 주의
- **partial 실패 누적**: 3000 종목 중 일부 실패가 다음 sync 에서 retry 큐로 운영되어야 — 본 endpoint 범위 외 (Phase F 모니터링 단계)

### 이전 세션 잔존 (본 세션과 무관)

- v1.2 Cp 2β 진행 중 — `IndicatorParametersDrawer.tsx` (신규) + 페이지/패널/차트 변경
- v1.1 known issue: Aurora CLS 0.393, 2026-04-20 OHLCV 0값 추적
- 백엔드 이월: 다른 서비스 DIP 확장, `Mapped[str]` → `Literal`, R-04~06

## Context for Next Session

### 사용자의 원 목적 (본 세션 흐름)

세션 진입 시 사용자가 던진 첫 요청은 "다음 작업 알려줘". 핸드오프 확인 후 4개 옵션 제시 (`AskUserQuestion`):
1. Phase B 계획서 3건 작성 ← **선택**
2. 본 세션 결과 커밋
3. Phase A 코드화 착수
4. Excel 파일 처리 결정

수행 흐름:
1. **Phase A 패턴 정독** — `endpoint-14-ka10101.md` 668줄 풀 read 로 11 섹션 템플릿 / Repository 패턴 / SAVEPOINT 격리 / DoD 구조 학습
2. **Excel 시트 정독** — openpyxl 로 `종목정보 리스트(ka10099)` 46행, `종목정보 조회(ka10100)` 45행, `주식기본정보요청(ka10001)` 76행 풀 dump. mrkt_tp 16종, 응답 14/14/45 필드, NXT/벤더 메모 추출
3. **endpoint-03-ka10099.md** — ~720줄. mrkt_tp 16종 enum, 시장 격리 SAVEPOINT, 디액티베이션 안전판, mock 강제 false, zero-padded 정규화
4. **endpoint-04-ka10100.md** — ~510줄. stk_cd 6자리 강제, ensure_exists lazy fetch, ka10099 자산 100% 공유
5. **endpoint-05-ka10001.md** — ~880줄. 45 필드 4 카테고리 분해, KRX only 정책, fundamental_hash, 부호 처리, alias 매핑, 3000 종목 sync 시간 추정
6. **CHANGELOG prepend + HANDOFF overwrite** — 세션 마감

### 선택한 접근과 이유

- **endpoint-14 패턴 100% 복제**: 11 섹션 통일 — DoD/위험/결정필요 표 형식 동일. Phase B 3건이 600~880줄로 비슷한 깊이
- **자산 공유 명시**: §11.3 비교 표로 ka10099 vs ka10100 vs ka10001 의 책임 분담과 공유 자산(NormalizedStock, Stock ORM, KiwoomStkInfoClient) 명확화 — Repository/UseCase 구현 시 중복 작업 방지
- **운영 검증 미확정 항목 명시 분리**: §11.1 결정 필요 표 + §10.3 DoD 운영 검증 항목 분리. 첫 호출 후 master.md § 12 결정 기록으로 승격 절차 통일
- **단위·부호 모호성 명시**: ka10001 의 mac/cap/oyr_hgst 같은 모호 필드를 §11.2 알려진 위험 + §10.3 운영 검증으로 이중 명시 — 코드화 단계에서 forget 방지
- **Phase 단위 권고 유지**: master.md § 11 의 "각 Phase 의 계획서를 모두 받은 후 그 Phase 만 코드화" 방식. 다음 세션은 Phase C 계획서 5건 (백테스팅 본체) 우선
- **`fundamental_hash` 도입**: 외부 벤더 PER/ROE 주 1회 갱신 특성을 활용. Phase F 시그널 단계의 "실적 발표일 추정" 시그널 source

### 사용자 선호·제약 (재확인)

- **한국어 커밋 메시지 + Co-Authored-By** (전역 CLAUDE.md)
- **`git push` 명시 요청 시에만** — 본 세션도 커밋 없음 (사용자가 검토 후 커밋 결정)
- **선택지 제시 후 사용자 결정** — 본 세션 `AskUserQuestion` 1건 (다음 작업 4 옵션)
- **체크리스트 + 한 줄 현황** (memory: feedback_progress_visibility) — TaskCreate 5건 사용
- **block-no-verify heredoc 오탐지 대응** (memory: project_block_no_verify_heredoc_pitfall) — 커밋 시 `git commit -F <file>` 우회

### 다음 세션에서 먼저 확인할 것

1. **Phase A·B 6 endpoint + master.md + SPEC.md 일괄 커밋 여부** — 추천: `docs(kiwoom): backend_kiwoom 통합 계획서 + Phase A·B 6건 + backend_py SPEC.md`
2. **Phase C 진입 합의** — `endpoint-06-ka10081.md` (일봉, **백테스팅 본체** ★) → `ka10082` → `ka10083` → `ka10094` → `ka10086`
3. **Phase A 코드화 시점 합의** — 25개 모든 계획서 후 일괄 vs Phase 단위 교차. 후자 권장 (master.md § 11). Phase B 까지 코드 = stock + sector + stock_fundamental 영속화 완료
4. **`키움 REST API 문서.xlsx` gitignore 결정** — 710KB 바이너리. 권장: (b) gitignore + 별도 보관
5. **이전 세션 v1.2 Cp 2β 잔존** — 분리 커밋 또는 폐기 결정. 본 세션 키움 작업과 무관

### Phase C 의 핵심 (다음 세션 준비)

- **ka10081**: 주식일봉차트 — KRX/NXT 둘 다 호출 (`stk_cd=005930` + `stk_cd=005930_NX`). **백테스팅 코어**. `stock_price_krx` + `stock_price_nxt` 분리 적재
- **ka10082/83/94**: 주봉/월봉/년봉 — ka10081 패턴 복제. UseCase `IngestPeriodicOhlcvUseCase` 가 4 endpoint 통합
- **ka10086**: 일별주가 + **투자자별 + 신용비** — KRX/NXT 분리. `stock_daily_flow` 테이블 (ind_netprps/orgn_netprps/frgn_netprps + crd_rt 등)
- **DB**: Migration 003 `ohlcv_krx.py` (stock_price_krx + 주/월/년) + Migration 004 `ohlcv_nxt.py` (NXT 분리 + stock.nxt_enable)
- **Phase B 의존**: stock 테이블 + nxt_enable 필터로 NXT 호출 큐 생성 → Phase B 가 끝나면 Phase C 즉시 진입

### 가치 있는 발견 (본 세션)

1. **Excel 시트 깊이 정독이 단위 모호성 발견에 결정적**: ka10001 의 mac="24352", cap="1311" 만 보면 무심코 KRW 가정 가능. Excel 명시 부재 → DoD 운영 검증 항목으로 승격
2. **`mrkt_tp` 의미 endpoint 별 분리의 정합성**: ka10099(시장 16종, 0=KOSPI/10=KOSDAQ) vs ka10101(업종 5종, 0=KOSPI/1=KOSDAQ) — 같은 "0" 이 양쪽 다 KOSPI 지만, "1" 은 ka10101 에서 KOSDAQ 인 반면 ka10099 에서는 의미 없는 값. 3 enum 분리 결정의 근거
3. **`_NX` suffix Length 차이의 의미**: ka10100(L=6, suffix 거부) 와 ka10001(L=20, suffix 허용) 의 차이가 design intent 명확화 — ka10100 은 종목 마스터(거래소 무관 메타), ka10001 은 거래소별 시세 포함
4. **Excel 응답 예시의 의심 포인트**: ka10099 R46 의 5 row 가 모두 같은 종목 + 같은 marketCode + mrkt_tp 와 불일치 → 단순 샘플 문제로 추정하나 운영 검증 항목으로 승격
5. **외부 벤더 PER/ROE 의 변경 감지**: Excel R41/R43 의 "주 1회" 메모를 fundamental_hash 컬럼으로 활용. 정적 메모를 운영 데이터 source 로 전환
6. **3000 종목 sync 시간 산정**: Semaphore=4 + 250ms interval = 이론 3분 — 단순 곱셈 계산이 RPS 가드 설계의 sanity check. 실측 5~12분 예상은 키움 응답 시간 + 네트워크 변동성
7. **lazy fetch 의 시스템 안전망 역할**: Phase C 의 ka10081 호출자가 미지 종목 만났을 때 ka10100 ensure_exists 가 INSERT — Phase B/C 의 분리된 책임이 단일 호출 흐름으로 이어짐
8. **partial 실패의 정량적 임계**: 1%/10% 임계값을 alert 분기로 활용 — 자격증명/RPS/장애 의심 분기. 백테스팅 데이터 신뢰성 운영의 첫 가드
9. **시장 단위 SAVEPOINT 격리**: `begin_nested` 가 outer 트랜잭션과 별개로 시장별 commit boundary 만들어 한 시장 실패가 다른 시장 적재를 막지 않음 — Phase A 의 ka10101 패턴이 Phase B 의 ka10099 에서 본격 활용
10. **`strip_kiwoom_suffix` helper 의 공유성**: ka10001/ka10081/ka10082/... 모든 시계열 endpoint 가 응답 `stk_cd` 의 suffix 처리 필요 — 공통 helper 한 줄이 6+ endpoint 의 안전망

## Files Modified This Session

```
신규 파일 (untracked):
src/backend_kiwoom/docs/plans/
├ endpoint-03-ka10099.md         ~720 줄 신규
├ endpoint-04-ka10100.md         ~510 줄 신규
└ endpoint-05-ka10001.md         ~880 줄 신규

기존 파일 갱신:
CHANGELOG.md                     +85 줄 prepend (본 세션 항목)
HANDOFF.md                       overwrite (본 문서)

이전 세션 untracked 누적 (커밋 대기):
src/backend_kiwoom/docs/plans/master.md
src/backend_kiwoom/docs/plans/endpoint-01-au10001.md
src/backend_kiwoom/docs/plans/endpoint-02-au10002.md
src/backend_kiwoom/docs/plans/endpoint-14-ka10101.md
src/backend_py/SPEC.md
src/backend_kiwoom/docs/키움 REST API 문서.xlsx (710KB, gitignore 결정 미정)
docs/research/kiwoom-rest-feasibility.md (M)

이전 세션 v1.2 Cp 2β 잔존 (분리 커밋 권장):
src/frontend/src/components/charts/IndicatorParametersDrawer.tsx
src/frontend/src/components/charts/IndicatorParametersDrawer.test.tsx
src/frontend/src/app/stocks/[code]/page.tsx (M)
src/frontend/src/components/charts/IndicatorTogglePanel.tsx (M)
src/frontend/src/components/charts/PriceAreaChart.tsx (M)
```

**0 commits, 3 docs new (Phase B) + 2 updated. Phase A·B 누적 = 6 endpoint 계획서 + master.md + SPEC.md.**

### Context to Load (다음 세션)

Phase C 계획서 작성 시 먼저 로드할 파일:

```
src/backend_kiwoom/docs/plans/master.md                    # 25 endpoint 카탈로그 + Phase C 정의 + per-endpoint 템플릿
src/backend_kiwoom/docs/plans/endpoint-03-ka10099.md       # Phase B 패턴 — NormalizedStock / Stock ORM / NXT enable 게이팅
src/backend_kiwoom/docs/plans/endpoint-05-ka10001.md       # Phase B 패턴 — _NX/_AL suffix / ExchangeType / build_stk_cd / strip_kiwoom_suffix
src/backend_kiwoom/docs/plans/endpoint-14-ka10101.md       # Phase A 패턴 — call_paginated / SAVEPOINT 격리
src/backend_kiwoom/docs/키움 REST API 문서.xlsx             # ka10081/ka10082/ka10083/ka10094/ka10086 시트 정독 (R22 stk_cd Length, R28~ 응답 필드, R44~ 응답 예시)
```

다음 세션 첫 명령 추천: `Phase C (ka10081/ka10082/ka10083/ka10094/ka10086) 계획서 5건 작성해줘` 또는 `Phase A·B 6 endpoint + master.md + SPEC.md 커밋 후 Phase A 코드화 착수`
