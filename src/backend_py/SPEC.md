# backend_py — 종합 기술 명세서

> **대상**: `src/backend_py/` (FastAPI + SQLAlchemy 2.0 async, Hexagonal Architecture)
> **작성일**: 2026-05-07
> **소스 기준 커밋**: master `b3e2546` (Cp 2α 직후)
> **스펙 범위**: 개요·기술스택 → 아키텍처 → 도메인/DB → REST API → 외부연동 → 배치 → 보안/관측 → 마이그레이션/배포

---

## 1. 개요·기술스택

### 1.1 프로젝트 정체성

TED Signal 백엔드는 한국 주식 시장의 **이상 신호**(대차잔고 급감 / 추세전환 / 숏스퀴즈)를 일별 탐지·집계해 알림·백테스트·AI 리포트로 제공하는 서비스다. Spring Boot 원본을 2026-04 Phase 1~9 에 걸쳐 Python 으로 전면 재작성했다.

- **패키지명**: `ted-signal-backend` (`pyproject.toml:2`)
- **버전**: `0.1.0`
- **런타임**: Python `>=3.12,<3.15`
- **패키지 매니저**: `uv` (lock 파일 기반 재현성)
- **레포 위치**: `src/backend_py/` (모노레포의 백엔드 루트)

### 1.2 도메인 책임 (P10~P15)

| 영역 | 모듈 | 책임 |
|------|------|------|
| 시장데이터 수집 | `MarketDataCollectionService` | KRX OHLCV / 공매도 / 대차잔고 일일 적재 |
| 시그널 탐지 | `SignalDetectionService` | 3종 시그널 (RAPID_DECLINE / TREND_REVERSAL / SHORT_SQUEEZE) |
| 백테스팅 | `BacktestEngineService` | vectorbt + pandas pivot 으로 N영업일 후 수익률 집계 |
| 알림 | `NotificationService` | Telegram HTML 메시지, 사용자 선호도 기반 필터링 |
| 포트폴리오 (P10) | `RegisterAccount/RecordTransaction/ComputeSnapshot/ComputePerformance` | 계좌·보유·거래·평가 스냅샷·성과 |
| 엑셀 임포트 (P10) | `ExcelImportService` | KIS 체결내역 .xlsx → portfolio_transaction |
| KIS 연동 (P11) | `SyncPortfolioFromKisMock/RealUseCase`, `TestKisConnectionUseCase` | 잔고 동기화 (mock + real) |
| 자격증명 (P15) | `BrokerageCredentialUseCase`, `CredentialCipher` | Fernet 대칭 암호화 CRUD |
| AI 리포트 (P13) | `AnalysisReportService`, `OpenAIProvider` | DART Tier1 + Tier2 정성 → strict JSON |

### 1.3 핵심 의존성 (`pyproject.toml`)

- **웹**: `fastapi>=0.115`, `uvicorn[standard]`, `slowapi`, `prometheus-fastapi-instrumentator`
- **DB**: `sqlalchemy[asyncio]>=2.0.36`, `asyncpg`, `psycopg2-binary` (Alembic 전용), `alembic>=1.14`
- **데이터**: `pandas>=2.2`, `numpy>=1.26`, `vectorbt>=0.26`, `pykrx>=1.0.45`
- **HTTP/외부**: `httpx>=0.27`, `tenacity>=9` (지수 백오프 재시도)
- **배치**: `apscheduler>=3.10`
- **암호화**: `cryptography>=43` (Fernet)
- **엑셀**: `openpyxl>=3.1`, `python-multipart`
- **로깅**: `structlog>=24.4`
- **검증**: `pydantic>=2.9`, `pydantic-settings>=2.6`

### 1.4 개발 도구 (`extras = dev`)

`pytest`, `pytest-asyncio` (`asyncio_mode=auto`), `pytest-cov`, `testcontainers[postgres]>=4.8`, `ruff>=0.7`, `mypy>=1.13`, `pandas-stubs`, `types-python-dateutil`.

### 1.5 코드 스타일

- **포매팅**: `ruff format` (line 120, double quote)
- **린트 룰셋**: `E,W,F,I,B,UP,N,SIM`
  - `E501` (line length) 무시 — 포매터가 처리
  - `B008` 무시 — FastAPI Depends/Query/Path 의 공식 DI 패턴
- **타입체크**: `mypy --strict`
  - `disallow_untyped_defs`, `no_implicit_optional`, `warn_redundant_casts`, `warn_unused_ignores`
  - `pydantic.mypy` plugin 활성화
  - 외부 모듈 stub 누락 무시: `prometheus_fastapi_instrumentator`, `pykrx`, `apscheduler`
- **테스트 마커**: `requires_kis_real_account` — 기본 skip, 로컬에서 `pytest -m requires_kis_real_account` 로 실행

---

## 2. 아키텍처 (Hexagonal)

### 2.1 레이어 구조

```
app/
├ domain/                       # 순수 모델 (현재 비어있음 — ORM 모델이 도메인 표현 겸용)
├ application/                  # UseCase + Port + DTO
│  ├ dto/                       # 입출력 값 객체
│  │  ├ credential.py           # MaskedCredentialView
│  │  ├ kis.py                  # KisCredentials, KisHoldingRow, KisEnvironment
│  │  └ results.py              # CollectionResult, DetectionResult, BacktestExecutionResult
│  ├ port/out/                  # 외부 추상화 (Protocol)
│  │  ├ kis_port.py             # KisHoldingsFetcher, KisRealFetcherFactory, KisUpstreamError
│  │  └ llm_provider.py         # LLMProvider, Tier1/Tier2 dataclass, JSON Schema
│  └ service/                   # UseCase 구현
│     ├ analysis_report_service.py
│     ├ backtest_service.py
│     ├ excel_import_service.py
│     ├ market_data_service.py
│     ├ notification_service.py
│     ├ portfolio_service.py    # 8 UseCase + 2 ErrorClass 계층
│     └ signal_detection_service.py
├ adapter/
│  ├ web/                       # FastAPI inbound adapter
│  │  ├ _deps.py                # Depends 모음 (세션, KRX/KIS/DART/Telegram, admin key)
│  │  ├ _schemas.py             # Pydantic 요청/응답 스키마
│  │  ├ _error_handler.py       # RequestValidationError → 400 매핑
│  │  ├ _rate_limit.py          # slowapi Limiter (admin key 단위)
│  │  └ routers/                # 7 라우터 (signals, backtest, batch, notifications, portfolio, reports + 메타)
│  └ out/                       # outbound adapter
│     ├ ai/openai_provider.py   # OpenAI Chat Completions, strict JSON
│     ├ external/               # KRX, KIS, DART, Telegram (httpx + tenacity)
│     └ persistence/            # SQLAlchemy ORM + Repository
│        ├ base.py              # DeclarativeBase + TimestampMixin
│        ├ session.py           # AsyncEngine 싱글톤 + sessionmaker
│        ├ models/              # 12 ORM 모델
│        └ repositories/        # 13 Repository
├ batch/                        # APScheduler 잡
│  ├ scheduler.py               # AsyncIOScheduler + CronTrigger
│  ├ market_data_job.py         # 3-Step 파이프라인 (collect → detect → notify)
│  ├ backtest_job.py            # 단일 Step 파이프라인
│  └ trading_day.py             # 주말 판정
├ config/settings.py            # Pydantic Settings (env + .env)
├ observability/logging.py      # structlog + 민감 데이터 마스킹
├ security/credential_cipher.py # Fernet 대칭 암호화
└ main.py                       # FastAPI app factory + lifespan
```

### 2.2 의존성 방향 규칙

- `adapter/web` → `application/service` → `application/port` ← `adapter/out`
- `adapter/out/external/kis_client.py` 는 `application/port/out/kis_port.py` 의 `KisHoldingsFetcher` Protocol 을 **structural typing** 으로 만족 (명시 상속 없음)
- `application` 레이어는 `adapter/out` 의 concrete 클래스를 **import 하지 않는다**. 단, `_deps.py`(composition root)는 양쪽 모두를 알고 주입한다.
- `application/dto` 는 `KisCredentials`·`MaskedCredentialView` 처럼 외부 adapter 가 import 해도 되는 값 객체 — application → adapter 방향으로 흐른다 (Hexagonal 합치).

### 2.3 코드 생성 3-Pass 전략

`CLAUDE.md` 에 명시된 패턴:
1. **Scaffolding Pass**: SQLAlchemy 모델, Repository, UseCase Protocol, Pydantic DTO, FastAPI Router 스켈레톤 일괄 생성
2. **Domain Pass**: 비즈니스 로직 개별 구현 (pandas 벡터화 우선)
3. **Integration Pass**: 인증 의존성, 예외 핸들러, testcontainers 통합 테스트, Docker + entrypoint

### 2.4 동시성 모델

- **asyncio 일급**: 모든 I/O (DB, HTTP, 파일) 는 async
- **상호배제**: `KrxClient._lock = asyncio.Lock()` — pykrx 호출은 2초 rate-limit 직렬화 (`krx_client.py:62`)
- **CPU 바운드 분리**: `asyncio.to_thread(self._invoke_silent, ...)` — pykrx 동기 함수를 워커 스레드로 (`krx_client.py:197`)
- **세션 스코프**: 요청당 1 세션 (`_deps.get_session`), 정상 종료 시 commit / 예외 시 rollback (`_deps.py:27-36`)
- **싱글톤**: `get_engine`, `get_sessionmaker`, `get_settings`, `get_krx_client`, `get_credential_cipher` 모두 `@lru_cache(maxsize=1)`

---

## 3. 도메인·DB 스키마

### 3.1 Enum (StrEnum, `models/enums.py`)

| Enum | 값 |
|------|-----|
| `MarketType` | `KOSPI`, `KOSDAQ` |
| `SignalType` | `RAPID_DECLINE`, `TREND_REVERSAL`, `SHORT_SQUEEZE` |
| `SignalGrade` | `A` (≥80), `B` (≥60), `C` (≥40), `D` (<40) — `from_score(int)` 분류 |
| `BatchJobStatus` | `SUCCESS`, `FAILED`, `RUNNING` |

### 3.2 ORM 모델 일람 (12 테이블)

#### 3.2.1 시장 데이터 (Phase 1~2)

**stock** (`models/stock.py`) — 종목 마스터
| 컬럼 | 타입 | 제약 |
|------|------|------|
| id | BigInteger | PK, autoincrement |
| stock_code | VARCHAR(6) | NOT NULL, UNIQUE |
| stock_name | VARCHAR(100) | NOT NULL |
| market_type | VARCHAR(10) | NOT NULL |
| sector | VARCHAR(100) | nullable |
| is_active | Boolean | default true |
| created_at / updated_at / deleted_at | TIMESTAMPTZ | server_default + onupdate |

**stock_price** (`models/stock_price.py`) — 일별 시세, **trading_date 월별 파티션**
- PK: `(id, trading_date)` (파티션 키 포함)
- UNIQUE: `(stock_id, trading_date)` (`uq_stock_price_stock_date`)
- 컬럼: close_price, open_price, high_price, low_price (BigInteger), volume (default 0), market_cap, change_rate (Numeric(10,4))

**short_selling** (`models/short_selling.py`) — 일별 공매도, 월별 파티션
- UNIQUE: `(stock_id, trading_date)`
- 컬럼: short_volume, short_amount (BigInteger, default 0), short_ratio (Numeric(10,4))

**lending_balance** (`models/lending_balance.py`) — 일별 대차잔고, 월별 파티션
- UNIQUE: `(stock_id, trading_date)`
- 컬럼: balance_quantity, balance_amount, change_rate, change_quantity, **consecutive_decrease_days** (전일 대비 음의 변동이 연속된 일수 — `RAPID_DECLINE` 점수 보강에 사용)

#### 3.2.2 분석 (Phase 2)

**signal** (`models/signal.py`)
- UNIQUE: `(stock_id, signal_date, signal_type)` (`uq_signal_stock_date_type`) — 하루에 같은 (종목, 타입) 시그널 중복 방지
- FK: `stock_id → stock.id`
- 컬럼: signal_type (VARCHAR(30)), score (Integer), grade (VARCHAR(1)), detail (JSONB), return_5d/10d/20d (Numeric(10,4) — 백테스트가 채움)

**backtest_result** (`models/backtest_result.py`)
- 누적 append 방식 (UNIQUE 없음). 조회는 `period_end DESC LIMIT 1`
- 컬럼: signal_type, period_start/end, total_signals, hit_count_{5,10,20}d, hit_rate_{5,10,20}d, avg_return_{5,10,20}d

#### 3.2.3 알림 설정

**notification_preference** (`models/notification_preference.py`)
- **싱글톤** (id=1, autoincrement=False)
- 클래스 상수: `SINGLETON_ID=1`, `DEFAULT_MIN_SCORE=60`, `DEFAULT_SIGNAL_TYPES=["RAPID_DECLINE","TREND_REVERSAL","SHORT_SQUEEZE"]`
- 토글 컬럼 4개: daily_summary_enabled, urgent_alert_enabled, batch_failure_enabled, weekly_report_enabled (default true)
- min_score (default 60), signal_types (JSONB array)

#### 3.2.4 포트폴리오 (P10)

**brokerage_account** (`models/portfolio.py`)
- account_alias (VARCHAR(50), UNIQUE)
- broker_code: `manual | kis | kiwoom`
- connection_type: `manual | kis_rest_mock | kis_rest_real`
- environment: `mock | real`
- 검증: `RegisterAccountUseCase.execute` 가 `kis_rest_real ↔ environment='real'` 강제 1:1 매핑

**portfolio_holding**
- UNIQUE: `(account_id, stock_id)`
- CHECK: `quantity >= 0`, `avg_buy_price >= 0`
- FK: `account_id → brokerage_account.id ON DELETE CASCADE`
- 컬럼: quantity (Integer), avg_buy_price (Numeric(15,2)), first_bought_at, last_transacted_at

**portfolio_transaction**
- CHECK: `quantity > 0`, `price >= 0`
- transaction_type: `BUY | SELL`
- source: `manual | kis_sync | excel_import` (Migration 006 에서 'excel_import' 추가)

**portfolio_snapshot**
- UNIQUE: `(account_id, snapshot_date)`
- 컬럼: total_value, total_cost, unrealized_pnl, realized_pnl, holdings_count

**brokerage_account_credential** (P15, Migration 008)
- UNIQUE: `account_id` (계좌당 1 레코드)
- FK: `account_id → brokerage_account.id ON DELETE CASCADE`
- 컬럼: app_key_cipher, app_secret_cipher, account_no_cipher (모두 LargeBinary), key_version (default 1)
- **plaintext 절대 저장하지 않음** — Fernet 암호화 후 BYTEA 로 저장

#### 3.2.5 AI 리포트 (P13)

**dart_corp_mapping** (Migration 004)
- PK: `stock_code` (VARCHAR(6))
- corp_code (VARCHAR(8), UNIQUE), corp_name

**analysis_report** (Migration 005)
- UNIQUE: `(stock_code, report_date)` — KST 일자 단위 캐시
- 컬럼: provider (VARCHAR(30)), model_id (VARCHAR(60)), content (JSONB), sources (JSONB array, default `[]`), token_in/out, elapsed_ms

### 3.3 ER 관계 요약

```
stock 1 ──< stock_price (월별 파티션)
       1 ──< short_selling (월별 파티션)
       1 ──< lending_balance (월별 파티션)
       1 ──< signal ──< (return_5d/10d/20d 채워짐)
       1 ──< portfolio_holding (FK)
       1 ──< portfolio_transaction (FK)

brokerage_account 1 ──< portfolio_holding (CASCADE)
                  1 ──< portfolio_transaction (CASCADE)
                  1 ──< portfolio_snapshot (CASCADE)
                  1 ── 1 brokerage_account_credential (CASCADE)

signal_type ──< backtest_result (집계 — FK 없음)

dart_corp_mapping (stock_code 매핑) ↔ analysis_report (stock_code 캐시)
```

### 3.4 Repository 패턴

13개 Repository (`adapter/out/persistence/repositories/__init__.py`) — 모두 async, `AsyncSession` 주입.

| Repository | 주요 메서드 |
|------------|-------------|
| `StockRepository` | `find_by_code`, `list_by_ids`, `list_active`, `upsert_by_code` |
| `StockPriceRepository` | `list_between`, `list_by_trading_date`, `list_by_stocks_between`, `upsert_many` |
| `ShortSellingRepository` | 동일 패턴 |
| `LendingBalanceRepository` | 동일 패턴 + `list_by_stocks_between` |
| `SignalRepository` | `list_by_date`, `list_by_stock`, `list_between`, `list_by_stocks_between(min_score=)`, `find_latest_signal_date`, `add_many` |
| `BacktestResultRepository` | `add_many` |
| `NotificationPreferenceRepository` | `get_or_create`, `save` (싱글톤 보장) |
| `BrokerageAccountRepository` | `get`, `find_by_alias`, `list_active`, `add` |
| `PortfolioHoldingRepository` | `find_by_account_and_stock`, `list_by_account(only_active=)`, `upsert` |
| `PortfolioTransactionRepository` | `add`, `list_by_account(limit=)` |
| `PortfolioSnapshotRepository` | `upsert`, `list_between` |
| `BrokerageAccountCredentialRepository` | `upsert` (3 필드 각각 암호화), `get_decrypted`, `get_masked_view`, `find_row`, `delete` |
| `AnalysisReportRepository` | `find_by_cache_key`, `save` |
| `DartCorpMappingRepository` | `find_by_stock_code`, `bulk_upsert` |

---

## 4. REST API 카탈로그

### 4.1 진입점 + 메타

| Method | Path | 설명 | 가시성 |
|--------|------|------|--------|
| GET | `/health` | 상태 코드만 (`{"status":"UP"}`) | public |
| GET | `/internal/info` | env·app 명 (`include_in_schema=False`) | 내부 |
| GET | `/metrics` | Prometheus 메트릭 (`include_in_schema=False`) | 내부 |
| GET | `/docs` | Swagger UI | public (운영은 Caddy 차단) |

`/health` 는 외부 노출용, `/internal/info` 와 `/metrics` 는 Caddy/리버스프록시에서 외부 차단 (운영 가정).

### 4.2 인증 모델

- **관리자 API Key**: `X-API-Key` 헤더 + `Settings.admin_api_key` 비교
  - `_deps.require_admin_key` 가 `hmac.compare_digest` 로 timing-safe 비교 (`_deps.py:113-127`)
  - 키 미설정 시 모든 요청 401 (fail-closed)
- **카카오 OAuth**: 프론트가 처리 (현재 백엔드에는 없음 — `CLAUDE.md` 명시 영역)
- **Rate Limit**: slowapi `@limiter.limit("30/minute")` — `_admin_key_or_ip` 가 `apikey:<value>` 우선, 없으면 `ip:<addr>` (현재는 `/api/reports/{stock_code}` 만 적용)

### 4.3 라우터별 엔드포인트

#### 4.3.1 `/api/signals` (`routers/signals.py`)

| Method | Path | 인증 | 쿼리/바디 | 응답 |
|--------|------|------|-----------|------|
| GET | `/api/signals` | public | `date`, `type`, `limit=500` (1~5000) | `list[SignalResponse]` |
| GET | `/api/signals/latest` | public | `type`, `limit=500` | `LatestSignalsResponse` (signal_date null 가능) |
| GET | `/api/stocks/{stock_code}` | public | `^\d{6}$`, `from`, `to` (기본 92일) | `StockDetailResponse` (stock + prices + signals) |
| POST | `/api/signals/detect` | admin | `date` (≤ today) | `DetectionResult` |

#### 4.3.2 `/api/backtest` (`routers/backtest.py`)

| Method | Path | 인증 | 쿼리/바디 | 응답 |
|--------|------|------|-----------|------|
| GET | `/api/backtest` | public | — | `list[BacktestResultResponse]` (SignalType 별 최신 1건) |
| POST | `/api/backtest/run` | admin | `from`, `to` (기본 직전 3년, 최대 3년) | `BacktestExecutionResult` |

#### 4.3.3 `/api/batch` (`routers/batch.py`)

| Method | Path | 인증 | 쿼리/바디 | 응답 |
|--------|------|------|-----------|------|
| POST | `/api/batch/collect` | admin | `date` (≤ today) | `CollectionResult` |

#### 4.3.4 `/api/notifications` (`routers/notifications.py`)

| Method | Path | 인증 | 바디 | 응답 |
|--------|------|------|------|------|
| GET | `/api/notifications/preferences` | public | — | `NotificationPreferenceResponse` |
| PUT | `/api/notifications/preferences` | admin | `NotificationPreferenceUpdateRequest` | `NotificationPreferenceResponse` |

#### 4.3.5 `/api/portfolio` (`routers/portfolio.py`) — **전 엔드포인트 admin**

| Method | Path | 바디/쿼리 | 응답 |
|--------|------|-----------|------|
| POST | `/accounts` | `AccountCreateRequest` | 201 `AccountResponse` |
| GET | `/accounts` | — | `list[AccountResponse]` |
| POST | `/accounts/{id}/transactions` | `TransactionCreateRequest` | 201 `TransactionResponse` |
| GET | `/accounts/{id}/holdings` | — | `list[HoldingResponse]` |
| GET | `/accounts/{id}/transactions` | `limit=100` (max 500) | `list[TransactionResponse]` |
| POST | `/accounts/{id}/snapshot` | `asof` | `SnapshotResponse` |
| GET | `/accounts/{id}/snapshots` | `start`, `end` (기본 3개월) | `list[SnapshotResponse]` |
| GET | `/accounts/{id}/performance` | `start`, `end` (기본 3개월) | `PerformanceResponse` (return·MDD·Sharpe) |
| POST | `/accounts/{id}/sync` | — | `SyncResponse` (mock/real 자동 분기) |
| POST | `/accounts/{id}/test-connection` | — | `TestConnectionResponse` (real 전용 dry-run) |
| GET | `/accounts/{id}/signal-alignment` | `since`, `until`, `min_score=60` | `SignalAlignmentResponse` |
| POST | `/accounts/{id}/import/excel` | `file: UploadFile` (.xlsx, ≤10MB) | `ExcelImportResponse` |
| POST | `/accounts/{id}/credentials` | `BrokerageCredentialRequest` | 201 `BrokerageCredentialResponse` |
| PUT | `/accounts/{id}/credentials` | `BrokerageCredentialRequest` | `BrokerageCredentialResponse` |
| GET | `/accounts/{id}/credentials` | — | `BrokerageCredentialResponse` (마스킹) |
| DELETE | `/accounts/{id}/credentials` | — | 204 |

#### 4.3.6 `/api/reports` (`routers/reports.py`) — admin + rate-limited

| Method | Path | 쿼리 | 응답 |
|--------|------|------|------|
| POST | `/api/reports/{stock_code}` (`30/minute`) | `force_refresh=False` | `AnalysisReportResponse` |

### 4.4 응답 스키마 핵심 (`_schemas.py`)

- `_Base(model_config=ConfigDict(from_attributes=True))` — ORM 모델 직접 변환 지원 (Pydantic v2 `model_validate(obj)`)
- 도메인별 그룹: Signals / Backtest / NotificationPreference / Portfolio (P10) / Brokerage Credential (P15) / Signal Alignment / AI Report
- 검증 패턴 예시:
  - `stock_code: ^\d{6}$` (Path 검증)
  - `KisAccountNo: ^\d{8}-\d{2}$` (CANO + ACNT_PRDT_CD)
  - `KisAppKey: ^\S+$` (16~128자, 공백 불가)
  - `transaction_type: ^(BUY|SELL)$`
  - `connection_type: ^(manual|kis_rest_mock|kis_rest_real)$`
  - `min_score: 0~100 (Annotated[int, Field(ge=0, le=100)])`

### 4.5 예외 → HTTP 매핑 (`_error_handler.py` + `routers/portfolio.py:_credential_error_to_http`)

| 도메인 예외 | HTTP |
|-------------|------|
| `RequestValidationError` (Pydantic) | 400 + `{status, message, timestamp}` |
| `StockNotFoundError`, `AccountNotFoundError`, `CredentialNotFoundError` | 404 |
| `AccountAliasConflictError`, `CredentialAlreadyExistsError`, `InsufficientHoldingError` | 409 |
| `InvalidRealEnvironmentError` | 403 |
| `UnsupportedConnectionError`, `CredentialRejectedError` (KIS 401/403) | 400 |
| `UnsupportedExcelFormatError` | 422 |
| `TooManyRowsError` | 413 |
| `SyncError` (KIS 업스트림 5xx/네트워크) | 502 |
| `AnalysisReportError` (LLM/DART 실패) | 502 |
| `CredentialCipherError` (Fernet 복호화 실패) | 500 (로그에는 예외 타입만, 사용자에는 일반 메시지) |
| `RateLimitExceeded` | 429 + `Retry-After: 60` |

---

## 5. 외부 연동

### 5.1 KRX (`adapter/out/external/krx_client.py`)

- **라이브러리**: `pykrx` (data.krx.co.kr 회원 ID/PW 인증) — 2026-04 익명 차단 이후 **KRX_ID/KRX_PW 환경변수 필수**
- **rate limit**: `asyncio.Lock` + `_throttle()` 로 호출 간격 ≥ `krx_request_interval_seconds=2.0` 강제
- **stdout 차폐**: pykrx 가 `print` 로 ID 를 흘리는 이슈 → `contextlib.redirect_stdout/stderr` 로 버퍼 가둠
- **재시도**: `tenacity @retry` (3회, exp 2~10s, ConnectionError/TimeoutError/OSError 만)
- **API**:
  - `fetch_stock_prices(date)` → `list[StockPriceRow]` (ohlcv + market_cap + 시장구분 매핑)
  - `fetch_short_selling(date)` → `list[ShortSellingRow]`
  - `fetch_lending_balance(date)` → `list[LendingBalanceRow]` (스키마 불일치 시 빈 리스트 + 경고)
  - `build_stock_name_map(date_str)` → 티커 → 종목명 dict (이름 없으면 Repository 가 기존값 보존)
- **알려진 이슈**: KRX 익명 차단 — 자격증명 미설정 시 모든 데이터 0 rows. 프로덕션 Java 배치는 현재 무력화 (메모리 참조).

### 5.2 KIS (`adapter/out/external/kis_client.py`)

- **2환경**:
  - MOCK: `https://openapivts.koreainvestment.com:29443`, TR_ID `VTTC8434R`
  - REAL: `https://openapi.koreainvestment.com:9443`, TR_ID `TTTC8434R`
- **base_url 은 환경 상수 직접 고정** — Settings 에서 mock 으로 위장한 실 URL 주입 차단
- **REAL 환경 보호**: `credentials=None` 으로 REAL 생성 시 즉시 `KisNotConfiguredError` (PR 3 이후 DB 자격증명 저장소와 연결)
- **OAuth2**: 토큰 24h TTL, 인스턴스 캐시 + 만료 5분 전 자동 재발급 (`_TOKEN_RENEW_MARGIN_SECONDS=300.0`)
- **In-memory mock**: `kis_use_in_memory_mock=True` 시 `_build_in_memory_transport()` 활성 → `httpx.MockTransport` 가 토큰 + 결정론 잔고 3건 반환 (E2E/CI 안정성용, 외부 호출 0)
- **에러 분리**:
  - HTTP 401/403 → `KisCredentialRejectedError` (사용자 재등록 필요 → 라우터 400)
  - 그 외 5xx/네트워크/파싱 → `KisUpstreamError` (라우터 502)
  - 응답 본문은 DEBUG 로그 only — `[MASKED_JWT]`/`[MASKED_HEX]` 자동 스크럽
- **API**:
  - `test_connection()`: 토큰 발급만 시도 (재시도 없음 — "빠른 1회 검증" 의미)
  - `fetch_balance()`: `output1` → `list[KisHoldingRow]` (qty>0 만 통과)

### 5.3 DART (`adapter/out/external/dart_client.py`)

- **API Key**: `dart_api_key` (무료 발급, 일 10,000 호출)
- **응답 규약**: HTTP 200 + `{"status": "000"}` 정상, `"013"` = 데이터 없음 (빈 반환), 그 외 `DartUpstreamError`
- **재시도**: `tenacity @retry(httpx.HTTPError, 3회, exp 1~8s)`
- **엔드포인트**:
  - `fetch_company(corp_code)` → `DartCompanyInfo | None` (`/company.json`)
  - `fetch_disclosures(corp_code, bgn_de, end_de, page_no=1, page_count≤100)` → `list[DartDisclosure]` (`/list.json`)
    - `dart_viewer_url`: `https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}` (property)
  - `fetch_financial_summary(corp_code, bsns_year, reprt_code='11011', fs_div='CFS')` → `DartFinancialStatement` (`/fnlttSinglAcntAll.json`)
    - reprt_code: `11011`(사업), `11012`(반기), `11013`(1Q), `11014`(3Q)
    - fs_div: `CFS`(연결) / `OFS`(별도)
  - `fetch_corp_code_zip()` → `bytes` (`PK\x03\x04` 매직 검증, read timeout 60s) — 전체 기업 corp_code 매핑 ZIP
- **금액 파싱**: 천단위 콤마 / `(123)` 음수 / `-`/`--` → None / `_to_decimal` 헬퍼

### 5.4 Telegram (`adapter/out/external/telegram_client.py`)

- **No-op 모드**: `bot_token` 또는 `chat_id` 둘 중 하나라도 비면 `enabled=False` → 모든 호출 silent skip
- **메시지 포맷**: HTML parse_mode 기본, 사용자 데이터(종목명) 는 `html.escape(quote=False)` 로 인젝션 차단 (`notification_service.py:65`)
- **실패 정책**: `httpx.HTTPError` → 경고 로그 + `False` 반환 (UseCase 비차단)

### 5.5 OpenAI (`adapter/out/ai/openai_provider.py`)

- **Plan B (현재)**: `/v1/chat/completions` 직접 호출 (openai SDK 미의존 — MockTransport 주입 용이)
- **strict JSON**: `response_format={"type": "json_schema", "json_schema": REPORT_JSON_SCHEMA}` (`llm_provider.py:161-210`)
- **3-Tier 라우팅 (설계)**:
  - flagship: `gpt-4o` (분석 본체, `analyze`)
  - collector: `gpt-4o-mini` (Tier2 web_search — 현재 미구현, 빈 리스트 반환)
  - nano: `gpt-4o-mini` (프론트 카드 리패키징 — 현재 passthrough)
- **SSRF 방어**: `_validate_base_url` — `https` 스킴 + 유효 hostname 강제 (메타데이터 IP 169.254.169.254 등 차단)
- **프롬프트 인젝션 완화**:
  - 시스템 프롬프트가 "유일한 지시원" 명시
  - Tier1/Tier2 데이터를 `<tier1_data>...</tier1_data>` XML-like fence 안에 격납
  - `_sanitize_fenced` 가 닫는 태그 충돌(`</tier1_data>` → `</tier1_data_literal>`) 방지
- **URL 안전 필터**: `_safe_sources` + `is_safe_public_url` 가 `http/https` 스킴만 통과 (`javascript:`/`file:`/사설 IP 차단)
- **계층화**: `LLMProvider` Protocol → 추후 `PerplexityProvider`/`ClaudeProvider` 로 Plan A 전환 가능

### 5.6 외부 호출 공통 패턴

- 모두 `httpx.AsyncClient` + `tenacity` 재시도
- `transport=httpx.MockTransport(...)` 주입으로 테스트 격리 (CI 외부 호출 0 보장)
- `__aenter__/__aexit__` 지원 — 요청 스코프 사용
- `close()` 메서드 보유 — Depends yield 스코프에서 `finally:` 정리

---

## 6. 배치 (APScheduler)

### 6.1 스케줄러 구성 (`batch/scheduler.py`)

- **타임존**: `KST = ZoneInfo("Asia/Seoul")` 명시 (프로세스 TZ 가 UTC 여도 하루 밀림 방지)
- **활성화**: `scheduler_enabled=False` 기본 (테스트/개발). 운영만 True

| Job ID | Trigger | 콜백 |
|--------|---------|------|
| `market_data_pipeline` | `CronTrigger(day_of_week='mon-fri', hour=06, minute=00, tz=KST)` | `_fire_pipeline` |
| `backtest_pipeline` | `CronTrigger(day_of_week='mon', hour=07, minute=00, tz=KST)` | `fire_backtest_pipeline` (`backtest_enabled=True` 일 때만) |

- 옵션: `replace_existing=True`, `max_instances=1`, `coalesce=True` (중복 실행 방지)

### 6.2 `market_data_pipeline` — 3-Step (`batch/market_data_job.py`)

```
trading_day check (월-금) ─→ Step 1 collect ─→ Step 2 detect ─→ Step 3 notify
                              (KrxClient)      (Signal*)        (Telegram)
```

- **Step 격리**: 각 Step 별 독립 세션 (`async with factory() as session`) + try/commit/except/rollback
- **Step 3 조건부**: `detect` 성공 시만 `notify` 실행. detect 실패 시 notify 는 `succeeded=False, error="detect step 실패로 notify 생략"` 로 마킹
- **결과 모델**: `PipelineResult(trading_date, skipped, steps[], total_elapsed_ms)` — Pydantic frozen
- **거래일 판정**: `is_trading_day(d)` = `d.weekday() < 5` (공휴일은 KRX 빈 응답으로 자연 폴백)
- **수동 실행 옵션**: `force_when_non_trading=True` 로 주말 실행 가능
- **요약 메트릭**:
  - collect: `{stocks, prices, short, lending}`
  - detect: `{rapid, trend, squeeze}`
  - notify: `{sent}`

### 6.3 `backtest_pipeline` — 단일 Step (`batch/backtest_job.py`)

- 기본: 직전 3년 (`backtest_period_years=3`) 재계산
- `period_end = period_end ?? today`, `period_start = end - relativedelta(years=N)`
- `BacktestEngineService.execute(start, end)` → `backtest_result` 에 SignalType 별 row append (UNIQUE 없음)
- 단일 세션, `session.flush()` 후 wrapper 가 `commit()`
- 실패 시 rollback + `BacktestPipelineResult(error=...)` 반환 (스케줄러 루프 보호)

### 6.4 시그널 탐지 알고리즘 (`signal_detection_service.py`)

| 시그널 | 트리거 | 점수 | 임계값 |
|--------|--------|------|--------|
| RAPID_DECLINE | 대차잔고 `change_rate ≤ -12%` | `min(100, base + consec + 10)` (`base = min(60, abs*2.5)`, `consec = min(20, days*5)`) | 통과 시 무조건 저장 |
| TREND_REVERSAL | 5MA vs 20MA 데드크로스 (`yesterday short ≥ long AND today short < long`) | `min(100, divergence_score(40) + speed_score(30) + 30)` | `≥ 50` |
| SHORT_SQUEEZE | 부분 점수 합 (balance 30 + volume 25 + price 25 + short_ratio 20) | sum | `≥ 60` |

- **history**: TREND_REVERSAL 은 30일 (`TREND_HISTORY_DAYS=30`), SHORT_SQUEEZE 볼륨 평균은 30일
- **중복 방지**: `(stock_id, signal_type)` UNIQUE — `existing_keys` set 으로 in-memory 1차 방어
- **detail 필드**: JSONB — Java 호환 위해 camelCase (`balanceChangeRate`, `crossType`, `volumeChangeRate` 등)

### 6.5 백테스트 엔진 (`backtest_service.py`)

벡터 연산 기반 (Java 의 TreeMap 순회 → pandas pivot 으로 재작성):

1. **price_panel**: `(stock_id, trading_date) → close_price` 와이드 피벗 테이블
2. **수익률 행렬**: `pct_change` 대신 `(price_wide.shift(-N) / price_base - 1) * 100` — N=5/10/20 한 번에 계산
3. **벡터 lookup**: `rdf.at[signal_date, stock_id]` 으로 시그널 발생일 × 종목 교차점 추출
4. **NaN/inf 처리**:
   - `price_base = price_wide.where(price_wide > 0)` — 분모만 마스킹 (분자 0 → -100% 유효)
   - `np.isfinite` 로 inf 제거 — 단일 inf 가 평균을 `Decimal('Infinity')` 로 만드는 INSERT 실패 방지
5. **집계**: SignalType 별 `total_signals`, `hit_count`/`hit_rate`/`avg_return` (5/10/20d)

### 6.6 스크립트 (`scripts/`)

| 스크립트 | 용도 |
|----------|------|
| `entrypoint.py` | 컨테이너 진입점 — Alembic 마이그레이션 + Uvicorn 기동 |
| `backfill_signal_detection.py` | 과거 구간 시그널 일괄 탐지 |
| `backfill_stock_prices.py` | 과거 OHLCV 백필 |
| `fix_stock_names.py` | 종목명 결측 보정 |
| `seed_ui_demo.py` | UI 데모용 seed 데이터 |
| `seed_e2e_accounts.py` | E2E 테스트 계좌 seed |
| `seed_backtest_e2e.py` | E2E 백테스트 시드 |
| `sync_dart_corp_mapping.py` | DART corpCode ZIP → DB 일괄 동기화 |
| `run_backtest.py` | one-shot 백테스트 (스케줄러 우회) |

---

## 7. 보안·인증·관측

### 7.1 자격증명 암호화 (`security/credential_cipher.py`)

- **알고리즘**: Fernet (AES-128-CBC + HMAC-SHA256) — `cryptography` 라이브러리
- **마스터키**: `Settings.kis_credential_master_key` (env 주입) — 빈 값이면 `MasterKeyNotConfiguredError` 로 즉시 기동 차단
- **키 회전 대비**: `_fernets: dict[int, Fernet]` 으로 다중 버전 관리 (`encrypt` 는 항상 `current_version`, `decrypt` 는 row 의 `key_version` 사용)
- **예외 계층**:
  - `CredentialCipherError` (최상위)
  - `MasterKeyNotConfiguredError` (기동 차단)
  - `UnknownKeyVersionError` (회전 후 구버전 키 미보존)
  - `DecryptionFailedError` (`InvalidToken` 래핑 — 메시지에 plaintext/cipher 포함하지 않음)
- **저장 흐름**: `KisCredentials(app_key, app_secret, account_no)` → 3 필드 각각 `cipher.encrypt()` → BYTEA 컬럼
- **마스킹 뷰**: `_mask_tail(value, keep=4)` — `<bullet × (len-keep)><last 4>` 비례 마스킹
  - `app_secret` 은 어떤 경로로도 plaintext 노출되지 않음 (조회 메서드 자체가 없음)

### 7.2 관리자 키 검증 (`adapter/web/_deps.py:113`)

```python
expected = settings.admin_api_key
if not expected:
    raise HTTPException(401, "Admin API key 미설정")  # fail-closed
provided = x_api_key or ""
if not hmac.compare_digest(expected.encode(), provided.encode()):
    raise HTTPException(401, "Invalid API key")
```

- timing-safe 비교 + 길이 차이도 leak 안 함
- `Settings.admin_api_key` 권장 길이: 32+ 바이트

### 7.3 Rate Limiting (`adapter/web/_rate_limit.py`)

- **싱글톤**: `Limiter(key_func=_admin_key_or_ip)`
- **key_func 우선순위**: `X-API-Key` 헤더 → `apikey:<value>` / 없으면 `ip:<remote_addr>` (defense-in-depth)
- **현재 적용**: `/api/reports/{stock_code}` (POST) — `30/minute` 기본값
- **초과 시**: `RateLimitExceeded` → 429 + `Retry-After: 60` 헤더

### 7.4 CORS (`main.py:62-72`)

- 화이트리스트 방식 — `Settings.cors_allow_origins` 가 비면 미들웨어 미장착 (모든 출처 거부)
- `"*"` 와일드카드 명시 거부 (credentials 와 함께 사용 불가)
- 허용 메서드: GET/POST/PUT/PATCH/DELETE/OPTIONS
- 허용 헤더: Authorization, Content-Type, X-Admin-Api-Key, X-API-Key
- `max_age=600`

### 7.5 입력 검증

- **Pydantic v2** 모든 요청 스키마 (`adapter/web/_schemas.py`)
- **정규식 패턴**:
  - stock_code: `^\d{6}$`
  - KIS 계좌번호: `^\d{8}-\d{2}$`
  - 매수/매도: `^(BUY|SELL)$`
- **숫자 범위**: `Annotated[int, Field(ge=0, le=100)]`, `Field(gt=0)`, etc.
- **파일 업로드 (Excel)**:
  - 확장자 `.xlsx` 만 허용 → 415
  - 크기 ≤ 10MB → 413
  - 행 수 ≤ 10,000 → 413 (`TooManyRowsError`)

### 7.6 SSRF 방어

- `is_safe_public_url(url)` (`llm_provider.py:216`) — `http/https` 스킴 + 유효 hostname 만 통과
  - 적용: AnalysisReportService.\_merge_tier1_sources, OpenAIProvider.\_safe_sources
- `OpenAIProvider._validate_base_url` — `openai_base_url` 은 반드시 `https` 스킴

### 7.7 로깅 (`observability/logging.py`)

structlog + 민감 데이터 자동 마스킹 (PR 6 / KIS sync 시리즈):

- **2층 방어**:
  1. **키 기반 치환**: dict/kwargs 키가 `SENSITIVE_KEYS` (완전일치) 또는 `SENSITIVE_KEY_SUFFIXES` (접미일치) → 값 `[MASKED]`
  2. **정규식 scrub**:
     - JWT: `\beyJ[A-Za-z0-9_-]{10,}\.[...]\.[...]\b` → `[MASKED_JWT]`
     - 40+ hex: `\b[0-9a-fA-F]{40,}\b` → `[MASKED_HEX]`
- **민감 키 (예시)**: `app_key`, `app_secret`, `access_token`, `authorization`, `x-api-key`, `openai_api_key`, `dart_api_key`, `telegram_bot_token`, `krx_pw`, `kis_credential_master_key`, `kis_app_key_mock`...
- **접미 패턴**: `_api_key`, `_app_secret`, `_access_token`, `_bot_token`, `_master_key`, `_pw` ... — 신규 env 추가 시 동기화 불필요
- **stdlib 통합**: `ProcessorFormatter.foreign_pre_chain` — 기존 `logging.getLogger(__name__).info(...)` 호출도 동일 chain 경유
- **렌더러 분기**: `app_env == "local"` → `ConsoleRenderer` / 그 외 → `JSONRenderer`
- **idempotent**: `_configured` guard — `setup_logging` 다중 호출 무해 (테스트는 `reset_logging_for_tests`)

### 7.8 메트릭

- **Prometheus**: `prometheus-fastapi-instrumentator` — `/metrics` 엔드포인트 (`include_in_schema=False`)
- 자동 수집: HTTP 요청 수, 지연, 상태코드 분포

### 7.9 예외 핸들러 (`adapter/web/_error_handler.py`)

```python
@app.exception_handler(RequestValidationError)
async def _validation(request, exc) -> JSONResponse:
    # errors[0].loc + msg → "field.path: 메시지"
    return JSONResponse(400, {status, message, timestamp})

@app.exception_handler(ValidationError)  # Pydantic 도메인 검증
async def _pyd_validation(request, exc) -> JSONResponse:
    return JSONResponse(400, {status, message, timestamp})
```

### 7.10 보안 결정 요약

| 항목 | 정책 |
|------|------|
| 관리자 키 비교 | `hmac.compare_digest` (timing-safe) |
| KIS 자격증명 저장 | Fernet AES-128-CBC + HMAC, key_version 관리 |
| `app_secret` 노출 | 모든 경로에서 금지 — GET 응답에도 없음 |
| JWT/hex 로그 노출 | 정규식 자동 scrub |
| URL 스킴 검증 | http/https + 유효 hostname (LLM 응답·DART hm_url) |
| OpenAI base_url | https 강제 (SSRF) |
| KIS REAL URL 위장 | base_url 환경 상수 직접 고정 (Settings 우회 차단) |
| CORS | 화이트리스트만, `*` 거부 |
| 파일 업로드 | 확장자 + 크기 + 행 수 다중 검증 |
| Excel parser | openpyxl read_only (zip bomb 완화) |
| Telegram 메시지 | `html.escape` 인젝션 방어 |
| Forwarded headers | Docker 사설 대역만 신뢰 (entrypoint) |

---

## 8. 마이그레이션·배포

### 8.1 Alembic 구성 (`alembic.ini` + `migrations/env.py`)

- **드라이버 분리**:
  - 마이그레이션: 동기 `psycopg2` — asyncpg 가 다중 statement (`DO $$ ... $$; CREATE TABLE`) 미지원 회피
  - 런타임: async `asyncpg`
- **URL 치환**: `env.py._resolve_sync_url()` 가 `+asyncpg` → `+psycopg2` 로 자동 변환
- **메타데이터**: `from app.adapter.out.persistence.models import *` — Alembic autogenerate 가 모든 모델 인식

### 8.2 마이그레이션 히스토리

| Revision | 설명 | down_revision |
|----------|------|---------------|
| `001_init_schema` | V1 초기 (Java Flyway V1 동등) — stock, stock_price, short_selling, lending_balance, signal, backtest_result | None |
| `002_notification_preference` | V2 알림 설정 테이블 (Java Flyway V2 동등) | 001 |
| `003_portfolio_schema` | P10 포트폴리오 4 테이블 (account/holding/transaction/snapshot) | 002 |
| `004_dart_corp_mapping` | P13a DART 기업코드 매핑 | 003 |
| `005_analysis_report` | P13b AI 분석 리포트 | 004 |
| `006_portfolio_excel_source` | `portfolio_transaction.source` CHECK 에 `'excel_import'` 추가 | 005 |
| `007_kis_real_connection` | `brokerage_account.connection_type` 에 `'kis_rest_real'` 추가 | 006 |
| `008_brokerage_credential` | `brokerage_account_credential` (Fernet 암호화 BYTEA) | 007 |

### 8.3 컨테이너 진입점 (`scripts/entrypoint.py`)

레거시 Java Flyway 스키마와의 호환 처리:

```
alembic_version 없음 AND stock 존재
  → alembic stamp 002_notification_preference (V1+V2 완료 마킹)
  → alembic upgrade head (003+ 적용)
그 외 (신규 DB 또는 이미 tracked)
  → alembic upgrade head
```

이후 Uvicorn 기동:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --proxy-headers \
  --forwarded-allow-ips "127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
```

`FORWARDED_ALLOW_IPS` env 로 오버라이드 가능 (Kubernetes 등 다른 런타임 대응).

### 8.4 Dockerfile (Multi-stage)

```
builder (python:3.12-slim)
  - uv 0.11 (digest pinning ghcr.io/astral-sh/uv:0.11@sha256:240fb85a...)
  - uv sync --frozen --no-dev (캐시 활용 — pyproject + uv.lock 만 먼저 복사)
  - app/, alembic.ini, migrations/, scripts/ 복사 후 재 sync

runtime (python:3.12-slim)
  - useradd appuser (uid 1001, shell=/usr/sbin/nologin) — 인터랙티브 셸 차단
  - PATH=/app/.venv/bin
  - HEALTHCHECK: GET http://127.0.0.1:8000/health (interval 30s, timeout 5s, start_period 60s)
  - CMD: python scripts/entrypoint.py
```

### 8.5 환경 변수 (`config/settings.py`)

- **소스 우선순위**: 환경변수 → `.env` → `.env.prod`
- **case-insensitive**, `extra="ignore"`

| 카테고리 | 변수 | 기본값 / 비고 |
|----------|------|----------------|
| 앱 | `APP_NAME` | `ted-signal-backend` |
| 앱 | `APP_ENV` | `local` (`local`/`dev`/`prod`) |
| 앱 | `PORT` | `8000` |
| 앱 | `LOG_LEVEL` | `INFO` (Literal) |
| CORS | `CORS_ALLOW_ORIGINS` | `[]` |
| DB | `DATABASE_URL` | `postgresql+asyncpg://signal:signal@localhost:5432/signal_db` |
| DB | `DATABASE_ECHO` / `DATABASE_POOL_SIZE` / `DATABASE_MAX_OVERFLOW` | `False` / `5` / `10` |
| KRX | `KRX_ID` / `KRX_PW` | 빈 값 시 인증 필요 엔드포인트 실패 |
| KRX | `KRX_REQUEST_INTERVAL_SECONDS` | `2.0` |
| Telegram | `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | 둘 중 하나 비면 no-op |
| Admin | `ADMIN_API_KEY` | 빈 값 시 모든 admin 요청 401 (fail-closed) |
| Rate Limit | `AI_REPORT_RATE_LIMIT` | `30/minute` |
| Scheduler | `SCHEDULER_ENABLED` | `False` (운영만 True) |
| Scheduler | `SCHEDULER_HOUR_KST` / `SCHEDULER_MINUTE_KST` | `6` / `0` |
| Backtest | `BACKTEST_ENABLED` | `True` (scheduler_enabled=True 일 때만 의미) |
| Backtest | `BACKTEST_CRON_DAY_OF_WEEK` / `_HOUR_KST` / `_MINUTE_KST` / `_PERIOD_YEARS` | `mon` / `7` / `0` / `3` |
| OpenAI | `OPENAI_BASE_URL` / `OPENAI_API_KEY` | `https://api.openai.com/v1` / `""` |
| OpenAI | `OPENAI_MODEL_FLAGSHIP` / `_COLLECTOR` / `_NANO` | `gpt-4o` / `gpt-4o-mini` / `gpt-4o-mini` |
| OpenAI | `OPENAI_REQUEST_TIMEOUT_SECONDS` | `60.0` |
| AI Report | `AI_REPORT_PROVIDER` / `_CACHE_HOURS` / `_WEB_SEARCH_ENABLED` | `openai` / `24` / `False` |
| DART | `DART_BASE_URL` / `DART_API_KEY` / `DART_REQUEST_TIMEOUT_SECONDS` | `https://opendart.fss.or.kr/api` / `""` / `15.0` |
| KIS | `KIS_BASE_URL_MOCK` / `KIS_APP_KEY_MOCK` / `KIS_APP_SECRET_MOCK` / `KIS_ACCOUNT_NO_MOCK` | mock 만 Settings 보유 (real 은 DB) |
| KIS | `KIS_REQUEST_TIMEOUT_SECONDS` | `15.0` |
| KIS | `KIS_USE_IN_MEMORY_MOCK` | `False` (운영 절대 True 금지) |
| KIS | `KIS_CREDENTIAL_MASTER_KEY` | Fernet `generate_key()` 출력 (32B base64) — 빈 값 시 기동 차단 |

### 8.6 로컬 개발

```bash
cd src/backend_py
uv sync --extra dev                    # 의존성 설치 (venv 자동 생성)
uv run uvicorn app.main:app --reload --port 8000
uv run pytest                          # 테스트
uv run ruff check . && uv run ruff format .
uv run mypy app                        # strict
```

진입점:
- 헬스체크: http://127.0.0.1:8000/health
- Swagger: http://127.0.0.1:8000/docs
- 메트릭: http://127.0.0.1:8000/metrics

### 8.7 Compaction Recovery

`CLAUDE.md` 규약 — 컨텍스트 손실 시:
1. `pipeline/state/current-state.json` 읽기
2. `pipeline/decisions/decision-registry.md` 읽기
3. 현재 단계 산출물 로드

### 8.8 테스트 (`tests/`)

27개 테스트 파일 — 통합/단위 혼합:

| 파일 | 범위 |
|------|------|
| `conftest.py` | testcontainers PG16 픽스처, async 세션 |
| `test_health.py`, `test_cors.py` | 메타 |
| `test_routers.py` | 라우터 통합 |
| `test_repositories.py` | Repository CRUD |
| `test_services.py` | 시그널/마켓데이터 서비스 |
| `test_batch.py` | 3-Step 파이프라인 |
| `test_krx_client.py`, `test_dart_client.py`, `test_kis_client.py`, `test_telegram_client.py` | MockTransport 기반 외부 어댑터 |
| `test_kis_real_sync.py` | KIS REAL 경로 (admin key + credential 흐름) |
| `test_brokerage_credential.py` | Fernet CRUD + 마스킹 + 키 회전 |
| `test_portfolio.py` | 8 UseCase 회귀 (20+ KB, 가장 큰 파일) |
| `test_excel_import.py` | KIS xlsx 파서 + 중복 스킵 |
| `test_analysis_report.py` | DART Tier1 + LLM strict JSON + 캐시 |
| `test_logging_masking.py` | structlog 마스킹 (JWT/hex/키) |
| `test_e2e_flow.py` | 종단 시나리오 (signal → backtest → portfolio → report) |
| `test_seed_ui_demo.py`, `test_backfill_stock_prices.py`, `test_market_data_lending_deltas.py`, `test_sync_dart_corp_mapping.py`, `test_notification_service.py` | 보조 |

마커: `requires_kis_real_account` — 실 KIS 계정 자격증명 필요, CI 기본 skip.

---

## 부록 A. 주요 파일 요약 (1줄)

| 파일 | 줄수 | 책임 |
|------|------|------|
| `app/main.py` | 105 | FastAPI app factory, lifespan, CORS, slowapi, Prometheus |
| `app/config/settings.py` | 154 | Pydantic Settings (45+ env field) |
| `app/observability/logging.py` | 239 | structlog + 민감값 마스킹 |
| `app/security/credential_cipher.py` | 87 | Fernet + key_version 관리 |
| `app/batch/scheduler.py` | 76 | APScheduler AsyncIOScheduler + KST CronTrigger |
| `app/batch/market_data_job.py` | 172 | 3-Step 파이프라인 (collect/detect/notify) |
| `app/batch/backtest_job.py` | 110 | 단일 Step 파이프라인 |
| `app/application/service/signal_detection_service.py` | 296 | 3종 시그널 알고리즘 (pandas 벡터화) |
| `app/application/service/backtest_service.py` | 189 | vectorbt + pivot/shift 수익률 계산 |
| `app/application/service/portfolio_service.py` | 916 | 8 UseCase + 12 ErrorClass + KIS sync mock/real |
| `app/application/service/excel_import_service.py` | 329 | KIS xlsx 파서 + Service |
| `app/application/service/analysis_report_service.py` | 323 | DART Tier1 수집 + LLM 위임 + 캐시 |
| `app/application/service/notification_service.py` | 77 | Telegram HTML, html.escape 인젝션 방어 |
| `app/application/service/market_data_service.py` | 161 | KRX 수집 + lending delta 계산 |
| `app/application/port/out/kis_port.py` | 68 | `KisHoldingsFetcher` Protocol + 예외 |
| `app/application/port/out/llm_provider.py` | 231 | `LLMProvider` Protocol + Tier1/2 dataclass + JSON Schema |
| `app/adapter/web/_deps.py` | 128 | Depends 모음 (세션/외부/admin key) |
| `app/adapter/web/_schemas.py` | 321 | Pydantic 요청/응답 스키마 (40+ 모델) |
| `app/adapter/web/routers/portfolio.py` | 590 | 16 엔드포인트 (P10/11/15) |
| `app/adapter/out/external/kis_client.py` | 355 | KIS REST + In-memory MockTransport |
| `app/adapter/out/external/krx_client.py` | 263 | pykrx 비동기 래퍼 + rate limit |
| `app/adapter/out/external/dart_client.py` | 343 | DART OpenAPI 4 엔드포인트 |
| `app/adapter/out/external/telegram_client.py` | 65 | no-op 모드 + HTML parse_mode |
| `app/adapter/out/ai/openai_provider.py` | 296 | strict JSON + 프롬프트 인젝션 방어 |
| `app/adapter/out/persistence/models/portfolio.py` | 139 | 5 ORM 모델 (account/holding/tx/credential/snapshot) |
| `scripts/entrypoint.py` | 82 | Alembic stamp 호환 + Uvicorn |
| `migrations/env.py` | 66 | asyncpg → psycopg2 URL 치환 |

---

## 부록 B. 호출 흐름 예시 — `/api/portfolio/accounts/{id}/sync`

```
1. POST /api/portfolio/accounts/42/sync
   └ require_admin_key (X-API-Key)

2. 라우터 (routers/portfolio.py:262-309)
   ├ get_session()  →  AsyncSession
   ├ get_kis_client()       →  KisClient (MOCK)
   ├ get_credential_cipher() →  CredentialCipher (Fernet)
   └ get_kis_real_client_factory() → factory(creds) → KisClient(REAL, ...)

3. account = BrokerageAccountRepository.get(42)  → connection_type 분기

4-a. connection_type == "kis_rest_mock":
       SyncPortfolioFromKisMockUseCase(session, kis_client=kis).execute(account_id, account)
         └ kis.fetch_balance()  →  list[KisHoldingRow]
         └ _apply_kis_holdings(...) → upsert PortfolioHolding

4-b. connection_type == "kis_rest_real":
       credential_repo = BrokerageAccountCredentialRepository(session, cipher)
       SyncPortfolioFromKisRealUseCase(...).execute(account_id, account)
         └ _ensure_kis_real_account (env=real 검증)
         └ credential_repo.get_decrypted(42)  →  KisCredentials | None (404 if None)
         └ async with factory(creds) as client:  →  KisClient(REAL, creds)
              └ client.fetch_balance()
         └ _apply_kis_holdings(...)

5. 예외 분기:
     KisCredentialRejectedError → CredentialRejectedError → 400
     KisUpstreamError → SyncError → 502
     CredentialCipherError → 500 (로그에는 type만, body에는 일반 메시지)

6. 응답: SyncResponse {fetched, created, updated, unchanged, stock_created}
```

---

## 부록 C. 알려진 제약 및 결정 (Memory 발췌)

- **KRX 익명 차단 (2026-04~)**: `KRX_ID`/`KRX_PW` 미설정 시 모든 데이터 0 rows. 현재 메모리: `project_krx_auth_blocker.md` 참조.
- **KIS REAL URL 위장 차단**: `kis_client.py` 가 `_MOCK_BASE_URL`/`_REAL_BASE_URL` 을 환경 상수로 직접 고정해 Settings 가 mock 으로 위장한 실 URL 주입을 막는다.
- **In-memory mock 제약**: `KIS_USE_IN_MEMORY_MOCK=True` 는 MOCK 환경에서만 자동 활성. REAL 에서 사용하려면 테스트가 명시적으로 `transport=...` 주입.
- **Big-bang 재작성**: Java→Python 전면 이전 — Phase 1~9 완료 (2026-04). 사전-운영 단계 + 단일 팀이라 점진적 마이그레이션보다 일괄 재작성 채택.
- **MVP 범위**: 4~6주 런칭. 앱은 v1 PWA 대체 권장.

---

_이 명세서는 `master b3e2546` 시점의 소스 정독 결과로, 코드와 동기화가 필요할 경우 `app/` 디렉터리의 docstring 과 본 문서를 함께 갱신해야 한다._
