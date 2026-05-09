# endpoint-10-ka10086.md — 일별주가요청 (OHLCV + 투자자별 + 외인 + 신용)

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10086` |
| API 명 | 일별주가요청 |
| 분류 | Tier 3 (백테스팅 시그널 보강 — 투자자별 + 외인 + 신용) |
| Phase | **C** |
| 우선순위 | **P0** (백테스팅 시그널 핵심) |
| Method | `POST` |
| URL | **`/api/dostk/mrkcond`** (chart 가 아님!) |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX 만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| 의존 endpoint | `au10001`, `ka10099`(stock + nxt_enable) |
| 관련 endpoint | `ka10081`(일봉) — OHLCV 는 ka10081 가 정답. 본 endpoint 는 **투자자별 + 외인 + 신용 필드만** stock_daily_flow 적재 |

---

## 1. 목적

일별 단위로 **22 필드**: OHLCV + 거래대금 + 등락률 + 신용비 + 외인 비율/보유/비중/순매수 + 개인/기관/외국계 net + 프로그램 + 신용잔고율.

**ka10081 와의 결정적 차이**: ka10081 은 **시계열 백테스팅 코어 OHLCV**, ka10086 은 **시그널 보강** (투자자별 흐름 / 외인 / 신용). URL 도 다름 (`/mrkcond` vs `/chart`).

**왜 P0**:
- 투자자별 net (개인/기관/외인) 은 백테스팅의 **수급 시그널 핵심 입력**
- 외인 비율 / 외인 보유 / 신용비 / 신용잔고율 은 모멘텀·과열 판정 시그널
- ka10081 OHLCV 만으로 백테스팅 가능하지만 **수급 시그널 없으면 단순 가격 추세 분석에 그침**

**ka10081 와의 데이터 중첩 처리**:
- OHLCV (open/high/low/close/volume) 는 양쪽 응답에 모두 등장 → **ka10081 적재값을 정답** 으로 채택
- ka10086 의 stock_daily_flow 테이블에는 **OHLCV 영속화 안 함** (또는 cross-check only)
- ka10086 고유 필드 (투자자별 + 외인 + 신용) 만 영속화

---

## 2. Request 명세

### 2.1 Header

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `api-id` | TR 명 | String | Y | 10 | `"ka10086"` 고정 |
| `authorization` | 접근토큰 | String | Y | 1000 | `Bearer <token>` |
| `cont-yn` | 연속조회 여부 | String | N | 1 | 페이지네이션 |
| `next-key` | 연속조회 키 | String | N | 50 | |

### 2.2 Body

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `stk_cd` | 종목코드 | String | Y | **20** | KRX `005930`, NXT `005930_NX`, SOR `005930_AL` |
| `qry_dt` | 조회일자 | String | Y | 8 | `YYYYMMDD` (이 날짜 이후 시계열 응답 — ka10081 와 같은 의미) |
| `indc_tp` | 표시구분 | String | Y | 1 | `0`=수량 / `1`=금액(백만원) |

> **ka10081 와의 차이**: `base_dt` → `qry_dt`, `upd_stkpc_tp` → `indc_tp`. 의미도 다름 (수정주가 → 표시 단위).

### 2.3 Pydantic 모델

```python
# app/adapter/out/kiwoom/mrkcond.py
class DailyStockMarketRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    stk_cd: Annotated[str, Field(min_length=6, max_length=20)]
    qry_dt: Annotated[str, Field(pattern=r"^\d{8}$")]
    indc_tp: Literal["0", "1"]


class DailyMarketDisplayMode(StrEnum):
    """indc_tp 의미. 백테스팅 시그널은 투자자별 net 의 단위 일관성을 위해 항상 같은 값."""
    QUANTITY = "0"     # 주식수
    AMOUNT = "1"       # 백만원
```

> **백테스팅 시그널 권장**: `indc_tp=0` (수량 단위). 외인 보유/비중 같은 비율 필드는 단위 무관. 투자자별 net 은 수량 기준이 다른 종목 비교에 안정적 (가격 변동 무관).

### 2.4 Request 예시 (Excel R54)

```json
POST https://api.kiwoom.com/api/dostk/mrkcond
Content-Type: application/json;charset=UTF-8
api-id: ka10086

{
    "stk_cd": "005930",
    "qry_dt": "20241125",
    "indc_tp": "0"
}
```

---

## 3. Response 명세

### 3.1 Header

| Element | Description |
|---------|-------------|
| `api-id` | `"ka10086"` 에코 |
| `cont-yn` | `Y` 면 다음 페이지 |
| `next-key` | 다음 호출 헤더 |

### 3.2 Body — 22 필드 (5 카테고리)

| Element | 한글명 | 영속화 컬럼 | 카테고리 | 메모 |
|---------|-------|-------------|----------|------|
| `daly_stkpc[]` | 일별주가 list | — | — | 페이지 단위 array |
| `date` | 날짜 | `trading_date` (DATE) | A.시점 | YYYYMMDD |
| `open_pric` | 시가 | `open_price` (BIGINT) | B.OHLCV | KRW. 부호 포함 (예: `+78800`) |
| `high_pric` | 고가 | `high_price` (BIGINT) | B.OHLCV | |
| `low_pric` | 저가 | `low_price` (BIGINT) | B.OHLCV | |
| `close_pric` | 종가 | `close_price` (BIGINT) | B.OHLCV | |
| `pred_rt` | 전일비 | `prev_compare_amount` (BIGINT) | B.OHLCV | KRW. ka10081 의 `pred_pre` 와 동일 |
| `flu_rt` | 등락률 | `change_rate` (NUMERIC(8,4)) | B.OHLCV | % |
| `trde_qty` | 거래량 | `trade_volume` (BIGINT) | B.OHLCV | 주 |
| `amt_mn` | 금액(백만원) | `trade_amount_mn` (BIGINT) | B.OHLCV | **백만원 단위 명시** |
| `crd_rt` | 신용비 | `credit_rate` (NUMERIC(8,4)) | C.신용 | % |
| `crd_remn_rt` | 신용잔고율 | `credit_balance_rate` (NUMERIC(8,4)) | C.신용 | % |
| `ind` | 개인 | `individual_net` (BIGINT) | D.투자자별 | indc_tp=0 면 수량, =1 면 백만원. 부호 포함 |
| `orgn` | 기관 | `institutional_net` (BIGINT) | D.투자자별 | |
| `frgn` | 외국계 | `foreign_brokerage_net` (BIGINT) | D.투자자별 | |
| `prm` | 프로그램 | `program_net` (BIGINT) | D.투자자별 | 프로그램 매매 |
| `for_qty` | 외인수량 | `foreign_volume` (BIGINT) | E.외인 | 외인 거래량 |
| `for_rt` | 외인비 | `foreign_rate` (NUMERIC(8,4)) | E.외인 | 거래대비 외인 비율 % |
| `for_poss` | 외인보유 | `foreign_holdings` (BIGINT) | E.외인 | 외인 보유 주식 수 (누적) |
| `for_wght` | 외인비중 | `foreign_weight` (NUMERIC(8,4)) | E.외인 | 외인 보유 비중 % |
| `for_netprps` | 외인순매수 | `foreign_net_purchase` (BIGINT) | E.외인 | **외인 net (Excel R15 주의: 수량으로만 응답)** |
| `orgn_netprps` | 기관순매수 | `institutional_net_purchase` (BIGINT) | E.외인 | |
| `ind_netprps` | 개인순매수 | `individual_net_purchase` (BIGINT) | E.외인 | |

### 3.3 카테고리 분리 의미

- **A. 시점**: trading_date (FK)
- **B. OHLCV** (8 필드): ka10081 와 100% 중첩 → **본 테이블에 영속화 안 함** (또는 cross-check only)
- **C. 신용** (2 필드): 신용 거래 시그널 (단기 과열 / 매도 압력)
- **D. 투자자별** (4 필드): 일별 자금 흐름 (수급 시그널의 핵심)
- **E. 외인 + 순매수** (7 필드): 외인 누적 보유 + 일별 net 매매

→ **stock_daily_flow 테이블에 적재할 필드: C + D + E = 13 필드** (B 제외).

### 3.4 Excel R15 주의 (R56 응답 예시)

> **외국인순매수 데이터는 거래소로부터 금액데이터가 제공되지 않고 수량으로만 조회됩니다.**

→ `indc_tp=1` (금액 모드) 호출해도 `for_netprps`/`orgn_netprps`/`ind_netprps` 는 **수량**. 단위 mismatch 주의 — 별도 컬럼 분기 필요 가능성.

### 3.5 Response 예시 (Excel R56 일부)

```json
{
    "daly_stkpc": [
        {
            "date": "20241125",
            "open_pric": "+78800",
            "high_pric": "+101100",
            "low_pric": "-54500",
            "close_pric": "-55000",
            "pred_rt": "-22800",
            "flu_rt": "-29.31",
            "trde_qty": "20278",
            "amt_mn": "1179",
            "crd_rt": "0.00",
            "ind": "--714",
            "orgn": "+693",
            "for_qty": "--266783",
            "frgn": "0",
            "prm": "0",
            ...
        }
    ]
}
```

> **주의**: Excel 예시에 `ind="--714"`, `for_qty="--266783"` 처럼 **이중 부호** 등장. 단순 표기 오류 또는 "표시 부호 + 음수 값" 의 혼합. 운영 검증 필수.

### 3.6 Pydantic 모델

```python
# app/adapter/out/kiwoom/_records.py
class DailyMarketRow(BaseModel):
    """ka10086 응답 row — 22 필드."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    date: str = ""
    # OHLCV (ka10081 와 중첩 — 본 테이블 영속화 안 함, cross-check 용)
    open_pric: str = ""
    high_pric: str = ""
    low_pric: str = ""
    close_pric: str = ""
    pred_rt: str = ""
    flu_rt: str = ""
    trde_qty: str = ""
    amt_mn: str = ""
    # 신용
    crd_rt: str = ""
    crd_remn_rt: str = ""
    # 투자자별
    ind: str = ""
    orgn: str = ""
    frgn: str = ""
    prm: str = ""
    # 외인
    for_qty: str = ""
    for_rt: str = ""
    for_poss: str = ""
    for_wght: str = ""
    for_netprps: str = ""
    orgn_netprps: str = ""
    ind_netprps: str = ""

    def to_normalized(
        self,
        *,
        stock_id: int,
        exchange: ExchangeType,
        indc_mode: DailyMarketDisplayMode,
    ) -> "NormalizedDailyFlow":
        return NormalizedDailyFlow(
            stock_id=stock_id,
            trading_date=_parse_yyyymmdd(self.date) or date.min,
            exchange=exchange,
            indc_mode=indc_mode,
            credit_rate=_to_decimal(self.crd_rt),
            credit_balance_rate=_to_decimal(self.crd_remn_rt),
            individual_net=_strip_double_sign_int(self.ind),
            institutional_net=_strip_double_sign_int(self.orgn),
            foreign_brokerage_net=_strip_double_sign_int(self.frgn),
            program_net=_strip_double_sign_int(self.prm),
            foreign_volume=_strip_double_sign_int(self.for_qty),
            foreign_rate=_to_decimal(self.for_rt),
            foreign_holdings=_to_int(self.for_poss),
            foreign_weight=_to_decimal(self.for_wght),
            # Excel R15: 외인/기관/개인 순매수는 indc_tp 무시하고 항상 수량
            foreign_net_purchase=_strip_double_sign_int(self.for_netprps),
            institutional_net_purchase=_strip_double_sign_int(self.orgn_netprps),
            individual_net_purchase=_strip_double_sign_int(self.ind_netprps),
        )


def _strip_double_sign_int(s: str) -> int | None:
    """Excel 예시의 '--714' 같은 이중 부호 처리.

    `--714` → -714 (또는 +714? 운영 검증 필요)
    `+693` → 693
    빈값 → None
    """
    if not s or s.strip() in ("-", "+", "--"):
        return None
    s = s.strip().replace(",", "")
    # 이중 부호 검출
    if s.startswith("--"):
        # 가설 A: '-' + 음수값 = 더 큰 음수 의미
        # 가설 B: '-' 표시 + '-' 부호 (즉 음수)
        # 권장: 운영 첫 호출 raw 응답 측정 후 결정. 일단 가설 B 채택.
        return _to_int(s[1:])     # "-714"
    if s.startswith("++"):
        return _to_int(s[1:])
    return _to_int(s)


class DailyMarketResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    daly_stkpc: list[DailyMarketRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""


@dataclass(frozen=True, slots=True)
class NormalizedDailyFlow:
    stock_id: int
    trading_date: date
    exchange: ExchangeType
    indc_mode: DailyMarketDisplayMode
    credit_rate: Decimal | None
    credit_balance_rate: Decimal | None
    individual_net: int | None
    institutional_net: int | None
    foreign_brokerage_net: int | None
    program_net: int | None
    foreign_volume: int | None
    foreign_rate: Decimal | None
    foreign_holdings: int | None
    foreign_weight: Decimal | None
    foreign_net_purchase: int | None       # 항상 수량 (Excel R15)
    institutional_net_purchase: int | None  # 항상 수량 (R15 가정)
    individual_net_purchase: int | None     # 항상 수량 (R15 가정)
```

---

## 4. NXT 처리

| 항목 | 적용 여부 |
|------|-----------|
| `stk_cd` 에 `_NX` suffix | **Y** (Length=20) |
| `nxt_enable` 게이팅 | **Y** |
| `mrkt_tp` 별 분리 | N |
| KRX 운영 / 모의 차이 | mockapi 는 KRX 전용 |

### 4.1 KRX/NXT 분리 적재 의미

ka10081 와 동일 — KRX/NXT 의 거래량/투자자별 net 이 분리됨. 같은 종목·같은 날에:
- KRX 의 `for_netprps` = KRX 거래소 외인 순매수
- NXT 의 `for_netprps` = NXT 거래소 외인 순매수

→ stock_daily_flow 의 UNIQUE 가 `(stock_id, trading_date, exchange)` 로 KRX/NXT 분리 row.

---

## 5. DB 스키마

### 5.1 신규 테이블 — Migration 005 (`005_stock_daily_flow.py`)

> Migration 003/004 (OHLCV) 와 분리. ka10086 만의 stock_daily_flow 는 별도 마이그레이션.

```sql
CREATE TABLE kiwoom.stock_daily_flow (
    id                          BIGSERIAL PRIMARY KEY,
    stock_id                    BIGINT NOT NULL REFERENCES kiwoom.stock(id) ON DELETE CASCADE,
    trading_date                DATE NOT NULL,
    exchange                    VARCHAR(4) NOT NULL,                 -- KRX / NXT
    indc_mode                   CHAR(1) NOT NULL,                    -- 0=수량 / 1=금액(백만원)

    -- C. 신용
    credit_rate                 NUMERIC(8, 4),
    credit_balance_rate         NUMERIC(8, 4),

    -- D. 투자자별 net (단위 indc_mode 따름)
    individual_net              BIGINT,
    institutional_net           BIGINT,
    foreign_brokerage_net       BIGINT,
    program_net                 BIGINT,

    -- E. 외인 + 순매수
    foreign_volume              BIGINT,
    foreign_rate                NUMERIC(8, 4),
    foreign_holdings            BIGINT,
    foreign_weight              NUMERIC(8, 4),
    foreign_net_purchase        BIGINT,                              -- 항상 수량 (R15)
    institutional_net_purchase  BIGINT,                              -- 항상 수량 (R15 가정)
    individual_net_purchase     BIGINT,                              -- 항상 수량 (R15 가정)

    fetched_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_daily_flow_stock_date_exchange
        UNIQUE (stock_id, trading_date, exchange)
);

CREATE INDEX idx_daily_flow_trading_date ON kiwoom.stock_daily_flow(trading_date);
CREATE INDEX idx_daily_flow_stock_id ON kiwoom.stock_daily_flow(stock_id);
CREATE INDEX idx_daily_flow_exchange ON kiwoom.stock_daily_flow(exchange);
```

### 5.2 ORM 모델

```python
# app/adapter/out/persistence/models/stock_daily_flow.py
class StockDailyFlow(Base):
    __tablename__ = "stock_daily_flow"
    __table_args__ = (
        UniqueConstraint("stock_id", "trading_date", "exchange",
                          name="uq_daily_flow_stock_date_exchange"),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("kiwoom.stock.id", ondelete="CASCADE"), nullable=False
    )
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    exchange: Mapped[str] = mapped_column(String(4), nullable=False)
    indc_mode: Mapped[str] = mapped_column(String(1), nullable=False)

    credit_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    credit_balance_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    individual_net: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    institutional_net: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    foreign_brokerage_net: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    program_net: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    foreign_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    foreign_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    foreign_holdings: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    foreign_weight: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    foreign_net_purchase: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    institutional_net_purchase: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    individual_net_purchase: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

### 5.3 OHLCV 중복 적재 안 함

ka10086 응답의 8 OHLCV 필드 (open_pric ~ amt_mn) 는 stock_daily_flow 에 영속화 안 함. 정답은 ka10081 의 stock_price_krx/nxt.

대신 `raw_response` 테이블에는 응답 전체 JSON 저장 — 추후 디버깅이나 ka10081 vs ka10086 OHLCV 비교 시 활용.

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomMarketCondClient.fetch_daily_market`

```python
# app/adapter/out/kiwoom/mrkcond.py
class KiwoomMarketCondClient:
    """`/api/dostk/mrkcond` 계열. ka10086 만 우선 — 후속 endpoint 추가 시 같은 클래스에 메서드."""

    PATH = "/api/dostk/mrkcond"

    def __init__(self, kiwoom_client: KiwoomClient) -> None:
        self._client = kiwoom_client

    async def fetch_daily_market(
        self,
        stock_code: str,
        *,
        query_date: date,
        exchange: ExchangeType = ExchangeType.KRX,
        indc_mode: DailyMarketDisplayMode = DailyMarketDisplayMode.QUANTITY,
        max_pages: int = 10,
    ) -> list[DailyMarketRow]:
        """ka10086 호출. cont-yn 페이지네이션 자동."""
        if not (len(stock_code) == 6 and stock_code.isdigit()):
            raise ValueError(f"stock_code 6자리 숫자만: {stock_code}")
        stk_cd = build_stk_cd(stock_code, exchange)
        body = {
            "stk_cd": stk_cd,
            "qry_dt": query_date.strftime("%Y%m%d"),
            "indc_tp": indc_mode.value,
        }

        all_rows: list[DailyMarketRow] = []
        async for page in self._client.call_paginated(
            api_id="ka10086",
            endpoint=self.PATH,
            body=body,
            max_pages=max_pages,
        ):
            parsed = DailyMarketResponse.model_validate(page.body)
            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id="ka10086",
                    return_code=parsed.return_code,
                    return_msg=parsed.return_msg,
                )
            all_rows.extend(parsed.daly_stkpc)
        return all_rows
```

### 6.2 Repository

```python
# app/adapter/out/persistence/repositories/stock_daily_flow.py
class StockDailyFlowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, rows: Sequence[NormalizedDailyFlow]) -> int:
        if not rows:
            return 0
        valid = [r for r in rows if r.trading_date != date.min]
        if not valid:
            return 0
        values = [
            {
                "stock_id": r.stock_id,
                "trading_date": r.trading_date,
                "exchange": r.exchange.value,
                "indc_mode": r.indc_mode.value,
                "credit_rate": r.credit_rate,
                "credit_balance_rate": r.credit_balance_rate,
                "individual_net": r.individual_net,
                "institutional_net": r.institutional_net,
                "foreign_brokerage_net": r.foreign_brokerage_net,
                "program_net": r.program_net,
                "foreign_volume": r.foreign_volume,
                "foreign_rate": r.foreign_rate,
                "foreign_holdings": r.foreign_holdings,
                "foreign_weight": r.foreign_weight,
                "foreign_net_purchase": r.foreign_net_purchase,
                "institutional_net_purchase": r.institutional_net_purchase,
                "individual_net_purchase": r.individual_net_purchase,
            }
            for r in valid
        ]

        stmt = pg_insert(StockDailyFlow).values(values)
        update_set = {
            col: stmt.excluded[col] for col in values[0]
            if col not in ("stock_id", "trading_date", "exchange")
        }
        update_set["fetched_at"] = func.now()
        update_set["updated_at"] = func.now()
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_id", "trading_date", "exchange"],
            set_=update_set,
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return rowcount_of(result)

    async def get_range(
        self,
        stock_id: int,
        *,
        exchange: ExchangeType,
        start_date: date,
        end_date: date,
    ) -> list[StockDailyFlow]:
        stmt = (
            select(StockDailyFlow)
            .where(
                StockDailyFlow.stock_id == stock_id,
                StockDailyFlow.exchange == exchange.value,
                StockDailyFlow.trading_date >= start_date,
                StockDailyFlow.trading_date <= end_date,
            )
            .order_by(StockDailyFlow.trading_date)
        )
        return list((await self._session.execute(stmt)).scalars())
```

### 6.3 UseCase — `IngestDailyFlowUseCase`

```python
# app/application/service/daily_flow_service.py
class IngestDailyFlowUseCase:
    """단일 종목·단일 거래소 일별 수급 적재.

    indc_mode 기본 = QUANTITY (수량) — 백테스팅 시그널 일관성.
    멱등성: ON CONFLICT (stock_id, trading_date, exchange) UPDATE.

    같은 indc_mode 로만 적재 권장 — 단위 mismatch 방지.
    indc_mode 변경하려면 deactivate + 재호출 필요 (별도 스크립트).
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        mrkcond_client: KiwoomMarketCondClient,
        lookup_use_case: LookupStockUseCase,
        env: Literal["prod", "mock"] = "prod",
    ) -> None:
        self._session = session
        self._client = mrkcond_client
        self._lookup = lookup_use_case
        self._stock_repo = StockRepository(session)
        self._flow_repo = StockDailyFlowRepository(session)
        self._env = env

    async def execute(
        self,
        stock_code: str,
        *,
        query_date: date,
        exchange: ExchangeType = ExchangeType.KRX,
        indc_mode: DailyMarketDisplayMode = DailyMarketDisplayMode.QUANTITY,
    ) -> DailyFlowIngestOutcome:
        # mock + NXT 가드
        if self._env == "mock" and exchange is ExchangeType.NXT:
            return DailyFlowIngestOutcome(
                stock_code=stock_code, exchange=exchange,
                skipped=True, reason="mock_no_nxt",
            )

        stock = await self._lookup.ensure_exists(stock_code)
        if not stock.is_active:
            return DailyFlowIngestOutcome(
                stock_code=stock_code, exchange=exchange,
                skipped=True, reason="inactive",
            )
        if exchange is ExchangeType.NXT and not stock.nxt_enable:
            return DailyFlowIngestOutcome(
                stock_code=stock_code, exchange=exchange,
                skipped=True, reason="nxt_disabled",
            )

        try:
            raw_rows = await self._client.fetch_daily_market(
                stock_code, query_date=query_date,
                exchange=exchange, indc_mode=indc_mode,
            )
        except KiwoomBusinessError as exc:
            return DailyFlowIngestOutcome(
                stock_code=stock_code, exchange=exchange,
                error=f"business: {exc.return_code}",
            )

        normalized = [
            r.to_normalized(stock_id=stock.id, exchange=exchange, indc_mode=indc_mode)
            for r in raw_rows
        ]
        upserted = await self._flow_repo.upsert_many(normalized)

        return DailyFlowIngestOutcome(
            stock_code=stock_code, exchange=exchange,
            fetched=len(raw_rows), upserted=upserted,
        )


@dataclass(frozen=True, slots=True)
class DailyFlowIngestOutcome:
    stock_code: str
    exchange: ExchangeType
    fetched: int = 0
    upserted: int = 0
    skipped: bool = False
    reason: str | None = None
    error: str | None = None
```

### 6.4 Bulk + 백필

`IngestDailyFlowBulkUseCase` 는 ka10081 의 `IngestDailyOhlcvBulkUseCase` 패턴 복제. KRX + NXT 둘 다 호출.

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **수동 단건** | on-demand | `POST /api/kiwoom/daily-flow/{stock_code}/sync?date=...&exchange=KRX` |
| **수동 일괄** | on-demand | `POST /api/kiwoom/daily-flow/sync` |
| **일 1회 cron** | KST 19:00 평일 | ka10081 (18:30) 직후 — OHLCV 가 먼저 적재되어야 cross-check 의미 |
| **백필** | on-demand | `python scripts/backfill_daily_flow.py --start 2023-01-01 --end 2026-05-07` |

```python
# app/batch/daily_flow_job.py
async def fire_daily_flow_sync() -> None:
    today = date.today()
    if not is_trading_day(today):
        return
    try:
        async with get_sessionmaker()() as session:
            kiwoom_client = build_kiwoom_client_for("prod-main")
            mrkcond = KiwoomMarketCondClient(kiwoom_client)
            stkinfo = KiwoomStkInfoClient(kiwoom_client)
            lookup = LookupStockUseCase(
                session, stkinfo_client=stkinfo, env=settings.kiwoom_default_env,
            )
            single = IngestDailyFlowUseCase(
                session, mrkcond_client=mrkcond, lookup_use_case=lookup,
                env=settings.kiwoom_default_env,
            )
            bulk = IngestDailyFlowBulkUseCase(session, single_use_case=single)
            result = await bulk.execute(query_date=today)
        logger.info(
            "daily_flow sync 완료 query_date=%s krx_success=%d nxt_success=%d rows=%d",
            today, result.krx_success, result.nxt_success, result.total_rows_inserted,
        )
    except Exception:
        logger.exception("daily_flow_sync 콜백 예외")


scheduler.add_job(
    fire_daily_flow_sync,
    CronTrigger(day_of_week="mon-fri", hour=19, minute=0, timezone=KST),
    id="daily_flow",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
    misfire_grace_time=60 * 90,
)
```

### 7.1 RPS / 시간 추정

ka10081 와 호출 수 동일 (KRX 3000 + NXT 1500 = 4500). 페이지네이션 발생 시 더 길어짐.

→ ka10081 (18:30 ~) + ka10086 (19:00 ~) = 2시간 슬롯 안에 두 batch 완료 권장. 19:00 이 너무 빠르면 19:30 으로 조정.

---

## 8. 에러 처리

ka10081 § 8 과 동일 + 본 endpoint 추가:

| 시나리오 | 처리 |
|---------|------|
| 응답 row 의 `--714` 이중 부호 | `_strip_double_sign_int` 가 `-` prefix 1개 제거 후 `_to_int` |
| `for_netprps` 등이 `indc_tp=1` 모드인데 수량값 (R15 주의) | 정규화 단계에서 무시. 단 stock_daily_flow 의 `*_net_purchase` 컬럼이 항상 수량인 점을 주석에 명시 |
| `for_poss` (외인 보유) 가 누적치 | 일별 변화를 알려면 diff 계산 필요 — 본 endpoint 는 raw 적재만 |

---

## 9. 테스트

### 9.1 Unit (MockTransport)

`tests/adapter/kiwoom/test_mrkcond_daily_market.py`:

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 단일 페이지 | 200 + daly_stkpc 5건 | 5건 반환 |
| 페이지네이션 | cont-yn=Y → N | 2회 호출, 합쳐짐 |
| `return_code=1` | 비즈니스 에러 | KiwoomBusinessError |
| `for_netprps="--714"` 이중 부호 | 정상 응답 | normalized.foreign_net_purchase = -714 (가설 B) |
| `for_netprps="+5000"` | 정상 부호 | 5000 |
| 빈 응답 | daly_stkpc=[] | 빈 list |
| stk_cd "00593" | 호출 차단 | ValueError |
| ExchangeType.NXT | stk_cd build | request body `stk_cd="005930_NX"` |
| indc_mode=AMOUNT (1) | request body | `indc_tp="1"` |
| 22 필드 모두 빈값 | 응답 모두 "" | normalized 의 모든 필드 None |
| 응답에 추가 신규 필드 | extra="ignore" | 통과 |
| `date=""` row | upsert 단계에서 자동 skip | upserted=0 |

### 9.2 Integration (testcontainers)

`tests/application/test_daily_flow_service.py`:

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| INSERT (DB 빈) | stock 1 + 5 row 응답 | stock_daily_flow 5 row, exchange='KRX' |
| KRX + NXT 분리 적재 | nxt_enable=true 종목 + KRX 5 + NXT 5 | row 10개, exchange 별 분리 |
| 멱등성 | 같은 호출 두 번 | row 5 유지, updated_at 갱신 |
| nxt_disabled skip | 종목 nxt_enable=false + NXT 호출 | reason="nxt_disabled" |
| inactive skip | is_active=false | reason="inactive" |
| mock no NXT | env="mock" + NXT | reason="mock_no_nxt" |
| 이중 부호 처리 | `for_netprps="--12345"` | DB row.foreign_net_purchase = -12345 |
| indc_mode 변경 시도 | 같은 (stock, date, exchange) 의 indc_mode=0 row 후 indc_mode=1 호출 | UPDATE — `indc_mode` 갱신 (단위 mismatch 의 위험은 documentation 의 책임) |
| 외인 누적 보유 추적 | 두 다른 일자의 for_poss diff | 본 endpoint 는 raw 만 — diff 는 백테스팅 엔진 |

### 9.3 ka10081 vs ka10086 OHLCV cross-check (optional)

```python
@pytest.mark.requires_kiwoom_real
async def test_ohlcv_consistency_between_endpoints():
    """ka10081 와 ka10086 의 같은 일자 OHLCV 가 일치하는지 — 데이터 source 신뢰도."""
    # ka10081 일봉 호출
    # ka10086 일별주가 호출
    # close_price 일치 (±0 KRW), volume 일치 (±0 주) 검증
    pass
```

---

## 10. 완료 기준 (DoD)

### 10.1 코드

**C-2α (인프라, 커밋 `cddd268`)**:
- [x] `app/adapter/out/kiwoom/mrkcond.py` — `KiwoomMarketCondClient.fetch_daily_market` (C-1α 2R H-1 cross-stock pollution 차단 적용)
- [x] `app/adapter/out/kiwoom/_records.py` — `DailyMarketRow`, `DailyMarketResponse`, `NormalizedDailyFlow`, `_strip_double_sign_int` (가설 B)
- [x] `app/application/constants.py` — `DailyMarketDisplayMode` StrEnum + `EXCHANGE_TYPE_MAX_LENGTH=4` Final (2b-M2)
- [x] `app/adapter/out/persistence/models/stock_daily_flow.py` — `StockDailyFlow` ORM
- [x] `app/adapter/out/persistence/repositories/stock_daily_flow.py` — `StockDailyFlowRepository` (`_SUPPORTED_EXCHANGES = {KRX, NXT}` 2b-M1)
- [x] `migrations/versions/007_kiwoom_stock_daily_flow.py` (007 — 005/006 은 stock_price)

**C-2β (자동화, 완료)**:
- [x] `app/application/service/daily_flow_service.py` — `IngestDailyFlowUseCase` + `DailyFlowSyncOutcome` + `DailyFlowSyncResult`
- [x] `app/adapter/web/routers/daily_flow.py` — POST `/daily-flow/sync` + POST `/stocks/{code}/daily-flow/refresh` + GET `/stocks/{code}/daily-flow`
- [x] `app/batch/daily_flow_job.py` — `fire_daily_flow_sync` (실패율 10% 알람)
- [x] `app/scheduler.py` — `DailyFlowScheduler` (KST mon-fri 19:00)
- [x] `app/adapter/web/_deps.py` 확장 — `IngestDailyFlowUseCaseFactory` + get/set/reset
- [x] `app/config/settings.py` — `scheduler_daily_flow_sync_alias` 필드
- [x] `app/main.py` 확장 — lifespan factory (indc_mode=QUANTITY) + scheduler start/shutdown + router include + reset_*
- [ ] `scripts/backfill_daily_flow.py` — CLI (C-1β 동일 방식 — 별도 chunk 보류)

### 10.2 테스트

**C-2α (인프라, 66 cases / 760 tests / 93.43% coverage)**:
- [x] Unit — `_strip_double_sign_int` 23 cases (가설 B + BIGINT overflow + 혼합/3중 부호 + edge)
- [x] Unit — `KiwoomMarketCondClient.fetch_daily_market` 15 cases (정상/exchange/페이지네이션/business error/검증/indc_mode/빈 응답/정규화/cross-stock pollution)
- [x] Unit — `DailyMarketDisplayMode` StrEnum 7 cases
- [x] Integration — Migration 007 8 cases (테이블/UNIQUE/FK/인덱스/컬럼 타입/server_default/CASCADE/downgrade 멱등)
- [x] Integration — `StockDailyFlowRepository` 13 cases (10 신규 + 3 SOR 차단 회귀)

**C-2β (자동화, 52 cases / 812 tests / 93.13% coverage, 이중 리뷰 1R PASS)**:
- [x] Integration — `IngestDailyFlowUseCase` (KRX/NXT 분리 ingest, partial failure 격리, indc_mode 전달, base_date 검증, only_market_codes 화이트리스트, refresh_one NXT 격리)
- [x] Integration — `daily_flow_router` (admin guard 401, KiwoomError 5계층 매핑, message echo 차단 회귀, GET range cap, SOR 차단)
- [x] Integration — `DailyFlowScheduler` (cron 19:00 mon-fri, 멱등성, fire 콜백 실패율 알람)
- [x] Integration — `IngestDailyFlowUseCaseFactory` deps (get/set/reset/503 fail-closed)
- [x] Integration — lifespan startup/shutdown 사이클 (test_scheduler.py 환경변수 확장 + test_stock_master_scheduler.py)

**운영 (대기)**:
- [ ] (optional) ka10081 vs ka10086 OHLCV cross-check

### 10.3 운영 검증

- [ ] 삼성전자 호출 → 22 필드 모두 채워짐 (특히 `for_netprps`/`orgn_netprps`/`ind_netprps`)
- [ ] **이중 부호 패턴 확정**: `--714` 가 `-714` 인지 `+714` 인지 — 같은 일자 `ind` 와 거래소 일별 net 데이터 (KOSCOM 공시 등) 비교
- [ ] `indc_tp=0` (수량) vs `indc_tp=1` (백만원) 응답 차이 — `for_netprps` 가 indc_tp 무관 수량 (R15) 인지 확정
- [ ] 외인순매수 합계 = 외인거래량 (대략) 검증 — `for_qty` ≥ |`for_netprps`|
- [ ] NXT 응답이 KRX 와 다른 net 값을 보여주는지 (NXT 거래량 분리 보장)
- [ ] 페이지네이션 빈도 (3년 백필 시)
- [ ] active 3000 + NXT 1500 = 4500 호출 sync 실측 시간 (30~60분 추정)
- [ ] partial 실패율 (1주 모니터)

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10086 daily flow ingest (investor net + foreign + credit, KRX + NXT)`
- [ ] `master.md` § 12 결정 기록에:
  - 이중 부호 (`--714`) 의미 확정
  - `for_netprps`/`orgn_netprps`/`ind_netprps` 단위 (수량 only 인지)
  - ka10081 vs ka10086 OHLCV 일치율
  - active 3000 + NXT 1500 sync 실측 소요 시간
  - 페이지네이션 빈도

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | 이중 부호 의미 | (a) `--714` = -714 (가설 B 현재) / (b) +714 / (c) 표시 부호 + 음수 | 운영 첫 호출 raw 측정 후 |
| 2 | indc_mode 기본값 | (a) QUANTITY (현재) / (b) AMOUNT / (c) 둘 다 별도 row | 백테스팅 시그널 단위 검토 후 |
| 3 | 외인순매수 단위 mismatch 처리 | (a) R15 가정대로 항상 수량 (현재) / (b) indc_tp 따름 (R15 무시) | 운영 검증 후 |
| 4 | OHLCV 중복 적재 안 함 | (a) 안 함 (현재) / (b) cross-check 컬럼 5개만 / (c) 다 적재 | Phase H 데이터 품질 단계 |
| 5 | 일 1회 cron 시간 | (a) 19:00 (현재, ka10081 18:30 + 30분) / (b) 19:30 / (c) ka10081 와 병렬 | Phase C 후반 측정 |
| 6 | for_poss 누적값 처리 | (a) raw 적재 (현재) / (b) diff 컬럼 추가 | 백테스팅 시그널 결정 |
| 7 | 페이지네이션 max_pages | 10 (현재) / 20 / 50 | 운영 실측 후 |

### 11.2 알려진 위험

- **이중 부호 (`--714`) 가 가장 큰 unknown**: Excel 예시가 너무 모호. 운영 첫 호출에서 정확한 raw 응답을 측정하고 가설 검증 필요. 잘못 처리하면 net 매매의 **부호 반전** → 백테스팅 시그널이 정반대로 동작
- **R15 주의 사항의 정확성**: 외인/기관/개인 순매수가 indc_tp 무시하고 항상 수량인지, 운영 응답에서 indc_tp=1 일 때 다른 단위로 오는지 검증 필수. 단위 mismatch 가 생기면 수십% 시그널 오차
- **`crd_rt` (신용비) 의미**: 신용 잔고 비율인지, 신용 거래 발생률인지 — 한국 거래소 일반 정의는 "전체 발행주식 대비 신용잔고 비율" 추정. master.md § 12 에 정의 명시 필요
- **`for_poss` 가 누적값**: 일별 변화는 별도 계산. 백테스팅에서 "외인 매도 시그널" 을 만들려면 diff = today - yesterday 가 필요 — 본 endpoint 는 raw 만, diff 계산은 백테스팅 엔진의 책임
- **`prm` (프로그램 매매)** 의 의미: 알고리즘 / 차익거래 / 패시브펀드 의 합. 단순 수치라 의미 분해는 별도 통계 필요
- **NXT 의 투자자별 데이터 분리 보장**: NXT 거래소가 외인/기관/개인 net 을 별도 집계하는지, 키움이 KRX 와 동일 값을 mirror 하는지 운영 검증 — 만약 mirror 라면 NXT 컬럼은 의미 약함
- **OHLCV 중복 검증**: ka10081 vs ka10086 의 같은 날 close_price 가 다르면 어느 source 가 정답인가? 키움 내부에서도 source 가 다른지 (chart vs mrkcond 카테고리) 확인 필요
- **3년 백필 시 페이지네이션**: ka10086 의 1 페이지 row 수가 ka10081 와 다를 수 있음 — 22 필드라 페이지 row 수가 더 적을 가능성 (~300 거래일 추정)
- **`indc_mode` 변경의 영향**: 같은 (stock, date, exchange) 에서 한 번 indc_mode=0 적재 후 indc_mode=1 적재하면 단위가 섞임. 별도 deactivate 컬럼 / migration 으로 안전판 필요할 수도
- **시간대**: ka10086 응답 `date` 가 KST 거래일 가정. UTC 변환 시 일자 어긋남 주의

### 11.3 ka10086 vs ka10081 비교

| 항목 | ka10081 | ka10086 |
|------|---------|---------|
| URL | /api/dostk/chart | **/api/dostk/mrkcond** |
| 카테고리 | 시계열 OHLCV | 시세 + 수급 |
| 응답 필드 | 10 | **22** |
| 영속화 테이블 | stock_price_krx/nxt | **stock_daily_flow** (별도) |
| OHLCV 적재 | **정답** | 중복 — 적재 안 함 |
| 추가 정보 | — | 신용 / 투자자별 / 외인 / 순매수 |
| 호출 부담 | light | heavier (페이지 row 수 적을 가능성) |
| Phase C 우선순위 | P0 (코어) | P0 (시그널) |
| 백테스팅 역할 | 가격 시계열 | 수급 / 외인 / 신용 시그널 |

→ 두 endpoint 가 **상호 보완** — 둘 다 P0 이지만 책임 분리 명확.

### 11.4 향후 확장

- **`for_poss` diff 컬럼**: 일별 외인 보유 변화를 별도 컬럼으로 — Phase F 시그널 단계에서 추가
- **신용 거래 패턴 시그널**: `crd_rt` 와 `crd_remn_rt` 의 추세를 시그널화 — 백테스팅 엔진의 derived feature
- **프로그램 매매 분해**: `prm` 을 차익 / 패시브 / 알고로 분해하려면 별도 endpoint 필요 (ka10086 범위 외)
- **장중 호출**: 14:00 KST 등 장중 호출로 실시간 수급 — Phase 범위 외
- **데이터 품질 리포트** (Phase H): ka10081 vs ka10086 OHLCV 일치율, 이중 부호 발생 빈도, NXT 가 KRX mirror 인지 cross-check

---

## 12. Phase C-2γ — Migration 008 (D-E 중복 컬럼 DROP)

> **추가일**: 2026-05-09 (운영 dry-run 1회차 결과 반영, ADR-0001 § 20.3 #1)
> **선행 조건**: C-2α 인프라 (`cddd268`) + C-2β 자동화 (`e442416`) + dry-run ADR (`bf7320c`) 완료
> **분류**: refactor (스키마 단순화 + 백엔드/테스트/응답 DTO 동시 정리). 외부 동작 변화 = **응답 DTO 에서 3 필드 제거** (breaking — 그러나 운영 미가동, 영향 없음)

### 12.1 배경 (운영 dry-run § 20.2 #1)

ka10086 응답에서 **D 카테고리 ↔ E 카테고리 컬럼 3쌍이 100% 동일값** (1,200/1,200 row):

| D (투자자별 net) | E (순매수) | 정규화 후 컬럼 (DROP 대상) |
|------------------|-----------|----------------------------|
| `ind` ≡ `ind_netprps` | (E) | `individual_net_purchase` |
| `orgn` ≡ `orgn_netprps` | (E) | `institutional_net_purchase` |
| `for_qty` ≡ `for_netprps` | (E) | `foreign_net_purchase` |

**결론**: stock_daily_flow 13 영속 컬럼 중 3 컬럼이 데이터 중복. 스토리지 ~23% 낭비 + ORM/Repository/DTO 3중 mapping 불필요. 13 → **10 컬럼**.

> 참고: `frgn` (외국계 brokerage) ↔ `for_netprps` 는 0% 동일 (다른 의미). `frgn` = `foreign_brokerage_net` 은 그대로 유지.

### 12.2 결정 (ADR-0001 § 20.3)

| # | 사안 | 결정 |
|---|------|------|
| 1 | D-E 중복 컬럼 3개 | **Migration 008 — DROP** (사용자 승인) |
| 2 | downgrade 정책 | **데이터 가드 + 컬럼 ADD (NULL)** — 007 와 동일 패턴. 데이터 손실 차단 우선 |
| 3 | 응답 DTO breaking | **수용** — 운영 미가동, downstream 0. C-2β 커밋(`e442416`) 이후 외부 호출 없음 |
| 4 | 명세 doc 동기화 | § 4 (필드 매핑) / § 5.1 (스키마 SQL) / § 5.2 (ORM) / § 5.3 (Repository) / § 9 (예시) 갱신 — Migration 007 그대로 두고 § 12 가 정답 |

### 12.3 영향 범위 (5 코드 + 4 테스트)

**코드 (5 files)**:

| # | 파일 | 변경 |
|---|------|------|
| 1 | `migrations/versions/008_drop_daily_flow_dup_columns.py` (신규) | UPGRADE: `DROP COLUMN` × 3. DOWNGRADE: 데이터 가드 + `ADD COLUMN` × 3 (NULL) |
| 2 | `app/adapter/out/persistence/models/stock_daily_flow.py` | `Mapped[int \| None]` 3 필드 + `__table_args__`/`Index` 영향 없음 — 단순 컬럼 정의만 제거 |
| 3 | `app/adapter/out/persistence/repositories/stock_daily_flow.py` | `_payload` 3 매핑 + `excluded` 3 매핑 제거 (총 6줄) |
| 4 | `app/adapter/out/kiwoom/_records.py` | `NormalizedDailyFlow` 3 필드 + `from_row` 3 매핑 제거. `_strip_double_sign_int` 호출은 `for_netprps`/`orgn_netprps`/`ind_netprps` raw 자체에 대해서는 더 이상 필요 없음 — D 컬럼 (`ind`/`orgn`/`for_qty`) 가 정답 (이미 normalize 됨) |
| 5 | `app/adapter/web/routers/daily_flow.py` | `_DailyFlowOut` 3 필드 제거 |

**테스트 (4 갱신 + 1 신규)**:

| # | 파일 | 변경 |
|---|------|------|
| 1 | `tests/test_migration_008.py` (신규) | (a) 007 적용 후 13 컬럼 확인 (b) 008 적용 후 10 컬럼 + 3 컬럼 부재 확인 (c) downgrade 가드 — 데이터 있을 시 RAISE (d) downgrade — 데이터 0건 시 컬럼 복원 |
| 2 | `tests/test_migration_007.py` | **유지** — 007 history 불변 보장. 13 컬럼 셋 그대로 |
| 3 | `tests/test_stock_daily_flow_repository.py` | `foreign_net_purchase`/`institutional_net_purchase`/`individual_net_purchase` kwarg + assertion 제거 (2 곳) |
| 4 | `tests/test_daily_flow_router.py` | 응답 fixture 의 3 필드 제거 (1 곳) + JSON snapshot assertion 갱신 |
| 5 | `tests/test_kiwoom_mrkcond_client.py` | `NormalizedDailyFlow` assertion 의 3 필드 제거 (1 곳). `_strip_double_sign_int` 23 cases 유지 (가설 B 회귀) |

**문서 (3)**:
- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 21 추가 (C-2γ 결과)
- `docs/plans/endpoint-10-ka10086.md` 본 doc § 4/§ 5 영향 범위만 inline 주석 (`-- C-2γ 후 DROP`) — full rewrite 지양
- `CHANGELOG.md` / `HANDOFF.md` 갱신

### 12.4 Migration 008 SQL 초안

```sql
-- UPGRADE
ALTER TABLE kiwoom.stock_daily_flow
    DROP COLUMN IF EXISTS individual_net_purchase,
    DROP COLUMN IF EXISTS institutional_net_purchase,
    DROP COLUMN IF EXISTS foreign_net_purchase;

-- DOWNGRADE (007 와 동일한 데이터 가드 패턴)
DO $$
DECLARE v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM kiwoom.stock_daily_flow;
    IF v_count > 0 THEN
        RAISE EXCEPTION 'stock_daily_flow 데이터(%건) 가 있어 downgrade 차단. 수동 백업 후 재시도.', v_count;
    END IF;
END $$;

ALTER TABLE kiwoom.stock_daily_flow
    ADD COLUMN foreign_net_purchase BIGINT,
    ADD COLUMN institutional_net_purchase BIGINT,
    ADD COLUMN individual_net_purchase BIGINT;
```

> 컬럼 순서는 downgrade 시 007 와 다르게 마지막에 추가됨 — `__table_args__` / 명시 SELECT 패턴이라 동작 무관, 데이터 0 가드라 row hydrate 위험 없음.

### 12.5 적대적 이중 리뷰 — 사전 self-check (ted-run 진입 전)

| # | 위험 | 완화 |
|---|------|------|
| H-1 | C-2β 응답 DTO 가 외부 downstream 에 노출됐다면 breaking | 운영 미가동 — `master` 외 deploy 0. HANDOFF 확인 |
| H-2 | downgrade 시 NULL 컬럼 복원 → 과거 백업 restore 불일치 | 데이터 가드로 빈 테이블만 허용. 운영 데이터 있을 시 RAISE |
| H-3 | normalize 함수에서 `_strip_double_sign_int` 호출이 더 이상 필요한가 | `_strip_double_sign_int` 자체는 `ind`/`orgn`/`for_qty` (D 카테고리, raw `--714` 형태) 정규화에 여전히 필요. 단 `for_netprps`/`orgn_netprps`/`ind_netprps` 호출 라인은 제거 (D 와 동일값이라 D 만 처리하면 됨) |
| H-4 | Migration 007 test 가 13 컬럼 hard-coded | 007 test 는 그대로 유지. 008 test 가 10 컬럼 검증. 두 test 가 마이그레이션 history 의 각 단계를 독립 검증 |
| H-5 | upsert payload 가 3 필드 제거 후 idempotent 인가 | UNIQUE (stock_id, trading_date, exchange) 그대로. payload 필드 줄어들면 ON CONFLICT 에서 더 적은 컬럼 갱신 — 의미 동일 |
| H-6 | NXT row mirror 정책 (§ 20.2 #2) 영향 | 코드 변경 없음. NXT 는 외인 컬럼 KRX 중복 그대로 — 정책 결정대로 유지 |

### 12.6 DoD (C-2γ)

**코드**:
- [ ] `migrations/versions/008_drop_daily_flow_dup_columns.py`
- [ ] `app/adapter/out/persistence/models/stock_daily_flow.py` 3 컬럼 제거
- [ ] `app/adapter/out/persistence/repositories/stock_daily_flow.py` payload + excluded 6줄 제거
- [ ] `app/adapter/out/kiwoom/_records.py` `NormalizedDailyFlow` 3 필드 + `from_row` 3 매핑 제거
- [ ] `app/adapter/web/routers/daily_flow.py` `_DailyFlowOut` 3 필드 제거

**테스트** (목표: 812 → ~810 cases / coverage 유지 ≥ 93%):
- [ ] `tests/test_migration_008.py` 신규 — 4 cases (UPGRADE 컬럼 셋 / DOWNGRADE 가드 / DOWNGRADE 컬럼 복원 / 멱등)
- [ ] `tests/test_migration_007.py` 그대로 유지 — 13 컬럼
- [ ] `tests/test_stock_daily_flow_repository.py` 갱신 (2 fixture)
- [ ] `tests/test_daily_flow_router.py` 갱신 (1 fixture + assertion)
- [ ] `tests/test_kiwoom_mrkcond_client.py` 갱신 (1 assertion 블록)
- [ ] `ruff check` + `mypy --strict` PASS

**이중 리뷰**:
- [ ] 1R PASS (Reviewer A: 스키마/마이그레이션 / Reviewer B: 응답 DTO breaking)

**문서**:
- [ ] ADR-0001 § 21 추가 (C-2γ 결과)
- [ ] CHANGELOG: `refactor(kiwoom): Phase C-2γ — Migration 008 (D-E 중복 3 컬럼 DROP, 13→10)`
- [ ] HANDOFF.md 갱신

### 12.7 다음 chunk (C-2γ 이후)

1. **C-1β/C-2β MEDIUM 일관 개선** — `errors → tuple` / `StockMasterNotFoundError` 전용 예외 (§ 19.5 + C-1β 동일 이슈)
2. **scripts/backfill_daily_flow.py CLI** + 3년 백필 시간 실측 — Phase C-2 마무리
3. **C-3 (ka10082/83 주봉/월봉)** — chart endpoint 재사용
4. **KOSCOM cross-check 수동** — 가설 B 최종 확정 (스크립트 외)

---

_Phase C 의 마지막 endpoint. ka10081 (가격) + 본 endpoint (수급) 의 짝꿍이 백테스팅의 base. 이중 부호 + 외인순매수 단위가 운영 first call 의 가장 큰 검증 포인트._
