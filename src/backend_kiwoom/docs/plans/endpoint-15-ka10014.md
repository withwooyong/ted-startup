# endpoint-15-ka10014.md — 공매도추이요청 (시그널 보강)

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10014` |
| API 명 | 공매도추이요청 |
| 분류 | Tier 5 (시그널 보강 — 공매도) |
| Phase | **E** |
| 우선순위 | **P1** (1주 내) |
| Method | `POST` |
| URL | `/api/dostk/shsa` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX 만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| 의존 endpoint | `au10001`, `ka10099` (stock 마스터 + nxt_enable) |
| 후속 endpoint | (없음 — 백테스팅 시그널의 입력) |

---

## 1. 목적

종목 단위 **공매도 일별 추이** 를 적재한다. 공매도는 백테스팅의 강한 시그널 — 외인/기관의 매도 압력을 수치화하고, 공매도 잔고 누적 / 평균 단가 / 거래 비중으로 추가 분석 가능.

1. **공매도 시그널** — `shrts_qty` (일별 공매도량) / `trde_wght` (매매비중) 의 spike 탐지
2. **누적 공매도 추세** — `ovr_shrts_qty` (기간 누적) 의 증감으로 매도 압력 추적
3. **공매도 평균가 비교** — `shrts_avg_pric` 와 종가 (`close_pric`) 차이로 공매도 세력의 손익 추정
4. **거래 비중 시그널** — 공매도 비중이 거래량의 N% 이상이면 매도 압력 강화 신호

**왜 P1**:
- 백테스팅 첫 사이클의 종목 OHLCV (Phase C) 만으로는 공매도 압력 시그널을 확인 불가
- KRX 공식 공매도 데이터는 `pykrx` 통해 가능했으나 KRX 익명 차단 (Memory: `project_krx_auth_blocker.md`) 로 신뢰 불가 — 키움이 정답 source
- ka10086 의 신용 데이터 (Phase C) 와 조합으로 매도 측 압력 종합 분석

**Phase E reference**: ka10068 / ka20068 (대차거래) 도 같은 카테고리 (공매도 ↔ 대차 ↔ 신용) — 본 계획서가 "기간 조회 + 종목 단위 시계열" 패턴의 reference. ka10068 은 시장 단위, ka20068 은 다시 종목 단위로 본 endpoint 와 동일 패턴.

---

## 2. Request 명세

### 2.1 Header

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `api-id` | TR 명 | String | Y | 10 | `"ka10014"` 고정 |
| `authorization` | 접근토큰 | String | Y | 1000 | `Bearer <token>` |
| `cont-yn` | 연속조회 여부 | String | N | 1 | 응답 헤더 그대로 전달 |
| `next-key` | 연속조회 키 | String | N | 50 | 응답 헤더 그대로 전달 |

### 2.2 Body

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `stk_cd` | 종목코드 | String | Y | **20** | KRX `005930`, NXT `005930_NX`, SOR `005930_AL` |
| `tm_tp` | 시간구분 | String | N | 1 | `0`:시작일 / `1`:기간 (운영 검증 — 두 값 차이 확인) |
| `strt_dt` | 시작일자 | String | Y | 8 | `YYYYMMDD` |
| `end_dt` | 종료일자 | String | Y | 8 | `YYYYMMDD` |

> **`tm_tp` 의미 미확정**: Excel 명세는 "시작일/기간" 두 값만 — 의미 모호. 첫 호출에서 두 값에 대해 응답 차이 확인 (예: `tm_tp=0` 은 strt_dt 만 사용?, `tm_tp=1` 은 strt_dt~end_dt 기간?)
>
> **`stk_cd` Length=20**: NXT (`005930_NX`) 호출 가능. master.md § 3 의 KRX/NXT 분리 원칙 적용.

### 2.3 Request 예시 (Excel 원문)

```json
POST https://api.kiwoom.com/api/dostk/shsa
Content-Type: application/json;charset=UTF-8
api-id: ka10014
authorization: Bearer Egicyx...

{
    "stk_cd": "005930",
    "tm_tp": "1",
    "strt_dt": "20250501",
    "end_dt": "20250519"
}
```

### 2.4 Pydantic 모델

```python
# app/adapter/out/kiwoom/shsa.py
class ShortSellingTimeType(StrEnum):
    """tm_tp 값 — 의미는 운영 검증 후 확정."""
    START_ONLY = "0"
    PERIOD = "1"


class ShortSellingTrendRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    stk_cd: Annotated[str, Field(min_length=6, max_length=20)]
    tm_tp: ShortSellingTimeType = ShortSellingTimeType.PERIOD
    strt_dt: Annotated[str, Field(pattern=r"^\d{8}$")]
    end_dt: Annotated[str, Field(pattern=r"^\d{8}$")]
```

---

## 3. Response 명세

### 3.1 Header

| Element | Type | Description |
|---------|------|-------------|
| `api-id` | String | `"ka10014"` 에코 |
| `cont-yn` | String | `Y` 면 다음 페이지 |
| `next-key` | String | 다음 호출 헤더에 세팅 |

### 3.2 Body

| Element | 한글명 | Type | Length | 영속화 컬럼 | 메모 |
|---------|-------|------|--------|-------------|------|
| `shrts_trnsn[]` | 공매도추이 list | LIST | — | (전체 row 적재) | **list key 명** |
| `dt` | 일자 | String | 20 | `trading_date` (DATE) | `YYYYMMDD` |
| `close_pric` | 종가 | String | 20 | `close_price` (BIGINT) | KRW. **부호 포함** (`-55800`) — ka10086/ka10081 와 동일 |
| `pred_pre_sig` | 전일대비기호 | String | 20 | `prev_compare_sign` (CHAR(1)) | `1`~`5` |
| `pred_pre` | 전일대비 | String | 20 | `prev_compare_amount` (BIGINT) | 부호 포함 |
| `flu_rt` | 등락율 | String | 20 | `change_rate` (NUMERIC(8,4)) | %. 부호 포함 (`-1.76`) |
| `trde_qty` | 거래량 | String | 20 | `trade_volume` (BIGINT) | 주 |
| `shrts_qty` | 공매도량 | String | 20 | `short_volume` (BIGINT) | **시그널 핵심** |
| `ovr_shrts_qty` | 누적공매도량 | String | 20 | `cumulative_short_volume` (BIGINT) | "설정 기간의 공매도량 합산" — 응답 기간의 누적 |
| `trde_wght` | 매매비중 | String | 20 | `short_trade_weight` (NUMERIC(8,4)) | %. 부호 포함 (`+8.58`) |
| `shrts_trde_prica` | 공매도거래대금 | String | 20 | `short_trade_amount` (BIGINT) | 백만원 추정 (운영 검증) |
| `shrts_avg_pric` | 공매도평균가 | String | 20 | `short_avg_price` (BIGINT) | KRW |
| `return_code` | 처리코드 | Integer | — | (raw_response only) | 0 정상 |
| `return_msg` | 처리메시지 | String | — | (raw_response only) | |

### 3.3 Response 예시 (Excel 원문, 일부)

```json
{
    "shrts_trnsn": [
        {
            "dt": "20250519",
            "close_pric": "-55800",
            "pred_pre_sig": "5",
            "pred_pre": "-1000",
            "flu_rt": "-1.76",
            "trde_qty": "9802105",
            "shrts_qty": "841407",
            "ovr_shrts_qty": "6424755",
            "trde_wght": "+8.58",
            "shrts_trde_prica": "46985302",
            "shrts_avg_pric": "55841"
        },
        {
            "dt": "20250516",
            "close_pric": "-56800",
            "pred_pre_sig": "5",
            "pred_pre": "-500",
            "flu_rt": "-0.87",
            "trde_qty": "10385352",
            "shrts_qty": "487354",
            "ovr_shrts_qty": "5583348",
            "trde_wght": "+4.69",
            "shrts_trde_prica": "27725268",
            "shrts_avg_pric": "56889"
        }
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다"
}
```

> **정렬 DESC**: 예시는 2025-05-19 → 2025-05-16 (최신 → 오래). ka10081 일봉과 동일 가정 — 운영 검증 후 정규화 ORDER BY 강제.

### 3.4 Pydantic 모델 + 정규화

```python
# app/adapter/out/kiwoom/_records.py
class ShortSellingRow(BaseModel):
    """ka10014 응답 row."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    dt: str = ""
    close_pric: str = ""
    pred_pre_sig: str = ""
    pred_pre: str = ""
    flu_rt: str = ""
    trde_qty: str = ""
    shrts_qty: str = ""
    ovr_shrts_qty: str = ""
    trde_wght: str = ""
    shrts_trde_prica: str = ""
    shrts_avg_pric: str = ""

    def to_normalized(
        self,
        *,
        stock_id: int,
        exchange: ExchangeType,
    ) -> "NormalizedShortSelling":
        return NormalizedShortSelling(
            stock_id=stock_id,
            trading_date=_parse_yyyymmdd(self.dt) or date.min,
            exchange=exchange,
            close_price=_to_int(self.close_pric),
            prev_compare_amount=_to_int(self.pred_pre),
            prev_compare_sign=self.pred_pre_sig or None,
            change_rate=_to_decimal(self.flu_rt),
            trade_volume=_to_int(self.trde_qty),
            short_volume=_to_int(self.shrts_qty),
            cumulative_short_volume=_to_int(self.ovr_shrts_qty),
            short_trade_weight=_to_decimal(self.trde_wght),
            short_trade_amount=_to_int(self.shrts_trde_prica),
            short_avg_price=_to_int(self.shrts_avg_pric),
        )


class ShortSellingResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    shrts_trnsn: list[ShortSellingRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""


@dataclass(frozen=True, slots=True)
class NormalizedShortSelling:
    stock_id: int
    trading_date: date
    exchange: ExchangeType
    close_price: int | None
    prev_compare_amount: int | None
    prev_compare_sign: str | None
    change_rate: Decimal | None
    trade_volume: int | None
    short_volume: int | None
    cumulative_short_volume: int | None
    short_trade_weight: Decimal | None
    short_trade_amount: int | None
    short_avg_price: int | None
```

---

## 4. NXT 처리

| 항목 | 적용 여부 |
|------|-----------|
| `stk_cd` 에 `_NX` suffix | **Y** (Length=20) |
| `nxt_enable` 게이팅 | **Y** |
| `mrkt_tp` 별 분리 | N |
| KRX 운영 / 모의 차이 | mockapi 는 KRX 전용 |

### 4.1 NXT 공매도 데이터의 의미

- **KRX 공매도**: 정규장 + 시간외 단일가 — 한국 시장의 주된 공매도 source
- **NXT 공매도**: NXT 거래소가 공매도를 허용하는지 운영 검증 필요. 거래소 운영 정책상 공매도 미지원 가능성 (NXT 호출 시 `return_code != 0` 또는 빈 list 가능)

→ NXT 호출은 **시도하되, 빈 응답 / 비즈니스 에러를 정상 처리** (master.md § 6.4 패턴). 백테스팅 시그널은 KRX 공매도 위주.

### 4.2 KRX/NXT 동시 호출 패턴

ka10081 일봉 동일 — KRX/NXT 독립 호출 + nxt_enable=true 만 NXT 시도 + KRX 실패해도 NXT 시도.

---

## 5. DB 스키마

### 5.1 신규 테이블 — Migration 006 (`006_short_lending.py`)

> ka10068 / ka20068 (대차거래) 와 같은 마이그레이션. 시그널 보강 카테고리 통합.

```sql
CREATE TABLE kiwoom.short_selling_kw (
    id                       BIGSERIAL PRIMARY KEY,
    stock_id                 BIGINT NOT NULL REFERENCES kiwoom.stock(id) ON DELETE CASCADE,
    trading_date             DATE NOT NULL,
    exchange                 VARCHAR(3) NOT NULL,            -- "KRX" / "NXT"
    close_price              BIGINT,
    prev_compare_amount      BIGINT,
    prev_compare_sign        CHAR(1),
    change_rate              NUMERIC(8, 4),
    trade_volume             BIGINT,
    short_volume             BIGINT,                          -- shrts_qty (시그널 핵심)
    cumulative_short_volume  BIGINT,                          -- ovr_shrts_qty (응답 기간 누적)
    short_trade_weight       NUMERIC(8, 4),                   -- trde_wght (%)
    short_trade_amount       BIGINT,                          -- 백만원 추정
    short_avg_price          BIGINT,                          -- shrts_avg_pric
    fetched_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_short_selling_kw UNIQUE (stock_id, trading_date, exchange)
);

CREATE INDEX idx_short_selling_kw_date ON kiwoom.short_selling_kw(trading_date);
CREATE INDEX idx_short_selling_kw_stock ON kiwoom.short_selling_kw(stock_id);
CREATE INDEX idx_short_selling_kw_weight_high
    ON kiwoom.short_selling_kw(trading_date, short_trade_weight DESC NULLS LAST)
    WHERE short_trade_weight IS NOT NULL;
```

> **`idx_short_selling_kw_weight_high`** — 일별 매매비중 상위 종목 조회 시그널 — partial index 로 NULL 제외.

### 5.2 ORM 모델

```python
# app/adapter/out/persistence/models/short_selling_kw.py
class ShortSellingKw(Base):
    __tablename__ = "short_selling_kw"
    __table_args__ = (
        UniqueConstraint("stock_id", "trading_date", "exchange",
                          name="uq_short_selling_kw"),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("kiwoom.stock.id", ondelete="CASCADE"), nullable=False
    )
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    exchange: Mapped[str] = mapped_column(String(3), nullable=False)

    close_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_compare_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_compare_sign: Mapped[str | None] = mapped_column(String(1), nullable=True)
    change_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    trade_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    short_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cumulative_short_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    short_trade_weight: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    short_trade_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    short_avg_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

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

### 5.3 row 수 추정

| 항목 | 값 |
|------|----|
| active 종목 수 | ~3,000 |
| nxt_enable 비율 (공매도 응답 가정) | ~30% (NXT 공매도 미지원 가능성) |
| 1일 row | 3,000 KRX + 900 NXT = ~3,900 |
| 1년 (252 거래일) | ~983,000 |
| 3년 백필 | ~2.95M |

→ 단일 테이블, 파티션 불필요. 종목 OHLCV 의 ~70% 부담.

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomShortSellingClient.fetch_trend`

```python
# app/adapter/out/kiwoom/shsa.py
class KiwoomShortSellingClient:
    """`/api/dostk/shsa` 카테고리. ka10014 외 추가 공매도 endpoint 가 들어오면 같은 클래스에 메서드 추가."""

    PATH = "/api/dostk/shsa"

    def __init__(self, kiwoom_client: KiwoomClient) -> None:
        self._client = kiwoom_client

    async def fetch_trend(
        self,
        stock_code: str,
        *,
        start_date: date,
        end_date: date,
        tm_tp: ShortSellingTimeType = ShortSellingTimeType.PERIOD,
        exchange: ExchangeType = ExchangeType.KRX,
        max_pages: int = 5,
    ) -> list[ShortSellingRow]:
        """단일 종목·단일 거래소의 공매도 추이.

        - tm_tp=PERIOD (default) — strt_dt~end_dt 기간 응답
        - max_pages=5 기본. 1 페이지 ~30 거래일 추정 (운영 검증)
        """
        if not (len(stock_code) == 6 and stock_code.isdigit()):
            raise ValueError(f"stock_code 6자리 숫자만: {stock_code}")
        stk_cd = build_stk_cd(stock_code, exchange)

        body = {
            "stk_cd": stk_cd,
            "tm_tp": tm_tp.value,
            "strt_dt": start_date.strftime("%Y%m%d"),
            "end_dt": end_date.strftime("%Y%m%d"),
        }

        all_rows: list[ShortSellingRow] = []
        async for page in self._client.call_paginated(
            api_id="ka10014",
            endpoint=self.PATH,
            body=body,
            max_pages=max_pages,
        ):
            parsed = ShortSellingResponse.model_validate(page.body)
            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id="ka10014",
                    return_code=parsed.return_code,
                    return_msg=parsed.return_msg,
                )
            all_rows.extend(parsed.shrts_trnsn)

        return all_rows
```

### 6.2 Repository

```python
# app/adapter/out/persistence/repositories/short_selling.py
class ShortSellingKwRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, rows: Sequence[NormalizedShortSelling]) -> int:
        if not rows:
            return 0

        values = [
            {
                "stock_id": r.stock_id,
                "trading_date": r.trading_date,
                "exchange": r.exchange.value,
                "close_price": r.close_price,
                "prev_compare_amount": r.prev_compare_amount,
                "prev_compare_sign": r.prev_compare_sign,
                "change_rate": r.change_rate,
                "trade_volume": r.trade_volume,
                "short_volume": r.short_volume,
                "cumulative_short_volume": r.cumulative_short_volume,
                "short_trade_weight": r.short_trade_weight,
                "short_trade_amount": r.short_trade_amount,
                "short_avg_price": r.short_avg_price,
            }
            for r in rows
            if r.trading_date != date.min
        ]
        if not values:
            return 0

        stmt = pg_insert(ShortSellingKw).values(values)
        update_set = {col: stmt.excluded[col] for col in values[0]
                      if col not in ("stock_id", "trading_date", "exchange")}
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
    ) -> list[ShortSellingKw]:
        stmt = (
            select(ShortSellingKw)
            .where(
                ShortSellingKw.stock_id == stock_id,
                ShortSellingKw.exchange == exchange.value,
                ShortSellingKw.trading_date >= start_date,
                ShortSellingKw.trading_date <= end_date,
            )
            .order_by(ShortSellingKw.trading_date)
        )
        return list((await self._session.execute(stmt)).scalars())

    async def get_high_weight_stocks(
        self,
        on_date: date,
        *,
        min_weight: Decimal,
        limit: int = 50,
    ) -> list[ShortSellingKw]:
        """일별 공매도 매매비중이 높은 종목 — 시그널 추출용."""
        stmt = (
            select(ShortSellingKw)
            .where(
                ShortSellingKw.trading_date == on_date,
                ShortSellingKw.short_trade_weight >= min_weight,
            )
            .order_by(ShortSellingKw.short_trade_weight.desc().nulls_last())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars())
```

### 6.3 UseCase — `IngestShortSellingUseCase`

```python
# app/application/service/short_selling_service.py
class IngestShortSellingUseCase:
    """단일 종목·단일 거래소 공매도 적재."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        shsa_client: KiwoomShortSellingClient,
        lookup_use_case: LookupStockUseCase,
        env: Literal["prod", "mock"] = "prod",
    ) -> None:
        self._session = session
        self._client = shsa_client
        self._lookup = lookup_use_case
        self._repo = ShortSellingKwRepository(session)
        self._env = env

    async def execute(
        self,
        stock_code: str,
        *,
        start_date: date,
        end_date: date,
        tm_tp: ShortSellingTimeType = ShortSellingTimeType.PERIOD,
        exchange: ExchangeType = ExchangeType.KRX,
    ) -> ShortSellingIngestOutcome:
        if self._env == "mock" and exchange is ExchangeType.NXT:
            return ShortSellingIngestOutcome(
                stock_code=stock_code, exchange=exchange,
                upserted=0, skipped=True, reason="mock_no_nxt",
            )

        stock = await self._lookup.ensure_exists(stock_code)
        if not stock.is_active:
            return ShortSellingIngestOutcome(
                stock_code=stock_code, exchange=exchange,
                upserted=0, skipped=True, reason="inactive",
            )
        if exchange is ExchangeType.NXT and not stock.nxt_enable:
            return ShortSellingIngestOutcome(
                stock_code=stock_code, exchange=exchange,
                upserted=0, skipped=True, reason="nxt_disabled",
            )

        try:
            raw_rows = await self._client.fetch_trend(
                stock_code,
                start_date=start_date, end_date=end_date,
                tm_tp=tm_tp, exchange=exchange,
            )
        except KiwoomBusinessError as exc:
            return ShortSellingIngestOutcome(
                stock_code=stock_code, exchange=exchange,
                upserted=0, error=f"business: {exc.return_code}",
            )

        normalized = [
            r.to_normalized(stock_id=stock.id, exchange=exchange)
            for r in raw_rows
        ]
        upserted = await self._repo.upsert_many(normalized)

        return ShortSellingIngestOutcome(
            stock_code=stock_code, exchange=exchange,
            start_date=start_date, end_date=end_date,
            fetched=len(raw_rows), upserted=upserted,
        )


@dataclass(frozen=True, slots=True)
class ShortSellingIngestOutcome:
    stock_code: str
    exchange: ExchangeType
    start_date: date | None = None
    end_date: date | None = None
    fetched: int = 0
    upserted: int = 0
    skipped: bool = False
    reason: str | None = None
    error: str | None = None
```

### 6.4 Bulk — `IngestShortSellingBulkUseCase`

```python
class IngestShortSellingBulkUseCase:
    """active 종목 공매도 일괄 적재.

    동시성: RPS 4 + 250ms.
    소요: 3000 × 0.25s = 750초 ≈ 12분 (이론, KRX 만).
      KRX + NXT (~30%) = 3,900 호출 → 16분.
      실측 추정 30~60분.
    """

    BATCH_SIZE = 50

    def __init__(
        self,
        session: AsyncSession,
        *,
        single_use_case: IngestShortSellingUseCase,
    ) -> None:
        self._session = session
        self._single = single_use_case
        self._stock_repo = StockRepository(session)

    async def execute(
        self,
        *,
        start_date: date,
        end_date: date,
        only_market_codes: Sequence[str] | None = None,
        only_stock_codes: Sequence[str] | None = None,
    ) -> ShortSellingBulkResult:
        stmt = select(Stock).where(Stock.is_active.is_(True))
        if only_market_codes:
            stmt = stmt.where(Stock.market_code.in_(only_market_codes))
        if only_stock_codes:
            stmt = stmt.where(Stock.stock_code.in_(only_stock_codes))
        stocks = list((await self._session.execute(stmt)).scalars())

        krx_outcomes: list[ShortSellingIngestOutcome] = []
        nxt_outcomes: list[ShortSellingIngestOutcome] = []

        for i, stock in enumerate(stocks, start=1):
            try:
                async with self._session.begin_nested():
                    o = await self._single.execute(
                        stock.stock_code,
                        start_date=start_date, end_date=end_date,
                        exchange=ExchangeType.KRX,
                    )
                    krx_outcomes.append(o)
            except Exception as exc:
                logger.warning("KRX short ingest 실패 %s: %s", stock.stock_code, exc)
                krx_outcomes.append(ShortSellingIngestOutcome(
                    stock_code=stock.stock_code, exchange=ExchangeType.KRX,
                    error=f"{type(exc).__name__}: {exc}",
                ))

            if stock.nxt_enable:
                try:
                    async with self._session.begin_nested():
                        o = await self._single.execute(
                            stock.stock_code,
                            start_date=start_date, end_date=end_date,
                            exchange=ExchangeType.NXT,
                        )
                        nxt_outcomes.append(o)
                except Exception as exc:
                    logger.warning("NXT short ingest 실패 %s: %s", stock.stock_code, exc)
                    nxt_outcomes.append(ShortSellingIngestOutcome(
                        stock_code=stock.stock_code, exchange=ExchangeType.NXT,
                        error=f"{type(exc).__name__}: {exc}",
                    ))

            if i % self.BATCH_SIZE == 0:
                await self._session.commit()
                logger.info("short ingest progress %d/%d", i, len(stocks))

        await self._session.commit()
        return ShortSellingBulkResult(
            start_date=start_date, end_date=end_date,
            total_stocks=len(stocks),
            krx_outcomes=krx_outcomes,
            nxt_outcomes=nxt_outcomes,
        )


@dataclass(frozen=True, slots=True)
class ShortSellingBulkResult:
    start_date: date
    end_date: date
    total_stocks: int
    krx_outcomes: list[ShortSellingIngestOutcome]
    nxt_outcomes: list[ShortSellingIngestOutcome]

    @property
    def total_rows_inserted(self) -> int:
        krx = sum(o.upserted for o in self.krx_outcomes)
        nxt = sum(o.upserted for o in self.nxt_outcomes)
        return krx + nxt
```

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **수동 단건** | on-demand | `POST /api/kiwoom/short/{stock_code}?start=YYYY-MM-DD&end=YYYY-MM-DD&exchange=KRX` (admin) |
| **수동 일괄** | on-demand | `POST /api/kiwoom/short/sync` (admin) |
| **일 1회 cron** | KST 19:45 평일 | 종목 OHLCV 카테고리 (18:30~19:30) 종료 후. 주 단위 윈도 호출 |
| **백필** | on-demand | `python scripts/backfill_short.py --start 2023-01-01 --end 2026-05-07` |

### 7.1 라우터

```python
# app/adapter/web/routers/short_selling.py
router = APIRouter(prefix="/api/kiwoom/short", tags=["kiwoom-short-selling"])


@router.post(
    "/{stock_code}",
    response_model=ShortSellingIngestOutcomeOut,
    dependencies=[Depends(require_admin_key)],
)
async def ingest_one_short(
    stock_code: str,
    start: date = Query(...),
    end: date = Query(...),
    exchange: Literal["KRX", "NXT"] = Query(default="KRX"),
    use_case: IngestShortSellingUseCase = Depends(get_ingest_short_use_case),
) -> ShortSellingIngestOutcomeOut:
    outcome = await use_case.execute(
        stock_code,
        start_date=start, end_date=end,
        exchange=ExchangeType(exchange),
    )
    return ShortSellingIngestOutcomeOut.model_validate(asdict(outcome))


@router.post(
    "/sync",
    response_model=ShortSellingBulkResultOut,
    dependencies=[Depends(require_admin_key)],
)
async def sync_short_bulk(
    body: ShortSellingBulkRequestIn,
    use_case: IngestShortSellingBulkUseCase = Depends(get_ingest_short_bulk_use_case),
) -> ShortSellingBulkResultOut:
    result = await use_case.execute(
        start_date=body.start_date,
        end_date=body.end_date,
        only_market_codes=body.only_market_codes or None,
        only_stock_codes=body.only_stock_codes or None,
    )
    return ShortSellingBulkResultOut.model_validate(asdict(result))


@router.get(
    "/{stock_code}",
    response_model=list[ShortSellingOut],
)
async def get_short_range(
    stock_code: str,
    start: date = Query(...),
    end: date = Query(...),
    exchange: Literal["KRX", "NXT"] = Query(default="KRX"),
    session: AsyncSession = Depends(get_session),
) -> list[ShortSellingOut]:
    stock_repo = StockRepository(session)
    stock = await stock_repo.find_by_code(stock_code)
    if stock is None:
        raise HTTPException(status_code=404, detail=f"stock not found: {stock_code}")
    repo = ShortSellingKwRepository(session)
    rows = await repo.get_range(
        stock.id, exchange=ExchangeType(exchange),
        start_date=start, end_date=end,
    )
    return [ShortSellingOut.model_validate(r) for r in rows]


@router.get(
    "/signals/high-weight",
    response_model=list[ShortSellingOut],
)
async def get_high_weight_signals(
    on_date: date = Query(...),
    min_weight: Decimal = Query(default=Decimal("5.0")),
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[ShortSellingOut]:
    """일별 매매비중 상위 종목 — 시그널 추출."""
    repo = ShortSellingKwRepository(session)
    rows = await repo.get_high_weight_stocks(
        on_date, min_weight=min_weight, limit=limit,
    )
    return [ShortSellingOut.model_validate(r) for r in rows]
```

### 7.2 APScheduler Job

```python
# app/batch/short_selling_job.py
async def fire_short_selling_sync() -> None:
    """매 평일 19:45 KST — 직전 1주 공매도 적재.

    cron 시간 chain:
      18:30 — ka10081 (일봉)
      19:00 — ka10086 (일별 + 투자자별)
      19:15 — ka20006 (업종 일봉)
      19:30 — ka10080 (분봉)
      19:45 — ka10014 (공매도) ← 본 job
      20:00 — ka10068 (대차) ← 다음 endpoint
    """
    today = date.today()
    if not is_trading_day(today):
        return
    try:
        async with get_sessionmaker()() as session:
            kiwoom_client = build_kiwoom_client_for("prod-main")
            shsa = KiwoomShortSellingClient(kiwoom_client)
            stkinfo = KiwoomStkInfoClient(kiwoom_client)
            lookup = LookupStockUseCase(
                session, stkinfo_client=stkinfo, env=settings.kiwoom_default_env,
            )
            single = IngestShortSellingUseCase(
                session, shsa_client=shsa, lookup_use_case=lookup,
                env=settings.kiwoom_default_env,
            )
            bulk = IngestShortSellingBulkUseCase(session, single_use_case=single)

            # 직전 7일 (주말/공휴일 포함, 응답이 거래일만 응답)
            result = await bulk.execute(
                start_date=today - timedelta(days=7),
                end_date=today,
            )
        logger.info(
            "short selling sync 완료 total=%d rows=%d",
            result.total_stocks, result.total_rows_inserted,
        )
    except Exception:
        logger.exception("short selling sync 콜백 예외")


scheduler.add_job(
    fire_short_selling_sync,
    CronTrigger(day_of_week="mon-fri", hour=19, minute=45, timezone=KST),
    id="short_selling_sync",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
    misfire_grace_time=60 * 90,    # 90분 grace
)
```

### 7.3 RPS / 시간 추정

| 항목 | 값 |
|------|----|
| active 종목 수 | ~3,000 |
| nxt_enable + 공매도 응답 비율 | ~30% (NXT 공매도 제한 가능성) |
| 호출당 인터벌 | 250ms |
| 동시성 | 4 |
| 1회 sync 호출 수 | 3000 + 900 = 3,900 |
| 페이지네이션 평균 | 1 (7일 윈도 ~ 5 거래일 < 1 페이지) |
| 이론 시간 | 3900 / 4 × 0.25 = 244초 ≈ 4분 |
| 실측 추정 | 30~60분 |

→ cron 19:45 + 90분 grace.

---

## 8. 에러 처리

| HTTP / 응답 | 도메인 예외 | 라우터 매핑 | UseCase 정책 |
|-------------|-------------|-------------|--------------|
| 400 (잘못된 stock_code) | `ValueError` | 400 | 호출 전 차단 |
| 401 / 403 | `KiwoomCredentialRejectedError` | 400 | bubble up |
| 429 | `KiwoomRateLimitedError` | 503 | 재시도 후 다음 종목 |
| 5xx, 네트워크 | `KiwoomUpstreamError` | 502 | 다음 종목 |
| `return_code != 0` | `KiwoomBusinessError` | 400 | outcome.error 노출, 다음 종목 |
| 응답 `dt=""` | (적재 skip) | — | upsert_many 자동 제외 |
| 빈 응답 `list=[]` | (정상 — 공매도 없는 종목) | — | upserted=0 |
| NXT 빈 응답 (NXT 공매도 미지원) | (정상) | — | upserted=0, warning 안 함 |
| 페이지네이션 폭주 | `KiwoomPaginationLimitError` | 502 | max_pages=5 도달 시 중단 |
| FK 위반 | `IntegrityError` | 502 | UseCase 가 ensure_exists 선행 |

### 8.1 partial 실패 알람

3000 KRX × 1 호출 = 3000 + NXT (~900) = 3,900 호출 중:
- < 5%: 정상 (NXT 공매도 미지원 빈 응답 다수 가능)
- 5~15%: warning
- > 15%: error + alert

### 8.2 같은 호출 두 번 (멱등성)

UNIQUE (stock_id, trading_date, exchange) ON CONFLICT UPDATE — 마지막 값 갱신.

⚠ **`ovr_shrts_qty` (누적공매도량) 의 의미**: 응답 기간 내 누적 (`strt_dt`~응답 row 일자). 같은 일자 row 라도 호출 시 strt_dt 가 다르면 누적값이 다름 — UPDATE 시 마지막 호출의 strt_dt 기준 누적값으로 덮어씀. 백테스팅 일관성을 위해 **항상 strt_dt 를 고정** (예: 그 종목의 최초 상장일 또는 운영자 결정 base 일자).

---

## 9. 테스트

### 9.1 Unit (MockTransport)

`tests/adapter/kiwoom/test_shsa_client.py`:

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 단일 페이지 | 200 + list 5건 | 5건 반환 |
| 페이지네이션 | 첫 cont-yn=Y, 둘째 N | 합쳐 N건 |
| 빈 list (공매도 없는 종목) | 200 + `shrts_trnsn=[]` | 빈 list |
| `return_code=1` | 비즈니스 에러 | `KiwoomBusinessError` |
| 401 | 자격증명 거부 | `KiwoomCredentialRejectedError` |
| stock_code "00593" | 호출 차단 | `ValueError` |
| ExchangeType.NXT | stk_cd build | request body `stk_cd="005930_NX"` |
| tm_tp 분기 | START_ONLY | `tm_tp="0"` |
| `dt=""` row | 빈 dt 1건 + 정상 4건 | repo skip |
| 부호 포함 | close_pric="-55800" | `_to_int` → -55800 |
| 등락율 부호 | flu_rt="-1.76" | `_to_decimal` → Decimal("-1.76") |
| 매매비중 부호 | trde_wght="+8.58" | `_to_decimal` → Decimal("8.58") |
| 페이지네이션 폭주 | cont-yn=Y 무한 | `max_pages=5` 도달 → `KiwoomPaginationLimitError` |

### 9.2 Integration (testcontainers)

`tests/application/test_short_selling_service.py`:

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| INSERT (DB 빈) | stock 1건 + 응답 5 row | short_selling_kw 5 row INSERT |
| UPDATE (멱등성) | 같은 호출 두 번 | row 5개 유지, updated_at 갱신 |
| KRX + NXT 분리 적재 | nxt_enable=true | krx 5 + nxt 5 row, exchange 컬럼 분리 |
| `nxt_enable=false` skip | 종목.nxt_enable=false + NXT 호출 | outcome.skipped=true |
| inactive stock skip | is_active=false | outcome.skipped=true |
| mock no NXT | env="mock" + NXT | outcome.skipped=true, reason="mock_no_nxt" |
| 빈 응답 (NXT 공매도 미지원) | 응답 list=[] | upserted=0, warning 없음 |
| Bulk 50 batch | 100 종목 | 50건마다 commit |
| only_market_codes 필터 | KOSPI 만 | KOSDAQ skip |
| `ovr_shrts_qty` 누적값 | 다른 strt_dt 두 번 호출 | UPDATE 마지막 호출 값으로 |
| high_weight 시그널 추출 | 100 row 중 weight > 5% 가 20개 | get_high_weight 가 20개 반환 |

### 9.3 E2E

```python
@pytest.mark.requires_kiwoom_real
async def test_real_ka10014():
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
        shsa = KiwoomShortSellingClient(kiwoom_client)

        rows = await shsa.fetch_trend(
            "005930",
            start_date=date.today() - timedelta(days=14),
            end_date=date.today(),
            exchange=ExchangeType.KRX,
        )
        assert len(rows) >= 5    # 14일 ≈ 10 거래일

        first = rows[0]
        assert first.dt
        assert first.shrts_qty != ""

        # tm_tp 의미 검증 — START_ONLY vs PERIOD 응답 차이
        rows_start = await shsa.fetch_trend(
            "005930",
            start_date=date.today() - timedelta(days=14),
            end_date=date.today(),
            tm_tp=ShortSellingTimeType.START_ONLY,
            exchange=ExchangeType.KRX,
        )
        # 응답 row 수 / 일자 분포 비교 (운영 검증 후 가정 확정)
    finally:
        async with KiwoomAuthClient(base_url="https://api.kiwoom.com") as auth:
            await auth.revoke_token(creds, token.token)
```

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `app/adapter/out/kiwoom/shsa.py` — `KiwoomShortSellingClient.fetch_trend`
- [ ] `app/adapter/out/kiwoom/_records.py` — `ShortSellingRow`, `ShortSellingResponse`, `NormalizedShortSelling`
- [ ] `app/adapter/out/persistence/models/short_selling_kw.py` — `ShortSellingKw`
- [ ] `app/adapter/out/persistence/repositories/short_selling.py` — `ShortSellingKwRepository`
- [ ] `app/application/service/short_selling_service.py` — `IngestShortSellingUseCase`, `IngestShortSellingBulkUseCase`
- [ ] `app/adapter/web/routers/short_selling.py` — POST/GET endpoints + 시그널 추출
- [ ] `app/batch/short_selling_job.py` — APScheduler 등록 (KST mon-fri 19:45)
- [ ] `migrations/versions/006_short_lending.py` — `short_selling_kw` (ka10068/ka20068 의 lending_balance_kw 와 같은 마이그레이션)
- [ ] `scripts/backfill_short.py` — CLI

### 10.2 테스트

- [ ] Unit 13 시나리오 (§9.1) PASS
- [ ] Integration 11 시나리오 (§9.2) PASS
- [ ] coverage `KiwoomShortSellingClient`, `IngestShortSellingUseCase`, `ShortSellingKwRepository` ≥ 80%

### 10.3 운영 검증

- [ ] **`tm_tp` 의미 확정** — `0` (START_ONLY) vs `1` (PERIOD) 의 응답 차이 (row 수 / 일자 분포)
- [ ] **NXT 공매도 응답 가능 여부** — NXT 거래소 공매도 데이터 존재 확인
- [ ] `dt` 정렬 (Excel 예시 DESC — ka10081 동일 가정)
- [ ] `shrts_trde_prica` 단위 (백만원 vs 원, ka10081 와 동일 운영 검증)
- [ ] **`ovr_shrts_qty` 누적 의미** — 응답 기간 누적인지 종목 전체 누적인지 (Excel "설정 기간의 공매도량 합산" 모호)
- [ ] 1 페이지 응답 일수 (1주 윈도 = ~5 거래일 < 1 페이지 가정)
- [ ] active 3000 + NXT 900 sync 실측 시간
- [ ] partial 실패율 (NXT 빈 응답 비율)
- [ ] `pred_pre_sig` 분포 (1~5)

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10014 short selling trend ingest (KRX + NXT)`
- [ ] `master.md` § 12 결정 기록에:
  - `tm_tp` 의미 확정
  - NXT 공매도 응답 가능성
  - `ovr_shrts_qty` 누적 의미

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | `tm_tp` default | START_ONLY (0) / **PERIOD (1)** (권장) | 운영 검증 후 |
| 2 | sync 윈도 | 1주 (현재) / 1달 / 1일 (당일만) | Phase E 코드화 직전 |
| 3 | 백필 윈도 | 3년 (ka10081 와 동일) / 1년 | Phase H |
| 4 | NXT 호출 정책 | 시도 (현재) / KRX 만 | 운영 검증 후 |
| 5 | 부분 실패 alert 임계치 | 5%/15% (현재) / 다른 비율 | 운영 1주 모니터 후 |
| 6 | `ovr_shrts_qty` 의미 처리 | **응답 그대로 적재** (현재) / 자체 누적 계산 | 운영 검증 후 |
| 7 | high_weight 시그널 임계치 | 5% (현재) / 10% | 백테스팅 정책 |

### 11.2 알려진 위험

- **`tm_tp` 의미 미확정**: Excel 명세 모호 — 잘못 사용 시 응답이 의도와 다를 수 있음. 운영 1순위 검증
- **NXT 공매도 미지원 가능성**: NXT 거래소 운영 정책상 공매도 차단 가능 — 호출 시 `return_code != 0` 또는 빈 list 응답. 본 endpoint 의 partial 실패율 추정에 영향
- **`ovr_shrts_qty` 누적 모호**: "설정 기간의 공매도량 합산" 이 응답 기간 누적인지 종목 누적인지. 같은 일자 row 라도 strt_dt 다른 호출에서 누적값 달라질 수 있음 — UPDATE 정책 결정
- **`shrts_trde_prica` 단위**: 백만원 추정. ka10081 의 `trde_prica` 와 같은 단위 가정 — 운영 검증 후 master.md § 12 한 번만 기록
- **응답 정렬 미확정**: Excel 예시는 DESC. 백테스팅 엔진은 ASC 가정 — 정규화 후 ORDER BY 강제
- **공매도 데이터 신뢰도**: 키움 vs KRX 공식 공매도 데이터 (이전 `pykrx`) 차이 검증 — 데이터 품질 리포트 (Phase H)
- **공매도 보고 지연**: 공매도 거래일과 키움 응답 일자 사이의 lag (T+1 또는 T+2 가능) — 운영 1주 측정. 백테스팅 시 lag 만큼 시그널 지연 보정 필요
- **쇼트 스퀴즈 시그널 검증**: 누적 공매도량 + 매매비중 spike 후 가격 반등 패턴 — Phase H 데이터 품질 리포트의 검증 사례
- **`change_rate` (`flu_rt`) 의 부호**: Excel 예시 `"-1.76"` 부호 명시. ka10081 의 일봉 응답에는 등락률 필드 없음 — derived feature 와 비교
- **NXT 공매도 빈 응답 처리**: warning 누적 시 alert 폭증 가능 — `nxt_enable=true & 빈 응답` 케이스를 정상 처리로 분류 (warning 안 함)

### 11.3 ka10014 vs ka10086 비교 (시그널 카테고리 충돌)

| 항목 | ka10014 (본 endpoint) | ka10086 (Phase C) |
|------|---------------------|-------------------|
| URL | /api/dostk/shsa | /api/dostk/mrkcond |
| 카테고리 | **공매도** | 일별주가 + 투자자별 + **신용** |
| 매도 측 시그널 | 공매도량 / 매매비중 | 신용 잔고 비율 (`crd_rt`) |
| 매매 단위 | 종목·일자 | 종목·일자·거래소 |
| 응답 row 수 | 1주 ~5 | 1일 1 row (단건) |
| 책임 분리 | **공매도 (raw 매도)** | **신용 (대출 매도)** |

→ **두 시그널은 보완**:
- 공매도 = 빌린 주식을 시장에 매도 (직접 매도 압력)
- 신용 = 증거금으로 산 주식의 강제 매도 가능성 (간접 매도 압력)
- 백테스팅 엔진이 두 시그널 종합 → 매도 측 압력 종합 점수

→ 본 endpoint 의 `short_volume` + ka10086 의 `crd_rt` 가 같은 derived feature 로 들어가는 것이 자연.

### 11.4 향후 확장

- **연속 공매도 일수 시그널**: 본 endpoint 의 raw `short_volume` 으로 N일 연속 매도 압력 계산 — derived feature
- **공매도 평균가 vs 종가 손익**: `short_avg_price` 와 그 일자 `close_price` 차이 → 공매도 세력의 미실현 손익 추정
- **업종 공매도 압력**: stock.sector_id 그루핑 + 업종별 매매비중 평균
- **데이터 정합성 검증**: 키움 vs KRX 공식 (`pykrx` 또는 KRX 공매도 데이터 사이트) — Phase H
- **공매도 잔고 스냅샷 (별도 endpoint)**: 본 endpoint 는 일별 거래량. 잔고 스냅샷은 별도 카테고리 — 키움 카탈로그 추가 조사

---

_Phase E 의 첫 endpoint, 그리고 매도 측 시그널의 raw source. 본 endpoint 가 안정 작동하면 ka10068 (대차) + ka10086 (신용) 와 결합한 종합 매도 압력 시그널 분석 가능. ka10068/ka20068 은 본 계획서의 패턴 복제 (시장 단위 / 종목 단위 차이만)._
