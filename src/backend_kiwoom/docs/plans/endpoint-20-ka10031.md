# endpoint-20-ka10031.md — 전일거래량상위요청

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10031` |
| API 명 | 전일거래량상위요청 |
| 분류 | Tier 6 (순위) |
| Phase | **F** |
| 우선순위 | **P3** |
| Method | `POST` |
| URL | `/api/dostk/rkinfo` |
| 의존 endpoint | `au10001`, `ka10099` |

> **Phase F reference 는 endpoint-18-ka10027.md** + endpoint-19-ka10030.md (당일 거래량). 본 계획서는 **차이점만**.

---

## 1. 목적

**전일 거래량 상위 100 종목** — 어제 종가 기준 거래량 / 거래대금 순위. ka10030 (당일) 의 전일 버전.

1. **전일 활성도 시그널** — 어제 거래량 spike 종목이 오늘 추가 매매 가능성
2. **`rank_strt`/`rank_end` 페이지네이션 식 응답** — 0~100 범위 페이지 시작/끝 지정. 본 endpoint 만의 페이지네이션 패턴
3. **응답 필드 가장 단순** (6 필드) — 5 ranking endpoint 중 가장 가벼움

**ka10027/30 과 차이**:
- 응답 list 키 = `pred_trde_qty_upper`
- **응답 필드 6개** (가장 단순): stk_cd / stk_nm / cur_prc / pred_pre_sig / pred_pre / trde_qty
- Body 필드 5개 (`mrkt_tp` + `qry_tp` + `rank_strt` + `rank_end` + `stex_tp`)
- `qry_tp` = `1`:전일거래량 상위100 / `2`:전일거래대금 상위100 (ka10027 의 sort_tp 5종 / ka10030 의 3종 보다 단순)
- **`rank_strt`/`rank_end` (0~100)** — 페이지 시작/끝 명시 호출. cont-yn 페이지네이션과 다름

---

## 2. Request 명세

### 2.1 Body

| Element | 한글명 | Required | Length | Description |
|---------|-------|----------|--------|-------------|
| `mrkt_tp` | 시장구분 | Y | 3 | `000`/`001`/`101` |
| `qry_tp` | 조회구분 | Y | 1 | `1`:전일거래량 상위100 / `2`:전일거래대금 상위100 |
| `rank_strt` | 순위시작 | Y | 3 | 0~100 — 페이지 시작 |
| `rank_end` | 순위끝 | Y | 3 | 0~100 — 페이지 끝 |
| `stex_tp` | 거래소구분 | Y | 1 | `1`/`2`/`3` |

> **`rank_strt`/`rank_end` 페이지네이션 의미**: 한 호출에 100건 응답 가능 (전체) → `rank_strt=0`, `rank_end=100` 으로 한 번에 가져오기 권장. 분할 호출 시 `0~50` + `51~100` 등.

### 2.2 Pydantic

```python
class PredVolumeQueryType(StrEnum):
    PRED_VOLUME = "1"        # 전일거래량 상위100
    PRED_TRADE_AMOUNT = "2"  # 전일거래대금 상위100


class PredVolumeUpperRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    mrkt_tp: RankingMarketType
    qry_tp: PredVolumeQueryType
    rank_strt: Annotated[str, Field(pattern=r"^\d{1,3}$")]
    rank_end: Annotated[str, Field(pattern=r"^\d{1,3}$")]
    stex_tp: RankingExchangeType
```

---

## 3. Response 명세 (6 필드)

### 3.1 Body

| Element | 한글명 | 영속화 | 메모 |
|---------|-------|--------|------|
| `pred_trde_qty_upper[]` | 전일거래량상위 list | (전체 row) | **list key 명** |
| `stk_cd` | 종목코드 | stock_id (FK) + stock_code_raw | NXT `_NX` 보존 검증 |
| `stk_nm` | 종목명 | payload | |
| `cur_prc` | 현재가 | payload (BIGINT, 부호) | |
| `pred_pre_sig` | 전일대비기호 | payload | 1~5 |
| `pred_pre` | 전일대비 | payload (BIGINT, 부호) | |
| `trde_qty` | 거래량 | **`primary_metric` (BIGINT)** | qry_tp=1/2 모두 정렬 기준 (운영 검증 후 — qry_tp=2 시 거래대금 별도 필드 가능) |

### 3.2 Response 예시 (Excel 원문)

```json
{
    "pred_trde_qty_upper": [
        {
            "stk_cd": "005930",
            "stk_nm": "삼성전자",
            "cur_prc": "-43750",
            "pred_pre_sig": "5",
            "pred_pre": "-50",
            "trde_qty": "34605668"
        },
        {
            "stk_cd": "005930",
            "stk_nm": "삼성전자",
            "cur_prc": "-56600",
            "pred_pre_sig": "5",
            "pred_pre": "-100",
            "trde_qty": "33014975"
        }
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다"
}
```

> **★ 응답 정렬 의문**: Excel 예시의 일부 row 는 `cur_prc=81` / `trde_qty=0` 등 — 거래정지 / 비활성 종목이 상위에 등장. `qry_tp` 의 의미가 "전일 거래량 상위" 만이 아니라 다른 정렬 가능성. 운영 검증 1순위.

### 3.3 Pydantic + 정규화

```python
class PredVolumeUpperRow(BaseModel):
    """ka10031 응답 row — 6 필드 (가장 단순)."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    stk_cd: str = ""
    stk_nm: str = ""
    cur_prc: str = ""
    pred_pre_sig: str = ""
    pred_pre: str = ""
    trde_qty: str = ""

    def to_payload(self) -> dict[str, Any]:
        return {
            "stk_nm": self.stk_nm,
            "cur_prc": _to_int(self.cur_prc),
            "pred_pre_sig": self.pred_pre_sig or None,
            "pred_pre": _to_int(self.pred_pre),
        }


class PredVolumeUpperResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    pred_trde_qty_upper: list[PredVolumeUpperRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""
```

---

## 4. NXT 처리

ka10027/30 동일.

---

## 5. DB 스키마

ka10027 의 `ranking_snapshot` 재사용. `ranking_type=PRED_VOLUME` 분기.

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomRkInfoClient.fetch_pred_volume_upper`

```python
class KiwoomRkInfoClient:
    async def fetch_pred_volume_upper(
        self,
        *,
        market_type: RankingMarketType = RankingMarketType.ALL,
        qry_tp: PredVolumeQueryType = PredVolumeQueryType.PRED_VOLUME,
        rank_strt: int = 0,
        rank_end: int = 100,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
    ) -> tuple[list[PredVolumeUpperRow], dict[str, Any]]:
        """ka10031 — 전일 거래량 상위 100. cont-yn 페이지네이션 안 씀 (rank_strt/rank_end 로 분할).

        주의: rank_strt=0, rank_end=100 으로 한 번 호출이 일반.
        """
        body = {
            "mrkt_tp": market_type.value,
            "qry_tp": qry_tp.value,
            "rank_strt": str(rank_strt),
            "rank_end": str(rank_end),
            "stex_tp": exchange_type.value,
        }

        # cont-yn 페이지네이션 미사용 — 단일 호출
        page = await self._client.call(
            api_id="ka10031",
            endpoint=self.PATH,
            body=body,
        )
        parsed = PredVolumeUpperResponse.model_validate(page.body)
        if parsed.return_code != 0:
            raise KiwoomBusinessError(
                api_id="ka10031",
                return_code=parsed.return_code,
                return_msg=parsed.return_msg,
            )
        return parsed.pred_trde_qty_upper, body
```

### 6.2 UseCase — `IngestPredVolumeUpperUseCase`

```python
class IngestPredVolumeUpperUseCase:
    """ka10031 — 전일 거래량 상위 적재."""

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
        qry_tp: PredVolumeQueryType = PredVolumeQueryType.PRED_VOLUME,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        rank_strt: int = 0,
        rank_end: int = 100,
    ) -> RankingIngestOutcome:
        try:
            raw_rows, used_filters = await self._client.fetch_pred_volume_upper(
                market_type=market_type, qry_tp=qry_tp,
                rank_strt=rank_strt, rank_end=rank_end,
                exchange_type=exchange_type,
            )
        except KiwoomBusinessError as exc:
            return RankingIngestOutcome(
                ranking_type=RankingType.PRED_VOLUME, snapshot_at=snapshot_at,
                upserted=0, error=f"business: {exc.return_code}",
            )

        # ka10027 패턴 — stock 매핑 + NormalizedRanking
        stock_codes_clean = [strip_kiwoom_suffix(r.stk_cd) for r in raw_rows]
        stocks_by_code = await self._stock_repo.find_by_codes(stock_codes_clean)

        normalized = []
        for rank_offset, raw_row in enumerate(raw_rows, start=rank_strt + 1):
            code_clean = strip_kiwoom_suffix(raw_row.stk_cd)
            stock = stocks_by_code.get(code_clean)
            payload = raw_row.to_payload()
            payload["stk_cd_raw"] = raw_row.stk_cd

            normalized.append(NormalizedRanking(
                snapshot_date=snapshot_at.date(),
                snapshot_time=snapshot_at.time().replace(microsecond=0),
                ranking_type=RankingType.PRED_VOLUME,
                sort_tp=qry_tp.value,
                market_type=market_type.value,
                exchange_type=exchange_type.value,
                rank=rank_offset,
                stock_id=stock.id if stock else None,
                primary_metric=Decimal(_to_int(raw_row.trde_qty) or 0),
                payload=payload,
                request_filters=used_filters,
            ))

        upserted = await self._repo.upsert_many(normalized)

        return RankingIngestOutcome(
            ranking_type=RankingType.PRED_VOLUME,
            snapshot_at=snapshot_at,
            sort_tp=qry_tp.value,
            market_type=market_type.value,
            exchange_type=exchange_type.value,
            fetched=len(raw_rows), upserted=upserted,
        )
```

### 6.3 Bulk

ka10027 동일 패턴. 운영 default = `mrkt_tp ∈ {001, 101}` × `qry_tp ∈ {1, 2}` (거래량 + 거래대금) = 4 호출.

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **일 1회 cron** | KST 19:40 평일 | ka10030 (19:35) 직후 |

라우터 + APScheduler Job 은 ka10027/30 패턴 복제.

```python
scheduler.add_job(
    fire_pred_volume_sync,
    CronTrigger(day_of_week="mon-fri", hour=19, minute=40, timezone=KST),
    id="pred_volume_sync",
    ...
)
```

---

## 8. 에러 처리

ka10027 동일.

---

## 9. 테스트

### 9.1 Unit

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 응답 | 200 + list 100건 | 100건 반환 |
| 빈 list | 200 + `pred_trde_qty_upper=[]` | 빈 list |
| `return_code=1` | 비즈니스 에러 | `KiwoomBusinessError` |
| qry_tp 분기 | PRED_TRADE_AMOUNT | request body `qry_tp="2"` |
| rank_strt/rank_end 분할 | 0~50 호출 | request body `rank_strt="0", rank_end="50"` |
| **cont-yn 페이지네이션 미사용** | 단일 호출 후 종료 | call_paginated 안 호출 |

### 9.2 Integration

ka10027 패턴 + rank_strt offset 검증.

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| INSERT | rank_strt=0, list 50건 | rank 1~50 INSERT |
| 분할 호출 멱등성 | 0~50 + 51~100 두 번 호출 | 100 row INSERT, rank 1~100 |

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `app/adapter/out/kiwoom/rkinfo.py` — `KiwoomRkInfoClient.fetch_pred_volume_upper`
- [ ] `app/adapter/out/kiwoom/_records.py` — `PredVolumeUpperRow/Response`, `PredVolumeQueryType`
- [ ] `app/application/service/ranking_service.py` — `IngestPredVolumeUpperUseCase`, `IngestPredVolumeUpperBulkUseCase`
- [ ] `app/adapter/web/routers/rankings.py` — POST/GET pred-volume endpoints
- [ ] `app/batch/ranking_jobs.py` — APScheduler 등록 (KST mon-fri 19:40)

### 10.2 테스트

- [ ] Unit 6 시나리오 PASS
- [ ] Integration 5 시나리오 PASS

### 10.3 운영 검증

- [ ] **응답 정렬 의문 해결** — Excel 예시에 거래정지 종목 등장. qry_tp 의 진짜 의미 확인
- [ ] `qry_tp=2` (거래대금 상위) 응답에 거래대금 필드가 별도로 오는지 — `trde_qty` 가 거래대금으로 대체되는지
- [ ] `rank_strt`/`rank_end` 분할 호출의 응답 정렬 일관성
- [ ] cont-yn 페이지네이션 발생 가능 여부 (rank_end=100 보다 많은 응답)
- [ ] NXT 응답 row 수 (KRX 보다 적음 가정)

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10031 pred volume upper ranking`
- [ ] `master.md` § 12 결정 기록에:
  - `qry_tp=1/2` 의 응답 정렬 의미

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | 운영 default qry_tp | PRED_VOLUME 만 / VOLUME + AMOUNT 둘 (현재) | Phase F 코드화 |
| 2 | rank_strt/rank_end 정책 | 0~100 한 번 (현재) / 분할 | 운영 검증 |
| 3 | 다중 시점 sync | 1 시점 / 다중 | Phase F 후반 |

### 11.2 알려진 위험

- **Excel 예시의 거래정지 종목 등장**: `cur_prc=81`, `trde_qty=0` 같은 row 가 상위에 — qry_tp 의미가 모호 가능. 첫 호출 검증
- **`qry_tp=2` 응답 schema**: 거래대금 상위인데 응답 필드는 `trde_qty` (거래량). 거래대금 필드가 별도로 오는지 검증. 안 오면 `primary_metric` 분기 필요
- **rank_strt/rank_end 페이지네이션의 cont-yn 충돌**: 두 페이지네이션 메커니즘 동시 가능 여부. 단일 호출 가정이 안전
- **응답 row 수 제한 100**: 다른 ranking endpoint 와 같은지 명세 미지정
- **본 endpoint 의 백테스팅 가치**: ka10030 (당일) 의 전일 버전 — 시그널 가치는 ka10030 보다 낮음. P3 우선순위 (선택)

### 11.3 ka10031 vs ka10027/30 차이 요약

| 항목 | ka10027 | ka10030 | ka10031 (본) |
|------|---------|---------|---------|
| 응답 list 키 | pred_pre_flu_rt_upper | tdy_trde_qty_upper | pred_trde_qty_upper |
| 응답 필드 | 12 | 23 | **6 (가장 단순)** |
| Body 필드 | 9 | 9 | **5** |
| sort_tp 의미 | 5종 | 3종 | qry_tp 2종 |
| 페이지네이션 | cont-yn | cont-yn | **rank_strt/rank_end** |
| 우선순위 | P2 | P2 | **P3** |

### 11.4 향후 확장

- **전일 vs 당일 거래량 비교 derived feature**: ka10030 의 trde_qty 와 본 endpoint 의 trde_qty cross-reference

---

_Phase F 의 세 번째 endpoint. 5 ranking 중 가장 단순. ka10030 (당일) 의 전일 버전 — 백테스팅 P3 우선순위._
