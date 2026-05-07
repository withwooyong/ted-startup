# endpoint-23-ka10058.md — 투자자별일별매매종목요청 (Phase G reference)

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10058` |
| API 명 | 투자자별일별매매종목요청 |
| 분류 | Tier 7 (투자자별 매매) |
| Phase | **G** |
| 우선순위 | **P2** |
| Method | `POST` |
| URL | `/api/dostk/stkinfo` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX 만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| 의존 endpoint | `au10001`, `ka10099` (stock 마스터) |
| 후속 endpoint | `ka10059` (종목별 투자자/기관별 wide), `ka10131` (기관/외국인 연속매매) |

---

## 1. 목적

**특정 투자자 + 특정 매매구분 (순매수/순매도) 의 종목 list** 를 적재한다. ka10086 (Phase C) 가 종목·일자·거래소 단위 투자자별 net 이라면, 본 endpoint 는 **(특정 투자자, 특정 매매구분) → 종목 ranking**.

1. **외인 순매수 상위 종목** — `invsr_tp=9000` (외국인) + `trde_tp=2` (순매수) → 외인이 대량 매수한 종목 list
2. **개인 순매도 상위** — `invsr_tp=8000` (개인) + `trde_tp=1` (순매도) → 개인 패닉 매도 종목
3. **기관 순매수 상위** — `invsr_tp=9999` (기관계) + `trde_tp=2` → 기관 매수 시그널
4. **`prsm_avg_pric` (추정평균가)** — 그 투자자의 평균 매매가 추정 → 손익 추정

**왜 P2**:
- 백테스팅 시그널의 강한 입력 — 외인/기관/개인 매매 흐름 종목 단위 추적
- ka10086 의 `stock_daily_flow` 와 책임 분리: ka10086 = 종목 단위, 본 endpoint = (투자자 + 매매구분) 단위 종목 ranking

**Phase G reference**: ka10059 / ka10131 도 같은 카테고리 (투자자/기관/외국인 매매). 본 계획서가 `investor_flow_daily` 테이블 + 12 invsr_tp + 매매구분 통합 패턴 정의.

---

## 2. Request 명세

### 2.1 Body (6 필드)

| Element | 한글명 | Required | Length | Description |
|---------|-------|----------|--------|-------------|
| `strt_dt` | 시작일자 | Y | 8 | `YYYYMMDD` |
| `end_dt` | 종료일자 | Y | 8 | `YYYYMMDD` |
| `trde_tp` | 매매구분 | Y | 1 | `1`:순매도 / `2`:순매수 |
| `mrkt_tp` | 시장구분 | Y | 3 | `001`:코스피 / `101`:코스닥 (★ ka10027 의 `000` 전체는 안 됨) |
| `invsr_tp` | 투자자구분 | Y | 4 | 12 카테고리 (개인/외국인/기관계/금융투자/투신/사모/은행/보험/연기금/국가/기타금융/기타법인) |
| `stex_tp` | 거래소구분 | Y | 1 | `1`:KRX / `2`:NXT / `3`:통합 |

> **`invsr_tp` 12 카테고리** (Excel 명세):
> - `8000`:개인
> - `9000`:외국인
> - `1000`:금융투자
> - `3000`:투신
> - `3100`:사모펀드
> - `5000`:기타금융
> - `4000`:은행
> - `2000`:보험
> - `6000`:연기금
> - `7000`:국가
> - `7100`:기타법인
> - `9999`:기관계 (1000+2000+3000+4000+5000+6000+7000 합산 추정)
>
> **`mrkt_tp` 의미 5번째 정의**: ka10027 (000/001/101) 와 다름 — 본 endpoint 는 `001/101` 만 (000 전체 없음).

### 2.2 Pydantic

```python
# app/adapter/out/kiwoom/stkinfo.py
class InvestorTradeType(StrEnum):
    NET_SELL = "1"
    NET_BUY = "2"


class InvestorType(StrEnum):
    """ka10058 의 invsr_tp — 12 카테고리."""
    INDIVIDUAL = "8000"           # 개인
    FOREIGN = "9000"              # 외국인
    INSTITUTION_TOTAL = "9999"    # 기관계
    FINANCIAL_INV = "1000"        # 금융투자
    INVESTMENT_TRUST = "3000"     # 투신
    PRIVATE_FUND = "3100"         # 사모펀드
    OTHER_FINANCIAL = "5000"      # 기타금융
    BANK = "4000"                 # 은행
    INSURANCE = "2000"            # 보험
    PENSION_FUND = "6000"         # 연기금
    NATION = "7000"               # 국가
    OTHER_CORP = "7100"           # 기타법인


class InvestorMarketType(StrEnum):
    """ka10058 만의 mrkt_tp — 코스피/코스닥 만."""
    KOSPI = "001"
    KOSDAQ = "101"


class InvestorDailyTradeStockRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    strt_dt: Annotated[str, Field(pattern=r"^\d{8}$")]
    end_dt: Annotated[str, Field(pattern=r"^\d{8}$")]
    trde_tp: InvestorTradeType
    mrkt_tp: InvestorMarketType
    invsr_tp: InvestorType
    stex_tp: RankingExchangeType
```

---

## 3. Response 명세 (11 필드)

### 3.1 Body

| Element | 한글명 | 영속화 | 메모 |
|---------|-------|--------|------|
| `invsr_daly_trde_stk[]` | 투자자별 일별 매매 종목 list | (전체 row) | **list key 명** |
| `stk_cd` | 종목코드 | stock_id (FK) + stock_code_raw | NXT `_NX` 검증 |
| `stk_nm` | 종목명 | payload | |
| `netslmt_qty` | 순매도수량 | **`primary_metric` (BIGINT, 부호)** | trde_tp 별 의미. 부호 포함 (`+4464`) |
| `netslmt_amt` | 순매도금액 | payload (BIGINT, 부호) | |
| `prsm_avg_pric` | 추정평균가 | payload (BIGINT) | 그 투자자의 평균 매매가 |
| `cur_prc` | 현재가 | payload (BIGINT, 부호) | |
| `pre_sig` | 대비기호 | payload | 1~5 |
| `pred_pre` | 전일대비 | payload (BIGINT, 부호) | |
| `avg_pric_pre` | 평균가대비 | payload (BIGINT, 부호) | cur_prc - prsm_avg_pric. 손익 |
| `pre_rt` | 대비율 | payload (Decimal, 부호) | |
| `dt_trde_qty` | 기간거래량 | payload (BIGINT) | 응답 기간 (strt~end) 누적 |
| `return_code` | 처리코드 | (raw_response only) | |
| `return_msg` | 처리메시지 | (raw_response only) | |

> **`netslmt_qty`/`netslmt_amt` 의 의미**: `trde_tp=2` (순매수) 호출이라도 응답 필드는 `netslmt_qty` ("순매도수량" 명칭). 실제 값은 `trde_tp` 따라 부호 / 의미 다름 — 운영 검증 1순위.

### 3.2 Response 예시 (Excel 일부)

```json
{
    "invsr_daly_trde_stk": [
        {
            "stk_cd": "005930",
            "stk_nm": "삼성전자",
            "netslmt_qty": "+4464",
            "netslmt_amt": "+25467",
            "prsm_avg_pric": "57056",
            "cur_prc": "+61300",
            "pre_sig": "2",
            "pred_pre": "+4000",
            "avg_pric_pre": "+4244",
            "pre_rt": "+7.43",
            "dt_trde_qty": "1554171"
        }
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다"
}
```

> ⚠ Excel 예시에 `avg_pric_pre = "--335"` 같은 **이중 부호** 있음 (ka10086 의 이중 부호 문제와 동일). `_strip_double_sign_int` helper (Phase C ka10086) 재사용.

### 3.3 Pydantic + 정규화

```python
class InvestorDailyTradeRow(BaseModel):
    """ka10058 응답 row — 11 필드."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    stk_cd: str = ""
    stk_nm: str = ""
    netslmt_qty: str = ""
    netslmt_amt: str = ""
    prsm_avg_pric: str = ""
    cur_prc: str = ""
    pre_sig: str = ""
    pred_pre: str = ""
    avg_pric_pre: str = ""
    pre_rt: str = ""
    dt_trde_qty: str = ""

    def to_normalized(
        self,
        *,
        stock_id: int | None,
        as_of_date: date,
        investor_type: InvestorType,
        trade_type: InvestorTradeType,
        market_type: InvestorMarketType,
        exchange_type: RankingExchangeType,
        rank: int,
    ) -> "NormalizedInvestorDailyTrade":
        return NormalizedInvestorDailyTrade(
            as_of_date=as_of_date,
            stock_id=stock_id,
            stock_code_raw=self.stk_cd,
            investor_type=investor_type,
            trade_type=trade_type,
            market_type=market_type,
            exchange_type=exchange_type,
            rank=rank,
            net_volume=_strip_double_sign_int(self.netslmt_qty),
            net_amount=_strip_double_sign_int(self.netslmt_amt),
            estimated_avg_price=_to_int(self.prsm_avg_pric),
            current_price=_to_int(self.cur_prc),
            prev_compare_sign=self.pre_sig or None,
            prev_compare_amount=_to_int(self.pred_pre),
            avg_price_compare=_strip_double_sign_int(self.avg_pric_pre),
            prev_compare_rate=_to_decimal(self.pre_rt),
            period_volume=_to_int(self.dt_trde_qty),
            stock_name=self.stk_nm,
        )


class InvestorDailyTradeResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    invsr_daly_trde_stk: list[InvestorDailyTradeRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""


@dataclass(frozen=True, slots=True)
class NormalizedInvestorDailyTrade:
    as_of_date: date                     # 응답 기간의 종료일 (end_dt)
    stock_id: int | None
    stock_code_raw: str
    investor_type: InvestorType
    trade_type: InvestorTradeType
    market_type: InvestorMarketType
    exchange_type: RankingExchangeType
    rank: int                             # 응답 list 순서
    net_volume: int | None
    net_amount: int | None
    estimated_avg_price: int | None
    current_price: int | None
    prev_compare_sign: str | None
    prev_compare_amount: int | None
    avg_price_compare: int | None
    prev_compare_rate: Decimal | None
    period_volume: int | None
    stock_name: str
```

---

## 4. NXT 처리

| 항목 | 적용 여부 |
|------|-----------|
| `stk_cd` 에 `_NX` suffix | (응답 row 의 stk_cd) — 보존 검증 |
| `nxt_enable` 게이팅 | N (호출 시 stex_tp 분리) |
| `mrkt_tp` 별 분리 | **Y** (KOSPI / KOSDAQ 분리 호출) |
| `stex_tp` 별 분리 | **Y** (1/2/3 — 거래소 분리) |

### 4.1 호출 매트릭스

| 차원 | 값 수 |
|------|-------|
| mrkt_tp | 2 (001 / 101) |
| invsr_tp | 12 (전체) — 운영 default = 3 (개인/외국인/기관계) |
| trde_tp | 2 (1/2) |
| stex_tp | 3 — 운영 default = 통합 (3) 만 |
| 호출 수 (default) | 2 × 3 × 2 × 1 = **12 호출 / 일** |

→ Phase F (4 호출 / 시점 / endpoint) 보다 부담 큼. 단, ka10058 / 59 / 131 합치면 ~30+ 호출 / 일.

---

## 5. DB 스키마

### 5.1 신규 테이블 — Migration 008 (`008_investor_flow.py`)

> ka10059 (wide format), ka10131 (연속매매) 와 같은 마이그레이션. Phase G 통합.

```sql
CREATE TABLE kiwoom.investor_flow_daily (
    id                       BIGSERIAL PRIMARY KEY,
    as_of_date               DATE NOT NULL,                  -- 응답 기간의 종료일 (end_dt)
    market_type              VARCHAR(3) NOT NULL,             -- "001"/"101"
    exchange_type            VARCHAR(1) NOT NULL,             -- "1"/"2"/"3"
    investor_type            VARCHAR(4) NOT NULL,             -- "8000"/"9000"/...
    trade_type               VARCHAR(1) NOT NULL,             -- "1"/"2"
    rank                     INTEGER NOT NULL,                 -- 응답 list 순서
    stock_id                 BIGINT REFERENCES kiwoom.stock(id) ON DELETE SET NULL,
    stock_code_raw           VARCHAR(20) NOT NULL,
    stock_name               VARCHAR(100),

    net_volume               BIGINT,                           -- netslmt_qty (부호)
    net_amount               BIGINT,                           -- netslmt_amt (부호)
    estimated_avg_price      BIGINT,                           -- prsm_avg_pric
    current_price            BIGINT,                           -- cur_prc (부호)
    prev_compare_sign        CHAR(1),
    prev_compare_amount      BIGINT,
    avg_price_compare        BIGINT,                           -- avg_pric_pre (부호)
    prev_compare_rate        NUMERIC(8, 4),
    period_volume            BIGINT,

    fetched_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_investor_flow_daily UNIQUE (
        as_of_date, market_type, exchange_type,
        investor_type, trade_type, rank
    )
);

CREATE INDEX idx_investor_flow_date_inv ON kiwoom.investor_flow_daily(
    as_of_date, investor_type, trade_type
);
CREATE INDEX idx_investor_flow_stock ON kiwoom.investor_flow_daily(stock_id)
    WHERE stock_id IS NOT NULL;
```

### 5.2 ORM 모델

```python
# app/adapter/out/persistence/models/investor_flow_daily.py
class InvestorFlowDaily(Base):
    __tablename__ = "investor_flow_daily"
    __table_args__ = (
        UniqueConstraint(
            "as_of_date", "market_type", "exchange_type",
            "investor_type", "trade_type", "rank",
            name="uq_investor_flow_daily",
        ),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    market_type: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange_type: Mapped[str] = mapped_column(String(1), nullable=False)
    investor_type: Mapped[str] = mapped_column(String(4), nullable=False)
    trade_type: Mapped[str] = mapped_column(String(1), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("kiwoom.stock.id", ondelete="SET NULL"), nullable=True
    )
    stock_code_raw: Mapped[str] = mapped_column(String(20), nullable=False)
    stock_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    net_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    estimated_avg_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    current_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_compare_sign: Mapped[str | None] = mapped_column(String(1), nullable=True)
    prev_compare_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    avg_price_compare: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_compare_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    period_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

### 5.3 row 수 추정

| 항목 | 값 |
|------|----|
| 호출당 응답 row | ~50~200 |
| 호출 수 / 일 (default 12) | 12 |
| 1일 row | 600~2,400 |
| 1년 (252 거래일) | 150K~600K |
| 3년 백필 | 450K~1.8M |

→ 단일 테이블, 파티션 불필요.

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomInvestorClient.fetch_daily_trade_stocks`

```python
# app/adapter/out/kiwoom/stkinfo.py (KiwoomStkInfoClient 의 같은 클래스에 메서드 추가)
class KiwoomStkInfoClient:
    """`/api/dostk/stkinfo` — ka10099/100/001/101 + ka10058/59 공유."""

    PATH = "/api/dostk/stkinfo"

    async def fetch_investor_daily_trade_stocks(
        self,
        *,
        start_date: date,
        end_date: date,
        trade_type: InvestorTradeType,
        market_type: InvestorMarketType,
        investor_type: InvestorType,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        max_pages: int = 10,
    ) -> tuple[list[InvestorDailyTradeRow], dict[str, Any]]:
        """ka10058 — (투자자, 매매구분, 시장, 거래소) 종목 list."""
        body = {
            "strt_dt": start_date.strftime("%Y%m%d"),
            "end_dt": end_date.strftime("%Y%m%d"),
            "trde_tp": trade_type.value,
            "mrkt_tp": market_type.value,
            "invsr_tp": investor_type.value,
            "stex_tp": exchange_type.value,
        }

        all_rows: list[InvestorDailyTradeRow] = []
        async for page in self._client.call_paginated(
            api_id="ka10058", endpoint=self.PATH, body=body, max_pages=max_pages,
        ):
            parsed = InvestorDailyTradeResponse.model_validate(page.body)
            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id="ka10058",
                    return_code=parsed.return_code,
                    return_msg=parsed.return_msg,
                )
            all_rows.extend(parsed.invsr_daly_trde_stk)

        return all_rows, body
```

### 6.2 Repository — `InvestorFlowDailyRepository`

```python
# app/adapter/out/persistence/repositories/investor_flow.py
class InvestorFlowDailyRepository:
    """ka10058 의 investor_flow_daily — ka10059/131 의 다른 테이블과 분리."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, rows: Sequence[NormalizedInvestorDailyTrade]) -> int:
        if not rows:
            return 0

        values = [
            {
                "as_of_date": r.as_of_date,
                "market_type": r.market_type.value,
                "exchange_type": r.exchange_type.value,
                "investor_type": r.investor_type.value,
                "trade_type": r.trade_type.value,
                "rank": r.rank,
                "stock_id": r.stock_id,
                "stock_code_raw": r.stock_code_raw,
                "stock_name": r.stock_name,
                "net_volume": r.net_volume,
                "net_amount": r.net_amount,
                "estimated_avg_price": r.estimated_avg_price,
                "current_price": r.current_price,
                "prev_compare_sign": r.prev_compare_sign,
                "prev_compare_amount": r.prev_compare_amount,
                "avg_price_compare": r.avg_price_compare,
                "prev_compare_rate": r.prev_compare_rate,
                "period_volume": r.period_volume,
            }
            for r in rows
        ]

        stmt = pg_insert(InvestorFlowDaily).values(values)
        update_set = {col: stmt.excluded[col] for col in values[0]
                      if col not in ("as_of_date", "market_type", "exchange_type",
                                     "investor_type", "trade_type", "rank")}
        update_set["fetched_at"] = func.now()
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                "as_of_date", "market_type", "exchange_type",
                "investor_type", "trade_type", "rank",
            ],
            set_=update_set,
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return rowcount_of(result)

    async def get_top_stocks(
        self,
        as_of_date: date,
        *,
        investor_type: InvestorType,
        trade_type: InvestorTradeType,
        market_type: InvestorMarketType = InvestorMarketType.KOSPI,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        limit: int = 50,
    ) -> list[InvestorFlowDaily]:
        stmt = (
            select(InvestorFlowDaily)
            .where(
                InvestorFlowDaily.as_of_date == as_of_date,
                InvestorFlowDaily.investor_type == investor_type.value,
                InvestorFlowDaily.trade_type == trade_type.value,
                InvestorFlowDaily.market_type == market_type.value,
                InvestorFlowDaily.exchange_type == exchange_type.value,
            )
            .order_by(InvestorFlowDaily.rank)
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars())
```

### 6.3 UseCase — `IngestInvestorDailyTradeUseCase`

```python
# app/application/service/investor_flow_service.py
class IngestInvestorDailyTradeUseCase:
    """ka10058 — 한 (투자자, 매매구분, 시장, 거래소) 묶음 적재."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        stkinfo_client: KiwoomStkInfoClient,
        stock_repo: StockRepository,
    ) -> None:
        self._session = session
        self._client = stkinfo_client
        self._stock_repo = stock_repo
        self._repo = InvestorFlowDailyRepository(session)

    async def execute(
        self,
        *,
        start_date: date,
        end_date: date,
        investor_type: InvestorType,
        trade_type: InvestorTradeType = InvestorTradeType.NET_BUY,
        market_type: InvestorMarketType = InvestorMarketType.KOSPI,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
    ) -> InvestorIngestOutcome:
        try:
            raw_rows, _used_filters = await self._client.fetch_investor_daily_trade_stocks(
                start_date=start_date, end_date=end_date,
                trade_type=trade_type, market_type=market_type,
                investor_type=investor_type, exchange_type=exchange_type,
            )
        except KiwoomBusinessError as exc:
            return InvestorIngestOutcome(
                upserted=0, error=f"business: {exc.return_code}",
            )

        # stock 매핑
        stock_codes_clean = [strip_kiwoom_suffix(r.stk_cd) for r in raw_rows]
        stocks_by_code = await self._stock_repo.find_by_codes(stock_codes_clean)

        normalized = []
        for rank, raw_row in enumerate(raw_rows, start=1):
            code_clean = strip_kiwoom_suffix(raw_row.stk_cd)
            stock = stocks_by_code.get(code_clean)

            normalized.append(raw_row.to_normalized(
                stock_id=stock.id if stock else None,
                as_of_date=end_date,
                investor_type=investor_type,
                trade_type=trade_type,
                market_type=market_type,
                exchange_type=exchange_type,
                rank=rank,
            ))

        upserted = await self._repo.upsert_many(normalized)

        return InvestorIngestOutcome(
            as_of_date=end_date,
            investor_type=investor_type,
            trade_type=trade_type,
            market_type=market_type,
            exchange_type=exchange_type,
            fetched=len(raw_rows), upserted=upserted,
        )


@dataclass(frozen=True, slots=True)
class InvestorIngestOutcome:
    as_of_date: date | None = None
    investor_type: InvestorType | None = None
    trade_type: InvestorTradeType | None = None
    market_type: InvestorMarketType | None = None
    exchange_type: RankingExchangeType | None = None
    fetched: int = 0
    upserted: int = 0
    error: str | None = None
```

### 6.4 Bulk — `IngestInvestorDailyTradeBulkUseCase`

```python
class IngestInvestorDailyTradeBulkUseCase:
    """일 1회 sync — 12 호출 default (2 mrkt × 3 inv × 2 trde).

    동시성: RPS 4 + 250ms = 12 / 4 × 0.25 = 0.75초 (이론).
    실측 1~10초.
    """

    DEFAULT_INVESTORS = [
        InvestorType.INDIVIDUAL,
        InvestorType.FOREIGN,
        InvestorType.INSTITUTION_TOTAL,
    ]

    def __init__(
        self,
        session: AsyncSession,
        *,
        single_use_case: IngestInvestorDailyTradeUseCase,
    ) -> None:
        self._session = session
        self._single = single_use_case

    async def execute(
        self,
        *,
        start_date: date,
        end_date: date,
        investors: Sequence[InvestorType] | None = None,
    ) -> list[InvestorIngestOutcome]:
        target_investors = list(investors) if investors else self.DEFAULT_INVESTORS

        outcomes: list[InvestorIngestOutcome] = []
        for market_type in [InvestorMarketType.KOSPI, InvestorMarketType.KOSDAQ]:
            for investor_type in target_investors:
                for trade_type in [InvestorTradeType.NET_BUY, InvestorTradeType.NET_SELL]:
                    try:
                        async with self._session.begin_nested():
                            o = await self._single.execute(
                                start_date=start_date, end_date=end_date,
                                investor_type=investor_type,
                                trade_type=trade_type,
                                market_type=market_type,
                                exchange_type=RankingExchangeType.UNIFIED,
                            )
                            outcomes.append(o)
                    except Exception as exc:
                        logger.warning(
                            "investor flow 실패 inv=%s trde=%s mkt=%s: %s",
                            investor_type.value, trade_type.value, market_type.value, exc,
                        )
                        outcomes.append(InvestorIngestOutcome(
                            as_of_date=end_date,
                            investor_type=investor_type, trade_type=trade_type,
                            market_type=market_type, exchange_type=RankingExchangeType.UNIFIED,
                            error=f"{type(exc).__name__}: {exc}",
                        ))

        await self._session.commit()
        return outcomes
```

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **수동 단건** | on-demand | `POST /api/kiwoom/investor/daily?invsr_tp=9000&trde_tp=2&mrkt_tp=001` |
| **수동 bulk** | on-demand | `POST /api/kiwoom/investor/daily/sync?start=&end=` |
| **일 1회 cron** | KST 20:00 평일 | Phase F (19:55) 직후 |
| **백필** | on-demand | `python scripts/backfill_investor.py --start ... --end ...` |

### 7.1 라우터

```python
# app/adapter/web/routers/investor_flow.py
router = APIRouter(prefix="/api/kiwoom/investor", tags=["kiwoom-investor"])


@router.post(
    "/daily",
    response_model=InvestorIngestOutcomeOut,
    dependencies=[Depends(require_admin_key)],
)
async def ingest_one_investor_daily(
    start: date = Query(...),
    end: date = Query(...),
    invsr_tp: str = Query(default="9000"),    # 외국인
    trde_tp: Literal["1", "2"] = Query(default="2"),
    mrkt_tp: Literal["001", "101"] = Query(default="001"),
    stex_tp: Literal["1", "2", "3"] = Query(default="3"),
    use_case: IngestInvestorDailyTradeUseCase = Depends(get_ingest_investor_daily_use_case),
) -> InvestorIngestOutcomeOut:
    outcome = await use_case.execute(
        start_date=start, end_date=end,
        investor_type=InvestorType(invsr_tp),
        trade_type=InvestorTradeType(trde_tp),
        market_type=InvestorMarketType(mrkt_tp),
        exchange_type=RankingExchangeType(stex_tp),
    )
    return InvestorIngestOutcomeOut.model_validate(asdict(outcome))


@router.post(
    "/daily/sync",
    response_model=list[InvestorIngestOutcomeOut],
    dependencies=[Depends(require_admin_key)],
)
async def sync_investor_daily_bulk(
    body: InvestorBulkRequestIn,
    use_case: IngestInvestorDailyTradeBulkUseCase = Depends(get_ingest_investor_daily_bulk_use_case),
) -> list[InvestorIngestOutcomeOut]:
    outcomes = await use_case.execute(
        start_date=body.start_date, end_date=body.end_date,
        investors=[InvestorType(c) for c in body.investors] if body.investors else None,
    )
    return [InvestorIngestOutcomeOut.model_validate(asdict(o)) for o in outcomes]


@router.get(
    "/daily/top",
    response_model=list[InvestorFlowDailyOut],
)
async def get_top_stocks(
    as_of_date: date = Query(...),
    invsr_tp: str = Query(default="9000"),
    trde_tp: Literal["1", "2"] = Query(default="2"),
    mrkt_tp: Literal["001", "101"] = Query(default="001"),
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[InvestorFlowDailyOut]:
    repo = InvestorFlowDailyRepository(session)
    rows = await repo.get_top_stocks(
        as_of_date,
        investor_type=InvestorType(invsr_tp),
        trade_type=InvestorTradeType(trde_tp),
        market_type=InvestorMarketType(mrkt_tp),
        limit=limit,
    )
    return [InvestorFlowDailyOut.model_validate(r) for r in rows]
```

### 7.2 APScheduler Job

```python
# app/batch/investor_flow_jobs.py
async def fire_investor_daily_sync() -> None:
    """매 평일 20:00 KST."""
    today = date.today()
    if not is_trading_day(today):
        return
    try:
        async with get_sessionmaker()() as session:
            kiwoom_client = build_kiwoom_client_for("prod-main")
            stkinfo = KiwoomStkInfoClient(kiwoom_client)
            stock_repo = StockRepository(session)
            single = IngestInvestorDailyTradeUseCase(
                session, stkinfo_client=stkinfo, stock_repo=stock_repo,
            )
            bulk = IngestInvestorDailyTradeBulkUseCase(
                session, single_use_case=single,
            )
            outcomes = await bulk.execute(
                start_date=today, end_date=today,
            )
        success = sum(1 for o in outcomes if o.error is None)
        logger.info(
            "investor daily sync 완료 success=%d/%d",
            success, len(outcomes),
        )
    except Exception:
        logger.exception("investor daily sync 콜백 예외")


scheduler.add_job(
    fire_investor_daily_sync,
    CronTrigger(day_of_week="mon-fri", hour=20, minute=0, timezone=KST),
    id="investor_daily_sync",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
    misfire_grace_time=60 * 30,
)
```

### 7.3 RPS / 시간

| 항목 | 값 |
|------|----|
| 1 시점 sync 호출 수 | 12 (default 3 inv × 2 mkt × 2 trde) |
| 호출당 인터벌 | 250ms |
| 동시성 | 4 |
| 이론 시간 | 12 / 4 × 0.25 = 0.75초 |
| 실측 추정 | 5~30초 |

---

## 8. 에러 처리

ka10027 동일 + 부분 실패 격리 (한 (mrkt, inv, trde) 실패가 다른 호출 막지 않음).

### 8.1 partial 실패 알람

12 호출 중:
- < 5%: 정상
- 5~15%: warning
- > 15%: error + alert

---

## 9. 테스트

### 9.1 Unit

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 응답 | 200 + list 50건 | 50건 반환 |
| 빈 list | 200 + `invsr_daly_trde_stk=[]` | 빈 list |
| `return_code=1` | 비즈니스 에러 | `KiwoomBusinessError` |
| invsr_tp 12 카테고리 | INDIVIDUAL/FOREIGN/... | request body `invsr_tp` 분기 |
| trde_tp 분기 | NET_BUY | `trde_tp="2"` |
| mrkt_tp KOSPI/KOSDAQ | KOSPI | `mrkt_tp="001"` |
| 부호 포함 | netslmt_qty="+4464" | `_strip_double_sign_int` → 4464 |
| 이중 부호 (Excel `--335`) | avg_pric_pre="--335" | `_strip_double_sign_int` → -335 |
| 페이지네이션 | cont-yn=Y → N | 합쳐 N건 |

### 9.2 Integration

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| INSERT (DB 빈) | 응답 50 row | investor_flow_daily 50 row INSERT |
| UPDATE (멱등성) | 같은 호출 두 번 | row 50개 유지, fetched_at 갱신 |
| 다른 (inv, trde) 분리 | (외인, 매수) + (개인, 매도) 두 호출 | 100 row INSERT (UNIQUE 분리) |
| stock lookup miss | stock 마스터 비어있음 | stock_id=NULL, stock_code_raw 보관 |
| Bulk 12 호출 | 3 inv × 2 mkt × 2 trde | 12 outcome 반환 |
| 한 호출 실패 | 1개 KiwoomBusinessError | 다른 호출 진행, outcome.error 노출 |
| get_top_stocks 시그널 | 외인 매수 50건 적재 | 50 rank 1~50 정렬 |

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `app/adapter/out/kiwoom/stkinfo.py` — `KiwoomStkInfoClient.fetch_investor_daily_trade_stocks` (기존 클래스에 메서드 추가)
- [ ] `app/adapter/out/kiwoom/_records.py` — `InvestorDailyTradeRow/Response`, `InvestorType`, `InvestorTradeType`, `InvestorMarketType`
- [ ] `app/adapter/out/persistence/models/investor_flow_daily.py` — `InvestorFlowDaily`
- [ ] `app/adapter/out/persistence/repositories/investor_flow.py` — `InvestorFlowDailyRepository`
- [ ] `app/application/service/investor_flow_service.py` — `IngestInvestorDailyTradeUseCase`, `IngestInvestorDailyTradeBulkUseCase`
- [ ] `app/adapter/web/routers/investor_flow.py` — POST/GET endpoints
- [ ] `app/batch/investor_flow_jobs.py` — APScheduler 등록 (KST mon-fri 20:00)
- [ ] `migrations/versions/008_investor_flow.py` — `investor_flow_daily` (ka10059/131 와 같은 마이그레이션)

### 10.2 테스트

- [ ] Unit 9 시나리오 PASS
- [ ] Integration 7 시나리오 PASS

### 10.3 운영 검증

- [ ] **`netslmt_qty`/`netslmt_amt` 의 부호 의미** — `trde_tp=2` (순매수) 호출 시 양수 / `trde_tp=1` (순매도) 호출 시 양수 (절댓값) 인지
- [ ] **이중 부호 (`--335`) 발생 빈도** (ka10086 동일 문제)
- [ ] `prsm_avg_pric` 산출 방법 (그 투자자의 그 종목 평균 매매가)
- [ ] 응답 row 수 (`mrkt_tp=001` 시 KOSPI 50~200 추정)
- [ ] `dt_trde_qty` (기간거래량) 의 의미 — 응답 기간 누적 거래량
- [ ] 12 invsr_tp 별 응답 row 수 차이 (소형 카테고리는 row 적을 가능성)
- [ ] NXT 응답에서 stk_cd 형식 (`_NX` 보존)

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10058 investor daily trade ingest + investor_flow_daily 통합 테이블`
- [ ] `master.md` § 12 결정 기록에:
  - `netslmt_qty/_amt` 부호 의미
  - 이중 부호 빈도 + 처리 정책
  - `prsm_avg_pric` 산출

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | 운영 default investors | INDIVIDUAL + FOREIGN + INSTITUTION_TOTAL (현재) / 12 모두 | Phase G 코드화 |
| 2 | 운영 default 윈도 | 1일 (start=end=오늘) / 1주 / 1달 | Phase G 코드화 |
| 3 | 운영 default trde_tp | 둘 (현재) / NET_BUY 만 | Phase G 코드화 |
| 4 | stex_tp 분리 호출 | 통합만 (현재) / 1+2 분리 | Phase G 후반 |
| 5 | 이중 부호 처리 | `_strip_double_sign_int` (ka10086 helper) | Phase G 코드화 |
| 6 | 백필 윈도 | 3년 / 1년 | Phase H |

### 11.2 알려진 위험

- **`netslmt_qty` 의미 모호 (★)**: 응답 필드명은 "순매도수량" 인데 trde_tp=2 (순매수) 호출 응답에도 등장 — 부호 / 의미가 trde_tp 따라 달라짐. 운영 1순위 검증
- **이중 부호 (`--335`)**: ka10086 의 동일 문제 — `_strip_double_sign_int` 재사용. 빈도 운영 1주 측정
- **12 invsr_tp 별 응답 분포 차이**: 개인/외국인/기관계 는 row 많고, 국가/기타법인 등은 row 적을 가능성. partial 실패율 추정에 영향
- **`prsm_avg_pric` 산출 모호**: 기간 평균인지 일별 평균인지. 운영 검증 — `avg_pric_pre = cur_prc - prsm_avg_pric` 산식 일관성으로 추정 가능
- **응답 row 수 제한**: 키움 명시 없음. 50~200 추정. 페이지네이션 발생 시 max_pages=10 으로 제한
- **시그널 시점 lag**: ka10058 응답이 T+1 또는 T+2 lag 가능 (외인 매매 보고는 T+2 가 일반). 백테스팅 시그널의 시점 보정 필요
- **`as_of_date` 의미**: 응답이 strt_dt~end_dt 기간이라면, 본 row 의 시그널 시점은 end_dt. 단, period_volume (기간 거래량) 은 누적값이라 백테스팅 엔진의 진입가 시점과 다름

### 11.3 ka10058 vs ka10086 비교 (책임 분리)

| 항목 | ka10058 (본) | ka10086 (Phase C) |
|------|-----------|------------------|
| URL | /api/dostk/stkinfo | /api/dostk/mrkcond |
| 호출 단위 | (투자자, 매매구분, 시장, 거래소) → 종목 list | (종목, 일자) → 모든 투자자 wide |
| 식별자 | invsr_tp + trde_tp + mrkt_tp | stk_cd + qry_dt |
| 응답 row 의미 | 그 (투자자, 매매구분) 의 상위 종목 | 그 종목·일자의 모든 투자자별 합계 |
| 응답 row 수 | 50~200 | 1 (단건) |
| primary_metric | netslmt_qty (그 투자자의 net) | (해당 없음 — wide row) |
| 영속화 테이블 | investor_flow_daily | stock_daily_flow |
| 백테스팅 시그널 | (투자자) 매수/매도 상위 종목 추출 | (종목) 의 모든 투자자 net 합계 |

→ 두 endpoint **서로 보완**. ka10058 = 종목 추출용, ka10086 = 종목별 종합용.

### 11.4 ka10058 vs ka10059 비교 (Phase G 내부)

| 항목 | ka10058 (본) | ka10059 |
|------|-----------|---------|
| URL | /api/dostk/stkinfo | 동일 |
| 호출 단위 | (투자자 1, 매매 1) → 종목 list | (종목 1, 일자 1) → 모든 투자자 wide |
| 응답 schema | 종목 ranking | wide investor breakdown |
| 응답 필드 수 | 11 | **20** (12 invsr 카테고리 + OHLCV) |
| 영속화 | investor_flow_daily | (별도 테이블 — endpoint-24 결정) |

→ ka10059 는 **wide format**. 본 endpoint 의 long format 과 다름. ka10059 가 ka10086 의 wide 와 비슷.

### 11.5 향후 확장

- **외인 매수 + 등락률 cross signal**: ka10058 (외인 매수 상위) + ka10027 (등락률 상위) 의 교집합 → 강한 시그널
- **추정평균가 vs 실시간가 손익 시그널**: avg_pric_pre / prsm_avg_pric → 그 투자자의 평가손익 추정
- **연속 매수 일수 derived**: 같은 (stock, investor) 가 N일 연속 net_volume > 0 → 누적 매수 시그널 (ka10131 의 raw 와 비교)
- **invsr_tp 카테고리별 cross-reference**: 외인 (9000) + 기관계 (9999) 의 매수 일치 종목 찾기

---

_Phase G 의 reference 계획서. `investor_flow_daily` 테이블 + 12 invsr_tp + 매매구분 통합 패턴 정의. ka10059 (wide format) / ka10131 (연속매매) 과 책임 분리 — 본 endpoint = ranking 추출, ka10059 = 종목 단위 wide breakdown, ka10131 = 연속매매 일수 강조._
