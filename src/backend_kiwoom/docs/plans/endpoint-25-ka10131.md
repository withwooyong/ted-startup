# endpoint-25-ka10131.md — 기관외국인연속매매현황요청

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10131` |
| API 명 | 기관외국인연속매매현황요청 |
| 분류 | Tier 7 (투자자별 매매) |
| Phase | **G** |
| 우선순위 | **P2** |
| Method | `POST` |
| URL | `/api/dostk/frgnistt` |
| 의존 endpoint | `au10001`, `ka10099` (stock 마스터) |
| 후속 endpoint | (없음 — 25 endpoint 마지막) |

> **Phase G reference 는 endpoint-23-ka10058.md**. 본 계획서는 차이점만.

---

## 1. 목적

**기관/외국인 연속순매수 현황 ranking** — N일 연속 순매수가 강조된 시그널. ka10058 (특정 투자자 매매 ranking) / ka10059 (종목 단위 wide) 와 다른 차원: **연속 일수 자체가 시그널**.

1. **연속순매수 일수 시그널** — `frgnr_cont_netprps_dys` (외국인) / `orgn_cont_netprps_dys` (기관) — N일 연속이 길수록 강한 추세
2. **연속순매수 누적 (`cont_netprps_qty`/`amt`)** — 그 연속 기간의 누적 매수량/금액
3. **합계 (`tot_cont_netprps_*`)** — 기관 + 외국인 합산 연속 일수
4. **기간 주가 등락률 (`prid_stkpc_flu_rt`)** — 그 연속 기간 동안 주가 변동 → 매수가 효과적인지

**ka10058/59 와 차이**:
- URL `/api/dostk/frgnistt` (다른 카테고리)
- **`netslmt_tp=2` (순매수 고정)** — 매도 ranking 없음
- `dt` 파라미터 = `1`:최근일 / `3`:3일 / `5`/`10`/`20`/`120`/`0`:기간 — **연속 윈도 직접 지정**
- `stk_inds_tp` = `0`:종목 / `1`:업종 — 종목 단위와 업종 단위 분기

---

## 2. Request 명세

### 2.1 Body (8 필드)

| Element | 한글명 | Required | Length | Description |
|---------|-------|----------|--------|-------------|
| `dt` | 기간 | Y | 3 | `1`:최근일 / `3`/`5`/`10`/`20`/`120`:N일 / `0`:strt_dt~end_dt 기간 |
| `strt_dt` | 시작일자 | N | 8 | dt=0 시 사용 |
| `end_dt` | 종료일자 | N | 8 | dt=0 시 사용 |
| `mrkt_tp` | 장구분 | Y | 3 | `001`:코스피 / `101`:코스닥 |
| `netslmt_tp` | 순매도수구분 | Y | 1 | `2`:순매수 (**고정값**) |
| `stk_inds_tp` | 종목업종구분 | Y | 1 | `0`:종목(주식) / `1`:업종 |
| `amt_qty_tp` | 금액수량구분 | Y | 1 | `0`:금액 / `1`:수량 |
| `stex_tp` | 거래소구분 | Y | 1 | `1`/`2`/`3` |

> ⚠ **`amt_qty_tp` 의미가 ka10059 와 반대**: ka10059 는 `1`=금액 / `2`=수량, 본 endpoint 는 `0`=금액 / `1`=수량. UseCase enum 분리 + 운영 검증 1순위.

### 2.2 Pydantic

```python
class ContinuousPeriodType(StrEnum):
    """ka10131 의 dt — 연속 윈도."""
    LATEST = "1"
    DAYS_3 = "3"
    DAYS_5 = "5"
    DAYS_10 = "10"
    DAYS_20 = "20"
    DAYS_120 = "120"
    PERIOD = "0"           # strt_dt + end_dt 사용


class ContinuousAmtQtyType(StrEnum):
    """ka10131 만의 amt_qty_tp — ka10059 와 0/1 의미 반대."""
    AMOUNT = "0"
    QUANTITY = "1"


class StockIndsType(StrEnum):
    STOCK = "0"
    INDUSTRY = "1"


class ContinuousFrgnOrgnRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    dt: ContinuousPeriodType
    strt_dt: Annotated[str, Field(pattern=r"^\d{8}$")] | None = None
    end_dt: Annotated[str, Field(pattern=r"^\d{8}$")] | None = None
    mrkt_tp: InvestorMarketType                  # ka10058 의 001/101
    netslmt_tp: Literal["2"] = "2"               # 고정값
    stk_inds_tp: StockIndsType
    amt_qty_tp: ContinuousAmtQtyType
    stex_tp: RankingExchangeType
```

---

## 3. Response 명세 (19 필드)

### 3.1 Body

| Element | 한글명 | 영속화 | 메모 |
|---------|-------|--------|------|
| `orgn_frgnr_cont_trde_prst[]` | 기관외국인연속매매 list | (전체 row) | **list key 명** |
| `rank` | 순위 | rank (INTEGER) | 응답 list 순서 |
| `stk_cd` | 종목코드 | stock_id (FK) + stock_code_raw | Length=6 (NXT 미지원 가능) |
| `stk_nm` | 종목명 | stock_name | |
| `prid_stkpc_flu_rt` | 기간중주가등락률 | period_stock_price_flu_rt (Decimal, 부호) | |
| **`orgn_nettrde_amt`** | 기관순매매금액 | orgn_net_amount (BIGINT, 부호) | |
| **`orgn_nettrde_qty`** | 기관순매매량 | orgn_net_volume (BIGINT, 부호) | |
| **`orgn_cont_netprps_dys`** | 기관계연속순매수일수 | orgn_cont_days (INTEGER, 부호) | **연속 일수 시그널** |
| **`orgn_cont_netprps_qty`** | 기관계연속순매수량 | orgn_cont_volume (BIGINT, 부호) | 연속 기간 누적 |
| **`orgn_cont_netprps_amt`** | 기관계연속순매수금액 | orgn_cont_amount (BIGINT, 부호) | 연속 기간 누적 |
| **`frgnr_nettrde_qty`** | 외국인순매매량 | frgnr_net_volume (BIGINT, 부호) | |
| **`frgnr_nettrde_amt`** | 외국인순매매액 | frgnr_net_amount (BIGINT, 부호) | |
| **`frgnr_cont_netprps_dys`** | 외국인연속순매수일수 | frgnr_cont_days (INTEGER, 부호) | **시그널** |
| **`frgnr_cont_netprps_qty`** | 외국인연속순매수량 | frgnr_cont_volume (BIGINT, 부호) | |
| **`frgnr_cont_netprps_amt`** | 외국인연속순매수금액 | frgnr_cont_amount (BIGINT, 부호) | |
| **`nettrde_qty`** | 순매매량 | total_net_volume (BIGINT, 부호) | 기관 + 외국인 합 |
| **`nettrde_amt`** | 순매매액 | total_net_amount (BIGINT, 부호) | |
| **`tot_cont_netprps_dys`** | 합계연속순매수일수 | total_cont_days (INTEGER, 부호) | **종합 시그널** |
| **`tot_cont_nettrde_qty`** | 합계연속순매매수량 | total_cont_volume (BIGINT, 부호) | |
| **`tot_cont_netprps_amt`** | 합계연속순매수금액 | total_cont_amount (BIGINT, 부호) | |
| `return_code` | 처리코드 | (raw_response only) | |
| `return_msg` | 처리메시지 | (raw_response only) | |

### 3.2 Response 예시 (Excel 일부)

```json
{
    "orgn_frgnr_cont_trde_prst": [
        {
            "rank": "1",
            "stk_cd": "005930",
            "stk_nm": "삼성전자",
            "prid_stkpc_flu_rt": "-5.80",
            "orgn_nettrde_amt": "+48",
            "orgn_nettrde_qty": "+173",
            "orgn_cont_netprps_dys": "+1",
            "orgn_cont_netprps_qty": "+173",
            "orgn_cont_netprps_amt": "+48",
            "frgnr_nettrde_qty": "+0",
            "frgnr_nettrde_amt": "+0",
            "frgnr_cont_netprps_dys": "+1",
            "frgnr_cont_netprps_qty": "+1",
            "frgnr_cont_netprps_amt": "+0",
            "nettrde_qty": "+173",
            "nettrde_amt": "+48",
            "tot_cont_netprps_dys": "+2",
            "tot_cont_nettrde_qty": "+174",
            "tot_cont_netprps_amt": "+48"
        }
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다"
}
```

> 검증: `tot_cont_netprps_dys = orgn_cont_netprps_dys + frgnr_cont_netprps_dys` (2 = 1 + 1 ✓)

### 3.3 Pydantic + 정규화

```python
class ContinuousFrgnOrgnRow(BaseModel):
    """ka10131 응답 row — 19 필드."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    rank: str = ""
    stk_cd: str = ""
    stk_nm: str = ""
    prid_stkpc_flu_rt: str = ""
    orgn_nettrde_amt: str = ""
    orgn_nettrde_qty: str = ""
    orgn_cont_netprps_dys: str = ""
    orgn_cont_netprps_qty: str = ""
    orgn_cont_netprps_amt: str = ""
    frgnr_nettrde_qty: str = ""
    frgnr_nettrde_amt: str = ""
    frgnr_cont_netprps_dys: str = ""
    frgnr_cont_netprps_qty: str = ""
    frgnr_cont_netprps_amt: str = ""
    nettrde_qty: str = ""
    nettrde_amt: str = ""
    tot_cont_netprps_dys: str = ""
    tot_cont_nettrde_qty: str = ""
    tot_cont_netprps_amt: str = ""

    def to_normalized(
        self,
        *,
        stock_id: int | None,
        as_of_date: date,
        period_type: ContinuousPeriodType,
        market_type: InvestorMarketType,
        amt_qty_tp: ContinuousAmtQtyType,
        stk_inds_tp: StockIndsType,
        exchange_type: RankingExchangeType,
    ) -> "NormalizedFrgnOrgnConsecutive":
        return NormalizedFrgnOrgnConsecutive(
            stock_id=stock_id,
            stock_code_raw=self.stk_cd,
            stock_name=self.stk_nm,
            as_of_date=as_of_date,
            period_type=period_type,
            market_type=market_type,
            amt_qty_tp=amt_qty_tp,
            stk_inds_tp=stk_inds_tp,
            exchange_type=exchange_type,
            rank=_to_int(self.rank) or 0,
            period_stock_price_flu_rt=_to_decimal(self.prid_stkpc_flu_rt),
            orgn_net_amount=_strip_double_sign_int(self.orgn_nettrde_amt),
            orgn_net_volume=_strip_double_sign_int(self.orgn_nettrde_qty),
            orgn_cont_days=_strip_double_sign_int(self.orgn_cont_netprps_dys),
            orgn_cont_volume=_strip_double_sign_int(self.orgn_cont_netprps_qty),
            orgn_cont_amount=_strip_double_sign_int(self.orgn_cont_netprps_amt),
            frgnr_net_volume=_strip_double_sign_int(self.frgnr_nettrde_qty),
            frgnr_net_amount=_strip_double_sign_int(self.frgnr_nettrde_amt),
            frgnr_cont_days=_strip_double_sign_int(self.frgnr_cont_netprps_dys),
            frgnr_cont_volume=_strip_double_sign_int(self.frgnr_cont_netprps_qty),
            frgnr_cont_amount=_strip_double_sign_int(self.frgnr_cont_netprps_amt),
            total_net_volume=_strip_double_sign_int(self.nettrde_qty),
            total_net_amount=_strip_double_sign_int(self.nettrde_amt),
            total_cont_days=_strip_double_sign_int(self.tot_cont_netprps_dys),
            total_cont_volume=_strip_double_sign_int(self.tot_cont_nettrde_qty),
            total_cont_amount=_strip_double_sign_int(self.tot_cont_netprps_amt),
        )


class ContinuousFrgnOrgnResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    orgn_frgnr_cont_trde_prst: list[ContinuousFrgnOrgnRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""


@dataclass(frozen=True, slots=True)
class NormalizedFrgnOrgnConsecutive:
    stock_id: int | None
    stock_code_raw: str
    stock_name: str
    as_of_date: date
    period_type: ContinuousPeriodType
    market_type: InvestorMarketType
    amt_qty_tp: ContinuousAmtQtyType
    stk_inds_tp: StockIndsType
    exchange_type: RankingExchangeType
    rank: int
    period_stock_price_flu_rt: Decimal | None
    # 기관
    orgn_net_amount: int | None
    orgn_net_volume: int | None
    orgn_cont_days: int | None
    orgn_cont_volume: int | None
    orgn_cont_amount: int | None
    # 외국인
    frgnr_net_volume: int | None
    frgnr_net_amount: int | None
    frgnr_cont_days: int | None
    frgnr_cont_volume: int | None
    frgnr_cont_amount: int | None
    # 합계
    total_net_volume: int | None
    total_net_amount: int | None
    total_cont_days: int | None
    total_cont_volume: int | None
    total_cont_amount: int | None
```

---

## 4. NXT 처리

| 항목 | 적용 여부 |
|------|-----------|
| `stk_cd` 에 `_NX` suffix | (응답 row 의 stk_cd) — 보존 검증. 응답 length 6 명시 |
| `nxt_enable` 게이팅 | N (호출 시 stex_tp 분리) |
| `mrkt_tp` 별 분리 | **Y** (KOSPI / KOSDAQ) |
| `stex_tp` 별 분리 | **Y** (1/2/3) |

응답 stk_cd Length=6 으로 명시 → `_NX` stripped 가정. 검증 후 strip_kiwoom_suffix 패턴 적용.

---

## 5. DB 스키마

### 5.1 신규 테이블 — Migration 008 (`008_investor_flow.py`)

> ka10058 의 investor_flow_daily, ka10059 의 stock_investor_breakdown 와 같은 마이그레이션. **별도 테이블** (스키마 다름).

```sql
CREATE TABLE kiwoom.frgn_orgn_consecutive (
    id                              BIGSERIAL PRIMARY KEY,
    as_of_date                      DATE NOT NULL,                     -- 호출 일자 (기간 종료)
    period_type                     VARCHAR(3) NOT NULL,                -- "1"/"3"/"5"/"10"/"20"/"120"/"0"
    market_type                     VARCHAR(3) NOT NULL,                -- "001"/"101"
    amt_qty_tp                      VARCHAR(1) NOT NULL,                -- "0"/"1"
    stk_inds_tp                     VARCHAR(1) NOT NULL,                -- "0"/"1"
    exchange_type                   VARCHAR(1) NOT NULL,                -- "1"/"2"/"3"
    rank                            INTEGER NOT NULL,
    stock_id                        BIGINT REFERENCES kiwoom.stock(id) ON DELETE SET NULL,
    stock_code_raw                  VARCHAR(20) NOT NULL,
    stock_name                      VARCHAR(100),

    period_stock_price_flu_rt       NUMERIC(8, 4),
    -- 기관
    orgn_net_amount                 BIGINT,
    orgn_net_volume                 BIGINT,
    orgn_cont_days                  INTEGER,
    orgn_cont_volume                BIGINT,
    orgn_cont_amount                BIGINT,
    -- 외국인
    frgnr_net_volume                BIGINT,
    frgnr_net_amount                BIGINT,
    frgnr_cont_days                 INTEGER,
    frgnr_cont_volume               BIGINT,
    frgnr_cont_amount               BIGINT,
    -- 합계
    total_net_volume                BIGINT,
    total_net_amount                BIGINT,
    total_cont_days                 INTEGER,
    total_cont_volume               BIGINT,
    total_cont_amount               BIGINT,

    fetched_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_frgn_orgn_consecutive UNIQUE (
        as_of_date, period_type, market_type, amt_qty_tp,
        stk_inds_tp, exchange_type, rank
    )
);

CREATE INDEX idx_frgn_orgn_cons_date ON kiwoom.frgn_orgn_consecutive(as_of_date);
CREATE INDEX idx_frgn_orgn_cons_stock ON kiwoom.frgn_orgn_consecutive(stock_id)
    WHERE stock_id IS NOT NULL;
CREATE INDEX idx_frgn_orgn_cons_total_days
    ON kiwoom.frgn_orgn_consecutive(as_of_date, total_cont_days DESC NULLS LAST);
```

> **`idx_frgn_orgn_cons_total_days`**: 일별 합계 연속순매수 일수 상위 종목 조회 — 시그널 핵심.

### 5.2 ORM 모델

```python
# app/adapter/out/persistence/models/frgn_orgn_consecutive.py
class FrgnOrgnConsecutive(Base):
    __tablename__ = "frgn_orgn_consecutive"
    __table_args__ = (
        UniqueConstraint(
            "as_of_date", "period_type", "market_type", "amt_qty_tp",
            "stk_inds_tp", "exchange_type", "rank",
            name="uq_frgn_orgn_consecutive",
        ),
        {"schema": "kiwoom"},
    )
    # ... 컬럼 정의 (위 SQL 동일)
```

### 5.3 row 수 추정

| 항목 | 값 |
|------|----|
| 1 호출당 응답 row | ~50~200 |
| 호출 수 / 일 (default 4) | 4 (2 mkt × 2 amt_qty) |
| 1일 row | 200~800 |
| 1년 (252 거래일) | 50K~200K |
| 3년 백필 | 150K~600K |

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomForeignClient.fetch_continuous`

```python
# app/adapter/out/kiwoom/frgnistt.py
class KiwoomForeignClient:
    """`/api/dostk/frgnistt` 카테고리. ka10131 만의 첫 endpoint — 향후 추가 가능."""

    PATH = "/api/dostk/frgnistt"

    def __init__(self, kiwoom_client: KiwoomClient) -> None:
        self._client = kiwoom_client

    async def fetch_continuous(
        self,
        *,
        period_type: ContinuousPeriodType = ContinuousPeriodType.LATEST,
        start_date: date | None = None,
        end_date: date | None = None,
        market_type: InvestorMarketType = InvestorMarketType.KOSPI,
        stk_inds_tp: StockIndsType = StockIndsType.STOCK,
        amt_qty_tp: ContinuousAmtQtyType = ContinuousAmtQtyType.AMOUNT,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        max_pages: int = 5,
    ) -> tuple[list[ContinuousFrgnOrgnRow], dict[str, Any]]:
        """ka10131 — 기관/외국인 연속매매 ranking."""
        body: dict[str, Any] = {
            "dt": period_type.value,
            "strt_dt": start_date.strftime("%Y%m%d") if start_date else "",
            "end_dt": end_date.strftime("%Y%m%d") if end_date else "",
            "mrkt_tp": market_type.value,
            "netslmt_tp": "2",                  # 고정값
            "stk_inds_tp": stk_inds_tp.value,
            "amt_qty_tp": amt_qty_tp.value,
            "stex_tp": exchange_type.value,
        }

        all_rows: list[ContinuousFrgnOrgnRow] = []
        async for page in self._client.call_paginated(
            api_id="ka10131", endpoint=self.PATH, body=body, max_pages=max_pages,
        ):
            parsed = ContinuousFrgnOrgnResponse.model_validate(page.body)
            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id="ka10131",
                    return_code=parsed.return_code,
                    return_msg=parsed.return_msg,
                )
            all_rows.extend(parsed.orgn_frgnr_cont_trde_prst)

        return all_rows, body
```

### 6.2 Repository — `FrgnOrgnConsecutiveRepository`

```python
# app/adapter/out/persistence/repositories/frgn_orgn_consecutive.py
class FrgnOrgnConsecutiveRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, rows: Sequence[NormalizedFrgnOrgnConsecutive]) -> int:
        if not rows:
            return 0

        values = [
            {
                "as_of_date": r.as_of_date,
                "period_type": r.period_type.value,
                "market_type": r.market_type.value,
                "amt_qty_tp": r.amt_qty_tp.value,
                "stk_inds_tp": r.stk_inds_tp.value,
                "exchange_type": r.exchange_type.value,
                "rank": r.rank,
                "stock_id": r.stock_id,
                "stock_code_raw": r.stock_code_raw,
                "stock_name": r.stock_name,
                "period_stock_price_flu_rt": r.period_stock_price_flu_rt,
                "orgn_net_amount": r.orgn_net_amount,
                "orgn_net_volume": r.orgn_net_volume,
                "orgn_cont_days": r.orgn_cont_days,
                "orgn_cont_volume": r.orgn_cont_volume,
                "orgn_cont_amount": r.orgn_cont_amount,
                "frgnr_net_volume": r.frgnr_net_volume,
                "frgnr_net_amount": r.frgnr_net_amount,
                "frgnr_cont_days": r.frgnr_cont_days,
                "frgnr_cont_volume": r.frgnr_cont_volume,
                "frgnr_cont_amount": r.frgnr_cont_amount,
                "total_net_volume": r.total_net_volume,
                "total_net_amount": r.total_net_amount,
                "total_cont_days": r.total_cont_days,
                "total_cont_volume": r.total_cont_volume,
                "total_cont_amount": r.total_cont_amount,
            }
            for r in rows if r.rank > 0
        ]
        if not values:
            return 0

        stmt = pg_insert(FrgnOrgnConsecutive).values(values)
        update_set = {col: stmt.excluded[col] for col in values[0]
                      if col not in ("as_of_date", "period_type", "market_type",
                                     "amt_qty_tp", "stk_inds_tp", "exchange_type", "rank")}
        update_set["fetched_at"] = func.now()
        stmt = stmt.on_conflict_do_update(
            index_elements=["as_of_date", "period_type", "market_type",
                            "amt_qty_tp", "stk_inds_tp", "exchange_type", "rank"],
            set_=update_set,
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return rowcount_of(result)

    async def get_top_by_total_days(
        self,
        as_of_date: date,
        *,
        period_type: ContinuousPeriodType = ContinuousPeriodType.LATEST,
        market_type: InvestorMarketType = InvestorMarketType.KOSPI,
        limit: int = 50,
    ) -> list[FrgnOrgnConsecutive]:
        """합계 연속순매수 일수 상위 종목 — 시그널 핵심."""
        stmt = (
            select(FrgnOrgnConsecutive)
            .where(
                FrgnOrgnConsecutive.as_of_date == as_of_date,
                FrgnOrgnConsecutive.period_type == period_type.value,
                FrgnOrgnConsecutive.market_type == market_type.value,
            )
            .order_by(FrgnOrgnConsecutive.total_cont_days.desc().nulls_last())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars())
```

### 6.3 UseCase + Bulk

```python
class IngestFrgnOrgnConsecutiveUseCase:
    """단일 호출 (period_type, market_type, amt_qty_tp, stk_inds_tp, exchange_type) 적재."""
    # ka10058 패턴 동일


class IngestFrgnOrgnConsecutiveBulkUseCase:
    """일 1회 sync — 운영 default = 2 mkt × 2 amt_qty × 1 period (LATEST) = 4 호출.

    동시성: RPS 4 + 250ms = 1초 (이론).
    실측 1~10초.
    """
    # ka10058 BulkUseCase 패턴 동일
```

운영 default = `period_type ∈ {LATEST}` × `market_type ∈ {001, 101}` × `amt_qty_tp ∈ {0, 1}` × `stk_inds_tp = STOCK` × `exchange_type = UNIFIED` = **4 호출**.

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **수동** | on-demand | `POST /api/kiwoom/foreign/continuous?dt=1&mrkt_tp=001` |
| **수동 bulk** | on-demand | `POST /api/kiwoom/foreign/continuous/sync` |
| **일 1회 cron** | KST 21:00 평일 | ka10059 (20:30) 직후 — Phase G 마지막 |

```python
scheduler.add_job(
    fire_frgn_orgn_continuous_sync,
    CronTrigger(day_of_week="mon-fri", hour=21, minute=0, timezone=KST),
    id="frgn_orgn_continuous_sync",
    ...
)
```

### 7.3 RPS / 시간

| 항목 | 값 |
|------|----|
| 1 시점 sync 호출 | 4 |
| 이론 시간 | 4 / 4 × 0.25 = 0.25초 |
| 실측 추정 | 1~5초 |

---

## 8. 에러 처리

ka10058 동일.

---

## 9. 테스트

### 9.1 Unit

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 응답 | 200 + list 50건 | 50건 반환 |
| 빈 list | 200 | 빈 list |
| `return_code=1` | 비즈니스 에러 | `KiwoomBusinessError` |
| period_type 분기 | DAYS_5 | `dt="5"` |
| period_type=PERIOD | + strt_dt + end_dt | request body 채워짐 |
| amt_qty_tp 분기 (0/1) | AMOUNT | `amt_qty_tp="0"` |
| 부호 포함 (cont_days) | "+1" | `_strip_double_sign_int` → 1 |
| 부호 포함 (음수) | orgn_cont_days="-3" | -3 (3일 연속 매도) |
| tot_cont_days 검증 | total = orgn + frgnr | (정합성 check 안 함, raw 적재) |

### 9.2 Integration

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| INSERT (DB 빈) | 응답 50 row | frgn_orgn_consecutive 50 row INSERT |
| UPDATE (멱등성) | 같은 호출 두 번 | row 50개 유지 |
| 다른 period_type 분리 | LATEST + DAYS_5 두 호출 | 100 row INSERT (UNIQUE 분리) |
| 다른 amt_qty 분리 | AMOUNT + QUANTITY | 분리 |
| Bulk 4 호출 | 2 mkt × 2 amt_qty | 4 outcome |
| stock lookup miss | stock 비어있음 | stock_id=NULL |
| get_top_by_total_days 시그널 | 50 row 적재 | total_cont_days desc 정렬 50개 |

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `app/adapter/out/kiwoom/frgnistt.py` — `KiwoomForeignClient.fetch_continuous`
- [ ] `app/adapter/out/kiwoom/_records.py` — `ContinuousFrgnOrgnRow/Response`, `ContinuousPeriodType`, `ContinuousAmtQtyType`, `StockIndsType`
- [ ] `app/adapter/out/persistence/models/frgn_orgn_consecutive.py` — `FrgnOrgnConsecutive`
- [ ] `app/adapter/out/persistence/repositories/frgn_orgn_consecutive.py` — `FrgnOrgnConsecutiveRepository`
- [ ] `app/application/service/investor_flow_service.py` — `IngestFrgnOrgnConsecutiveUseCase`, `IngestFrgnOrgnConsecutiveBulkUseCase`
- [ ] `app/adapter/web/routers/foreign_continuous.py` — POST/GET endpoints
- [ ] `app/batch/investor_flow_jobs.py` — APScheduler 등록 (KST mon-fri 21:00)
- [ ] `migrations/versions/008_investor_flow.py` — `frgn_orgn_consecutive` (ka10058/59 와 같은 마이그레이션)

### 10.2 테스트

- [ ] Unit 9 시나리오 PASS
- [ ] Integration 7 시나리오 PASS

### 10.3 운영 검증

- [ ] **`amt_qty_tp` 의미 (0=금액, 1=수량) 확정** — ka10059 와 반대 (1=금액, 2=수량)
- [ ] **`tot_cont_netprps_dys = orgn_cont_netprps_dys + frgnr_cont_netprps_dys` 정합성**
- [ ] `period_type` 별 응답 row 수 (LATEST vs DAYS_120 차이)
- [ ] `cont_netprps_qty` 가 연속 기간 누적 (시작일 ~ 종료일) 인지 검증
- [ ] `prid_stkpc_flu_rt` (기간 등락률) 의 시작일 기준 (LATEST=어제? PERIOD=strt_dt~end_dt?)
- [ ] 응답 row 수 (한 페이지 ~50? 100?)
- [ ] **응답 stk_cd Length=6 명시 — NXT 응답 형식**
- [ ] netslmt_tp=2 외 다른 값 시도 시 응답 (예: =1 매도 가능?)

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10131 frgn orgn continuous trade ingest`
- [ ] `master.md` § 12 결정 기록에:
  - `amt_qty_tp` 의미 (ka10059 와 반대 — 운영 검증)
  - `period_type` 별 응답 차이

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | 운영 default period_type | LATEST (현재) / LATEST + DAYS_5 | Phase G 코드화 |
| 2 | 운영 default amt_qty | 둘 (현재) / AMOUNT 만 | Phase G 코드화 |
| 3 | stk_inds_tp 정책 | STOCK 만 / STOCK + INDUSTRY | Phase G 코드화 |
| 4 | 백필 윈도 | 3년 / 1년 / LATEST 만 forward-only | Phase H |
| 5 | 다중 시점 sync | 1 시점 (현재) / 다중 | Phase G 후반 |

### 11.2 알려진 위험

- **`amt_qty_tp` 의미 ka10059 와 반대 (★)**: ka10059 = `1`=금액 / `2`=수량, ka10131 = `0`=금액 / `1`=수량. 같은 키움 API 의 일관성 깨짐. 운영 1순위 검증 + 잘못 사용 시 단위 mismatch
- **이중 부호 (Phase C ka10086 동일)**: 19 필드 부호 처리 — `_strip_double_sign_int` 재사용
- **`tot_cont_netprps_dys` 산식 모호**: Excel 예시 `2 = 1 + 1` 합산. 그러나 다른 row 에서 `orgn_dys + frgnr_dys != tot_dys` 가능 — 운영 검증
- **`period_type=PERIOD` (0) 시 strt_dt/end_dt 응답 의미**: 그 기간의 연속 매수가 어떻게 산정되는지 (시작일 이전 연속 일수 포함?). 응답 의미 운영 검증
- **`cont_netprps_*` 누적 vs 일별**: 본 endpoint 응답이 그 기간 누적 (시작일~종료일 합산) 인지, 호출 시점 직전 N일 누적인지. 백테스팅 시점 보정 영향
- **응답 stk_cd Length=6 (★)**: NXT (`_NX`) 미지원 가능. ka20068 (대차 종목별) 동일 위험
- **`netslmt_tp=2` 고정의 의미**: 매도 ranking 미지원. 매도 추적은 ka10058 의 `trde_tp=1` (순매도) 로 보강
- **`stk_inds_tp=1` (업종) 응답 schema**: 종목과 같은지 다른지. 같은 schema 면 stock_code_raw 에 업종코드 들어감. 운영 검증 후 stock_id NULL 처리

### 11.3 ka10131 vs ka10058 비교

| 항목 | ka10131 (본) | ka10058 |
|------|---------|---------|
| URL | /api/dostk/frgnistt | /api/dostk/stkinfo |
| 호출 단위 | (period, market) → 종목 ranking | (investor, trade_type, market) → 종목 ranking |
| 투자자 카테고리 | 기관 + 외국인 + 합계 (3 wide) | 12 카테고리 중 1 |
| 매매구분 | 순매수 고정 (netslmt_tp=2) | 순매수 / 순매도 |
| 연속 일수 강조 | **Yes** (`cont_netprps_dys`) | No |
| 응답 필드 수 | 19 | 11 |
| 영속화 테이블 | frgn_orgn_consecutive | investor_flow_daily |
| 백테스팅 시그널 | **연속 일수 강조** (강한 추세) | 단일 매수/매도 ranking |
| amt_qty_tp 의미 | **0=금액, 1=수량** | (해당 없음 — ka10058 은 trde_tp 분기) |

→ 두 endpoint 보완: ka10058 = 단일 시점 ranking, ka10131 = 연속 추세 ranking.

### 11.4 ka10131 의 백테스팅 시그널 활용

```python
# Phase H derived feature (예시)
async def derive_strong_continuous_signal(
    repo: FrgnOrgnConsecutiveRepository,
    on_date: date,
    *,
    min_total_days: int = 5,        # 5일 연속 이상
    min_orgn_days: int = 3,
    min_frgnr_days: int = 3,
) -> list[Stock]:
    """기관 + 외국인 동시 연속 매수 종목 — 강한 추세 신호."""
    rows = await repo.get_top_by_total_days(on_date)
    return [
        r.stock for r in rows
        if r.total_cont_days and r.total_cont_days >= min_total_days
        and r.orgn_cont_days and r.orgn_cont_days >= min_orgn_days
        and r.frgnr_cont_days and r.frgnr_cont_days >= min_frgnr_days
    ]
```

→ ka10058 의 단일 시점 매수 상위 + ka10131 의 N일 연속 강조 → 두 시그널 교집합 = **강한 매수 추세 종목**.

### 11.5 향후 확장

- **ka10131 + ka10081 cross signal**: 연속순매수 일수 + 그 기간 주가 등락률 → 매수가 가격을 끌어올렸는지 검증
- **`prid_stkpc_flu_rt` 활용**: 연속 매수 후 주가가 오르는 비율 → 외인/기관 매수의 효과성 통계 (Phase H)
- **업종 단위 (stk_inds_tp=1)**: 업종별 연속 매수 시그널 — 섹터 회전 분석
- **연속 일수 spike alert**: total_cont_days 가 갑자기 N일 증가 (예: 0 → 5) → 추세 시작 시그널
- **ka10131 의 종목 단위 raw 시그널 vs ka10058 의 종목 ranking**: 두 source 의 같은 종목 cross-reference 데이터 품질 리포트

---

_Phase G 의 마지막이자 backend_kiwoom 25 endpoint 의 마지막. 외인/기관 연속순매수 일수 시그널 — 단일 시점 ranking (ka10058) 과 wide breakdown (ka10059) 의 시간 차원 보완. 25 endpoint 계획서 100% 완성으로 backend_kiwoom 의 코드화 진입 준비 완료._
