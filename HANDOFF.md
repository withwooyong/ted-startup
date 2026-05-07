# Session Handoff

> Last updated: 2026-05-07 (KST) — **backend_kiwoom 25 endpoint 계획서 100% 완성**
> Branch: `master` (working tree dirty — Phase D 3 + E·F·G 11 = 14 신규 계획서 + CHANGELOG/HANDOFF 미커밋)
> Latest commit: `de6d109` — docs(kiwoom): Phase C 5건 (Phase A·B·C 까지 푸시 완료)
> 세션 시작점: 위와 동일 (`de6d109`) — 본 세션도 **커밋 0건**

## Current Status

`backend_kiwoom` 의 **Phase A 3 + B 3 + C 5 + D 3 + E 3 + F 5 + G 3 = 25 endpoint 계획서 100% 완성**. 누적 ~20,140줄 (master.md 포함). 코드는 0줄. **다음 세션은 Phase A 부터 코드화 착수**.

**25 endpoint 계획서가 완성되면 가능한 것**:
- 모든 endpoint 의 KRX/NXT 분리 정책, DB 스키마, Migration 분할, cron chain, 운영 검증 우선순위가 단일 진실 소스 (계획서 25개 + master.md) 로 정리됨
- 코드화 진입 시 Phase A 부터 순차 작성 — 각 Phase 완료 후 백테스팅 엔진의 점진적 검증
- 운영 검증 1순위 항목 25개 모음 (CHANGELOG § 운영 검증 우선순위) 으로 첫 호출 시 raw 측정 → master.md § 12 결정 기록 승격

## Completed This Session (Phase E + F + G — 11 endpoint, Documentation only)

| # | 산출물 | 위치 | 줄수 | 성격 |
|---|--------|------|------|------|
| 1 | endpoint-15-ka10014 | Phase E reference (공매도) | **1,069** | tm_tp 의미 + 11 필드 + KRX/NXT |
| 2 | endpoint-16-ka10068 | 대차 시장 단위 | 700 | partial unique index 정의 |
| 3 | endpoint-17-ka20068 | 대차 종목별 | 672 | ka10068 패턴 복제 |
| 4 | endpoint-18-ka10027 | Phase F reference (등락률) | **979** | ranking_snapshot + JSONB payload |
| 5 | endpoint-19-ka10030 | 당일 거래량 (23 필드 wide) | 574 | camelCase 응답 + 장중/장후/장전 |
| 6 | endpoint-20-ka10031 | 전일 거래량 (가장 단순) | 398 | rank_strt/rank_end 페이지네이션 |
| 7 | endpoint-21-ka10032 | 거래대금 (now_rank/pred_rank) | 388 | Body 가장 단순 + 호가 |
| 8 | endpoint-22-ka10023 | 거래량 급증 | 442 | 합성 sort_tp 키 (tm_tp/tm) |
| 9 | endpoint-23-ka10058 | Phase G reference (long ranking) | **920** | 12 invsr_tp + investor_flow_daily |
| 10 | endpoint-24-ka10059 | 종목별 wide breakdown | 657 | 20 필드 + 12 투자자 카테고리 |
| 11 | endpoint-25-ka10131 | 연속매매 (마지막) | 697 | 연속 일수 시그널 |
| 12 | CHANGELOG.md prepend | 본 세션 항목 | +200 | |
| 13 | HANDOFF.md overwrite | 본 문서 | — | |

**Phase E·F·G 11건 = 7,496줄. 코드 변경 0.**

**Phase A + B + C + D + E + F + G 누적 = 25 endpoint 계획서 ~19,485줄 + master.md 653줄 = ~20,140줄.** 25 endpoint **100% 완성** (전 endpoint 계획서 완료).

## In Progress / Pending

| # | 항목 | 상태 | Notes |
|---|------|------|-------|
| 1 | **다음 세션: Phase A 코드화 착수** | 🟢 즉시 가능 | master.md § 11 권고. pyproject.toml + Dockerfile + Alembic 001 + KiwoomClient 공통 트랜스포트 + au10001/au10002/ka10101 코드화 + testcontainers 통합 테스트 |
| 2 | **본 세션 결과 커밋** (Phase D + E·F·G) | ⏳ 사용자 대기 | Phase D 3건 + Phase E·F·G 11건 = 14건 일괄 또는 분리 커밋. 추천: 분리 (이미 D 는 직전 세션 산출물) |
| 3 | **운영 검증 1순위 정리** | 🟡 코드화 진입 시점 | 25 endpoint × 운영 검증 항목 ~70개 → master.md § 12 결정 기록 승격 |
| 4 | Phase H 통합 | 🟡 후순위 | 백테스팅 view, 데이터 품질 리포트, retention drop, 분봉↔일봉 합성 검증 |

## Key Decisions Made (본 세션)

### Phase E (시그널 보강) 핵심 설계

1. **`/api/dostk/shsa` (공매도) + `/api/dostk/slb` (대차) 카테고리 분리**: 두 카테고리는 의미 (raw 매도 압력 vs 거시 추세) 와 호출 단위 (종목 vs 시장+종목) 가 다름 → 별도 클라이언트 / 별도 마이그레이션 같은 파일
2. **`lending_balance_kw` partial unique index**: ka10068 (시장) + ka20068 (종목별) 같은 테이블, scope 컬럼 + 두 partial unique index 로 (scope=MARKET, trading_date) / (scope=STOCK, stock_id, trading_date) 분리
3. **공매도 NXT 미지원 가능성 정책**: 호출 시도 + 빈 응답 정상 처리 — warning 누적 안 함. NXT 거래소 운영 정책상 공매도 차단 가능성 대응
4. **`tm_tp` 의미 미확정 (ka10014)**: Excel 명세 모호 — 운영 1순위 검증. PERIOD (1) default 가정 + START_ONLY (0) 검증

### Phase F (순위) 핵심 설계

5. **`ranking_snapshot` 통합 테이블 + JSONB payload**: 5 ranking endpoint (ka10027/30/31/32/23) 의 가변 schema 흡수. UNIQUE 키 6개 (snapshot_date/time, ranking_type, sort_tp, market_type, exchange_type, rank). GIN 인덱스로 ad-hoc payload 쿼리 가속
6. **`KiwoomRkInfoClient` 단일 클래스**: 5 endpoint 가 같은 URL `/api/dostk/rkinfo` 공유 → 5 메서드 (`fetch_flu_rt_upper` / `fetch_today_volume_upper` / `fetch_pred_volume_upper` / `fetch_trde_prica_upper` / `fetch_volume_sdnin`)
7. **`mrkt_tp` 의미 4번째 정의** (000/001/101): ka10099 / ka10101 / ka10027 카테고리 / ka10058 카테고리 4 가지 의미. 5 ranking endpoint (ka10027/30/31/32/23) 가 같은 의미. enum 분리 (`RankingMarketType`)
8. **camelCase 응답 흡수 (ka10030)**: Pydantic `Field(alias="returnCode")` + `populate_by_name=True` 안전망. Excel 표기 차이가 실제 응답 차이 또는 Excel 표기 오류 — 운영 검증
9. **`primary_metric` 분기 (sort_tp 별 다른 metric)**: ka10027 (flu_rt 단일) → ka10030 (volume/turnover/amount 분기) → ka10023 (sdnin_qty/sdnin_rt 분기) — UseCase 가 호출 시 sort_tp 받아 metric 추출
10. **`rank_strt`/`rank_end` 페이지네이션 (ka10031 only)**: cont-yn 미사용 — 0~100 분할 호출 패턴. 다른 4 endpoint 와 다름
11. **`now_rank`/`pred_rank` 직접 응답 (ka10032)**: 순위 변동 시그널의 raw input. 다른 ranking 은 derived feature 로 계산 필요
12. **합성 sort_tp 키 (ka10023)**: `composite="{sort_tp}_{tm_tp}_{tm}"` — 같은 시점에 다른 윈도 호출 분리. ranking_snapshot UNIQUE 키 확장 없이 구현
13. **cron 19시대 chain (Phase F)**: 19:30 ka10027 → 19:35 ka10030 → 19:40 ka10031 → 19:50 ka10032 → 19:55 ka10023. 각 5~10분 간격

### Phase G (투자자별) 핵심 설계

14. **3 테이블 분리 (long / wide / continuous)**:
    - ka10058 = `investor_flow_daily` (long format ranking)
    - ka10059 = `stock_investor_breakdown` (wide format 12 카테고리)
    - ka10131 = `frgn_orgn_consecutive` (연속 일수 시그널)
    - 같은 마이그레이션 (008) + 같은 service 모듈, 다른 테이블
15. **12 `invsr_tp` 카테고리 (ka10058)**: 개인/외국인/기관계 + 9 sub (금융투자/보험/투신/기타금융/은행/연기금/사모/국가/기타법인). 운영 default = 3 (개인/외인/기관계)
16. **wide format vs long format 분리 의미**: ka10058 = 종목 ranking 추출 (시그널 후보), ka10059 = 종목 단위 12 투자자 정밀 분석. 두 endpoint 보완
17. **`flu_rt` 표기 차이 (ka10058 vs ka10059)**: ka10058 의 `pre_rt = "+7.43"` vs ka10059 의 `flu_rt = "+698"` (우측 2자리 소수점 = 6.98%). 정규화 시 / 100 분기 필요
18. **`amt_qty_tp` 의미 ka10059 vs ka10131 반대**: ka10059 (1=금액/2=수량) vs ka10131 (0=금액/1=수량). 같은 키움 API 일관성 깨짐 — 운영 1순위 검증
19. **`netslmt_qty` (ka10058) 부호 모호**: 응답 필드명 "순매도수량" 인데 trde_tp=2 (순매수) 호출 응답에도 등장. 부호/의미가 trde_tp 따라 달라짐
20. **이중 부호 (`--335`/`--714`) 일반화**: ka10086 의 `_strip_double_sign_int` helper 가 Phase E + G 6 endpoint 에서 재사용 — 단일 helper 통일
21. **연속 일수 시그널 (ka10131)**: total_cont_days desc + DESC NULLS LAST partial index — 강한 추세 종목 추출 1순위 쿼리
22. **cron chain Phase F → G**: 19:55 ka10023 → 20:00 ka10058 → 20:30 ka10059 → 21:00 ka10131. 25 endpoint 마지막 cron

## Known Issues

### 운영 검증 1순위 (DoD § 10.3 모음 — Phase E·F·G 19개 항목)

| Endpoint | 미확정 항목 | 영향 |
|----------|------------|------|
| ka10014 | **`tm_tp` (0/1) 의미** | 응답 row 분포 |
| ka10014 | NXT 공매도 응답 가능 여부 | partial 실패율 |
| ka10014 | `ovr_shrts_qty` 누적 의미 | 백테스팅 정합성 |
| ka10068 | 시장 분리 응답 가능 여부 | 호출 매트릭스 |
| ka10068 | `rmnd` 누적 vs 일별 | 시그널 의미 |
| ka20068 | NXT 호출 가능 여부 (Length=6) | NXT 시그널 |
| ka10027 | `stk_cls`/`cntr_str`/`cnt` 의미 | payload 활용 |
| **ka10030** | **`returnCode/returnMsg` camelCase 응답 확정** | **5 endpoint 일관성** |
| ka10030 | 장중/장후/장전 분리값 발효 시점 | mrkt_open_tp 활용 |
| ka10031 | qry_tp=1 vs 2 응답 정렬 | trde_qty 의미 |
| ka10032 | `now_rank` vs list 순서 | rank 컬럼 |
| ka10023 | `tm_tp=1` + `tm="5"` 의미 | 분 단위 시그널 |
| **ka10058** | **`netslmt_qty/_amt` 부호 의미** | 부호 처리 |
| ka10058 | 이중 부호 빈도 | helper 적용 |
| **ka10059** | **`flu_rt` 표기 (`+698` = 6.98%)** | 정규화 / 100 |
| ka10059 | `orgn = 12 sub-카테고리 합` 정합성 | wide 검증 |
| ka10059 | `natfor` (내외국인) 의미 | 컬럼 활용 |
| **ka10131** | **`amt_qty_tp` (0/1) — ka10059 와 반대** | **단위 mismatch** |
| ka10131 | `cont_netprps_dys` 산식 (orgn + frgnr = total?) | 시그널 정합성 |

### 알려진 위험 (계획 단계, 본 세션 추가)

- **`mrkt_tp` 의미 4번째/5번째 정의 + `amt_qty_tp` 의미 반대 (ka10059 vs ka10131)**: 같은 키움 API 의 일관성 깨짐 — 5 카테고리 enum 분리 필수. 잘못 매핑하면 단위 mismatch 또는 시장 mismatch
- **camelCase 응답 (ka10030)**: Excel 표기와 실제 응답 차이가 ka10030 만의 표기 오류일 가능성. Pydantic alias + populate_by_name=True 안전망으로 두 표기 모두 흡수 — 코드화 후 첫 호출에서 raw 키 dump 1순위
- **`netslmt_qty` 부호/의미 모호 (ka10058)**: trde_tp=1 (순매도) vs =2 (순매수) 호출 응답에서 같은 필드명 — 부호 / 의미가 호출 trde_tp 따라 달라짐. 잘못 처리 시 시그널 부호 반전
- **이중 부호 (`--335`/`--714`)**: ka10086 (Phase C) 의 동일 위험 — Phase E·G 6 endpoint 에 동일 helper 재사용. 운영 첫 호출에서 빈도 측정
- **`flu_rt` 표기 ka10058 vs ka10059 차이**: `+7.43` vs `+698` (= 6.98%). 정규화 시 / 100 분기 필요. 같은 카테고리 (`/api/dostk/stkinfo`) 인데 표기 다른 이유 운영 검증
- **NXT 응답 stk_cd Length 차이**: ka10131 (Length=6) / ka20068 (Length=6) — NXT (`_NX`) 미지원 가능. ka10058 (Length=20) / ka10059 (Length=20) — NXT 지원. 같은 카테고리에서도 차이
- **응답 list 정렬 가정 (ranking_snapshot rank)**: list 순서가 sort_tp 순위 (1, 2, 3, ...) 가정 — 정렬 깨지면 rank 컬럼 의미 깨짐
- **JSONB payload 의 disk 부담 (Phase F)**: 23 필드 wide (ka10030) × 5 endpoint × 1년 → ~3MB 추정. 5년+ 시점 운영 monitor
- **연속순매수 일수의 `as_of_date` lag (ka10131)**: 외인 매매 보고가 T+2 lag 가능. 백테스팅 시점 보정 필요
- **3000 종목 × 60분 sync 의 자격증명 만료 위험 (ka10059)**: au10001 24시간 만료. ka10081 동일 위험. 자동 재발급 동작 검증 1순위
- **`stk_inds_tp=1` (업종) 응답 schema (ka10131)**: 종목과 같은지 다른지. 같은 schema 면 stock_code_raw 에 업종코드 들어감 → stock_id NULL 처리

## Context for Next Session

### 사용자의 원 목적 (본 세션 흐름)

세션 시작 명령: `Phase E~G 계획서 작성하자`. 직전 세션 핸드오프의 3 옵션 중 (A) 11건 일괄 선택.

수행 흐름:
1. **Excel 11 시트 dump** — Phase E (3) + Phase F (5) + Phase G (3) 정독. 패턴 분석 (URL 카테고리 / 응답 schema / sort_tp 의미 / `mrkt_tp`/`amt_qty_tp` 의미 변형)
2. **Phase E 3건** (ka10014 reference 1069줄 → ka10068 700줄 → ka20068 672줄) — 공매도/대차 카테고리
3. **Phase F 5건** (ka10027 reference 979줄 → ka10030 574줄 → ka10031 398줄 → ka10032 388줄 → ka10023 442줄) — ranking_snapshot 통합 테이블 패턴
4. **Phase G 3건** (ka10058 reference 920줄 → ka10059 657줄 → ka10131 697줄) — long/wide/continuous 3 테이블 분리
5. **CHANGELOG prepend + HANDOFF overwrite** — 25 endpoint 100% 완성 마감

### 선택한 접근과 이유

- **Phase 별 reference + 차이점만 패턴**: Phase D 의 ka10081 reference + ka10082/83/94/86 분기 패턴을 Phase E·F·G 에서도 재사용. 본 세션 11건 중 reference 3건 (ka10014/ka10027/ka10058) 만 길게 (920~1069줄), 나머지 8건은 차이점만 (388~700줄)
- **Phase F 통합 테이블**: 5 ranking endpoint 가 같은 URL `/api/dostk/rkinfo` 공유 → JSONB payload 로 단일 테이블. 새 endpoint 추가 시 enum 만 확장 — Phase F 5건 작성 후 Phase H 시점에 추가 ranking 도입 가능
- **Phase G 3 테이블 분리**: ka10058 (long ranking) / ka10059 (wide breakdown) / ka10131 (continuous) 의 의미 차이가 충분 — 한 테이블로 통합하면 NULL 컬럼 폭증 + 조회 분리 어려움
- **운영 검증 항목 4중 명시**: 19 endpoint 별 1순위 항목을 (DoD § 10.3 + § 11.1 결정 + § 11.2 위험 + 비교표 § 11.3) 4중 명시. 코드화 후 첫 호출 시 forget 방지
- **이중 부호 처리 일반화**: ka10086 의 helper 가 Phase E·G 6 endpoint 에 재사용 — 단일 helper 통일로 부호 처리 정책 한 곳에서 관리

### 사용자 선호·제약 (재확인)

- **한국어 커밋 메시지 + Co-Authored-By** (전역 CLAUDE.md)
- **`git push` 명시 요청 시에만** — 본 세션도 커밋 없음 (사용자가 검토 후 커밋 결정)
- **선택지 제시 후 사용자 결정** — 본 세션은 명시 명령으로 진입, 추가 분기 없음
- **체크리스트 + 한 줄 현황** (memory: feedback_progress_visibility) — TaskCreate 18건 사용 (E·F·G 각 endpoint 별 task)
- **block-no-verify heredoc 오탐지 대응** (memory: project_block_no_verify_heredoc_pitfall) — 본 세션은 커밋 없음

### 다음 세션에서 먼저 확인할 것

1. **Phase D + E·F·G 일괄 또는 분리 커밋 합의**:
   - 옵션 A (분리): `docs(kiwoom): Phase D 3건 — 보강 시계열 (틱·분봉·업종)` + `docs(kiwoom): Phase E·F·G 11건 — 25 endpoint 계획서 100% 완성`
   - 옵션 B (일괄): `docs(kiwoom): Phase D·E·F·G 14건 — 25 endpoint 계획서 100% 완성`
2. **Phase A 코드화 착수 합의** — master.md § 11 권고 진입:
   - pyproject.toml (uv) + Dockerfile + alembic.ini
   - Settings (Pydantic v2 BaseSettings) + Fernet credential cipher
   - structlog 마스킹 (token/secretkey/authorization 자동)
   - KiwoomClient 공통 트랜스포트 (httpx + tenacity + Semaphore)
   - Migration 001 (kiwoom_credential / kiwoom_token / raw_response / stock 마스터 일부)
   - au10001 (토큰 발급) + au10002 (폐기) + ka10101 (sector 마스터)
   - testcontainers PG16 통합 테스트
3. **운영 검증 우선순위 정의** — Phase A 코드화 후 첫 호출 시점. master.md § 12 결정 기록 승격 항목 70+ 개 (25 endpoint × 평균 ~3 항목)
4. **Migration numbering 정정** — Phase D 의 ka20006 (008_sector_price_daily) 와 Phase G 의 008_investor_flow 충돌 → 010_sector_price_daily 재배치 필요 (master.md § 4.3 갱신)

### 25 endpoint Phase 별 의존성 그래프 (코드화 진입 시 확인)

```
Phase A (au10001/au10002/ka10101)
   └ KiwoomClient 공통 트랜스포트 + Migration 001 + sector 마스터
   ↓ 후속 Phase 모두 의존
Phase B (ka10099/ka10100/ka10001) — stock 마스터 + nxt_enable
   ↓ Phase C/D/E/G (종목 단위 endpoint) 모두 의존
Phase C (ka10081/82/83/94/ka10086) — 백테스팅 OHLCV
   └ Migration 003/004/005 (KRX OHLCV / NXT OHLCV / stock_daily_flow)
   ↓ Phase D/E (시그널 보강의 비교 source)
Phase D (ka10079/10080/ka20006) — 보강 시계열
   ├ ka20006 → ka10101 sector 마스터 의존
   └ Migration 005 (intraday — tick/minute) + 010 (sector_price_daily — 008 재배치 필요)
Phase E (ka10014/10068/20068) — 시그널 보강
   └ Migration 006 (short_lending)
Phase F (ka10027/30/31/32/23) — 순위
   ├ stock 마스터 lookup miss 허용 (NULL FK)
   └ Migration 007 (rankings)
Phase G (ka10058/10059/10131) — 투자자별
   └ Migration 008 (investor_flow — 3 테이블)
Phase H — 통합 (백테스팅 view, 데이터 품질, retention drop)
```

### 가치 있는 발견 (본 세션 11 endpoint)

1. **`ranking_snapshot` 통합 테이블의 ROI (Phase F)**: 5 endpoint × 평균 800줄 = 4,000줄 코드를 단일 테이블 + JSONB payload + 5 메서드 단일 클래스로 통합. 새 ranking 추가 시 ~200줄 (enum + UseCase) 만 작성
2. **`mrkt_tp` 의미 4번째/5번째 정의**: ka10099 (0/10/30/...) → ka10101 (0/1/2/4/7) → ka10027 (000/001/101) → ka10058 (001/101) → ka10131 (001/101). 같은 파라미터 이름의 5 가지 의미 — Python enum 분리로 컴파일 시점 차단
3. **`amt_qty_tp` 의미 ka10059 vs ka10131 반대**: 같은 키움 API 의 일관성 깨짐. 운영 검증 1순위 — 잘못 매핑 시 단위 mismatch
4. **camelCase 응답 (ka10030 만의 위험)**: Pydantic alias 안전망으로 두 표기 흡수. 5 ranking 중 ka10030 만 다른 표기 = Excel 표기 오류 가능성 또는 키움 응답 비일관성
5. **partial unique index 패턴 (Phase E)**: PostgreSQL partial index 로 (scope=MARKET) / (scope=STOCK) 분리 UNIQUE 키 — ka10068/ka20068 같은 테이블 통합 + 안전성 보장
6. **연속 일수 시그널 (ka10131)**: 단일 시점 ranking (ka10058) + wide breakdown (ka10059) 의 시간 차원 보완. `total_cont_days` desc 정렬이 백테스팅 강한 추세 종목 추출 1순위
7. **이중 부호 helper 일반화**: ka10086 (Phase C) 의 `_strip_double_sign_int` 가 Phase E·G 6 endpoint 에 재사용 — 단일 helper 정책 + 미래 부호 처리 변경 시 한 곳에서만 수정
8. **3 테이블 분리 (Phase G)**: long ranking / wide breakdown / continuous 의 의미 차이가 통합 테이블 NULL 컬럼 폭증보다 큼. 책임 분리가 disk 부담보다 우선
9. **cron chain 19~21시 분리**: 14 cron 등록 시점 (Phase B~G + Phase A의 weekly sector_sync) 의 chain. 각 5~30분 간격 + Semaphore 충돌 회피 + 운영 1주차에 시간 조정 가능
10. **Excel 표기와 응답 일관성 위험 일반화**: `tm_tp` 모호 (ka10014) / `acc_trde_qty` 누락 (ka10080) / `mrkt_tp` 다른 의미 / camelCase (ka10030) / 이중 부호 (ka10086 / ka10058) / `amt_qty_tp` 반대 (ka10059 vs ka10131) / `flu_rt` 다른 표기 (ka10058 vs ka10059). Excel 자체가 trusted source 가 아님 — 운영 첫 호출에서 raw 측정이 항상 1순위. 본 세션의 25 운영 검증 항목 모음이 코드화 후 첫 운영 검증의 단일 reference

## Files Modified This Session

```
신규 파일 (untracked):
src/backend_kiwoom/docs/plans/
├ endpoint-15-ka10014.md         1,069 줄 신규 ★ Phase E reference (공매도)
├ endpoint-16-ka10068.md           700 줄 신규 (대차 시장)
├ endpoint-17-ka20068.md           672 줄 신규 (대차 종목별)
├ endpoint-18-ka10027.md           979 줄 신규 ★ Phase F reference (등락률 + ranking_snapshot)
├ endpoint-19-ka10030.md           574 줄 신규 (당일 거래량 23 필드)
├ endpoint-20-ka10031.md           398 줄 신규 (전일 거래량 단순)
├ endpoint-21-ka10032.md           388 줄 신규 (거래대금 + now_rank/pred_rank)
├ endpoint-22-ka10023.md           442 줄 신규 (거래량 급증)
├ endpoint-23-ka10058.md           920 줄 신규 ★ Phase G reference (long ranking + 12 invsr_tp)
├ endpoint-24-ka10059.md           657 줄 신규 (wide breakdown 20 필드)
└ endpoint-25-ka10131.md           697 줄 신규 (연속매매 — 25 endpoint 의 마지막)

기존 파일 갱신:
CHANGELOG.md                     +200 줄 prepend
HANDOFF.md                       overwrite (본 문서)
```

**0 commits, 11 docs new (Phase E·F·G) + 2 updated. Phase A·B·C·D·E·F·G 누적 = 25 endpoint 계획서 100% 완성.**

### Context to Load (다음 세션 — Phase A 코드화 착수)

```
src/backend_kiwoom/docs/plans/master.md                    # 25 endpoint 카탈로그 + 모든 Phase 정의 + § 12 결정 기록
src/backend_kiwoom/docs/plans/endpoint-01-au10001.md       # Phase A — 토큰 발급
src/backend_kiwoom/docs/plans/endpoint-02-au10002.md       # Phase A — 토큰 폐기
src/backend_kiwoom/docs/plans/endpoint-14-ka10101.md       # Phase A — sector 마스터
src/backend_py/SPEC.md                                      # 패턴 reference (KiwoomClient / Settings / structlog 마스킹 / Fernet)
src/backend_kiwoom/SPEC.md                                  # 본 프로젝트 명세서 (코드화 진입 시 갱신)
```

다음 세션 첫 명령 추천:
- (A) `Phase D + E·F·G 14건 일괄 커밋 후 Phase A 코드화 착수해줘` — master.md § 11 권고
- (B) `Phase D 3건과 Phase E·F·G 11건 분리 커밋 후 Phase A 코드화 착수` — 분리 커밋 + 진입
- (C) `25 endpoint 계획서 검토 후 보강 필요한 항목 점검` — 코드화 진입 전 검토 라운드
