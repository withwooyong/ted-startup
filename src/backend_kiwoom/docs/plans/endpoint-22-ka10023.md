# endpoint-22-ka10023.md — 거래량급증요청

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10023` |
| API 명 | 거래량급증요청 |
| 분류 | Tier 6 (순위) |
| Phase | **F** |
| 우선순위 | **P2** |
| Method | `POST` |
| URL | `/api/dostk/rkinfo` |
| 의존 endpoint | `au10001`, `ka10099` |

> **Phase F reference 는 endpoint-18-ka10027.md**. 본 계획서는 차이점만.

---

## 1. 목적

**거래량 급증 종목** — 단순 거래량 상위 (ka10030) 가 아닌 **급증/급감 비율 시그널**. 거래량 spike 가 가격 변동의 선행 지표인지 검증의 입력.

1. **거래량 spike 시그널** — 급증률 (`sdnin_rt`) 이 N% 이상이면 가격 변동 선행 가능성
2. **분 단위 vs 전일 비교** — `tm_tp=1`(분) / `tm_tp=2`(전일) — 단기/중기 spike 분리
3. **급감 시그널** — `sort_tp=3/4` (급감량/급감률) 으로 매수세 약화 종목 탐지

**ka10027~10032 와 차이**:
- 응답 list 키 = `trde_qty_sdnin`
- 응답 필드 10개 (ka10031 의 6 보다 많고 ka10027 의 12 보다 적음)
- sort_tp = `1`:급증량 / `2`:급증률 / `3`:급감량 / `4`:급감률 (4종)
- **`tm_tp` (시간구분)** — `1`:분 / `2`:전일 — 본 endpoint 만의 시간 윈도 분리
- **`tm` (시간 입력)** — tm_tp=1 시 분 입력 (예: "5", "10")

---

## 2. Request 명세

### 2.1 Body (8 필드)

| Element | 한글명 | Required | Length | Description |
|---------|-------|----------|--------|-------------|
| `mrkt_tp` | 시장구분 | Y | 3 | `000`/`001`/`101` |
| `sort_tp` | 정렬구분 | Y | 1 | `1`:급증량 / `2`:급증률 / `3`:급감량 / `4`:급감률 |
| **`tm_tp`** | 시간구분 | Y | 1 | `1`:분 / `2`:전일 |
| `trde_qty_tp` | 거래량구분 | Y | 1 | `5`:5천주 / `10`/`50`/`100`/`200`/`300`/`500`/`1000` |
| `tm` | 시간 (분 입력) | N | 2 | tm_tp=1 시 입력 (예: "5", "10") |
| `stk_cnd` | 종목조건 | Y | 1 | `0`/`1`/`3`/`4`/`5`/외 |
| `pric_tp` | 가격구분 | Y | 1 | `0`/`2`/`5`/`6`/`8`/`9` |
| `stex_tp` | 거래소구분 | Y | 1 | `1`/`2`/`3` |

### 2.2 Pydantic

```python
class VolumeSdninSortType(StrEnum):
    SDNIN_QTY = "1"      # 급증량
    SDNIN_RATE = "2"     # 급증률
    DECREASE_QTY = "3"   # 급감량
    DECREASE_RATE = "4"  # 급감률


class VolumeSdninTimeType(StrEnum):
    """ka10023 만의 tm_tp."""
    MINUTE = "1"          # 분 윈도 (tm 필드와 함께)
    YESTERDAY = "2"        # 전일 비교


class VolumeSdninRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    mrkt_tp: RankingMarketType
    sort_tp: VolumeSdninSortType
    tm_tp: VolumeSdninTimeType
    trde_qty_tp: str
    tm: str = ""              # tm_tp=MINUTE 시에만 의미
    stk_cnd: str
    pric_tp: str
    stex_tp: RankingExchangeType
```

---

## 3. Response 명세 (10 필드)

### 3.1 Body

| Element | 한글명 | 영속화 | 메모 |
|---------|-------|--------|------|
| `trde_qty_sdnin[]` | 거래량급증 list | (전체 row) | **list key 명** |
| `stk_cd` | 종목코드 | stock_id (FK) + stock_code_raw | |
| `stk_nm` | 종목명 | payload | |
| `cur_prc` | 현재가 | payload (BIGINT, 부호) | |
| `pred_pre_sig` | 전일대비기호 | payload | |
| `pred_pre` | 전일대비 | payload (BIGINT, 부호) | |
| `flu_rt` | 등락률 | payload (Decimal, 부호) | |
| `prev_trde_qty` | 이전거래량 | payload (BIGINT) | tm_tp=MINUTE 시 N분전 거래량, YESTERDAY 시 전일 거래량 |
| `now_trde_qty` | 현재거래량 | payload (BIGINT) | |
| **`sdnin_qty`** | 급증량 | **`primary_metric` (BIGINT, 부호)** | sort_tp=1/3 시 정렬 기준. `+8571012` 부호 포함 |
| `sdnin_rt` | 급증률 | payload (Decimal, 부호) | sort_tp=2/4 시 정렬 기준. `+38.04` 부호 포함 |
| `return_code` | 처리코드 | (raw_response only) | |
| `return_msg` | 처리메시지 | (raw_response only) | |

### 3.2 Response 예시 (Excel 일부)

```json
{
    "trde_qty_sdnin": [
        {
            "stk_cd": "005930",
            "stk_nm": "삼성전자",
            "cur_prc": "-152000",
            "pred_pre_sig": "5",
            "pred_pre": "-100",
            "flu_rt": "-0.07",
            "prev_trde_qty": "22532511",
            "now_trde_qty": "31103523",
            "sdnin_qty": "+8571012",
            "sdnin_rt": "+38.04"
        }
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다"
}
```

> 검증: `sdnin_qty = now_trde_qty - prev_trde_qty` (8571012 = 31103523 - 22532511 ✓)
> 검증: `sdnin_rt = sdnin_qty / prev_trde_qty × 100` (38.04% = 8571012 / 22532511 × 100 ✓)

### 3.3 Pydantic + 정규화

```python
class VolumeSdninRow(BaseModel):
    """ka10023 응답 row — 10 필드."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    stk_cd: str = ""
    stk_nm: str = ""
    cur_prc: str = ""
    pred_pre_sig: str = ""
    pred_pre: str = ""
    flu_rt: str = ""
    prev_trde_qty: str = ""
    now_trde_qty: str = ""
    sdnin_qty: str = ""
    sdnin_rt: str = ""

    def to_payload(self) -> dict[str, Any]:
        return {
            "stk_nm": self.stk_nm,
            "cur_prc": _to_int(self.cur_prc),
            "pred_pre_sig": self.pred_pre_sig or None,
            "pred_pre": _to_int(self.pred_pre),
            "flu_rt": _to_decimal_str(self.flu_rt),
            "prev_trde_qty": _to_int(self.prev_trde_qty),
            "now_trde_qty": _to_int(self.now_trde_qty),
            "sdnin_rt": _to_decimal_str(self.sdnin_rt),
        }


class VolumeSdninResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    trde_qty_sdnin: list[VolumeSdninRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""


def primary_metric_of_volume_sdnin(
    sort_tp: VolumeSdninSortType, row: VolumeSdninRow,
) -> Decimal | None:
    """sort_tp 별 다른 정렬 기준."""
    if sort_tp in (VolumeSdninSortType.SDNIN_QTY, VolumeSdninSortType.DECREASE_QTY):
        v = _to_int(row.sdnin_qty)
        return Decimal(v) if v is not None else None
    if sort_tp in (VolumeSdninSortType.SDNIN_RATE, VolumeSdninSortType.DECREASE_RATE):
        return _to_decimal(row.sdnin_rt)
    return None
```

---

## 4. NXT 처리

ka10027 동일.

---

## 5. DB 스키마

`ranking_snapshot` 재사용. `ranking_type=VOLUME_SDNIN` 분기. **`tm_tp` + `tm` 도 `request_filters` JSONB 에 보관** — 같은 시점에 다른 tm_tp 호출 시 row 분리.

⚠ **UNIQUE 키 추가 필요?**: 현재 `(snapshot_date, snapshot_time, ranking_type, sort_tp, market_type, exchange_type, rank)`. 본 endpoint 는 `tm_tp`/`tm` 까지 다르면 같은 시점에 두 row 가능 → `sort_tp` 컬럼에 `f"{sort_tp.value}_{tm_tp.value}_{tm}"` 같은 합성 키 사용 권장.

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomRkInfoClient.fetch_volume_sdnin`

```python
class KiwoomRkInfoClient:
    async def fetch_volume_sdnin(
        self,
        *,
        market_type: RankingMarketType = RankingMarketType.ALL,
        sort_tp: VolumeSdninSortType = VolumeSdninSortType.SDNIN_QTY,
        tm_tp: VolumeSdninTimeType = VolumeSdninTimeType.YESTERDAY,
        tm: str = "",
        trde_qty_tp: str = "5",
        stk_cnd: str = "0",
        pric_tp: str = "0",
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        max_pages: int = 5,
    ) -> tuple[list[VolumeSdninRow], dict[str, Any]]:
        body = {
            "mrkt_tp": market_type.value,
            "sort_tp": sort_tp.value,
            "tm_tp": tm_tp.value,
            "trde_qty_tp": trde_qty_tp,
            "tm": tm,
            "stk_cnd": stk_cnd,
            "pric_tp": pric_tp,
            "stex_tp": exchange_type.value,
        }

        all_rows: list[VolumeSdninRow] = []
        async for page in self._client.call_paginated(
            api_id="ka10023", endpoint=self.PATH, body=body, max_pages=max_pages,
        ):
            parsed = VolumeSdninResponse.model_validate(page.body)
            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id="ka10023",
                    return_code=parsed.return_code,
                    return_msg=parsed.return_msg,
                )
            all_rows.extend(parsed.trde_qty_sdnin)

        return all_rows, body
```

### 6.2 UseCase — `IngestVolumeSdninUseCase`

```python
class IngestVolumeSdninUseCase:
    """ka10023 — 거래량 급증 적재."""

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
        sort_tp: VolumeSdninSortType = VolumeSdninSortType.SDNIN_QTY,
        tm_tp: VolumeSdninTimeType = VolumeSdninTimeType.YESTERDAY,
        tm: str = "",
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        **filters: Any,
    ) -> RankingIngestOutcome:
        try:
            raw_rows, used_filters = await self._client.fetch_volume_sdnin(
                market_type=market_type, sort_tp=sort_tp, tm_tp=tm_tp, tm=tm,
                exchange_type=exchange_type,
                **filters,
            )
        except KiwoomBusinessError as exc:
            return RankingIngestOutcome(
                ranking_type=RankingType.VOLUME_SDNIN, snapshot_at=snapshot_at,
                upserted=0, error=f"business: {exc.return_code}",
            )

        stock_codes_clean = [strip_kiwoom_suffix(r.stk_cd) for r in raw_rows]
        stocks_by_code = await self._stock_repo.find_by_codes(stock_codes_clean)

        # 합성 sort_tp 키 — 같은 시점에 tm_tp 다른 row 분리
        composite_sort_tp = (
            f"{sort_tp.value}_{tm_tp.value}"
            + (f"_{tm}" if tm else "")
        )

        normalized = []
        for rank, raw_row in enumerate(raw_rows, start=1):
            code_clean = strip_kiwoom_suffix(raw_row.stk_cd)
            stock = stocks_by_code.get(code_clean)
            payload = raw_row.to_payload()
            payload["stk_cd_raw"] = raw_row.stk_cd
            payload["sdnin_qty"] = _to_int(raw_row.sdnin_qty)    # primary_metric 외 raw 도 보관

            normalized.append(NormalizedRanking(
                snapshot_date=snapshot_at.date(),
                snapshot_time=snapshot_at.time().replace(microsecond=0),
                ranking_type=RankingType.VOLUME_SDNIN,
                sort_tp=composite_sort_tp,        # ★ 합성 키
                market_type=market_type.value,
                exchange_type=exchange_type.value,
                rank=rank,
                stock_id=stock.id if stock else None,
                primary_metric=primary_metric_of_volume_sdnin(sort_tp, raw_row),
                payload=payload,
                request_filters=used_filters,
            ))

        upserted = await self._repo.upsert_many(normalized)

        return RankingIngestOutcome(
            ranking_type=RankingType.VOLUME_SDNIN,
            snapshot_at=snapshot_at,
            sort_tp=composite_sort_tp,
            market_type=market_type.value,
            exchange_type=exchange_type.value,
            fetched=len(raw_rows), upserted=upserted,
        )
```

### 6.3 Bulk

운영 default = `mrkt_tp ∈ {001, 101}` × `sort_tp ∈ {1, 2}` (급증량 + 급증률) × `tm_tp = YESTERDAY` = 4 호출.

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **일 1회 cron** | KST 19:55 평일 | ka10032 (19:50) 직후. Phase F 5 endpoint 의 마지막 |

---

## 8. 에러 처리

ka10027 동일.

---

## 9. 테스트

### 9.1 Unit

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 응답 | 200 + list 50건 | 50건 반환 |
| sort_tp 분기 + primary_metric | SDNIN_QTY | primary_metric = sdnin_qty |
| sort_tp 분기 + primary_metric | SDNIN_RATE | primary_metric = sdnin_rt |
| tm_tp=MINUTE + tm="5" | request body `tm_tp="1", tm="5"` | |
| 합성 sort_tp 키 | sort=1 + tm_tp=2 | composite="1_2" |
| 합성 sort_tp 키 with tm | sort=1 + tm_tp=1 + tm=5 | composite="1_1_5" |
| 부호 포함 | sdnin_qty="+8571012" | `_to_int` → 8571012 |
| 부호 포함 (음수) | sdnin_qty="-1000000" | `_to_int` → -1000000 (급감) |

### 9.2 Integration

ka10027 동일 + 합성 sort_tp 키 검증.

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| 같은 시점 다른 tm_tp | YESTERDAY + MINUTE 두 호출 | composite_sort_tp 다른 row 분리 INSERT |

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `app/adapter/out/kiwoom/rkinfo.py` — `KiwoomRkInfoClient.fetch_volume_sdnin`
- [ ] `app/adapter/out/kiwoom/_records.py` — `VolumeSdninRow/Response`, `VolumeSdninSortType`, `VolumeSdninTimeType`, `primary_metric_of_volume_sdnin`
- [ ] `app/application/service/ranking_service.py` — `IngestVolumeSdninUseCase`, `IngestVolumeSdninBulkUseCase`
- [ ] `app/adapter/web/routers/rankings.py` — POST/GET volume-sdnin endpoints
- [ ] `app/batch/ranking_jobs.py` — APScheduler 등록 (KST mon-fri 19:55)

### 10.2 테스트

- [ ] Unit 8 시나리오 PASS
- [ ] Integration 6 시나리오 PASS

### 10.3 운영 검증

- [ ] **`tm_tp=1` (분) + `tm="5"` 의미** — 5분 전 거래량 vs 현재 거래량 비교인지 검증
- [ ] **`prev_trde_qty` 의미** — tm_tp=MINUTE 시 N분 전, YESTERDAY 시 어제 같은 시점 vs 어제 종가
- [ ] `sdnin_qty = now_trde_qty - prev_trde_qty` 산식 일관성 검증
- [ ] `sdnin_rt = sdnin_qty / prev_trde_qty × 100` 산식 일관성 검증
- [ ] sort_tp=DECREASE (3/4) 시 응답 정렬 (음수 sdnin_qty 가 상위?)
- [ ] tm_tp=MINUTE 시 가능한 tm 값 (1/3/5/10/30/60?)

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10023 volume surge ranking`
- [ ] `master.md` § 12 결정 기록에:
  - `tm_tp` + `tm` 의미 확정
  - `prev_trde_qty` 의미 (시점 기준)

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | 운영 default sort_tp | SDNIN_QTY 만 / SDNIN_QTY + SDNIN_RATE (현재) | Phase F 코드화 |
| 2 | 운영 default tm_tp | YESTERDAY (현재) / MINUTE (장중 시그널) | Phase F 후반 |
| 3 | tm_tp=MINUTE 시 tm 값 | 5 분 (현재) / 10 / 30 | 운영 검증 후 |
| 4 | DECREASE (sort_tp=3/4) 수집 여부 | 안 함 (현재) / 함 | 백테스팅 정책 |
| 5 | 합성 sort_tp 키 정책 | composite (현재) / sort_tp 컬럼 확장 | Phase F 코드화 |

### 11.2 알려진 위험

- **`tm_tp` + `tm` 조합의 응답 차이**: tm_tp=1 (분) + tm="5" → 5분 전 / + tm="10" → 10분 전. 잘못 이해 시 시그널 시점 어긋남
- **`prev_trde_qty` 시점 모호**: tm_tp=YESTERDAY 시 "어제 같은 시점" vs "어제 종가" — 운영 검증
- **`sdnin_qty` 부호**: 급증 = 양수, 급감 = 음수 추정. sort_tp=3/4 (감소) 응답에서 음수 정렬 검증
- **합성 sort_tp 키의 disk 부담**: 같은 시점에 4 sort × 2 tm_tp = 8 묶음 가능. 데이터 부담 작음 (한 번에 100 row × 8 = 800)
- **분 단위 시그널의 장중 호출 필요**: tm_tp=MINUTE 은 장중에 의미. 종가 후 (19:55) 호출 시 prev_trde_qty 가 어떻게 산출되는지 검증
- **`now_trde_qty` 가 누적 거래량인지 시점 거래량인지**: ka10080 분봉의 acc_trde_qty 와 비교

### 11.3 ka10023 vs 다른 ranking 차이 요약

| 항목 | ka10023 (본) | ka10027 | ka10030 | ka10031 | ka10032 |
|------|---------|---------|---------|---------|---------|
| Body 필드 | 8 | 9 | 9 | 5 | 3 |
| 응답 필드 | 10 | 12 | 23 | 6 | 13 |
| sort_tp 의미 | 4종 (급증량/률/감량/감률) | 5종 | 3종 | qry_tp 2종 | (없음) |
| tm_tp / tm | **있음** | 없음 | mrkt_open_tp | 없음 | 없음 |
| 시간 윈도 분리 | 분 / 전일 | 시점 | 시점 + 장구분 | 시점 | 시점 |
| 백테스팅 가치 | 시그널 spike | 시그널 1순위 | 활성도 | 전일 활성도 | 거래대금 |

### 11.4 향후 확장

- **장중 다중 시점 sync**: tm_tp=MINUTE 으로 09:30 / 11:00 / 13:00 / 14:30 — 분 단위 spike 추적
- **DECREASE 시그널 활용**: sort_tp=3/4 으로 매수세 약화 종목 탐지
- **sdnin spike 후 가격 변동 추적**: 본 endpoint 의 sdnin_rt 가 N% 이상 종목의 다음 거래일 종가 변동 분석 — Phase H 데이터 품질 리포트

---

_Phase F 의 다섯 번째이자 마지막 endpoint. 거래량 spike 시그널의 raw source. 5 ranking endpoint 모두 완성으로 Phase F 가 ranking_snapshot 통합 테이블 + JSONB payload 패턴으로 마감._
