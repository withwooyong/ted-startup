# endpoint-12-ka10080.md — 주식분봉차트조회요청 (보강 시계열)

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10080` |
| API 명 | 주식분봉차트조회요청 |
| 분류 | Tier 4 (보강 시계열) |
| Phase | **D** |
| 우선순위 | **P2** (1주~2주 내) |
| Method | `POST` |
| URL | `/api/dostk/chart` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX 만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| 의존 endpoint | `au10001`, `ka10099` (stock 마스터 + nxt_enable 게이팅) |
| 후속 endpoint | (없음 — 일중 시그널 / 슬리피지 / 장중 진입 시뮬의 입력) |

---

## 1. 목적

**일중 N분 단위 OHLCV** 를 적재한다. ka10081 (일봉) 의 일 1 row 와 ka10079 (틱) 의 매 체결 사이의 sweet spot. 백테스팅 측면:

1. **장중 진입 시뮬** — 일봉 시가/종가 외에 09:00~15:30 사이의 분봉 진입 가능
2. **일봉 OHLC 검증** — 1분봉을 일 단위로 합성한 OHLC 가 ka10081 응답과 일치하는지
3. **변동성 시그널** — 분봉 단위 표준편차, 거래량 spike 탐지
4. **NXT 일중 가격 패턴** — KRX 정규장 후 NXT (~20:00 까지) 의 가격 변동

**왜 P2**:
- 백테스팅 첫 사이클에는 일봉으로 충분
- 그러나 시그널 정밀도 향상 / 진입 타이밍 분석은 분봉 필수 — Phase D 에서 안정 적재 가능 시 백테스팅 엔진의 v2 가 활용
- 데이터 부담은 틱보다 100~600배 가벼움 (1분봉 = 일 ~390 row, 1틱 = ~수만 row)

**Phase D 3 endpoint 중 본 endpoint 가 normal-path** — ka10079 (틱) 는 opt-in, ka20006 (업종) 은 종목과 별개 카테고리.

---

## 2. Request 명세

### 2.1 Header

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `api-id` | TR 명 | String | Y | 10 | `"ka10080"` 고정 |
| `authorization` | 접근토큰 | String | Y | 1000 | `Bearer <token>` |
| `cont-yn` | 연속조회 여부 | String | N | 1 | 응답 헤더 그대로 전달 |
| `next-key` | 연속조회 키 | String | N | 50 | 응답 헤더 그대로 전달 |

### 2.2 Body

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `stk_cd` | 종목코드 | String | Y | 20 | KRX `005930`, NXT `005930_NX`, SOR `005930_AL` |
| `tic_scope` | 틱범위 | String | Y | 2 | `1`/`3`/`5`/`10`/`15`/`30`/`45`/`60` (8개) |
| `upd_stkpc_tp` | 수정주가구분 | String | Y | 1 | `0`=원본 / `1`=수정주가 (백테스팅용) |
| `base_dt` | 기준일자 | String | **N** | 8 | `YYYYMMDD` — 미지정시 최신일 응답. 백필에 사용 |

> **`tic_scope` 가 ka10079 와 다름**: 분봉은 `15`/`45` 추가, `1`/`3`/`5`/`10`/`30` 공유. UseCase 에서 `MinuteScope` enum 분리 필수.
>
> **`base_dt` optional** — ka10081 일봉은 required, 본 endpoint 만 선택. 미지정시 키움이 가장 최근 일자 응답 추정 (운영 검증).

### 2.3 Request 예시 (Excel 원문)

```json
POST https://api.kiwoom.com/api/dostk/chart
Content-Type: application/json;charset=UTF-8
api-id: ka10080
authorization: Bearer Egicyx...

{
    "stk_cd": "005930",
    "tic_scope": "1",
    "upd_stkpc_tp": "1",
    "base_dt": "20260202"
}
```

### 2.4 Pydantic 모델

```python
# app/adapter/out/kiwoom/chart.py
class MinuteScope(StrEnum):
    """ka10080 의 tic_scope. ka10079 의 TickScope 와 분리."""
    MIN_1 = "1"
    MIN_3 = "3"
    MIN_5 = "5"
    MIN_10 = "10"
    MIN_15 = "15"
    MIN_30 = "30"
    MIN_45 = "45"
    MIN_60 = "60"


class MinuteChartRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    stk_cd: Annotated[str, Field(min_length=6, max_length=20)]
    tic_scope: MinuteScope
    upd_stkpc_tp: Literal["0", "1"]
    base_dt: Annotated[str, Field(pattern=r"^\d{8}$")] | None = None
```

> 백테스팅 호출은 항상 `upd_stkpc_tp="1"`. 백필 시 `base_dt=YYYYMMDD` 점진적 과거.

---

## 3. Response 명세

### 3.1 Header

| Element | Type | Description |
|---------|------|-------------|
| `api-id` | String | `"ka10080"` 에코 |
| `cont-yn` | String | `Y` 면 다음 페이지 |
| `next-key` | String | 다음 호출 헤더에 세팅 |

### 3.2 Body

| Element | 한글명 | Type | Length | 영속화 컬럼 | 메모 |
|---------|-------|------|--------|-------------|------|
| `stk_cd` | 종목코드 | String | 6 | (FK lookup) | NXT 응답에 `_NX` 보존 여부 운영 검증 |
| `stk_min_pole_chart_qry[]` | 분봉차트 list | LIST | — | (전체 row 적재) | **list key 명** |
| `cur_prc` | 현재가 (분봉의 종가) | String | 20 | `close_price` (BIGINT) | KRW. 부호 포함 (`-78800`) |
| `trde_qty` | 거래량 (이번 분봉의 거래량) | String | 20 | `trade_volume` (BIGINT) | 주 |
| `cntr_tm` | 체결시간 (분봉의 시작 또는 종료 시각) | String | 20 | `bucket_at` (TIMESTAMPTZ KST) | **`YYYYMMDDHHMMSS` 14자리** — 분봉의 어느 시점인지 운영 검증 |
| `open_pric` | 시가 (분봉의 시가) | String | 20 | `open_price` (BIGINT) | 부호 포함 가능 |
| `high_pric` | 고가 | String | 20 | `high_price` (BIGINT) | 부호 포함 가능 |
| `low_pric` | 저가 | String | 20 | `low_price` (BIGINT) | 부호 포함 가능 |
| **`acc_trde_qty`** | **누적 거래량** | String | 20 | `cumulative_volume` (BIGINT) | **★ Excel 스펙 표에는 없고 예시에만 등장** — 응답에 실제 오는지 운영 검증 1순위 |
| `pred_pre` | 전일대비 | String | 20 | `prev_compare_amount` (BIGINT) | 현재가 - 전일종가. 부호 포함 (`"-600"`) |
| `pred_pre_sig` | 전일대비기호 | String | 20 | `prev_compare_sign` (CHAR(1)) | `1`:상한가 / `2`:상승 / `3`:보합 / `4`:하한가 / `5`:하락 |
| `return_code` | 처리코드 | Integer | — | (raw_response only) | 0 정상 |
| `return_msg` | 처리메시지 | String | — | (raw_response only) | |

### 3.3 Response 예시 (Excel 원문)

```json
{
    "stk_cd": "005930",
    "stk_min_pole_chart_qry": [
        {
            "cur_prc": "-78800",
            "trde_qty": "7913",
            "cntr_tm": "20250917132000",
            "open_pric": "-78850",
            "high_pric": "-78900",
            "low_pric": "-78800",
            "acc_trde_qty": "14947571",
            "pred_pre": "-600",
            "pred_pre_sig": "5"
        },
        {
            "cur_prc": "-78900",
            "trde_qty": "16084",
            "cntr_tm": "20250917131900",
            "open_pric": "-78900",
            "high_pric": "-78900",
            "low_pric": "-78800",
            "acc_trde_qty": "14939658",
            "pred_pre": "-500",
            "pred_pre_sig": "5"
        }
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다"
}
```

> **Excel 예시는 DESC 정렬** (13:20 → 13:19). 운영 검증 1순위 — 응답 정렬 가정이 백테스팅 엔진의 시계열 입력에 직결.
>
> `cntr_tm` 분봉 의미: `20250917132000` = `13:20:00`. 이게 분봉의 **시작** (13:20~13:21) 인지 **종료** (13:19~13:20) 인지 운영 검증 필수.

### 3.4 Pydantic 모델 + 정규화

```python
# app/adapter/out/kiwoom/_records.py
class MinuteChartRow(BaseModel):
    """ka10080 응답 row."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    cur_prc: str = ""
    trde_qty: str = ""
    cntr_tm: str = ""
    open_pric: str = ""
    high_pric: str = ""
    low_pric: str = ""
    acc_trde_qty: str = ""              # ★ Excel 스펙 누락 — 응답에 실제 오는지 운영 검증
    pred_pre: str = ""
    pred_pre_sig: str = ""

    def to_normalized(
        self,
        *,
        stock_id: int,
        exchange: ExchangeType,
        adjusted: bool,
        tic_scope: MinuteScope,
    ) -> "NormalizedMinuteRow":
        return NormalizedMinuteRow(
            stock_id=stock_id,
            exchange=exchange,
            adjusted=adjusted,
            tic_scope=tic_scope.value,
            bucket_at=_parse_yyyymmddhhmmss_kst(self.cntr_tm)
                or datetime.min.replace(tzinfo=KST),
            close_price=_to_int(self.cur_prc),
            trade_volume=_to_int(self.trde_qty),
            open_price=_to_int(self.open_pric),
            high_price=_to_int(self.high_pric),
            low_price=_to_int(self.low_pric),
            cumulative_volume=_to_int(self.acc_trde_qty),
            prev_compare_amount=_to_int(self.pred_pre),
            prev_compare_sign=self.pred_pre_sig or None,
        )


class MinuteChartResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    stk_cd: str = ""
    stk_min_pole_chart_qry: list[MinuteChartRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""


@dataclass(frozen=True, slots=True)
class NormalizedMinuteRow:
    stock_id: int
    exchange: ExchangeType
    adjusted: bool
    tic_scope: str                  # "1"/"3"/.../"60"
    bucket_at: datetime             # KST aware
    close_price: int | None
    trade_volume: int | None
    open_price: int | None
    high_price: int | None
    low_price: int | None
    cumulative_volume: int | None
    prev_compare_amount: int | None
    prev_compare_sign: str | None
```

> `_parse_yyyymmddhhmmss_kst("20250917132000")` → `datetime(2025, 9, 17, 13, 20, 0, tzinfo=KST)`. ka10079 와 helper 공유.

---

## 4. NXT 처리

| 항목 | 적용 여부 |
|------|-----------|
| `stk_cd` 에 `_NX` suffix | **Y** (Length=20, Excel R22) |
| `nxt_enable` 게이팅 | **Y** |
| `mrkt_tp` 별 분리 | N |
| KRX 운영 / 모의 차이 | mockapi 는 KRX 전용 |

### 4.1 KRX/NXT 동시 호출 패턴

ka10081 일봉과 동일. KRX/NXT 독립 호출 + nxt_enable=true 만 NXT 호출 + KRX 실패해도 NXT 시도.

### 4.2 NXT 분봉의 의미

- **KRX 분봉**: 09:00~15:30 정규장 + 시간외 단일가 (9~15시 사이 6.5h × 60 / scope 분 = 1분봉 ~390 row/일)
- **NXT 분봉**: 8:00~20:00 추정 — KRX 정규장 외 시간대 데이터. 야간 가격 발견 패턴 분석에 사용
- **시그널**: NXT 16:00~20:00 가격 변동이 다음 KRX 시가에 미치는 영향

→ NXT 분봉은 **틱과 달리 전 종목 기본 ON**. 데이터 부담이 작음 (1분봉 × 12h = ~720 row/일).

---

## 5. DB 스키마

### 5.1 신규 테이블 — Migration 005 (`005_intraday.py`)

> ka10079 (틱) 와 같은 마이그레이션. 두 테이블 동시 생성.

```sql
CREATE TABLE kiwoom.stock_minute_price (
    id                       BIGSERIAL PRIMARY KEY,
    stock_id                 BIGINT NOT NULL REFERENCES kiwoom.stock(id) ON DELETE CASCADE,
    exchange                 VARCHAR(3) NOT NULL,            -- "KRX" / "NXT"
    tic_scope                VARCHAR(2) NOT NULL,            -- "1"/"3"/.../"60"
    bucket_at                TIMESTAMPTZ NOT NULL,            -- KST aware. 분봉의 시작 또는 종료 (운영 검증)
    adjusted                 BOOLEAN NOT NULL DEFAULT true,
    open_price               BIGINT,
    high_price               BIGINT,
    low_price                BIGINT,
    close_price              BIGINT,
    trade_volume             BIGINT,
    cumulative_volume        BIGINT,                         -- acc_trde_qty
    prev_compare_amount      BIGINT,
    prev_compare_sign        CHAR(1),
    fetched_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_minute_stock_exchange_scope_bucket
        UNIQUE (stock_id, exchange, tic_scope, bucket_at, adjusted)
)
PARTITION BY RANGE (bucket_at);

-- 월별 파티션
CREATE TABLE kiwoom.stock_minute_price_y2026m05 PARTITION OF kiwoom.stock_minute_price
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE kiwoom.stock_minute_price_y2026m06 PARTITION OF kiwoom.stock_minute_price
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
-- ... 추가 6개월

CREATE INDEX idx_minute_stock_exchange_scope_time
    ON kiwoom.stock_minute_price(stock_id, exchange, tic_scope, bucket_at);
CREATE INDEX idx_minute_bucket_at
    ON kiwoom.stock_minute_price(bucket_at);
```

### 5.2 ORM 모델

```python
# app/adapter/out/persistence/models/stock_minute_price.py
class StockMinutePrice(Base):
    __tablename__ = "stock_minute_price"
    __table_args__ = (
        UniqueConstraint(
            "stock_id", "exchange", "tic_scope", "bucket_at", "adjusted",
            name="uq_minute_stock_exchange_scope_bucket",
        ),
        {"schema": "kiwoom", "postgresql_partition_by": "RANGE (bucket_at)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("kiwoom.stock.id", ondelete="CASCADE"), nullable=False
    )
    exchange: Mapped[str] = mapped_column(String(3), nullable=False)
    tic_scope: Mapped[str] = mapped_column(String(2), nullable=False)
    bucket_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    adjusted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    open_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    high_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    low_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    close_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    trade_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cumulative_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_compare_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_compare_sign: Mapped[str | None] = mapped_column(String(1), nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )
```

### 5.3 row 수 추정 (전체 종목 1분봉)

| 시나리오 | row 수 |
|---------|--------|
| 1 종목 / KRX 정규장 6.5h / 1분봉 | ~390 |
| 1 종목 / NXT 12h / 1분봉 | ~720 |
| 3000 active × 1분봉 × KRX 1일 | ~1.17M |
| 3000 active × 1분봉 × KRX 1년 (252 거래일) | ~295M |
| 3000 active × 1분봉 × KRX+NXT 1년 (NXT 50%) | ~590M |
| **5분봉**으로 줄이면 | × 1/5 = 약 60~120M/년 |

→ **운영 default 권장**: 5분봉 / 전체 종목. 1분봉은 P0 종목만 또는 화이트리스트.

### 5.4 Retention

| 기간 | 사용처 |
|------|--------|
| 365 일 (5분봉) | 1년 백테스트 hot path |
| 90 일 (1분봉, P0 종목) | 정밀 시그널 |

→ Phase H 에서 retention drop. 단, 분봉은 일/주봉 합성으로 일부 정보 보존 가능.

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomChartClient.fetch_minute`

```python
# app/adapter/out/kiwoom/chart.py
class KiwoomChartClient:
    """ka10079~ka10094 공유."""

    PATH = "/api/dostk/chart"

    async def fetch_minute(
        self,
        stock_code: str,
        *,
        tic_scope: MinuteScope = MinuteScope.MIN_1,
        base_date: date | None = None,
        exchange: ExchangeType = ExchangeType.KRX,
        adjusted: bool = True,
        max_pages: int = 10,
    ) -> list[MinuteChartRow]:
        """단일 종목·단일 거래소·단일 tic_scope 의 분봉 시계열.

        - base_date 미지정 → 키움이 최신일 응답
        - cont-yn=Y 페이지네이션 자동 처리
        - max_pages=10 기본. 1분봉 백필 1주 = ~2000 row → ~3 페이지 추정 (운영 검증)
        """
        if not (len(stock_code) == 6 and stock_code.isdigit()):
            raise ValueError(f"stock_code 6자리 숫자만: {stock_code}")
        stk_cd = build_stk_cd(stock_code, exchange)

        body: dict[str, Any] = {
            "stk_cd": stk_cd,
            "tic_scope": tic_scope.value,
            "upd_stkpc_tp": "1" if adjusted else "0",
        }
        if base_date is not None:
            body["base_dt"] = base_date.strftime("%Y%m%d")

        all_rows: list[MinuteChartRow] = []
        async for page in self._client.call_paginated(
            api_id="ka10080",
            endpoint=self.PATH,
            body=body,
            max_pages=max_pages,
        ):
            parsed = MinuteChartResponse.model_validate(page.body)
            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id="ka10080",
                    return_code=parsed.return_code,
                    return_msg=parsed.return_msg,
                )
            all_rows.extend(parsed.stk_min_pole_chart_qry)

        return all_rows
```

### 6.2 Repository

```python
# app/adapter/out/persistence/repositories/stock_intraday.py
class StockMinutePriceRepository:
    """단일 테이블 (KRX/NXT 같은 테이블, exchange 컬럼으로 분리).

    StockTickPriceRepository 와는 별도 — 컬럼 다름 (cumulative_volume 추가).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, rows: Sequence[NormalizedMinuteRow]) -> int:
        if not rows:
            return 0

        values = [
            {
                "stock_id": r.stock_id,
                "exchange": r.exchange.value,
                "tic_scope": r.tic_scope,
                "bucket_at": r.bucket_at,
                "adjusted": r.adjusted,
                "open_price": r.open_price,
                "high_price": r.high_price,
                "low_price": r.low_price,
                "close_price": r.close_price,
                "trade_volume": r.trade_volume,
                "cumulative_volume": r.cumulative_volume,
                "prev_compare_amount": r.prev_compare_amount,
                "prev_compare_sign": r.prev_compare_sign,
            }
            for r in rows
            if r.bucket_at != datetime.min.replace(tzinfo=KST)    # 빈 cntr_tm skip
        ]
        if not values:
            return 0

        stmt = pg_insert(StockMinutePrice).values(values)
        update_set = {col: stmt.excluded[col] for col in values[0]
                      if col not in ("stock_id", "exchange", "tic_scope",
                                     "bucket_at", "adjusted")}
        update_set["fetched_at"] = func.now()
        update_set["updated_at"] = func.now()
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_id", "exchange", "tic_scope",
                            "bucket_at", "adjusted"],
            set_=update_set,
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return rowcount_of(result)

    async def get_latest_bucket(
        self,
        stock_id: int,
        *,
        exchange: ExchangeType,
        tic_scope: str = "1",
        adjusted: bool = True,
    ) -> datetime | None:
        """그 종목의 가장 최근 bucket_at — 백필 진입점 산정용."""
        stmt = (
            select(StockMinutePrice.bucket_at)
            .where(
                StockMinutePrice.stock_id == stock_id,
                StockMinutePrice.exchange == exchange.value,
                StockMinutePrice.tic_scope == tic_scope,
                StockMinutePrice.adjusted.is_(adjusted),
            )
            .order_by(StockMinutePrice.bucket_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_range(
        self,
        stock_id: int,
        *,
        exchange: ExchangeType,
        tic_scope: str,
        start: datetime,
        end: datetime,
        adjusted: bool = True,
    ) -> list[StockMinutePrice]:
        stmt = (
            select(StockMinutePrice)
            .where(
                StockMinutePrice.stock_id == stock_id,
                StockMinutePrice.exchange == exchange.value,
                StockMinutePrice.tic_scope == tic_scope,
                StockMinutePrice.adjusted.is_(adjusted),
                StockMinutePrice.bucket_at >= start,
                StockMinutePrice.bucket_at <= end,
            )
            .order_by(StockMinutePrice.bucket_at)
        )
        return list((await self._session.execute(stmt)).scalars())
```

### 6.3 UseCase — `IngestMinuteUseCase`

```python
# app/application/service/intraday_service.py
class IngestMinuteUseCase:
    """단일 거래소 단일 종목 분봉 적재.

    멱등성: ON CONFLICT (stock_id, exchange, tic_scope, bucket_at, adjusted) UPDATE.
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
        self._minute_repo = StockMinutePriceRepository(session)
        self._env = env

    async def execute(
        self,
        stock_code: str,
        *,
        tic_scope: MinuteScope = MinuteScope.MIN_1,
        base_date: date | None = None,
        exchange: ExchangeType = ExchangeType.KRX,
        adjusted: bool = True,
    ) -> MinuteIngestOutcome:
        if self._env == "mock" and exchange is ExchangeType.NXT:
            return MinuteIngestOutcome(
                stock_code=stock_code, exchange=exchange, tic_scope=tic_scope,
                upserted=0, skipped=True, reason="mock_no_nxt",
            )

        stock = await self._lookup.ensure_exists(stock_code)
        if not stock.is_active:
            return MinuteIngestOutcome(
                stock_code=stock_code, exchange=exchange, tic_scope=tic_scope,
                upserted=0, skipped=True, reason="inactive",
            )
        if exchange is ExchangeType.NXT and not stock.nxt_enable:
            return MinuteIngestOutcome(
                stock_code=stock_code, exchange=exchange, tic_scope=tic_scope,
                upserted=0, skipped=True, reason="nxt_disabled",
            )

        try:
            raw_rows = await self._client.fetch_minute(
                stock_code,
                tic_scope=tic_scope,
                base_date=base_date,
                exchange=exchange,
                adjusted=adjusted,
            )
        except KiwoomBusinessError as exc:
            return MinuteIngestOutcome(
                stock_code=stock_code, exchange=exchange, tic_scope=tic_scope,
                upserted=0, error=f"business: {exc.return_code}",
            )

        normalized = [
            r.to_normalized(
                stock_id=stock.id, exchange=exchange,
                adjusted=adjusted, tic_scope=tic_scope,
            )
            for r in raw_rows
        ]
        upserted = await self._minute_repo.upsert_many(normalized)

        return MinuteIngestOutcome(
            stock_code=stock_code, exchange=exchange, tic_scope=tic_scope,
            base_date=base_date,
            fetched=len(raw_rows), upserted=upserted,
        )


@dataclass(frozen=True, slots=True)
class MinuteIngestOutcome:
    stock_code: str
    exchange: ExchangeType
    tic_scope: MinuteScope
    base_date: date | None = None
    fetched: int = 0
    upserted: int = 0
    skipped: bool = False
    reason: str | None = None
    error: str | None = None
```

### 6.4 Bulk — `IngestMinuteBulkUseCase`

```python
class IngestMinuteBulkUseCase:
    """active 종목의 분봉 일괄 적재.

    동시성: RPS 4 + 250ms.
    소요: 3000 종목 × 2 거래소 × 0.25s = 1500초 ≈ 25분 (이론).
      실측 추정 30~60분.

    화이트리스트 운영 (선택): only_stock_codes 로 제한 가능.
    """

    BATCH_SIZE = 50

    def __init__(
        self,
        session: AsyncSession,
        *,
        single_use_case: IngestMinuteUseCase,
    ) -> None:
        self._session = session
        self._single = single_use_case
        self._stock_repo = StockRepository(session)

    async def execute(
        self,
        *,
        tic_scope: MinuteScope = MinuteScope.MIN_5,    # 운영 default 5분
        base_date: date | None = None,
        only_stock_codes: Sequence[str] | None = None,
    ) -> MinuteBulkResult:
        stmt = select(Stock).where(Stock.is_active.is_(True))
        if only_stock_codes:
            stmt = stmt.where(Stock.stock_code.in_(only_stock_codes))
        stocks = list((await self._session.execute(stmt)).scalars())

        krx_outcomes: list[MinuteIngestOutcome] = []
        nxt_outcomes: list[MinuteIngestOutcome] = []

        for i, stock in enumerate(stocks, start=1):
            try:
                async with self._session.begin_nested():
                    o = await self._single.execute(
                        stock.stock_code,
                        tic_scope=tic_scope, base_date=base_date,
                        exchange=ExchangeType.KRX,
                    )
                    krx_outcomes.append(o)
            except Exception as exc:
                logger.warning("KRX minute ingest 실패 %s: %s", stock.stock_code, exc)
                krx_outcomes.append(MinuteIngestOutcome(
                    stock_code=stock.stock_code, exchange=ExchangeType.KRX,
                    tic_scope=tic_scope, error=f"{type(exc).__name__}: {exc}",
                ))

            if stock.nxt_enable:
                try:
                    async with self._session.begin_nested():
                        o = await self._single.execute(
                            stock.stock_code,
                            tic_scope=tic_scope, base_date=base_date,
                            exchange=ExchangeType.NXT,
                        )
                        nxt_outcomes.append(o)
                except Exception as exc:
                    logger.warning("NXT minute ingest 실패 %s: %s", stock.stock_code, exc)
                    nxt_outcomes.append(MinuteIngestOutcome(
                        stock_code=stock.stock_code, exchange=ExchangeType.NXT,
                        tic_scope=tic_scope, error=f"{type(exc).__name__}: {exc}",
                    ))

            if i % self.BATCH_SIZE == 0:
                await self._session.commit()
                logger.info("minute ingest progress %d/%d", i, len(stocks))

        await self._session.commit()
        return MinuteBulkResult(
            tic_scope=tic_scope,
            base_date=base_date,
            total_stocks=len(stocks),
            krx_outcomes=krx_outcomes,
            nxt_outcomes=nxt_outcomes,
        )


@dataclass(frozen=True, slots=True)
class MinuteBulkResult:
    tic_scope: MinuteScope
    base_date: date | None
    total_stocks: int
    krx_outcomes: list[MinuteIngestOutcome]
    nxt_outcomes: list[MinuteIngestOutcome]

    @property
    def total_rows_inserted(self) -> int:
        krx = sum(o.upserted for o in self.krx_outcomes)
        nxt = sum(o.upserted for o in self.nxt_outcomes)
        return krx + nxt
```

### 6.5 Backfill — `BackfillMinuteUseCase`

```python
class BackfillMinuteUseCase:
    """과거 일자 분봉 백필.

    base_date 를 점진적으로 과거로 이동:
      base_date = end_date → 응답
      가장 오래된 응답 일자 - 1일 → 다음 base_date 호출
      반복하다 start_date 도달 시 종료
    """

    async def execute(
        self,
        stock_codes: Sequence[str],
        *,
        end_date: date,
        days: int = 90,
        tic_scope: MinuteScope = MinuteScope.MIN_5,
        exchange: ExchangeType = ExchangeType.KRX,
    ) -> MinuteBulkResult:
        start_date = end_date - timedelta(days=days)
        # 종목별로 base_date 점진 호출 — 운영 검증: 1 페이지 응답 일수
        ...
```

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **수동 단건** | on-demand | `POST /api/kiwoom/minute/{stock_code}?tic_scope=5&exchange=KRX` (admin) |
| **수동 일괄** | on-demand | `POST /api/kiwoom/minute/sync?tic_scope=5` (admin) |
| **일 1회 cron** | KST 19:00 평일 | 5분봉 default. 본 endpoint 는 ka10086 (19:00) 와 시간 겹침 — 19:30 으로 분리 권장 |
| **백필** | on-demand | `python scripts/backfill_minute.py --tic_scope 5 --start 2026-04-01 --end 2026-05-07` |

### 7.1 라우터

```python
# app/adapter/web/routers/intraday.py
router = APIRouter(prefix="/api/kiwoom/minute", tags=["kiwoom-intraday"])


@router.post(
    "/{stock_code}",
    response_model=MinuteIngestOutcomeOut,
    dependencies=[Depends(require_admin_key)],
)
async def ingest_one_minute(
    stock_code: str,
    tic_scope: Literal["1", "3", "5", "10", "15", "30", "45", "60"] = Query(default="5"),
    base_date: date | None = Query(default=None),
    exchange: Literal["KRX", "NXT"] = Query(default="KRX"),
    adjusted: bool = Query(default=True),
    use_case: IngestMinuteUseCase = Depends(get_ingest_minute_use_case),
) -> MinuteIngestOutcomeOut:
    outcome = await use_case.execute(
        stock_code,
        tic_scope=MinuteScope(tic_scope),
        base_date=base_date,
        exchange=ExchangeType(exchange),
        adjusted=adjusted,
    )
    return MinuteIngestOutcomeOut.model_validate(asdict(outcome))


@router.post(
    "/sync",
    response_model=MinuteBulkResultOut,
    dependencies=[Depends(require_admin_key)],
)
async def sync_minute_bulk(
    body: MinuteBulkRequestIn = Body(default_factory=MinuteBulkRequestIn),
    use_case: IngestMinuteBulkUseCase = Depends(get_ingest_minute_bulk_use_case),
) -> MinuteBulkResultOut:
    result = await use_case.execute(
        tic_scope=MinuteScope(body.tic_scope or "5"),
        base_date=body.base_date,
        only_stock_codes=body.only_stock_codes or None,
    )
    return MinuteBulkResultOut.model_validate(asdict(result))


@router.get(
    "/{stock_code}",
    response_model=list[StockMinutePriceOut],
)
async def get_minute_range(
    stock_code: str,
    start: datetime = Query(...),
    end: datetime = Query(...),
    tic_scope: Literal["1", "3", "5", "10", "15", "30", "45", "60"] = Query(default="5"),
    exchange: Literal["KRX", "NXT"] = Query(default="KRX"),
    adjusted: bool = Query(default=True),
    session: AsyncSession = Depends(get_session),
) -> list[StockMinutePriceOut]:
    stock_repo = StockRepository(session)
    stock = await stock_repo.find_by_code(stock_code)
    if stock is None:
        raise HTTPException(status_code=404, detail=f"stock not found: {stock_code}")
    repo = StockMinutePriceRepository(session)
    rows = await repo.get_range(
        stock.id,
        exchange=ExchangeType(exchange),
        tic_scope=tic_scope,
        start=start, end=end,
        adjusted=adjusted,
    )
    return [StockMinutePriceOut.model_validate(r) for r in rows]
```

### 7.2 APScheduler Job

```python
# app/batch/minute_ingest_job.py
async def fire_minute_sync() -> None:
    """매 평일 19:30 KST — 5분봉 적재 (KRX + NXT).

    cron 시간 분리:
      18:30 — ka10081 (일봉)
      19:00 — ka10086 (일별 + 투자자별)
      19:30 — ka10080 (분봉)  ← 본 job
    """
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
            single = IngestMinuteUseCase(
                session, chart_client=chart, lookup_use_case=lookup,
                env=settings.kiwoom_default_env,
            )
            bulk = IngestMinuteBulkUseCase(session, single_use_case=single)
            result = await bulk.execute(
                tic_scope=MinuteScope.MIN_5,
                base_date=today,
            )
        logger.info(
            "minute sync 완료 base_date=%s tic_scope=%s total=%d rows=%d",
            today, result.tic_scope.value,
            result.total_stocks, result.total_rows_inserted,
        )
    except Exception:
        logger.exception("minute sync 콜백 예외")


scheduler.add_job(
    fire_minute_sync,
    CronTrigger(day_of_week="mon-fri", hour=19, minute=30, timezone=KST),
    id="minute_sync",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
    misfire_grace_time=60 * 90,    # 90분 grace
)
```

> ka10079 틱 (19:30) 과 시간 겹침 — 둘 다 활성화 시 분리 필요. 분봉 19:30, 틱 20:00 등.

### 7.3 RPS / 시간 추정

| 항목 | 값 (5분봉) |
|------|----|
| active 종목 수 | ~3,000 |
| nxt_enable 비율 | ~50% |
| 1회 sync 호출 수 | 3000 + 1500 = 4500 |
| 호출당 인터벌 | 250ms |
| 동시성 | 4 |
| 페이지네이션 평균 | 1 (5분봉 1일 = ~80 row, 1 페이지에 들어감 가정) |
| 이론 시간 | 4500 / 4 × 0.25 = 281초 ≈ 4.7분 |
| 실측 추정 | 30~60분 |

→ cron 19:30 + 90분 grace.

---

## 8. 에러 처리

| HTTP / 응답 | 도메인 예외 | 라우터 매핑 | UseCase 정책 |
|-------------|-------------|-------------|--------------|
| 400 (잘못된 stock_code) | `ValueError` | 400 | 호출 전 차단 |
| 401 / 403 | `KiwoomCredentialRejectedError` | 400 | bubble up |
| 429 | `KiwoomRateLimitedError` | 503 | tenacity 재시도 후 다음 종목 |
| 5xx, 네트워크 | `KiwoomUpstreamError` | 502 | 다음 종목 |
| `return_code != 0` | `KiwoomBusinessError` | 400 | outcome.error 로 노출, 다음 종목 |
| 응답 `cntr_tm=""` | (적재 skip) | — | upsert_many 가 자동 제외 |
| 빈 응답 `list=[]` | (정상) | — | upserted=0 |
| 페이지네이션 폭주 | `KiwoomPaginationLimitError` | 502 | max_pages=10 도달 시 중단 |
| FK 위반 | `IntegrityError` | 502 | UseCase 가 ensure_exists 선행 |
| **`acc_trde_qty` 응답에 없음** | (none → cumulative_volume=NULL) | — | warning 로그 + 첫 호출에만 alert |

### 8.1 partial 실패 알람

3000 active × 2 = 4500 호출 중 ka10081 과 동일:
- < 1%: 정상
- 1~5%: warning
- > 5%: error + alert

### 8.2 같은 호출 두 번 (멱등성)

UNIQUE (stock_id, exchange, tic_scope, bucket_at, adjusted) ON CONFLICT UPDATE — 마지막 값 갱신. 부작용 없음.

---

## 9. 테스트

### 9.1 Unit (MockTransport)

`tests/adapter/kiwoom/test_chart_minute.py`:

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 단일 페이지 | 200 + list 80건 + cont-yn=N | 80건 반환 |
| 페이지네이션 | 첫 200 + cont-yn=Y, 둘째 100 + N | 합쳐 N건 |
| 빈 list | 200 + `stk_min_pole_chart_qry=[]` | 빈 list 반환 |
| `return_code=1` | 비즈니스 에러 | `KiwoomBusinessError` |
| 401 | 자격증명 거부 | `KiwoomCredentialRejectedError` |
| stock_code "00593" | 호출 차단 | `ValueError` |
| ExchangeType.NXT | stk_cd build | request body `stk_cd="005930_NX"` |
| MinuteScope 분기 | MIN_15 | `tic_scope="15"` |
| upd_stkpc_tp 분기 | adjusted=False | `upd_stkpc_tp="0"` |
| base_date 지정 | `date(2026, 5, 7)` | request body `base_dt="20260507"` |
| base_date 미지정 | None | request body 에 base_dt 키 없음 |
| `cntr_tm=""` row | 빈 cntr_tm 1건 + 정상 4건 | repo 가 자동 skip |
| 부호 포함 | open_pric="-78850" | `_to_int` → -78850 |
| `acc_trde_qty` 누락 | row 에 acc_trde_qty 없음 | cumulative_volume=None |
| 페이지네이션 폭주 | cont-yn=Y 무한 | `max_pages=10` 도달 → `KiwoomPaginationLimitError` |

### 9.2 Integration (testcontainers)

`tests/application/test_minute_service.py`:

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| INSERT (DB 빈 상태) | stock 1건 + 응답 80 row | stock_minute_price 80 row INSERT |
| UPDATE (멱등성) | 같은 호출 두 번 | row 80개 유지, updated_at 갱신 |
| KRX + NXT 분리 적재 | nxt_enable=true 종목 | krx 80 + nxt 80 row, exchange 컬럼 분리 |
| `nxt_enable=false` skip | 종목.nxt_enable=false + NXT 호출 | outcome.skipped=true, reason="nxt_disabled" |
| inactive stock skip | is_active=false + 호출 | outcome.skipped=true, reason="inactive" |
| mock no NXT | env="mock" + ExchangeType.NXT | outcome.skipped=true, reason="mock_no_nxt" |
| tic_scope 분리 | scope=1 80건 + scope=5 16건 같은 종목 | 96 row (UNIQUE 분리) |
| adjusted 분리 | adjusted=true + adjusted=false 같은 bucket | 2 row |
| Bulk 50 batch commit | 100 종목 ingest | 50건마다 commit, 중간 오류 격리 |
| only_stock_codes 필터 | 화이트리스트 5종목 | 5종목만 처리 |
| 빈 응답 처리 | 응답 list=[] | upserted=0 |
| `acc_trde_qty` 누락 시 | 응답에 acc_trde_qty 키 없음 | cumulative_volume=NULL row INSERT |
| 월별 파티션 동작 | bucket_at 다른 두 달 row | 각각 다른 파티션에 INSERT |

### 9.3 E2E (요청 시 1회)

```python
@pytest.mark.requires_kiwoom_real
async def test_real_ka10080():
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

        # 삼성전자 5분봉 (오늘 기준)
        rows = await chart.fetch_minute(
            "005930",
            tic_scope=MinuteScope.MIN_5,
            base_date=date.today(),
            exchange=ExchangeType.KRX,
        )
        assert len(rows) >= 60     # 5분봉 1일 ~80 row 추정 (정규장 6.5h)

        first = rows[0]
        assert first.cntr_tm
        assert _parse_yyyymmddhhmmss_kst(first.cntr_tm) is not None
        assert first.cur_prc != ""

        # acc_trde_qty 검증 — Excel 예시에 있지만 응답에 실제 오는지
        assert first.acc_trde_qty != "" or len([r for r in rows if r.acc_trde_qty]) == 0
        # → 빈 문자열이라도 키 자체는 응답에 있음 / 또는 모든 row 가 빈 acc_trde_qty

        # NXT 5분봉
        nxt = await chart.fetch_minute(
            "005930",
            tic_scope=MinuteScope.MIN_5,
            base_date=date.today(),
            exchange=ExchangeType.NXT,
        )
        # NXT 가 시간외 데이터까지 응답하는지 확인 — 12h × 12 buckets/h = ~144 row 가능
        assert len(nxt) >= 1
    finally:
        async with KiwoomAuthClient(base_url="https://api.kiwoom.com") as auth:
            await auth.revoke_token(creds, token.token)
```

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `app/adapter/out/kiwoom/chart.py` — `KiwoomChartClient.fetch_minute`
- [ ] `app/adapter/out/kiwoom/_records.py` — `MinuteChartRow`, `MinuteChartResponse`, `NormalizedMinuteRow`, `MinuteScope` enum
- [ ] `app/adapter/out/persistence/models/stock_minute_price.py` — `StockMinutePrice` (월별 파티션)
- [ ] `app/adapter/out/persistence/repositories/stock_intraday.py` — `StockMinutePriceRepository` (ka10079 의 TickRepo 와 같은 파일)
- [ ] `app/application/service/intraday_service.py` — `IngestMinuteUseCase`, `IngestMinuteBulkUseCase`, `BackfillMinuteUseCase`
- [ ] `app/adapter/web/routers/intraday.py` — POST/GET endpoints (ka10079 과 같은 라우터)
- [ ] `app/batch/minute_ingest_job.py` — APScheduler 등록 (KST mon-fri 19:30)
- [ ] `migrations/versions/005_intraday.py` — `stock_minute_price` 월별 파티션 (ka10079 와 동일 마이그레이션)
- [ ] `scripts/backfill_minute.py` — CLI

### 10.2 테스트

- [ ] Unit 15 시나리오 (§9.1) PASS
- [ ] Integration 13 시나리오 (§9.2) PASS
- [ ] coverage `KiwoomChartClient.fetch_minute`, `IngestMinuteUseCase`, `StockMinutePriceRepository` ≥ 80%

### 10.3 운영 검증

- [ ] **`acc_trde_qty` 가 실제 응답에 오는가** (Excel 스펙 표 누락 vs 예시 등장 — 결정 1순위)
- [ ] `cntr_tm` 분봉 의미: 시작 시각인지 종료 시각인지 (예: `132000` = 13:20:00 이 13:20~13:21 의 시작인지 13:19~13:20 의 종료인지)
- [ ] `cntr_tm` 정렬 (Excel 예시는 DESC — 최신 → 오래)
- [ ] base_date 미지정 시 응답이 어느 일자인지 (오늘? 가장 최근 거래일?)
- [ ] base_date 지정 시 응답이 그 일자만인지 며칠 포함인지
- [ ] 1 페이지 응답 row 수 (5분봉 = ~80 추정, 1분봉 = ~390 추정)
- [ ] 페이지네이션 발생 빈도 (3000 종목 sync 의 평균 페이지 수)
- [ ] NXT 응답이 KRX 정규장 외 시간대까지 포함하는지 (8:00~20:00 추정)
- [ ] NXT 응답 stk_cd 형식 (`005930_NX` 보존 vs stripped)
- [ ] `pred_pre` 부호 일관성 (ka10079 의 `"500"` 과 본 endpoint 의 `"-600"` 차이)
- [ ] active 3000 + NXT 1500 sync 실측 시간

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10080 minute chart ingest (KRX + NXT, monthly partition)`
- [ ] `master.md` § 12 결정 기록에:
  - `acc_trde_qty` 응답 여부 확정
  - `cntr_tm` 분봉 의미 (시작/종료 시각)
  - `cntr_tm` 정렬 가정
  - 1 페이지 row 수 (1분봉 / 5분봉)
  - active 3000 + NXT 1500 sync 실측 시간

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | 운영 default tic_scope | 1분 (정밀) / 5분 (권장) / 10분 | Phase D 코드화 직전 |
| 2 | 1분봉 화이트리스트 운영 | 전체 active / KOSPI200 등 P0 종목만 (권장) / 운영자 수동 | Phase D 코드화 |
| 3 | NXT 분봉 수집 여부 | KRX 만 / KRX+NXT (권장) | Phase D 코드화 |
| 4 | retention 기간 | 365일 (5분봉) / 90일 (1분봉) / 다른 분봉 별도 | Phase H |
| 5 | cron 시간 | 19:30 (제안) / 18:00 (장 마감 직후) / 20:30 (NXT 종료 후) | Phase D 후반 |
| 6 | 백필 전략 | 종목당 base_date 점진 / 일별 전 종목 순회 | 1 페이지 일수 측정 후 |
| 7 | 파티션 boundary | 월별 (권장) / 주별 (1분봉 부담 큰 경우) | Phase D 코드화 |
| 8 | adjusted 정책 | 1 (권장) / 0 + 1 둘 다 | 백테스팅 정책 |

### 11.2 알려진 위험

- **`acc_trde_qty` 가 가장 큰 unknown** — Excel 스펙 표(R34)에는 없고 예시(R42)에만 등장. 실제 응답에 없으면 cumulative_volume 컬럼이 항상 NULL → 시그널 활용 불가. 첫 호출에서 raw response 확인 필수
- **`cntr_tm` 분봉의 시작/종료 의미** — `132000` 이 13:20 시작 (13:20~13:21) 인지 종료 (13:19~13:20) 인지에 따라 백테스팅 진입 시점이 1분 어긋남. 잘못 처리하면 시그널 검증이 1분 lag — 운영 검증 후 정규화 helper 보정
- **`cntr_tm` 정렬 미확정** — Excel 예시는 DESC. ka10081 일봉의 `dt` 도 정렬 미확정. 백테스팅 엔진은 ASC 가정 — 정규화 후 ORDER BY 강제
- **base_date 미지정 시 응답 범위** — 오늘만 vs 최근 N일 vs 정해진 page size. 백필 전략에 영향. 첫 호출에서 응답 일자 분포 확인
- **`pred_pre` 부호 일관성** — ka10079 Excel 예시는 부호 누락 (`"500"`), ka10080 은 부호 명시 (`"-600"`). 같은 키움 카테고리에서 다른 표현은 Excel 표기 오류일 가능성 — 운영 검증 필수
- **데이터 부담** — 5분봉 / 전체 종목 / 1년 = ~60M row × 2 거래소 = ~120M row. 월별 파티션 + retention 365일 운영 가능. 1분봉 까지 가면 600M+ — 화이트리스트 필수
- **수정주가 분봉의 의미** — 액면분할 당일 분봉이 어떻게 보정되는지 키움 명세 없음. ka10081 일봉 검증 후 본 endpoint 도 동일 가정
- **NXT 분봉 운영시간** — NXT 8:00~20:00 추정. 시간외 단일가 분봉이 응답에 포함되는지, 어떤 시간 범위를 응답하는지 운영 검증 필요
- **cont-yn 페이지네이션의 시간 경계** — 1 페이지가 어디서 끊기는지 (특정 일자 경계 / row 수 경계 / next-key 형식) 미확정. 페이지 경계가 일자 경계와 일치하지 않으면 백필 시 로직 복잡화
- **분봉 ↔ 일봉 합성 정합성** — 1분봉을 일 단위 OHLC 로 합성해 ka10081 일봉과 비교. 차이가 있으면 어느 source 가 정답인가? 데이터 품질 리포트 1순위

### 11.3 ka10079 vs ka10080 비교 (재정리)

| 항목 | ka10079 틱 | ka10080 분봉 |
|------|-----------|--------------|
| URL | /api/dostk/chart | 동일 |
| Body | stk_cd + tic_scope + upd_stkpc_tp | + **base_dt (optional)** |
| tic_scope 유효값 | 1/3/5/10/30 (5종) | 1/3/5/10/15/30/45/60 (8종) |
| 응답 list 키 | `stk_tic_chart_qry` | `stk_min_pole_chart_qry` |
| 응답 필드 수 | 8 | **9** (acc_trde_qty 추가) |
| 시간 컬럼 | `cntr_tm` (14자리) | 동일 |
| 백필 가능성 | 불가 (base_dt 없음) | **가능** |
| 화이트리스트 필수 | Yes | No (전체 종목 가능) |
| Repository | StockTickPriceRepository | StockMinutePriceRepository |
| Service | IngestTickUseCase | IngestMinuteUseCase |
| 테이블 | stock_tick_price | stock_minute_price |
| 마이그레이션 | 005_intraday.py 공유 | 동일 |

→ **두 endpoint 가 같은 마이그레이션 + 같은 라우터 + 같은 service 모듈**. UseCase / Repository / Model 만 분리.

### 11.4 ka10080 분봉 vs ka10081 일봉 합성 검증

```python
# Phase H 데이터 품질 리포트 (Pseudo-code)
async def verify_minute_to_daily_synthesis(stock_code: str, on_date: date) -> Report:
    """1분봉 합성 OHLC 와 ka10081 일봉 OHLC 비교."""
    one_min = await minute_repo.get_range(
        stock_id, exchange=KRX, tic_scope="1",
        start=datetime(on_date.year, on_date.month, on_date.day, 9, 0, tzinfo=KST),
        end=datetime(on_date.year, on_date.month, on_date.day, 15, 30, tzinfo=KST),
    )
    synth = synthesize_daily(one_min)        # open=첫분봉 시가, close=마지막 분봉 종가, ...
    daily = await daily_repo.get_one(stock_id, on_date, exchange=KRX)

    diff = abs(synth.close - daily.close_price) / daily.close_price
    if diff > 0.001:        # 0.1% 차이
        report.add_anomaly(stock_code, on_date, synth, daily)
    return report
```

→ **차이가 0% 가 정상**. 0.1% 이상 차이가 빈번하면 어느 source 가 정답인지 운영 결정 + 백테스팅 엔진의 source 변경.

### 11.5 향후 확장

- **분봉 → 일봉 합성 view**: stock_minute_price 의 1분봉을 일 단위로 GROUP BY 한 OHLCV — ka10081 비교 / 백필 누락 보완
- **분봉 변동성 시그널**: 분봉 단위 σ, log return → 시그널 derived feature
- **거래량 spike 탐지**: cumulative_volume 의 분 단위 증가율 패턴
- **장 시작 5분 / 장 마감 5분 패턴**: 동시호가 직후 / 정규장 마감 직전 분봉 별도 분석
- **WebSocket 실시간 분봉**: Phase 외 — 본 endpoint 는 batch 한정
- **TimescaleDB hypertable**: PG 파티션의 자동 chunk 관리 + 압축. Phase H

---

_Phase D 의 두 번째 endpoint, 그리고 normal-path. 일봉이 백테스팅의 1차 입력이고, 분봉은 정밀 시그널 / 진입 시뮬의 2차 입력. ka10079 (틱) 와 같은 카테고리지만 본 endpoint 가 백테스팅의 실용적 가치가 더 큼._
