# endpoint-14-ka10101.md — 업종코드 리스트

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10101` |
| API 명 | 업종코드 리스트 |
| 분류 | Tier 1 (메타 — 업종 마스터) |
| Phase | **A** |
| 우선순위 | **P1** |
| Method | `POST` |
| URL | `/api/dostk/stkinfo` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX 만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| 의존 endpoint | `au10001` (토큰 필요) |
| 후속 endpoint | `ka20006` (업종일봉), Phase F 순위 endpoint 들의 sector 매핑 |

---

## 1. 목적

키움이 사용하는 **업종 코드 사전(dictionary)** 을 적재한다. 업종 코드는 다음 위치에서 참조된다:

- `ka10099` 응답의 `upName` (업종명) — 코드 매핑 필요
- `ka10001` 응답의 sector 정보 (간접)
- `ka20001~ka20019` 업종 시세 / 일봉 / 주봉 등 — `inds_cd` 파라미터로 사용
- 백테스팅 시 종목 → 업종 → 시장(KOSPI200/KOSDAQ150 등) 그루핑

**왜 P1 (P0 아님)**:
- 백테스팅 첫 사이클에는 종목·OHLCV 만으로 동작 가능
- 업종 코드는 시그널 강화 / 섹터 회전 분석 / 업종 별 백테스팅 비교 단계에서 필요
- 그러나 Phase A 의 KiwoomClient (공통 트랜스포트) 가 정상 작동하는지 **검증용 첫 endpoint** 로 적합 — 인증 외 정상 데이터 호출의 가장 단순한 케이스

**Phase A 에 포함시킨 이유**:
1. au10001 이 정상 작동하면 즉시 ka10101 호출로 인증 흐름 e2e 검증
2. 응답 구조가 단순 (4 필드 list) — 공통 트랜스포트의 페이지네이션·재시도·로깅을 가벼운 데이터로 검증
3. Phase B 의 ka10099 (대용량) 가 깨졌을 때 디버깅 비교군

---

## 2. Request 명세

### 2.1 Header

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `api-id` | TR 명 | String | Y | 10 | `"ka10101"` 고정 |
| `authorization` | 접근토큰 | String | Y | 1000 | `Bearer <token>` |
| `cont-yn` | 연속조회 여부 | String | N | 1 | 응답 헤더의 값을 다음 호출에 그대로 전달 |
| `next-key` | 연속조회 키 | String | N | 50 | 응답 헤더의 값을 다음 호출에 그대로 전달 |

### 2.2 Body

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `mrkt_tp` | 시장구분 | String | Y | 1 | `0:코스피(거래소), 1:코스닥, 2:KOSPI200, 4:KOSPI100, 7:KRX100(통합지수)` |

> **유효값 5개**: `0`, `1`, `2`, `4`, `7` (3, 5, 6 은 미정의 — 호출 금지)

### 2.3 Request 예시

```json
POST https://api.kiwoom.com/api/dostk/stkinfo
Content-Type: application/json;charset=UTF-8
api-id: ka10101
authorization: Bearer WQJCwyqInphKnR3bSRtB9NE1lv...

{
    "mrkt_tp": "0"
}
```

### 2.4 Pydantic 모델

```python
# app/adapter/out/kiwoom/stkinfo.py
class SectorListRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    mrkt_tp: Literal["0", "1", "2", "4", "7"]
```

---

## 3. Response 명세

### 3.1 Header

| Element | 한글명 | Type | Description |
|---------|-------|------|-------------|
| `api-id` | TR 명 | String | `"ka10101"` 에코 |
| `cont-yn` | 연속조회 여부 | String | `Y` 면 다음 페이지 존재 |
| `next-key` | 연속조회 키 | String | 다음 호출 헤더에 세팅 |

### 3.2 Body

| Element | 한글명 | Type | Required | Description |
|---------|-------|------|----------|-------------|
| `list` | 업종코드 리스트 | LIST | N | 업종 row 배열 |
| `list[].marketCode` | 시장구분코드 | String | N | 요청한 `mrkt_tp` 에코 (스펙은 LIST 표기지만 예시는 String — Excel 표기 오류로 추정) |
| `list[].code` | 업종코드 | String | N | 3자리 추정 (예: `"001"`) |
| `list[].name` | 업종명 | String | N | 한글 (예: `"종합(KOSPI)"`) |
| `list[].group` | 그룹 | String | N | 정렬·분류용 (예: `"1"`, `"2"`) |
| `return_code` | 처리 코드 | Integer | (예시) | `0` 정상 |
| `return_msg` | 처리 메시지 | String | (예시) | `"정상적으로 처리되었습니다"` |

### 3.3 Response 예시 (Excel 원문)

```json
{
    "return_msg": "정상적으로 처리되었습니다",
    "return_code": 0,
    "list": [
        { "marketCode": "0", "code": "001", "name": "종합(KOSPI)",  "group": "1" },
        { "marketCode": "0", "code": "002", "name": "대형주",       "group": "2" },
        { "marketCode": "0", "code": "003", "name": "중형주",       "group": "3" },
        { "marketCode": "0", "code": "004", "name": "소형주",       "group": "4" },
        { "marketCode": "0", "code": "005", "name": "음식료업",     "group": "5" },
        { "marketCode": "0", "code": "006", "name": "섬유의복",     "group": "6" },
        { "marketCode": "0", "code": "007", "name": "종이목재",     "group": "7" },
        { "marketCode": "0", "code": "008", "name": "화학",         "group": "8" },
        { "marketCode": "0", "code": "009", "name": "의약품",       "group": "9" },
        { "marketCode": "0", "code": "010", "name": "비금속광물",   "group": "10" },
        { "marketCode": "0", "code": "011", "name": "철강금속",     "group": "11" }
    ]
}
```

### 3.4 Pydantic 모델

```python
class SectorRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    marketCode: str = Field(alias="marketCode")            # JSON 키 그대로
    code: Annotated[str, Field(min_length=1, max_length=10)]
    name: Annotated[str, Field(min_length=1, max_length=100)]
    group: str = ""


class SectorListResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    list: list[SectorRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""
```

> **camelCase 키 유지**: 키움 응답 스키마 그대로. 영속화 단계에서 snake_case 컬럼으로 매핑.

---

## 4. NXT 처리

| 항목 | 적용 여부 |
|------|-----------|
| `stk_cd` 에 `_NX` suffix | N (종목코드 없음) |
| `nxt_enable` 게이팅 | N |
| `mrkt_tp` 별 분리 호출 | **Y** (5개 시장 각각 호출) |

업종 마스터는 시장 단위 분리 — 5개 호출을 순차/병렬 수행 후 합쳐 적재.

---

## 5. DB 스키마

### 5.1 신규 테이블 (Migration 002 — `stock_fundamental_and_sector.py`)

```sql
CREATE TABLE kiwoom.sector (
    id              BIGSERIAL PRIMARY KEY,
    market_code     VARCHAR(2) NOT NULL,                  -- "0"/"1"/"2"/"4"/"7"
    sector_code     VARCHAR(10) NOT NULL,                 -- "001"~"099"
    sector_name     VARCHAR(100) NOT NULL,
    group_no        VARCHAR(10),                          -- 정렬용
    is_active       BOOLEAN NOT NULL DEFAULT true,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),   -- 마지막 동기화
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_sector_market_code UNIQUE (market_code, sector_code)
);

CREATE INDEX idx_sector_market ON kiwoom.sector(market_code);
CREATE INDEX idx_sector_active ON kiwoom.sector(is_active) WHERE is_active = true;
```

### 5.2 ORM 모델

```python
# app/adapter/out/persistence/models/sector.py
class Sector(Base):
    __tablename__ = "sector"
    __table_args__ = (
        UniqueConstraint("market_code", "sector_code", name="uq_sector_market_code"),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    market_code: Mapped[str] = mapped_column(String(2), nullable=False)
    sector_code: Mapped[str] = mapped_column(String(10), nullable=False)
    sector_name: Mapped[str] = mapped_column(String(100), nullable=False)
    group_no: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

### 5.3 Sector 디액티베이션 정책

키움이 업종을 폐지/재편성하면 sync 결과에서 빠질 수 있다. 두 정책 후보:

| 정책 | 동작 | 장점 | 단점 |
|------|------|------|------|
| **A. Hard delete** | 응답에 없는 row 는 DELETE | 단순 | FK 참조하는 다른 테이블에서 깨짐 |
| **B. is_active=false 마킹** (권장) | 응답에 없으면 `is_active=false` 로 update | FK 안전, 과거 데이터 보존 | 쿼리에서 `WHERE is_active=true` 필터 필수 |

**기본 채택**: B. 정책. UseCase 가 sync 마지막에 "이번 응답에 없는 (market_code, sector_code) 는 is_active=false" UPDATE 수행.

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomStkInfoClient.fetch_sectors()`

```python
# app/adapter/out/kiwoom/stkinfo.py
class KiwoomStkInfoClient:
    """`/api/dostk/stkinfo` 계열 엔드포인트 묶음.

    KiwoomClient(공통 트랜스포트) 를 의존성으로 받아 토큰 캐시·재시도·rate-limit 을 위임.
    """

    API_ID = "ka10101"
    PATH = "/api/dostk/stkinfo"

    def __init__(self, kiwoom_client: KiwoomClient) -> None:
        self._client = kiwoom_client

    async def fetch_sectors(self, mrkt_tp: str) -> SectorListResponse:
        """단일 시장의 업종 리스트 조회. 페이지네이션 자동 처리."""
        if mrkt_tp not in ("0", "1", "2", "4", "7"):
            raise ValueError(f"mrkt_tp 유효값 외: {mrkt_tp}")

        all_rows: list[SectorRow] = []
        return_code = 0
        return_msg = ""

        async for page in self._client.call_paginated(
            api_id="ka10101",
            endpoint=self.PATH,
            body={"mrkt_tp": mrkt_tp},
            max_pages=20,
        ):
            parsed = SectorListResponse.model_validate(page.body)
            all_rows.extend(parsed.list)
            return_code = parsed.return_code
            return_msg = parsed.return_msg

        return SectorListResponse(
            list=all_rows,
            return_code=return_code,
            return_msg=return_msg,
        )
```

> `call_paginated` 는 KiwoomClient 가 제공 (master.md § 6.2). `cont-yn=Y` 인 동안 같은 body 로 반복 호출 + `next-key` 헤더 세팅.

### 6.2 Repository

```python
# app/adapter/out/persistence/repositories/sector.py
class SectorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_market(self, market_code: str, *, only_active: bool = True) -> list[Sector]:
        stmt = select(Sector).where(Sector.market_code == market_code)
        if only_active:
            stmt = stmt.where(Sector.is_active.is_(True))
        return list((await self._session.execute(stmt)).scalars())

    async def upsert_many(self, rows: list[dict[str, Any]]) -> int:
        """PostgreSQL ON CONFLICT 로 (market_code, sector_code) UNIQUE upsert.

        반환: 영향받은 row 수.
        """
        if not rows:
            return 0
        stmt = pg_insert(Sector).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["market_code", "sector_code"],
            set_={
                "sector_name": stmt.excluded.sector_name,
                "group_no": stmt.excluded.group_no,
                "is_active": True,                          # 응답에 등장하면 다시 활성화
                "fetched_at": func.now(),
                "updated_at": func.now(),
            },
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return rowcount_of(result)

    async def deactivate_missing(
        self, market_code: str, present_codes: set[str]
    ) -> int:
        """응답에 없는 sector_code 들을 is_active=false 로 UPDATE."""
        stmt = (
            update(Sector)
            .where(
                Sector.market_code == market_code,
                Sector.is_active.is_(True),
                Sector.sector_code.notin_(present_codes) if present_codes else true(),
            )
            .values(is_active=False, updated_at=func.now())
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return rowcount_of(result)
```

### 6.3 UseCase — `SyncSectorMasterUseCase`

```python
# app/application/service/sector_service.py
class SyncSectorMasterUseCase:
    """5개 시장의 업종 마스터를 키움에서 가져와 sector 테이블 동기화.

    원자성: 시장 별로 트랜잭션 분리. 한 시장 호출 실패가 다른 시장 적재를 막지 않는다.
    """

    SUPPORTED_MARKETS = ("0", "1", "2", "4", "7")

    def __init__(
        self,
        session: AsyncSession,
        *,
        stkinfo_client: KiwoomStkInfoClient,
    ) -> None:
        self._session = session
        self._client = stkinfo_client
        self._repo = SectorRepository(session)

    async def execute(self) -> SectorSyncResult:
        per_market: list[MarketSyncOutcome] = []

        for mrkt_tp in self.SUPPORTED_MARKETS:
            try:
                response = await self._client.fetch_sectors(mrkt_tp)
            except KiwoomError as exc:
                logger.warning("sector sync 실패 mrkt_tp=%s: %s", mrkt_tp, exc)
                per_market.append(MarketSyncOutcome(
                    market_code=mrkt_tp,
                    fetched=0,
                    upserted=0,
                    deactivated=0,
                    error=f"{type(exc).__name__}: {exc}",
                ))
                continue

            rows_dict = [
                {
                    "market_code": r.marketCode,
                    "sector_code": r.code,
                    "sector_name": r.name,
                    "group_no": r.group or None,
                }
                for r in response.list
            ]
            upserted = await self._repo.upsert_many(rows_dict)
            present = {r.code for r in response.list}
            deactivated = await self._repo.deactivate_missing(mrkt_tp, present)
            per_market.append(MarketSyncOutcome(
                market_code=mrkt_tp,
                fetched=len(response.list),
                upserted=upserted,
                deactivated=deactivated,
            ))

        return SectorSyncResult(
            markets=per_market,
            total_fetched=sum(m.fetched for m in per_market),
            total_upserted=sum(m.upserted for m in per_market),
            total_deactivated=sum(m.deactivated for m in per_market),
        )


@dataclass(frozen=True, slots=True)
class MarketSyncOutcome:
    market_code: str
    fetched: int
    upserted: int
    deactivated: int
    error: str | None = None


@dataclass(frozen=True, slots=True)
class SectorSyncResult:
    markets: list[MarketSyncOutcome]
    total_fetched: int
    total_upserted: int
    total_deactivated: int
```

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **수동 동기화** | on-demand | `POST /api/kiwoom/sectors/sync` (admin) |
| **주 1회 cron** | 일요일 KST 03:00 | APScheduler — 업종 변경이 잦지 않음 |
| **운영 초기 1회** | seed | `python scripts/seed_sectors.py` |

### 7.1 라우터

```python
# app/adapter/web/routers/kiwoom_meta.py
router = APIRouter(prefix="/api/kiwoom", tags=["kiwoom-meta"])


@router.get(
    "/sectors",
    response_model=list[SectorOut],
)
async def list_sectors(
    market_code: Literal["0", "1", "2", "4", "7"] | None = Query(default=None),
    only_active: bool = Query(default=True),
    session: AsyncSession = Depends(get_session),
) -> list[SectorOut]:
    """저장된 업종 마스터 조회 (DB only — 키움 호출 안 함)."""
    repo = SectorRepository(session)
    if market_code:
        rows = await repo.list_by_market(market_code, only_active=only_active)
    else:
        rows = []
        for mc in SyncSectorMasterUseCase.SUPPORTED_MARKETS:
            rows.extend(await repo.list_by_market(mc, only_active=only_active))
    return [SectorOut.model_validate(r) for r in rows]


@router.post(
    "/sectors/sync",
    response_model=SectorSyncResultOut,
    dependencies=[Depends(require_admin_key)],
)
async def sync_sectors(
    use_case: SyncSectorMasterUseCase = Depends(get_sync_sector_use_case),
) -> SectorSyncResultOut:
    """5개 시장 업종 마스터 강제 동기화."""
    result = await use_case.execute()
    return SectorSyncResultOut.model_validate(asdict(result))
```

### 7.2 APScheduler Job

```python
# app/batch/sector_sync_job.py
async def fire_sector_sync() -> None:
    """주 1회 — 업종 마스터 동기화."""
    try:
        async with get_sessionmaker()() as session:
            kiwoom_client = build_kiwoom_client_for("prod-main")  # alias 결정 필요
            stkinfo_client = KiwoomStkInfoClient(kiwoom_client)
            uc = SyncSectorMasterUseCase(session, stkinfo_client=stkinfo_client)
            result = await uc.execute()
            await session.commit()
        logger.info(
            "sector sync 완료 fetched=%d upserted=%d deactivated=%d",
            result.total_fetched, result.total_upserted, result.total_deactivated,
        )
    except Exception:
        logger.exception("sector sync 콜백 예외")


# scheduler.py 에 등록
scheduler.add_job(
    fire_sector_sync,
    CronTrigger(day_of_week="sun", hour=3, minute=0, timezone=KST),
    id="sector_sync_weekly",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
)
```

---

## 8. 에러 처리

| HTTP / 응답 | 도메인 예외 | 라우터 매핑 | UseCase 정책 |
|-------------|-------------|-------------|--------------|
| 401 / 403 | `KiwoomCredentialRejectedError` | 400 | UseCase 가 다른 시장 호출 계속 |
| 429 | (tenacity 재시도) → `KiwoomRateLimitedError` | 503 | UseCase 가 다른 시장 호출 계속 |
| 5xx, 네트워크 | `KiwoomUpstreamError` | 502 | UseCase 가 다른 시장 호출 계속 |
| `return_code != 0` | `KiwoomBusinessError` | 400 | UseCase 가 다른 시장 호출 계속 |
| `mrkt_tp` 잘못된 값 (3/5/6 등) | `ValueError` | 400 (`HTTPException`) | 호출 자체를 막음 |
| 응답 `list` 가 빈 배열 | — (정상) | 200 | upserted=0, deactivated=0 |
| Pydantic 검증 실패 | `KiwoomResponseValidationError` | 502 | 그 시장만 실패, 다른 시장 계속 |

### 8.1 시장 단위 격리

UseCase 는 **시장별 try/except** 로 한 시장 실패가 전체를 깨지 않게 한다 — `MarketSyncOutcome.error` 필드로 부분 실패 노출.

---

## 9. 테스트

### 9.1 Unit (MockTransport)

`tests/adapter/kiwoom/test_stkinfo_client.py`:

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 단일 시장 | mrkt_tp=0 + 200 + list 11건 | `SectorListResponse.list` 11개 |
| 단일 페이지 (cont-yn=N) | `cont-yn` 응답 헤더 없음 | `call_paginated` 1회로 종료 |
| 다중 페이지 (cont-yn=Y → N) | 첫 응답 cont-yn=Y + next-key, 두번째 N | call_paginated 2회 호출, 결과 합쳐짐 |
| 빈 list | 200 + `"list": []` | `SectorListResponse.list` 빈 배열 (정상) |
| `return_code=1` | 200 + 비즈니스 에러 | `KiwoomBusinessError` |
| 401 | 401 응답 | `KiwoomCredentialRejectedError` |
| 잘못된 mrkt_tp | mrkt_tp="3" | `ValueError` (호출 안 함) |
| 응답 필드 누락 (`code` 없음) | 200 + 잘못된 row | `KiwoomResponseValidationError` (Pydantic) |

### 9.2 Integration (testcontainers)

`tests/application/test_sector_service.py`:

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| 첫 sync (빈 DB) | 5 시장 모두 200 + 데이터 | `SectorSyncResult.total_upserted > 0`, `total_deactivated = 0` |
| 재 sync (변경 없음) | 같은 응답 다시 | `total_upserted == 5개 시장 합계`, `total_deactivated = 0` |
| 폐지된 업종 처리 | 첫 sync 후 두번째 응답에서 `code=011` 빠짐 | `Sector.is_active=False` 로 UPDATE 됨 |
| 재등장한 업종 처리 | 비활성화된 code 가 다시 응답에 등장 | `is_active=True` 복원 |
| 한 시장 호출 실패 | 시장 0,1 정상 + 시장 2 가 502 | 시장 0/1 적재됨, 시장 2 outcome.error != None, 다른 시장 영향 없음 |
| 시장명 변경 | code 동일 + name 다름 | `sector_name` UPDATE |
| 부분 페이지 | 첫 응답 5건 + 둘째 응답 6건 | 11건 모두 적재 |

### 9.3 E2E

```python
@pytest.mark.requires_kiwoom_real
async def test_real_sector_sync():
    creds = KiwoomCredentials(
        appkey=os.environ["KIWOOM_PROD_APPKEY"],
        secretkey=os.environ["KIWOOM_PROD_SECRETKEY"],
    )
    async with KiwoomAuthClient(base_url="https://api.kiwoom.com") as auth:
        token = await auth.issue_token(creds)
    try:
        kiwoom_client = KiwoomClient(
            base_url="https://api.kiwoom.com",
            token=token.token,
        )
        stkinfo = KiwoomStkInfoClient(kiwoom_client)
        # KOSPI 업종 — 100여 건 예상
        kospi = await stkinfo.fetch_sectors("0")
        assert len(kospi.list) >= 30
        # KOSDAQ
        kosdaq = await stkinfo.fetch_sectors("1")
        assert len(kosdaq.list) >= 20
    finally:
        async with KiwoomAuthClient(base_url="https://api.kiwoom.com") as auth:
            await auth.revoke_token(creds, token.token)
```

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `app/adapter/out/kiwoom/_client.py` 의 `KiwoomClient.call` + `call_paginated` (au10001 테스트 후 본격 도입)
- [ ] `app/adapter/out/kiwoom/stkinfo.py` 에 `KiwoomStkInfoClient.fetch_sectors`
- [ ] `app/adapter/out/persistence/models/sector.py`
- [ ] `app/adapter/out/persistence/repositories/sector.py`
- [ ] `app/application/service/sector_service.py` (`SyncSectorMasterUseCase`)
- [ ] `app/adapter/web/routers/kiwoom_meta.py` (`GET/POST /api/kiwoom/sectors`)
- [ ] `app/batch/sector_sync_job.py` + scheduler 등록
- [ ] `migrations/versions/002_stock_fundamental_and_sector.py` (sector 테이블 정의 — fundamental 은 Phase B)

### 10.2 테스트

- [ ] Unit 8 시나리오 (§9.1) PASS
- [ ] Integration 7 시나리오 (§9.2) PASS
- [ ] coverage `KiwoomStkInfoClient`, `SyncSectorMasterUseCase`, `SectorRepository` ≥ 80%

### 10.3 운영 검증

- [ ] 5개 시장 모두 호출 성공 + 각 시장 row 수 확인 (mrkt_tp=0 KOSPI: ~30~50개 추정)
- [ ] `code` 필드 길이 분포 확인 (3자리 가정 — 그 외 길이가 등장하면 schema 조정)
- [ ] `marketCode` 필드 String 가정이 맞는지 확인 (스펙 표기는 LIST 였음)
- [ ] 페이지네이션 발생 여부 (KOSPI 의 list 크기가 50 미만이면 단일 페이지로 끝날 가능성 높음)
- [ ] 같은 sync 두 번 실행해 멱등성 확인 (`total_upserted` 동일, `total_deactivated=0`)

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10101 sector master sync (5 markets)`
- [ ] `master.md` § 12 결정 기록에 `marketCode` String 확정 + 시장별 row 수 메모

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | 폐지된 업종 처리 | hard delete / `is_active=false` (권장) | 본 endpoint 내 (§5.3) |
| 2 | 주 1회 cron 의 alias | `prod-main` 단일 / 별도 `prod-meta` | Phase A 후반 |
| 3 | KOSPI200/KOSPI100/KRX100 (`mrkt_tp=2/4/7`) 가 일반 업종과 동일 스키마인지 | 운영 검증 | DoD § 10.3 |
| 4 | `marketCode` 필드 타입 | String (예시 기준) / LIST (스펙 표기) | DoD § 10.3 |
| 5 | `code` 길이 (3 / 4 / 가변) | 운영 검증 | DoD § 10.3 |

### 11.2 알려진 위험

- **Excel 스펙 vs 실제 응답 차이**: `marketCode` 가 스펙은 LIST 인데 예시는 String. 실제는 String 일 가능성이 높지만 첫 호출에서 raw response 확인 필수
- **페이지네이션 미발생 가정**: 업종 코드는 보통 한 시장당 50개 미만이라 단일 페이지로 끝날 것. 그러나 KOSPI200 같은 지수 구성종목 list 가 200건이면 페이지네이션 동작 — `call_paginated` 가 동작하는지 검증
- **KOSPI200/100/KRX100 의 의미**: `mrkt_tp=2/4/7` 이 "업종" 이라기보다 "지수 구성종목" 일 가능성. 그러면 `code` 가 종목 코드일 수 있음 → 별도 테이블/처리 필요할 수 있음. 운영 검증 필수
- **시장 0 (코스피) vs 거래소 코드 KOSPI**: `mrkt_tp=0` 이 "코스피(거래소)" — KOSDAQ(`1`) 와 형제 관계. 다른 endpoint 의 mrkt_tp 와 의미가 달라 매핑 표 정리 필요
- **`upName` 매핑 보장 안 됨**: ka10099 응답의 `upName` 이 본 endpoint 의 `name` 과 1:1 매칭되지 않을 수 있음 (한글 표기 차이). 매핑 보강 작업이 Phase B 에서 발생할 가능성
- **업종 코드 표준성**: KIS / DART 가 사용하는 업종 코드와 키움 코드가 다를 가능성. 백테스팅이 KIS 와 cross-reference 한다면 매핑 테이블 필요

### 11.3 mrkt_tp 의미 비교 (다른 endpoint 와)

| API | mrkt_tp 의미 |
|-----|--------------|
| **ka10101 (본 endpoint)** | `0:코스피, 1:코스닥, 2:KOSPI200, 4:KOSPI100, 7:KRX100` |
| ka10099 (종목정보 리스트) | `0:코스피, 10:코스닥, 30:K-OTC, 50:코넥스, 60:ETN, 70:손실제한 ETN, 80:금현물, 90:...` |
| ka10027/30/31/32 (순위) | `1:KRX, 2:NXT, 3:통합` |

→ **혼동 주의**. 같은 파라미터명이 endpoint 별로 의미가 완전히 다르다. UseCase 레이어에서 상수 분리 필요.

```python
# constants.py
class SectorMarketType(StrEnum):
    KOSPI = "0"
    KOSDAQ = "1"
    KOSPI200 = "2"
    KOSPI100 = "4"
    KRX100 = "7"


class StockListMarketType(StrEnum):
    KOSPI = "0"
    KOSDAQ = "10"
    K_OTC = "30"
    KONEX = "50"
    ETN = "60"
    # ...


class RankingExchangeType(StrEnum):
    KRX = "1"
    NXT = "2"
    UNIFIED = "3"
```

### 11.4 향후 확장

- **stock.sector_id FK**: ka10099 의 `upName` 을 sector 의 `name` 으로 매핑해 `stock.sector_id` 채움 (Phase B 에서)
- **업종별 백테스팅**: sector_code 단위 그룹화로 "철강금속" 업종 시그널 통계 등
- **지수 구성종목 (`mrkt_tp=2/4/7`) 별도 처리**: 만약 응답이 종목 리스트라면 `index_constituent` 테이블로 분리

---

_Phase A 의 세 번째 endpoint. au10001 + au10002 의 인증 흐름이 정상 작동하는지 가벼운 데이터 호출로 검증하는 역할. 페이지네이션·재시도·로깅 마스킹의 첫 e2e 검증 케이스._
