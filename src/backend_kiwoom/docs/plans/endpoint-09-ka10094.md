# endpoint-09-ka10094.md — 주식년봉차트조회요청

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10094` |
| API 명 | 주식년봉차트조회요청 |
| 분류 | Tier 3 (백테스팅 OHLCV — 년봉) |
| Phase | **C** |
| 우선순위 | **P2** |
| Method | `POST` |
| URL | `/api/dostk/chart` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX 만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| 의존 endpoint | `au10001`, `ka10099` |
| 관련 endpoint | `ka10081/82/83` — **본 계획서는 그들의 패턴 복제 + 응답 필드 7개만** |

> **본 계획서는 차이점만 기술**. 공통 사항은 [`endpoint-06-ka10081.md`](./endpoint-06-ka10081.md), [`endpoint-07-ka10082.md`](./endpoint-07-ka10082.md), [`endpoint-08-ka10083.md`](./endpoint-08-ka10083.md) 참조.

---

## 1. 목적

**년봉 OHLCV** 시계열 적재. 백테스팅의 초장기 회귀 분석 / 멀티 사이클 비교 / 50년 트렌드.

**ka10081/82/83 와의 결정적 차이**: **응답 필드 7개만** (`pred_pre`/`pred_pre_sig`/`trde_tern_rt` 없음 — Excel R32~R38).

**왜 P2 (P0/P1 아님)**:
- 백테스팅 1차 시그널은 일/주/월봉으로 충분
- 년봉은 장기 추세 / 멀티 사이클 비교 / 회귀 분석 등 후속 단계 도구
- 호출량 매우 적음 (3년 백필 = 3 row, 30년 = 30 row)

---

## 2. Request 명세

ka10081/82/83 과 **완전 동일**.

```python
class YearlyChartRequest(DailyChartRequest):
    pass
```

---

## 3. Response 명세

### 3.1 ka10081/82/83 와의 차이

| 항목 | ka10081/82/83 | ka10094 |
|------|---------|---------|
| 응답 list 키 | `stk_dt_pole_chart_qry` 등 | **`stk_yr_pole_chart_qry`** |
| 필드 수 | 10 | **7** (3 필드 누락) |
| 누락 필드 | — | `pred_pre`, `pred_pre_sig`, `trde_tern_rt` |
| `dt` 의미 | 거래일/주 시작/달 시작 | **그 해의 첫 거래일** (보통 1월 2일) |

### 3.2 Response 필드 (Excel R31~R38)

| Element | 한글명 | 영속화 컬럼 |
|---------|-------|-------------|
| `cur_prc` | 현재가 (해당 년 종가) | `close_price` |
| `trde_qty` | 거래량 (연간 합) | `trade_volume` |
| `trde_prica` | 거래대금 (연간 합) | `trade_amount` |
| `dt` | 일자 (년 시작일) | `trading_date` |
| `open_pric` | 시가 (1월 첫 거래일 시가) | `open_price` |
| `high_pric` | 고가 (연중 최고) | `high_price` |
| `low_pric` | 저가 (연중 최저) | `low_price` |

→ `_DailyOhlcvMixin` 의 `prev_compare_amount` / `prev_compare_sign` / `turnover_rate` 컬럼은 **NULL 로 유지**. 본 endpoint 는 이 3 컬럼을 채우지 않음.

### 3.3 Response 예시 (Excel R42)

```json
{
    "stk_cd": "005930",
    "stk_yr_pole_chart_qry": [
        {
            "cur_prc": "78200",
            "trde_qty": "10541142553",
            "trde_prica": "698972287992549",
            "dt": "20250102",
            "open_pric": "65100",
            "high_pric": "118800",
            "low_pric": "34900"
        },
        {
            "cur_prc": "65100",
            "trde_qty": "69328600",
            ...
        }
    ]
}
```

### 3.4 Pydantic 모델

```python
# app/adapter/out/kiwoom/_records.py
class YearlyChartRow(BaseModel):
    """ka10094 응답 row — 7 필드만."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    cur_prc: str = ""
    trde_qty: str = ""
    trde_prica: str = ""
    dt: str = ""
    open_pric: str = ""
    high_pric: str = ""
    low_pric: str = ""
    # pred_pre, pred_pre_sig, trde_tern_rt 없음

    def to_normalized(
        self,
        *,
        stock_id: int,
        exchange: ExchangeType,
        adjusted: bool,
    ) -> NormalizedDailyOhlcv:
        return NormalizedDailyOhlcv(
            stock_id=stock_id,
            trading_date=_parse_yyyymmdd(self.dt) or date.min,
            exchange=exchange,
            adjusted=adjusted,
            open_price=_to_int(self.open_pric),
            high_price=_to_int(self.high_pric),
            low_price=_to_int(self.low_pric),
            close_price=_to_int(self.cur_prc),
            trade_volume=_to_int(self.trde_qty),
            trade_amount=_to_int(self.trde_prica),
            prev_compare_amount=None,           # 응답에 없음
            prev_compare_sign=None,
            turnover_rate=None,
        )


class YearlyChartResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    stk_cd: str = ""
    stk_yr_pole_chart_qry: list[YearlyChartRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""
```

> `NormalizedDailyOhlcv` 는 ka10081 의 dataclass 그대로. 누락 필드는 `None`.

---

## 4. NXT 처리

### 4.1 NXT 호출의 의미

NXT 거래소는 ~2025-03 운영 시작. 2025년 NXT 년봉은 **부분 년 데이터** (3월~12월 거래분만). 이전 연도 NXT 년봉은 응답 0 row 추정.

| base_dt 시점 | 응답 |
|-------------|------|
| 2025년 이후 base_dt | 2025년 부분 년봉 + (NXT 운영 시작 후의 일부) |
| 2024년 이전 base_dt | 빈 list `[]` 추정 — 운영 검증 |

### 4.2 NXT 호출 권장 정책

- **(a) 호출 안 함** (권장) — 년봉의 의미가 "1년치 OHLC" 인데 부분 년은 의미 약함
- (b) 호출하되 부분 년 row 만 적재

→ Phase C 1차에는 (a). NXT 년봉은 운영 1년 후 재검토.

```python
class IngestPeriodicOhlcvUseCase:
    async def execute(self, ..., period: Period, exchange: ExchangeType, ...):
        if period is Period.YEARLY and exchange is ExchangeType.NXT:
            # 부분 년봉의 의미 약 — 적재 skip
            return OhlcvIngestOutcome(
                skipped=True, reason="yearly_nxt_disabled",
            )
```

---

## 5. DB 스키마

### 5.1 신규 테이블 — Migration 003 + 004 의 일부

```sql
-- Migration 003 (KRX)
CREATE TABLE kiwoom.stock_price_yearly_krx (...);   -- _DailyOhlcvMixin 컬럼 동일

-- Migration 004 (NXT) — 정의는 하되 ka10094 NXT 호출 안 함 (§4.2)
CREATE TABLE kiwoom.stock_price_yearly_nxt (...);
```

### 5.2 ORM 모델

```python
# app/adapter/out/persistence/models/stock_price_yearly.py
class StockPriceYearlyKrx(Base, _DailyOhlcvMixin):
    __tablename__ = "stock_price_yearly_krx"
    __table_args__ = (
        UniqueConstraint("stock_id", "trading_date", "adjusted",
                          name="uq_price_yearly_krx_stock_date"),
        {"schema": "kiwoom"},
    )


class StockPriceYearlyNxt(Base, _DailyOhlcvMixin):
    __tablename__ = "stock_price_yearly_nxt"
    __table_args__ = (
        UniqueConstraint("stock_id", "trading_date", "adjusted",
                          name="uq_price_yearly_nxt_stock_date"),
        {"schema": "kiwoom"},
    )
```

### 5.3 trading_date 의미

ka10094 의 `dt` 는 그 해의 **첫 거래일** (1월 2일 — 1월 1일 신정 휴장). 운영 검증 후 확정.

### 5.4 NULL 컬럼

`prev_compare_amount`, `prev_compare_sign`, `turnover_rate` 는 본 endpoint 적재 row 에서 항상 NULL. mixin 공유라 컬럼은 존재.

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter

```python
# app/adapter/out/kiwoom/chart.py
async def fetch_yearly(
    self,
    stock_code: str,
    *,
    base_date: date,
    exchange: ExchangeType = ExchangeType.KRX,
    adjusted: bool = True,
    max_pages: int = 2,
) -> list[YearlyChartRow]:
    """ka10081 패턴 복제. api_id="ka10094", list 키 'stk_yr_pole_chart_qry', 응답 7 필드."""
    if not (len(stock_code) == 6 and stock_code.isdigit()):
        raise ValueError(f"stock_code 6자리 숫자만: {stock_code}")
    stk_cd = build_stk_cd(stock_code, exchange)
    body = {
        "stk_cd": stk_cd,
        "base_dt": base_date.strftime("%Y%m%d"),
        "upd_stkpc_tp": "1" if adjusted else "0",
    }
    all_rows: list[YearlyChartRow] = []
    async for page in self._client.call_paginated(
        api_id="ka10094",
        endpoint=self.PATH,
        body=body,
        max_pages=max_pages,
    ):
        parsed = YearlyChartResponse.model_validate(page.body)
        if parsed.return_code != 0:
            raise KiwoomBusinessError(
                api_id="ka10094",
                return_code=parsed.return_code,
                return_msg=parsed.return_msg,
            )
        all_rows.extend(parsed.stk_yr_pole_chart_qry)
    return all_rows
```

### 6.2 UseCase / Repository

ka10082/83 의 `IngestPeriodicOhlcvUseCase` + `StockPricePeriodicRepository` 의 **YEARLY 분기 추가** + NXT skip 가드.

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **수동 단건** | on-demand | `POST /api/kiwoom/ohlcv/{stock_code}/yearly` |
| **수동 일괄** | on-demand | `POST /api/kiwoom/ohlcv/yearly/sync` |
| **연 1회 cron** | 매년 1월 5일 KST 03:00 | 직전 년의 OHLC 마감 + 새해 휴장 후 첫 거래일 며칠 후 |
| **백필** | on-demand | `python scripts/backfill_ohlcv.py --period yearly --years 30` |

```python
# app/batch/yearly_ohlcv_job.py
scheduler.add_job(
    fire_yearly_ohlcv_sync,
    CronTrigger(month=1, day=5, hour=3, minute=0, timezone=KST),
    id="yearly_ohlcv",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
)
```

### 7.1 RPS / 시간 추정

active 3000 종목 KRX only (NXT skip) = 3000 호출. 약 3분.

---

## 8. 에러 처리

ka10081 § 8 + 본 endpoint 추가:

| 시나리오 | 처리 |
|---------|------|
| `period=YEARLY + exchange=NXT` UseCase 호출 | `OhlcvIngestOutcome(skipped=True, reason="yearly_nxt_disabled")` |
| 응답 `prev_compare_*` 누락 | 정상 (Pydantic 에 정의 안 함) |

---

## 9. 테스트

### 9.1 차이점만

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 응답 list 키 | 200 + `stk_yr_pole_chart_qry` 5건 | parse 정상 |
| 7 필드 응답 | row 에 `pred_pre` 없음 | Pydantic extra="ignore" 통과, normalized.prev_compare_amount=None |
| 응답에 `pred_pre` 가 우연히 등장 | `extra="ignore"` 로 무시 | 무시됨 (영속화 안 함) |
| period dispatch | UseCase.execute(period=YEARLY, exchange=KRX) | KiwoomChartClient.fetch_yearly 호출 |
| NXT skip | UseCase.execute(period=YEARLY, exchange=NXT) | skipped=true, reason="yearly_nxt_disabled", 호출 안 함 |
| 30년 백필 | base_date=오늘, 응답 30 row | 1 페이지로 종료 |
| 신규 상장 종목 | 상장 5년 미만 | 응답 5 row, error 없음 |

### 9.2 ka10081 의 14 시나리오 일부 공유

페이지네이션 / mock / dt 빈값 / 부호 / 자격증명 / 5xx 등 동일.

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `KiwoomChartClient.fetch_yearly`
- [ ] `YearlyChartRow`, `YearlyChartResponse` Pydantic (7 필드)
- [ ] `StockPriceYearlyKrx`, `StockPriceYearlyNxt` ORM
- [ ] `StockPricePeriodicRepository` 의 YEARLY 분기
- [ ] `IngestPeriodicOhlcvUseCase` 의 YEARLY 분기 + NXT skip 가드
- [ ] 라우터 `POST /api/kiwoom/ohlcv/yearly/sync`
- [ ] APScheduler 등록 (매년 1월 5일 KST 03:00)
- [ ] Migration 003/004 의 yearly 테이블 추가

### 10.2 테스트

- [ ] ka10081 시나리오 일부 + 본 endpoint 차이점 7건 PASS
- [ ] coverage `fetch_yearly`, NXT skip ≥ 80%

### 10.3 운영 검증

- [ ] `dt` 가 1월 2일(신정 휴장 후 첫 거래일) 형태인지 확정
- [ ] 30년 백필 시 페이지네이션 발생 여부 (1 페이지 가정)
- [ ] 신규 상장 종목의 부분 년봉 row 등장 여부 (예: 2024년 8월 상장 → 2024년 row 가 OHLC 어떻게)
- [ ] NXT 호출 응답 — 2024년 이전 base_dt 호출 시 빈 list 인지 에러인지
- [ ] 키움 년봉의 high/low 가 월봉 max/min 과 일치하는지

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10094 yearly OHLCV ingest (KRX only, NXT skip)`
- [ ] `master.md` § 12: `dt` 의미 + NXT skip 정책 결정 기록

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | NXT 년봉 호출 정책 | (a) skip (현재 권장) / (b) 부분 년 적재 | NXT 운영 1년 후 재검토 |
| 2 | 부분 년 OHLC 처리 (신규 상장) | (a) 그대로 적재 (현재) / (b) 첫 정식 1년만 | Phase D 후반 |
| 3 | 호출 빈도 | (a) 연 1회 (현재) / (b) 분기마다 (당해 OHLC 갱신) | Phase D 후반 |

### 11.2 알려진 위험

- **`stk_yr_pole_chart_qry` 키 명**: Excel R31 표기. 응답 검증 필수
- **응답 7 필드 가정의 정확성**: Excel R32~R38 만 정의. 운영 응답에 추가 필드 등장 가능 (`extra="ignore"` 안전)
- **`pred_pre` 가 년봉에 의미 없음**: 전년 종가 대비 등 "전년 대비" 가 응답에 없는 것이 정상. 만약 운영에서 이 필드가 추가되면 영속화 컬럼 매핑 (mixin 의 prev_compare_amount) 추가
- **장기 백필 시 액면분할 영향**: 30년 백필 시 같은 종목의 액면분할 수십 회 발생 가능. `upd_stkpc_tp=1` 가 정확히 30년치 모두 보정하는지 운영 검증 — 의심되면 raw mode 비교
- **NXT 운영 시작일 이전**: 2024년 이전 base_dt 호출 응답 패턴 미확정 — KiwoomBusinessError vs 빈 list 분기
- **년봉 high/low 가 월/주/일봉의 max/min 과 일치 여부**: 동일 source 라면 정합성 보장. 차이 발생 시 데이터 source 신뢰도 의심
- 나머지 위험은 ka10081 § 11.2 동일

### 11.3 Phase C 의 4 chart endpoint 비교 표

| 항목 | ka10081 일봉 | ka10082 주봉 | ka10083 월봉 | ka10094 년봉 |
|------|--------|--------|--------|--------|
| 우선순위 | **P0** | P1 | P1 | **P2** |
| 응답 필드 | 10 | 10 | 10 | **7** |
| 응답 list 키 | `stk_dt_pole_chart_qry` | `stk_stk_pole_chart_qry` | `stk_mth_pole_chart_qry` | `stk_yr_pole_chart_qry` |
| 영속화 테이블 | stock_price_krx/nxt | stock_price_weekly_krx/nxt | stock_price_monthly_krx/nxt | stock_price_yearly_krx/nxt |
| NXT 호출 | Y | Y | Y | **N (skip)** |
| cron | 평일 18:30 | 금 19:00 | 매월 1일 03:00 | 매년 1월 5일 03:00 |
| 백필 페이지 (3년) | 1~12 페이지 | 1 페이지 | 1 페이지 | 1 페이지 |
| 호출 수 (Phase B 5시장) | 4500 | 4500 | 4500 | **3000** (NXT 제외) |
| 코드량 | reference (~1100줄) | ~250줄 (복제) | ~250줄 (복제) | ~250줄 (복제 + 7 필드) |

### 11.4 Phase C 4 endpoint 코드 공유 요약

| 자산 | ka10081 | ka10082 | ka10083 | ka10094 |
|------|---------|---------|---------|---------|
| `KiwoomChartClient` | reference | 메서드 추가 | 메서드 추가 | 메서드 추가 |
| `_DailyOhlcvMixin` | 정의 | 사용 | 사용 | 사용 |
| `NormalizedDailyOhlcv` | 정의 | 사용 | 사용 | 사용 (None 필드 다수) |
| `_to_int`/`_to_decimal` | (Phase B 의 helper) | 공유 | 공유 | 공유 |
| Repository | StockPriceRepository (일봉 hot path) | StockPricePeriodicRepository | 동일 | 동일 |
| UseCase | IngestDailyOhlcvUseCase + Bulk | IngestPeriodicOhlcvUseCase | 동일 | 동일 + NXT skip |
| 라우터 | `/ohlcv/{code}/daily` | `/ohlcv/{code}/weekly` | `/ohlcv/{code}/monthly` | `/ohlcv/{code}/yearly` |

→ ka10081 가 1100줄, 나머지 3 endpoint 합쳐도 ~750줄. **4 endpoint 의 Phase C 차트 카테고리 전체 코드는 ~1900줄**.

---

_Phase C 의 chart 카테고리 마지막 endpoint. 7 필드만이라 가장 짧지만 NXT 호출 정책 결정이 본 endpoint 의 unique 한 쟁점._
