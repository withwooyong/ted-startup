# backend_kiwoom — 통합 작업 계획서

> **목적**: 키움 REST API 25개를 호출해 백테스팅용 데이터를 PostgreSQL 에 적재하는 **독립 백엔드** 신규 구축
> **작성일**: 2026-05-07
> **참조 문서**: `src/backend_py/키움 REST API 문서.xlsx` (209 sheets, 207 endpoints)
> **계획서 위치**: `src/backend_kiwoom/docs/plans/`

---

## 0. 핵심 요약

### 0.1 배경

기존 `backend_py` 는 KRX(`pykrx`) 기반 OHLCV 로 시그널 탐지·백테스팅을 수행한다. 그러나:

- **KRX 익명 차단** (2026-04~) 로 데이터 수집 자체가 불안정 (Memory: `project_krx_auth_blocker.md`)
- **NXT 거래 가격이 빠져 있어** 실제 체결가와 백테스팅 시계열 사이에 괴리 발생
- KRX OHLCV 단일 출처 의존 → 검증·재현·교차 점검이 불가능

→ 키움 REST API 를 **독립 출처**로 끌어와 KRX/NXT 두 시계열을 **분리 저장**하고, 백테스팅 엔진이 둘 중 어느 쪽으로도 돌 수 있게 만든다.

### 0.2 NXT 데이터 위치 (재확인)

| 질문 | 답 | 출처 |
|------|----|---|
| NXT 거래 가능 종목 | `ka10099` / `ka10100` 응답의 `nxtEnable` (`Y` 면 가능) | Excel `종목정보 리스트(ka10099)` R42, `종목정보 조회(ka10100)` R41 |
| NXT 일/주/월/년/분/틱 OHLCV | `ka10079~ka10094` + `ka10086` 모두 종목코드에 `_NX` suffix. 예: `005930` (KRX) → `005930_NX` (NXT) → `005930_AL` (SOR 통합) | Excel R22 "거래소별 종목코드 (KRX:039490, NXT:039490_NX, SOR:039490_AL)" |
| NXT 모의투자 지원 | **없음** — `mockapi.kiwoom.com` 은 KRX 만. NXT 는 `api.kiwoom.com` (운영) 전용 | Excel 모든 시트 R10 "모의투자 도메인 (KRX만 지원가능)" |

→ **백테스팅 데이터는 운영 도메인 호출이 필수**. 운영 자격증명 등록·암호화는 `backend_py` 의 `CredentialCipher` 패턴을 재사용.

### 0.3 독립 프로젝트 원칙

- **코드 의존성 없음**: `backend_py.app.*` 를 import 하지 않는다. Hexagonal/structlog 마스킹/Fernet 암호화 같은 **패턴은 재사용** 하되 클래스/모듈은 새로 작성한다.
- **DB 분리 가능성 유지**: 같은 PG 인스턴스 + 별도 스키마(`kiwoom`) 또는 별도 DB. 기본은 별도 스키마로 시작.
- **공통 자산은 docs 만**: `src/backend_py/키움 REST API 문서.xlsx` 만 참조. 코드는 0 import.

---

## 1. Tech Stack

`backend_py` 와 동일 스택 — 동일 팀이 운영하므로 학습 비용 최소화.

| 영역 | 선택 | 비고 |
|------|------|------|
| 언어 | Python 3.12+ | mypy --strict |
| 웹 | FastAPI 0.115+ | 수집 트리거 + 조회용 REST |
| ORM | SQLAlchemy 2.0 (asyncpg) | async 일급 |
| 마이그레이션 | Alembic (psycopg2 동기) | backend_py 와 동일 분리 패턴 |
| HTTP 클라이언트 | httpx + tenacity | 재시도 + MockTransport |
| 배치 | APScheduler | KST 정시 |
| 검증 | Pydantic v2 | strict typing |
| 패키지 매니저 | uv | lock 기반 재현성 |
| 로깅 | structlog + 민감값 마스킹 | backend_py PR 6 패턴 복제 |
| 암호화 | cryptography Fernet | KIWOOM_APPKEY/SECRETKEY 보호 |
| 테스트 | pytest + pytest-asyncio + testcontainers PG16 | CI 외부 호출 0 |

### 1.1 디렉토리 (예정)

```
src/backend_kiwoom/
├ pyproject.toml
├ uv.lock
├ alembic.ini
├ Dockerfile
├ README.md
├ SPEC.md                              # 본 문서가 코드 작성 후 갱신될 명세서
├ docs/
│  └ plans/
│     ├ master.md                      # ← 본 문서
│     ├ endpoint-01-au10001.md         # 인증
│     ├ endpoint-02-au10002.md
│     ├ endpoint-03-ka10099.md         # NXT 종목 마스터
│     ├ endpoint-04-ka10100.md
│     ├ endpoint-05-ka10001.md         # 펀더멘털
│     ├ endpoint-06-ka10081.md         # 일봉 (KRX + NXT)
│     ├ endpoint-07-ka10082.md
│     ├ endpoint-08-ka10083.md
│     ├ endpoint-09-ka10094.md
│     ├ endpoint-10-ka10086.md         # 일별 + 투자자별
│     ├ endpoint-11-ka10079.md         # 틱
│     ├ endpoint-12-ka10080.md         # 분봉
│     ├ endpoint-13-ka20006.md         # 업종 일봉
│     ├ endpoint-14-ka10101.md         # 업종코드 리스트
│     ├ endpoint-15-ka10014.md         # 공매도 추이
│     ├ endpoint-16-ka10068.md         # 대차거래 추이
│     ├ endpoint-17-ka20068.md         # 대차 종목별
│     ├ endpoint-18-ka10027.md         # 등락률 상위
│     ├ endpoint-19-ka10030.md         # 거래량 상위
│     ├ endpoint-20-ka10031.md
│     ├ endpoint-21-ka10032.md         # 거래대금 상위
│     ├ endpoint-22-ka10023.md         # 거래량 급증
│     ├ endpoint-23-ka10058.md         # 투자자별 일별 매매
│     ├ endpoint-24-ka10059.md
│     └ endpoint-25-ka10131.md         # 기관/외국인 연속매매
├ migrations/
│  └ versions/
│     ├ 001_init_kiwoom_schema.py
│     └ ...
├ app/
│  ├ main.py
│  ├ config/settings.py
│  ├ security/
│  │  └ credential_cipher.py           # Fernet (backend_py 복제·간소화)
│  ├ observability/logging.py          # structlog 마스킹 (복제)
│  ├ adapter/
│  │  ├ web/
│  │  │  ├ _deps.py
│  │  │  ├ _schemas.py
│  │  │  └ routers/
│  │  │     ├ stocks.py                # 종목 마스터·NXT 가능 여부 조회
│  │  │     ├ ohlcv.py                 # KRX/NXT OHLCV 조회
│  │  │     ├ collect.py               # 수동 수집 트리거
│  │  │     └ rankings.py              # 순위·투자자별 조회
│  │  └ out/
│  │     ├ kiwoom/                     # 키움 REST 어댑터
│  │     │  ├ _client.py               # KiwoomClient 본체 (httpx + 토큰 캐시)
│  │     │  ├ _records.py              # Pydantic raw row DTO
│  │     │  ├ _exceptions.py           # KiwoomUpstreamError, RateLimitError 등
│  │     │  ├ auth.py                  # au10001/au10002
│  │     │  ├ stkinfo.py               # ka10099/ka10100/ka10001/ka10101
│  │     │  ├ chart.py                 # ka10079~ka10094
│  │     │  ├ mrkcond.py               # ka10086
│  │     │  ├ rkinfo.py                # ka10027/30/31/32/23
│  │     │  ├ frgnistt.py              # ka10131
│  │     │  ├ shsa.py                  # ka10014
│  │     │  ├ slb.py                   # ka10068/ka20068
│  │     │  └ sect.py                  # ka20006 (chart 폴더에도 가능)
│  │     └ persistence/
│  │        ├ session.py
│  │        ├ base.py
│  │        ├ models/                  # ORM
│  │        │  ├ stock.py              # exchange_type, nxt_enable 추가
│  │        │  ├ stock_price_krx.py
│  │        │  ├ stock_price_nxt.py
│  │        │  ├ stock_fundamental.py
│  │        │  ├ short_selling.py
│  │        │  ├ lending_balance.py
│  │        │  ├ ranking_snapshot.py
│  │        │  ├ investor_flow.py
│  │        │  ├ sector.py
│  │        │  └ raw_response.py       # 원본 JSON snapshot (재처리 용)
│  │        └ repositories/
│  │           └ ...
│  ├ application/
│  │  ├ port/out/
│  │  │  └ kiwoom_port.py              # KiwoomChartFetcher Protocol 등
│  │  ├ dto/
│  │  └ service/
│  │     ├ token_service.py
│  │     ├ stock_master_service.py
│  │     ├ ohlcv_service.py            # KRX + NXT 동시 수집
│  │     ├ ranking_service.py
│  │     └ investor_flow_service.py
│  └ batch/
│     ├ scheduler.py
│     ├ daily_master_job.py
│     ├ daily_ohlcv_job.py
│     ├ daily_ranking_job.py
│     └ trading_day.py
├ scripts/
│  ├ entrypoint.py
│  ├ backfill_ohlcv.py
│  ├ seed_credentials.py
│  └ list_nxt_eligible.py              # nxtEnable=Y 종목 추출 CLI
└ tests/
   └ ...
```

---

## 2. 25 Endpoint 카탈로그

### 2.1 Tier 분류 (의존성 그래프 기준)

```
Tier 1 (블로커, 모든 호출의 전제)         3개  │ Phase A
  └ au10001 (token) ─┬─→ Tier 2~8 전부
    au10002 (revoke)
    ka10101 (업종코드)

Tier 2 (종목 마스터 — NXT 가능여부 source) 3개  │ Phase B
  ka10099 (mrkt_tp 별 list, nxtEnable)
  ka10100 (단건, nxtEnable)
  ka10001 (펀더멘털 PER/PBR/시총)

Tier 3 (백테스팅 OHLCV ★)                 5개  │ Phase C
  ka10081 (일봉, 수정주가) ─┐
  ka10082 (주봉)             ├─ KRX + NXT 둘 다 호출
  ka10083 (월봉)             │
  ka10094 (년봉)             ┘
  ka10086 (일별주가 + 투자자별 + 신용비, KRX/NXT 둘 다)

Tier 4 (보강 시계열)                     3개  │ Phase D
  ka10079 (틱) — 필요시
  ka10080 (분봉)
  ka20006 (업종 일봉)

Tier 5 (시그널 보강)                     3개  │ Phase E
  ka10014 (공매도 추이)
  ka10068 (대차거래 추이)
  ka20068 (대차거래 추이 종목별)

Tier 6 (순위 — 시나리오 검증)             5개  │ Phase F
  ka10027 (전일대비 등락률 상위)
  ka10030 (당일 거래량 상위)
  ka10031 (전일 거래량 상위)
  ka10032 (거래대금 상위)
  ka10023 (거래량 급증)

Tier 7 (투자자별 매매)                   3개  │ Phase G
  ka10058 (투자자별 일별 매매 종목)
  ka10059 (종목별 투자자/기관별)
  ka10131 (기관/외국인 연속매매)
```

### 2.2 25 Endpoint 표

| # | API ID | 명 | URL | NXT (`_NX`) 지원 | 우선순위 | 의존 |
|---|--------|----|-----|------------------|----------|------|
| 1 | `au10001` | 접근토큰 발급 | `/oauth2/token` | — | P0 | — |
| 2 | `au10002` | 접근토큰 폐기 | `/oauth2/revoke` | — | P0 | au10001 |
| 3 | `ka10099` | 종목정보 리스트 | `/api/dostk/stkinfo` | (응답 nxtEnable) | P0 | au10001 |
| 4 | `ka10100` | 종목정보 조회 | `/api/dostk/stkinfo` | (응답 nxtEnable) | P0 | au10001 |
| 5 | `ka10001` | 주식기본정보요청 | `/api/dostk/stkinfo` | ★ stk_cd suffix | P1 | au10001, ka10099 |
| 6 | `ka10081` | 주식일봉차트 | `/api/dostk/chart` | ★ | **P0** | ka10099 |
| 7 | `ka10082` | 주식주봉차트 | `/api/dostk/chart` | ★ | P1 | ka10099 |
| 8 | `ka10083` | 주식월봉차트 | `/api/dostk/chart` | ★ | P1 | ka10099 |
| 9 | `ka10094` | 주식년봉차트 | `/api/dostk/chart` | ★ | P2 | ka10099 |
| 10 | `ka10086` | 일별주가요청 | `/api/dostk/mrkcond` | ★ | **P0** | ka10099 |
| 11 | `ka10079` | 주식틱차트 | `/api/dostk/chart` | ★ | P3 | ka10099 |
| 12 | `ka10080` | 주식분봉차트 | `/api/dostk/chart` | ★ | P2 | ka10099 |
| 13 | `ka20006` | 업종일봉조회 | `/api/dostk/chart` | (참고) | P2 | ka10101 |
| 14 | `ka10101` | 업종코드 리스트 | `/api/dostk/stkinfo` | — | P1 | au10001 |
| 15 | `ka10014` | 공매도 추이 ✅ Phase E | `/api/dostk/shsa` | ★ | P1 | ka10099 |
| 16 | `ka10068` | 대차거래 추이 ✅ Phase E (scope=MARKET) | `/api/dostk/slb` | (참고) | P1 | au10001 |
| 17 | `ka20068` | 대차거래 추이(종목별) ✅ Phase E (scope=STOCK KRX only) | `/api/dostk/slb` | (참고) | P2 | ka10099 |
| 18 | `ka10027` | 전일대비 등락률 상위 | `/api/dostk/rkinfo` | mrkt_tp 1/2/3 | P2 | au10001 |
| 19 | `ka10030` | 당일 거래량 상위 | `/api/dostk/rkinfo` | mrkt_tp 1/2/3 | P2 | au10001 |
| 20 | `ka10031` | 전일 거래량 상위 | `/api/dostk/rkinfo` | mrkt_tp 1/2/3 | P3 | au10001 |
| 21 | `ka10032` | 거래대금 상위 | `/api/dostk/rkinfo` | mrkt_tp 1/2/3 | P2 | au10001 |
| 22 | `ka10023` | 거래량 급증 | `/api/dostk/rkinfo` | mrkt_tp 1/2/3 | P2 | au10001 |
| 23 | `ka10058` | 투자자별 일별 매매 종목 | `/api/dostk/stkinfo` | mrkt_tp 1/2/3 | P2 | au10001 |
| 24 | `ka10059` | 종목별 투자자/기관별 | `/api/dostk/stkinfo` | ★ | P2 | ka10099 |
| 25 | `ka10131` | 기관/외국인 연속매매 | `/api/dostk/frgnistt` | mrkt_tp 1/2/3 | P2 | au10001 |

**범례**:
- `★` = `stk_cd` 파라미터에 `_NX` suffix 를 붙여 호출 → KRX/NXT 시계열 분리 수집
- `mrkt_tp 1/2/3` = 거래소 구분 파라미터로 (1: KRX / 2: NXT / 3: 통합) 분리 호출
- P0 = 백테스팅 동작에 즉시 필요 / P1 = 1주 내 / P2 = 2주 내 / P3 = 선택

---

## 3. NXT 수집 전략 (백테스팅 핵심)

### 3.1 기본 원칙

> **"KRX 와 NXT 는 별도 시계열로 분리 저장. 통합은 application 레이어에서 view 로 합성."**

이유:
1. **체결 가격이 다름** — 같은 종목·같은 시각이라도 KRX 와 NXT 가 호가단위 차이로 미세하게 갈림
2. **거래량/거래대금이 분리** — NXT 거래가 장 운영시간(8:00~20:00 등) 으로 길어 OHLCV 윈도가 다름
3. **재현성** — 백테스팅 결과를 "어느 거래소 가격으로 돌렸는지" 추적 가능해야 함
4. **장애 격리** — NXT 만 수집 실패해도 KRX 시계열은 그대로 사용

### 3.2 수집 흐름

```
1. ka10099 호출 (mrkt_tp 별, 0/10/30/50/60/...)
   → stock 마스터 upsert + nxt_enable 컬럼 채움

2. nxt_enable='Y' 종목만 NXT 호출 큐에 등록

3. ka10081 (일봉) 두 번 호출:
     a) stk_cd=005930        → stock_price_krx 테이블에 적재
     b) stk_cd=005930_NX     → stock_price_nxt 테이블에 적재 (nxt_enable='Y' 만)

4. 백테스팅 엔진은 시나리오 별로 분기:
     - 보수적: stock_price_krx 단독
     - NXT 포함: stock_price_combined view (KRX 가 없으면 NXT 로 fallback / 가중평균 등)
```

### 3.3 SOR (`_AL`) 처리

키움 SOR(최선주문집행) `_AL` suffix 는 KRX/NXT 자동 라우팅으로 **체결 시점 기준** 최선가. 백테스팅용으로는:

- **권장**: 별도 수집하지 않음 (실시간 체결 의미가 강함, 과거 데이터 일관성 보장 약함)
- 필요 시 PoC 단위로 ka10081 만 `_AL` 추가 호출하여 비교 검증 데이터 제공

### 3.4 종목코드 규칙

```python
# enums.py (예정)
class ExchangeType(StrEnum):
    KRX = "KRX"
    NXT = "NXT"
    SOR = "SOR"

def to_kiwoom_code(stock_code: str, exchange: ExchangeType) -> str:
    if exchange is ExchangeType.KRX:
        return stock_code            # "005930"
    if exchange is ExchangeType.NXT:
        return f"{stock_code}_NX"    # "005930_NX"
    if exchange is ExchangeType.SOR:
        return f"{stock_code}_AL"    # "005930_AL"
```

---

## 4. DB 스키마 초안

### 4.1 핵심 테이블 (Phase B~G 누적)

| 테이블 | 핵심 컬럼 | 용도 |
|--------|-----------|------|
| `stock` | id PK, stock_code (UQ, 6), stock_name, market_type (KOSPI/KOSDAQ/KONEX/ETN/...), nxt_enable BOOL, sector_code, listed_date, list_count, audit_info, last_price | ka10099/100 마스터 |
| `stock_fundamental` | stock_id FK, asof_date, per/eps/roe/pbr/ev/bps, sale_amt/bus_pro/cup_nga, market_cap, dstr_stk/rt | ka10001 일별 스냅샷 |
| `stock_price_krx` | stock_id FK, trading_date, open/high/low/close (BIGINT), volume, amount, change_rate, adjusted (BOOL) | ka10081 KRX |
| `stock_price_nxt` | stock_id FK, trading_date, open/high/low/close, volume, amount, change_rate, adjusted | ka10081 NXT (nxt_enable='Y' 만) |
| `stock_price_weekly_krx` / `_nxt` | … | ka10082 |
| `stock_price_monthly_krx` / `_nxt` | … | ka10083 |
| `stock_price_yearly_krx` / `_nxt` | … | ka10094 |
| `stock_daily_flow` | stock_id FK, exchange_type, date, open/high/low/close, volume, amount, ind_netprps, orgn_netprps, frgn_netprps, for_qty, for_rt, for_wght, crd_rt, crd_remn_rt | ka10086 (KRX/NXT 분리) |
| `stock_minute_price` | stock_id FK, exchange_type, ts (TZ), tic_scope (1/3/5/...), open/high/low/close/volume | ka10080 (선택적) |
| `stock_tick_price` | stock_id FK, exchange_type, ts, price, volume | ka10079 (선택적, 대용량 — 파티션 필수) |
| `sector` | sector_code PK, sector_name, market_type | ka10101 |
| `sector_price_daily` | **sector_id BIGINT FK** (1R HIGH #4 — sector.id BIGSERIAL 일치), date, open/high/low/close (centi BIGINT 4), volume | ka20006 ✅ D-1 `249c277` |
| `short_selling_kw` | stock_id FK, date, exchange_type, short_volume, short_amount, short_ratio | ka10014 |
| `lending_balance_kw` | stock_id FK, date, balance_qty, balance_amt, change_qty | ka10068/ka20068 |
| `ranking_snapshot` | id PK, snapshot_date, snapshot_time, ranking_type (etr_rate/volume/amount/...), exchange_type, rank, stock_id FK, payload JSONB | ka10027/30/31/32/23 통합 저장 |
| `investor_flow_daily` | stock_id FK, date, exchange_type, investor_type (ind/orgn/frgn/etc), buy_qty, sell_qty, net_qty, buy_amt, sell_amt, net_amt | ka10058/10059 |
| `frgn_orgn_consecutive` | stock_id FK, date, frgn_consec_days, frgn_consec_qty, orgn_consec_days, orgn_consec_qty | ka10131 |
| `kiwoom_credential` | id PK, alias UQ, appkey_cipher BYTEA, secretkey_cipher BYTEA, key_version, env (prod/mock), created_at, updated_at | 자격증명 Fernet |
| `kiwoom_token` | id PK, credential_id FK, token_cipher BYTEA, token_type, expires_at, issued_at | au10001 캐시 (선택) |
| `raw_response` | id PK, api_id, request_hash, request_payload JSONB, response_payload JSONB, http_status, fetched_at | 원본 JSON 보관 (재처리·디버깅) |

### 4.2 인덱스/제약 패턴

- **모든 시계열**: `UNIQUE(stock_id, trading_date)` + `(trading_date)` 월별 파티션 권장
- **OHLCV 분리 저장**: `stock_price_krx` 와 `stock_price_nxt` 두 테이블. `nxt_enable=False` 종목은 NXT 테이블에 row 자체가 없음 → 조인 시 LEFT 가 자연
- **순위 스냅샷**: 일자·시각·랭킹타입 단위 묶음 저장. payload JSONB 로 가변 컬럼 흡수
- **raw_response**: 일/시간 단위 파티션 + 90일 retention (재처리 후 삭제)

### 4.3 Migration 분할

```
001_init_kiwoom_schema.py
  └ stock, kiwoom_credential, kiwoom_token, raw_response

002_stock_fundamental_and_sector.py
  └ stock_fundamental, sector, sector_price_daily

003_ohlcv_krx.py
  └ stock_price_krx, weekly_krx, monthly_krx, yearly_krx

004_ohlcv_nxt.py
  └ stock_price_nxt, weekly_nxt, monthly_nxt, yearly_nxt
  + stock.nxt_enable BOOL 컬럼 (003 와 분리해 NXT 활성화 마이그레이션 따로 적용 가능)

005_intraday.py (선택)
  └ stock_minute_price, stock_tick_price (월별 파티션)

006_short_lending.py
  └ short_selling_kw, lending_balance_kw

007_rankings.py
  └ ranking_snapshot

008_investor_flow.py
  └ stock_daily_flow, investor_flow_daily, frgn_orgn_consecutive
```

---

## 5. Phase 분할 (수행 순서)

| Phase | 기간 | 산출물 | Endpoint |
|-------|------|--------|----------|
| **Phase A — 기반** | 2~3 일 | pyproject, Dockerfile, settings, structlog 마스킹, Fernet, KiwoomClient (httpx + 토큰 캐시 + tenacity), Alembic 001/002, OAuth UseCase | au10001, au10002, ka10101 |
| **Phase B — 종목 마스터 (NXT enable)** | 2 일 | stock 테이블 + nxt_enable, ka10099 mrkt_tp 6종 순회 (0/10/30/50/60/70), ka10100 단건, 일일 마스터 배치 | ka10099, ka10100, ka10001 |
| **Phase C — OHLCV 백테스팅 본체 ★** | 4~5 일 | stock_price_krx + stock_price_nxt + 주/월/년, ka10081/82/83/94 (KRX·NXT 동시), ka10086, 백필 스크립트 | ka10081, ka10082, ka10083, ka10094, ka10086 |
| **Phase D — 보강 시계열** | 2 일 | stock_minute_price, sector, ka10080 분봉, ka10079 틱(선택), ka20006 업종 일봉 | ka10079, ka10080, ka20006 |
| **Phase E — 시그널 보강** | 2 일 | short_selling_kw, lending_balance_kw, ka10014 / ka10068 / ka20068 | ka10014, ka10068, ka20068 |
| **Phase F — 순위** | 3 일 | ranking_snapshot, 5개 ranking endpoint 통합 collector | ka10027, ka10030, ka10031, ka10032, ka10023 |
| **Phase G — 투자자별** | 2~3 일 | stock_daily_flow, investor_flow_daily, frgn_orgn_consecutive | ka10058, ka10059, ka10131 |
| **Phase H — 통합** | 2 일 | 백테스팅 view (KRX/NXT 합성), 데이터 품질 리포트, README/SPEC.md, Grafana 대시보드 (선택) | — |

**총 19~22 일** 추정. 인력 1명 풀타임 기준.

### 5.1 Phase A 가 끝나면 가능한 것

- 토큰 발급/폐기
- `KiwoomClient` 재사용 가능 (다음 Phase 에서 `__aenter__/_get_access_token` 만 활용)
- structlog 가 토큰/secretkey 자동 마스킹
- 업종 코드 dict (ka10101) 로 후속 sector_code 매핑 준비

### 5.2 Phase C 가 끝나면 가능한 것

- KRX/NXT 일봉 백테스팅 즉시 가능
- 기존 `backend_py.BacktestEngineService` 와 동일한 pivot/shift 로직을 `kiwoom.stock_price_krx` 기준으로 돌려 **결과 비교** 가능
- 데이터 정합성 검증: 같은 날·같은 종목의 KRX vs `pykrx` close_price 차이가 ±1 KRW 이내인지 등

---

## 6. 외부 호출 정책 (모든 Phase 공통)

### 6.1 KiwoomClient 설계

```python
# app/adapter/out/kiwoom/_client.py (예정 시그니처)
class KiwoomClient:
    """모든 키움 endpoint 의 공통 트랜스포트.

    - `__aenter__/__aexit__` 지원 (요청 스코프 + 프로세스 공유 둘 다 가능)
    - access_token 인스턴스 캐시 + expires_dt 5분 마진 자동 재발급
    - cont-yn / next-key 자동 페이지네이션 헬퍼 제공
    - tenacity @retry: HTTPError + 5xx + 429 만 재시도, 4xx (잘못된 요청)는 즉시 fail
    - rate limit guard: asyncio.Semaphore(N) — 키움 공식 RPS 가이드 충족
    """

    async def call(
        self,
        api_id: str,                    # "ka10081"
        endpoint: str,                  # "/api/dostk/chart"
        body: dict[str, Any],
        *,
        cont_yn: str | None = None,
        next_key: str | None = None,
    ) -> KiwoomResponse: ...

    async def call_paginated(
        self,
        api_id: str,
        endpoint: str,
        body: dict[str, Any],
        *,
        max_pages: int = 50,
    ) -> AsyncIterator[KiwoomResponse]: ...
```

### 6.2 Pagination

키움은 **응답 Header 의 `cont-yn=Y` + `next-key`** 를 다음 요청 헤더에 그대로 넣어 추가 호출. backend_kiwoom 는 이를 `call_paginated` 헬퍼로 추상화.

### 6.3 Rate Limit

키움 공식 가이드는 **초당 5 회** 권장. 안전 마진 4 RPS:

```python
SEMAPHORE = asyncio.Semaphore(4)  # 4 동시 호출
MIN_INTERVAL = 0.25                # 호출 간 최소 250ms

async def _throttle(self):
    elapsed = time.monotonic() - self._last_call_ts
    if elapsed < MIN_INTERVAL:
        await asyncio.sleep(MIN_INTERVAL - elapsed)
    self._last_call_ts = time.monotonic()
```

429 응답 시 tenacity 가 exp backoff (1s → 8s) 로 재시도.

### 6.4 에러 분류

| HTTP / 응답 status | 도메인 예외 | 라우터 매핑 |
|--------------------|-------------|-------------|
| 401, 403 + 토큰 메시지 | `KiwoomCredentialRejectedError` | 400 |
| 429 | `KiwoomRateLimitedError` (재시도) | — |
| 5xx, 네트워크, 파싱 실패 | `KiwoomUpstreamError` | 502 |
| 응답 `return_code != 0` (비정상 처리) | `KiwoomBusinessError` (코드 보존) | 400 + detail |
| 토큰 만료 직전 | 자동 재발급 |  — |

### 6.5 자격증명 보관

`backend_py` 패턴 복제:
- `Settings.kiwoom_credential_master_key` (env 주입, Fernet 32B base64)
- `kiwoom_credential` 테이블에 `appkey_cipher`, `secretkey_cipher` 만 BYTEA 저장
- `KiwoomCredentialCipher` 가 encrypt/decrypt
- 운영 자격증명은 DB only — Settings 에는 두지 않음 (실수로 .env 커밋 방지)

### 6.6 로깅 마스킹

`structlog` processor 가 자동으로 다음을 `[MASKED]` / `[MASKED_HEX]` 처리:
- `appkey`, `secretkey`, `authorization`, `token`, `access_token`, `secret`, `_master_key`, `kiwoom_appkey`, `kiwoom_secretkey`
- 40+ hex / JWT 패턴 정규식

---

## 7. 도메인/모드 (Settings)

```python
# config/settings.py (예정)
class Settings(BaseSettings):
    # 키움 도메인
    kiwoom_base_url_prod: str = "https://api.kiwoom.com"
    kiwoom_base_url_mock: str = "https://mockapi.kiwoom.com"  # KRX 만 — NXT 데이터는 prod 필수
    kiwoom_default_env: Literal["prod", "mock"] = "mock"      # 운영 배포만 prod
    kiwoom_request_timeout_seconds: float = 15.0
    kiwoom_min_request_interval_seconds: float = 0.25
    kiwoom_concurrent_requests: int = 4

    # 자격증명 마스터키
    kiwoom_credential_master_key: str = ""

    # NXT 수집 토글
    nxt_collection_enabled: bool = True   # False 면 KRX 만, 운영 전환 전 안전판

    # 백필 윈도
    backfill_max_days: int = 1095          # 3년
    backfill_concurrency: int = 2          # NXT 동시 백필 제한
```

---

## 8. 테스트 전략

### 8.1 Layer 별

| Layer | 도구 | 외부 호출 |
|-------|------|-----------|
| Adapter (KiwoomClient) | `httpx.MockTransport` 주입 + 결정론 응답 | 0 |
| Repository | testcontainers PG16 + 빈 DB | 0 |
| UseCase / Service | Adapter mock + Repository real | 0 |
| Batch / Scheduler | Job 단위 실행, 시간 mock | 0 |
| Smoke (`@pytest.mark.requires_kiwoom_real`) | 실 운영 키 | 1회/PR (CI 기본 skip) |

### 8.2 픽스처

- `kiwoom_mock_transport(api_id) → httpx.MockTransport` — 한 줄로 결정론 응답 등록
- `seed_stock_master(session, stocks=[...])` — Repository 통합 테스트 setup
- `frozen_time(2025, 5, 7)` — 거래일 판정·캐시 만료 검증

### 8.3 NXT 검증 시나리오

1. `nxt_enable='Y'` 종목 `005930` 은 KRX 와 NXT 양쪽 호출 모두 성공해 **두 row** 가 적재된다
2. `nxt_enable='N'` 종목은 NXT 호출이 시도되지 않는다 (큐에 등록도 안 됨)
3. NXT 호출만 실패하고 KRX 호출은 성공하면 → KRX row 는 저장, NXT row 는 미저장 + 에러 로그
4. 같은 (stock, date) 의 KRX vs NXT close_price 차이가 ±5% 이내인지 데이터 품질 리포트 생성

---

## 9. 위험 / 의존성

| 위험 | 완화 |
|------|------|
| 키움 공식 RPS 한도 (초당 5회) | Semaphore(4) + 250ms 인터벌 + 429 재시도 + 동시 백필 2개로 제한 |
| 운영 자격증명만 NXT 지원 | mock 환경에서는 nxt_collection_enabled=False 강제. 실수 prod 호출 차단 |
| 페이지네이션 무한 루프 | call_paginated 가 `max_pages=50` 하드 캡 + cont_yn 추적 카운터 |
| ka10079 틱 데이터 폭증 | Phase D 에서 별도 의사결정 — 기본 OFF, 종목/기간 화이트리스트 시에만 수집 |
| 모든 시계열 충돌 (한 PG 인스턴스) | 별도 schema (`kiwoom`) + 월별 파티션 + retention 정책 |
| 키움 API 변경 (필드 추가/리네임) | raw_response 테이블에 원본 JSON 보관 → 리파싱 가능 |
| 토큰 노출 사고 | structlog 자동 마스킹 + 응답 본문은 DEBUG 로그 only |

---

## 10. Per-Endpoint 작업계획서 템플릿

각 endpoint 계획서는 `endpoint-XX-{api_id}.md` 파일 1개. 다음 섹션을 채운다.

```markdown
# endpoint-XX-{api_id}.md — {API 명}

## 0. 메타
- API ID: {api_id}
- 분류: {Tier 1~7}
- Phase: {A~G}
- Method: POST
- 운영 URL: https://api.kiwoom.com{path}
- 모의 URL: {KRX 만 / N/A}
- 의존: {선행 endpoint id}

## 1. 목적
{왜 이 endpoint 가 필요한가 — 백테스팅 시나리오와 연결}

## 2. Request 명세
- Header: api-id, authorization, cont-yn, next-key
- Body: {필드 표 — Excel 시트 그대로 + 검증 규칙}

## 3. Response 명세
- Body: {필드 표 + 우리가 영속화할 컬럼 매핑}

## 4. NXT 처리
- stk_cd 에 _NX 붙이는가: Y/N
- nxt_enable 게이팅: Y/N
- mrkt_tp 별 분리: Y/N

## 5. DB 스키마
- 영향 테이블: {테이블명}
- 신규 컬럼: {있다면}
- UNIQUE / 인덱스: {제약}

## 6. UseCase / Service
- 클래스명: {예: SyncDailyOhlcvUseCase}
- 시그니처: async def execute(...) -> ...
- 호출 빈도: 일 1회 / 분 / 실시간

## 7. 배치 / 트리거
- 스케줄: KST CronTrigger 표현식
- 수동: POST /api/kiwoom/collect/{api_id}?date=YYYY-MM-DD (admin)

## 8. 에러 처리
- 502 (KiwoomUpstreamError): retry 후에도 실패 시
- 400 (KiwoomBusinessError): return_code != 0
- 429: 자동 backoff, count 리포트

## 9. 테스트
- Unit: MockTransport + 결정론 응답
- Integration: testcontainers PG + repository
- 시나리오: {NXT enable Y/N, 페이지네이션, 빈 응답}

## 10. 완료 기준 (DoD)
- [ ] Adapter 메서드 작성 + 단위 테스트
- [ ] Repository 메서드 작성 + 통합 테스트
- [ ] UseCase 작성 + 통합 테스트
- [ ] 라우터 작성 (수동 트리거)
- [ ] 배치 job (해당 시) 등록
- [ ] CHANGELOG 항목 추가
- [ ] 운영 1회 dry-run 으로 1종목 데이터 확인

## 11. 위험 / 메모
{이 endpoint 만의 특이사항 — 예: ka10079 의 last_tic_cnt 페이지네이션}
```

---

## 11. 다음 세션 진행 순서

1. **Phase A 계획서 3건 먼저** — `endpoint-01-au10001.md` / `endpoint-02-au10002.md` / `endpoint-14-ka10101.md`
   - 동시에 pyproject/Dockerfile/Alembic 001 스캐폴딩 합의 가능
2. **Phase B 계획서 3건** — `endpoint-03-ka10099.md` / `endpoint-04-ka10100.md` / `endpoint-05-ka10001.md`
3. **Phase C 계획서 5건 (백테스팅 본체)** — `endpoint-06-ka10081.md` 부터
4. 이후 Phase D/E/F/G 순차

각 Phase 의 계획서를 모두 받은 후 **그 Phase 만 코드화** 하는 식으로 진행.

---

## 12. 메모 / 결정 기록

| 일자 | 항목 | 결정 |
|------|------|------|
| 2026-05-07 | 범위 | MVP 8 + 보조 6 + 순위/투자자 11 = **25 endpoint** (ETF/ELW/금현물/주문/실시간웹소켓 제외) |
| 2026-05-07 | 스택 | backend_py 와 동일 (FastAPI + SQLAlchemy 2.0 async + uv + Alembic + structlog + Fernet) |
| 2026-05-07 | 코드 의존성 | `backend_py.app.*` 0 import. 패턴만 복제 |
| 2026-05-07 | DB | 별도 schema `kiwoom` (또는 별도 DB) — 기본은 schema 분리 |
| 2026-05-07 | NXT 저장 전략 | KRX/NXT **물리 분리 테이블** + application 레이어 view 합성 |
| 2026-05-07 | SOR (`_AL`) | 정기 수집 안 함. 비교 PoC 만 |
| 2026-05-07 | 모의투자 | mock 도메인은 KRX 전용 — NXT 수집은 운영(prod) 필수 |
| 2026-05-07 | 자격증명 | Fernet 암호화 후 `kiwoom_credential` BYTEA 저장 |
| 2026-05-07 | RPS | 초당 4회 + 250ms 인터벌 (공식 5회 안전 마진) |

---

_이 문서는 코드 작성 시작 후 SPEC.md 로 분기/진화시킨다. 계획서는 master.md + endpoint-XX-{api_id}.md 25개로 완성된다._
