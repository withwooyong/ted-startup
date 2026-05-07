# endpoint-19-ka10030.md — 당일거래량상위요청

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10030` |
| API 명 | 당일거래량상위요청 |
| 분류 | Tier 6 (순위) |
| Phase | **F** |
| 우선순위 | **P2** |
| Method | `POST` |
| URL | `/api/dostk/rkinfo` |
| 의존 endpoint | `au10001`, `ka10099` |
| 후속 endpoint | (Phase F 내 다른 ranking) |

> **Phase F reference 는 endpoint-18-ka10027.md**. 본 계획서는 **차이점만** 기술 — 5 endpoint 공유 인프라 (KiwoomRkInfoClient / ranking_snapshot / RankingType enum) 는 그대로 사용.

---

## 1. 목적

**당일 거래량 상위 종목 스냅샷**. ka10027 (등락률) 보다 더 wide 한 응답 (23 필드) — **장중/장후/장전 시간대별 거래량 분리** 가 핵심.

1. **거래량 시그널** — 일별 거래량 spike 종목 탐지
2. **시간대 분리** — 정규장 (`opmr_*`) / 장후 시간외 (`af_mkrt_*`) / 장전 시간외 (`bf_mkrt_*`) 거래량 비교
3. **거래회전율 (`trde_tern_rt`)** — 거래량 / 상장주식수 → 종목 활성도 직접 지표

**ka10027 와 차이**:
- 응답 list 키 = `tdy_trde_qty_upper`
- 응답 필드 23개 (장중/장후/장전 거래량 wide)
- sort_tp = `1`:거래량 / `2`:거래회전율 / `3`:거래대금 (3종)
- Body 필터 = 9 필드 (mrkt_tp, sort_tp, mang_stk_incls, crd_tp, trde_qty_tp, pric_tp, trde_prica_tp, mrkt_open_tp, stex_tp)
- **`returnCode` / `returnMsg` (camelCase!)** — Excel 예시. ka10027 의 `return_code` / `return_msg` 와 다름 → **운영 검증 1순위**

---

## 2. Request 명세

### 2.1 Body

| Element | 한글명 | Required | Length | Description |
|---------|-------|----------|--------|-------------|
| `mrkt_tp` | 시장구분 | Y | 3 | `000`/`001`/`101` |
| `sort_tp` | 정렬구분 | Y | 1 | `1`:거래량 / `2`:거래회전율 / `3`:거래대금 |
| `mang_stk_incls` | 관리종목포함 | Y | 1 | `0`:포함 / `1`:미포함 / 외 12종 (Excel 명세) |
| `crd_tp` | 신용구분 | Y | 1 | `0`:전체 / `1`~`4`:A~D / `8`:대주 / `9`:전체 |
| `trde_qty_tp` | 거래량구분 | Y | 1 | `0`:전체 / `5`:5천주 / `10`:1만 / 외 |
| `pric_tp` | 가격구분 | Y | 1 | `0`:전체 / `1`~`10` |
| `trde_prica_tp` | 거래대금구분 | Y | 1 | `0`:전체 / 외 |
| `mrkt_open_tp` | 장운영구분 | Y | 1 | `0`:전체 / `1`:장중 / `2`:장전시간외 / `3`:장후시간외 |
| `stex_tp` | 거래소구분 | Y | 1 | `1`/`2`/`3` |

### 2.2 Pydantic

```python
class TodayVolumeSortType(StrEnum):
    VOLUME = "1"
    TURNOVER_RATE = "2"
    TRADE_AMOUNT = "3"


class MarketOpenType(StrEnum):
    """ka10030 만의 mrkt_open_tp."""
    ALL = "0"
    INTRADAY = "1"               # 장중
    BEFORE_MARKET = "2"          # 장전시간외
    AFTER_MARKET = "3"           # 장후시간외


class TodayVolumeUpperRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    mrkt_tp: RankingMarketType
    sort_tp: TodayVolumeSortType
    mang_stk_incls: str
    crd_tp: Literal["0", "1", "2", "3", "4", "8", "9"]
    trde_qty_tp: str
    pric_tp: str
    trde_prica_tp: str
    mrkt_open_tp: MarketOpenType
    stex_tp: RankingExchangeType
```

---

## 3. Response 명세 (23 필드)

### 3.1 Body

| Element | 한글명 | 영속화 | 메모 |
|---------|-------|--------|------|
| `tdy_trde_qty_upper[]` | 당일거래량상위 list | (전체 row) | **list key 명** |
| `stk_cd` | 종목코드 | stock_id (FK) + stock_code_raw (NXT 보존) | |
| `stk_nm` | 종목명 | payload | 디버그 |
| `cur_prc` | 현재가 | payload (BIGINT, 부호) | |
| `pred_pre_sig` | 전일대비기호 | payload | |
| `pred_pre` | 전일대비 | payload (BIGINT, 부호) | |
| `flu_rt` | 등락률 | payload (Decimal, 부호) | |
| `trde_qty` | 거래량 | **`primary_metric` (BIGINT)** | sort_tp=1 시 정렬 기준 |
| `pred_rt` | 전일비 | payload (Decimal, 부호) | 거래량 / 전일거래량 비율 |
| `trde_tern_rt` | 거래회전율 | payload (Decimal, 부호) | sort_tp=2 시 정렬 기준 |
| `trde_amt` | 거래금액 | payload (BIGINT) | sort_tp=3 시 정렬 기준 (백만원 추정) |
| `opmr_trde_qty` | 장중거래량 | payload | mrkt_open_tp=1 분리 |
| `opmr_pred_rt` | 장중전일비 | payload | |
| `opmr_trde_rt` | 장중거래회전율 | payload | |
| `opmr_trde_amt` | 장중거래금액 | payload | |
| `af_mkrt_trde_qty` | 장후거래량 | payload | mrkt_open_tp=3 분리 |
| `af_mkrt_pred_rt` | 장후전일비 | payload | |
| `af_mkrt_trde_rt` | 장후거래회전율 | payload | |
| `af_mkrt_trde_amt` | 장후거래금액 | payload | |
| `bf_mkrt_trde_qty` | 장전거래량 | payload | mrkt_open_tp=2 분리 |
| `bf_mkrt_pred_rt` | 장전전일비 | payload | |
| `bf_mkrt_trde_rt` | 장전거래회전율 | payload | |
| `bf_mkrt_trde_amt` | 장전거래금액 | payload | |
| **`returnCode`** | 처리코드 | (raw_response only) | **★ camelCase** — ka10027 의 `return_code` 와 다름 |
| **`returnMsg`** | 처리메시지 | (raw_response only) | **★ camelCase** |

> **★ camelCase 응답 필드 (returnCode/returnMsg)**: Excel 예시 그대로. 같은 카테고리 내 일관성 깨짐 — 운영 검증 1순위. Pydantic 모델은 `Field(alias="returnCode")` 로 두 표기 모두 흡수.

### 3.2 Response 예시 (Excel, 일부)

```json
{
    "tdy_trde_qty_upper": [
        {
            "stk_cd": "005930",
            "stk_nm": "삼성전자",
            "cur_prc": "-152000",
            "pred_pre_sig": "5",
            "pred_pre": "-100",
            "flu_rt": "-0.07",
            "trde_qty": "34954641",
            "pred_rt": "+155.13",
            "trde_tern_rt": "+48.21",
            "trde_amt": "5308092",
            "opmr_trde_qty": "0",
            "opmr_pred_rt": "0.00",
            "opmr_trde_rt": "+0.00",
            "opmr_trde_amt": "0",
            "af_mkrt_trde_qty": "0",
            "af_mkrt_pred_rt": "0.00",
            "af_mkrt_trde_rt": "+0.00",
            "af_mkrt_trde_amt": "0",
            "bf_mkrt_trde_qty": "0",
            "bf_mkrt_pred_rt": "0.00",
            "bf_mkrt_trde_rt": "+0.00",
            "bf_mkrt_trde_amt": "0"
        }
    ],
    "returnCode": 0,
    "returnMsg": "정상적으로 처리되었습니다"
}
```

> Excel 예시의 모든 row 의 `opmr_/af_mkrt_/bf_mkrt_` 값이 0 — sync 시점 (장중/장후/장전 분리 미발효) 가능성. 운영 검증으로 실제 분리값 확인.

### 3.3 Pydantic + 정규화

```python
class TodayVolumeUpperRow(BaseModel):
    """ka10030 응답 row — 23 필드."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    stk_cd: str = ""
    stk_nm: str = ""
    cur_prc: str = ""
    pred_pre_sig: str = ""
    pred_pre: str = ""
    flu_rt: str = ""
    trde_qty: str = ""
    pred_rt: str = ""
    trde_tern_rt: str = ""
    trde_amt: str = ""
    opmr_trde_qty: str = ""
    opmr_pred_rt: str = ""
    opmr_trde_rt: str = ""
    opmr_trde_amt: str = ""
    af_mkrt_trde_qty: str = ""
    af_mkrt_pred_rt: str = ""
    af_mkrt_trde_rt: str = ""
    af_mkrt_trde_amt: str = ""
    bf_mkrt_trde_qty: str = ""
    bf_mkrt_pred_rt: str = ""
    bf_mkrt_trde_rt: str = ""
    bf_mkrt_trde_amt: str = ""

    def to_payload(self) -> dict[str, Any]:
        """JSONB payload — 23 필드 모두 보관."""
        return {
            "stk_nm": self.stk_nm,
            "cur_prc": _to_int(self.cur_prc),
            "pred_pre_sig": self.pred_pre_sig or None,
            "pred_pre": _to_int(self.pred_pre),
            "flu_rt": _to_decimal_str(self.flu_rt),
            "pred_rt": _to_decimal_str(self.pred_rt),
            "trde_tern_rt": _to_decimal_str(self.trde_tern_rt),
            "trde_amt": _to_int(self.trde_amt),
            "opmr_trde_qty": _to_int(self.opmr_trde_qty),
            "opmr_pred_rt": _to_decimal_str(self.opmr_pred_rt),
            "opmr_trde_rt": _to_decimal_str(self.opmr_trde_rt),
            "opmr_trde_amt": _to_int(self.opmr_trde_amt),
            "af_mkrt_trde_qty": _to_int(self.af_mkrt_trde_qty),
            "af_mkrt_pred_rt": _to_decimal_str(self.af_mkrt_pred_rt),
            "af_mkrt_trde_rt": _to_decimal_str(self.af_mkrt_trde_rt),
            "af_mkrt_trde_amt": _to_int(self.af_mkrt_trde_amt),
            "bf_mkrt_trde_qty": _to_int(self.bf_mkrt_trde_qty),
            "bf_mkrt_pred_rt": _to_decimal_str(self.bf_mkrt_pred_rt),
            "bf_mkrt_trde_rt": _to_decimal_str(self.bf_mkrt_trde_rt),
            "bf_mkrt_trde_amt": _to_int(self.bf_mkrt_trde_amt),
        }


class TodayVolumeUpperResponse(BaseModel):
    """★ camelCase 키 처리."""
    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
        populate_by_name=True,    # alias + 원본 둘 다 허용
    )
    tdy_trde_qty_upper: list[TodayVolumeUpperRow] = Field(default_factory=list)
    return_code: int = Field(default=0, alias="returnCode")
    return_msg: str = Field(default="", alias="returnMsg")


def primary_metric_of_today_volume(
    sort_tp: TodayVolumeSortType, row: TodayVolumeUpperRow,
) -> Decimal | None:
    """sort_tp 별로 다른 정렬 기준 metric."""
    if sort_tp is TodayVolumeSortType.VOLUME:
        v = _to_int(row.trde_qty)
        return Decimal(v) if v is not None else None
    if sort_tp is TodayVolumeSortType.TURNOVER_RATE:
        return _to_decimal(row.trde_tern_rt)
    if sort_tp is TodayVolumeSortType.TRADE_AMOUNT:
        v = _to_int(row.trde_amt)
        return Decimal(v) if v is not None else None
    return None
```

> **`primary_metric` 분기**: ka10027 와 달리 `sort_tp` 별로 다른 필드. UseCase 가 호출 시 sort_tp 받아 그 metric 추출.

---

## 4. NXT 처리

ka10027 동일. mrkt_tp + stex_tp 매트릭스. 운영 default = `mrkt_tp ∈ {001, 101}` × `stex_tp = 3` × `sort_tp ∈ {1}` (거래량 만) = 2 호출.

---

## 5. DB 스키마

ka10027 의 `ranking_snapshot` 테이블 재사용. `ranking_type=TODAY_VOLUME` 으로 분기. **새 테이블 / 마이그레이션 없음**.

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomRkInfoClient.fetch_today_volume_upper`

```python
class KiwoomRkInfoClient:
    # fetch_flu_rt_upper 는 ka10027 endpoint-18 참조

    async def fetch_today_volume_upper(
        self,
        *,
        market_type: RankingMarketType = RankingMarketType.ALL,
        sort_tp: TodayVolumeSortType = TodayVolumeSortType.VOLUME,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        mang_stk_incls: str = "0",
        crd_tp: str = "0",
        trde_qty_tp: str = "0",
        pric_tp: str = "0",
        trde_prica_tp: str = "0",
        mrkt_open_tp: MarketOpenType = MarketOpenType.ALL,
        max_pages: int = 5,
    ) -> tuple[list[TodayVolumeUpperRow], dict[str, Any]]:
        body = {
            "mrkt_tp": market_type.value,
            "sort_tp": sort_tp.value,
            "mang_stk_incls": mang_stk_incls,
            "crd_tp": crd_tp,
            "trde_qty_tp": trde_qty_tp,
            "pric_tp": pric_tp,
            "trde_prica_tp": trde_prica_tp,
            "mrkt_open_tp": mrkt_open_tp.value,
            "stex_tp": exchange_type.value,
        }

        all_rows: list[TodayVolumeUpperRow] = []
        async for page in self._client.call_paginated(
            api_id="ka10030",
            endpoint=self.PATH,
            body=body,
            max_pages=max_pages,
        ):
            parsed = TodayVolumeUpperResponse.model_validate(page.body)
            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id="ka10030",
                    return_code=parsed.return_code,
                    return_msg=parsed.return_msg,
                )
            all_rows.extend(parsed.tdy_trde_qty_upper)

        return all_rows, body
```

### 6.2 UseCase — `IngestTodayVolumeUpperUseCase`

```python
class IngestTodayVolumeUpperUseCase:
    """ka10030 — 당일 거래량 상위. ka10027 의 IngestFluRtUpperUseCase 와 동일 패턴."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        rkinfo_client: KiwoomRkInfoClient,
        stock_repo: StockRepository,
    ) -> None:
        self._session = session
        self._client = rkinfo_client
        self._stock_repo = stock_repo
        self._repo = RankingSnapshotRepository(session)

    async def execute(
        self,
        *,
        snapshot_at: datetime,
        market_type: RankingMarketType = RankingMarketType.KOSPI,
        sort_tp: TodayVolumeSortType = TodayVolumeSortType.VOLUME,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        mrkt_open_tp: MarketOpenType = MarketOpenType.ALL,
        **filters: Any,
    ) -> RankingIngestOutcome:
        try:
            raw_rows, used_filters = await self._client.fetch_today_volume_upper(
                market_type=market_type,
                sort_tp=sort_tp,
                exchange_type=exchange_type,
                mrkt_open_tp=mrkt_open_tp,
                **filters,
            )
        except KiwoomBusinessError as exc:
            return RankingIngestOutcome(
                ranking_type=RankingType.TODAY_VOLUME, snapshot_at=snapshot_at,
                upserted=0, error=f"business: {exc.return_code}",
            )

        # ka10027 동일 패턴 — stk_cd 매핑 + NormalizedRanking 생성
        stock_codes_clean = [strip_kiwoom_suffix(r.stk_cd) for r in raw_rows]
        stocks_by_code = await self._stock_repo.find_by_codes(stock_codes_clean)

        normalized = []
        for rank, raw_row in enumerate(raw_rows, start=1):
            code_clean = strip_kiwoom_suffix(raw_row.stk_cd)
            stock = stocks_by_code.get(code_clean)
            payload = raw_row.to_payload()
            payload["stk_cd_raw"] = raw_row.stk_cd

            normalized.append(NormalizedRanking(
                snapshot_date=snapshot_at.date(),
                snapshot_time=snapshot_at.time().replace(microsecond=0),
                ranking_type=RankingType.TODAY_VOLUME,
                sort_tp=sort_tp.value,
                market_type=market_type.value,
                exchange_type=exchange_type.value,
                rank=rank,
                stock_id=stock.id if stock else None,
                primary_metric=primary_metric_of_today_volume(sort_tp, raw_row),
                payload=payload,
                request_filters=used_filters,
            ))

        upserted = await self._repo.upsert_many(normalized)

        return RankingIngestOutcome(
            ranking_type=RankingType.TODAY_VOLUME,
            snapshot_at=snapshot_at,
            sort_tp=sort_tp.value,
            market_type=market_type.value,
            exchange_type=exchange_type.value,
            fetched=len(raw_rows), upserted=upserted,
        )
```

### 6.3 Bulk — `IngestTodayVolumeUpperBulkUseCase`

ka10027 의 BulkUseCase 와 같은 패턴. 운영 default = `mrkt_tp ∈ {001, 101}` × `sort_tp ∈ {1}` (거래량만) = 2 호출.

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **수동 단건** | on-demand | `POST /api/kiwoom/rankings/today-volume?market_type=001&sort_tp=1` (admin) |
| **수동 bulk** | on-demand | `POST /api/kiwoom/rankings/today-volume/sync` (admin) |
| **일 1회 cron** | KST 19:35 평일 | ka10027 (19:30) 직후 |

### 7.1 라우터 추가 (rankings.py 의 ka10027 라우터에)

```python
@router.post(
    "/today-volume",
    response_model=RankingIngestOutcomeOut,
    dependencies=[Depends(require_admin_key)],
)
async def ingest_today_volume(
    snapshot_at: datetime = Query(default_factory=lambda: datetime.now(KST)),
    market_type: Literal["000", "001", "101"] = Query(default="000"),
    sort_tp: Literal["1", "2", "3"] = Query(default="1"),
    exchange_type: Literal["1", "2", "3"] = Query(default="3"),
    mrkt_open_tp: Literal["0", "1", "2", "3"] = Query(default="0"),
    use_case: IngestTodayVolumeUpperUseCase = Depends(get_ingest_today_volume_use_case),
) -> RankingIngestOutcomeOut:
    outcome = await use_case.execute(
        snapshot_at=snapshot_at,
        market_type=RankingMarketType(market_type),
        sort_tp=TodayVolumeSortType(sort_tp),
        exchange_type=RankingExchangeType(exchange_type),
        mrkt_open_tp=MarketOpenType(mrkt_open_tp),
    )
    return RankingIngestOutcomeOut.model_validate(asdict(outcome))


# /sync 엔드포인트 + GET 조회는 ka10027 와 같은 패턴
```

### 7.2 APScheduler Job

```python
# app/batch/ranking_jobs.py 에 추가
async def fire_today_volume_sync() -> None:
    """매 평일 19:35 KST."""
    today = date.today()
    if not is_trading_day(today):
        return
    try:
        snapshot_at = datetime.now(KST)
        async with get_sessionmaker()() as session:
            kiwoom_client = build_kiwoom_client_for("prod-main")
            rkinfo = KiwoomRkInfoClient(kiwoom_client)
            stock_repo = StockRepository(session)
            single = IngestTodayVolumeUpperUseCase(
                session, rkinfo_client=rkinfo, stock_repo=stock_repo,
            )
            bulk = IngestTodayVolumeUpperBulkUseCase(session, single_use_case=single)
            outcomes = await bulk.execute(snapshot_at=snapshot_at)
        success = sum(1 for o in outcomes if o.error is None)
        logger.info(
            "today volume sync 완료 success=%d/%d at=%s",
            success, len(outcomes), snapshot_at,
        )
    except Exception:
        logger.exception("today volume sync 콜백 예외")


scheduler.add_job(
    fire_today_volume_sync,
    CronTrigger(day_of_week="mon-fri", hour=19, minute=35, timezone=KST),
    id="today_volume_sync",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
    misfire_grace_time=60 * 30,
)
```

---

## 8. 에러 처리

ka10027 동일 + camelCase 응답 처리 (Pydantic alias).

---

## 9. 테스트

### 9.1 Unit

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 응답 (camelCase) | 200 + `returnCode=0` + list 50건 | 50건 반환 |
| **camelCase / snake_case 둘 다 흡수** | 200 + `return_code=0` (snake) | 50건 반환 (alias 동작) |
| sort_tp 분기 + primary_metric | sort_tp=VOLUME 호출 | primary_metric = trde_qty 값 |
| sort_tp 분기 + primary_metric | sort_tp=TURNOVER_RATE | primary_metric = trde_tern_rt 값 |
| 23 필드 to_payload | wide row | payload 에 21 필드 (stk_cd 제외) |
| mrkt_open_tp 분기 | INTRADAY | request body `mrkt_open_tp="1"` |
| 부호 포함 | flu_rt="-0.07" | `_to_decimal_str` → "-0.07" |

### 9.2 Integration

ka10027 동일 + 23 필드 payload 검증.

---

## 10. 완료 기준 (DoD)

### 10.1 코드 (ka10027 의 같은 모듈에 추가)

- [ ] `app/adapter/out/kiwoom/rkinfo.py` — `KiwoomRkInfoClient.fetch_today_volume_upper`
- [ ] `app/adapter/out/kiwoom/_records.py` — `TodayVolumeUpperRow/Response`, `TodayVolumeSortType`, `MarketOpenType`, `primary_metric_of_today_volume`
- [ ] `app/application/service/ranking_service.py` — `IngestTodayVolumeUpperUseCase`, `IngestTodayVolumeUpperBulkUseCase`
- [ ] `app/adapter/web/routers/rankings.py` — POST/GET today-volume endpoints
- [ ] `app/batch/ranking_jobs.py` — APScheduler 등록 (KST mon-fri 19:35)

### 10.2 테스트

- [ ] Unit 7 시나리오 PASS (특히 camelCase/snake_case 둘 다)
- [ ] Integration 6 시나리오 PASS (ka10027 + 23 필드 payload)

### 10.3 운영 검증

- [ ] **`returnCode` / `returnMsg` (camelCase) 응답 확정** — 운영 첫 호출에서 raw 키 확인
- [ ] **장중/장후/장전 거래량 분리값** — Excel 예시는 모두 0. 실제 응답 시점 (장중 호출) 시 분리 작동
- [ ] `trde_amt` 단위 (백만원 추정 — ka10081 동일)
- [ ] `pred_rt` (전일비) 의미 — 거래량 비율 vs 가격 비율
- [ ] `mrkt_open_tp` 분기별 응답 row 수 (`1`:장중 vs `0`:전체)
- [ ] sort_tp 별 응답 정렬 (1:거래량 desc / 2:회전율 desc / 3:거래대금 desc)

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10030 today volume upper ranking`
- [ ] `master.md` § 12 결정 기록에:
  - **`returnCode/returnMsg` camelCase 응답 일관성** (5 ranking endpoint 중 ka10030 만?)
  - 장중/장후/장전 분리값 시점

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | 운영 default sort_tp | VOLUME (현재) / VOLUME + TRADE_AMOUNT | Phase F 코드화 |
| 2 | mrkt_open_tp default | ALL (현재) / INTRADAY (장중만) | 운영 검증 후 |
| 3 | 다중 시점 sync | 19:35 (종가 후) / 장중 (13:00) 추가 | Phase F 후반 |
| 4 | mang_stk_incls default | 0 (포함) / 1 (미포함) | 운영 검증 후 |
| 5 | 응답 camelCase 처리 | alias (현재) / 변환 미들웨어 | Phase F 코드화 |

### 11.2 알려진 위험

- **★ `returnCode` / `returnMsg` camelCase**: Excel 예시만의 표기 오류일 가능성 높음. 5 ranking endpoint 중 ka10030 만 다른 표기 — 운영 첫 호출에서 raw 응답으로 확정. Pydantic `populate_by_name=True` + alias 로 두 표기 모두 흡수 — 안전망
- **장중/장후/장전 분리값 의미**: Excel 예시 모두 0. 호출 시점이 영향 — 장 종료 후 호출 시 `opmr_*` 만 채워지고 `bf_/af_` 는 0 가능. 운영 검증
- **`trde_amt` 단위**: ka10081 의 `trde_prica` 와 같은 단위 (백만원 추정) 가정. 본 endpoint 만의 차이 검증
- **`pred_rt` 가 거래량 비율인지 가격 비율인지**: Excel 명세 모호. 같은 row 의 `flu_rt` (등락률) 와 별개 — 거래량 / 전일거래량 비율 가정
- **`crd_tp` 의미가 ka10027 의 `crd_cnd` 와 다름**: 같은 신용 필터지만 파라미터명 다름. UseCase 분리 필수
- **23 필드 wide payload 의 disk 부담**: ka10027 의 12 필드 보다 ~2배. 5 ranking endpoint 중 가장 부담 큼 — 운영 1년 후 monitor
- **`mrkt_open_tp` 분리 호출의 의미**: 운영 default = ALL (전체). INTRADAY 만 호출 시 정규장 거래량만 반환 (장후/장전 0) — 시점 별 시그널 차이 검증 필요

### 11.3 ka10030 vs ka10027 차이 요약

| 항목 | ka10027 | ka10030 |
|------|---------|---------|
| 응답 list 키 | pred_pre_flu_rt_upper | tdy_trde_qty_upper |
| 응답 필드 수 | 12 | **23** (wide) |
| sort_tp 의미 | 5종 (등락률) | 3종 (거래량/회전율/대금) |
| primary_metric 분기 | 단일 (flu_rt) | sort_tp 별 분기 |
| `returnCode` 응답 표기 | snake_case | **camelCase** (Excel 표기) |
| Body 필터 수 | 9 | 9 (이름만 다름) |
| 장중/장후/장전 분리 | 없음 | **있음** (mrkt_open_tp) |

### 11.4 향후 확장

- **장중/장후/장전 시간대별 시그널**: `opmr_/af_mkrt_/bf_mkrt_` 분리 — derived feature
- **거래회전율 monitoring**: `trde_tern_rt` spike 종목 — 단기 시그널
- **다중 시점 sync**: 장 시작 (09:30) + 종가 후 (19:35) — 장중 ↔ 종가 거래량 변화

---

_Phase F 의 두 번째 endpoint. ka10027 패턴 복제 + 23 필드 wide payload + camelCase 응답 처리. 거래량 시그널의 raw source._
