# endpoint-06-ka10081.md — 주식일봉차트조회요청 ★ 백테스팅 코어

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10081` |
| API 명 | 주식일봉차트조회요청 |
| 분류 | Tier 3 (백테스팅 OHLCV ★) |
| Phase | **C** |
| 우선순위 | **P0** (백테스팅 코어) |
| Method | `POST` |
| URL | `/api/dostk/chart` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX 만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| 의존 endpoint | `au10001`, `ka10099`(stock 마스터 + nxt_enable 게이팅) |
| 후속 endpoint | `ka10082`(주봉), `ka10083`(월봉), `ka10094`(년봉) — 동일 패턴. 백테스팅 엔진의 시계열 source |

---

## 1. 목적

백테스팅의 **가장 중요한 데이터 source**. 일봉 OHLCV + 거래량/거래대금 + 거래회전율을 KRX/NXT 분리하여 적재한다.

1. **백테스팅 코어 시계열** — 모든 시그널 / 수익률 / 손실 계산의 1차 입력
2. **KRX vs NXT 분리** — 같은 종목·같은 날의 두 거래소 가격 추적 (체결가 차이 / 거래량 분리 / 장 운영시간 차이)
3. **수정주가 적용** — `upd_stkpc_tp=1` 로 액면분할/배당락 자동 보정 (백테스팅 결과 왜곡 방지)
4. **연속조회** — `cont-yn=Y` + `next-key` 헤더로 과거 백필 (3년 = ~720 거래일 → 페이지 다중)

**왜 P0**:
- Phase C 까지 끝나야 `backend_py` 의 BacktestEngineService 와 동등한 시계열 분석 가능
- 본 endpoint 가 안정 작동하지 않으면 Phase D~G 의 보강 데이터(분봉/순위/투자자별)가 모두 무의미
- KRX 익명 차단 이후 신뢰 가능한 OHLCV 의 **유일한 후보**

**Phase C 5 endpoint 중 본 endpoint 가 reference**: ka10082/83/94 는 본 계획서의 패턴 복제 (list 키만 다름). ka10086 은 URL 다르고 응답 22 필드 — 별도 계획서.

---

## 2. Request 명세

### 2.1 Header

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `api-id` | TR 명 | String | Y | 10 | `"ka10081"` 고정 |
| `authorization` | 접근토큰 | String | Y | 1000 | `Bearer <token>` |
| `cont-yn` | 연속조회 여부 | String | N | 1 | 응답 헤더 그대로 전달 |
| `next-key` | 연속조회 키 | String | N | 50 | 응답 헤더 그대로 전달 |

### 2.2 Body

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `stk_cd` | 종목코드 | String | Y | **20** | KRX `005930`, NXT `005930_NX`, SOR `005930_AL` |
| `base_dt` | 기준일자 | String | Y | 8 | `YYYYMMDD` (이 날짜를 포함한 과거 시계열 응답) |
| `upd_stkpc_tp` | 수정주가구분 | String | Y | 1 | `0`=원본 / `1`=수정주가 (백테스팅용) |

### 2.3 Request 예시 (Excel R43)

```json
POST https://api.kiwoom.com/api/dostk/chart
Content-Type: application/json;charset=UTF-8
api-id: ka10081
authorization: Bearer WQJCwyqInphKnR3bSRtB9NE1lv...

{
    "stk_cd": "005930",
    "base_dt": "20250908",
    "upd_stkpc_tp": "1"
}
```

### 2.4 Pydantic 모델

```python
# app/adapter/out/kiwoom/chart.py
class DailyChartRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    stk_cd: Annotated[str, Field(min_length=6, max_length=20)]
    base_dt: Annotated[str, Field(pattern=r"^\d{8}$")]
    upd_stkpc_tp: Literal["0", "1"]


class AdjustedPriceMode(StrEnum):
    """upd_stkpc_tp 의미. 백테스팅은 항상 ADJUSTED."""
    RAW = "0"
    ADJUSTED = "1"
```

> 백테스팅 호출은 **항상 `upd_stkpc_tp="1"`**. raw 모드는 비교 검증용.

---

## 3. Response 명세

### 3.1 Header

| Element | Type | Description |
|---------|------|-------------|
| `api-id` | String | `"ka10081"` 에코 |
| `cont-yn` | String | `Y` 면 다음 페이지 |
| `next-key` | String | 다음 호출 헤더에 세팅 |

### 3.2 Body

| Element | 한글명 | Type | Length | 영속화 컬럼 | 메모 |
|---------|-------|------|--------|-------------|------|
| `stk_cd` | 종목코드 | String | 6 | (FK lookup) | 응답에 _NX 보존되어 오는지 운영 검증 필요 |
| `stk_dt_pole_chart_qry[]` | 일봉차트 list | LIST | — | (전체 row 적재) | **list key 명** — ka10082~94 와 다름 |
| `cur_prc` | 현재가 (해당 일자 종가) | String | 20 | `close_price` (BIGINT) | KRW. 부호 포함 가능 |
| `trde_qty` | 거래량 | String | 20 | `trade_volume` (BIGINT) | 주 |
| `trde_prica` | 거래대금 | String | 20 | `trade_amount` (BIGINT) | 백만원 추정 (운영 검증) |
| `dt` | 일자 | String | 20 | `trading_date` (DATE) | `YYYYMMDD` |
| `open_pric` | 시가 | String | 20 | `open_price` (BIGINT) | KRW. 부호 포함 가능 |
| `high_pric` | 고가 | String | 20 | `high_price` (BIGINT) | KRW. 부호 포함 가능 |
| `low_pric` | 저가 | String | 20 | `low_price` (BIGINT) | KRW. 부호 포함 가능 |
| `pred_pre` | 전일대비 | String | 20 | `prev_compare_amount` (BIGINT) | 현재가 - 전일종가. `+600` 부호 포함 |
| `pred_pre_sig` | 전일대비기호 | String | 20 | `prev_compare_sign` (CHAR(1)) | `1`:상한가 / `2`:상승 / `3`:보합 / `4`:하한가 / `5`:하락 |
| `trde_tern_rt` | 거래회전율 | String | 20 | `turnover_rate` (NUMERIC(8,4)) | %. `+0.16` 부호 포함 |
| `return_code` | 처리코드 | Integer | — | (raw_response only) | 0 정상 |
| `return_msg` | 처리메시지 | String | — | (raw_response only) | |

### 3.3 Response 예시 (Excel R45)

```json
{
    "stk_cd": "005930",
    "stk_dt_pole_chart_qry": [
        {
            "cur_prc": "70100",
            "trde_qty": "9263135",
            "trde_prica": "648525",
            "dt": "20250908",
            "open_pric": "69800",
            "high_pric": "70500",
            "low_pric": "69600",
            "pred_pre": "+600",
            "pred_pre_sig": "2",
            "trde_tern_rt": "+0.16"
        }
    ]
}
```

### 3.4 Pydantic 모델 + 정규화

```python
# app/adapter/out/kiwoom/_records.py
class DailyChartRow(BaseModel):
    """ka10081 응답 row — 키움 응답 그대로 (string + 부호 포함)."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    cur_prc: str = ""
    trde_qty: str = ""
    trde_prica: str = ""
    dt: str = ""
    open_pric: str = ""
    high_pric: str = ""
    low_pric: str = ""
    pred_pre: str = ""
    pred_pre_sig: str = ""
    trde_tern_rt: str = ""

    def to_normalized(
        self,
        *,
        stock_id: int,
        exchange: ExchangeType,
        adjusted: bool,
    ) -> "NormalizedDailyOhlcv":
        return NormalizedDailyOhlcv(
            stock_id=stock_id,
            trading_date=_parse_yyyymmdd(self.dt) or date.min,    # 빈 dt 는 caller skip
            exchange=exchange,
            adjusted=adjusted,
            open_price=_to_int(self.open_pric),
            high_price=_to_int(self.high_pric),
            low_price=_to_int(self.low_pric),
            close_price=_to_int(self.cur_prc),
            trade_volume=_to_int(self.trde_qty),
            trade_amount=_to_int(self.trde_prica),
            prev_compare_amount=_to_int(self.pred_pre),
            prev_compare_sign=self.pred_pre_sig or None,
            turnover_rate=_to_decimal(self.trde_tern_rt),
        )


class DailyChartResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    stk_cd: str = ""
    stk_dt_pole_chart_qry: list[DailyChartRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""


@dataclass(frozen=True, slots=True)
class NormalizedDailyOhlcv:
    stock_id: int
    trading_date: date
    exchange: ExchangeType
    adjusted: bool                 # upd_stkpc_tp 1=True
    open_price: int | None
    high_price: int | None
    low_price: int | None
    close_price: int | None
    trade_volume: int | None
    trade_amount: int | None
    prev_compare_amount: int | None
    prev_compare_sign: str | None  # 1~5
    turnover_rate: Decimal | None
```

> `_to_int("+600")` → 600, `_to_int("-200")` → -200 (ka10001 의 helper 재사용). `_to_decimal("+0.16")` → `Decimal("0.16")`.

---

## 4. NXT 처리

| 항목 | 적용 여부 |
|------|-----------|
| `stk_cd` 에 `_NX` suffix | **Y** (Length=20 + Excel R22 명시) |
| `nxt_enable` 게이팅 | **Y** (NXT 호출 전 stock.nxt_enable=true 검증) |
| `mrkt_tp` 별 분리 | N (시계열은 단건 호출) |
| KRX 운영 / 모의 차이 | mockapi 는 KRX 전용 — `_NX` 호출은 운영 도메인만 |

### 4.1 KRX/NXT 동시 호출 패턴

```python
async def ingest_one_stock_daily(stock: Stock, base_dt: date) -> IngestOutcome:
    """한 종목의 일봉을 KRX + NXT 둘 다 적재 (NXT 가능 종목만 NXT 호출)."""
    krx_outcome = await ingest_for_exchange(stock, base_dt, ExchangeType.KRX)
    if stock.nxt_enable and settings.nxt_collection_enabled:
        nxt_outcome = await ingest_for_exchange(stock, base_dt, ExchangeType.NXT)
    else:
        nxt_outcome = IngestOutcome(skipped=True, reason="nxt_disabled")
    return CombinedOutcome(krx=krx_outcome, nxt=nxt_outcome)
```

### 4.2 KRX 실패 시 NXT 도 skip 정책

| 옵션 | 동작 | 권장 |
|------|------|------|
| (a) **독립 호출** | KRX 실패해도 NXT 호출 시도 | (권장) |
| (b) 의존 호출 | KRX 실패시 NXT skip | NXT API 가 같은 토큰을 사용하므로 자격증명 문제면 둘 다 실패 |

→ (a) 채택. KRX/NXT 호출이 독립 try/except. 부분 실패 허용.

### 4.3 응답 stk_cd 의 suffix 처리

요청 `005930_NX` → 응답 `stk_cd` 가 `005930_NX` 로 오는지 `005930` 으로 stripped 되는지 **운영 검증 필요**. 어느 쪽이든 `strip_kiwoom_suffix(response.stk_cd)` 로 base code 추출 후 stock_id FK 매핑.

### 4.4 NXT 운영 시작일 이전 일자 호출 (백필)

NXT 거래소 운영 시작일 (~2025-03 추정) 이전의 base_dt 로 NXT 호출 시 응답 패턴:

| 가능 시나리오 | 우리 처리 |
|--------------|-----------|
| 빈 list `[]` | 정상 — 적재 0 row |
| `return_code != 0` | KiwoomBusinessError → caller 가 swallow |
| 정상 KRX 데이터 mirror | (있으면 안 됨, 검증 필요) |

→ 백필 스크립트는 NXT 호출의 base_dt 가 운영 시작일 이후인지 가드.

---

## 5. DB 스키마

### 5.1 신규 테이블 — Migration 003 + 004 분리

> **마이그레이션 분할 이유**: `kiwoom_enable` 컬럼은 stock 에 이미 있음 (Phase B). 003 = KRX, 004 = NXT 분리 적용으로 운영 중 NXT 활성화/비활성화 토글 가능.

#### Migration 003 — `003_ohlcv_krx.py`

```sql
CREATE TABLE kiwoom.stock_price_krx (
    id                       BIGSERIAL PRIMARY KEY,
    stock_id                 BIGINT NOT NULL REFERENCES kiwoom.stock(id) ON DELETE CASCADE,
    trading_date             DATE NOT NULL,
    adjusted                 BOOLEAN NOT NULL DEFAULT true,        -- upd_stkpc_tp=1 가정
    open_price               BIGINT,
    high_price               BIGINT,
    low_price                BIGINT,
    close_price              BIGINT,
    trade_volume             BIGINT,
    trade_amount             BIGINT,
    prev_compare_amount      BIGINT,
    prev_compare_sign        CHAR(1),
    turnover_rate            NUMERIC(8, 4),
    fetched_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_price_krx_stock_date UNIQUE (stock_id, trading_date, adjusted)
);

CREATE INDEX idx_price_krx_trading_date ON kiwoom.stock_price_krx(trading_date);
CREATE INDEX idx_price_krx_stock_id ON kiwoom.stock_price_krx(stock_id);
```

#### Migration 004 — `004_ohlcv_nxt.py`

```sql
CREATE TABLE kiwoom.stock_price_nxt (
    -- stock_price_krx 와 동일 컬럼 구조
    id                       BIGSERIAL PRIMARY KEY,
    stock_id                 BIGINT NOT NULL REFERENCES kiwoom.stock(id) ON DELETE CASCADE,
    trading_date             DATE NOT NULL,
    adjusted                 BOOLEAN NOT NULL DEFAULT true,
    open_price               BIGINT,
    high_price               BIGINT,
    low_price                BIGINT,
    close_price              BIGINT,
    trade_volume             BIGINT,
    trade_amount             BIGINT,
    prev_compare_amount      BIGINT,
    prev_compare_sign        CHAR(1),
    turnover_rate            NUMERIC(8, 4),
    fetched_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_price_nxt_stock_date UNIQUE (stock_id, trading_date, adjusted)
);

CREATE INDEX idx_price_nxt_trading_date ON kiwoom.stock_price_nxt(trading_date);
CREATE INDEX idx_price_nxt_stock_id ON kiwoom.stock_price_nxt(stock_id);
```

> **물리 분리** (master.md § 3.1): 같은 종목·같은 날의 KRX/NXT 가격이 다를 수 있고, 수집 실패 격리·재현성 추적·백테스팅 시나리오 분기를 위해 두 테이블.

### 5.2 ORM 모델 — base 클래스 공유

```python
# app/adapter/out/persistence/models/_ohlcv_base.py
class _DailyOhlcvMixin:
    """KRX/NXT 두 테이블 공통 컬럼 정의."""

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("kiwoom.stock.id", ondelete="CASCADE"), nullable=False
    )
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    adjusted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    open_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    high_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    low_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    close_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    trade_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    trade_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_compare_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_compare_sign: Mapped[str | None] = mapped_column(String(1), nullable=True)
    turnover_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class StockPriceKrx(Base, _DailyOhlcvMixin):
    __tablename__ = "stock_price_krx"
    __table_args__ = (
        UniqueConstraint("stock_id", "trading_date", "adjusted",
                          name="uq_price_krx_stock_date"),
        {"schema": "kiwoom"},
    )


class StockPriceNxt(Base, _DailyOhlcvMixin):
    __tablename__ = "stock_price_nxt"
    __table_args__ = (
        UniqueConstraint("stock_id", "trading_date", "adjusted",
                          name="uq_price_nxt_stock_date"),
        {"schema": "kiwoom"},
    )
```

### 5.3 통합 view (선택)

```sql
-- Migration 004 의 일부
CREATE VIEW kiwoom.stock_price_combined AS
    SELECT 'KRX' AS exchange, * FROM kiwoom.stock_price_krx WHERE adjusted = true
    UNION ALL
    SELECT 'NXT' AS exchange, * FROM kiwoom.stock_price_nxt WHERE adjusted = true;
```

→ 백테스팅 엔진이 시나리오 별로 분기 (KRX only / NXT only / 통합).

### 5.4 파티션 검토

3년 시계열 = 종목 3000 × 720 거래일 = ~2.16M row × 2 거래소 = ~4.3M row. 단일 테이블로 충분 — 월별 파티션은 5년+ 시점에 검토.

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomChartClient.fetch_daily`

```python
# app/adapter/out/kiwoom/chart.py
class KiwoomChartClient:
    """`/api/dostk/chart` 계열 묶음. ka10079~ka10094 공유."""

    PATH = "/api/dostk/chart"

    def __init__(self, kiwoom_client: KiwoomClient) -> None:
        self._client = kiwoom_client

    async def fetch_daily(
        self,
        stock_code: str,
        *,
        base_date: date,
        exchange: ExchangeType = ExchangeType.KRX,
        adjusted: bool = True,
        max_pages: int = 10,
    ) -> list[DailyChartRow]:
        """단일 종목·단일 거래소의 일봉 시계열. cont-yn 자동 페이지네이션."""
        if not (len(stock_code) == 6 and stock_code.isdigit()):
            raise ValueError(f"stock_code 6자리 숫자만: {stock_code}")
        stk_cd = build_stk_cd(stock_code, exchange)

        body = {
            "stk_cd": stk_cd,
            "base_dt": base_date.strftime("%Y%m%d"),
            "upd_stkpc_tp": "1" if adjusted else "0",
        }

        all_rows: list[DailyChartRow] = []
        async for page in self._client.call_paginated(
            api_id="ka10081",
            endpoint=self.PATH,
            body=body,
            max_pages=max_pages,
        ):
            parsed = DailyChartResponse.model_validate(page.body)
            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id="ka10081",
                    return_code=parsed.return_code,
                    return_msg=parsed.return_msg,
                )
            all_rows.extend(parsed.stk_dt_pole_chart_qry)

        return all_rows
```

> `max_pages=10` 기본값 — 키움 일봉 1 페이지 ~600 거래일 추정. 3년 백필이면 2 페이지.

### 6.2 Repository

```python
# app/adapter/out/persistence/repositories/stock_price.py
class StockPriceRepository:
    """KRX/NXT 두 테이블의 인터페이스 통일.

    exchange 파라미터로 분기. UseCase 는 어느 테이블인지 신경 쓰지 않음.
    """

    _MODEL_BY_EXCHANGE = {
        ExchangeType.KRX: StockPriceKrx,
        ExchangeType.NXT: StockPriceNxt,
    }

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _model(self, exchange: ExchangeType) -> type[Base]:
        if exchange not in self._MODEL_BY_EXCHANGE:
            raise ValueError(f"unsupported exchange: {exchange}")
        return self._MODEL_BY_EXCHANGE[exchange]

    async def upsert_many(
        self,
        rows: Sequence[NormalizedDailyOhlcv],
        *,
        exchange: ExchangeType,
    ) -> int:
        if not rows:
            return 0
        model = self._model(exchange)
        values = [
            {
                "stock_id": r.stock_id,
                "trading_date": r.trading_date,
                "adjusted": r.adjusted,
                "open_price": r.open_price,
                "high_price": r.high_price,
                "low_price": r.low_price,
                "close_price": r.close_price,
                "trade_volume": r.trade_volume,
                "trade_amount": r.trade_amount,
                "prev_compare_amount": r.prev_compare_amount,
                "prev_compare_sign": r.prev_compare_sign,
                "turnover_rate": r.turnover_rate,
            }
            for r in rows
            if r.trading_date != date.min          # 빈 dt 응답 row 제외
        ]
        if not values:
            return 0

        stmt = pg_insert(model).values(values)
        update_set = {col: stmt.excluded[col] for col in values[0]
                      if col not in ("stock_id", "trading_date", "adjusted")}
        update_set["fetched_at"] = func.now()
        update_set["updated_at"] = func.now()
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_id", "trading_date", "adjusted"],
            set_=update_set,
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return rowcount_of(result)

    async def get_latest_date(
        self,
        stock_id: int,
        *,
        exchange: ExchangeType,
        adjusted: bool = True,
    ) -> date | None:
        """그 종목의 가장 최근 trading_date — 백필 진입점 산정용."""
        model = self._model(exchange)
        stmt = (
            select(model.trading_date)
            .where(model.stock_id == stock_id, model.adjusted.is_(adjusted))
            .order_by(model.trading_date.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_range(
        self,
        stock_id: int,
        *,
        exchange: ExchangeType,
        start_date: date,
        end_date: date,
        adjusted: bool = True,
    ) -> list[Base]:
        """백테스팅 엔진이 사용하는 read API."""
        model = self._model(exchange)
        stmt = (
            select(model)
            .where(
                model.stock_id == stock_id,
                model.adjusted.is_(adjusted),
                model.trading_date >= start_date,
                model.trading_date <= end_date,
            )
            .order_by(model.trading_date)
        )
        return list((await self._session.execute(stmt)).scalars())
```

### 6.3 UseCase — `IngestDailyOhlcvUseCase`

```python
# app/application/service/ohlcv_service.py
class IngestDailyOhlcvUseCase:
    """단일 거래소 단일 종목 일봉 적재.

    Phase B 의존:
    - stock 테이블에서 종목 조회 (없으면 LookupStockUseCase.ensure_exists 로 lazy fetch)
    - nxt_enable=False 면 NXT 호출 안 함

    멱등성: ON CONFLICT (stock_id, trading_date, adjusted) UPDATE.
    같은 날 두 번 호출하면 마지막 호출의 값으로 갱신 (장중 호출 후 장 마감 후 재호출 가능).
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        chart_client: KiwoomChartClient,
        lookup_use_case: LookupStockUseCase,
        env: Literal["prod", "mock"] = "prod",
    ) -> None:
        self._session = session
        self._client = chart_client
        self._lookup = lookup_use_case
        self._stock_repo = StockRepository(session)
        self._price_repo = StockPriceRepository(session)
        self._env = env

    async def execute(
        self,
        stock_code: str,
        *,
        base_date: date,
        exchange: ExchangeType = ExchangeType.KRX,
        adjusted: bool = True,
    ) -> OhlcvIngestOutcome:
        # mock 도메인은 NXT 호출 차단
        if self._env == "mock" and exchange is ExchangeType.NXT:
            return OhlcvIngestOutcome(
                stock_code=stock_code,
                exchange=exchange,
                upserted=0,
                skipped=True,
                reason="mock_no_nxt",
            )

        # stock 마스터 보장 (lazy fetch)
        stock = await self._lookup.ensure_exists(stock_code)
        if not stock.is_active:
            return OhlcvIngestOutcome(
                stock_code=stock_code,
                exchange=exchange,
                upserted=0,
                skipped=True,
                reason="inactive",
            )
        if exchange is ExchangeType.NXT and not stock.nxt_enable:
            return OhlcvIngestOutcome(
                stock_code=stock_code,
                exchange=exchange,
                upserted=0,
                skipped=True,
                reason="nxt_disabled",
            )

        # 키움 호출
        try:
            raw_rows = await self._client.fetch_daily(
                stock_code,
                base_date=base_date,
                exchange=exchange,
                adjusted=adjusted,
            )
        except KiwoomBusinessError as exc:
            return OhlcvIngestOutcome(
                stock_code=stock_code,
                exchange=exchange,
                upserted=0,
                skipped=False,
                error=f"business: {exc.return_code}",
            )

        normalized = [
            r.to_normalized(stock_id=stock.id, exchange=exchange, adjusted=adjusted)
            for r in raw_rows
        ]
        upserted = await self._price_repo.upsert_many(normalized, exchange=exchange)

        return OhlcvIngestOutcome(
            stock_code=stock_code,
            exchange=exchange,
            fetched=len(raw_rows),
            upserted=upserted,
        )


@dataclass(frozen=True, slots=True)
class OhlcvIngestOutcome:
    stock_code: str
    exchange: ExchangeType
    fetched: int = 0
    upserted: int = 0
    skipped: bool = False
    reason: str | None = None
    error: str | None = None
```

### 6.4 Bulk 진행자 — `IngestDailyOhlcvBulkUseCase`

```python
class IngestDailyOhlcvBulkUseCase:
    """모든 active 종목의 일봉을 KRX + NXT 일괄 적재.

    동시성: master.md § 6.3 RPS 4 + 250ms interval.
    소요: 3000 종목 × 2 (KRX+NXT) × 0.25s = 1500초 ≈ 25분 (이론).
      실측 30~60분 추정 (페이지네이션 + 응답 시간).
    """

    BATCH_SIZE = 50    # 50 종목 처리 후 commit

    def __init__(
        self,
        session: AsyncSession,
        *,
        single_use_case: IngestDailyOhlcvUseCase,
    ) -> None:
        self._session = session
        self._single = single_use_case
        self._stock_repo = StockRepository(session)

    async def execute(
        self,
        *,
        base_date: date,
        only_market_codes: Sequence[str] | None = None,
        only_stock_codes: Sequence[str] | None = None,
    ) -> OhlcvBulkResult:
        # active 종목 조회
        stmt = select(Stock).where(Stock.is_active.is_(True))
        if only_market_codes:
            stmt = stmt.where(Stock.market_code.in_(only_market_codes))
        if only_stock_codes:
            stmt = stmt.where(Stock.stock_code.in_(only_stock_codes))
        stocks = list((await self._session.execute(stmt)).scalars())

        krx_outcomes: list[OhlcvIngestOutcome] = []
        nxt_outcomes: list[OhlcvIngestOutcome] = []

        for i, stock in enumerate(stocks, start=1):
            # KRX
            try:
                async with self._session.begin_nested():
                    o = await self._single.execute(
                        stock.stock_code, base_date=base_date,
                        exchange=ExchangeType.KRX,
                    )
                    krx_outcomes.append(o)
            except Exception as exc:
                logger.warning("KRX ingest 실패 %s: %s", stock.stock_code, exc)
                krx_outcomes.append(OhlcvIngestOutcome(
                    stock_code=stock.stock_code, exchange=ExchangeType.KRX,
                    error=f"{type(exc).__name__}: {exc}",
                ))

            # NXT (nxt_enable 만)
            if stock.nxt_enable:
                try:
                    async with self._session.begin_nested():
                        o = await self._single.execute(
                            stock.stock_code, base_date=base_date,
                            exchange=ExchangeType.NXT,
                        )
                        nxt_outcomes.append(o)
                except Exception as exc:
                    logger.warning("NXT ingest 실패 %s: %s", stock.stock_code, exc)
                    nxt_outcomes.append(OhlcvIngestOutcome(
                        stock_code=stock.stock_code, exchange=ExchangeType.NXT,
                        error=f"{type(exc).__name__}: {exc}",
                    ))

            # 50건마다 commit
            if i % self.BATCH_SIZE == 0:
                await self._session.commit()
                logger.info("ingest progress %d/%d", i, len(stocks))

        await self._session.commit()
        return OhlcvBulkResult(
            base_date=base_date,
            total_stocks=len(stocks),
            krx_outcomes=krx_outcomes,
            nxt_outcomes=nxt_outcomes,
        )


@dataclass(frozen=True, slots=True)
class OhlcvBulkResult:
    base_date: date
    total_stocks: int
    krx_outcomes: list[OhlcvIngestOutcome]
    nxt_outcomes: list[OhlcvIngestOutcome]

    @property
    def krx_success(self) -> int:
        return sum(1 for o in self.krx_outcomes if o.upserted > 0)

    @property
    def nxt_success(self) -> int:
        return sum(1 for o in self.nxt_outcomes if o.upserted > 0)

    @property
    def total_rows_inserted(self) -> int:
        krx = sum(o.upserted for o in self.krx_outcomes)
        nxt = sum(o.upserted for o in self.nxt_outcomes)
        return krx + nxt
```

### 6.5 백필 — `BackfillDailyOhlcvUseCase`

```python
class BackfillDailyOhlcvUseCase:
    """과거 일자 백필. base_date 를 점진적으로 과거로 이동.

    키움은 base_dt 를 포함한 과거 시계열을 응답 — 한 호출로 ~600 거래일 추정.
    3년 백필은 base_dt = 오늘 → 응답에 모든 일자 포함될 가능성 높음.
    """

    async def execute(
        self,
        stock_codes: Sequence[str],
        *,
        end_date: date,
        years: int = 3,
        exchange: ExchangeType = ExchangeType.KRX,
    ) -> OhlcvBulkResult:
        start_date = end_date - timedelta(days=years * 365)
        # base_dt = end_date 호출. 응답이 start_date 까지 도달하지 못하면
        # 가장 오래된 응답 일자 - 1 일을 다음 base_dt 로 추가 호출 (max 5회).
        # ...
```

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **수동 단건** | on-demand | `POST /api/kiwoom/ohlcv/{stock_code}/daily?date=YYYYMMDD&exchange=KRX` |
| **수동 일괄** | on-demand | `POST /api/kiwoom/ohlcv/daily/sync?date=YYYYMMDD` |
| **일 1회 cron** | KST 18:30 평일 | 장 마감(15:30) + 청산(17:30) + ka10001 (17:45) 후 안정 시점 |
| **백필** | on-demand | `python scripts/backfill_ohlcv.py --start 2023-01-01 --end 2026-05-07` |

### 7.1 라우터

```python
# app/adapter/web/routers/ohlcv.py
router = APIRouter(prefix="/api/kiwoom/ohlcv", tags=["kiwoom-ohlcv"])


@router.post(
    "/{stock_code}/daily",
    response_model=OhlcvIngestOutcomeOut,
    dependencies=[Depends(require_admin_key)],
)
async def ingest_one_daily(
    stock_code: str,
    base_date: date = Query(default_factory=lambda: date.today()),
    exchange: Literal["KRX", "NXT"] = Query(default="KRX"),
    adjusted: bool = Query(default=True),
    use_case: IngestDailyOhlcvUseCase = Depends(get_ingest_daily_use_case),
) -> OhlcvIngestOutcomeOut:
    outcome = await use_case.execute(
        stock_code,
        base_date=base_date,
        exchange=ExchangeType(exchange),
        adjusted=adjusted,
    )
    return OhlcvIngestOutcomeOut.model_validate(asdict(outcome))


@router.post(
    "/daily/sync",
    response_model=OhlcvBulkResultOut,
    dependencies=[Depends(require_admin_key)],
)
async def sync_daily_bulk(
    body: OhlcvBulkRequestIn = Body(default_factory=OhlcvBulkRequestIn),
    use_case: IngestDailyOhlcvBulkUseCase = Depends(get_ingest_daily_bulk_use_case),
) -> OhlcvBulkResultOut:
    result = await use_case.execute(
        base_date=body.base_date or date.today(),
        only_market_codes=body.only_market_codes or None,
        only_stock_codes=body.only_stock_codes or None,
    )
    return OhlcvBulkResultOut.model_validate(asdict(result))


@router.get(
    "/{stock_code}/daily",
    response_model=list[StockPriceOut],
)
async def get_daily_range(
    stock_code: str,
    start_date: date = Query(...),
    end_date: date = Query(...),
    exchange: Literal["KRX", "NXT"] = Query(default="KRX"),
    adjusted: bool = Query(default=True),
    session: AsyncSession = Depends(get_session),
) -> list[StockPriceOut]:
    """백테스팅 엔진의 read API."""
    stock_repo = StockRepository(session)
    stock = await stock_repo.find_by_code(stock_code)
    if stock is None:
        raise HTTPException(status_code=404, detail=f"stock not found: {stock_code}")
    price_repo = StockPriceRepository(session)
    rows = await price_repo.get_range(
        stock.id, exchange=ExchangeType(exchange),
        start_date=start_date, end_date=end_date, adjusted=adjusted,
    )
    return [StockPriceOut.model_validate(r) for r in rows]
```

### 7.2 APScheduler Job

```python
# app/batch/daily_ohlcv_job.py
async def fire_daily_ohlcv_sync() -> None:
    """매 평일 18:30 KST — 일봉 적재 (KRX + NXT)."""
    today = date.today()
    if not is_trading_day(today):
        return
    try:
        async with get_sessionmaker()() as session:
            kiwoom_client = build_kiwoom_client_for("prod-main")
            chart = KiwoomChartClient(kiwoom_client)
            stkinfo = KiwoomStkInfoClient(kiwoom_client)
            lookup = LookupStockUseCase(
                session, stkinfo_client=stkinfo, env=settings.kiwoom_default_env,
            )
            single = IngestDailyOhlcvUseCase(
                session, chart_client=chart, lookup_use_case=lookup,
                env=settings.kiwoom_default_env,
            )
            bulk = IngestDailyOhlcvBulkUseCase(session, single_use_case=single)
            result = await bulk.execute(base_date=today)
        logger.info(
            "daily ohlcv sync 완료 base_date=%s total=%d krx_success=%d "
            "nxt_success=%d rows=%d",
            today, result.total_stocks,
            result.krx_success, result.nxt_success,
            result.total_rows_inserted,
        )
    except Exception:
        logger.exception("daily_ohlcv_sync 콜백 예외")


scheduler.add_job(
    fire_daily_ohlcv_sync,
    CronTrigger(day_of_week="mon-fri", hour=18, minute=30, timezone=KST),
    id="daily_ohlcv",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
    misfire_grace_time=60 * 90,    # 90분 grace — 60분 작업이라 여유
)
```

### 7.3 RPS / 시간 추정

| 항목 | 값 |
|------|----|
| active 종목 수 | ~3,000 (Phase B 5시장) |
| nxt_enable 종목 비율 | 추정 30~50% (운영 검증 필요) → ~1,000~1,500 |
| 호출당 인터벌 | 250ms |
| 동시성 | 4 (Semaphore) |
| 1회 sync 호출 수 | KRX 3000 + NXT 1500 = 4500 호출 |
| 이론 시간 | 4500 / 4 × 0.25 = 281초 ≈ 4.7분 |
| 실측 추정 | 30~60분 (페이지네이션 + 응답 시간 + 재시도) |

→ cron 18:30 + 90분 grace.

---

## 8. 에러 처리

| HTTP / 응답 | 도메인 예외 | 라우터 매핑 | UseCase 정책 |
|-------------|-------------|-------------|--------------|
| 400 (잘못된 stock_code) | `ValueError` | 400 | 호출 전 차단 |
| 401 / 403 | `KiwoomCredentialRejectedError` | 400 | bubble up — 모든 종목 실패 가능 |
| 429 | `KiwoomRateLimitedError` | 503 | tenacity 재시도 후 실패 시 다음 종목 |
| 5xx, 네트워크 | `KiwoomUpstreamError` | 502 | 다음 종목 |
| `return_code != 0` | `KiwoomBusinessError` | 400 | outcome.error 로 노출, 다음 종목 |
| 응답 `dt=""` 또는 `dt` 형식 오류 | (적재 skip) | — | upsert_many 가 trading_date=date.min row 자동 제외 |
| 빈 응답 `list=[]` | (정상) | — | upserted=0, error 아님 |
| FK 위반 (stock 미존재) | `IntegrityError` | 502 | UseCase 가 ensure_exists 선행 — 발생하면 안 됨 |
| NXT 호출이 KRX 와 같은 가격 (mirror 의심) | (warning 로그) | — | 적재는 진행, 데이터 품질 리포트 alert |

### 8.1 partial 실패 알람

3000 종목 × 2 거래소 = 4500 호출 중:
- < 1% 실패 (~45 호출): 정상
- 1~5%: warning 로그
- > 5%: error + 자격증명/RPS 점검 alert

### 8.2 같은 날 두 번 호출 (멱등성)

장중 호출 후 장 마감 후 재호출 — UNIQUE (stock_id, trading_date, adjusted) ON CONFLICT DO UPDATE 가 마지막 호출 값으로 갱신. 부작용 없음.

---

## 9. 테스트

### 9.1 Unit (MockTransport)

`tests/adapter/kiwoom/test_chart_daily.py`:

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 단일 페이지 | 200 + list 5건 + cont-yn=N | `fetch_daily` 5건 반환 |
| 페이지네이션 | 첫 200 + cont-yn=Y + list 600건, 둘째 list 200건 + N | call_paginated 2회, 합쳐 800건 |
| 빈 list | 200 + `stk_dt_pole_chart_qry=[]` | 빈 list 반환 |
| `return_code=1` | 비즈니스 에러 | `KiwoomBusinessError` |
| 401 | 자격증명 거부 | `KiwoomCredentialRejectedError` |
| stock_code "00593" | 호출 차단 | `ValueError` |
| ExchangeType.NXT 호출 | stk_cd build | request body `stk_cd="005930_NX"` 검증 |
| upd_stkpc_tp 분기 | adjusted=True | request body `upd_stkpc_tp="1"` |
| upd_stkpc_tp 분기 | adjusted=False | request body `upd_stkpc_tp="0"` |
| `dt=""` row | 응답에 빈 dt 1건 + 정상 4건 | to_normalized 가 trading_date=date.min, repo 가 자동 skip |
| 부호 포함 가격 | open_pric="+78800" | `_to_int` → 78800 |
| 음수 가격 | low_pric="-54500" | `_to_int` → -54500 (이건 부호 의미 모호 — Pydantic 검증 통과 후 그대로) |
| `pred_pre_sig` 1~5 | 1: 상한가 / 2: 상승 / ... | prev_compare_sign 그대로 저장 |
| 페이지네이션 폭주 | cont-yn=Y 무한 | `max_pages=10` 도달 → `KiwoomPaginationLimitError` |

### 9.2 Integration (testcontainers)

`tests/application/test_ohlcv_service.py`:

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| INSERT (DB 빈 상태) | stock 1건 + 응답 5 row | stock_price_krx 5 row INSERT |
| UPDATE (멱등성) | 같은 호출 두 번 | row 5개 유지, updated_at 갱신 |
| KRX + NXT 분리 적재 | nxt_enable=true 종목 + KRX 5건 + NXT 5건 | krx 5 + nxt 5 row, 두 테이블 분리 |
| `nxt_enable=false` skip | 종목.nxt_enable=false + NXT 호출 시도 | outcome.skipped=true, reason="nxt_disabled", row 0 |
| inactive stock skip | is_active=false + 호출 | outcome.skipped=true, reason="inactive" |
| mock no NXT | env="mock" + ExchangeType.NXT | outcome.skipped=true, reason="mock_no_nxt" |
| stock 미존재 + ensure_exists 호출 | 새 stock_code | LookupStockUseCase 가 ka10100 호출 + INSERT, 그 후 ka10081 적재 |
| 빈 응답 처리 | 응답 list=[] | upserted=0, error 없음 |
| dt 빈값 row 자동 skip | 5 row 중 1건 dt="" | upserted=4 (빈 dt 자동 제외) |
| adjusted=true vs false 동시 | 같은 종목·같은 날 두 모드 호출 | row 2개 (adjusted UNIQUE 분리) |
| Bulk 50건 batch commit | 100 종목 ingest | 50건마다 commit, 중간 오류가 50건 단위로 격리 |
| Bulk only_market_codes 필터 | KOSPI 만 | KOSDAQ 종목 처리 안 됨 |

### 9.3 E2E (요청 시 1회)

```python
@pytest.mark.requires_kiwoom_real
async def test_real_ka10081():
    creds = KiwoomCredentials(
        appkey=os.environ["KIWOOM_PROD_APPKEY"],
        secretkey=os.environ["KIWOOM_PROD_SECRETKEY"],
    )
    async with KiwoomAuthClient(base_url="https://api.kiwoom.com") as auth:
        token = await auth.issue_token(creds)
    try:
        kiwoom_client = KiwoomClient(
            base_url="https://api.kiwoom.com", token=token.token,
        )
        chart = KiwoomChartClient(kiwoom_client)

        # 삼성전자 KRX 일봉 (오늘 기준)
        krx = await chart.fetch_daily("005930", base_date=date.today(), exchange=ExchangeType.KRX)
        assert len(krx) >= 60     # 한 호출에 60+ 거래일 응답 추정

        latest = krx[0]            # 첫 row 가 최신 일자 추정 (응답 정렬 운영 검증)
        assert latest.dt
        assert _parse_yyyymmdd(latest.dt) is not None
        assert latest.cur_prc != ""

        # 삼성전자 NXT 일봉
        nxt = await chart.fetch_daily("005930", base_date=date.today(), exchange=ExchangeType.NXT)
        # NXT 운영 시작일 이후 데이터만 — 60건 미만 가능
        assert len(nxt) >= 1

        # KRX 와 NXT 의 같은 일자 close_price 비교
        latest_date = krx[0].dt
        nxt_same_date = next((r for r in nxt if r.dt == latest_date), None)
        if nxt_same_date is not None:
            krx_close = _to_int(latest.cur_prc)
            nxt_close = _to_int(nxt_same_date.cur_prc)
            # ±5% 차이 허용
            ratio = abs(krx_close - nxt_close) / krx_close
            assert ratio < 0.05
    finally:
        async with KiwoomAuthClient(base_url="https://api.kiwoom.com") as auth:
            await auth.revoke_token(creds, token.token)
```

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `app/adapter/out/kiwoom/chart.py` — `KiwoomChartClient.fetch_daily`
- [ ] `app/adapter/out/kiwoom/_records.py` — `DailyChartRow`, `DailyChartResponse`, `NormalizedDailyOhlcv`
- [ ] `app/adapter/out/persistence/models/_ohlcv_base.py` — `_DailyOhlcvMixin`
- [ ] `app/adapter/out/persistence/models/stock_price_krx.py` — `StockPriceKrx`
- [ ] `app/adapter/out/persistence/models/stock_price_nxt.py` — `StockPriceNxt`
- [ ] `app/adapter/out/persistence/repositories/stock_price.py` — `StockPriceRepository`
- [ ] `app/application/service/ohlcv_service.py` — `IngestDailyOhlcvUseCase`, `IngestDailyOhlcvBulkUseCase`, `BackfillDailyOhlcvUseCase`
- [ ] `app/adapter/web/routers/ohlcv.py` — POST/GET endpoints
- [ ] `app/batch/daily_ohlcv_job.py` — APScheduler 등록 (KST mon-fri 18:30)
- [ ] `migrations/versions/003_ohlcv_krx.py` + `004_ohlcv_nxt.py` (분리 적용 가능)
- [ ] `scripts/backfill_ohlcv.py` — CLI

### 10.2 테스트

- [ ] Unit 14 시나리오 (§9.1) PASS
- [ ] Integration 12 시나리오 (§9.2) PASS
- [ ] coverage `KiwoomChartClient`, `IngestDailyOhlcvUseCase`, `StockPriceRepository` ≥ 80%

### 10.3 운영 검증

- [ ] 삼성전자(005930) 일봉 호출 — 1 페이지에 몇 거래일 응답하는가? (60? 600?)
- [ ] `dt` 응답이 ASC 인지 DESC 인지 — 정렬 가정 검증
- [ ] `pred_pre_sig` 값 1~5 분포 (보합 3 이 거의 안 나오는지 확인)
- [ ] `trde_prica` 단위 (백만원 가정 — 운영 검증)
- [ ] `cur_prc`, `open_pric` 등에 부호(+/-) 오는지 (Excel ka10086 예시는 부호 포함)
- [ ] NXT 응답이 KRX 와 stk_cd 어떻게 다른지 (`005930_NX` vs `005930` stripped)
- [ ] NXT 운영 시작일 이전 base_dt 호출 시 응답 패턴
- [ ] 페이지네이션 발생 빈도 (3년 백필 시 페이지 수)
- [ ] `cont-yn=Y` + `next-key` 가 어떤 형식인지 (date / index?)
- [ ] active 3000 + NXT 1500 = 4500 호출 sync 실측 시간
- [ ] partial 실패율 (1주 모니터)

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10081 daily OHLCV ingest (KRX + NXT separated)`
- [ ] `master.md` § 12 결정 기록에:
  - `dt` 정렬 (ASC/DESC) 확정
  - `trde_prica` 단위 확정
  - 1 페이지 row 수 / 페이지네이션 빈도
  - NXT 응답 stk_cd 형식
  - active 3000 + NXT 1500 sync 실측 소요 시간

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | KRX/NXT 호출 순서 | (a) 직렬 (KRX → NXT) (현재) / (b) 병렬 (asyncio.gather) | Phase C 후반 — RPS 측정 후 |
| 2 | adjusted=true 만 적재 vs 양쪽 | (a) adjusted=true 만 (권장) / (b) raw 도 별도 row | 백테스팅 1차에는 (a) |
| 3 | 백필 page 전략 | (a) base_dt 만 한 번 / (b) 응답 가장 오래된 날 - 1일을 다음 base_dt 로 반복 | 1 페이지 row 수 확인 후 |
| 4 | NXT 운영 시작일 가드 | (a) 호출 전 가드 (b) 응답 0 row 로 자연 처리 (현재) | 운영 검증 후 |
| 5 | KRX vs NXT mirror 검증 | (a) 같은 날 close 차이 ±0.001% 이하 시 NXT mirror 의심 alert / (b) 미검증 | Phase C 후 데이터 품질 리포트에서 |
| 6 | 일 1회 cron 시간 | 18:30 (현재) / 19:00 / 다른 batch 와 겹침 회피 | Phase C 후반 |
| 7 | bulk batch 크기 (50) | 100 / 200 — commit 빈도 | 실측 후 |

### 11.2 알려진 위험

- **`cur_prc` 가 "현재가" 이름이지만 일봉 응답에서는 "그 일자 종가"** 로 해석. 이름 ↔ 의미 불일치 — 영속화 컬럼명은 `close_price` 로 명확화
- **`dt` 정렬 가정 미검증**: ASC (오래된 → 최신) 인지 DESC 인지 운영 검증 필요. 백테스팅 엔진의 시계열 가정에 영향
- **`pred_pre`, `pred_pre_sig`, `trde_tern_rt` 가 일봉에 의미 있는가**: 이 필드들은 "전일 대비" — 일봉의 경우 그 날의 전일 대비 (KRX 의 OHLC 와 별개로 거래소 메타데이터). 백테스팅에는 불필요할 수 있음 — 일단 적재
- **NXT 응답 stk_cd 형식 미확정**: 요청 `005930_NX` → 응답이 어떻게 오는지 (Excel R30 은 Length=6 으로 명시 — `_NX` stripped 추정). `strip_kiwoom_suffix` 안전망 필수
- **수정주가 적용 보장**: `upd_stkpc_tp=1` 이 정확히 KRX 의 수정주가와 같은지, 키움 자체 수정주가인지 운영 검증 — `pykrx` close_price 와 비교 검증 ±1 KRW 이내 확인
- **NXT 운영 시작일 데이터**: NXT 거래소 ~2025-03 시작 추정. 그 이전 base_dt 의 NXT 호출 응답이 빈 list 인지 에러인지 검증 필수
- **3년 백필의 페이지 수**: 키움 응답이 1 페이지 600 거래일이면 3년 = 720 거래일 = 2 페이지. 60 거래일이면 12 페이지 — 백필 시간 차이가 큼
- **`stock_price_combined` view 성능**: UNION ALL 이 인덱스 스캔 두 번이라 느릴 수 있음 — 백테스팅 hot path 면 materialized view 검토
- **금융 데이터 정합성**: 같은 종목·같은 날의 KRX OHLC 가 키움 vs `pykrx` 사이에 차이 있을 수 있음. 데이터 품질 리포트 (§ 10.3) 가 필수
- **bulk commit 중간 오류**: 50건 batch 후 commit 실패 시 다음 batch 진입 불가 — try/except + alert 필요. Phase B 의 SAVEPOINT 패턴 동일
- **시간대 (KST)**: `dt` 가 KST 거래일이라고 가정. UTC 변환 시 일자 어긋남 주의 — DATE 컬럼이 timezone-naive 라 KST 만 사용

### 11.3 ka10081 vs ka10082/83/94 비교

| 항목 | ka10081 일봉 | ka10082 주봉 | ka10083 월봉 | ka10094 년봉 |
|------|---------|--------|--------|--------|
| URL | /api/dostk/chart | 동일 | 동일 | 동일 |
| Request | stk_cd + base_dt + upd_stkpc_tp | 동일 | 동일 | 동일 |
| Response list 키 | `stk_dt_pole_chart_qry` | `stk_stk_pole_chart_qry` | `stk_mth_pole_chart_qry` | `stk_yr_pole_chart_qry` |
| 응답 필드 수 | 10 | 10 | 10 | **7** (pred_pre/pred_pre_sig/trde_tern_rt 없음) |
| 영속화 테이블 | stock_price_krx/nxt | stock_price_weekly_krx/nxt | stock_price_monthly_krx/nxt | stock_price_yearly_krx/nxt |
| 백테스팅 우선순위 | **P0** | P1 | P1 | P2 |

→ ka10082/83 는 본 계획서의 **거의 완전 복제**. ka10094 만 응답 필드 7개로 컬럼 일부 제외. 4 endpoint 모두 같은 `KiwoomChartClient` 의 메서드 4개 + 비슷한 ORM 4쌍.

### 11.4 ka10086 과의 차이

| 항목 | ka10081 | ka10086 |
|------|---------|---------|
| URL | /api/dostk/chart | **/api/dostk/mrkcond** |
| 카테고리 | 차트 (시세 시계열) | 시세 (일별주가 + 투자자 흐름) |
| Request body | base_dt | qry_dt + indc_tp(0:수량/1:금액) |
| 응답 필드 수 | 10 | **22** |
| 추가 정보 | OHLCV + 거래대금/회전율 | OHLCV + **투자자별 net** + **외인 비중/보유** + **신용비** |
| 영속화 테이블 | stock_price_* | **stock_daily_flow** (별도) |
| 호출 부담 | 일봉 (light) | heavier — 22 필드 |

→ ka10086 은 OHLCV 를 중복 적재하지 않음. **ka10081 의 OHLCV 가 정답** + ka10086 의 투자자별 + 외인 + 신용 필드만 stock_daily_flow 에 별도 적재. (endpoint-10 계획서에서 결정)

### 11.5 향후 확장

- **백테스팅 엔진의 read API**: `StockPriceRepository.get_range` 가 단일 종목. 다종목 batch read 는 별도 메서드 (Phase H 통합 단계)
- **데이터 품질 리포트**: KRX vs NXT 가격 차이 분포, KRX vs `pykrx` 일치율, partial 실패 누적 — Phase H
- **분봉/틱 (ka10079/10080)**: 본 endpoint 가 안정 작동하면 Phase D 에서 동일 패턴 + tic_scope 추가
- **수정주가 raw 비교**: adjusted=False 도 일부 종목 적재해 액면분할 영향 검증 — Phase H
- **장중 호출**: 14:00 KST 등 장중 호출로 실시간 시계열 — 본 Phase 범위 외

---

_Phase C 의 첫 endpoint, 그리고 백테스팅의 코어. 본 endpoint 가 안정 작동해야 Phase D~G 의 보강 데이터(분봉/순위/투자자별) 가 의미를 가진다. ka10082/83/94 는 본 계획서의 패턴 복제로 빠르게 완성 가능._
