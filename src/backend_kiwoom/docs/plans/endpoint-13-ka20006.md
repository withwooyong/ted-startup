# endpoint-13-ka20006.md — 업종일봉조회요청 (보강 시계열)

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka20006` |
| API 명 | 업종일봉조회요청 |
| 분류 | Tier 4 (보강 시계열 — 업종 지수) |
| Phase | **D** |
| 우선순위 | **P2** |
| Method | `POST` |
| URL | `/api/dostk/chart` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX 만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| 의존 endpoint | `au10001`, `ka10101` (업종 마스터) |
| 후속 endpoint | (없음 — 섹터 회전 / 시장 비교 백테스트의 입력) |

---

## 1. 목적

**업종 단위 일봉 OHLCV** 를 적재한다. ka10081 이 종목 단위 일봉이라면, 본 endpoint 는 KOSPI / KOSDAQ / 업종 지수 단위. 백테스팅 측면:

1. **섹터 회전 시그널** — 종합(KOSPI) / 대형주 / 중형주 / 소형주 / 업종(음식료/화학/의약품/...) 의 상대 강도
2. **시장 비교 (Beta)** — 종목 일봉 vs 업종 일봉의 상관계수 / 베타 계산
3. **업종 momentum** — 일봉 종가 N일 변화율로 업종 단위 추세 추적
4. **시장 redirect 시그널** — KOSPI200 vs KRX100 의 발산 패턴

**왜 P2**:
- 백테스팅 첫 사이클은 종목 단위로 충분
- 그러나 시그널의 "시장 대비 상대 강도" 보강은 본 endpoint 가 핵심
- 데이터 부담은 종목 OHLCV 의 1/100 수준 (업종 ~50개 vs 종목 ~3000개)

**Phase D 3 endpoint 중 본 endpoint 가 가장 가벼움**. 종목과 별개 카테고리라 ka10081 패턴 복제하면서 NXT 미지원으로 단순화.

---

## 2. Request 명세

### 2.1 Header

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `api-id` | TR 명 | String | Y | 10 | `"ka20006"` 고정 |
| `authorization` | 접근토큰 | String | Y | 1000 | `Bearer <token>` |
| `cont-yn` | 연속조회 여부 | String | N | 1 | 응답 헤더 그대로 전달 |
| `next-key` | 연속조회 키 | String | N | 50 | 응답 헤더 그대로 전달 |

### 2.2 Body

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `inds_cd` | 업종코드 | String | Y | **3** | `001`:종합(KOSPI), `002`:대형주, `003`:중형주, `004`:소형주, `101`:종합(KOSDAQ), `201`:KOSPI200, `302`:KOSTAR, `701`:KRX100 + 나머지 (ka10101 참조) |
| `base_dt` | 기준일자 | String | Y | 8 | `YYYYMMDD` (이 날짜를 포함한 과거 시계열 응답) |

> **주의**: ka10101 의 `mrkt_tp=2` (KOSPI200) → ka20006 의 `inds_cd=201` 매핑. 두 endpoint 의 코드 체계가 **다른 차원**이다.
>
> ka10101 의 `code` 필드 ("001"/"002"/...) 가 ka20006 의 `inds_cd` 와 직접 호환. UseCase 가 `Sector.sector_code` 를 그대로 사용.

### 2.3 Request 예시 (Excel 원문)

```json
POST https://api.kiwoom.com/api/dostk/chart
Content-Type: application/json;charset=UTF-8
api-id: ka20006
authorization: Bearer Egicyx...

{
    "inds_cd": "001",
    "base_dt": "20250905"
}
```

### 2.4 Pydantic 모델

```python
# app/adapter/out/kiwoom/chart.py (또는 sect.py 분리)
class SectorChartRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    inds_cd: Annotated[str, Field(min_length=3, max_length=3, pattern=r"^\d{3}$")]
    base_dt: Annotated[str, Field(pattern=r"^\d{8}$")]
```

> ka10081 과 달리 **`upd_stkpc_tp` 없음** — 지수는 수정주가 개념이 다름 (자체 보정).

---

## 3. Response 명세

### 3.1 Header

| Element | Type | Description |
|---------|------|-------------|
| `api-id` | String | `"ka20006"` 에코 |
| `cont-yn` | String | `Y` 면 다음 페이지 |
| `next-key` | String | 다음 호출 헤더에 세팅 |

### 3.2 Body

| Element | 한글명 | Type | Length | 영속화 컬럼 | 메모 |
|---------|-------|------|--------|-------------|------|
| `inds_cd` | 업종코드 | String | 20 | (FK lookup via Sector) | 응답 length 20 — 요청 3 과 다름 |
| `inds_dt_pole_qry[]` | 업종일봉차트 list | LIST | — | (전체 row 적재) | **list key 명** |
| `cur_prc` | 현재가 (지수 종가) | String | 20 | `close_index_centi` (BIGINT) | **★ 지수값은 소수점 제거 후 100배 값으로 반환** (예: `252127` = 2521.27) |
| `trde_qty` | 거래량 | String | 20 | `trade_volume` (BIGINT) | 주 |
| `dt` | 일자 | String | 20 | `trading_date` (DATE) | `YYYYMMDD` |
| `open_pric` | 시가 (지수 시가) | String | 20 | `open_index_centi` (BIGINT) | **100배 값** |
| `high_pric` | 고가 | String | 20 | `high_index_centi` (BIGINT) | **100배 값** |
| `low_pric` | 저가 | String | 20 | `low_index_centi` (BIGINT) | **100배 값** |
| `trde_prica` | 거래대금 | String | 20 | `trade_amount` (BIGINT) | 백만원 추정 (운영 검증) |
| `return_code` | 처리코드 | Integer | — | (raw_response only) | 0 정상 |
| `return_msg` | 처리메시지 | String | — | (raw_response only) | |

> **★ 가장 큰 ka10081 과의 차이**: "지수 값은 소수점 제거 후 100배 값으로 반환"
> - 예: KOSPI 종합 2521.27 → 응답 `"252127"`
> - 영속화: 그대로 BIGINT 저장 (centi-index 단위) + 컬럼명에 `_centi` suffix 로 명시
> - 또는 NUMERIC(12,2) 로 응답 / 100 저장 — **두 옵션 § 11.1 결정 필요**
>
> **`pred_pre`/`pred_pre_sig`/`trde_tern_rt` 없음** (ka10081 에 비해): 지수 카테고리는 전일대비 / 회전율 미제공. 백테스팅에서 필요하면 derived feature.

### 3.3 Response 예시 (Excel 원문)

```json
{
    "inds_cd": "001",
    "inds_dt_pole_qry": [
        {
            "cur_prc": "252127",
            "trde_qty": "393564",
            "dt": "20250210",
            "open_pric": "251064",
            "high_pric": "252733",
            "low_pric": "249918",
            "trde_prica": "10582466"
        },
        {
            "cur_prc": "252192",
            "trde_qty": "419872",
            "dt": "20250207",
            "open_pric": "253209",
            "high_pric": "253763",
            "low_pric": "251901",
            "trde_prica": "10240141"
        }
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다"
}
```

> KOSPI 종합 (`inds_cd=001`) 의 2025-02-10 종가 = 2521.27 (응답 252127). 정렬은 DESC (예시 기준).

### 3.4 Pydantic 모델 + 정규화

```python
# app/adapter/out/kiwoom/_records.py
class SectorChartRow(BaseModel):
    """ka20006 응답 row."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    cur_prc: str = ""
    trde_qty: str = ""
    dt: str = ""
    open_pric: str = ""
    high_pric: str = ""
    low_pric: str = ""
    trde_prica: str = ""

    def to_normalized(
        self,
        *,
        sector_id: int,
    ) -> "NormalizedSectorDailyOhlcv":
        return NormalizedSectorDailyOhlcv(
            sector_id=sector_id,
            trading_date=_parse_yyyymmdd(self.dt) or date.min,
            open_index_centi=_to_int(self.open_pric),
            high_index_centi=_to_int(self.high_pric),
            low_index_centi=_to_int(self.low_pric),
            close_index_centi=_to_int(self.cur_prc),
            trade_volume=_to_int(self.trde_qty),
            trade_amount=_to_int(self.trde_prica),
        )


class SectorChartResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    inds_cd: str = ""
    inds_dt_pole_qry: list[SectorChartRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""


@dataclass(frozen=True, slots=True)
class NormalizedSectorDailyOhlcv:
    sector_id: int
    trading_date: date
    open_index_centi: int | None        # 응답 그대로 (×100 값)
    high_index_centi: int | None
    low_index_centi: int | None
    close_index_centi: int | None
    trade_volume: int | None
    trade_amount: int | None

    # 사용자 친화 read 헬퍼
    @property
    def close_index(self) -> Decimal | None:
        return Decimal(self.close_index_centi) / 100 if self.close_index_centi is not None else None
```

> **저장 형식 결정** (§ 11.1): centi BIGINT (응답 그대로) + read 헬퍼로 / 100. 정수 산술이 빠르고 정확. 별도 NUMERIC 변환 불필요.

---

## 4. NXT 처리

| 항목 | 적용 여부 |
|------|-----------|
| `stk_cd` 에 `_NX` suffix | **N** (종목코드 없음 — 업종 지수) |
| `nxt_enable` 게이팅 | N |
| `mrkt_tp` 별 분리 | N |
| KRX 운영 / 모의 차이 | mockapi 는 KRX 전용 (지수도 동일) |

### 4.1 NXT 미지원의 의미

업종 지수는 거래소 통합 지수 — KRX/NXT 분리 개념 없음. ka10101 의 `mrkt_tp=2/4/7` (KOSPI200/100/KRX100) 도 지수이지 거래소가 아님.

→ 본 endpoint 는 단일 호출 (KRX/NXT 동시 호출 패턴 없음). master.md § 3 의 "물리 분리" 대상 아님.

→ 단, NXT 거래소가 별도 지수를 산출하면 (예: NXT 100) 본 endpoint 가 그 inds_cd 를 응답 가능. **운영 검증**: ka10101 의 응답에 NXT 관련 inds_cd 가 등장하는지 확인 후 본 endpoint 가 NXT 지수도 응답 가능한지 확인.

---

## 5. DB 스키마

### 5.1 신규 테이블 — Migration 002 또는 별도

> **결정 필요** (§ 11.1): Migration 002 (`stock_fundamental_and_sector.py`) 에 sector 와 함께 sector_price_daily 추가 vs 별도 마이그레이션 분리.
>
> **권장**: 별도 마이그레이션 `008_sector_price_daily.py` (Phase D 활성화 시점).
> 이유: sector 마스터는 Phase A (P1) 에 작성, 본 테이블은 Phase D — 적용 시점 분리.

```sql
CREATE TABLE kiwoom.sector_price_daily (
    id                       BIGSERIAL PRIMARY KEY,
    sector_id                BIGINT NOT NULL REFERENCES kiwoom.sector(id) ON DELETE CASCADE,
    trading_date             DATE NOT NULL,
    open_index_centi         BIGINT,                          -- 지수 × 100
    high_index_centi         BIGINT,
    low_index_centi          BIGINT,
    close_index_centi        BIGINT,
    trade_volume             BIGINT,
    trade_amount             BIGINT,
    fetched_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_sector_price_daily UNIQUE (sector_id, trading_date)
);

CREATE INDEX idx_sector_price_daily_date ON kiwoom.sector_price_daily(trading_date);
CREATE INDEX idx_sector_price_daily_sector ON kiwoom.sector_price_daily(sector_id);
```

### 5.2 ORM 모델

```python
# app/adapter/out/persistence/models/sector_price_daily.py
class SectorPriceDaily(Base):
    __tablename__ = "sector_price_daily"
    __table_args__ = (
        UniqueConstraint("sector_id", "trading_date", name="uq_sector_price_daily"),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sector_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("kiwoom.sector.id", ondelete="CASCADE"), nullable=False
    )
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)

    open_index_centi: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    high_index_centi: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    low_index_centi: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    close_index_centi: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    trade_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    trade_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

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
| 업종 수 (ka10101 5 시장 합계) | ~50~80 (운영 검증) |
| 1일 row | 50~80 |
| 1년 row (252 거래일) | ~12,600~20,160 |
| 3년 백필 | ~37,800~60,480 |

→ **단일 테이블, 파티션 불필요**. 종목 OHLCV 의 0.1~1% 부담.

### 5.4 sector 마스터와의 매핑

`Sector.sector_code` (ka10101 응답의 `code`) 가 ka20006 의 `inds_cd` 와 직접 호환. UseCase 가 `Sector.sector_code` 로 조회 → `Sector.id` 를 FK 로 사용.

⚠ **주의**: ka10101 의 `(market_code, sector_code)` UNIQUE — 같은 sector_code 가 시장별로 중복 가능. 본 endpoint 는 sector_code 만 받으므로 어느 market 의 sector 인지 구분 불가 → ka10101 의 `code` 가 시장 무관하게 unique 한지 운영 검증 필요. unique 하지 않다면 본 endpoint 의 inds_cd → market_code 매핑 규칙 필요.

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomChartClient.fetch_sector_daily` (또는 별도 클래스)

```python
# app/adapter/out/kiwoom/chart.py 또는 sect.py
class KiwoomChartClient:
    """ka10079~ka10094 + ka20006 공유."""

    PATH = "/api/dostk/chart"

    async def fetch_sector_daily(
        self,
        inds_cd: str,
        *,
        base_date: date,
        max_pages: int = 10,
    ) -> list[SectorChartRow]:
        """업종 일봉 시계열. cont-yn 자동 페이지네이션.

        - inds_cd: 3자리 ("001"/"101"/"201"/...). ka10101 sector_code 와 호환
        - max_pages=10 기본. 1 페이지 ~600 거래일 추정 (ka10081 와 동일 가정)
        """
        if not (len(inds_cd) == 3 and inds_cd.isdigit()):
            raise ValueError(f"inds_cd 3자리 숫자만: {inds_cd}")

        body = {
            "inds_cd": inds_cd,
            "base_dt": base_date.strftime("%Y%m%d"),
        }

        all_rows: list[SectorChartRow] = []
        async for page in self._client.call_paginated(
            api_id="ka20006",
            endpoint=self.PATH,
            body=body,
            max_pages=max_pages,
        ):
            parsed = SectorChartResponse.model_validate(page.body)
            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id="ka20006",
                    return_code=parsed.return_code,
                    return_msg=parsed.return_msg,
                )
            all_rows.extend(parsed.inds_dt_pole_qry)

        return all_rows
```

### 6.2 Repository

```python
# app/adapter/out/persistence/repositories/sector_price.py
class SectorPriceDailyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, rows: Sequence[NormalizedSectorDailyOhlcv]) -> int:
        if not rows:
            return 0

        values = [
            {
                "sector_id": r.sector_id,
                "trading_date": r.trading_date,
                "open_index_centi": r.open_index_centi,
                "high_index_centi": r.high_index_centi,
                "low_index_centi": r.low_index_centi,
                "close_index_centi": r.close_index_centi,
                "trade_volume": r.trade_volume,
                "trade_amount": r.trade_amount,
            }
            for r in rows
            if r.trading_date != date.min     # 빈 dt skip
        ]
        if not values:
            return 0

        stmt = pg_insert(SectorPriceDaily).values(values)
        update_set = {col: stmt.excluded[col] for col in values[0]
                      if col not in ("sector_id", "trading_date")}
        update_set["fetched_at"] = func.now()
        update_set["updated_at"] = func.now()
        stmt = stmt.on_conflict_do_update(
            index_elements=["sector_id", "trading_date"],
            set_=update_set,
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return rowcount_of(result)

    async def get_latest_date(self, sector_id: int) -> date | None:
        stmt = (
            select(SectorPriceDaily.trading_date)
            .where(SectorPriceDaily.sector_id == sector_id)
            .order_by(SectorPriceDaily.trading_date.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_range(
        self,
        sector_id: int,
        *,
        start_date: date,
        end_date: date,
    ) -> list[SectorPriceDaily]:
        stmt = (
            select(SectorPriceDaily)
            .where(
                SectorPriceDaily.sector_id == sector_id,
                SectorPriceDaily.trading_date >= start_date,
                SectorPriceDaily.trading_date <= end_date,
            )
            .order_by(SectorPriceDaily.trading_date)
        )
        return list((await self._session.execute(stmt)).scalars())
```

### 6.3 UseCase — `IngestSectorDailyUseCase`

```python
# app/application/service/sector_ohlcv_service.py
class IngestSectorDailyUseCase:
    """단일 업종 일봉 적재.

    sector 테이블에 inds_cd 가 없으면 KiwoomBusinessError 또는 캐시 미스 → 호출 안 함.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        chart_client: KiwoomChartClient,
    ) -> None:
        self._session = session
        self._client = chart_client
        self._sector_repo = SectorRepository(session)
        self._price_repo = SectorPriceDailyRepository(session)

    async def execute(
        self,
        inds_cd: str,
        *,
        base_date: date,
    ) -> SectorOhlcvIngestOutcome:
        # sector 마스터 조회 — 없으면 ka10101 sync 권고 후 fail
        sector = await self._sector_repo.find_by_code(inds_cd)
        if sector is None:
            return SectorOhlcvIngestOutcome(
                inds_cd=inds_cd,
                upserted=0,
                skipped=True,
                reason="sector_not_found",
            )
        if not sector.is_active:
            return SectorOhlcvIngestOutcome(
                inds_cd=inds_cd,
                upserted=0,
                skipped=True,
                reason="sector_inactive",
            )

        try:
            raw_rows = await self._client.fetch_sector_daily(
                inds_cd, base_date=base_date,
            )
        except KiwoomBusinessError as exc:
            return SectorOhlcvIngestOutcome(
                inds_cd=inds_cd,
                upserted=0,
                error=f"business: {exc.return_code}",
            )

        normalized = [
            r.to_normalized(sector_id=sector.id) for r in raw_rows
        ]
        upserted = await self._price_repo.upsert_many(normalized)

        return SectorOhlcvIngestOutcome(
            inds_cd=inds_cd,
            sector_name=sector.sector_name,
            fetched=len(raw_rows),
            upserted=upserted,
        )


@dataclass(frozen=True, slots=True)
class SectorOhlcvIngestOutcome:
    inds_cd: str
    sector_name: str | None = None
    fetched: int = 0
    upserted: int = 0
    skipped: bool = False
    reason: str | None = None
    error: str | None = None
```

### 6.4 Bulk — `IngestSectorDailyBulkUseCase`

```python
class IngestSectorDailyBulkUseCase:
    """모든 active 업종의 일봉 일괄 적재.

    동시성: RPS 4 + 250ms.
    소요: 50~80 업종 × 0.25s = 12~20초 (이론).
      실측 추정 1~5분 (페이지네이션 + 응답 시간).

    — ka10081 의 4500 호출 vs 본 endpoint 50~80 호출. 부담 작음.
    """

    BATCH_SIZE = 20

    def __init__(
        self,
        session: AsyncSession,
        *,
        single_use_case: IngestSectorDailyUseCase,
    ) -> None:
        self._session = session
        self._single = single_use_case
        self._sector_repo = SectorRepository(session)

    async def execute(
        self,
        *,
        base_date: date,
        only_market_codes: Sequence[str] | None = None,
    ) -> SectorOhlcvBulkResult:
        sectors = await self._sector_repo.list_all_active(
            only_market_codes=only_market_codes,
        )

        outcomes: list[SectorOhlcvIngestOutcome] = []
        for i, sector in enumerate(sectors, start=1):
            try:
                async with self._session.begin_nested():
                    o = await self._single.execute(
                        sector.sector_code, base_date=base_date,
                    )
                    outcomes.append(o)
            except Exception as exc:
                logger.warning(
                    "sector ingest 실패 inds_cd=%s: %s", sector.sector_code, exc,
                )
                outcomes.append(SectorOhlcvIngestOutcome(
                    inds_cd=sector.sector_code,
                    sector_name=sector.sector_name,
                    error=f"{type(exc).__name__}: {exc}",
                ))

            if i % self.BATCH_SIZE == 0:
                await self._session.commit()

        await self._session.commit()
        return SectorOhlcvBulkResult(
            base_date=base_date,
            total_sectors=len(sectors),
            outcomes=outcomes,
        )


@dataclass(frozen=True, slots=True)
class SectorOhlcvBulkResult:
    base_date: date
    total_sectors: int
    outcomes: list[SectorOhlcvIngestOutcome]

    @property
    def total_rows_inserted(self) -> int:
        return sum(o.upserted for o in self.outcomes)

    @property
    def success_count(self) -> int:
        return sum(1 for o in self.outcomes if o.upserted > 0)
```

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **수동 단건** | on-demand | `POST /api/kiwoom/sectors/{inds_cd}/daily?date=YYYYMMDD` (admin) |
| **수동 일괄** | on-demand | `POST /api/kiwoom/sectors/daily/sync?date=YYYYMMDD` (admin) |
| **일 1회 cron** | KST 19:15 평일 | ka10081 (18:30) → ka10086 (19:00) → 본 endpoint (19:15) → ka10080 분봉 (19:30) |
| **백필** | on-demand | `python scripts/backfill_sector.py --start 2023-01-01 --end 2026-05-07` |

### 7.1 라우터

```python
# app/adapter/web/routers/sector_ohlcv.py
router = APIRouter(prefix="/api/kiwoom/sectors", tags=["kiwoom-sector"])


@router.post(
    "/{inds_cd}/daily",
    response_model=SectorOhlcvIngestOutcomeOut,
    dependencies=[Depends(require_admin_key)],
)
async def ingest_one_sector_daily(
    inds_cd: str,
    base_date: date = Query(default_factory=lambda: date.today()),
    use_case: IngestSectorDailyUseCase = Depends(get_ingest_sector_daily_use_case),
) -> SectorOhlcvIngestOutcomeOut:
    outcome = await use_case.execute(inds_cd, base_date=base_date)
    return SectorOhlcvIngestOutcomeOut.model_validate(asdict(outcome))


@router.post(
    "/daily/sync",
    response_model=SectorOhlcvBulkResultOut,
    dependencies=[Depends(require_admin_key)],
)
async def sync_sector_daily_bulk(
    body: SectorOhlcvBulkRequestIn = Body(default_factory=SectorOhlcvBulkRequestIn),
    use_case: IngestSectorDailyBulkUseCase = Depends(get_ingest_sector_daily_bulk_use_case),
) -> SectorOhlcvBulkResultOut:
    result = await use_case.execute(
        base_date=body.base_date or date.today(),
        only_market_codes=body.only_market_codes or None,
    )
    return SectorOhlcvBulkResultOut.model_validate(asdict(result))


@router.get(
    "/{inds_cd}/daily",
    response_model=list[SectorPriceDailyOut],
)
async def get_sector_daily_range(
    inds_cd: str,
    start_date: date = Query(...),
    end_date: date = Query(...),
    session: AsyncSession = Depends(get_session),
) -> list[SectorPriceDailyOut]:
    """백테스팅 엔진의 read API."""
    sector_repo = SectorRepository(session)
    sector = await sector_repo.find_by_code(inds_cd)
    if sector is None:
        raise HTTPException(status_code=404, detail=f"sector not found: {inds_cd}")
    repo = SectorPriceDailyRepository(session)
    rows = await repo.get_range(
        sector.id, start_date=start_date, end_date=end_date,
    )
    return [SectorPriceDailyOut.model_validate(r) for r in rows]
```

### 7.2 APScheduler Job

```python
# app/batch/sector_ohlcv_job.py
async def fire_sector_daily_sync() -> None:
    """매 평일 19:15 KST — 업종 일봉 적재.

    cron 시간 분리:
      18:30 — ka10081 (종목 일봉)
      19:00 — ka10086 (종목 일별 + 투자자별)
      19:15 — ka20006 (업종 일봉)  ← 본 job
      19:30 — ka10080 (종목 분봉)
    """
    today = date.today()
    if not is_trading_day(today):
        return
    try:
        async with get_sessionmaker()() as session:
            kiwoom_client = build_kiwoom_client_for("prod-main")
            chart = KiwoomChartClient(kiwoom_client)
            single = IngestSectorDailyUseCase(session, chart_client=chart)
            bulk = IngestSectorDailyBulkUseCase(session, single_use_case=single)
            result = await bulk.execute(base_date=today)
        logger.info(
            "sector daily sync 완료 base_date=%s total=%d success=%d rows=%d",
            today, result.total_sectors, result.success_count, result.total_rows_inserted,
        )
    except Exception:
        logger.exception("sector daily sync 콜백 예외")


scheduler.add_job(
    fire_sector_daily_sync,
    CronTrigger(day_of_week="mon-fri", hour=19, minute=15, timezone=KST),
    id="sector_daily_sync",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
    misfire_grace_time=60 * 30,    # 30분 grace (호출 부담 작음)
)
```

### 7.3 RPS / 시간 추정

| 항목 | 값 |
|------|----|
| active 업종 수 | ~50~80 (운영 검증) |
| 호출당 인터벌 | 250ms |
| 동시성 | 4 |
| 1회 sync 호출 수 | 50~80 |
| 페이지네이션 평균 | 1 (ka10081 가정 동일) |
| 이론 시간 | 80 / 4 × 0.25 = 5초 |
| 실측 추정 | 1~5분 |

→ cron 19:15 + 30분 grace.

---

## 8. 에러 처리

| HTTP / 응답 | 도메인 예외 | 라우터 매핑 | UseCase 정책 |
|-------------|-------------|-------------|--------------|
| 400 (잘못된 inds_cd) | `ValueError` | 400 | 호출 전 차단 |
| 401 / 403 | `KiwoomCredentialRejectedError` | 400 | bubble up |
| 429 | `KiwoomRateLimitedError` | 503 | 재시도 후 다음 업종 |
| 5xx, 네트워크 | `KiwoomUpstreamError` | 502 | 다음 업종 |
| `return_code != 0` | `KiwoomBusinessError` | 400 | outcome.error 노출, 다음 업종 |
| sector 마스터 미존재 | (skip) | — | outcome.skipped=true, reason="sector_not_found" |
| sector 비활성 (is_active=false) | (skip) | — | outcome.skipped=true, reason="sector_inactive" |
| 응답 `dt=""` | (적재 skip) | — | upsert_many 자동 제외 |
| 빈 응답 `list=[]` | (정상) | — | upserted=0 |
| FK 위반 (sector_id 없음) | `IntegrityError` | 502 | UseCase 가 sector 조회 선행 |

### 8.1 partial 실패 알람

50~80 업종 × 1 호출 = 50~80 호출 중:
- < 1%: 정상
- 1~5%: warning
- > 5%: error + alert (호출 수 작아 1 건만 실패해도 1.25%~2%)

### 8.2 같은 호출 두 번 (멱등성)

UNIQUE (sector_id, trading_date) ON CONFLICT UPDATE — 마지막 값 갱신.

---

## 9. 테스트

### 9.1 Unit (MockTransport)

`tests/adapter/kiwoom/test_chart_sector.py`:

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 단일 페이지 | 200 + list 60건 + cont-yn=N | 60건 반환 |
| 페이지네이션 | 첫 cont-yn=Y, 둘째 N | 합쳐 N건 |
| 빈 list | 200 + `inds_dt_pole_qry=[]` | 빈 list |
| `return_code=1` | 비즈니스 에러 | `KiwoomBusinessError` |
| 401 | 자격증명 거부 | `KiwoomCredentialRejectedError` |
| inds_cd "01" | 호출 차단 | `ValueError` |
| inds_cd "1234" | 호출 차단 | `ValueError` |
| inds_cd "abc" | 호출 차단 | `ValueError` |
| base_date 포함 | `date(2026, 5, 7)` | request body `base_dt="20260507"` |
| `dt=""` row | 빈 dt 1건 + 정상 4건 | repo 가 자동 skip |
| 100배 값 그대로 | cur_prc="252127" | NormalizedSectorDailyOhlcv.close_index_centi=252127 |
| close_index property | close_index_centi=252127 | close_index = Decimal("2521.27") |
| 페이지네이션 폭주 | cont-yn=Y 무한 | `max_pages=10` 도달 → `KiwoomPaginationLimitError` |

### 9.2 Integration (testcontainers)

`tests/application/test_sector_ohlcv_service.py`:

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| INSERT (DB 빈 상태) | sector 1건 (inds_cd=001) + 응답 60 row | sector_price_daily 60 row INSERT |
| UPDATE (멱등성) | 같은 호출 두 번 | row 60개 유지, updated_at 갱신 |
| sector 미존재 | DB 에 inds_cd 없음 | outcome.skipped=true, reason="sector_not_found" |
| sector 비활성 | is_active=false | outcome.skipped=true, reason="sector_inactive" |
| sector 마스터 매핑 | inds_cd="001" → sector.sector_code=001 → sector_id 매핑 | INSERT 정상 |
| Bulk 50 sector | 50 active sectors | 50건 처리, 일부 페이지네이션 |
| only_market_codes 필터 | KOSPI 시장 만 | KOSDAQ sector skip |
| 빈 응답 처리 | 응답 list=[] | upserted=0 |
| 100배 값 INSERT | cur_prc="252127" | close_index_centi=252127 (그대로) |
| read 시 100배 변환 | repo.get_range 후 close_index 호출 | Decimal("2521.27") |

### 9.3 E2E (요청 시 1회)

```python
@pytest.mark.requires_kiwoom_real
async def test_real_ka20006():
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

        # KOSPI 종합 일봉
        rows = await chart.fetch_sector_daily("001", base_date=date.today())
        assert len(rows) >= 60

        latest = rows[0]
        assert latest.dt
        # 100배 값 가정 검증 — KOSPI 종합 = ~2500 정도라 응답은 250000 부근
        close = _to_int(latest.cur_prc)
        assert 100_000 <= close <= 1_000_000   # 1000~10000 KOSPI 범위 × 100

        # KOSPI200 (inds_cd=201)
        kospi200 = await chart.fetch_sector_daily("201", base_date=date.today())
        assert len(kospi200) >= 60
    finally:
        async with KiwoomAuthClient(base_url="https://api.kiwoom.com") as auth:
            await auth.revoke_token(creds, token.token)
```

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `app/adapter/out/kiwoom/chart.py` (또는 `sect.py`) — `KiwoomChartClient.fetch_sector_daily`
- [ ] `app/adapter/out/kiwoom/_records.py` — `SectorChartRow`, `SectorChartResponse`, `NormalizedSectorDailyOhlcv`
- [ ] `app/adapter/out/persistence/models/sector_price_daily.py` — `SectorPriceDaily`
- [ ] `app/adapter/out/persistence/repositories/sector_price.py` — `SectorPriceDailyRepository`
- [ ] `app/application/service/sector_ohlcv_service.py` — `IngestSectorDailyUseCase`, `IngestSectorDailyBulkUseCase`
- [ ] `app/adapter/web/routers/sector_ohlcv.py` — POST/GET endpoints
- [ ] `app/batch/sector_ohlcv_job.py` — APScheduler 등록 (KST mon-fri 19:15)
- [ ] `migrations/versions/008_sector_price_daily.py` — `sector_price_daily` 테이블
- [ ] `scripts/backfill_sector.py` — CLI

### 10.2 테스트

- [ ] Unit 13 시나리오 (§9.1) PASS
- [ ] Integration 10 시나리오 (§9.2) PASS
- [ ] coverage `KiwoomChartClient.fetch_sector_daily`, `IngestSectorDailyUseCase`, `SectorPriceDailyRepository` ≥ 80%

### 10.3 운영 검증

- [ ] **100배 값 가정 실증** — KOSPI 종합 응답값 / 100 ≈ 실제 KOSPI 지수와 일치하는지
- [ ] `inds_cd` 응답 length 가 20 으로 명시됨에도 실제는 3~4 자리만 오는지
- [ ] `dt` 정렬 (Excel 예시는 DESC — ka10081 와 동일 가정)
- [ ] `trde_prica` 단위 (백만원 추정 — ka10081 와 동일 운영 검증)
- [ ] 1 페이지 응답 row 수 (ka10081 와 동일 ~600 거래일 추정)
- [ ] 페이지네이션 발생 빈도 (3년 백필 시)
- [ ] **ka10101 의 sector_code 가 (market_code 무관) unique 한가** — `(market_code, sector_code)` UNIQUE 인지 `sector_code` 만 UNIQUE 인지. 잘못 매핑하면 KOSPI 와 KOSDAQ 의 같은 sector_code 가 충돌
- [ ] active 업종 50~80개 sync 실측 시간
- [ ] NXT 거래소 별도 지수 응답 가능 여부 (NXT 100 등)
- [ ] **수정주가 개념** — 본 endpoint 는 `upd_stkpc_tp` 없는데 지수가 자체 보정되는지

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka20006 sector daily ingest (KOSPI/KOSDAQ/sector indices)`
- [ ] `master.md` § 12 결정 기록에:
  - 100배 값 저장 형식 (centi BIGINT vs NUMERIC)
  - `inds_cd` 응답 length 실측
  - `(market_code, sector_code)` UNIQUE vs `sector_code` 만 UNIQUE
  - active 업종 수 + sync 실측 시간

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | 100배 값 저장 형식 | (a) **centi BIGINT (현재)** + read property 변환 / (b) NUMERIC(12,2) 응답 / 100 변환 후 저장 | Phase D 코드화 직전 |
| 2 | sector 마스터 매핑 | sector_code 만 / (market_code, sector_code) 페어 | ka10101 운영 검증 후 |
| 3 | 마이그레이션 분리 | Migration 002 (sector 와 함께) / **008 (Phase D 단독)** | Phase D 코드화 |
| 4 | NXT 지수 처리 | KRX 지수만 / NXT 별도 지수 (운영 검증 후) | 운영 검증 후 |
| 5 | cron 시간 | 19:15 (제안) / 18:45 (이른 시간) | Phase D 후반 |
| 6 | 백필 윈도 | 3년 (ka10081 와 동일) / 1년 (필요한 만큼) | Phase H 백테스팅 정책 |
| 7 | active 업종 결정 | ka10101 의 is_active=true 만 / 본 endpoint 의 첫 호출 응답 기반 | Phase D 코드화 |

### 11.2 알려진 위험

- **100배 값 가정의 정확성** — Excel 명세의 "지수 값은 소수점 제거 후 100배 값으로 반환" 이 모든 지수에 적용되는지. KOSPI200 (응답값이 ~50000 → 실제 500.00) / KRX100 / KOSDAQ150 등 모든 지수를 운영 검증. 잘못 적용하면 백테스팅의 시장 비교가 100배 어긋남
- **`cur_prc` "현재가" 의 의미** — 일봉 응답에서는 "그 일자 종가" 로 해석. ka10081 와 동일 — 컬럼명 `close_index_centi` 로 명확화
- **`dt` 정렬 미확정** — Excel 예시는 DESC. ka10081 와 동일 가정. 백테스팅 엔진은 ASC 가정 — 정규화 후 ORDER BY 강제
- **`inds_cd` length 응답이 20** — Excel 명세 R29 에 응답 length=20 으로 표기. 실제는 3~4 자리만 올 가능성 (요청 length=3). 운영 검증 후 String(10) 컬럼으로 충분한지 확인
- **sector 마스터 매핑 모호** — ka10101 의 (market_code, sector_code) UNIQUE 라면 같은 sector_code 가 시장별로 중복 가능. 본 endpoint 의 `inds_cd` 만으로 어느 sector 인지 결정 불가 → Sector 테이블의 UNIQUE 정책 변경 또는 별도 매핑 테이블 필요
- **수정주가 개념 부재** — 본 endpoint 는 `upd_stkpc_tp` 없음. 지수가 액면분할에 자동 보정되는지 (KOSPI 같은 시가총액 가중 지수는 자동 보정), 또는 보정이 미적용되는지 운영 검증
- **`pred_pre`/`pred_pre_sig`/`trde_tern_rt` 필드 없음** — ka10081 일봉에 비해 응답 정보 부족. 백테스팅의 derived feature 로 자체 계산 (close_t / close_t-1 - 1)
- **NXT 지수의 별도 산출 가능성** — NXT 거래소가 자체 지수 (NXT 100 등) 산출 시 본 endpoint 에서 응답되는지 ka10101 응답 확인 후 결정. 응답되지 않으면 NXT 시장 분석은 종목 단위만 가능
- **국제 지수 (NASDAQ / S&P500) 와의 매핑** — 본 endpoint 는 한국 내 지수만. 글로벌 비교는 별도 source 필요 — Phase 외
- **거래대금 (`trde_prica`) 단위** — ka10081 와 동일 백만원 가정. 운영 검증 후 master.md § 12 에 한 번만 기록 (다른 chart endpoint 들도 같은 단위 가정)

### 11.3 ka20006 vs ka10081 비교

| 항목 | ka10081 종목 일봉 | ka20006 업종 일봉 |
|------|-----------|------------------|
| URL | /api/dostk/chart | 동일 |
| Body 키 (식별자) | `stk_cd` (6~20자리) | `inds_cd` (3자리) |
| upd_stkpc_tp | 있음 | **없음** (지수 자체 보정) |
| 응답 list 키 | `stk_dt_pole_chart_qry` | `inds_dt_pole_qry` |
| 응답 필드 수 | 10 | **7** (pred_pre/pred_pre_sig/trde_tern_rt 없음) |
| 가격 단위 | KRW (정수) | **지수 × 100** (centi) |
| KRX/NXT 분리 | Yes | **No** (지수는 거래소 통합) |
| 영속화 테이블 | stock_price_krx/nxt | sector_price_daily |
| FK 대상 | stock | sector (ka10101) |
| 1회 sync 호출 수 | 4500 | **50~80** |
| sync 시간 추정 | 30~60분 | **1~5분** |
| 백테스팅 우선순위 | P0 | P2 |
| 마이그레이션 | 003/004 | 008 |

→ ka10081 의 70% 패턴 복제 + 지수 단위 변환 + sector FK + NXT 미지원으로 단순화. 본 계획서가 다른 chart endpoint 보다 짧은 이유.

### 11.4 ka20006 vs ka10101 의 매핑

```python
# Phase D 코드화 시점의 매핑 흐름
async def sync_all_sector_ohlcv(session: AsyncSession, base_date: date) -> None:
    sector_repo = SectorRepository(session)
    sectors = await sector_repo.list_all_active()
    # → ka10101 응답에서 채워진 sector 마스터

    for sector in sectors:
        # sector.sector_code = "001" / "002" / "101" / "201" / "302" / "701" / ...
        # → ka20006 의 inds_cd 와 직접 호환
        await ingest_use_case.execute(
            inds_cd=sector.sector_code,
            base_date=base_date,
        )
```

→ **본 endpoint 의 의존성**: ka10101 sync 가 선행되어 sector 마스터에 active row 가 존재해야 함. ka10101 은 Phase A (P1), 본 endpoint 는 Phase D (P2) — 시점 차이로 자연 보장. Phase D 코드화 전에 ka10101 의 운영 검증 (DoD § 10.3) 완료 권장.

### 11.5 향후 확장

- **백테스팅의 베타 계산**: 종목 일봉 vs `sector_price_daily` 의 일별 수익률 회귀 — derived feature
- **섹터 회전 시그널**: 업종별 N일 수익률 랭킹의 변화 패턴
- **시장 redirect 시그널**: KOSPI200 vs KRX100 의 발산 (large-cap vs broad market)
- **업종 주봉/월봉**: ka10081 의 ka10082~94 처럼 업종 주봉 (`ka20007`?) / 월봉 (`ka20008`?) 등 — 키움 카탈로그 추가 조사 필요
- **글로벌 지수**: NASDAQ / S&P500 별도 source — 본 endpoint 범위 외
- **업종 ↔ 종목 cross-reference**: stock.sector_id FK 가 있으면 자연스러운 join 쿼리 — Phase B 의 stock 마스터 보강 단계에서 수행

---

_Phase D 의 세 번째이자 마지막 endpoint. 가장 가벼운 호출 부담 + 가장 단순한 로직. 단, 100배 값 / sector 매핑 / NXT 지수 처리 의 세 결정이 본 endpoint 의 운영 검증 1순위. 백테스팅 엔진의 시장 비교 / 베타 계산 / 섹터 회전 시그널의 입력._

---

## 12. Phase D-1 — Migration 015 + ka20006 인프라 + 자동화 (통합 chunk)

> **추가일**: 2026-05-12 (Docker 배포 § 38 / secret 회전 가이드 § 39-prep 직후, Phase D 진입 chunk)
> **선행 조건**: Phase C 종결 (C-4 `00ac3b0` + Docker 배포 `550bee5`) + ka10101 sector 마스터 운영 (A-3α/β `cce855c`/`6cd4371`)
> **분류**: feat (신규 endpoint 도입 + Migration 1 + 응답 DTO 신규). 신규 도메인 (sector daily) — KRX only, NXT skip
> **scheduler_enabled 상태**: 사용자 결정으로 활성 보류 — Scheduler job 등록 코드만, 실 가동은 모든 작업 완료 후 일괄 활성

### 12.1 배경 (Phase D 진입)

11 endpoint (au 2 + ka 9) 완료 후 Phase C 데이터 측면 종결 + § 38 Docker 컨테이너 배포로 운영 인프라 안착. Phase D 의 3 endpoint 중 사용자 결정 (2026-05-12):

- **ka10080 분봉 (D-2)**: 데이터량 많음 (1100종목 × 380분 = 38만+ rows/일) → **마지막 endpoint 로 연기**. 대용량 파티션 결정 동반 필요
- **ka20006 업종일봉 (D-1)**: 가장 가벼움 (50~80 sector × 1 = 50~80 rows/일) → **본 chunk 가 Phase D 첫 진입**

ka10081/82/83/94 (4 chart endpoint) 패턴 + ka10101 sector 마스터 매핑이 모두 확립된 상태 → Phase C 기반의 패턴 복제 + 응답 7 필드 (10 → 7) + sector_id FK + NXT skip 만 핵심 차이.

### 12.2 결정 (ADR-0001 § 39 신규 예정)

| # | 사안 | 결정 | 근거 |
|---|------|------|------|
| 1 | 마이그레이션 번호 | **015** (014 yearly 직후). revision id = `015_sector_price_daily` (22 chars — VARCHAR(32) 안전) | 014 마지막 + naming 일관 |
| 2 | sector 매핑 정책 | **`sector_id` FK** (sector.id) — § 11.1 #2 옵션의 발전형. 운영 검증 결과 sector UNIQUE = `(market_code, sector_code)` 페어 → `inds_cd` (sector_code) 단독으론 매핑 불가 | sector.py L31 `uq_sector_market_code (market_code, sector_code)` |
| 3 | 100배 값 저장 형식 | **centi BIGINT** (`open_index_centi` / `high_index_centi` / `low_index_centi` / `close_index_centi`) + read property (`.close_index = close_index_centi / 100`) | § 11.1 #1 옵션 (a). KRX 정수 단위와 일관 (`stock_price_krx` 의 BIGINT 패턴) |
| 4 | NXT 호출 정책 | **skip** (KRX only) — UseCase 에서 `SectorIngestOutcome(skipped=True, reason="nxt_sector_not_supported")` 반환. NXT 별도 지수 산출 여부 미확정 + Excel 명세 R10 "모의투자 KRX 만" | § 11.1 #4 옵션 (a) — 운영 검증 후 재검토 |
| 5 | sector 마스터 ka10101 응답에 본 endpoint 호출 대상 sector 가 부재한 경우 | UseCase 에서 `SectorIngestOutcome(skipped=True, reason="sector_master_missing")` 반환 + 경고 로그. gap-filler 호출 안 함 (ka10100 같은 종목 단위 패턴 미적용 — sector 는 마스터 sync 가 선행) | sync 흐름 자연 보장 (cron 시각 19:15 vs ka10101 sync 18:00 권장) |
| 6 | 응답 7 필드 처리 | `NormalizedSectorDailyOhlcv` 의 `prev_compare_amount` / `prev_compare_sign` / `turnover_rate` 는 None 영속화 — DB NULL. ka10094 mixin 재사용 가능성 검토 (None 필드 다수 patterns) | § 11.1 mixin 후보 |
| 7 | cron 시간 | **mon-fri 07:00 KST** (§ 35 cron shift to morning 정책 일관) — ohlcv_daily 06:00 + daily_flow 06:30 의 직후. plan doc § 11.1 #5 의 19:15 안은 § 35 정책과 충돌하므로 본 chunk 에서 변경 | § 35 (2026-05-12) NXT 마감 후 새벽 cron 일관 |
| 8 | 백필 윈도 | **3년** (ka10081 패턴) — `scripts/backfill_sector.py` CLI 신규. 본 chunk 에서는 코드만, 실 백필은 별도 운영 chunk | § 11.1 #6 옵션 (a) |
| 9 | `inds_cd` UseCase 입력 | **`Sector.id` (PK) → repository 가 sector_code lookup** — UseCase 는 sector_id 만 받고 client 호출 직전에 sector_code 추출. base_date 와 함께 `IngestSectorDailyInput` DTO | sector_id 가 primary 식별자 (sector_code 단독은 충돌 가능) |

### 12.3 영향 범위 (10 코드 + 6 테스트)

**코드 (10 files)**:

| # | 파일 | 변경 |
|---|------|------|
| 1 | `migrations/versions/015_sector_price_daily.py` (신규) | `sector_price_daily` 테이블 신규. FK = `sector_id INTEGER REFERENCES kiwoom.sector(id)`. UNIQUE `(sector_id, trading_date)`. DDL 패턴 = 011 (월봉) 응용 |
| 2 | `app/adapter/out/persistence/models/sector_price_daily.py` (신규) | ORM (sector_id FK + 4 centi BIGINT + volume BIGINT + trade_amount BIGINT + created_at/updated_at) |
| 3 | `app/adapter/out/persistence/models/__init__.py` | export 추가 |
| 4 | `app/adapter/out/kiwoom/chart.py` 또는 `sect.py` 분리 (결정 chunk 진입 시) | `KiwoomChartClient.fetch_sector_daily(inds_cd, base_date)` 신규 + 빈 응답 sentinel break (C-flow-empty-fix 1:1) |
| 5 | `app/adapter/out/kiwoom/_records.py` | `SectorChartRow` / `SectorChartResponse` Pydantic 7 필드 신규 (extra="ignore") + `NormalizedSectorDailyOhlcv` |
| 6 | `app/adapter/out/persistence/repositories/sector_price.py` (신규) | `SectorPriceDailyRepository.upsert_many(sector_id, rows)` |
| 7 | `app/application/service/sector_ohlcv_service.py` (신규) | `IngestSectorDailyUseCase` + `IngestSectorDailyBulkUseCase` (active sector 전체 sync) + NXT skip 가드 + sector_master_missing 가드 |
| 8 | `app/adapter/web/routers/sector_ohlcv.py` (신규) | `POST /api/kiwoom/sectors/{id}/ohlcv/daily/refresh` + `POST /api/kiwoom/sectors/ohlcv/daily/sync` (전체) + admin API key 보호 |
| 9 | `app/scheduler.py` | `sector_daily_sync_daily` job 신규 (CronTrigger day_of_week=mon-fri hour=7 minute=0 KST). settings + lifespan alias 등록 |
| 10 | `app/config/settings.py` | `scheduler_sector_daily_sync_alias` 추가 (B/C/D 일관 fail-fast) |

**테스트 (4 신규 + 2 갱신)**:

| # | 파일 | 변경 |
|---|------|------|
| 1 | `tests/test_migration_015.py` (신규) | 014 패턴 1:1 — sector_price_daily 테이블 생성 / 컬럼 타입 / FK / UNIQUE / 인덱스 검증 |
| 2 | `tests/test_kiwoom_chart_client.py` 또는 `test_kiwoom_sect_client.py` (신규) | `fetch_sector_daily` 시나리오 — mock 응답 60 row 단일 페이지 / 페이지네이션 / 빈 응답 break / 7 필드 normalize / 자격증명 / 5xx |
| 3 | `tests/test_sector_ohlcv_service.py` (신규) | UseCase — sector_id lookup + KRX only / sector_master_missing skip / 정상 upsert / cont-yn 페이지네이션 / 100배 값 정규화 |
| 4 | `tests/test_sector_price_repository.py` (신규) | upsert idempotent / 동일 키 갱신 / FK constraint / UNIQUE 충돌 |
| 5 | `tests/test_sector_ohlcv_router.py` (신규) | sync 전체 + refresh 단건 + admin API key 검증 |
| 6 | `tests/test_scheduler_sector_daily.py` 또는 통합 | sector_daily job 등록 / CronTrigger mon-fri 07:00 KST / alias fail-fast |

**Pydantic + Settings (보조)**:
- `app/application/dto/sector_ohlcv.py` (신규) — `IngestSectorDailyInput` / `SectorIngestOutcome`

**문서**:
- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 39 신규 (D-1 결과)
- `CHANGELOG.md` / `STATUS.md` § 0/§ 1/§ 2/§ 5/§ 6 / `HANDOFF.md` / 본 doc § 12 (자기 참조)

### 12.4 적대적 이중 리뷰 — 사전 self-check (ted-run 진입 전)

| # | 위험 | 완화 |
|---|------|------|
| H-1 | sector 매핑 — `(market_code, sector_code)` UNIQUE 라 `inds_cd` 단독 lookup 불가 (§ 11.1 #2) | UseCase 가 sector_id (PK) 만 입력. ka10101 운영 검증 결과 sector_code 가 시장 간 중복 가능 (예: KOSPI 종합=001, KOSDAQ 종합=101 — 다름이지만 미래 발견 가능) → sector_id 가 안전 |
| H-2 | 100배 값 가정 운영 검증 미완 (§ 11.2) — KOSPI ~50000 / 100 → ~500 실제 일치 여부 | mock 테스트는 가정 그대로 검증. 운영 첫 호출 응답을 ADR § 39 운영 결과에 기록. 잘못 적용 시 centi → NUMERIC 마이그레이션 별도 (회복 가능) |
| H-3 | 응답 list key `inds_dt_pole_qry` 운영 검증 미완 (§ 11.2) | mock 테스트로 parser 검증. 운영 첫 호출 시 ka10081 `stk_dt_pole_chart_qry` / ka10082 `stk_stk_pole_chart_qry` / ka10083 `stk_mth_pole_chart_qry` / ka10094 `stk_yr_pole_chart_qry` 일관성으로 신뢰성 확보. 다르면 `extra="ignore"` 가 safe |
| H-4 | upd_stkpc_tp 없음 — 지수 자체 보정 가정 (§ 11.2) | 지수는 시가총액 가중이므로 액면분할에 자동 보정 (KOSPI200 표준). 단, 응답에 보정 전 raw 가 있을 가능성 운영 검증. ADR § 39 운영 결과에 기록 |
| H-5 | cron 07:00 KST mon-fri — 06:00 ohlcv_daily + 06:30 daily_flow 와 KRX rate limit (2초/호출) 경합 | sector 50~80 호출 × 2초 = 100~160초 = 1.7~2.7분. 06:30 daily_flow 의 sync 시간 (예: 4000+ stocks × 2초 ≈ 2~3시간) 와 겹칠 가능성 높음. **결정 #7 재검토 필요** — 옵션: (a) cron 늦춤 (예: 10:00) (b) Lock 직렬화 신뢰 (현재 KRX rate limit 이미 직렬화) (c) 별도 KRX 클라이언트 인스턴스. 본 chunk 에서는 (b) 채택 — 기존 lock 으로 안전 |
| H-6 | sector_master_missing 가드 — ka10101 sync 가 선행되지 않은 환경 | bulk UseCase 에서 `active=true` sector 만 iterate → 빈 리스트면 즉시 종료. 단건 UseCase 에서 `sector_id` 조회 결과 없으면 skip 반환. cron 직전 ka10101 자동 sync 안 함 (sector 마스터 안정성 가정) |
| H-7 | NXT skip 정책 정확성 (§ 11.2) — NXT 거래소가 자체 지수 산출 시점 발생 가능성 | 본 chunk 는 sector_price_daily 단일 테이블 (KRX only). NXT 지수 도입 시 별도 chunk (sector_price_nxt 또는 nxt_sector 별도 마스터) — 본 chunk 의 데이터 모델은 그 가능성 차단하지 않음 |
| H-8 | 1 페이지 응답 row 수 unknown (§ 11.2 추정 600 거래일) | 페이지네이션 코드는 항상 cont-yn 체크. mock 테스트로 단일 / 다중 페이지 + 빈 응답 break 시나리오 둘 다 검증. 운영 첫 호출 응답을 ADR § 39 에 기록 |
| H-9 | `inds_cd` 응답 length 20 vs 요청 3 (Excel 명세 vs 실제) | Pydantic `SectorChartRow.inds_cd: str` length 미제약. 응답 길이 확장 가능성 흡수. UseCase 에서 sector_code 와 직접 매칭 (응답 inds_cd 검증은 보조 sanity check 만) |
| H-10 | 거래대금 `trde_prica` 단위 (§ 11.2 추정 백만원) | ka10081 / 82 / 83 / 94 의 운영 검증 결과 백만원 확정 시점에 ADR 공통 § 으로 기록 권고. 본 chunk 에서는 BIGINT 단위 추정 그대로 + 운영 검증 후 단위 정정 마이그레이션 (필요 시) |
| H-11 | scheduler_enabled 활성 보류 정책 (§ 36) — 본 chunk 에 신규 cron job 등록 시 일관성 | sector_daily job 도 § 36 정책 따라 등록만 + 실 발화는 일괄 활성 chunk 까지 대기 (현재 8 scheduler 활성 상태이므로 9 scheduler 로 증가). 단, 컨테이너 재기동 시 자동 발화될 수 있음 — `SCHEDULER_SECTOR_DAILY_SYNC_ENABLED=false` env override 로 보호 가능 |
| H-12 | Migration 015 destructive 가능성 | 신규 테이블 + FK 만 — 비파괴. entrypoint 자동 마이그레이션 (§ 38.8 #2) 정책 그대로 안전 |
| H-13 | sect.py 분리 vs chart.py 통합 | `KiwoomChartClient` 가 종목 / 지수 둘 다 책임지면 SRP 위반 경계. 그러나 모두 `/api/dostk/chart` 동일 URL — Hexagonal "adapter" 단일성 유지. **결정**: chart.py 통합 + 메서드 명 prefix (`fetch_stock_daily` / `fetch_sector_daily`) 로 구분. sect.py 분리는 본 chunk 외 |

### 12.5 DoD (D-1)

**코드**:
- [ ] Migration 015 (sector_price_daily 단일 테이블)
- [ ] ORM 1 (SectorPriceDaily)
- [ ] Pydantic 3 (SectorChartRow / SectorChartResponse 7 필드 / NormalizedSectorDailyOhlcv)
- [ ] DTO 2 (IngestSectorDailyInput / SectorIngestOutcome)
- [ ] `KiwoomChartClient.fetch_sector_daily` + sentinel break
- [ ] Repository (SectorPriceDailyRepository.upsert_many)
- [ ] UseCase 2 (Single + Bulk + NXT skip + sector_master_missing 가드)
- [ ] Router 2 path (refresh 단건 / sync 전체) + admin API key 보호
- [ ] Scheduler sector_daily_sync_daily job 등록 (mon-fri KST 07:00, scheduler_enabled 정책 적용)
- [ ] Settings + lifespan alias

**테스트** (목표: 1059 → ~1090~1110 cases / coverage 유지 ≥ 91%):
- [ ] `test_migration_015.py` 신규
- [ ] `test_kiwoom_chart_client.py` (또는 sect_client) sector daily 시나리오 추가
- [ ] `test_sector_ohlcv_service.py` 신규
- [ ] `test_sector_price_repository.py` 신규
- [ ] `test_sector_ohlcv_router.py` 신규
- [ ] `test_scheduler_sector_daily.py` (또는 통합)
- [ ] `ruff check` + `mypy --strict` PASS

**이중 리뷰**:
- [ ] 1R PASS (Reviewer: 스키마/마이그레이션 + UseCase sector_id lookup 정확성 + cron 시간 결정 #7 재검증)

**문서**:
- [ ] ADR-0001 § 39 추가 (D-1 결과 + H-1~H-13 self-check 반영)
- [ ] STATUS.md § 0 / § 1 / § 2.1 / § 5 / § 6 갱신 (Phase D 진입 + ka20006 → 완료 + 12/25 endpoint)
- [ ] CHANGELOG: `feat(kiwoom): Phase D-1 — ka20006 sector daily OHLCV (Migration 015, KRX only, NXT skip, 12/25 endpoint)`
- [ ] HANDOFF.md 갱신
- [ ] master.md § 의 ka20006 row 갱신 (chunk 명 / 커밋 해시)

### 12.6 다음 chunk (D-1 이후)

1. **(5-13 06:30 KST 이후) cron 첫 발화 검증** — § 38 다음 chunk (OhlcvDaily 06:00 + DailyFlow 06:30 적재)
2. **(D-1 종결 + ka20006 운영 첫 호출 후) ADR § 39 운영 결과 채움** — 100배 값 / inds_dt_pole_qry list key / page row 수 / inds_cd length 등 § 11.2 운영 검증 항목
3. **Phase D-2 진입 — ka10080 분봉** (사용자 결정: 마지막 endpoint). 대용량 파티션 결정 chunk 선행 (월/분기 파티션 vs 단일 테이블 vs 별도 스키마)
4. **Phase E** — ka10014 (공매도) / ka10068 (대차) / ka20068 (대차 종목별) 신규 wave
5. **(5-19 이후) § 36.5 1주 모니터 측정 채움** — 현재 8 + sector_daily 1 = 9 scheduler 운영
6. **(전체 개발 종결 후) secret 회전** — `docs/ops/secret-rotation-2026-05-12.md` 절차서

### 12.7 운영 모니터 (코드 외, 본 chunk 직후 사용자 확인)

D-1 ted-run 완료 + 컨테이너 재배포 후 다음 항목을 ADR § 39 운영 결과에 누적:

- [ ] **첫 호출 (수동 trigger)**: `POST /api/kiwoom/sectors/{id}/ohlcv/daily/refresh` — sector_id=1 (KOSPI 종합) 단건 호출 성공 + DB upsert 확인
- [ ] **bulk sync (수동 trigger)**: `POST /api/kiwoom/sectors/ohlcv/daily/sync` — active sector 50~80개 일괄 sync 시간 + 0 failed
- [ ] **100배 값 검증**: KOSPI 종합 응답값 / 100 ≈ 실제 KOSPI 지수 (예: 2700 ± 5%) 일치
- [ ] **응답 필드 검증**: `inds_dt_pole_qry` list key 정확성 / 7 필드 가정 정확성
- [ ] **페이지네이션 발생 빈도**: 3년 백필 시 page 수
- [ ] **cron 07:00 KST 발화 (별도 활성 chunk 후)**: 06:30 daily_flow 와 KRX rate limit 경합 실측 (H-5)

---

_Phase D 진입 chunk. ka10080 분봉을 사용자 결정으로 마지막으로 미룬 결과, 가장 가벼운 sector daily 가 Phase D 첫 endpoint. ka10101 의 sector 마스터 + ka10081/82/83/94 의 chart 패턴 + § 35 cron 정책이 모두 확립된 상태라 신규 결정 항목은 9개 (§ 12.2) — 100배 값 / sector_id 매핑 / NXT skip / cron 시간 / 응답 7 필드 / 백필 윈도 / Migration 015 / UseCase 입력 / chart.py 통합. 12/25 endpoint 진입._

---

## 13. Phase D-1 follow-up — MaxPages cap 상향 + bulk insert 32767 chunk 분할 (운영 실패 대응)

> **추가일**: 2026-05-13 (KST) — Phase E (`0e767fe`) + 컨테이너 재배포 (`0ec6326`) 종결 후
> **분류**: fix (운영 인시던트 대응 — MaxPages cap 부족 + bulk insert 32767 한도 초과)
> **선행 조건**: Phase E 종결 / 12 scheduler 활성 / 15/25 endpoint
> **트리거**: 5-12 D-1 백필 시도 결과 — sector_daily 60/124 (48% success), daily_flow KOSDAQ 1814/4371 누락
> **cross-ref**: `endpoint-10-ka10086.md` § 13 (ka10086 cap 동반 상향)

### 13.1 배경 (Phase D-1 follow-up 진입)

**5-13 06:00 / 06:30 / 07:00 scheduler dead 추정 인시던트 → 자연 재현 검증 결과 반증**

5-13 17:30 stock_master / 18:00 stock_fundamental 자연 cron 정상 발화 (각각 4788/4063 row 처리). 06:00 의 0-row 는 **컨테이너 재배포 직후 일회성** 가설로 정리 (ADR § 41 신규 § 후보, 본 chunk 대상 아님).

**그러나 dead 검증 중 5-12 D-1 백필 실패 인시던트 발견**:

| # | 인시던트 | 실제 예외 | 카운트 | 근본 원인 |
|---|---------|---------|--------|----------|
| 1 | ka20006 sector_daily MaxPages | `KiwoomMaxPagesExceededError` (`SECTOR_DAILY_MAX_PAGES=10`) | 56 / 124 (45%) | 추정값 "1 page ~600 거래일" 틀림 — ka10086 실측 (1 page ~22 거래일) 패턴이면 3년 = 34 page → 10 부족 |
| 2 | ka20006 sector_daily InterfaceError | `asyncpg.exceptions._base.InterfaceError: the number of query arguments cannot exceed 32767` (sector_id 29/57/102/103/105/106/107/108) | 8 / 124 | PostgreSQL wire protocol int16 한도 — bulk insert row × column > 32767 |
| 3 | ka10086 daily_flow KOSDAQ MaxPages | `KiwoomMaxPagesExceededError` (`DAILY_MARKET_MAX_PAGES=40`) | 다수 (KRX 1814 누락) | 40 cap 부족 — 일부 KOSDAQ 종목 (오래된 상장) page > 40 |

**별도 인시던트 (본 chunk 범위 아님 — F chunk 분리)**:
- ka10001 stock_fundamental ASYNCPG 11건 = `NumericValueOutOfRangeError: precision 8 scale 4 must < 10^4` → NUMERIC(8,4) 컬럼 overflow (Migration 신규 + precision 확대 필요). VALIDATE 2건 = sentinel detect (ka10001 `_validate_stk_cd_for_lookup`) — WARN/skipped 분리 누락. **F chunk 별도 진행**.

### 13.2 결정 (ADR-0001 § 42 신규 예정)

| # | 사안 | 결정 | 근거 |
|---|------|------|------|
| 1 | `SECTOR_DAILY_MAX_PAGES` 상향 | 10 → **40** | ka10086 실측 패턴 (1 page ~22 거래일, mrkcond.py L51-53) 그대로 차용. 3년 = ~34 page + 안전 마진 6. 실측은 ted-run TDD 단계 + 운영 검증에 위임 |
| 2 | `DAILY_MARKET_MAX_PAGES` 상향 | 40 → **60** | 5-12 KOSDAQ 1814 누락 = 일부 종목 page > 40. 60 (안전 마진 26) 으로 상향. 운영 첫 호출 시 실제 page 분포 측정 → ADR § 42 운영 결과 |
| 3 | bulk insert chunk 분할 | `upsert_many` chunk_size = **1000** (rows). 32767 / 평균 13 col ≈ 2520 안전. 1000 보수치 | sector_daily 일부 sector (long-history 15년+) → 5500 row × 6 col ≈ 33000 한도 초과. 1000 row × 13 col = 13000 안전 |
| 4 | 적용 범위 | (a) sector_price_daily Repository (b) stock_daily_flow Repository | 본 chunk 범위. Phase E 의 short_selling / lending 은 별도 chunk (적용 의무 없음 — bulk row 수 추정 미만) |
| 5 | chunked upsert 헬퍼 | `_chunked_upsert(session, model, rows, *, chunk_size)` — 모든 Repository 가 공통 호출 | Repository 별 중복 회피. 미래 endpoint 표준 |
| 6 | `KiwoomMaxPagesExceededError` 보강 | `page` (도달한 페이지 수) + `cap` (한도) attribute 추가 — 예외 메시지에 노출 | 운영 가시화 — 어느 cap 이 얼마나 부족했는지 즉시 판단 |
| 7 | UseCase 시그니처 | 변경 0 — Repository 단에서 흡수 | UseCase / Service / Adapter / Migration 모두 변경 X. Repository 만 |
| 8 | Migration 신규 | **없음** (스키마 변경 0) | 코드 + 테스트만 |
| 9 | 백필 재호출 (운영) | 본 chunk 코드 머지 + 컨테이너 재배포 후 별도 운영 chunk | 5-12 sector_daily 64건 + KOSDAQ 1814건 재호출. ted-run / 본 코드 chunk 와 분리 |
| 10 | scheduler dead 진단 endpoint (Pending #7) | 본 chunk 범위 아님 — 5-13 일회성 가능성 인정 + `/admin/scheduler/diag` 유지 (운영 가치) | dead 가설 자연 재현 반증. ADR § 41 신규 § 별도 후보 (코드 변경 0) |

### 13.3 영향 범위 (6 코드 + 5 테스트)

**코드 (6 files)**:

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/adapter/out/kiwoom/chart.py` | `SECTOR_DAILY_MAX_PAGES = 10 → 40` (L350) + 주석 갱신 (실측 ka10086 패턴 차용) |
| 2 | `app/adapter/out/kiwoom/mrkcond.py` | `DAILY_MARKET_MAX_PAGES = 40 → 60` (L53) + 주석 갱신 (5-12 KOSDAQ 1814 누락 근거) |
| 3 | `app/adapter/out/kiwoom/_errors.py` (또는 동등) | `KiwoomMaxPagesExceededError` 클래스 — `page` / `cap` 필드 추가, `__str__` 에 노출 |
| 4 | `app/adapter/out/persistence/repositories/_base.py` (신규 또는 helper) | `async def _chunked_upsert(session, model, rows, *, chunk_size=1000) -> None` — INSERT … ON CONFLICT DO UPDATE 를 chunk_size 단위로 split |
| 5 | `app/adapter/out/persistence/repositories/sector_daily.py` (또는 sector_price_daily 명) | `upsert_many` → `_chunked_upsert` 호출로 변경 (chunk_size=1000) |
| 6 | `app/adapter/out/persistence/repositories/daily_flow.py` (또는 stock_daily_flow 명) | 동일 패턴 — `_chunked_upsert` 호출 |

**테스트 (5 신규)**:

| # | 파일 | 변경 |
|---|------|------|
| 1 | `tests/test_chart_sector_daily_max_pages.py` (기존 갱신) | `SECTOR_DAILY_MAX_PAGES == 40` 단위 / cap 도달 시 `KiwoomMaxPagesExceededError(page=40, cap=40)` 발생 검증 |
| 2 | `tests/test_mrkcond_daily_market_max_pages.py` (기존 갱신) | `DAILY_MARKET_MAX_PAGES == 60` 단위 / 동일 패턴 |
| 3 | `tests/test_repository_chunked_upsert.py` (신규) | `_chunked_upsert` helper — chunk_size=1000 / 빈 list / 1 row / 999 row (단일 chunk) / 1001 row (2 chunk) / 5500 row (6 chunk) 모두 검증 |
| 4 | `tests/test_sector_daily_repository_chunk.py` (신규 또는 기존 통합) | sector_daily Repository 5500 row × 6 col INSERT 시 32767 안전 (testcontainers PG16 실제 INSERT) |
| 5 | `tests/test_daily_flow_repository_chunk.py` (신규 또는 기존 통합) | daily_flow Repository 동일 패턴 |

**문서**:
- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 42 신규 (Phase D-1 follow-up 결과)
- `CHANGELOG.md` / `STATUS.md` § 0 / § 1 / § 4 / § 5 / § 6 / `HANDOFF.md` / 본 doc § 13 (자기 참조)
- `endpoint-10-ka10086.md` 끝에 § 13 cross-ref 노트 ("Phase D-1 follow-up = endpoint-13 § 13 참조")
- `master.md` ka20006 / ka10086 row 갱신 (cap 값 + chunk_size)

### 13.4 적대적 이중 리뷰 — 사전 self-check (ted-run 진입 전)

| # | 위험 | 완화 |
|---|------|------|
| H-1 | `SECTOR_DAILY_MAX_PAGES = 40` 도 부족 (long-history sector 15년+) | ted-run TDD 단계 + 운영 첫 호출 시 page 분포 측정. 60 / 100 추가 상향 옵션 유보. 본 chunk 디폴트 40 (ka10086 실측 패턴 일치 우선) |
| H-2 | `DAILY_MARKET_MAX_PAGES = 60` 도 부족 (KOSDAQ 오래된 종목 1990년대 상장) | 동일 — 운영 측정 → 100 상향 옵션 유보. 5-12 1814 누락 종목 1-2개 직접 호출하여 실제 page 수 확인 |
| H-3 | chunk_size = 1000 vs 더 보수치 500 | 1000 row × 13 col = 13000 (32767 한도 40%) — 충분 안전 마진. 단 5+ 필드 column 추가 시 재검토. testcontainers PG16 5500 row 테스트로 실측 검증 |
| H-4 | INSERT chunk 분할로 인한 ON CONFLICT 트랜잭션 경계 변경 | `_chunked_upsert` 가 단일 `session.begin()` 안에서 chunk loop — 전체 원자성 유지. partial chunk 실패 시 전체 롤백 (기존 동작과 동일) |
| H-5 | `KiwoomMaxPagesExceededError(page, cap)` 시그니처 변경 — 기존 호출처 영향 | 신규 attribute 추가만 (positional/keyword 둘 다 default). 기존 raise/except 호환. ruff/mypy strict 통과 검증 |
| H-6 | `_chunked_upsert` 가 generic — model 별 column 차이로 cardinality 다름 | helper 가 model 의 `__table__.columns` 메타 사용 — column 수 동적 계산. chunk_size 가 model 별로 다를 수 있는 cap 은 호출자 결정 (sector_daily / daily_flow 모두 1000 고정) |
| H-7 | 운영 5-12 sector_daily 64 + KOSDAQ 1814 재호출 의무 | 본 chunk 코드 변경 후 별도 운영 chunk (백필 CLI 또는 admin endpoint 호출). 본 chunk 의 ted-run 범위 아님 (코드 + 테스트 + 문서만) |
| H-8 | 1R CONDITIONAL 가능성 (D-1 / Phase E 패턴) | 6 코드 + 5 테스트 = D-1 (10/6) 대비 작은 chunk. 2R 진입 가정 풀 사이클 ~3-5 시간 견적 (Phase E 의 ~6-10 시간 절반) |
| H-9 | F chunk (ka10001 NUMERIC + sentinel) 와의 분리 정당성 | F 는 Migration 신규 (NUMERIC(8,4) → precision 확대) + WARN/skipped 분리 패턴 — bulk chunk fix 와 완전 독립. F 는 본 chunk 머지 후 별도 ted-run |
| H-10 | `_chunked_upsert` helper 가 Phase E (short_selling / lending) Repository 에 즉시 적용 안 됨 | Phase E 의 row 추정 (1 종목 × 1주 × 1 row = 작음) 으로 본 chunk fix 의무 없음. 향후 row 폭증 시 동일 helper 호출로 즉시 적용 가능 (helper 표준화 효과) |

### 13.5 DoD (Phase D-1 follow-up)

**코드**:
- [ ] `SECTOR_DAILY_MAX_PAGES = 40` 적용 (chart.py L350)
- [ ] `DAILY_MARKET_MAX_PAGES = 60` 적용 (mrkcond.py L53)
- [ ] `KiwoomMaxPagesExceededError(page, cap)` 시그니처 + `__str__` 갱신
- [ ] `_chunked_upsert` helper 구현 + chunk_size=1000 디폴트
- [ ] sector_daily Repository `upsert_many` → `_chunked_upsert` 호출
- [ ] daily_flow Repository 동일 패턴 적용

**테스트**:
- [ ] cap 단위 테스트 2건 (sector_daily / daily_market)
- [ ] `_chunked_upsert` 단위 테스트 (빈 / 1 / 999 / 1001 / 5500 row)
- [ ] sector_daily / daily_flow Repository integration (testcontainers PG16, 5500 row 안전)
- [ ] `ruff check` + `mypy --strict` PASS

**이중 리뷰**:
- [ ] 1R PASS (Reviewer: chunk_size 1000 보수치 + ON CONFLICT 트랜잭션 경계 + `_chunked_upsert` cardinality 동적 계산)

**문서**:
- [ ] ADR-0001 § 42 추가 (Phase D-1 follow-up 결과 + H-1~H-10 self-check 반영)
- [ ] STATUS.md § 0 / § 1 / § 4 / § 5 / § 6 갱신 (Phase D-1 follow-up 종결 + 5-12 백필 재호출 별도 chunk)
- [ ] CHANGELOG: `fix(kiwoom): Phase D-1 follow-up — MaxPages cap 상향 (ka20006 10→40, ka10086 40→60) + bulk insert 32767 chunk 분할`
- [ ] HANDOFF.md 갱신
- [ ] master.md ka20006 / ka10086 row 갱신
- [ ] endpoint-10-ka10086.md § 13 cross-ref 추가

### 13.6 다음 chunk (Phase D-1 follow-up 이후)

1. **운영 백필 재호출 chunk** — 5-12 sector_daily 64건 + KOSDAQ 1814건 (코드 변경 0, admin endpoint 호출만)
2. **F chunk — ka10001 NUMERIC overflow + sentinel WARN/skipped 분리** (별도 ted-run, Migration 신규)
3. **Phase E 후속** — 운영 첫 cron (07:30/07:45/08:00) 발화 결과 ADR § 40 운영 결과 채움
4. **(5-19 이후) § 36.5 1주 모니터 측정 채움** — 12 + (Phase E 후 추가) scheduler 운영
5. **Phase F / G / H** — 순위 / 투자자별 / 통합 신규 endpoint wave
6. **Phase D-2 ka10080 분봉** (마지막 endpoint)
7. **§11 포트폴리오 · AI 리포트 (P10~P15)** — 25 endpoint 완주 후
8. **(전체 개발 종결 후) secret 회전**

### 13.7 운영 모니터 (코드 외, 본 chunk 직후 사용자 확인)

본 chunk 머지 + 컨테이너 재배포 후 다음 항목을 ADR § 42 운영 결과에 누적:

- [ ] **5-12 sector_daily 재호출**: 실패 64건 sector 의 `POST /api/kiwoom/sectors/{id}/ohlcv/daily/refresh` — 0 MaxPages / 0 InterfaceError
- [ ] **5-12 ka10086 KOSDAQ 재호출**: 실패 ~1814 종목의 `POST /api/kiwoom/stocks/{code}/daily-flow/refresh?exchange=KRX&mrkt_tp=10` — 0 MaxPages
- [ ] **page 분포 실측**: ka20006 sector 별 실제 page 수 (40 cap 의 여유) / ka10086 KOSDAQ 종목 별 page 수 (60 cap 의 여유) — ADR § 42 운영 결과 표
- [ ] **chunk_size 1000 보수치 검증**: sector_daily 5500 row sector 의 실제 chunk 분할 횟수 + 총 elapsed (단일 chunk 대비 오버헤드)
- [ ] **(별도 chunk) 5-13 새벽 dead 인시던트 진단 endpoint 정리** — `/admin/scheduler/diag` 유지/제거 결정

---

_Phase D-1 ka20006 머지 + Phase E 매도 측 시그널 wave 머지 직후 발견된 운영 인시던트 대응 chunk. 핵심 원인 2개 — (a) MaxPages cap 추정값 ("1 page ~600 거래일") 이 실측 ka10086 (1 page ~22 거래일) 패턴과 13배 차이 (b) bulk insert 의 PostgreSQL wire protocol int16 한도 32767. 코드 6 + 테스트 5 + 문서 갱신만 — Migration 0 / UseCase 변경 0 / Repository 단 chunk_size 흡수. 운영 5-12 재호출은 별도 chunk._
