# endpoint-21-ka10032.md — 거래대금상위요청

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10032` |
| API 명 | 거래대금상위요청 |
| 분류 | Tier 6 (순위) |
| Phase | **F** |
| 우선순위 | **P2** |
| Method | `POST` |
| URL | `/api/dostk/rkinfo` |
| 의존 endpoint | `au10001`, `ka10099` |

> **Phase F reference 는 endpoint-18-ka10027.md**. 본 계획서는 차이점만.

---

## 1. 목적

**거래대금 상위 종목**. ka10030 (거래량) 과 비슷하지만 거래대금 단일 정렬 + **`now_rank` / `pred_rank` 필드** 로 순위 변동 직접 추적.

1. **거래대금 시그널** — 종목 활성도 + 가격 종합 (큰 종목의 작은 거래량 = 거래대금 높을 수 있음)
2. **순위 변동 추적** — `now_rank` (현재) vs `pred_rank` (전일) 차이로 급등/급락 시그널 직접
3. **호가 정보 (`sel_bid`/`buy_bid`)** — 매도/매수 호가가 응답에 포함

**ka10027/30 과 차이**:
- 응답 list 키 = `trde_prica_upper`
- 응답 필드 13개 (ka10027 의 12, ka10030 의 23 사이)
- **Body 필드 가장 단순 (3개)**: `mrkt_tp` + `mang_stk_incls` + `stex_tp` (sort_tp 없음 — 거래대금 단일 정렬)
- **`now_rank` / `pred_rank` 응답 포함** — 순위 변동 직접 추적

---

## 2. Request 명세

### 2.1 Body (3 필드)

| Element | 한글명 | Required | Length | Description |
|---------|-------|----------|--------|-------------|
| `mrkt_tp` | 시장구분 | Y | 3 | `000`/`001`/`101` |
| `mang_stk_incls` | 관리종목포함 | Y | 1 | `0`:미포함 / `1`:포함 |
| `stex_tp` | 거래소구분 | Y | 1 | `1`/`2`/`3` |

### 2.2 Pydantic

```python
class TradeAmountUpperRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    mrkt_tp: RankingMarketType
    mang_stk_incls: Literal["0", "1"]
    stex_tp: RankingExchangeType
```

> 5 ranking endpoint 중 가장 단순한 Body — 거래대금 단일 정렬이라 sort_tp 없음.

---

## 3. Response 명세 (13 필드)

### 3.1 Body

| Element | 한글명 | 영속화 | 메모 |
|---------|-------|--------|------|
| `trde_prica_upper[]` | 거래대금상위 list | (전체 row) | **list key 명** |
| `stk_cd` | 종목코드 | stock_id (FK) + stock_code_raw | |
| **`now_rank`** | 현재순위 | payload (INTEGER) | 응답 list 의 rank 와 비교 검증 |
| **`pred_rank`** | 전일순위 | payload (INTEGER) | **순위 변동 시그널의 직접 입력** |
| `stk_nm` | 종목명 | payload | |
| `cur_prc` | 현재가 | payload (BIGINT, 부호) | |
| `pred_pre_sig` | 전일대비기호 | payload | 1~5 |
| `pred_pre` | 전일대비 | payload (BIGINT, 부호) | |
| `flu_rt` | 등락률 | payload (Decimal, 부호) | |
| `sel_bid` | 매도호가 | payload (BIGINT, 부호) | 호가 정보 |
| `buy_bid` | 매수호가 | payload (BIGINT, 부호) | 호가 정보 |
| `now_trde_qty` | 현재거래량 | payload (BIGINT) | |
| `pred_trde_qty` | 전일거래량 | payload (BIGINT) | 전일 비교 |
| `trde_prica` | 거래대금 | **`primary_metric` (BIGINT)** | 정렬 기준. 백만원 추정 |
| `return_code` | 처리코드 | (raw_response only) | |
| `return_msg` | 처리메시지 | (raw_response only) | |

### 3.2 Response 예시 (Excel 일부)

```json
{
    "trde_prica_upper": [
        {
            "stk_cd": "005930",
            "now_rank": "1",
            "pred_rank": "1",
            "stk_nm": "삼성전자",
            "cur_prc": "-152000",
            "pred_pre_sig": "5",
            "pred_pre": "-100",
            "flu_rt": "-0.07",
            "sel_bid": "-152000",
            "buy_bid": "-150000",
            "now_trde_qty": "34954641",
            "pred_trde_qty": "22532511",
            "trde_prica": "5308092"
        }
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다"
}
```

### 3.3 Pydantic + 정규화

```python
class TradeAmountUpperRow(BaseModel):
    """ka10032 응답 row — 13 필드 + now_rank/pred_rank."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    stk_cd: str = ""
    now_rank: str = ""
    pred_rank: str = ""
    stk_nm: str = ""
    cur_prc: str = ""
    pred_pre_sig: str = ""
    pred_pre: str = ""
    flu_rt: str = ""
    sel_bid: str = ""
    buy_bid: str = ""
    now_trde_qty: str = ""
    pred_trde_qty: str = ""
    trde_prica: str = ""

    def to_payload(self) -> dict[str, Any]:
        return {
            "now_rank": _to_int(self.now_rank),
            "pred_rank": _to_int(self.pred_rank),
            "stk_nm": self.stk_nm,
            "cur_prc": _to_int(self.cur_prc),
            "pred_pre_sig": self.pred_pre_sig or None,
            "pred_pre": _to_int(self.pred_pre),
            "flu_rt": _to_decimal_str(self.flu_rt),
            "sel_bid": _to_int(self.sel_bid),
            "buy_bid": _to_int(self.buy_bid),
            "now_trde_qty": _to_int(self.now_trde_qty),
            "pred_trde_qty": _to_int(self.pred_trde_qty),
        }


class TradeAmountUpperResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    trde_prica_upper: list[TradeAmountUpperRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""
```

---

## 4. NXT 처리

ka10027 동일.

---

## 5. DB 스키마

`ranking_snapshot` 재사용. `ranking_type=TRDE_PRICA` 분기. **응답의 `now_rank` 가 응답 list 순서 (1, 2, 3) 와 일치해야 함** — 일치하지 않으면 `rank` 컬럼 = `now_rank` 사용 (운영 검증).

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomRkInfoClient.fetch_trde_prica_upper`

```python
class KiwoomRkInfoClient:
    async def fetch_trde_prica_upper(
        self,
        *,
        market_type: RankingMarketType = RankingMarketType.ALL,
        mang_stk_incls: Literal["0", "1"] = "1",
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        max_pages: int = 5,
    ) -> tuple[list[TradeAmountUpperRow], dict[str, Any]]:
        """ka10032 — 거래대금 상위. sort_tp 없음 (단일 정렬)."""
        body = {
            "mrkt_tp": market_type.value,
            "mang_stk_incls": mang_stk_incls,
            "stex_tp": exchange_type.value,
        }

        all_rows: list[TradeAmountUpperRow] = []
        async for page in self._client.call_paginated(
            api_id="ka10032", endpoint=self.PATH, body=body, max_pages=max_pages,
        ):
            parsed = TradeAmountUpperResponse.model_validate(page.body)
            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id="ka10032",
                    return_code=parsed.return_code,
                    return_msg=parsed.return_msg,
                )
            all_rows.extend(parsed.trde_prica_upper)

        return all_rows, body
```

### 6.2 UseCase — `IngestTradeAmountUpperUseCase`

```python
class IngestTradeAmountUpperUseCase:
    """ka10032 — 거래대금 상위 적재."""

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
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        mang_stk_incls: Literal["0", "1"] = "1",
    ) -> RankingIngestOutcome:
        try:
            raw_rows, used_filters = await self._client.fetch_trde_prica_upper(
                market_type=market_type,
                mang_stk_incls=mang_stk_incls,
                exchange_type=exchange_type,
            )
        except KiwoomBusinessError as exc:
            return RankingIngestOutcome(
                ranking_type=RankingType.TRDE_PRICA, snapshot_at=snapshot_at,
                upserted=0, error=f"business: {exc.return_code}",
            )

        stock_codes_clean = [strip_kiwoom_suffix(r.stk_cd) for r in raw_rows]
        stocks_by_code = await self._stock_repo.find_by_codes(stock_codes_clean)

        normalized = []
        for rank, raw_row in enumerate(raw_rows, start=1):
            code_clean = strip_kiwoom_suffix(raw_row.stk_cd)
            stock = stocks_by_code.get(code_clean)
            payload = raw_row.to_payload()
            payload["stk_cd_raw"] = raw_row.stk_cd

            # rank vs now_rank 정합성 — 다르면 now_rank 우선
            now_rank = _to_int(raw_row.now_rank)
            effective_rank = now_rank if now_rank is not None and now_rank > 0 else rank

            normalized.append(NormalizedRanking(
                snapshot_date=snapshot_at.date(),
                snapshot_time=snapshot_at.time().replace(microsecond=0),
                ranking_type=RankingType.TRDE_PRICA,
                sort_tp="0",                        # ka10032 는 sort_tp 없음
                market_type=market_type.value,
                exchange_type=exchange_type.value,
                rank=effective_rank,
                stock_id=stock.id if stock else None,
                primary_metric=Decimal(_to_int(raw_row.trde_prica) or 0),
                payload=payload,
                request_filters=used_filters,
            ))

        upserted = await self._repo.upsert_many(normalized)

        return RankingIngestOutcome(
            ranking_type=RankingType.TRDE_PRICA,
            snapshot_at=snapshot_at,
            sort_tp="0",
            market_type=market_type.value,
            exchange_type=exchange_type.value,
            fetched=len(raw_rows), upserted=upserted,
        )
```

### 6.3 Bulk

운영 default = `mrkt_tp ∈ {001, 101}` × `mang_stk_incls=1` = 2 호출.

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **일 1회 cron** | KST 19:50 평일 | ka10031 (19:40) 직후. ka10014 공매도 (19:45) 와 충돌 — **본 endpoint 19:50 + ka10023 19:55** |

라우터 + APScheduler Job 패턴은 ka10027 동일.

---

## 8. 에러 처리

ka10027 동일.

---

## 9. 테스트

### 9.1 Unit

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 응답 | 200 + list 50건 | 50건 반환 |
| 빈 list | 200 | 빈 list |
| now_rank vs rank | now_rank="1", list 첫 row | rank=1 (일치) |
| now_rank ≠ rank | now_rank="5", list 첫 row | effective_rank=5 (now_rank 우선) |
| pred_rank 변동 시그널 | now_rank=1, pred_rank=5 | payload.pred_rank=5 |

### 9.2 Integration

ka10027 동일 + `now_rank` 검증.

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `app/adapter/out/kiwoom/rkinfo.py` — `KiwoomRkInfoClient.fetch_trde_prica_upper`
- [ ] `app/adapter/out/kiwoom/_records.py` — `TradeAmountUpperRow/Response`
- [ ] `app/application/service/ranking_service.py` — `IngestTradeAmountUpperUseCase`, `IngestTradeAmountUpperBulkUseCase`
- [ ] `app/adapter/web/routers/rankings.py` — POST/GET trde-prica endpoints
- [ ] `app/batch/ranking_jobs.py` — APScheduler 등록 (KST mon-fri 19:50)

### 10.2 테스트

- [ ] Unit 5 시나리오 PASS
- [ ] Integration 5 시나리오 PASS

### 10.3 운영 검증

- [ ] **`now_rank` vs 응답 list 순서 일치 여부**
- [ ] **`pred_rank` 의미** — 어제 같은 시점 순위인지 어제 종가 후 순위인지
- [ ] `trde_prica` 단위 (백만원 추정 — ka10081 동일)
- [ ] `sel_bid` / `buy_bid` 호가의 의미 (현재가 호가? 종가 후 호가?)
- [ ] mang_stk_incls 0 vs 1 차이 (관리종목 등장 빈도)

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10032 trade amount upper ranking`
- [ ] `master.md` § 12 결정 기록에:
  - `now_rank/pred_rank` 의미 (시점 / 일자)

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | mang_stk_incls default | 1 (포함, 현재) / 0 (미포함) | Phase F 코드화 |
| 2 | rank vs now_rank 우선순위 | now_rank 우선 (현재) / list 순서 | 운영 검증 후 |
| 3 | 다중 시점 sync | 1 시점 / 다중 | Phase F 후반 |

### 11.2 알려진 위험

- **`now_rank` ≠ list 순서 가능성**: 같은 종목이 다른 sort 기준으로 응답에 등장 가능 (`mang_stk_incls=1` 시 우선주 / 관리주 포함). 운영 검증
- **`pred_rank` 시점 모호**: 어제 같은 시점 (예: 어제 19:50) 인지 어제 종가 후 (마지막 sync) 인지. derived feature 의 의미 결정에 영향
- **호가 (`sel_bid`/`buy_bid`) 시점**: 응답이 종가 후 호가인지 호출 시점 호가인지. 백테스팅 진입가 시뮬에 영향
- **`trde_prica` 단위**: 백만원 추정. ka10081 와 같은 단위 가정
- **`mang_stk_incls=1` (포함) vs `0` (미포함) 응답 차이**: 관리종목이 거래대금 상위에 자주 등장하면 시그널 노이즈

### 11.3 ka10032 vs 기타 차이 요약

| 항목 | ka10032 (본) | ka10027 | ka10030 |
|------|---------|---------|---------|
| Body 필드 | **3 (가장 단순)** | 9 | 9 |
| 응답 필드 | 13 | 12 | 23 |
| sort_tp | **없음** (단일 정렬) | 5종 | 3종 |
| now_rank/pred_rank | **있음** | 없음 | 없음 |
| 호가 (sel_bid/buy_bid) | **있음** | 매도/매수 잔량 | 없음 |

### 11.4 향후 확장

- **`pred_rank` 변동 직접 시그널**: payload.now_rank - payload.pred_rank → 순위 변동 derived feature (다른 ranking endpoint 는 derived 로 계산해야 함)
- **호가 정보의 활용**: 매도/매수 호가 spread → 유동성 시그널 (Phase H)

---

_Phase F 의 네 번째 endpoint. Body 가장 단순 + `now_rank/pred_rank` 직접 응답이 본 endpoint 의 unique value._
