# endpoint-11-ka10079.md — 주식틱차트조회요청 (보강 시계열)

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10079` |
| API 명 | 주식틱차트조회요청 |
| 분류 | Tier 4 (보강 시계열 — 미시구조) |
| Phase | **D** |
| 우선순위 | **P3** (선택 — 데이터 폭증 위험. 기본 OFF) |
| Method | `POST` |
| URL | `/api/dostk/chart` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX 만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| 의존 endpoint | `au10001`, `ka10099` (stock 마스터 + nxt_enable 게이팅) |
| 후속 endpoint | (없음 — 미시구조 분석 / 분봉 보정 / 슬리피지 시뮬 의 입력) |

---

## 1. 목적

**일중 체결 단위 시계열**을 적재한다. 일/분봉이 OHLCV 버킷 집계라면, 틱은 매 체결의 raw 흐름. 백테스팅 측면에서 다음 시나리오에서만 의미를 가진다:

1. **슬리피지 시뮬레이션** — 분봉의 평균가 가정 대신 실제 체결가 분포로 진입/청산 비용 추정
2. **분봉 OHLC 정합성 검증** — ka10080 분봉이 실제 틱 합성과 맞는지 cross-check
3. **체결 강도(매수/매도 우세) 시그널** — 동일 가격대 연속 체결 빈도, 급변 구간 탐지
4. **장 시작/마감 5분 미시구조** — 동시호가 직후의 가격 발견 패턴

**왜 P3 (기본 OFF)**:
- **데이터 폭증** — 액티브 종목은 1초당 수~수십 체결, 하루 ~10만 row × 종목 수. 3000 종목 × 365일 백필은 PG 한 인스턴스로 감당 불가
- **백테스팅 1차 가치 낮음** — 분봉만으로 충분한 시그널이 대부분
- **운영 부담** — RPS 4 제한 안에서 화이트리스트 50 종목도 일 1회 sync 가 ~1시간 소요 추정

→ **화이트리스트 정책 + 단기 retention** 전제. master.md § 9 의 "Phase D 에서 별도 의사결정 — 기본 OFF" 정책 구현.

**Phase D 3 endpoint 중 본 endpoint 가 가장 무겁고 가장 선택적**. ka10080 (분봉) 이 normal-path, ka10079 는 opt-in.

---

## 2. Request 명세

### 2.1 Header

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `api-id` | TR 명 | String | Y | 10 | `"ka10079"` 고정 |
| `authorization` | 접근토큰 | String | Y | 1000 | `Bearer <token>` |
| `cont-yn` | 연속조회 여부 | String | N | 1 | 응답 헤더 그대로 전달 |
| `next-key` | 연속조회 키 | String | N | 50 | 응답 헤더 그대로 전달 |

### 2.2 Body

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `stk_cd` | 종목코드 | String | Y | **20** | KRX `005930`, NXT `005930_NX`, SOR `005930_AL` |
| `tic_scope` | 틱범위 | String | Y | 2 | `1`/`3`/`5`/`10`/`30` (5개만) |
| `upd_stkpc_tp` | 수정주가구분 | String | Y | 1 | `0`=원본 / `1`=수정주가 |

> **`tic_scope` 의미**: "1틱" = 매 체결, "5틱" = 5체결마다 묶음. 미시구조 검증은 `1`, 분봉 합성 검증은 `30` 또는 `5` 권장.
>
> ka10080 분봉의 `tic_scope` (1/3/5/10/15/30/45/60 분) 와 **유효값이 다름** — UseCase 에서 enum 분리 필수.

### 2.3 Request 예시 (Excel 원문)

```json
POST https://api.kiwoom.com/api/dostk/chart
Content-Type: application/json;charset=UTF-8
api-id: ka10079
authorization: Bearer Egicyx...

{
    "stk_cd": "005930",
    "tic_scope": "1",
    "upd_stkpc_tp": "1"
}
```

### 2.4 Pydantic 모델

```python
# app/adapter/out/kiwoom/chart.py
class TickScope(StrEnum):
    """ka10079 의 tic_scope. ka10080 분봉의 MinuteScope 와 분리."""
    TICK_1 = "1"
    TICK_3 = "3"
    TICK_5 = "5"
    TICK_10 = "10"
    TICK_30 = "30"


class TickChartRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    stk_cd: Annotated[str, Field(min_length=6, max_length=20)]
    tic_scope: TickScope
    upd_stkpc_tp: Literal["0", "1"]
```

> 백테스팅 호출은 항상 `upd_stkpc_tp="1"`. 단, 일중 가격 발견 검증에는 `upd_stkpc_tp="0"` (원본) 도 비교 의미.

---

## 3. Response 명세

### 3.1 Header

| Element | Type | Description |
|---------|------|-------------|
| `api-id` | String | `"ka10079"` 에코 |
| `cont-yn` | String | `Y` 면 다음 페이지 |
| `next-key` | String | 다음 호출 헤더에 세팅 — `last_tic_cnt` 와 함께 운영 검증 (둘 중 무엇이 페이지네이션 키인지) |

### 3.2 Body

| Element | 한글명 | Type | Length | 영속화 컬럼 | 메모 |
|---------|-------|------|--------|-------------|------|
| `stk_cd` | 종목코드 | String | 6 | (FK lookup) | 응답에 `_NX` 보존 여부 운영 검증 |
| `last_tic_cnt` | 마지막 틱갯수 | String | — | (페이지네이션 키 후보) | **운영 검증 1순위** — 빈 문자열 vs 숫자 vs page 종료 표시 |
| `stk_tic_chart_qry[]` | 틱차트 list | LIST | — | (전체 row 적재) | **list key 명** |
| `cur_prc` | 현재가 (체결가) | String | 20 | `price` (BIGINT) | KRW. 부호 포함 가능 (ka10080 예시는 `-78800`) |
| `trde_qty` | 거래량 (이번 체결 수량) | String | 20 | `volume` (BIGINT) | 주 |
| `cntr_tm` | 체결시간 | String | 20 | `executed_at` (TIMESTAMPTZ KST) | **`YYYYMMDDHHMMSS` 14자리** — ka10081 의 `dt` 와 다름 |
| `open_pric` | 시가 (그 틱 묶음의 시가) | String | 20 | `open_price` (BIGINT) | 부호 포함 가능 |
| `high_pric` | 고가 | String | 20 | `high_price` (BIGINT) | 부호 포함 가능 |
| `low_pric` | 저가 | String | 20 | `low_price` (BIGINT) | 부호 포함 가능 |
| `pred_pre` | 전일대비 | String | 20 | `prev_compare_amount` (BIGINT) | 현재가 - 전일종가. **Excel 예시는 부호 누락 (`"500"`) — 운영 검증 필요** |
| `pred_pre_sig` | 전일대비기호 | String | 20 | `prev_compare_sign` (CHAR(1)) | `1`:상한가 / `2`:상승 / `3`:보합 / `4`:하한가 / `5`:하락 |
| `return_code` | 처리코드 | Integer | — | (raw_response only) | 0 정상 |
| `return_msg` | 처리메시지 | String | — | (raw_response only) | |

### 3.3 Response 예시 (Excel 원문)

```json
{
    "stk_cd": "005930",
    "last_tic_cnt": "",
    "stk_tic_chart_qry": [
        {
            "cur_prc": "78900",
            "trde_qty": "143",
            "cntr_tm": "20250917131939",
            "open_pric": "78900",
            "high_pric": "78900",
            "low_pric": "78900",
            "pred_pre": "500",
            "pred_pre_sig": "5"
        },
        {
            "cur_prc": "78900",
            "trde_qty": "200",
            "cntr_tm": "20250917131939",
            "open_pric": "78900",
            "high_pric": "78900",
            "low_pric": "78900",
            "pred_pre": "500",
            "pred_pre_sig": "5"
        }
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다"
}
```

> **같은 `cntr_tm`(13:19:39) 에 두 row** — 1초 내 다중 체결 가능성. UNIQUE 제약은 `(stock_id, exchange, executed_at, sequence_no)` 가 안전 (단순 `(stock_id, executed_at)` 만 쓰면 collision).

### 3.4 Pydantic 모델 + 정규화

```python
# app/adapter/out/kiwoom/_records.py
class TickChartRow(BaseModel):
    """ka10079 응답 row."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    cur_prc: str = ""
    trde_qty: str = ""
    cntr_tm: str = ""
    open_pric: str = ""
    high_pric: str = ""
    low_pric: str = ""
    pred_pre: str = ""
    pred_pre_sig: str = ""

    def to_normalized(
        self,
        *,
        stock_id: int,
        exchange: ExchangeType,
        adjusted: bool,
        sequence_no: int,
    ) -> "NormalizedTickRow":
        return NormalizedTickRow(
            stock_id=stock_id,
            exchange=exchange,
            adjusted=adjusted,
            executed_at=_parse_yyyymmddhhmmss_kst(self.cntr_tm)
                or datetime.min.replace(tzinfo=KST),
            sequence_no=sequence_no,
            price=_to_int(self.cur_prc),
            volume=_to_int(self.trde_qty),
            open_price=_to_int(self.open_pric),
            high_price=_to_int(self.high_pric),
            low_price=_to_int(self.low_pric),
            prev_compare_amount=_to_int(self.pred_pre),
            prev_compare_sign=self.pred_pre_sig or None,
        )


class TickChartResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    stk_cd: str = ""
    last_tic_cnt: str = ""
    stk_tic_chart_qry: list[TickChartRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""


@dataclass(frozen=True, slots=True)
class NormalizedTickRow:
    stock_id: int
    exchange: ExchangeType
    adjusted: bool
    executed_at: datetime           # KST aware
    sequence_no: int                # 같은 cntr_tm 내 응답 순서 (0-based)
    price: int | None
    volume: int | None
    open_price: int | None
    high_price: int | None
    low_price: int | None
    prev_compare_amount: int | None
    prev_compare_sign: str | None
```

> `_parse_yyyymmddhhmmss_kst("20250917131939")` → `datetime(2025, 9, 17, 13, 19, 39, tzinfo=KST)`. 분봉 (ka10080) 도 같은 helper.
>
> `sequence_no` 는 **응답 페이지 내 순서** — 같은 `cntr_tm` 내 다중 체결을 UNIQUE 로 분리. 페이지 경계에서 reset 하지 않도록 caller 가 누적 카운터 유지.

---

## 4. NXT 처리

| 항목 | 적용 여부 |
|------|-----------|
| `stk_cd` 에 `_NX` suffix | **Y** (Length=20, Excel R22) |
| `nxt_enable` 게이팅 | **Y** (NXT 호출 전 stock.nxt_enable=true 검증) |
| `mrkt_tp` 별 분리 | N |
| KRX 운영 / 모의 차이 | mockapi 는 KRX 전용 |

### 4.1 NXT 틱 데이터의 의미

- KRX 틱 ≈ 정규장 + 시간외 단일가
- NXT 틱 ≈ 8:00~20:00 long-trading 윈도 — KRX 정규장 외 시간대의 가격 발견 패턴
- 백테스팅 시그널: NXT 의 장 마감 후 가격 변동이 다음 KRX 시가에 미치는 영향

→ **NXT 틱은 화이트리스트 + 단기 retention 만 운영 가치**. 전체 NXT 종목 틱 수집은 자제.

### 4.2 KRX 실패 시 NXT skip 정책

- (a) **독립 호출** (권장): KRX 실패해도 NXT 호출 시도
- (b) 의존 호출: KRX 실패시 NXT skip

→ ka10081 과 동일하게 (a) 채택. 단, 화이트리스트 정책 (§ 6.5) 으로 호출 자체가 적어 배포 위험 작음.

---

## 5. DB 스키마

### 5.1 신규 테이블 — Migration 005 (`005_intraday.py`)

> ka10080 분봉과 같은 마이그레이션. **Phase D 의 두 endpoint 가 한 마이그레이션에 묶이는 이유**: 인트라데이 적재 활성화/비활성화를 함께 토글.

```sql
CREATE TABLE kiwoom.stock_tick_price (
    id                       BIGSERIAL PRIMARY KEY,
    stock_id                 BIGINT NOT NULL REFERENCES kiwoom.stock(id) ON DELETE CASCADE,
    exchange                 VARCHAR(3) NOT NULL,        -- "KRX" / "NXT"
    executed_at              TIMESTAMPTZ NOT NULL,        -- KST aware
    sequence_no              INTEGER NOT NULL,            -- 같은 ms 내 다중 체결 분리
    adjusted                 BOOLEAN NOT NULL DEFAULT true,
    tic_scope                VARCHAR(2) NOT NULL DEFAULT '1',   -- 1/3/5/10/30
    price                    BIGINT,
    volume                   BIGINT,
    open_price               BIGINT,
    high_price               BIGINT,
    low_price                BIGINT,
    prev_compare_amount      BIGINT,
    prev_compare_sign        CHAR(1),
    fetched_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_tick_stock_executed
        UNIQUE (stock_id, exchange, executed_at, sequence_no, tic_scope, adjusted)
)
PARTITION BY RANGE (executed_at);

-- 월별 파티션 (Phase D 진입 시점 직전 달부터 6개월 미리 생성)
CREATE TABLE kiwoom.stock_tick_price_y2026m05 PARTITION OF kiwoom.stock_tick_price
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE kiwoom.stock_tick_price_y2026m06 PARTITION OF kiwoom.stock_tick_price
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
-- ... 추가 6개월

CREATE INDEX idx_tick_stock_exchange_time
    ON kiwoom.stock_tick_price(stock_id, exchange, executed_at);
CREATE INDEX idx_tick_executed_at
    ON kiwoom.stock_tick_price(executed_at);
```

### 5.2 ORM 모델

```python
# app/adapter/out/persistence/models/stock_tick_price.py
class StockTickPrice(Base):
    __tablename__ = "stock_tick_price"
    __table_args__ = (
        UniqueConstraint(
            "stock_id", "exchange", "executed_at", "sequence_no",
            "tic_scope", "adjusted",
            name="uq_tick_stock_executed",
        ),
        {"schema": "kiwoom", "postgresql_partition_by": "RANGE (executed_at)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("kiwoom.stock.id", ondelete="CASCADE"), nullable=False
    )
    exchange: Mapped[str] = mapped_column(String(3), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    adjusted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    tic_scope: Mapped[str] = mapped_column(String(2), nullable=False, server_default="1")

    price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    open_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    high_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    low_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_compare_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_compare_sign: Mapped[str | None] = mapped_column(String(1), nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

### 5.3 Retention 정책

| 정책 | 기간 | 근거 |
|------|------|------|
| **단기 보관** (권장 기본) | 30 일 | 슬리피지 캘리브레이션 / 분봉 검증의 hot path |
| **중기** | 90 일 | 시그널 백테스트 1 분기 |
| **장기** | 1 년 (선택) | 미시구조 연구 / 학습용 |

→ Phase H 통합 단계에서 `pg_cron` 또는 APScheduler job 으로 retention drop. **본 endpoint 의 데이터는 백업 안 함** — 키움 재호출로 복구 (단, 키움도 일정 기간 후 응답 안 할 수 있음).

### 5.4 파티션 운영

- **월별 파티션** 필수: 일별 row 가 종목당 ~10만, 화이트리스트 50 종목이면 일 500만 row, 월 1억 row
- 신규 파티션 생성: `scripts/create_tick_partitions.py --months-ahead 3` — APScheduler 가 월 1회 실행
- 오래된 파티션 DROP: retention 정책에 따라 cron drop

### 5.5 row 폭증 추정

| 시나리오 | row 수 (단일 거래소) |
|---------|---------------------|
| KOSPI 액티브 종목 1개 / 정규장 6.5h | ~100,000 (tic_scope=1) |
| KOSPI 액티브 종목 1개 / 30틱 | ~3,300 |
| 화이트리스트 50 종목 × 365일 / 정규장 + 1틱 | **~1.83 billion** (KRX), 2~3배 (NXT) |
| 화이트리스트 50 종목 × 30일 / 정규장 + 30틱 | ~5M (실용적 범위) |

→ **운영 default 권장**: tic_scope=`30`, 화이트리스트 30~50 종목, retention 30일.

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomChartClient.fetch_tick`

```python
# app/adapter/out/kiwoom/chart.py
class KiwoomChartClient:
    """ka10079~ka10094 공유."""

    PATH = "/api/dostk/chart"

    async def fetch_tick(
        self,
        stock_code: str,
        *,
        tic_scope: TickScope = TickScope.TICK_1,
        exchange: ExchangeType = ExchangeType.KRX,
        adjusted: bool = True,
        max_pages: int = 5,
    ) -> list[TickChartRow]:
        """단일 종목·단일 거래소·단일 tic_scope 의 틱 시계열.

        주의:
        - **base_dt 파라미터 없음** — 키움이 응답하는 기간이 고정 (운영 검증: 당일? 직전 N분?)
        - max_pages=5 기본. 액티브 종목은 1 페이지 ~수백 row 추정
        - cont-yn=Y 페이지네이션 + last_tic_cnt 의 의미 운영 검증 필요
        """
        if not (len(stock_code) == 6 and stock_code.isdigit()):
            raise ValueError(f"stock_code 6자리 숫자만: {stock_code}")
        stk_cd = build_stk_cd(stock_code, exchange)

        body = {
            "stk_cd": stk_cd,
            "tic_scope": tic_scope.value,
            "upd_stkpc_tp": "1" if adjusted else "0",
        }

        all_rows: list[TickChartRow] = []
        async for page in self._client.call_paginated(
            api_id="ka10079",
            endpoint=self.PATH,
            body=body,
            max_pages=max_pages,
        ):
            parsed = TickChartResponse.model_validate(page.body)
            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id="ka10079",
                    return_code=parsed.return_code,
                    return_msg=parsed.return_msg,
                )
            all_rows.extend(parsed.stk_tic_chart_qry)

        return all_rows
```

> `max_pages=5` — 한 호출에 액티브 종목의 정규장 1일 분량을 다 못 가져오면 호출 횟수 폭증. **운영 첫 호출에서 1 페이지 row 수 측정 후 조정**.

### 6.2 Repository

```python
# app/adapter/out/persistence/repositories/stock_intraday.py
class StockTickPriceRepository:
    """단일 테이블 (KRX/NXT 같은 테이블, exchange 컬럼으로 분리).

    분봉 (StockMinutePriceRepository) 와는 별도 — 컬럼 다름 (acc_trde_qty 등).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, rows: Sequence[NormalizedTickRow]) -> int:
        if not rows:
            return 0

        values = [
            {
                "stock_id": r.stock_id,
                "exchange": r.exchange.value,
                "executed_at": r.executed_at,
                "sequence_no": r.sequence_no,
                "adjusted": r.adjusted,
                "tic_scope": "1",          # caller 가 채워서 넘기는 게 더 안전
                "price": r.price,
                "volume": r.volume,
                "open_price": r.open_price,
                "high_price": r.high_price,
                "low_price": r.low_price,
                "prev_compare_amount": r.prev_compare_amount,
                "prev_compare_sign": r.prev_compare_sign,
            }
            for r in rows
            if r.executed_at != datetime.min.replace(tzinfo=KST)    # 빈 cntr_tm skip
        ]
        if not values:
            return 0

        stmt = pg_insert(StockTickPrice).values(values)
        update_set = {col: stmt.excluded[col] for col in values[0]
                      if col not in ("stock_id", "exchange", "executed_at",
                                     "sequence_no", "tic_scope", "adjusted")}
        update_set["fetched_at"] = func.now()
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_id", "exchange", "executed_at",
                            "sequence_no", "tic_scope", "adjusted"],
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
        start: datetime,
        end: datetime,
        tic_scope: str = "1",
    ) -> list[StockTickPrice]:
        stmt = (
            select(StockTickPrice)
            .where(
                StockTickPrice.stock_id == stock_id,
                StockTickPrice.exchange == exchange.value,
                StockTickPrice.tic_scope == tic_scope,
                StockTickPrice.executed_at >= start,
                StockTickPrice.executed_at <= end,
            )
            .order_by(StockTickPrice.executed_at, StockTickPrice.sequence_no)
        )
        return list((await self._session.execute(stmt)).scalars())
```

### 6.3 화이트리스트 — `TickWhitelistRepository`

```python
# app/adapter/out/persistence/repositories/tick_whitelist.py
class TickWhitelistRepository:
    """ka10079 호출 대상 종목 명시 관리.

    별도 테이블로 운영자가 명시 등록 — 자동 추가 안 함.
    """

    async def list_active(self) -> list[Stock]:
        """is_active=true & nxt_enable 무관 하게 등록된 화이트리스트 종목."""
        stmt = (
            select(Stock)
            .join(TickWhitelist, TickWhitelist.stock_id == Stock.id)
            .where(
                TickWhitelist.is_active.is_(True),
                Stock.is_active.is_(True),
            )
        )
        return list((await self._session.execute(stmt)).scalars())
```

> `tick_whitelist` 테이블 정의는 Migration 005 에 포함 — `id, stock_id FK, tic_scope, retention_days, is_active, added_at, added_by`. 운영 admin 라우터로 추가/제거.

### 6.4 UseCase — `IngestTickUseCase` (단건)

```python
# app/application/service/intraday_service.py
class IngestTickUseCase:
    """단일 거래소 단일 종목 틱 적재.

    멱등성: ON CONFLICT (stock_id, exchange, executed_at, sequence_no, tic_scope, adjusted) UPDATE.
    같은 시점·같은 sequence 가 들어오면 마지막 호출 값으로 갱신.
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
        self._tick_repo = StockTickPriceRepository(session)
        self._env = env

    async def execute(
        self,
        stock_code: str,
        *,
        tic_scope: TickScope = TickScope.TICK_1,
        exchange: ExchangeType = ExchangeType.KRX,
        adjusted: bool = True,
    ) -> TickIngestOutcome:
        if self._env == "mock" and exchange is ExchangeType.NXT:
            return TickIngestOutcome(
                stock_code=stock_code, exchange=exchange, tic_scope=tic_scope,
                upserted=0, skipped=True, reason="mock_no_nxt",
            )

        stock = await self._lookup.ensure_exists(stock_code)
        if not stock.is_active:
            return TickIngestOutcome(
                stock_code=stock_code, exchange=exchange, tic_scope=tic_scope,
                upserted=0, skipped=True, reason="inactive",
            )
        if exchange is ExchangeType.NXT and not stock.nxt_enable:
            return TickIngestOutcome(
                stock_code=stock_code, exchange=exchange, tic_scope=tic_scope,
                upserted=0, skipped=True, reason="nxt_disabled",
            )

        try:
            raw_rows = await self._client.fetch_tick(
                stock_code, tic_scope=tic_scope,
                exchange=exchange, adjusted=adjusted,
            )
        except KiwoomBusinessError as exc:
            return TickIngestOutcome(
                stock_code=stock_code, exchange=exchange, tic_scope=tic_scope,
                upserted=0, error=f"business: {exc.return_code}",
            )

        normalized = [
            r.to_normalized(
                stock_id=stock.id, exchange=exchange,
                adjusted=adjusted, sequence_no=i,
            )
            for i, r in enumerate(raw_rows)
        ]
        # tic_scope 채움 (Repository default 와 일치)
        for n in normalized:
            object.__setattr__(n, "tic_scope_value", tic_scope.value)
        upserted = await self._tick_repo.upsert_many_with_scope(normalized, tic_scope=tic_scope.value)

        return TickIngestOutcome(
            stock_code=stock_code, exchange=exchange, tic_scope=tic_scope,
            fetched=len(raw_rows), upserted=upserted,
        )


@dataclass(frozen=True, slots=True)
class TickIngestOutcome:
    stock_code: str
    exchange: ExchangeType
    tic_scope: TickScope
    fetched: int = 0
    upserted: int = 0
    skipped: bool = False
    reason: str | None = None
    error: str | None = None
```

### 6.5 화이트리스트 Bulk — `IngestTickWhitelistUseCase`

```python
class IngestTickWhitelistUseCase:
    """화이트리스트 종목만 일 1회 틱 적재.

    동시성: RPS 4 + 250ms = 4 호출/초.
    소요: 50 종목 × 2 거래소 (NXT enable 만) × 0.25s × max_pages 평균 3 = ~75초.
      실측 추정 5~30분 (페이지네이션 변동 + 응답 시간).
    """

    BATCH_SIZE = 10    # 화이트리스트는 작아 batch 작게

    def __init__(
        self,
        session: AsyncSession,
        *,
        single_use_case: IngestTickUseCase,
        whitelist_repo: TickWhitelistRepository,
    ) -> None:
        self._session = session
        self._single = single_use_case
        self._whitelist = whitelist_repo

    async def execute(
        self,
        *,
        tic_scope: TickScope = TickScope.TICK_30,    # 운영 default
    ) -> TickBulkResult:
        stocks = await self._whitelist.list_active()

        krx_outcomes: list[TickIngestOutcome] = []
        nxt_outcomes: list[TickIngestOutcome] = []

        for i, stock in enumerate(stocks, start=1):
            # KRX
            try:
                async with self._session.begin_nested():
                    o = await self._single.execute(
                        stock.stock_code, tic_scope=tic_scope,
                        exchange=ExchangeType.KRX,
                    )
                    krx_outcomes.append(o)
            except Exception as exc:
                logger.warning("KRX tick ingest 실패 %s: %s", stock.stock_code, exc)
                krx_outcomes.append(TickIngestOutcome(
                    stock_code=stock.stock_code, exchange=ExchangeType.KRX,
                    tic_scope=tic_scope, error=f"{type(exc).__name__}: {exc}",
                ))

            # NXT
            if stock.nxt_enable:
                try:
                    async with self._session.begin_nested():
                        o = await self._single.execute(
                            stock.stock_code, tic_scope=tic_scope,
                            exchange=ExchangeType.NXT,
                        )
                        nxt_outcomes.append(o)
                except Exception as exc:
                    logger.warning("NXT tick ingest 실패 %s: %s", stock.stock_code, exc)
                    nxt_outcomes.append(TickIngestOutcome(
                        stock_code=stock.stock_code, exchange=ExchangeType.NXT,
                        tic_scope=tic_scope, error=f"{type(exc).__name__}: {exc}",
                    ))

            if i % self.BATCH_SIZE == 0:
                await self._session.commit()
                logger.info("tick ingest progress %d/%d", i, len(stocks))

        await self._session.commit()
        return TickBulkResult(
            tic_scope=tic_scope,
            total_stocks=len(stocks),
            krx_outcomes=krx_outcomes,
            nxt_outcomes=nxt_outcomes,
        )


@dataclass(frozen=True, slots=True)
class TickBulkResult:
    tic_scope: TickScope
    total_stocks: int
    krx_outcomes: list[TickIngestOutcome]
    nxt_outcomes: list[TickIngestOutcome]

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
| **수동 단건** | on-demand | `POST /api/kiwoom/tick/{stock_code}?tic_scope=1&exchange=KRX` (admin) |
| **수동 화이트리스트 일괄** | on-demand | `POST /api/kiwoom/tick/sync` (admin) |
| **일 1회 cron (선택)** | KST 19:30 평일 | `nxt_collection_enabled=true` & `tick_collection_enabled=true` 둘 다 true 시 |
| **백필** | 미지원 | 키움이 base_dt 받지 않음 — 과거 틱 백필 불가 (운영 검증) |

### 7.1 라우터

```python
# app/adapter/web/routers/intraday.py
router = APIRouter(prefix="/api/kiwoom/tick", tags=["kiwoom-intraday"])


@router.post(
    "/{stock_code}",
    response_model=TickIngestOutcomeOut,
    dependencies=[Depends(require_admin_key)],
)
async def ingest_one_tick(
    stock_code: str,
    tic_scope: Literal["1", "3", "5", "10", "30"] = Query(default="1"),
    exchange: Literal["KRX", "NXT"] = Query(default="KRX"),
    adjusted: bool = Query(default=True),
    use_case: IngestTickUseCase = Depends(get_ingest_tick_use_case),
) -> TickIngestOutcomeOut:
    outcome = await use_case.execute(
        stock_code,
        tic_scope=TickScope(tic_scope),
        exchange=ExchangeType(exchange),
        adjusted=adjusted,
    )
    return TickIngestOutcomeOut.model_validate(asdict(outcome))


@router.post(
    "/sync",
    response_model=TickBulkResultOut,
    dependencies=[Depends(require_admin_key)],
)
async def sync_tick_whitelist(
    tic_scope: Literal["1", "3", "5", "10", "30"] = Query(default="30"),
    use_case: IngestTickWhitelistUseCase = Depends(get_ingest_tick_bulk_use_case),
) -> TickBulkResultOut:
    result = await use_case.execute(tic_scope=TickScope(tic_scope))
    return TickBulkResultOut.model_validate(asdict(result))


@router.get(
    "/{stock_code}",
    response_model=list[StockTickPriceOut],
)
async def get_tick_range(
    stock_code: str,
    start: datetime = Query(...),
    end: datetime = Query(...),
    exchange: Literal["KRX", "NXT"] = Query(default="KRX"),
    tic_scope: Literal["1", "3", "5", "10", "30"] = Query(default="1"),
    session: AsyncSession = Depends(get_session),
) -> list[StockTickPriceOut]:
    stock_repo = StockRepository(session)
    stock = await stock_repo.find_by_code(stock_code)
    if stock is None:
        raise HTTPException(status_code=404, detail=f"stock not found: {stock_code}")
    repo = StockTickPriceRepository(session)
    rows = await repo.get_range(
        stock.id, exchange=ExchangeType(exchange),
        start=start, end=end, tic_scope=tic_scope,
    )
    return [StockTickPriceOut.model_validate(r) for r in rows]


# whitelist 관리
@router.post("/whitelist/{stock_code}", dependencies=[Depends(require_admin_key)])
async def add_whitelist(stock_code: str, session: AsyncSession = Depends(get_session)) -> dict:
    """화이트리스트 등록 — 명시 호출만 허용."""
    ...


@router.delete("/whitelist/{stock_code}", dependencies=[Depends(require_admin_key)])
async def remove_whitelist(stock_code: str, session: AsyncSession = Depends(get_session)) -> dict:
    ...
```

### 7.2 APScheduler Job (선택)

```python
# app/batch/tick_ingest_job.py
async def fire_tick_whitelist_sync() -> None:
    """매 평일 19:30 KST — 화이트리스트 종목 틱 적재.

    `tick_collection_enabled=true` 일 때만 실제 호출.
    """
    if not settings.tick_collection_enabled:
        return
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
            single = IngestTickUseCase(
                session, chart_client=chart, lookup_use_case=lookup,
                env=settings.kiwoom_default_env,
            )
            whitelist_repo = TickWhitelistRepository(session)
            bulk = IngestTickWhitelistUseCase(
                session, single_use_case=single, whitelist_repo=whitelist_repo,
            )
            result = await bulk.execute(tic_scope=TickScope.TICK_30)
        logger.info(
            "tick whitelist sync 완료 stocks=%d rows=%d",
            result.total_stocks, result.total_rows_inserted,
        )
    except Exception:
        logger.exception("tick whitelist sync 콜백 예외")


scheduler.add_job(
    fire_tick_whitelist_sync,
    CronTrigger(day_of_week="mon-fri", hour=19, minute=30, timezone=KST),
    id="tick_whitelist_sync",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
    misfire_grace_time=60 * 60,    # 60분 grace
)
```

> ka10086 (19:00) 종료 후 시점. 일봉 (18:30) 과는 1시간 간격.

### 7.3 RPS / 시간 추정

| 항목 | 값 |
|------|----|
| 화이트리스트 종목 수 | 30~50 (운영자 결정) |
| nxt_enable 비율 | ~50% |
| 호출당 인터벌 | 250ms |
| 동시성 | 4 (Semaphore) |
| 1회 sync 호출 수 | 50 + 25 = 75 (KRX + NXT) |
| 페이지네이션 평균 | 3 (가설) |
| 총 호출 | ~225 |
| 이론 시간 | 225 × 0.25 / 4 = 14초 |
| 실측 추정 | 5~15분 (응답 시간 + 재시도) |

→ cron 19:30 + 60분 grace.

---

## 8. 에러 처리

| HTTP / 응답 | 도메인 예외 | 라우터 매핑 | UseCase 정책 |
|-------------|-------------|-------------|--------------|
| 400 (잘못된 stock_code) | `ValueError` | 400 | 호출 전 차단 |
| 401 / 403 | `KiwoomCredentialRejectedError` | 400 | bubble up — 모든 종목 실패 가능 |
| 429 | `KiwoomRateLimitedError` | 503 | tenacity 재시도 후 다음 종목 |
| 5xx, 네트워크 | `KiwoomUpstreamError` | 502 | 다음 종목 |
| `return_code != 0` | `KiwoomBusinessError` | 400 | outcome.error 로 노출, 다음 종목 |
| 응답 `cntr_tm=""` | (적재 skip) | — | upsert_many 가 자동 제외 |
| 빈 응답 `list=[]` | (정상) | — | upserted=0 |
| 페이지네이션 폭주 (cont-yn=Y 무한) | `KiwoomPaginationLimitError` | 502 | max_pages=5 도달 시 중단 |
| FK 위반 (stock 미존재) | `IntegrityError` | 502 | UseCase 가 ensure_exists 선행 |

### 8.1 partial 실패 알람

화이트리스트 50 종목 × 2 거래소 = 100 호출 중:
- < 5% 실패: 정상
- 5~15%: warning 로그
- > 15%: error + 자격증명/RPS 점검 alert

### 8.2 같은 호출 두 번 실행 (멱등성)

UNIQUE (stock_id, exchange, executed_at, sequence_no, tic_scope, adjusted) ON CONFLICT DO UPDATE — sequence_no 가 키에 포함되어 같은 cntr_tm 의 N row 가 같은 sequence 로 다시 들어오면 갱신.

⚠ **위험**: 두 번째 호출의 응답 row 순서가 첫 호출과 다르면 sequence_no 가 다른 row 가 INSERT 될 수 있음 — UNIQUE 가 cntr_tm 만이라 (stock, exchange, executed_at) 이면 중복. 운영 검증: 같은 stk_cd · 같은 시점에 두 번 호출 시 같은 `cntr_tm` row 가 같은 순서로 오는지.

---

## 9. 테스트

### 9.1 Unit (MockTransport)

`tests/adapter/kiwoom/test_chart_tick.py`:

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 단일 페이지 | 200 + list 5건 + cont-yn=N | 5건 반환 |
| 페이지네이션 | 첫 cont-yn=Y + last_tic_cnt 채움, 둘째 N | call_paginated 2회, 합쳐 N건 |
| 빈 list | 200 + `stk_tic_chart_qry=[]` | 빈 list 반환 |
| `return_code=1` | 비즈니스 에러 | `KiwoomBusinessError` |
| 401 | 자격증명 거부 | `KiwoomCredentialRejectedError` |
| stock_code "00593" | 호출 차단 | `ValueError` |
| ExchangeType.NXT 호출 | stk_cd build | request body `stk_cd="005930_NX"` |
| TickScope 분기 | TICK_30 | request body `tic_scope="30"` |
| upd_stkpc_tp 분기 | adjusted=False | `upd_stkpc_tp="0"` |
| `cntr_tm=""` row | 응답에 빈 cntr_tm 1건 + 정상 4건 | to_normalized 가 datetime.min 으로, repo 자동 skip |
| 부호 포함 가격 | open_pric="-78900" | `_to_int` → -78900 |
| 같은 cntr_tm 2 row | 2건 sequence_no=0,1 | 2 row INSERT (UNIQUE 분리) |
| 페이지네이션 폭주 | cont-yn=Y 무한 | `max_pages=5` 도달 → `KiwoomPaginationLimitError` |

### 9.2 Integration (testcontainers)

`tests/application/test_intraday_service.py`:

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| INSERT (DB 빈 상태) | stock 1건 + 응답 5 row | stock_tick_price 5 row INSERT |
| UPDATE (멱등성) | 같은 호출 두 번 | row 5개 유지, fetched_at 갱신 |
| KRX + NXT 분리 적재 | nxt_enable=true 종목 | krx 5 + nxt 5 row, exchange 컬럼 분리 |
| `nxt_enable=false` skip | 종목.nxt_enable=false + NXT 호출 | outcome.skipped=true, reason="nxt_disabled" |
| inactive stock skip | is_active=false + 호출 | outcome.skipped=true, reason="inactive" |
| mock no NXT | env="mock" + ExchangeType.NXT | outcome.skipped=true, reason="mock_no_nxt" |
| 같은 cntr_tm 다중 sequence | sequence_no 0,1,2 | 3 row 분리 저장 |
| tic_scope 분리 | scope=1 5건 + scope=30 5건 | 10 row (tic_scope UNIQUE 분리) |
| 화이트리스트 sync 25 종목 | 25 stocks + 50 호출 | 화이트리스트만 처리 |
| 화이트리스트 외 종목 skip | 등록 안 된 종목은 sync 대상 아님 | outcome 자체 미생성 |
| 빈 응답 처리 | 응답 list=[] | upserted=0 |
| 월별 파티션 동작 | executed_at 다른 두 달 row | 각각 다른 파티션에 INSERT |

### 9.3 E2E (요청 시 1회)

```python
@pytest.mark.requires_kiwoom_real
async def test_real_ka10079():
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

        # 삼성전자 KRX 1틱 (장중 / 직후 호출)
        rows = await chart.fetch_tick(
            "005930", tic_scope=TickScope.TICK_1,
            exchange=ExchangeType.KRX,
        )
        assert len(rows) >= 100      # 액티브 종목 1 페이지 ~수백 row 추정

        first = rows[0]
        assert first.cntr_tm
        assert _parse_yyyymmddhhmmss_kst(first.cntr_tm) is not None
        assert first.cur_prc != ""

        # 30틱 비교 — row 수 ~1/30
        tens = await chart.fetch_tick(
            "005930", tic_scope=TickScope.TICK_30,
            exchange=ExchangeType.KRX,
        )
        # 운영 검증: tic_scope=30 응답이 tic_scope=1 의 ~1/30 row 수인지
        assert 0 < len(tens) < len(rows)
    finally:
        async with KiwoomAuthClient(base_url="https://api.kiwoom.com") as auth:
            await auth.revoke_token(creds, token.token)
```

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `app/adapter/out/kiwoom/chart.py` — `KiwoomChartClient.fetch_tick`
- [ ] `app/adapter/out/kiwoom/_records.py` — `TickChartRow`, `TickChartResponse`, `NormalizedTickRow`, `TickScope` enum
- [ ] `app/adapter/out/persistence/models/stock_tick_price.py` — `StockTickPrice` (월별 파티션)
- [ ] `app/adapter/out/persistence/models/tick_whitelist.py` — `TickWhitelist`
- [ ] `app/adapter/out/persistence/repositories/stock_intraday.py` — `StockTickPriceRepository`, `TickWhitelistRepository`
- [ ] `app/application/service/intraday_service.py` — `IngestTickUseCase`, `IngestTickWhitelistUseCase`
- [ ] `app/adapter/web/routers/intraday.py` — POST/GET endpoints + whitelist 관리
- [ ] `app/batch/tick_ingest_job.py` — APScheduler 등록 (KST mon-fri 19:30, 토글 OFF 기본)
- [ ] `migrations/versions/005_intraday.py` — `stock_tick_price` 월별 파티션 + `tick_whitelist`
- [ ] `scripts/create_tick_partitions.py` — N개월 미리 파티션 생성 CLI
- [ ] `app/config/settings.py` — `tick_collection_enabled: bool = False`

### 10.2 테스트

- [ ] Unit 13 시나리오 (§9.1) PASS
- [ ] Integration 12 시나리오 (§9.2) PASS
- [ ] coverage `KiwoomChartClient.fetch_tick`, `IngestTickUseCase`, `StockTickPriceRepository` ≥ 80%

### 10.3 운영 검증

- [ ] **`last_tic_cnt` 의 의미** — 빈 문자열인지, 페이지 종료 row 수인지, 다음 호출 키인지
- [ ] 1 페이지 응답 row 수 (액티브 종목 vs 비액티브 종목)
- [ ] `cntr_tm` 정렬 순서 (최신 → 오래 vs 반대)
- [ ] **`pred_pre` 부호 포함 여부** — Excel 예시는 `"500"` 으로 부호 누락. ka10080 분봉은 `"-600"` 으로 부호 명시 — 일관성 검증 필요
- [ ] 같은 `cntr_tm` 내 다중 체결 발생 빈도 (sequence_no 의 의미)
- [ ] 키움이 응답하는 기간 — 당일만 vs 직전 N분 vs 전체 가능
- [ ] tic_scope=1 vs tic_scope=30 의 row 수 비율 (이론은 30:1)
- [ ] NXT 응답 stk_cd 형식 (`005930_NX` 보존 vs stripped)
- [ ] cont-yn=Y 페이지네이션 발생 빈도 + max_pages 적정값
- [ ] 화이트리스트 50 종목 sync 실측 시간

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10079 tick chart ingest (whitelist + monthly partition)`
- [ ] `master.md` § 12 결정 기록에:
  - `last_tic_cnt` 의미 확정
  - `pred_pre` 부호 일관성 (ka10079 vs ka10080)
  - 1 페이지 row 수 / 페이지네이션 빈도
  - 키움이 응답하는 기간 (당일 / 직전 N분)
  - 화이트리스트 50 종목 sync 실측 시간

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | 화이트리스트 초기 종목 | KOSPI200 / KOSDAQ150 / Top 거래대금 30 / 운영자 수동 | Phase D 코드화 직전 |
| 2 | tic_scope 운영 default | TICK_1 (정밀) / TICK_30 (실용) (권장) | 운영 1주차 |
| 3 | retention 기간 | 30일 (권장) / 90일 / 1년 | Phase H |
| 4 | NXT 틱 수집 여부 | KRX 만 / KRX+NXT (권장 — nxt_enable 만) | Phase D 코드화 |
| 5 | 같은 cntr_tm 다중 체결 처리 | sequence_no UNIQUE (현재) / 단일 row 합산 | 운영 검증 후 |
| 6 | cron 시간 | 19:30 (제안) / 18:00 / 미스케줄 (수동만) | Phase D 후반 |
| 7 | 파티션 boundary | 월별 (권장) / 주별 / 일별 | Phase D 코드화 |
| 8 | adjusted 기본값 | 1 (권장) / 0 (틱은 raw 가 의미 있을 수 있음) | 운영 검증 |

### 11.2 알려진 위험

- **`last_tic_cnt` 의 의미가 가장 큰 unknown** — Excel 예시는 빈 문자열. 응답 헤더 `cont-yn` + `next-key` 로 페이지네이션 추정하지만 `last_tic_cnt` 가 별도 키일 가능성. 첫 호출 헤더/바디 dump 필수
- **`pred_pre` 부호 일관성 (ka10079 vs ka10080)** — Excel 예시 ka10079 는 `"500"` 부호 없음, ka10080 은 `"-600"` 부호 있음. 같은 키움 카테고리에서 다른 표현은 Excel 표기 오류일 가능성 — 운영 검증 필수. 잘못 처리하면 prev_compare 부호 반전
- **데이터 폭증** — 액티브 50 종목 × tic_scope=1 × 정규장 = 일 ~500만 row. tic_scope=30 도 ~17만 row. 월별 파티션 + 30일 retention 으로 PG 인스턴스 부담 통제. 그래도 INSERT 부하 (UPSERT 의 ON CONFLICT 체크) 가 큼 — bulk batch + COPY 검토
- **`base_dt` 파라미터 부재** — 키움이 어떤 기간을 응답하는지 명세 없음. 현재 (호출 시점 직전) 만 응답할 가능성 높음 → **백필 불가**. 본 endpoint 는 forward-only ingest. 과거 데이터가 필요하면 별도 데이터 소스 필요
- **응답 정렬 미확정** — `cntr_tm` 이 ASC 인지 DESC 인지. 백테스팅 엔진은 ASC 가정 — 운영 검증 후 정렬 보정
- **같은 cntr_tm 다중 체결의 sequence_no 의미** — 응답 page 내 인덱스로만 부여 (응답이 다시 오면 같은 sequence 가 다른 체결을 가리킬 수 있음). 진정한 unique 키는 키움 내부 거래번호 (응답 미제공) — UNIQUE 제약이 idempotent 보장하지 못할 수 있음
- **수정주가 의미** — ka10081 일봉의 `upd_stkpc_tp=1` 은 액면분할/배당 보정. 틱 수준에서 같은 보정이 적용되는지 운영 검증 (특히 액면분할 당일의 틱 데이터)
- **NXT 운영시간 가정** — NXT 8:00~20:00 추정. 운영 검증 후 cron 시간/grace 조정. ka10079 가 NXT 의 어느 시간대 데이터를 응답하는지도 확인
- **`stock_tick_price_combined` view 안 만듦** — KRX/NXT 두 거래소를 섞으면 미시구조 의미 모호 (다른 매매 방식). exchange 컬럼으로 항상 분리 조회

### 11.3 ka10079 vs ka10080 vs ka10081 비교

| 항목 | ka10079 틱 | ka10080 분봉 | ka10081 일봉 |
|------|-----------|--------------|-------------|
| URL | /api/dostk/chart | 동일 | 동일 |
| Body | stk_cd + tic_scope + upd_stkpc_tp | + base_dt (optional) | stk_cd + base_dt + upd_stkpc_tp |
| tic_scope | 1/3/5/10/30 (5종) | 1/3/5/10/15/30/45/60 (8종) | — |
| 시간 필드 | `cntr_tm` (14자리) | `cntr_tm` (14자리) | `dt` (8자리) |
| 응답 list 키 | `stk_tic_chart_qry` | `stk_min_pole_chart_qry` | `stk_dt_pole_chart_qry` |
| 응답 필드 수 | 8 | **9** (acc_trde_qty 추가) | 10 |
| 거래대금 (`trde_prica`) | 없음 | 없음 | 있음 |
| 회전율 (`trde_tern_rt`) | 없음 | 없음 | 있음 |
| 누적 거래량 (`acc_trde_qty`) | 없음 | **있음** (Excel 예시만) | 없음 |
| 페이지네이션 키 | cont-yn + last_tic_cnt? | cont-yn + next-key | cont-yn + next-key |
| 영속화 테이블 | stock_tick_price | stock_minute_price | stock_price_krx/nxt |
| 파티션 | **월별 필수** | **월별 권장** | 단일 (5년+ 시점 검토) |
| 화이트리스트 | **필수** (데이터 폭증) | 옵션 (전체 종목 가능) | 전체 종목 |
| 백필 | 불가 (base_dt 없음) | 가능 (base_dt) | 가능 (base_dt) |
| 백테스팅 우선순위 | P3 (선택) | P2 | P0 |

→ ka10080 분봉이 `cntr_tm` + acc_trde_qty + base_dt 백필 등 차이가 충분 → 별도 계획서 (endpoint-12). ka10079 와 ka10080 둘 다 `KiwoomChartClient` 의 메서드로 추가.

### 11.4 향후 확장

- **틱 → 분봉 합성 검증**: stock_tick_price 의 1분 윈도 OHLCV 합성과 ka10080 분봉 응답 비교 — 데이터 정합성 리포트 (Phase H)
- **슬리피지 모델**: 백테스팅 엔진이 `entry_price = avg(price WHERE executed_at BETWEEN entry_minute_start AND end)` 로 평균 체결가 사용
- **장 시작/마감 5분 별도 분석**: 동시호가 직후의 가격 발견 패턴 — 별도 view
- **체결 강도 시그널**: 같은 가격대 연속 체결 빈도 (매수/매도 우세) — derived feature
- **압축 저장**: 30일 이상 데이터는 분봉 합성 후 틱 raw 삭제 — disk pressure 완화
- **TimescaleDB 검토**: PG 파티션보다 hypertable 이 자동 chunk 관리 + 압축 기능 — Phase H 평가

---

_Phase D 의 첫 endpoint, 그리고 백테스팅의 가장 선택적인 데이터. 화이트리스트 정책이 본 endpoint 의 운영 비용을 결정. 일/분봉이 정답이고, 틱은 검증·보정·미시구조 분석의 보조._
