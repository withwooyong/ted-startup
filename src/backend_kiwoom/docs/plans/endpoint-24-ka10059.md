# endpoint-24-ka10059.md — 종목별투자자기관별요청 (wide format)

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10059` |
| API 명 | 종목별투자자기관별요청 |
| 분류 | Tier 7 (투자자별 매매) |
| Phase | **G** |
| 우선순위 | **P2** |
| Method | `POST` |
| URL | `/api/dostk/stkinfo` |
| 의존 endpoint | `au10001`, `ka10099` (stock 마스터) |
| 후속 endpoint | (없음) |

> **Phase G reference 는 endpoint-23-ka10058.md**. 본 계획서는 차이점만.

---

## 1. 목적

**(종목, 일자) 단위 모든 투자자 카테고리 wide breakdown**. ka10058 (long format ranking) 의 정반대 구조 — 한 종목·한 일자에 12 투자자 net 을 wide row 한 번에.

1. **종목 단위 투자자 매매 흐름** — 한 종목의 일별 ind/orgn/frgn/fnnc/insrnc/invtrt/etc_fnnc/bank/penfnd/samo/natn/etc_corp/natfor 12 카테고리 net
2. **OHLCV cross-reference** — `cur_prc`/`acc_trde_qty`/`acc_trde_prica` 응답 포함 (ka10081 와 cross-check)
3. **`amt_qty_tp` (금액/수량)** + **`unit_tp` (천주/단주)** — 단위 분리 호출 가능
4. **`trde_tp` (순매수/매수/매도)** — 본 endpoint 만 3종 (ka10058 의 2종 보다 많음)

**ka10058 / ka10086 과 차이**:
- **ka10058 long format** (1 row = 1 종목, primary_metric 단일) ↔ **ka10059 wide format** (1 row = 1 종목 × 모든 투자자 net)
- **ka10086 (Phase C) wide format** 과 유사하지만 — ka10086 은 `/mrkcond` 카테고리 (일별주가 + 신용 + 외인 비중), ka10059 는 `/stkinfo` 카테고리 (12 투자자 net 만)

---

## 2. Request 명세

### 2.1 Body (5 필드)

| Element | 한글명 | Required | Length | Description |
|---------|-------|----------|--------|-------------|
| `dt` | 일자 | Y | 8 | `YYYYMMDD` (단일 일자 — ka10058 의 strt~end 와 다름) |
| `stk_cd` | 종목코드 | Y | **20** | NXT (`_NX`) 지원 |
| `amt_qty_tp` | 금액수량구분 | Y | 1 | `1`:금액 / `2`:수량 |
| `trde_tp` | 매매구분 | Y | 1 | `0`:순매수 / `1`:매수 / `2`:매도 |
| `unit_tp` | 단위구분 | Y | 4 | `1000`:천주 / `1`:단주 |

### 2.2 Pydantic

```python
class AmountQuantityType(StrEnum):
    AMOUNT = "1"
    QUANTITY = "2"


class StockInvestorTradeType(StrEnum):
    """ka10059 만의 trde_tp — ka10058 의 2종 (1/2) 보다 많음."""
    NET_BUY = "0"             # 순매수
    BUY = "1"                  # 매수만
    SELL = "2"                 # 매도만


class UnitType(StrEnum):
    THOUSAND_SHARES = "1000"   # 천주
    SINGLE_SHARE = "1"          # 단주


class StockInvestorBreakdownRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    dt: Annotated[str, Field(pattern=r"^\d{8}$")]
    stk_cd: Annotated[str, Field(min_length=6, max_length=20)]
    amt_qty_tp: AmountQuantityType
    trde_tp: StockInvestorTradeType
    unit_tp: UnitType
```

---

## 3. Response 명세 (20 필드)

### 3.1 Body — wide format

| Element | 한글명 | 영속화 | 메모 |
|---------|-------|--------|------|
| `stk_invsr_orgn[]` | 종목별 투자자 기관별 list | (전체 row) | **list key 명** |
| `dt` | 일자 | trading_date (DATE) | `YYYYMMDD` |
| `cur_prc` | 현재가 | current_price (BIGINT, 부호) | |
| `pre_sig` | 대비기호 | prev_compare_sign | 1~5 |
| `pred_pre` | 전일대비 | prev_compare_amount (BIGINT, 부호) | |
| `flu_rt` | 등락율 | change_rate (NUMERIC) | 우측 2자리 소수점 — 부호 포함 (`+698` = +6.98%) |
| `acc_trde_qty` | 누적거래량 | acc_trade_volume (BIGINT) | |
| `acc_trde_prica` | 누적거래대금 | acc_trade_amount (BIGINT) | 백만원 추정 |
| **`ind_invsr`** | 개인투자자 | net_individual (BIGINT, 부호) | trde_tp / amt_qty_tp 단위 의존 |
| **`frgnr_invsr`** | 외국인투자자 | net_foreign (BIGINT, 부호) | |
| **`orgn`** | 기관계 | net_institution_total (BIGINT, 부호) | |
| **`fnnc_invt`** | 금융투자 | net_financial_inv (BIGINT, 부호) | |
| **`insrnc`** | 보험 | net_insurance (BIGINT, 부호) | |
| **`invtrt`** | 투신 | net_investment_trust (BIGINT, 부호) | |
| **`etc_fnnc`** | 기타금융 | net_other_financial (BIGINT, 부호) | |
| **`bank`** | 은행 | net_bank (BIGINT, 부호) | |
| **`penfnd_etc`** | 연기금등 | net_pension_fund (BIGINT, 부호) | |
| **`samo_fund`** | 사모펀드 | net_private_fund (BIGINT, 부호) | |
| **`natn`** | 국가 | net_nation (BIGINT, 부호) | |
| **`etc_corp`** | 기타법인 | net_other_corp (BIGINT, 부호) | |
| **`natfor`** | 내외국인 | net_dom_for (BIGINT, 부호) | 운영 검증 — 의미 |
| `return_code` | 처리코드 | (raw_response only) | |
| `return_msg` | 처리메시지 | (raw_response only) | |

> **`flu_rt` 표기 주의**: Excel "우측 2자리 소수점" — `+698` 이 +6.98%. ka10058 의 `pre_rt` (`+7.43`) 와 다른 표기 — 정규화 시 / 100.

### 3.2 Response 예시 (Excel 일부)

```json
{
    "stk_invsr_orgn": [
        {
            "dt": "20241107",
            "cur_prc": "+61300",
            "pre_sig": "2",
            "pred_pre": "+4000",
            "flu_rt": "+698",
            "acc_trde_qty": "1105968",
            "acc_trde_prica": "64215",
            "ind_invsr": "1584",
            "frgnr_invsr": "-61779",
            "orgn": "60195",
            "fnnc_invt": "25514",
            "insrnc": "0",
            "invtrt": "0",
            "etc_fnnc": "34619",
            "bank": "4",
            "penfnd_etc": "-1",
            "samo_fund": "58",
            "natn": "0",
            "etc_corp": "0",
            "natfor": "1"
        }
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다"
}
```

> 검증: `orgn = fnnc_invt + insrnc + invtrt + etc_fnnc + bank + penfnd_etc + samo_fund + natn` (60195 = 25514 + 0 + 0 + 34619 + 4 + (-1) + 58 + 0 = 60194 — 1 차이 가능, 운영 검증)

### 3.3 Pydantic + 정규화

```python
class StockInvestorBreakdownRow(BaseModel):
    """ka10059 응답 row — 20 필드 wide."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    dt: str = ""
    cur_prc: str = ""
    pre_sig: str = ""
    pred_pre: str = ""
    flu_rt: str = ""
    acc_trde_qty: str = ""
    acc_trde_prica: str = ""
    ind_invsr: str = ""
    frgnr_invsr: str = ""
    orgn: str = ""
    fnnc_invt: str = ""
    insrnc: str = ""
    invtrt: str = ""
    etc_fnnc: str = ""
    bank: str = ""
    penfnd_etc: str = ""
    samo_fund: str = ""
    natn: str = ""
    etc_corp: str = ""
    natfor: str = ""

    def to_normalized(
        self,
        *,
        stock_id: int,
        amt_qty_tp: AmountQuantityType,
        trade_type: StockInvestorTradeType,
        unit_tp: UnitType,
        exchange_type: RankingExchangeType,
    ) -> "NormalizedStockInvestorBreakdown":
        return NormalizedStockInvestorBreakdown(
            stock_id=stock_id,
            trading_date=_parse_yyyymmdd(self.dt) or date.min,
            amt_qty_tp=amt_qty_tp,
            trade_type=trade_type,
            unit_tp=unit_tp,
            exchange_type=exchange_type,
            current_price=_to_int(self.cur_prc),
            prev_compare_sign=self.pre_sig or None,
            prev_compare_amount=_to_int(self.pred_pre),
            change_rate=_to_decimal_div_100(self.flu_rt),       # +698 → 6.98
            acc_trade_volume=_to_int(self.acc_trde_qty),
            acc_trade_amount=_to_int(self.acc_trde_prica),
            net_individual=_strip_double_sign_int(self.ind_invsr),
            net_foreign=_strip_double_sign_int(self.frgnr_invsr),
            net_institution_total=_strip_double_sign_int(self.orgn),
            net_financial_inv=_strip_double_sign_int(self.fnnc_invt),
            net_insurance=_strip_double_sign_int(self.insrnc),
            net_investment_trust=_strip_double_sign_int(self.invtrt),
            net_other_financial=_strip_double_sign_int(self.etc_fnnc),
            net_bank=_strip_double_sign_int(self.bank),
            net_pension_fund=_strip_double_sign_int(self.penfnd_etc),
            net_private_fund=_strip_double_sign_int(self.samo_fund),
            net_nation=_strip_double_sign_int(self.natn),
            net_other_corp=_strip_double_sign_int(self.etc_corp),
            net_dom_for=_strip_double_sign_int(self.natfor),
        )


class StockInvestorBreakdownResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    stk_invsr_orgn: list[StockInvestorBreakdownRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""


@dataclass(frozen=True, slots=True)
class NormalizedStockInvestorBreakdown:
    stock_id: int
    trading_date: date
    amt_qty_tp: AmountQuantityType
    trade_type: StockInvestorTradeType
    unit_tp: UnitType
    exchange_type: RankingExchangeType
    current_price: int | None
    prev_compare_sign: str | None
    prev_compare_amount: int | None
    change_rate: Decimal | None
    acc_trade_volume: int | None
    acc_trade_amount: int | None
    # 12 투자자 카테고리 net
    net_individual: int | None
    net_foreign: int | None
    net_institution_total: int | None
    net_financial_inv: int | None
    net_insurance: int | None
    net_investment_trust: int | None
    net_other_financial: int | None
    net_bank: int | None
    net_pension_fund: int | None
    net_private_fund: int | None
    net_nation: int | None
    net_other_corp: int | None
    net_dom_for: int | None
```

---

## 4. NXT 처리

| 항목 | 적용 여부 |
|------|-----------|
| `stk_cd` 에 `_NX` suffix | **Y** (Length=20) |
| `nxt_enable` 게이팅 | **Y** |
| `mrkt_tp` 별 분리 | N (종목 단위) |

ka10081 동일 패턴.

---

## 5. DB 스키마

### 5.1 신규 테이블 — Migration 008 (`008_investor_flow.py`)

> ka10058 의 `investor_flow_daily` 와 같은 마이그레이션. **별도 테이블** (wide format 이라 컬럼 다름).

```sql
CREATE TABLE kiwoom.stock_investor_breakdown (
    id                          BIGSERIAL PRIMARY KEY,
    stock_id                    BIGINT NOT NULL REFERENCES kiwoom.stock(id) ON DELETE CASCADE,
    trading_date                DATE NOT NULL,
    amt_qty_tp                  VARCHAR(1) NOT NULL,        -- "1"/"2"
    trade_type                  VARCHAR(1) NOT NULL,        -- "0"/"1"/"2"
    unit_tp                     VARCHAR(4) NOT NULL,        -- "1000"/"1"
    exchange_type               VARCHAR(1) NOT NULL,        -- "1"/"2"/"3"

    current_price               BIGINT,
    prev_compare_sign           CHAR(1),
    prev_compare_amount         BIGINT,
    change_rate                 NUMERIC(8, 4),
    acc_trade_volume            BIGINT,
    acc_trade_amount            BIGINT,

    -- 12 투자자 카테고리 net (양/음 부호 포함)
    net_individual              BIGINT,
    net_foreign                 BIGINT,
    net_institution_total       BIGINT,
    net_financial_inv           BIGINT,
    net_insurance               BIGINT,
    net_investment_trust        BIGINT,
    net_other_financial         BIGINT,
    net_bank                    BIGINT,
    net_pension_fund            BIGINT,
    net_private_fund            BIGINT,
    net_nation                  BIGINT,
    net_other_corp              BIGINT,
    net_dom_for                 BIGINT,

    fetched_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_stock_investor_breakdown UNIQUE (
        stock_id, trading_date, amt_qty_tp, trade_type, unit_tp, exchange_type
    )
);

CREATE INDEX idx_stock_investor_breakdown_date ON kiwoom.stock_investor_breakdown(trading_date);
CREATE INDEX idx_stock_investor_breakdown_stock ON kiwoom.stock_investor_breakdown(stock_id);
```

### 5.2 ORM 모델

```python
# app/adapter/out/persistence/models/stock_investor_breakdown.py
class StockInvestorBreakdown(Base):
    __tablename__ = "stock_investor_breakdown"
    __table_args__ = (
        UniqueConstraint(
            "stock_id", "trading_date", "amt_qty_tp",
            "trade_type", "unit_tp", "exchange_type",
            name="uq_stock_investor_breakdown",
        ),
        {"schema": "kiwoom"},
    )
    # ... 컬럼 정의 (위 SQL 동일)
```

### 5.3 row 수 추정

| 항목 | 값 |
|------|----|
| 종목 수 (active) | ~3,000 |
| amt_qty_tp × trade_type × unit_tp 조합 | 2 × 3 × 2 = 12 (전체) — 운영 default = (수량, 순매수, 천주) 1조합 |
| 1 종목 / 1일 / 1조합 | 1 row |
| 1일 row (default) | ~3,000 |
| 1년 (252 거래일) | ~756,000 |
| 3년 백필 | ~2.27M |

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomStkInfoClient.fetch_stock_investor_breakdown`

```python
class KiwoomStkInfoClient:
    async def fetch_stock_investor_breakdown(
        self,
        stock_code: str,
        *,
        on_date: date,
        amt_qty_tp: AmountQuantityType = AmountQuantityType.QUANTITY,
        trade_type: StockInvestorTradeType = StockInvestorTradeType.NET_BUY,
        unit_tp: UnitType = UnitType.THOUSAND_SHARES,
        exchange: ExchangeType = ExchangeType.KRX,
        max_pages: int = 5,
    ) -> tuple[list[StockInvestorBreakdownRow], dict[str, Any]]:
        """ka10059 — 종목별 투자자 wide breakdown.

        주의: 응답이 단일 일자 (`dt=on_date`) 1 row 기대 + cont-yn 페이지네이션 가능.
        """
        if not (len(stock_code) == 6 and stock_code.isdigit()):
            raise ValueError(f"stock_code 6자리 숫자만: {stock_code}")
        stk_cd = build_stk_cd(stock_code, exchange)

        body = {
            "dt": on_date.strftime("%Y%m%d"),
            "stk_cd": stk_cd,
            "amt_qty_tp": amt_qty_tp.value,
            "trde_tp": trade_type.value,
            "unit_tp": unit_tp.value,
        }

        all_rows: list[StockInvestorBreakdownRow] = []
        async for page in self._client.call_paginated(
            api_id="ka10059", endpoint=self.PATH, body=body, max_pages=max_pages,
        ):
            parsed = StockInvestorBreakdownResponse.model_validate(page.body)
            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id="ka10059",
                    return_code=parsed.return_code,
                    return_msg=parsed.return_msg,
                )
            all_rows.extend(parsed.stk_invsr_orgn)

        return all_rows, body
```

### 6.2 Repository — `StockInvestorBreakdownRepository`

```python
# app/adapter/out/persistence/repositories/stock_investor_breakdown.py
class StockInvestorBreakdownRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(
        self, rows: Sequence[NormalizedStockInvestorBreakdown],
    ) -> int:
        if not rows:
            return 0
        values = [
            {
                "stock_id": r.stock_id,
                "trading_date": r.trading_date,
                "amt_qty_tp": r.amt_qty_tp.value,
                "trade_type": r.trade_type.value,
                "unit_tp": r.unit_tp.value,
                "exchange_type": r.exchange_type.value,
                "current_price": r.current_price,
                "prev_compare_sign": r.prev_compare_sign,
                "prev_compare_amount": r.prev_compare_amount,
                "change_rate": r.change_rate,
                "acc_trade_volume": r.acc_trade_volume,
                "acc_trade_amount": r.acc_trade_amount,
                "net_individual": r.net_individual,
                "net_foreign": r.net_foreign,
                "net_institution_total": r.net_institution_total,
                "net_financial_inv": r.net_financial_inv,
                "net_insurance": r.net_insurance,
                "net_investment_trust": r.net_investment_trust,
                "net_other_financial": r.net_other_financial,
                "net_bank": r.net_bank,
                "net_pension_fund": r.net_pension_fund,
                "net_private_fund": r.net_private_fund,
                "net_nation": r.net_nation,
                "net_other_corp": r.net_other_corp,
                "net_dom_for": r.net_dom_for,
            }
            for r in rows if r.trading_date != date.min
        ]
        if not values:
            return 0

        stmt = pg_insert(StockInvestorBreakdown).values(values)
        update_set = {col: stmt.excluded[col] for col in values[0]
                      if col not in ("stock_id", "trading_date", "amt_qty_tp",
                                     "trade_type", "unit_tp", "exchange_type")}
        update_set["fetched_at"] = func.now()
        update_set["updated_at"] = func.now()
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_id", "trading_date", "amt_qty_tp",
                            "trade_type", "unit_tp", "exchange_type"],
            set_=update_set,
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return rowcount_of(result)

    async def get_range(
        self,
        stock_id: int,
        *,
        start_date: date,
        end_date: date,
        amt_qty_tp: AmountQuantityType = AmountQuantityType.QUANTITY,
        trade_type: StockInvestorTradeType = StockInvestorTradeType.NET_BUY,
        exchange: ExchangeType = ExchangeType.KRX,
    ) -> list[StockInvestorBreakdown]:
        stmt = (
            select(StockInvestorBreakdown)
            .where(
                StockInvestorBreakdown.stock_id == stock_id,
                StockInvestorBreakdown.amt_qty_tp == amt_qty_tp.value,
                StockInvestorBreakdown.trade_type == trade_type.value,
                StockInvestorBreakdown.exchange_type == exchange.value,
                StockInvestorBreakdown.trading_date >= start_date,
                StockInvestorBreakdown.trading_date <= end_date,
            )
            .order_by(StockInvestorBreakdown.trading_date)
        )
        return list((await self._session.execute(stmt)).scalars())
```

### 6.3 UseCase + Bulk

ka10058 패턴 + 종목 단위 호출. 운영 default = `(수량, 순매수, 천주, 통합)` 한 조합 × 3000 종목 = 3000 호출 / 일.

```python
class IngestStockInvestorBreakdownUseCase:
    """ka10059 — 단일 종목 wide breakdown 적재."""
    # ka10081 패턴과 같은 구조 (단일 종목 호출 + Bulk)


class IngestStockInvestorBreakdownBulkUseCase:
    """active 종목 일괄.

    동시성: RPS 4 + 250ms = 3000 / 4 × 0.25 = 188초 ≈ 3분 (이론).
    실측 추정 30~60분.
    """
    BATCH_SIZE = 50
    # ka10081 의 Bulk 패턴 동일
```

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **수동 단건** | on-demand | `POST /api/kiwoom/investor/stock/{stock_code}?dt=YYYY-MM-DD` |
| **수동 bulk** | on-demand | `POST /api/kiwoom/investor/stock/sync?dt=YYYY-MM-DD` |
| **일 1회 cron** | KST 20:30 평일 | ka10058 (20:00) 직후 |

라우터 + APScheduler 패턴은 ka10081 동일.

```python
scheduler.add_job(
    fire_stock_investor_breakdown_sync,
    CronTrigger(day_of_week="mon-fri", hour=20, minute=30, timezone=KST),
    id="stock_investor_breakdown_sync",
    ...
)
```

### 7.3 RPS / 시간

| 항목 | 값 |
|------|----|
| active 종목 | ~3,000 |
| 호출당 인터벌 | 250ms |
| 1회 sync 호출 | 3000 (1조합 default) |
| 이론 시간 | 188초 |
| 실측 추정 | 30~60분 |

→ cron 20:30 + 90분 grace.

---

## 8. 에러 처리

ka10058 동일.

---

## 9. 테스트

### 9.1 Unit

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 응답 | 200 + list 1건 (wide) | 1건 + 12 투자자 net 모두 정규화 |
| amt_qty_tp 분기 | QUANTITY | request body `amt_qty_tp="2"` |
| trde_tp 분기 (3종) | NET_BUY | `trde_tp="0"` |
| unit_tp 분기 | THOUSAND_SHARES | `unit_tp="1000"` |
| flu_rt 정규화 | "+698" | change_rate = Decimal("6.98") |
| 부호 포함 (foreign) | frgnr_invsr="-61779" | net_foreign = -61779 |
| 이중 부호 처리 | (`--714` 같은 case) | `_strip_double_sign_int` 동작 |
| orgn 합산 검증 | orgn=60195, fnnc/etc 합 | (정합성 check 안 함, raw 적재) |

### 9.2 Integration

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| INSERT (DB 빈) | stock 1건 + 응답 1 row | stock_investor_breakdown 1 row INSERT, 12 net 컬럼 채워짐 |
| UPDATE (멱등성) | 같은 호출 두 번 | row 1개 유지, updated_at 갱신 |
| 다른 amt_qty_tp 분리 | (수량) + (금액) 두 호출 | 2 row INSERT (UNIQUE 분리) |
| 다른 trde_tp 분리 | (순매수) + (매수만) 두 호출 | 2 row 분리 |
| KRX + NXT 분리 | nxt_enable=true 종목 | krx 1 + nxt 1 row (exchange_type 분리) |
| Bulk 50 batch | 100 종목 ingest | 50건마다 commit |
| 빈 응답 처리 | 응답 list=[] | upserted=0 |

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `app/adapter/out/kiwoom/stkinfo.py` — `KiwoomStkInfoClient.fetch_stock_investor_breakdown`
- [ ] `app/adapter/out/kiwoom/_records.py` — `StockInvestorBreakdownRow/Response`, `AmountQuantityType`, `StockInvestorTradeType`, `UnitType`
- [ ] `app/adapter/out/persistence/models/stock_investor_breakdown.py` — `StockInvestorBreakdown`
- [ ] `app/adapter/out/persistence/repositories/stock_investor_breakdown.py` — `StockInvestorBreakdownRepository`
- [ ] `app/application/service/investor_flow_service.py` — `IngestStockInvestorBreakdownUseCase`, `IngestStockInvestorBreakdownBulkUseCase`
- [ ] `app/adapter/web/routers/investor_flow.py` — POST/GET breakdown endpoints
- [ ] `app/batch/investor_flow_jobs.py` — APScheduler 등록 (KST mon-fri 20:30)
- [ ] `migrations/versions/008_investor_flow.py` — `stock_investor_breakdown` (ka10058/131 와 같은 마이그레이션)

### 10.2 테스트

- [ ] Unit 8 시나리오 PASS
- [ ] Integration 7 시나리오 PASS

### 10.3 운영 검증

- [ ] **`flu_rt` 표기 확정** ("우측 2자리 소수점" — `+698` = 6.98%)
- [ ] **`orgn = 12 sub-카테고리 합` 정합성 검증** (Excel 예시 1 차이)
- [ ] **`natfor` (내외국인) 의미** — Excel 명세 모호
- [ ] amt_qty_tp 별 응답 row 수 차이 (수량 vs 금액)
- [ ] trde_tp 별 응답 row 수 차이 (3종)
- [ ] unit_tp=1 (단주) 응답이 unit_tp=1000 (천주) × 1000 인지
- [ ] 페이지네이션 발생 빈도 (1 일자 = 보통 1 row 가정)
- [ ] **이중 부호 발생 빈도** (ka10086 동일 문제)
- [ ] NXT 응답 stk_cd 형식

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10059 stock investor breakdown ingest (wide format)`
- [ ] `master.md` § 12 결정 기록에:
  - `flu_rt` 표기 ("우측 2자리 소수점")
  - `natfor` 의미

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | 운영 default amt_qty_tp | QUANTITY (수량, 현재) / AMOUNT | Phase G 코드화 |
| 2 | 운영 default trde_tp | NET_BUY (현재) / 3종 모두 | Phase G 코드화 |
| 3 | 운영 default unit_tp | THOUSAND_SHARES (천주, 현재) / SINGLE_SHARE | Phase G 코드화 |
| 4 | NXT 호출 정책 | nxt_enable 만 | Phase G 코드화 |
| 5 | 백필 윈도 | 3년 / 1년 | Phase H |

### 11.2 알려진 위험

- **`flu_rt` 표기의 모호**: Excel "우측 2자리 소수점" — `+698` 이 +6.98% 가정. ka10058 의 `pre_rt` (`+7.43`) 와 다른 표기 — 운영 검증
- **`orgn` 합산 검증의 1 차이**: Excel 예시 60195 vs 합 60194 — 반올림? 다른 카테고리 누락? 운영 검증
- **`natfor` (내외국인) 의미**: Excel 명세 없음. "내국인 + 외국인" 합산? 별도 카테고리? ka10086 의 `for_*` 와 다른지 검증
- **`amt_qty_tp=1` (금액) 시 단위**: 백만원 vs 원 vs 천원. ka10086 의 외인순매수 단위 mismatch 와 같은 위험
- **이중 부호 (ka10086 의 `--714` 동일 위험)**: 12 카테고리 중 발생 가능. `_strip_double_sign_int` 재사용
- **wide 20 필드 ↔ long format 변환**: 백테스팅 엔진이 long 으로 사용한다면 view 또는 unpivot 쿼리 필요
- **ka10086 vs ka10059 의 같은 종목·같은 일자 net 일치도**: 데이터 정합성 1순위 — 어느 source 가 정답인지
- **3000 종목 × 60분 sync 의 자격증명 만료 위험**: au10001 24시간 만료. ka10081 동일 위험

### 11.3 ka10059 vs ka10058 vs ka10086 비교

| 항목 | ka10058 (long) | ka10059 (wide, 본) | ka10086 (Phase C) |
|------|-----------|---------|-----------|
| URL | /api/dostk/stkinfo | 동일 | /api/dostk/mrkcond |
| 호출 단위 | (투자자, 매매구분) → 종목 list | (종목, 일자) → 12 투자자 wide | (종목, 일자, 거래소) → wide (OHLCV + 신용 + 외인 비중 + 5 net) |
| 응답 row 수 | 50~200 | 1 | 1 |
| 응답 필드 수 | 11 | **20** | 22 |
| primary_metric | netslmt_qty | (없음 — wide row) | (없음) |
| 영속화 테이블 | investor_flow_daily | stock_investor_breakdown | stock_daily_flow |
| 백테스팅 시그널 | 종목 ranking | 종목 단위 12 투자자 | 종목 단위 종합 (OHLCV 외 5 net) |
| 12 투자자 카테고리 | 1개씩 호출 | wide 한 번에 | 5 카테고리만 (개인/외인/기관/사모/순매수합) |

→ **3 endpoint 책임 분리**:
- ka10058: ranking 추출 (종목 → 종합 시그널 후보)
- ka10059: 종목 단위 12 투자자 정밀 분석
- ka10086: 종목 단위 OHLCV + 매도 압력 (신용/외인 비중)

### 11.4 향후 확장

- **wide ↔ long 변환 view**: stock_investor_breakdown 의 12 net 컬럼을 (investor_type, net) 12 row 로 unpivot — 백테스팅 엔진의 long 쿼리 단순화
- **ka10086 vs ka10059 데이터 정합성 리포트**: 같은 종목·같은 일자의 net_individual / net_foreign / net_institution_total 비교 → 차이가 있으면 어느 source 가 정답인가
- **외인 + 기관계 동시 매수 종목 추출**: net_foreign > 0 AND net_institution_total > 0 → 강한 시그널
- **연기금/사모펀드의 ETF rotation 시그널**: net_pension_fund, net_private_fund 의 N일 연속 spike

---

_Phase G 의 두 번째 endpoint. ka10058 (long format ranking) 의 정반대 구조 — wide format 으로 종목 단위 12 투자자 net 정밀 분석. ka10086 와 책임 분리: ka10086 = 매도 압력 (신용/외인 비중) + 5 net 합계, ka10059 = 12 투자자 카테고리 정밀._
