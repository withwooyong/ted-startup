# endpoint-16-ka10068.md — 대차거래추이요청 (시장 단위)

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10068` |
| API 명 | 대차거래추이요청 |
| 분류 | Tier 5 (시그널 보강 — 대차) |
| Phase | **E** |
| 우선순위 | **P1** |
| Method | `POST` |
| URL | `/api/dostk/slb` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX 만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| 의존 endpoint | `au10001` (종목 마스터 의존 없음 — 시장 전체) |
| 후속 endpoint | `ka20068` (대차거래 추이 종목별) |

---

## 1. 목적

**시장 전체 대차거래** 일별 추이를 적재한다. ka10014 (공매도) 가 종목 단위 매도 압력이라면, 본 endpoint 는 **시장 전체의 대차 잔고/체결/상환** 추이 — 외인의 공매도 의도 추적의 거시 지표.

1. **외인 매도 시그널 (거시)** — 대차거래체결주수 spike 시 외인 공매도 직전 신호
2. **대차 잔고 추이** — `rmnd` (잔고주수) / `remn_amt` (잔고금액) 의 추세
3. **상환량 vs 체결량** — `dbrt_trde_rpy` (상환) > `dbrt_trde_cntrcnt` (체결) 면 매도 압력 완화
4. **시장 단위 비교** — KOSPI 전체 vs KOSDAQ 전체 (운영 검증 — 본 endpoint 가 시장별 분리 응답하는지)

**왜 P1**:
- ka10014 (종목 공매도) 의 거시 보완. 시장 전체 대차 잔고 추세 파악
- 종목 단위 보강은 ka20068 — 본 endpoint 와 같은 카테고리

**ka10014 와 본 endpoint 차이**: ka10014 는 종목 단위 (stk_cd 필수), 본 endpoint 는 **시장 단위** (stk_cd 없음 — `all_tp=1` 전체표시). 같은 URL `/api/dostk/slb` 에 ka20068 (종목별) 분기.

---

## 2. Request 명세

### 2.1 Header

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `api-id` | TR 명 | String | Y | 10 | `"ka10068"` 고정 |
| `authorization` | 접근토큰 | String | Y | 1000 | `Bearer <token>` |
| `cont-yn` | 연속조회 여부 | String | N | 1 | 응답 헤더 그대로 전달 |
| `next-key` | 연속조회 키 | String | N | 50 | 응답 헤더 그대로 전달 |

### 2.2 Body

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `strt_dt` | 시작일자 | String | N | 8 | `YYYYMMDD` |
| `end_dt` | 종료일자 | String | N | 8 | `YYYYMMDD` |
| `all_tp` | 전체구분 | Y | 6 | `1`:전체표시 (다른 값 미정의) |

> **`stk_cd` 없음** — 본 endpoint 는 시장 전체 대차. 종목별은 ka20068.
>
> **`all_tp=1` 고정**: Excel 에 다른 값 정의 없음. ka20068 의 `all_tp=0`(종목코드 입력종목만) 와 분리.

### 2.3 Request 예시 (Excel 원문)

```json
POST https://api.kiwoom.com/api/dostk/slb
Content-Type: application/json;charset=UTF-8
api-id: ka10068
authorization: Bearer Egicyx...

{
    "strt_dt": "20250401",
    "end_dt": "20250430",
    "all_tp": "1"
}
```

### 2.4 Pydantic 모델

```python
# app/adapter/out/kiwoom/slb.py
class LendingMarketTrendRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    strt_dt: Annotated[str, Field(pattern=r"^\d{8}$")] | None = None
    end_dt: Annotated[str, Field(pattern=r"^\d{8}$")] | None = None
    all_tp: Literal["1"] = "1"
```

---

## 3. Response 명세

### 3.1 Body

| Element | 한글명 | Type | Length | 영속화 컬럼 | 메모 |
|---------|-------|------|--------|-------------|------|
| `dbrt_trde_trnsn[]` | 대차거래추이 list | LIST | — | (전체 row 적재) | **list key 명** — ka20068 와 동일 |
| `dt` | 일자 | String | 8 | `trading_date` (DATE) | `YYYYMMDD`. ka20068 응답은 length=20 으로 다름 |
| `dbrt_trde_cntrcnt` | 대차거래체결주수 | String | 12 | `contracted_volume` (BIGINT) | 신규 대차 체결량 |
| `dbrt_trde_rpy` | 대차거래상환주수 | String | 18 | `repaid_volume` (BIGINT) | 상환된 대차량 |
| `dbrt_trde_irds` | 대차거래증감 | String | 60 | `delta_volume` (BIGINT) | = 체결 - 상환. **부호 가능** (예: `-13717978`) |
| `rmnd` | 잔고주수 | String | 18 | `balance_volume` (BIGINT) | 누적 잔고 |
| `remn_amt` | 잔고금액 | String | 18 | `balance_amount` (BIGINT) | 백만원 추정 |
| `return_code` | 처리코드 | Integer | — | (raw_response only) | 0 정상 |
| `return_msg` | 처리메시지 | String | — | (raw_response only) | |

### 3.2 Response 예시 (Excel, 일부)

```json
{
    "dbrt_trde_trnsn": [
        {
            "dt": "20250430",
            "dbrt_trde_cntrcnt": "35330036",
            "dbrt_trde_rpy": "25217364",
            "dbrt_trde_irds": "10112672",
            "rmnd": "2460259444",
            "remn_amt": "73956254"
        },
        {
            "dt": "20250428",
            "dbrt_trde_cntrcnt": "17165250",
            "dbrt_trde_rpy": "30883228",
            "dbrt_trde_irds": "-13717978",
            "rmnd": "2276180199",
            "remn_amt": "68480718"
        }
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다"
}
```

### 3.3 Pydantic + 정규화

```python
# app/adapter/out/kiwoom/_records.py
class LendingMarketRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    dt: str = ""
    dbrt_trde_cntrcnt: str = ""
    dbrt_trde_rpy: str = ""
    dbrt_trde_irds: str = ""
    rmnd: str = ""
    remn_amt: str = ""

    def to_normalized(self, *, scope: LendingScope) -> "NormalizedLendingMarket":
        return NormalizedLendingMarket(
            scope=scope,
            stock_id=None,                        # 시장 단위 — stock_id NULL
            trading_date=_parse_yyyymmdd(self.dt) or date.min,
            contracted_volume=_to_int(self.dbrt_trde_cntrcnt),
            repaid_volume=_to_int(self.dbrt_trde_rpy),
            delta_volume=_to_int(self.dbrt_trde_irds),
            balance_volume=_to_int(self.rmnd),
            balance_amount=_to_int(self.remn_amt),
        )


class LendingMarketResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    dbrt_trde_trnsn: list[LendingMarketRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""


class LendingScope(StrEnum):
    """시장 단위 vs 종목 단위 — `lending_balance_kw` 의 row 분기."""
    MARKET = "MARKET"      # ka10068
    STOCK = "STOCK"        # ka20068


@dataclass(frozen=True, slots=True)
class NormalizedLendingMarket:
    scope: LendingScope
    stock_id: int | None              # MARKET = None, STOCK = id
    trading_date: date
    contracted_volume: int | None
    repaid_volume: int | None
    delta_volume: int | None
    balance_volume: int | None
    balance_amount: int | None
```

---

## 4. NXT 처리

| 항목 | 적용 여부 |
|------|-----------|
| `stk_cd` 에 `_NX` suffix | **N** (stk_cd 자체 없음) |
| `nxt_enable` 게이팅 | N |
| `mrkt_tp` 별 분리 | N (응답이 시장 통합 전체) |

본 endpoint 는 시장 전체 대차 — KRX/NXT 분리 개념 없음. **단일 호출**.

⚠ **시장 분리 제공 여부**: Excel 명세는 KOSPI / KOSDAQ 분리 파라미터 없음 — 응답이 KRX 거래소 전체 통합 가정. 운영 검증 1순위 (ka10014 와 같은 mrkt_tp 분리 가능성).

---

## 5. DB 스키마

### 5.1 신규 테이블 — Migration 006 (`006_short_lending.py`)

> ka10014 의 `short_selling_kw` 와 같은 마이그레이션. ka20068 도 같은 테이블 (`scope` 컬럼으로 분리).

```sql
CREATE TABLE kiwoom.lending_balance_kw (
    id                  BIGSERIAL PRIMARY KEY,
    scope               VARCHAR(8) NOT NULL,                   -- "MARKET" / "STOCK"
    stock_id            BIGINT REFERENCES kiwoom.stock(id) ON DELETE CASCADE,
                                                                -- MARKET 일 때 NULL
    trading_date        DATE NOT NULL,
    contracted_volume   BIGINT,                                -- 체결주수
    repaid_volume       BIGINT,                                -- 상환주수
    delta_volume        BIGINT,                                -- 증감 (체결 - 상환, 부호)
    balance_volume      BIGINT,                                -- 잔고주수
    balance_amount      BIGINT,                                -- 잔고금액 (백만원 추정)
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- scope=MARKET: (scope, trading_date) UNIQUE (stock_id NULL 일 때)
    -- scope=STOCK: (scope, stock_id, trading_date) UNIQUE
    CONSTRAINT chk_lending_scope CHECK (
        (scope = 'MARKET' AND stock_id IS NULL) OR
        (scope = 'STOCK' AND stock_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX uq_lending_market_date
    ON kiwoom.lending_balance_kw(scope, trading_date)
    WHERE scope = 'MARKET' AND stock_id IS NULL;

CREATE UNIQUE INDEX uq_lending_stock_date
    ON kiwoom.lending_balance_kw(scope, stock_id, trading_date)
    WHERE scope = 'STOCK' AND stock_id IS NOT NULL;

CREATE INDEX idx_lending_trading_date ON kiwoom.lending_balance_kw(trading_date);
CREATE INDEX idx_lending_stock ON kiwoom.lending_balance_kw(stock_id) WHERE stock_id IS NOT NULL;
```

> **partial unique index 두 개**: scope 별로 UNIQUE 키 다름. PostgreSQL 의 partial index 패턴.
>
> **MARKET 일 때 stock_id NULL**: CHECK constraint 로 무결성 보장.

### 5.2 ORM 모델

```python
# app/adapter/out/persistence/models/lending_balance_kw.py
class LendingBalanceKw(Base):
    __tablename__ = "lending_balance_kw"
    __table_args__ = (
        Index("uq_lending_market_date", "scope", "trading_date",
              unique=True,
              postgresql_where=text("scope = 'MARKET' AND stock_id IS NULL")),
        Index("uq_lending_stock_date", "scope", "stock_id", "trading_date",
              unique=True,
              postgresql_where=text("scope = 'STOCK' AND stock_id IS NOT NULL")),
        CheckConstraint(
            "(scope = 'MARKET' AND stock_id IS NULL) OR "
            "(scope = 'STOCK' AND stock_id IS NOT NULL)",
            name="chk_lending_scope",
        ),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(8), nullable=False)
    stock_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("kiwoom.stock.id", ondelete="CASCADE"), nullable=True
    )
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)

    contracted_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    repaid_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    delta_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    balance_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    balance_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

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

| 항목 | MARKET (본) | STOCK (ka20068) |
|------|----|----|
| 1일 row | 1 | ~3,000 |
| 1년 (252 거래일) | ~252 | ~756,000 |
| 3년 백필 | ~756 | ~2.27M |

→ MARKET 단위는 무시할 수준 부담. STOCK 단위 (ka20068) 가 부담 큼.

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomLendingClient.fetch_market_trend`

```python
# app/adapter/out/kiwoom/slb.py
class KiwoomLendingClient:
    """`/api/dostk/slb` 카테고리. ka10068 / ka20068 공유."""

    PATH = "/api/dostk/slb"

    def __init__(self, kiwoom_client: KiwoomClient) -> None:
        self._client = kiwoom_client

    async def fetch_market_trend(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        max_pages: int = 5,
    ) -> list[LendingMarketRow]:
        """시장 전체 대차거래 추이 — 단일 호출 (mrkt_tp 분리 없음)."""
        body: dict[str, Any] = {"all_tp": "1"}
        if start_date is not None:
            body["strt_dt"] = start_date.strftime("%Y%m%d")
        if end_date is not None:
            body["end_dt"] = end_date.strftime("%Y%m%d")

        all_rows: list[LendingMarketRow] = []
        async for page in self._client.call_paginated(
            api_id="ka10068",
            endpoint=self.PATH,
            body=body,
            max_pages=max_pages,
        ):
            parsed = LendingMarketResponse.model_validate(page.body)
            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id="ka10068",
                    return_code=parsed.return_code,
                    return_msg=parsed.return_msg,
                )
            all_rows.extend(parsed.dbrt_trde_trnsn)

        return all_rows

    # ka20068 의 fetch_stock_trend 는 endpoint-17 계획서 참조
```

### 6.2 Repository — `LendingBalanceKwRepository`

```python
# app/adapter/out/persistence/repositories/lending_balance.py
class LendingBalanceKwRepository:
    """MARKET / STOCK 두 scope 통합 인터페이스."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_market(self, rows: Sequence[NormalizedLendingMarket]) -> int:
        """ka10068 — scope=MARKET 적재."""
        if not rows:
            return 0
        values = [
            {
                "scope": LendingScope.MARKET.value,
                "stock_id": None,
                "trading_date": r.trading_date,
                "contracted_volume": r.contracted_volume,
                "repaid_volume": r.repaid_volume,
                "delta_volume": r.delta_volume,
                "balance_volume": r.balance_volume,
                "balance_amount": r.balance_amount,
            }
            for r in rows if r.trading_date != date.min
        ]
        if not values:
            return 0

        # PostgreSQL partial unique index (scope, trading_date) WHERE scope='MARKET'
        stmt = pg_insert(LendingBalanceKw).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["scope", "trading_date"],
            index_where=text("scope = 'MARKET' AND stock_id IS NULL"),
            set_={
                "contracted_volume": stmt.excluded.contracted_volume,
                "repaid_volume": stmt.excluded.repaid_volume,
                "delta_volume": stmt.excluded.delta_volume,
                "balance_volume": stmt.excluded.balance_volume,
                "balance_amount": stmt.excluded.balance_amount,
                "fetched_at": func.now(),
                "updated_at": func.now(),
            },
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return rowcount_of(result)

    async def get_market_range(
        self, *, start_date: date, end_date: date,
    ) -> list[LendingBalanceKw]:
        stmt = (
            select(LendingBalanceKw)
            .where(
                LendingBalanceKw.scope == "MARKET",
                LendingBalanceKw.trading_date >= start_date,
                LendingBalanceKw.trading_date <= end_date,
            )
            .order_by(LendingBalanceKw.trading_date)
        )
        return list((await self._session.execute(stmt)).scalars())

    # upsert_stock / get_stock_range 는 endpoint-17 (ka20068) 에서 동일 패턴
```

### 6.3 UseCase — `IngestLendingMarketUseCase`

```python
# app/application/service/lending_service.py
class IngestLendingMarketUseCase:
    """ka10068 시장 단위 대차 적재. 단일 호출 — bulk 없음 (시장 1개)."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        slb_client: KiwoomLendingClient,
    ) -> None:
        self._session = session
        self._client = slb_client
        self._repo = LendingBalanceKwRepository(session)

    async def execute(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> LendingMarketIngestOutcome:
        try:
            raw_rows = await self._client.fetch_market_trend(
                start_date=start_date, end_date=end_date,
            )
        except KiwoomBusinessError as exc:
            return LendingMarketIngestOutcome(
                upserted=0, error=f"business: {exc.return_code}",
            )

        normalized = [
            r.to_normalized(scope=LendingScope.MARKET) for r in raw_rows
        ]
        upserted = await self._repo.upsert_market(normalized)

        return LendingMarketIngestOutcome(
            start_date=start_date, end_date=end_date,
            fetched=len(raw_rows), upserted=upserted,
        )


@dataclass(frozen=True, slots=True)
class LendingMarketIngestOutcome:
    start_date: date | None = None
    end_date: date | None = None
    fetched: int = 0
    upserted: int = 0
    error: str | None = None
```

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **수동** | on-demand | `POST /api/kiwoom/lending/market?start=YYYY-MM-DD&end=YYYY-MM-DD` (admin) |
| **일 1회 cron** | KST 20:00 평일 | ka10014 (19:45) 직후. 단일 호출 — RPS 부담 없음 |
| **백필** | on-demand | `python scripts/backfill_lending.py --start 2023-01-01 --end 2026-05-07` |

### 7.1 라우터

```python
# app/adapter/web/routers/lending.py
router = APIRouter(prefix="/api/kiwoom/lending", tags=["kiwoom-lending"])


@router.post(
    "/market",
    response_model=LendingMarketIngestOutcomeOut,
    dependencies=[Depends(require_admin_key)],
)
async def ingest_lending_market(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    use_case: IngestLendingMarketUseCase = Depends(get_ingest_lending_market_use_case),
) -> LendingMarketIngestOutcomeOut:
    outcome = await use_case.execute(start_date=start, end_date=end)
    return LendingMarketIngestOutcomeOut.model_validate(asdict(outcome))


@router.get(
    "/market",
    response_model=list[LendingBalanceOut],
)
async def get_lending_market_range(
    start: date = Query(...),
    end: date = Query(...),
    session: AsyncSession = Depends(get_session),
) -> list[LendingBalanceOut]:
    repo = LendingBalanceKwRepository(session)
    rows = await repo.get_market_range(start_date=start, end_date=end)
    return [LendingBalanceOut.model_validate(r) for r in rows]
```

### 7.2 APScheduler Job

```python
# app/batch/lending_market_job.py
async def fire_lending_market_sync() -> None:
    """매 평일 20:00 KST — 직전 1주 시장 대차 적재."""
    today = date.today()
    if not is_trading_day(today):
        return
    try:
        async with get_sessionmaker()() as session:
            kiwoom_client = build_kiwoom_client_for("prod-main")
            slb = KiwoomLendingClient(kiwoom_client)
            uc = IngestLendingMarketUseCase(session, slb_client=slb)
            outcome = await uc.execute(
                start_date=today - timedelta(days=7),
                end_date=today,
            )
            await session.commit()
        logger.info(
            "lending market sync 완료 fetched=%d upserted=%d",
            outcome.fetched, outcome.upserted,
        )
    except Exception:
        logger.exception("lending market sync 콜백 예외")


scheduler.add_job(
    fire_lending_market_sync,
    CronTrigger(day_of_week="mon-fri", hour=20, minute=0, timezone=KST),
    id="lending_market_sync",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
    misfire_grace_time=60 * 30,    # 30분 grace (단일 호출)
)
```

### 7.3 RPS / 시간

| 항목 | 값 |
|------|----|
| 1회 sync 호출 수 | 1 (시장 단위) |
| 페이지네이션 | 1 (1주 = ~5 거래일) |
| 시간 | <5초 |

→ cron 20:00 + 30분 grace.

---

## 8. 에러 처리

| HTTP / 응답 | 도메인 예외 | 라우터 매핑 | UseCase 정책 |
|-------------|-------------|-------------|--------------|
| 401 / 403 | `KiwoomCredentialRejectedError` | 400 | bubble up |
| 429 | `KiwoomRateLimitedError` | 503 | 재시도 |
| 5xx, 네트워크 | `KiwoomUpstreamError` | 502 | bubble up |
| `return_code != 0` | `KiwoomBusinessError` | 400 | outcome.error 노출 |
| 응답 `dt=""` | (적재 skip) | — | upsert_market 자동 제외 |
| 빈 list | (정상) | — | upserted=0 |

---

## 9. 테스트

### 9.1 Unit

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 단일 페이지 | 200 + list 5건 | 5건 반환 |
| 페이지네이션 | 첫 cont-yn=Y, 둘째 N | 합쳐 N건 |
| 빈 list | 200 + `dbrt_trde_trnsn=[]` | 빈 list |
| `return_code=1` | 비즈니스 에러 | `KiwoomBusinessError` |
| `dt=""` row | 빈 dt + 정상 4건 | repo skip |
| 부호 포함 (`delta_volume`) | dbrt_trde_irds="-13717978" | `_to_int` → -13717978 |
| 페이지네이션 폭주 | cont-yn=Y 무한 | `KiwoomPaginationLimitError` |

### 9.2 Integration

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| MARKET INSERT (DB 빈) | 응답 5 row | scope=MARKET 5 row INSERT, stock_id=NULL |
| UPDATE (멱등성) | 같은 호출 두 번 | row 5개 유지, updated_at 갱신 |
| MARKET / STOCK 충돌 안 함 | 같은 trading_date 에 MARKET row + STOCK row | 두 row 분리 (partial unique index) |
| CHECK constraint | scope=MARKET + stock_id=1 INSERT 시도 | IntegrityError |
| 빈 응답 | 응답 list=[] | upserted=0 |

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `app/adapter/out/kiwoom/slb.py` — `KiwoomLendingClient.fetch_market_trend` (ka20068 의 `fetch_stock_trend` 와 같은 클래스)
- [ ] `app/adapter/out/kiwoom/_records.py` — `LendingMarketRow`, `LendingMarketResponse`, `LendingScope` enum, `NormalizedLendingMarket`
- [ ] `app/adapter/out/persistence/models/lending_balance_kw.py` — `LendingBalanceKw` (partial unique index)
- [ ] `app/adapter/out/persistence/repositories/lending_balance.py` — `LendingBalanceKwRepository.upsert_market` (ka20068 의 `upsert_stock` 같은 파일)
- [ ] `app/application/service/lending_service.py` — `IngestLendingMarketUseCase`
- [ ] `app/adapter/web/routers/lending.py` — POST/GET market endpoints
- [ ] `app/batch/lending_market_job.py` — APScheduler 등록 (KST mon-fri 20:00)
- [ ] `migrations/versions/006_short_lending.py` — `lending_balance_kw` (ka10014 의 short_selling_kw 와 같은 마이그레이션)

### 10.2 테스트

- [ ] Unit 7 시나리오 PASS
- [ ] Integration 5 시나리오 PASS

### 10.3 운영 검증

- [ ] **시장 분리 응답 가능 여부** — KOSPI / KOSDAQ 분리 파라미터가 진짜 없는지 (응답이 통합 데이터인지)
- [ ] `dt` 정렬 (예시 DESC — 동일 가정)
- [ ] **`balance_amount` 단위** (백만원 추정 — 운영 검증 후 master.md § 12)
- [ ] `delta_volume = contracted_volume - repaid_volume` 검증
- [ ] 1 페이지 응답 일수 (1달 윈도 기준)
- [ ] `rmnd` 가 누적 잔고인지 일별 변동인지 (Excel 명세 모호)

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10068 lending market trend ingest`
- [ ] `master.md` § 12 결정 기록에:
  - 시장 분리 응답 가능성
  - `balance_amount` 단위 확정

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | sync 윈도 | 1주 (현재) / 1달 / 1일 | Phase E 코드화 |
| 2 | 시장 분리 가능 여부 | 운영 검증 후 결정 | DoD § 10.3 |
| 3 | scope=MARKET 의 stock_id NULL 처리 | partial unique index (현재) / 별도 테이블 분리 | Phase E 코드화 |
| 4 | 백필 윈도 | 3년 / 1년 | Phase H |

### 11.2 알려진 위험

- **시장 분리 미지원 가능성**: Excel 명세상 mrkt_tp 파라미터 없음. 응답이 KRX 거래소 전체 통합 가정 — 별도 KOSPI/KOSDAQ 분리 호출 불가 가능성. 운영 검증 1순위
- **`dt` 정렬**: 예시 DESC. 백테스팅 엔진은 ASC 가정 — 정규화 후 ORDER BY 강제
- **`balance_amount` 단위**: 백만원 추정. ka10014 / ka10081 와 같은 단위 가정. 운영 검증
- **`rmnd` 누적 의미**: "잔고주수" — 누적 잔고 (`rolling balance`) 인지 일별 변동인지 모호. 응답 row 들의 잔고 차이로 검증 가능
- **`delta_volume` 부호**: Excel 예시 `-13717978` 부호 명시. 음수면 상환 > 체결 (대차 잔고 감소)
- **응답 정렬과 누적값**: DESC 정렬 + 잔고 누적값 함께 처리 시 백테스팅 엔진의 시계열 가정과 충돌 가능 — 정규화 후 ASC 정렬 강제
- **시장 단위 데이터의 의미**: 종목 단위 (ka20068) 시그널과 시장 단위 (본 endpoint) 시그널을 같은 derived feature 에 합치면 단위 mismatch — 백테스팅 엔진이 두 scope 분리 처리

### 11.3 ka10068 vs ka20068 비교

| 항목 | ka10068 (시장) | ka20068 (종목별) |
|------|---------------|------------------|
| URL | /api/dostk/slb | 동일 |
| Body 식별자 | `all_tp=1` (없음) | `stk_cd` (Y) + `all_tp=0` |
| 응답 list 키 | `dbrt_trde_trnsn` | 동일 |
| 응답 필드 수 | 6 | 동일 6 (length 다름 — 8/12/18 vs 20/20/20) |
| Repository | `upsert_market` | `upsert_stock` |
| Service | `IngestLendingMarketUseCase` | `IngestLendingStockUseCase` |
| scope | MARKET | STOCK |
| 호출 빈도 | 일 1회 | 일 1회 × 3000 종목 |
| sync 시간 | <5초 | 30~60분 |

→ 두 endpoint 같은 테이블 (`lending_balance_kw`) + scope 컬럼 분기. ka20068 은 endpoint-17 계획서.

### 11.4 ka10014 vs 본 endpoint 비교 (시그널 카테고리)

| 항목 | ka10014 공매도 | 본 endpoint 대차 | ka20068 종목 대차 |
|------|---------------|------------------|------------------|
| URL | /api/dostk/shsa | /api/dostk/slb | 동일 |
| 단위 | 종목 | 시장 전체 | 종목 |
| 매도 압력 의미 | 직접 (raw 매도) | 거시 (외인 의도) | 종목 단위 거시 |
| 잔고 | 누적 공매도량 (`ovr_shrts_qty`) | 잔고 주수/금액 (`rmnd`) | 동일 |
| 시그널 | 매매비중 spike | 잔고 추세 | 잔고 추세 |
| 영속화 | short_selling_kw | lending_balance_kw | 동일 |

→ 매도 측 시그널 3중 (공매도 raw + 대차 거시 + 대차 종목별). 백테스팅 엔진이 각 source 별 weight 결정.

### 11.5 향후 확장

- **시장 단위 vs 종목 단위 합산 정합성**: ka10068 응답 합 vs ka20068 종목별 합 — 데이터 품질 리포트 (Phase H)
- **외인 매도 시그널 derived feature**: 대차 잔고 5일 이동평균 + 5일 변동률 → 외인 공매도 직전 신호
- **시장 분리 응답 가능 시 처리**: 운영 검증 후 KOSPI / KOSDAQ 분리 호출 — 본 테이블에 `market_code` 컬럼 추가
- **잔고 vs 거래의 의미 분리**: contracted_volume (체결) 은 일별 변동, balance_volume (잔고) 은 누적 — 시그널 연산 시 분리

---

_Phase E 의 두 번째 endpoint. ka10014 (종목 공매도) 의 거시 보완. 시장 단위라 호출 부담 작음 — 단일 호출 일 1회. ka20068 (종목별) 와 같은 URL 공유, 같은 테이블 적재 (scope 컬럼 분기)._
