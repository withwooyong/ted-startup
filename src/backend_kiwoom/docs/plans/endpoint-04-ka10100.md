# endpoint-04-ka10100.md — 종목정보 조회 (단건)

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10100` |
| API 명 | 종목정보 조회 |
| 분류 | Tier 2 (종목 마스터 — 단건 보강) |
| Phase | **B** |
| 우선순위 | **P0** (ka10099 의 gap-filler) |
| Method | `POST` |
| URL | `/api/dostk/stkinfo` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX 만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| 의존 endpoint | `au10001` (토큰), `ka10099` (bulk source — soft 의존) |
| 후속 endpoint | `ka10001` (펀더멘털 보강), Phase C 의 ka10081 호출 큐 보강 |

---

## 1. 목적

특정 종목 한 건의 마스터 데이터를 조회한다. **ka10099(bulk) 의 gap-filler** 역할:

1. **신규 상장 즉시 보강** — 일 1회 ka10099 cron 사이에 신규 상장된 종목이 다른 endpoint 응답에 등장하면, 본 endpoint 로 즉시 마스터 채움
2. **의심 종목 즉시 재조회** — Phase F 순위 응답에 stock_code 가 등장했는데 stock 테이블에 없으면 본 endpoint 로 lazy fetch
3. **단건 정확도 검증** — ka10099 의 페이지네이션 끝부분 종목이 누락되었는지 검증할 때 sample check
4. **운영 디버깅** — 특정 종목의 키움 raw response 를 빠르게 확인 (본 endpoint 의 응답 한 건이 ka10099 list[] 의 한 row 와 사실상 동일)

**왜 P0**:
- ka10099 만으로는 일 1회 sync 사이의 gap (신규 상장, 종목명 변경) 처리 불가
- Phase C 일봉 수집이 stock 테이블에 없는 종목을 만나면 호출 자체가 실패하므로 **lazy fetch** 안전망 필수

**ka10099 와의 역할 분담** (endpoint-03 § 11.3 표 참조):
- ka10099: **bulk source** — 시장 단위 일 1회 일괄
- ka10100: **gap-filler** — 종목 단위 on-demand

---

## 2. Request 명세

### 2.1 Header

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `api-id` | TR 명 | String | Y | 10 | `"ka10100"` 고정 |
| `authorization` | 접근토큰 | String | Y | 1000 | `Bearer <token>` |
| `cont-yn` | 연속조회 여부 | String | N | 1 | (단건 — 거의 안 씀) |
| `next-key` | 연속조회 키 | String | N | 50 | (단건 — 거의 안 씀) |

### 2.2 Body

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `stk_cd` | 종목코드 | String | Y | **6** | KRX 단축코드 only — `_NX` / `_AL` suffix 미허용 (Excel R22 Length=6) |

> **중요**: ka10100 의 `stk_cd` Length=6. 다른 차트 endpoint 의 `stk_cd` Length=20 (`_NX`/`_AL` 허용) 와 다름. 본 endpoint 는 **순수 KRX 종목코드만**.

### 2.3 Request 예시

```json
POST https://api.kiwoom.com/api/dostk/stkinfo
Content-Type: application/json;charset=UTF-8
api-id: ka10100
authorization: Bearer WQJCwyqInphKnR3bSRtB9NE1lv...

{
    "stk_cd": "005930"
}
```

### 2.4 Pydantic 모델

```python
# app/adapter/out/kiwoom/stkinfo.py
class StockLookupRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    stk_cd: Annotated[str, Field(min_length=6, max_length=6, pattern=r"^\d{6}$")]
```

> Pydantic regex 로 `^\d{6}$` 강제 — ETF 의 `0033xx` 도 같은 형식이지만 `_NX` 는 거부.

---

## 3. Response 명세

### 3.1 Header

| Element | Type | Description |
|---------|------|-------------|
| `api-id` | String | `"ka10100"` 에코 |
| `cont-yn` | String | (단건 응답이므로 보통 N) |
| `next-key` | String | (단건 응답이므로 보통 빈 값) |

### 3.2 Body (14 필드 — ka10099 row 와 동일 + return_code/msg)

ka10099 의 list[] 한 row 와 **사실상 동일 스키마**. 단 응답이 list 가 아니라 **flat object**:

| Element | 한글명 | Type | Length | 영속화 컬럼 | 메모 |
|---------|-------|------|--------|-------------|------|
| `code` | 종목코드 | String | — | `stock_code` | 단축코드 |
| `name` | 종목명 | String | 40 | `stock_name` | 한글 |
| `listCount` | 상장주식수 | String | — | `list_count` | zero-padded |
| `auditInfo` | 감리구분 | String | — | `audit_info` | |
| `regDay` | 상장일 | String | — | `listed_date` | YYYYMMDD |
| `lastPrice` | 전일종가 | String | — | `last_price` | zero-padded |
| `state` | 종목상태 | String | — | `state` | |
| `marketCode` | 시장구분코드 | String | — | `market_code` | 응답 코드 |
| `marketName` | 시장명 | String | — | `market_name` | |
| `upName` | 업종명 | String | — | `up_name` | |
| `upSizeName` | 회사크기분류 | String | — | `up_size_name` | |
| `companyClassName` | 회사분류 | String | — | `company_class_name` | 코스닥 only |
| `orderWarning` | 투자유의종목여부 | String | — | `order_warning` | 0/1/2/3/4/5 |
| `nxtEnable` | NXT가능여부 | String | — | `nxt_enable` | Y / 빈값 |
| `return_code` | 처리코드 | Integer | — | (raw_response only) | 0 정상 |
| `return_msg` | 처리메시지 | String | — | (raw_response only) | |

### 3.3 Response 예시 (Excel R45)

```json
{
    "code": "005930",
    "name": "삼성전자",
    "listCount": "0000000026034239",
    "auditInfo": "정상",
    "regDay": "20090803",
    "lastPrice": "00136000",
    "state": "증거금20%|담보대출|신용가능",
    "marketCode": "0",
    "marketName": "거래소",
    "upName": "금융업",
    "upSizeName": "대형주",
    "companyClassName": "",
    "orderWarning": "0",
    "nxtEnable": "Y",
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다"
}
```

### 3.4 Pydantic 모델 — ka10099 의 `StockListRow` 재사용 가능

```python
# app/adapter/out/kiwoom/_records.py (endpoint-03 와 공유)
class StockLookupResponse(BaseModel):
    """ka10100 응답 — flat object. ka10099 row 와 동일 필드 + return_code/msg."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    code: Annotated[str, Field(min_length=1, max_length=20)]
    name: Annotated[str, Field(min_length=1, max_length=40)]
    listCount: str = ""
    auditInfo: str = ""
    regDay: str = ""
    lastPrice: str = ""
    state: str = ""
    marketCode: str = ""
    marketName: str = ""
    upName: str = ""
    upSizeName: str = ""
    companyClassName: str = ""
    orderWarning: Annotated[str, Field(max_length=1)] = "0"
    nxtEnable: Annotated[str, Field(max_length=2)] = ""
    return_code: int = 0
    return_msg: str = ""

    def to_normalized(self) -> NormalizedStock:
        """ka10099 의 to_normalized 와 동일 변환. 단 requested_market_code 는 응답값."""
        return NormalizedStock(
            stock_code=self.code,
            stock_name=self.name,
            list_count=int(self.listCount.lstrip("0") or "0") if self.listCount else None,
            audit_info=self.auditInfo or None,
            listed_date=_parse_yyyymmdd(self.regDay),
            last_price=int(self.lastPrice.lstrip("0") or "0") if self.lastPrice else None,
            state=self.state or None,
            market_code=self.marketCode or "",
            market_name=self.marketName or None,
            up_name=self.upName or None,
            up_size_name=self.upSizeName or None,
            company_class_name=self.companyClassName or None,
            order_warning=self.orderWarning or "0",
            nxt_enable=(self.nxtEnable.upper() == "Y"),
            requested_market_type=self.marketCode,    # bulk 와 달리 응답값 그대로
        )
```

> ka10099 의 `StockListRow` 와 거의 동일. 차이는 (a) flat 응답 구조 (b) `return_code`/`msg` 동행 (c) `requested_market_type` 이 응답값. **`NormalizedStock` 은 완전 공유**.

---

## 4. NXT 처리

| 항목 | 적용 여부 |
|------|-----------|
| `stk_cd` 에 `_NX` suffix | **N** (Excel R22 Length=6 — 명시적으로 거부) |
| `nxt_enable` 게이팅 | **N** (응답에서 nxt_enable 정보를 받음 — source 역할) |
| `mrkt_tp` 별 분리 호출 | N (단건이라 mrkt_tp 파라미터 없음) |
| KRX 운영 / 모의 차이 | mockapi.kiwoom.com 호출 가능. 단 응답 `nxtEnable` 는 mock 에서 무의미 → mock 환경 강제 false |

### 4.1 mock 환경 처리

ka10099 와 동일 정책 (endpoint-03 § 4.2):

```python
if settings.kiwoom_default_env == "mock":
    normalized = replace(normalized, nxt_enable=False)
```

### 4.2 본 endpoint 가 NXT 게이팅의 source 역할도 한다

ka10099 가 누락한 종목(예: 신규 상장)의 NXT 가능 여부도 본 endpoint 호출 결과로 결정된다. UseCase 의 lazy fetch 흐름:

```
다른 endpoint 응답에서 stock_code="900260" 등장
   └→ Stock(stock_code="900260") 조회 → 없음
       └→ ka10100 호출 stk_cd="900260"
           └→ 응답 nxtEnable="Y" → stock 테이블 INSERT (nxt_enable=true)
               └→ Phase C ka10081 NXT 호출 큐에 자동 등록
```

---

## 5. DB 스키마

### 5.1 신규 테이블

**없음**. ka10099 가 정의한 `kiwoom.stock` 테이블에 같은 row 를 INSERT/UPDATE.

### 5.2 INSERT vs UPDATE 정책

| 시나리오 | 동작 |
|----------|------|
| `stock_code` 가 stock 에 없음 | INSERT — `is_active=true`, `nxt_enable=` 응답값 |
| `stock_code` 가 stock 에 있음 | UPDATE — 모든 필드 갱신, `is_active=true` 복원, `fetched_at` 현재 |
| `stock_code` 가 `is_active=false` 였음 | UPDATE — 응답에 등장했으므로 활성화 복원 |
| 응답 `return_code != 0` (예: 존재하지 않는 종목) | UseCase 가 INSERT 안 함 + caller 에 `KiwoomBusinessError` 전달 |

→ ka10099 의 `upsert_many` 와 같은 Repository 메서드를 단건으로 호출. **단건 전용 메서드는 추가 안 함**.

### 5.3 디액티베이션 정책

본 endpoint 는 **단건이므로 디액티베이션 안 함**. 활성화만 한다 (응답에 등장한 종목 = 살아있음). 디액티베이션은 ka10099 의 시장 단위 sync 가 책임.

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomStkInfoClient.lookup_stock`

```python
# app/adapter/out/kiwoom/stkinfo.py (ka10099 와 같은 클래스)
class KiwoomStkInfoClient:
    PATH = "/api/dostk/stkinfo"

    async def lookup_stock(self, stk_cd: str) -> StockLookupResponse:
        """단건 종목 조회. _NX/_AL suffix 거부."""
        if not (len(stk_cd) == 6 and stk_cd.isdigit()):
            raise ValueError(f"ka10100 stk_cd 는 6자리 숫자만 허용: {stk_cd}")

        result = await self._client.call(
            api_id="ka10100",
            endpoint=self.PATH,
            body={"stk_cd": stk_cd},
        )
        parsed = StockLookupResponse.model_validate(result.body)
        if parsed.return_code != 0:
            raise KiwoomBusinessError(
                api_id="ka10100",
                return_code=parsed.return_code,
                return_msg=parsed.return_msg,
            )
        return parsed
```

### 6.2 Repository — ka10099 와 공유

`StockRepository.upsert_many([single_normalized])` 또는 별도 단건 메서드 추가:

```python
class StockRepository:
    # ... ka10099 의 메서드들

    async def upsert_one(self, row: NormalizedStock) -> Stock:
        """단건 upsert. INSERT 시 stock 반환 (auto id 채움)."""
        stmt = pg_insert(Stock).values(
            stock_code=row.stock_code,
            stock_name=row.stock_name,
            list_count=row.list_count,
            audit_info=row.audit_info,
            listed_date=row.listed_date,
            last_price=row.last_price,
            state=row.state,
            market_code=row.market_code,
            market_name=row.market_name,
            up_name=row.up_name,
            up_size_name=row.up_size_name,
            company_class_name=row.company_class_name,
            order_warning=row.order_warning,
            nxt_enable=row.nxt_enable,
            is_active=True,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_code"],
            set_={
                "stock_name": stmt.excluded.stock_name,
                "list_count": stmt.excluded.list_count,
                "audit_info": stmt.excluded.audit_info,
                "listed_date": stmt.excluded.listed_date,
                "last_price": stmt.excluded.last_price,
                "state": stmt.excluded.state,
                "market_code": stmt.excluded.market_code,
                "market_name": stmt.excluded.market_name,
                "up_name": stmt.excluded.up_name,
                "up_size_name": stmt.excluded.up_size_name,
                "company_class_name": stmt.excluded.company_class_name,
                "order_warning": stmt.excluded.order_warning,
                "nxt_enable": stmt.excluded.nxt_enable,
                "is_active": True,
                "fetched_at": func.now(),
                "updated_at": func.now(),
            },
        ).returning(Stock)
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one()
```

### 6.3 UseCase — `LookupStockUseCase`

```python
# app/application/service/stock_master_service.py
class LookupStockUseCase:
    """단건 보강. 다음 두 방식으로 사용:
    1. CLI / API endpoint 로 명시 호출
    2. 다른 service 가 DB 미스 시 lazy 호출 (ensure_stock_exists)
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        stkinfo_client: KiwoomStkInfoClient,
        env: Literal["prod", "mock"] = "prod",
    ) -> None:
        self._session = session
        self._client = stkinfo_client
        self._repo = StockRepository(session)
        self._env = env

    async def execute(self, stock_code: str) -> Stock:
        """ka10100 호출 → upsert → 갱신된 Stock row 반환."""
        response = await self._client.lookup_stock(stock_code)
        normalized = response.to_normalized()
        if self._env == "mock":
            normalized = replace(normalized, nxt_enable=False)
        return await self._repo.upsert_one(normalized)

    async def ensure_exists(self, stock_code: str) -> Stock:
        """다른 service 의 lazy 보강 진입점.

        DB hit → 그대로 반환
        DB miss → ka10100 호출 후 INSERT
        """
        existing = await self._repo.find_by_code(stock_code)
        if existing is not None:
            return existing
        logger.info("stock_code=%s lazy fetch via ka10100", stock_code)
        return await self.execute(stock_code)
```

### 6.4 다른 Service 의 `ensure_exists` 사용 예 (Phase C 미리보기)

```python
# Phase C 의 OHLCV ingest service
class IngestDailyOhlcvUseCase:
    async def execute(self, stock_code: str, ...) -> None:
        # ka10081 호출 전 stock 마스터 보장
        stock = await self._lookup_use_case.ensure_exists(stock_code)
        if not stock.is_active:
            logger.warning("비활성 종목 %s 스킵", stock_code)
            return
        # ... ka10081 호출 + stock_price_krx INSERT
```

---

## 7. 배치 / 트리거

### 7.1 트리거 패턴

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **수동 단건 보강** | on-demand | `POST /api/kiwoom/stocks/{stock_code}/refresh` (admin) |
| **Lazy fetch** | on-demand | 다른 UseCase 가 `ensure_exists()` 호출 시 자동 |
| **누락 감지 cron** | 일 1회 KST 18:00 | ka10099 cron(17:30) 직후. 다른 endpoint 응답에 등장했으나 stock 에 없는 코드들 보강 |
| **운영 사고 복구** | on-demand | `python scripts/refresh_stock.py 005930 ...` |

### 7.2 라우터

```python
# app/adapter/web/routers/stocks.py (endpoint-03 의 router 에 추가)
@router.post(
    "/{stock_code}/refresh",
    response_model=StockOut,
    dependencies=[Depends(require_admin_key)],
)
async def refresh_stock(
    stock_code: str,
    use_case: LookupStockUseCase = Depends(get_lookup_stock_use_case),
) -> StockOut:
    """단건 종목 마스터 강제 재조회 + DB upsert.

    - stk_cd 6자리 숫자 강제 (`_NX` 접미사 거부)
    - 응답이 존재하지 않는 종목이면 400 (KiwoomBusinessError)
    """
    if not (len(stock_code) == 6 and stock_code.isdigit()):
        raise HTTPException(status_code=400, detail="stock_code 는 6자리 숫자")
    try:
        stock = await use_case.execute(stock_code)
    except KiwoomBusinessError as exc:
        raise HTTPException(
            status_code=400,
            detail={"return_code": exc.return_code, "return_msg": exc.return_msg},
        )
    return StockOut.model_validate(stock)


@router.get(
    "/{stock_code}",
    response_model=StockOut,
)
async def get_stock(
    stock_code: str,
    auto_lookup: bool = Query(default=False, description="DB 미스시 ka10100 자동 호출"),
    use_case: LookupStockUseCase = Depends(get_lookup_stock_use_case),
    session: AsyncSession = Depends(get_session),
) -> StockOut:
    """단건 조회 — DB only 또는 auto_lookup=true 시 lazy fetch."""
    repo = StockRepository(session)
    if auto_lookup:
        stock = await use_case.ensure_exists(stock_code)
    else:
        stock = await repo.find_by_code(stock_code)
        if stock is None:
            raise HTTPException(status_code=404, detail=f"stock not found: {stock_code}")
    return StockOut.model_validate(stock)
```

### 7.3 누락 감지 cron (선택)

```python
# app/batch/missing_stock_backfill_job.py
async def fire_missing_stock_backfill() -> None:
    """다른 endpoint 가 sync_log 에 기록한 미지 종목 코드들을 ka10100 으로 보강."""
    async with get_sessionmaker()() as session:
        repo = SyncLogRepository(session)
        missing = await repo.collect_unknown_stock_codes(since=date.today() - timedelta(days=1))
        if not missing:
            return
        kiwoom_client = build_kiwoom_client_for("prod-main")
        stkinfo = KiwoomStkInfoClient(kiwoom_client)
        uc = LookupStockUseCase(session, stkinfo_client=stkinfo)
        for code in missing:
            try:
                await uc.execute(code)
            except (KiwoomBusinessError, KiwoomError) as exc:
                logger.warning("ka10100 backfill 실패 %s: %s", code, exc)
        await session.commit()


scheduler.add_job(
    fire_missing_stock_backfill,
    CronTrigger(day_of_week="mon-fri", hour=18, minute=0, timezone=KST),
    id="missing_stock_backfill",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
)
```

> sync_log 테이블 추가는 **Phase B 범위 외**. 본 endpoint 는 lazy ensure_exists 만 보장하고, 누락 감지 cron 은 Phase C 진입 후 결정.

---

## 8. 에러 처리

| HTTP / 응답 | 도메인 예외 | 라우터 매핑 | UseCase 정책 |
|-------------|-------------|-------------|--------------|
| 400 (잘못된 stk_cd 형식) | `ValueError` | 400 (HTTPException) | execute 호출 전에 차단 |
| 401 / 403 | `KiwoomCredentialRejectedError` | 400 | bubble up |
| 429 | tenacity 재시도 → 한계시 `KiwoomRateLimitedError` | 503 | bubble up |
| 5xx, 네트워크 | `KiwoomUpstreamError` | 502 | bubble up |
| `return_code != 0` (존재하지 않는 종목) | `KiwoomBusinessError` | 400 + detail | ensure_exists 의 caller 가 처리 결정 |
| 응답에 `code` 가 빈 값 | `KiwoomResponseValidationError` | 502 | bubble up |
| Lazy ensure_exists 시 ka10100 실패 | KiwoomError 그대로 | caller 에 따라 다름 | Phase C 의 호출자가 그 종목 skip 결정 |

### 8.1 `return_code != 0` 의 의미

| return_code | 의미 추정 (운영 검증 필요) | 처리 |
|-------------|--------------------------|------|
| 0 | 정상 | upsert |
| 1+ | 비즈니스 에러 (존재하지 않는 종목 / 권한 / 일시 점검) | KiwoomBusinessError raise. UseCase 가 swallow 하지 않음 — caller 가 결정 |

→ 예: Phase C 호출자가 ensure_exists 에서 `KiwoomBusinessError` 받으면 그 종목을 skip + 별도 로그.

### 8.2 Lazy fetch 의 race condition

같은 stock_code 를 두 service 가 동시에 ensure_exists 호출하면:

```
T1: find_by_code("005930") → None
T2: find_by_code("005930") → None
T1: ka10100 호출 → upsert_one (INSERT)
T2: ka10100 호출 → upsert_one (UPDATE)   ← ON CONFLICT 안전
```

→ ON CONFLICT (stock_code) DO UPDATE 가 race 를 흡수. 단 ka10100 이 두 번 호출되어 RPS 를 낭비함 → 빈도 낮으면 무시. 빈도 높으면 distributed lock 필요 (Phase B 범위 외).

---

## 9. 테스트

### 9.1 Unit (MockTransport)

`tests/adapter/kiwoom/test_stkinfo_lookup.py`:

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 단건 | stk_cd="005930" + 200 + 정상 응답 | `StockLookupResponse` 정상 파싱 |
| 응답 nxtEnable="Y" | 정상 | `to_normalized().nxt_enable=True` |
| 응답 nxtEnable="" | 정상 | `to_normalized().nxt_enable=False` |
| 응답 nxtEnable="N" | 정상 | `to_normalized().nxt_enable=False` |
| `return_code=1` | 비즈니스 에러 | `KiwoomBusinessError(return_code=1)` |
| 401 | 자격증명 거부 | `KiwoomCredentialRejectedError` |
| stk_cd="00593" (5자리) | 호출 차단 | `ValueError` (httpx 호출 안 함) |
| stk_cd="005930_NX" (suffix) | 호출 차단 | `ValueError` |
| stk_cd="ABC123" (영문 포함) | 호출 차단 | `ValueError` |
| 응답 `code=""` | 200 + 빈 응답 | `KiwoomResponseValidationError` (Pydantic min_length=1) |
| 응답 `regDay="invalid"` | 200 | `to_normalized().listed_date=None` |

### 9.2 Integration (testcontainers)

`tests/application/test_lookup_stock_service.py`:

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| INSERT (DB miss) | stock 테이블 비어있음 + 정상 응답 | row 1 INSERT, returned Stock.id 채워짐 |
| UPDATE (DB hit) | stock 에 같은 code 존재 (구 데이터) + 응답 갱신값 | row 갱신, `updated_at` 변경 |
| 비활성화 종목 재활성화 | 기존 row.is_active=false → 응답 등장 | `is_active=true` 복원 |
| `ensure_exists` DB hit | stock 테이블에 이미 존재 | ka10100 호출 안 함 (mock spy 0회) |
| `ensure_exists` DB miss | stock 비어있음 | ka10100 호출 + INSERT |
| ensure_exists 의 ka10100 실패 | 502 응답 | KiwoomError raise (DB 변경 없음) |
| 같은 code 동시 ensure_exists 2회 | 병렬 호출 | 두 호출 모두 성공, ON CONFLICT 로 UPDATE, row 1개 |
| mock 환경 강제 false | env="mock" + nxtEnable="Y" | DB nxt_enable=False |
| return_code=1 (존재하지 않는 종목) | 200 + return_code=1 | KiwoomBusinessError raise, INSERT 안 됨 |

### 9.3 E2E (요청 시 1회)

```python
@pytest.mark.requires_kiwoom_real
async def test_real_stock_lookup():
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

        # 삼성전자 — KOSPI 대형주, NXT 가능
        samsung = await stkinfo.lookup_stock("005930")
        assert samsung.code == "005930"
        assert samsung.name == "삼성전자"
        assert samsung.return_code == 0
        # nxtEnable 가 운영에서 Y 인지 확인
        assert samsung.nxtEnable.upper() in ("Y", "")    # 빈값일 수도

        # 존재하지 않는 종목
        with pytest.raises(KiwoomBusinessError) as exc:
            await stkinfo.lookup_stock("999999")
        assert exc.value.return_code != 0
    finally:
        async with KiwoomAuthClient(base_url="https://api.kiwoom.com") as auth:
            await auth.revoke_token(creds, token.token)
```

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `app/adapter/out/kiwoom/stkinfo.py` 의 `KiwoomStkInfoClient.lookup_stock`
- [ ] `app/adapter/out/kiwoom/_records.py` 의 `StockLookupResponse` (StockListRow 와 90% 공유)
- [ ] `app/adapter/out/persistence/repositories/stock.py` 의 `StockRepository.upsert_one`, `find_by_code`
- [ ] `app/application/service/stock_master_service.py` 의 `LookupStockUseCase` (`execute` + `ensure_exists`)
- [ ] `app/adapter/web/routers/stocks.py` 의 `GET /api/kiwoom/stocks/{stock_code}` + `POST .../refresh`
- [ ] DI: `get_lookup_stock_use_case` Depends factory

### 10.2 테스트

- [ ] Unit 11 시나리오 (§9.1) PASS
- [ ] Integration 9 시나리오 (§9.2) PASS
- [ ] coverage `KiwoomStkInfoClient.lookup_stock`, `LookupStockUseCase` ≥ 80%

### 10.3 운영 검증

- [ ] 삼성전자(`005930`) 호출 → 응답 14 필드 모두 채워져 있음
- [ ] ETF(`069500` KODEX 200) 호출 가능 여부 — `companyClassName`/`upName` 비어 있을 수도
- [ ] 코스닥 종목(`035720` 카카오) 호출 → `companyClassName="외국기업"` 등 코스닥 전용 필드 등장
- [ ] 존재하지 않는 종목(`999999`) 호출 시 응답 패턴 확인 — `return_code != 0` 또는 빈 응답?
- [ ] NXT 가능 종목의 `nxtEnable="Y"` 등장 확인 (ka10099 응답과 일치)
- [ ] mock 도메인 호출 시 `nxtEnable` 응답 패턴 (빈값 / "N" / 그냥 "Y" 도 응답?)
- [ ] 응답 시간 측정 (단건이라 < 200ms 예상. 500ms 초과 시 timeout 조정)

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10100 stock single lookup + ensure_exists lazy fetch`
- [ ] `master.md` § 12 결정 기록에 mock 환경 nxtEnable 응답 패턴, 존재하지 않는 종목 응답 코드 메모

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | `ensure_exists` 의 lock 전략 | (a) 없음 — race 시 ka10100 중복 호출 (현재 설계) / (b) `asyncio.Lock` per stock_code 캐시 | 동시 호출 빈도 운영 측정 후 |
| 2 | 누락 감지 cron 도입 시점 | (a) Phase B 본 endpoint (b) Phase C 후 (권장) | Phase C 후 |
| 3 | 존재하지 않는 종목 응답 패턴 | DoD § 10.3 운영 검증 | 본 endpoint 코드화 시점 |
| 4 | mock 환경에서 ka10100 호출 허용 여부 | (a) 허용 + nxt_enable 강제 false (권장, ka10099 와 동일) / (b) prod 만 | Phase A 후반 |
| 5 | `_NX`/`_AL` suffix 거부 vs 허용 | (a) 거부 (현재 — 순수 마스터) / (b) 허용 후 base code 만 추출 | 권장: (a) |

### 11.2 알려진 위험

- **응답 스키마가 ka10099 의 list[] row 와 미세하게 다를 가능성**: Excel R28~R41 에 명시된 14 필드 외에 단건 응답에만 등장하는 필드가 있을 수도 (예: 상장 주관사, 결산월). 첫 호출에서 raw response 검증 필수
- **`return_code` 위치**: ka10099 는 list 와 같은 레벨, ka10100 도 flat object 의 같은 레벨. 둘 다 root 에 있다고 가정 — 검증 필요
- **존재하지 않는 종목 응답 패턴 미확정**: `return_code != 0` 인지, 200 + 모든 필드 빈값인지, 4xx 인지 운영 검증 필요. 처리 분기가 달라짐
- **ETF/ETN/ELW 응답 빈 필드 비율**: `upName`, `upSizeName`, `auditInfo` 가 ETF 에서는 모두 빈값일 가능성 → `min_length=1` 검증 약화 필요할 수도
- **`stk_cd` Length=6 제약**: Excel R22 에서 명시. 그러나 일부 신주인수권/하이일드펀드는 7자리일 가능성 — 운영에서 발견되면 length 완화 필요
- **lazy fetch 가 RPS 폭주 트리거**: Phase F 순위 응답에 미지 종목이 100건 등장하면 ka10100 100회 연속 호출 → master.md § 6.3 의 RPS 4 + 250ms 가드 필수
- **race condition 시 중복 호출**: §8.2 — 빈도 낮으면 무시. Phase C 진입 후 트래픽 측정으로 결정

### 11.3 ka10099 와의 코드 공유

| 자산 | 공유 여부 |
|------|-----------|
| `NormalizedStock` dataclass | **Y** (완전 동일) |
| `_parse_yyyymmdd` helper | **Y** |
| `Stock` ORM 모델 | **Y** (같은 테이블) |
| `StockRepository.upsert_one` / `upsert_many` | **분리** (단건 vs 다건 — 두 메서드 모두 같은 테이블) |
| `KiwoomStkInfoClient` 클래스 | **Y** (같은 클래스의 두 메서드) |
| Pydantic raw row 모델 | **분리** (`StockListRow` vs `StockLookupResponse` — 응답 구조가 다름) |
| 라우터 | **공유** (`/api/kiwoom/stocks/...` 같은 prefix) |

→ Repository 와 ORM 은 ka10099 가 정의. 본 endpoint 는 추가 메서드만.

### 11.4 향후 확장

- **재시도 전 캐시 hit 검증**: ensure_exists 가 ka10100 호출하기 전에 in-memory dict cache (TTL 5분) 으로 race 흡수 — Phase B 범위 외
- **stock 변경 history**: `stock_history` 테이블에 audit_info, state, last_price 변동을 row 추가 — 백테스팅 1차에는 불필요
- **bulk lookup**: 여러 stock_code 를 단일 호출로 배칭 — 키움 API 가 지원하지 않으므로 application 레이어 throttle (RPS 4) 만 가능

---

_Phase B 의 두 번째 endpoint. ka10099 의 gap-filler. Phase C 의 시계열 수집이 미지 종목을 만났을 때 안전망 역할을 한다. 본 endpoint 가 안정적으로 동작해야 Phase C 의 daily ohlcv 가 신규 상장 종목을 무중단으로 흡수할 수 있다._
