# endpoint-17-ka20068.md — 대차거래추이요청 (종목별)

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka20068` |
| API 명 | 대차거래추이요청(종목별) |
| 분류 | Tier 5 (시그널 보강 — 대차) |
| Phase | **E** |
| 우선순위 | **P2** (2주 내) |
| Method | `POST` |
| URL | `/api/dostk/slb` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX 만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| 의존 endpoint | `au10001`, `ka10099` (stock 마스터) |
| 후속 endpoint | (없음 — 시그널 입력) |

---

## 1. 목적

종목 단위 **대차거래** 일별 추이를 적재한다. ka10068 (시장 단위) 의 종목별 분리 — 같은 응답 schema, 다른 식별자 (`stk_cd` 추가).

1. **종목별 외인 매도 시그널** — 종목 단위 대차 잔고 spike → 공매도 압력 신호
2. **대차 잔고 vs 시가총액 비율** — `balance_volume / list_count` (Phase B 의 ka10099) 로 잔고 비중 산출
3. **종목 단위 매도 압력 종합** — 본 endpoint + ka10014 (공매도) + ka10086 (신용) 결합

**왜 P2**:
- 시장 단위 (ka10068) 만으로 거시 신호는 가능하지만, 백테스팅 종목 시그널은 본 endpoint 필수
- 호출 부담 = ka10014 와 동등 (3000 종목 × 1 호출)

**ka10068 와 차이**: stk_cd 추가 + `all_tp=0` (종목코드 입력 종목만). 응답 schema 동일. 본 계획서는 **ka10068 의 차이점만** 기술 (대부분 ka10068 패턴 복제).

---

## 2. Request 명세

### 2.1 Header

ka10068 동일 (`api-id="ka20068"` 만 다름).

### 2.2 Body

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `strt_dt` | 시작일자 | String | N | 8 | `YYYYMMDD` |
| `end_dt` | 종료일자 | String | N | 8 | `YYYYMMDD` |
| `all_tp` | 전체구분 | String | N | 1 | `0`:종목코드 입력종목만 표시 |
| `stk_cd` | 종목코드 | String | **Y** | **6** | ka10068 와 달리 6자리 — **NXT 미지원 가능성** |

> **★ stk_cd Length=6 (ka10068 의 ka10014 stk_cd Length=20 과 다름)**: NXT (`005930_NX`) 호출 가능 여부 운영 검증. 6자리만이라면 KRX 만.

### 2.3 Request 예시 (Excel 원문)

```json
POST https://api.kiwoom.com/api/dostk/slb
Content-Type: application/json;charset=UTF-8
api-id: ka20068
authorization: Bearer Egicyx...

{
    "strt_dt": "20250401",
    "end_dt": "20250430",
    "all_tp": "0",
    "stk_cd": "005930"
}
```

### 2.4 Pydantic 모델

```python
# app/adapter/out/kiwoom/slb.py
class LendingStockTrendRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    stk_cd: Annotated[str, Field(min_length=6, max_length=6)]  # ★ 6자리 only
    strt_dt: Annotated[str, Field(pattern=r"^\d{8}$")] | None = None
    end_dt: Annotated[str, Field(pattern=r"^\d{8}$")] | None = None
    all_tp: Literal["0"] = "0"
```

---

## 3. Response 명세

### 3.1 Body

ka10068 동일 schema. 응답 list 키도 같은 `dbrt_trde_trnsn` (6 필드).

| Element | 한글명 | Length (다름) | 영속화 |
|---------|-------|--------------|---------|
| `dt` | 일자 | **20** (ka10068 8) | trading_date |
| `dbrt_trde_cntrcnt` | 체결주수 | **20** (12) | contracted_volume |
| `dbrt_trde_rpy` | 상환주수 | **20** (18) | repaid_volume |
| `dbrt_trde_irds` | 증감 | **20** (60) | delta_volume |
| `rmnd` | 잔고주수 | **20** (18) | balance_volume |
| `remn_amt` | 잔고금액 | **20** (18) | balance_amount |

> 응답 length 가 ka10068 와 다름 — 같은 schema 라도 종목별이 더 작은 숫자라 패딩 길이 다를 가능성. 의미는 동일.

### 3.2 Response 예시 (Excel 원문)

```json
{
    "dbrt_trde_trnsn": [
        {
            "dt": "20250430",
            "dbrt_trde_cntrcnt": "1210354",
            "dbrt_trde_rpy": "2693108",
            "dbrt_trde_irds": "-1482754",
            "rmnd": "98242435",
            "remn_amt": "5452455"
        },
        {
            "dt": "20250428",
            "dbrt_trde_cntrcnt": "958772",
            "dbrt_trde_rpy": "3122807",
            "dbrt_trde_irds": "-2164035",
            "rmnd": "100245885",
            "remn_amt": "5593720"
        }
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다"
}
```

### 3.3 Pydantic — `LendingStockRow` (ka10068 의 LendingMarketRow 와 동일 schema)

```python
class LendingStockRow(BaseModel):
    """ka20068 응답 row — schema 는 ka10068 와 동일."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    dt: str = ""
    dbrt_trde_cntrcnt: str = ""
    dbrt_trde_rpy: str = ""
    dbrt_trde_irds: str = ""
    rmnd: str = ""
    remn_amt: str = ""

    def to_normalized(self, *, stock_id: int) -> "NormalizedLendingMarket":
        return NormalizedLendingMarket(
            scope=LendingScope.STOCK,
            stock_id=stock_id,
            trading_date=_parse_yyyymmdd(self.dt) or date.min,
            contracted_volume=_to_int(self.dbrt_trde_cntrcnt),
            repaid_volume=_to_int(self.dbrt_trde_rpy),
            delta_volume=_to_int(self.dbrt_trde_irds),
            balance_volume=_to_int(self.rmnd),
            balance_amount=_to_int(self.remn_amt),
        )


class LendingStockResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    dbrt_trde_trnsn: list[LendingStockRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""
```

> **`NormalizedLendingMarket` 재사용**: ka10068 / ka20068 같은 dataclass + scope 컬럼 분기.

---

## 4. NXT 처리

| 항목 | 적용 여부 |
|------|-----------|
| `stk_cd` 에 `_NX` suffix | **운영 검증 필요** (Length=6 명세지만 NXT 시도) |
| `nxt_enable` 게이팅 | (조건부) |
| `mrkt_tp` 별 분리 | N |

⚠ **stk_cd Length=6 (ka10014 의 20 과 달리)** — NXT 호출 시 `005930_NX` (8자리) 가 유효 처리되는지 첫 호출에서 확인. 실패 시 KRX 만 적재.

---

## 5. DB 스키마

ka10068 의 `lending_balance_kw` 테이블 재사용 — `scope=STOCK` 으로 분기. 새 테이블 / 마이그레이션 없음.

```sql
-- ka10068 의 partial unique index 활용
-- uq_lending_stock_date: (scope, stock_id, trading_date) WHERE scope='STOCK'
```

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomLendingClient.fetch_stock_trend`

```python
# app/adapter/out/kiwoom/slb.py (ka10068 의 같은 클래스에 메서드 추가)
class KiwoomLendingClient:
    PATH = "/api/dostk/slb"

    async def fetch_stock_trend(
        self,
        stock_code: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        max_pages: int = 5,
    ) -> list[LendingStockRow]:
        """단일 종목 대차거래 추이.

        주의: stk_cd Length=6 — NXT (`_NX`) 호출 운영 검증 필요.
        """
        if not (len(stock_code) == 6 and stock_code.isdigit()):
            raise ValueError(f"stock_code 6자리 숫자만: {stock_code}")

        body: dict[str, Any] = {
            "stk_cd": stock_code,    # ★ NXT suffix 운영 검증 후 build_stk_cd 도입
            "all_tp": "0",
        }
        if start_date is not None:
            body["strt_dt"] = start_date.strftime("%Y%m%d")
        if end_date is not None:
            body["end_dt"] = end_date.strftime("%Y%m%d")

        all_rows: list[LendingStockRow] = []
        async for page in self._client.call_paginated(
            api_id="ka20068",
            endpoint=self.PATH,
            body=body,
            max_pages=max_pages,
        ):
            parsed = LendingStockResponse.model_validate(page.body)
            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id="ka20068",
                    return_code=parsed.return_code,
                    return_msg=parsed.return_msg,
                )
            all_rows.extend(parsed.dbrt_trde_trnsn)

        return all_rows
```

### 6.2 Repository — `LendingBalanceKwRepository.upsert_stock`

```python
class LendingBalanceKwRepository:
    # upsert_market 는 ka10068 endpoint-16 참조

    async def upsert_stock(self, rows: Sequence[NormalizedLendingMarket]) -> int:
        """ka20068 — scope=STOCK 적재."""
        if not rows:
            return 0
        values = [
            {
                "scope": LendingScope.STOCK.value,
                "stock_id": r.stock_id,
                "trading_date": r.trading_date,
                "contracted_volume": r.contracted_volume,
                "repaid_volume": r.repaid_volume,
                "delta_volume": r.delta_volume,
                "balance_volume": r.balance_volume,
                "balance_amount": r.balance_amount,
            }
            for r in rows if r.trading_date != date.min and r.stock_id is not None
        ]
        if not values:
            return 0

        stmt = pg_insert(LendingBalanceKw).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["scope", "stock_id", "trading_date"],
            index_where=text("scope = 'STOCK' AND stock_id IS NOT NULL"),
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

    async def get_stock_range(
        self,
        stock_id: int,
        *,
        start_date: date,
        end_date: date,
    ) -> list[LendingBalanceKw]:
        stmt = (
            select(LendingBalanceKw)
            .where(
                LendingBalanceKw.scope == "STOCK",
                LendingBalanceKw.stock_id == stock_id,
                LendingBalanceKw.trading_date >= start_date,
                LendingBalanceKw.trading_date <= end_date,
            )
            .order_by(LendingBalanceKw.trading_date)
        )
        return list((await self._session.execute(stmt)).scalars())
```

### 6.3 UseCase — `IngestLendingStockUseCase` + `IngestLendingStockBulkUseCase`

```python
# app/application/service/lending_service.py
class IngestLendingStockUseCase:
    """단일 종목 대차거래 적재."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        slb_client: KiwoomLendingClient,
        lookup_use_case: LookupStockUseCase,
        env: Literal["prod", "mock"] = "prod",
    ) -> None:
        self._session = session
        self._client = slb_client
        self._lookup = lookup_use_case
        self._repo = LendingBalanceKwRepository(session)
        self._env = env

    async def execute(
        self,
        stock_code: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> LendingStockIngestOutcome:
        stock = await self._lookup.ensure_exists(stock_code)
        if not stock.is_active:
            return LendingStockIngestOutcome(
                stock_code=stock_code,
                upserted=0, skipped=True, reason="inactive",
            )

        try:
            raw_rows = await self._client.fetch_stock_trend(
                stock_code,
                start_date=start_date, end_date=end_date,
            )
        except KiwoomBusinessError as exc:
            return LendingStockIngestOutcome(
                stock_code=stock_code,
                upserted=0, error=f"business: {exc.return_code}",
            )

        normalized = [r.to_normalized(stock_id=stock.id) for r in raw_rows]
        upserted = await self._repo.upsert_stock(normalized)

        return LendingStockIngestOutcome(
            stock_code=stock_code,
            start_date=start_date, end_date=end_date,
            fetched=len(raw_rows), upserted=upserted,
        )


class IngestLendingStockBulkUseCase:
    """active 종목 대차거래 일괄 적재.

    동시성: RPS 4 + 250ms = 3000 / 4 × 0.25 = 188초 ≈ 3분 (이론).
    실측 추정 30~60분 (페이지네이션 + 응답 시간).
    """

    BATCH_SIZE = 50

    def __init__(
        self,
        session: AsyncSession,
        *,
        single_use_case: IngestLendingStockUseCase,
    ) -> None:
        self._session = session
        self._single = single_use_case

    async def execute(
        self,
        *,
        start_date: date,
        end_date: date,
        only_market_codes: Sequence[str] | None = None,
        only_stock_codes: Sequence[str] | None = None,
    ) -> LendingStockBulkResult:
        stmt = select(Stock).where(Stock.is_active.is_(True))
        if only_market_codes:
            stmt = stmt.where(Stock.market_code.in_(only_market_codes))
        if only_stock_codes:
            stmt = stmt.where(Stock.stock_code.in_(only_stock_codes))
        stocks = list((await self._session.execute(stmt)).scalars())

        outcomes: list[LendingStockIngestOutcome] = []
        for i, stock in enumerate(stocks, start=1):
            try:
                async with self._session.begin_nested():
                    o = await self._single.execute(
                        stock.stock_code,
                        start_date=start_date, end_date=end_date,
                    )
                    outcomes.append(o)
            except Exception as exc:
                logger.warning("lending stock 실패 %s: %s", stock.stock_code, exc)
                outcomes.append(LendingStockIngestOutcome(
                    stock_code=stock.stock_code,
                    error=f"{type(exc).__name__}: {exc}",
                ))

            if i % self.BATCH_SIZE == 0:
                await self._session.commit()
                logger.info("lending stock progress %d/%d", i, len(stocks))

        await self._session.commit()
        return LendingStockBulkResult(
            start_date=start_date, end_date=end_date,
            total_stocks=len(stocks), outcomes=outcomes,
        )


@dataclass(frozen=True, slots=True)
class LendingStockIngestOutcome:
    stock_code: str
    start_date: date | None = None
    end_date: date | None = None
    fetched: int = 0
    upserted: int = 0
    skipped: bool = False
    reason: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class LendingStockBulkResult:
    start_date: date
    end_date: date
    total_stocks: int
    outcomes: list[LendingStockIngestOutcome]

    @property
    def total_rows_inserted(self) -> int:
        return sum(o.upserted for o in self.outcomes)
```

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **수동 단건** | on-demand | `POST /api/kiwoom/lending/stock/{stock_code}?start=&end=` (admin) |
| **수동 일괄** | on-demand | `POST /api/kiwoom/lending/stock/sync` (admin) |
| **일 1회 cron** | KST 20:30 평일 | ka10068 (20:00) 직후. 종목 단위라 부담 큼 |
| **백필** | on-demand | `python scripts/backfill_lending_stock.py --start ... --end ...` |

### 7.1 라우터 추가 (lending.py 의 ka10068 라우터에)

```python
@router.post(
    "/stock/{stock_code}",
    response_model=LendingStockIngestOutcomeOut,
    dependencies=[Depends(require_admin_key)],
)
async def ingest_lending_stock(
    stock_code: str,
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    use_case: IngestLendingStockUseCase = Depends(get_ingest_lending_stock_use_case),
) -> LendingStockIngestOutcomeOut:
    outcome = await use_case.execute(stock_code, start_date=start, end_date=end)
    return LendingStockIngestOutcomeOut.model_validate(asdict(outcome))


@router.post(
    "/stock/sync",
    response_model=LendingStockBulkResultOut,
    dependencies=[Depends(require_admin_key)],
)
async def sync_lending_stock_bulk(
    body: LendingStockBulkRequestIn,
    use_case: IngestLendingStockBulkUseCase = Depends(get_ingest_lending_stock_bulk_use_case),
) -> LendingStockBulkResultOut:
    result = await use_case.execute(
        start_date=body.start_date, end_date=body.end_date,
        only_market_codes=body.only_market_codes or None,
        only_stock_codes=body.only_stock_codes or None,
    )
    return LendingStockBulkResultOut.model_validate(asdict(result))


@router.get(
    "/stock/{stock_code}",
    response_model=list[LendingBalanceOut],
)
async def get_lending_stock_range(
    stock_code: str,
    start: date = Query(...),
    end: date = Query(...),
    session: AsyncSession = Depends(get_session),
) -> list[LendingBalanceOut]:
    stock_repo = StockRepository(session)
    stock = await stock_repo.find_by_code(stock_code)
    if stock is None:
        raise HTTPException(status_code=404, detail=f"stock not found: {stock_code}")
    repo = LendingBalanceKwRepository(session)
    rows = await repo.get_stock_range(stock.id, start_date=start, end_date=end)
    return [LendingBalanceOut.model_validate(r) for r in rows]
```

### 7.2 APScheduler Job

```python
# app/batch/lending_stock_job.py
async def fire_lending_stock_sync() -> None:
    """매 평일 20:30 KST — 직전 1주 종목별 대차 적재."""
    today = date.today()
    if not is_trading_day(today):
        return
    try:
        async with get_sessionmaker()() as session:
            kiwoom_client = build_kiwoom_client_for("prod-main")
            slb = KiwoomLendingClient(kiwoom_client)
            stkinfo = KiwoomStkInfoClient(kiwoom_client)
            lookup = LookupStockUseCase(
                session, stkinfo_client=stkinfo, env=settings.kiwoom_default_env,
            )
            single = IngestLendingStockUseCase(
                session, slb_client=slb, lookup_use_case=lookup,
                env=settings.kiwoom_default_env,
            )
            bulk = IngestLendingStockBulkUseCase(session, single_use_case=single)
            result = await bulk.execute(
                start_date=today - timedelta(days=7),
                end_date=today,
            )
        logger.info(
            "lending stock sync 완료 total=%d rows=%d",
            result.total_stocks, result.total_rows_inserted,
        )
    except Exception:
        logger.exception("lending stock sync 콜백 예외")


scheduler.add_job(
    fire_lending_stock_sync,
    CronTrigger(day_of_week="mon-fri", hour=20, minute=30, timezone=KST),
    id="lending_stock_sync",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
    misfire_grace_time=60 * 90,
)
```

### 7.3 RPS / 시간

| 항목 | 값 |
|------|----|
| active 종목 수 | ~3,000 |
| 1회 sync 호출 수 | 3,000 (KRX only 가정) |
| 페이지네이션 평균 | 1 (1주 윈도) |
| 이론 시간 | 188초 ≈ 3분 |
| 실측 추정 | 30~60분 |

→ cron 20:30 + 90분 grace.

---

## 8. 에러 처리

ka10068 동일 + stock 미존재 시 LookupStockUseCase 가 ka10100 호출로 lazy fetch.

---

## 9. 테스트

### 9.1 Unit

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 단일 페이지 | 200 + list 5건 | 5건 반환 |
| stk_cd 7자리 | 차단 | `ValueError` |
| 빈 list (대차 없는 종목) | 200 + `dbrt_trde_trnsn=[]` | 빈 list |
| `return_code=1` | 비즈니스 에러 | `KiwoomBusinessError` |
| `dt=""` row | 자동 skip | repo |

### 9.2 Integration

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| STOCK INSERT (DB 빈) | stock 1건 + 응답 5 row | scope=STOCK 5 row INSERT |
| UPDATE (멱등성) | 같은 호출 두 번 | row 5개 유지, updated_at 갱신 |
| MARKET / STOCK 동시 존재 | scope=MARKET 5 + scope=STOCK 5 | 두 scope 분리 (partial unique index) |
| Bulk 50 batch | 100 종목 | 50건마다 commit |
| only_market_codes 필터 | KOSPI | KOSDAQ skip |

---

## 10. 완료 기준 (DoD)

### 10.1 코드 (ka10068 와 같은 파일에 추가)

- [ ] `app/adapter/out/kiwoom/slb.py` — `KiwoomLendingClient.fetch_stock_trend`
- [ ] `app/adapter/out/kiwoom/_records.py` — `LendingStockRow`, `LendingStockResponse`
- [ ] `app/adapter/out/persistence/repositories/lending_balance.py` — `LendingBalanceKwRepository.upsert_stock` / `get_stock_range`
- [ ] `app/application/service/lending_service.py` — `IngestLendingStockUseCase`, `IngestLendingStockBulkUseCase`
- [ ] `app/adapter/web/routers/lending.py` — POST/GET stock endpoints (ka10068 라우터 확장)
- [ ] `app/batch/lending_stock_job.py` — APScheduler 등록 (KST mon-fri 20:30)

### 10.2 테스트

- [ ] Unit 5 시나리오 PASS
- [ ] Integration 5 시나리오 PASS

### 10.3 운영 검증

- [ ] **NXT 호출 가능 여부** (stk_cd Length=6 명세) — `005930_NX` 시도 응답
- [ ] `dt` 정렬 (예시 DESC)
- [ ] 1 페이지 응답 일수
- [ ] `delta_volume` 부호 일관성 (ka10068 와 비교)
- [ ] active 3000 종목 sync 실측 시간

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka20068 lending stock trend ingest`

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | NXT 호출 정책 | KRX 만 (현재) / NXT 시도 | 운영 검증 후 |
| 2 | sync 윈도 | 1주 (현재) / 1달 | Phase E 코드화 |
| 3 | 백필 윈도 | 3년 / 1년 | Phase H |

### 11.2 알려진 위험

- **stk_cd Length=6 → NXT 미지원 가능성**: ka10014 (Length=20) 와 다름. NXT 호출 시 `005930_NX` (8자리) 가 거부될 수 있음. 운영 1순위 검증
- **ka10068 vs 본 endpoint 합산 정합성**: ka10068 시장 합 = ka20068 종목별 합 가정. 차이가 크면 어느 source 가 정답인지 데이터 품질 리포트
- **응답 length 차이 (8/12/18 vs 20)**: 데이터 의미는 동일. Pydantic 검증에서 String 으로 받으므로 문제 없음
- **`balance_amount` 단위**: ka10068 와 같은 단위 가정. 본 endpoint 만의 백만원 vs 원 차이 검증
- **종목 단위 대차 미지원 종목**: 일부 ETF / 스펙 / 우선주는 대차 거래 미지원 — 빈 응답 가능 (정상)

### 11.3 ka10068 vs ka20068 비교 (재정리)

| 항목 | ka10068 | ka20068 |
|------|---------|---------|
| Body 식별자 | `all_tp=1` | `stk_cd` (6) + `all_tp=0` |
| stk_cd Length | — | 6 (NXT 미지원 가능) |
| Repository | upsert_market | upsert_stock |
| Service | IngestLendingMarketUseCase | IngestLendingStockUseCase |
| scope | MARKET | STOCK |
| stock_id | NULL | FK |
| 호출 빈도 | 1 / day | 3000 / day |
| sync 시간 | <5초 | 30~60분 |
| cron | 20:00 | 20:30 |

→ 같은 URL `/api/dostk/slb` + 같은 응답 schema + 같은 테이블 (`scope` 컬럼 분기) → 코드 재사용 최대화. 본 계획서가 짧은 이유.

### 11.4 향후 확장

- **종목별 대차 잔고 / 시가총액 비율**: balance_volume / stock.list_count → 잔고 비중 시그널
- **공매도 + 대차 derived 시그널**: ka10014 의 short_volume + 본 endpoint 의 contracted_volume 가산 → 종합 매도 압력
- **ETF / 스펙 / 우선주 빈 응답 빈도**: 운영 1주 모니터 후 화이트리스트 / 블랙리스트 검토

---

_Phase E 의 세 번째이자 마지막 endpoint. ka10068 (시장) 의 종목별 분리. 같은 URL / 같은 응답 schema / 같은 테이블 — 본 계획서가 차이점만 짧게 기술. ka10014 (공매도) 와 결합으로 매도 압력 시그널 종합 분석 가능._

---

## 12. Phase E 통합 chunk (cross-ref)

> **본 endpoint 의 ted-run 진입 chunk 는 `endpoint-15-ka10014.md` § 12 (Phase E — Migration 016 + 매도 측 시그널 3 endpoint 통합) 참조** — 2026-05-12 추가.
>
> ka10014 (공매도) + ka10068 (시장 대차) + ka20068 (본 endpoint, 종목 대차) 3 endpoint 를 사용자 결정으로 통합 1 chunk 로 동시 ted-run. 결정 사항 (Migration 016 / scope 분기 / cron 시간 08:00 KST / NXT 정책 KRX only / scheduler_enabled / partial 임계치 등) 과 self-check (H-1~H-13) 와 DoD 는 모두 `endpoint-15-ka10014.md` § 12 에 단일 진실 출처로 작성됨. 본 endpoint 의 § 1~11 본문은 그대로 ted-run 입력.
