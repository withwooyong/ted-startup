# endpoint-08-ka10083.md — 주식월봉차트조회요청

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10083` |
| API 명 | 주식월봉차트조회요청 |
| 분류 | Tier 3 (백테스팅 OHLCV — 월봉) |
| Phase | **C** |
| 우선순위 | **P1** |
| Method | `POST` |
| URL | `/api/dostk/chart` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX 만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| 의존 endpoint | `au10001`, `ka10099`(stock + nxt_enable) |
| 관련 endpoint | `ka10081`(일봉) — **본 계획서는 ka10081/82 의 패턴 복제**. ka10082 는 본 endpoint 와 사실상 동일 구조 |

> **본 계획서는 차이점만 기술**. 공통 사항은 [`endpoint-06-ka10081.md`](./endpoint-06-ka10081.md), [`endpoint-07-ka10082.md`](./endpoint-07-ka10082.md) 참조.

---

## 1. 목적

**월봉 OHLCV** 시계열 적재. 백테스팅의 장기 시그널(12개월 모멘텀, 30개월 평균 등) 의 입력.

**ka10081/82 와의 차이**:
- 응답 list 키: `stk_mth_pole_chart_qry`
- 영속화 테이블: `stock_price_monthly_krx` / `stock_price_monthly_nxt`
- `dt` 의미: **그 달의 첫 거래일** (보통 매월 1일 또는 1일이 휴일이면 첫 거래일 — 운영 검증)
- 호출 빈도: 월 1회 (말일 또는 익월 1일 cron)
- 백필 페이지네이션 거의 없음 (3년 = 36 월봉 → 1 페이지 확실)

**왜 P1**: 일봉으로 월봉 합성 가능하지만 분기/연간 시그널 (예: 4분기 평균 거래량) 의 base 로 키움 자체 월봉이 정합성에 유리.

---

## 2. Request 명세

ka10081/82 와 **완전 동일**.

```python
# app/adapter/out/kiwoom/chart.py
class MonthlyChartRequest(DailyChartRequest):
    pass
```

---

## 3. Response 명세

### 3.1 ka10081/82 와의 차이

| 항목 | ka10081 | ka10082 | ka10083 |
|------|---------|---------|---------|
| 응답 list 키 | `stk_dt_pole_chart_qry` | `stk_stk_pole_chart_qry` | **`stk_mth_pole_chart_qry`** |
| 필드 수 | 10 | 10 | 10 (동일) |
| `dt` 의미 | 거래일 | 주 시작일 | **달의 첫 거래일** |
| `cur_prc` 의미 | 일 종가 | 주 종가 | **월 종가** (말일 종가) |

### 3.2 Response 예시 (Excel R45)

```json
{
    "stk_cd": "005930",
    "stk_mth_pole_chart_qry": [
        {
            "cur_prc": "78900",
            "trde_qty": "215040968",
            "trde_prica": "15774571011618",
            "dt": "20250901",
            "open_pric": "68400",
            "high_pric": "79500",
            "low_pric": "67500",
            "pred_pre": "+9200",
            "pred_pre_sig": "2",
            "trde_tern_rt": "..."
        }
    ]
}
```

### 3.3 Pydantic 모델

```python
# app/adapter/out/kiwoom/_records.py
class MonthlyChartRow(DailyChartRow):
    """ka10081 row 와 동일 필드. trading_date = 달 시작일로 매핑."""
    pass


class MonthlyChartResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    stk_cd: str = ""
    stk_mth_pole_chart_qry: list[MonthlyChartRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""
```

---

## 4. NXT 처리

ka10081 § 4 와 **완전 동일**.

---

## 5. DB 스키마

### 5.1 신규 테이블 — Migration 003 + 004 의 일부

```sql
-- Migration 003 (KRX)
CREATE TABLE kiwoom.stock_price_monthly_krx (...);   -- _DailyOhlcvMixin 컬럼 동일

-- Migration 004 (NXT)
CREATE TABLE kiwoom.stock_price_monthly_nxt (...);
```

### 5.2 ORM 모델

```python
# app/adapter/out/persistence/models/stock_price_monthly.py
class StockPriceMonthlyKrx(Base, _DailyOhlcvMixin):
    __tablename__ = "stock_price_monthly_krx"
    __table_args__ = (
        UniqueConstraint("stock_id", "trading_date", "adjusted",
                          name="uq_price_monthly_krx_stock_date"),
        {"schema": "kiwoom"},
    )


class StockPriceMonthlyNxt(Base, _DailyOhlcvMixin):
    __tablename__ = "stock_price_monthly_nxt"
    __table_args__ = (
        UniqueConstraint("stock_id", "trading_date", "adjusted",
                          name="uq_price_monthly_nxt_stock_date"),
        {"schema": "kiwoom"},
    )
```

### 5.3 trading_date 의미

- ka10083: 그 달의 **첫 거래일** (1일 휴일이면 첫 영업일). 응답 검증 후 확정. ka10082 의 의미와 동일하게 "기간의 시작일" 으로 통일 추정.

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter

```python
# app/adapter/out/kiwoom/chart.py (KiwoomChartClient 에 메서드 추가)
async def fetch_monthly(
    self,
    stock_code: str,
    *,
    base_date: date,
    exchange: ExchangeType = ExchangeType.KRX,
    adjusted: bool = True,
    max_pages: int = 3,
) -> list[MonthlyChartRow]:
    """ka10081 패턴 복제. api_id="ka10083", list 키 'stk_mth_pole_chart_qry'."""
    if not (len(stock_code) == 6 and stock_code.isdigit()):
        raise ValueError(f"stock_code 6자리 숫자만: {stock_code}")
    stk_cd = build_stk_cd(stock_code, exchange)
    body = {
        "stk_cd": stk_cd,
        "base_dt": base_date.strftime("%Y%m%d"),
        "upd_stkpc_tp": "1" if adjusted else "0",
    }
    all_rows: list[MonthlyChartRow] = []
    async for page in self._client.call_paginated(
        api_id="ka10083",
        endpoint=self.PATH,
        body=body,
        max_pages=max_pages,
    ):
        parsed = MonthlyChartResponse.model_validate(page.body)
        if parsed.return_code != 0:
            raise KiwoomBusinessError(
                api_id="ka10083",
                return_code=parsed.return_code,
                return_msg=parsed.return_msg,
            )
        all_rows.extend(parsed.stk_mth_pole_chart_qry)
    return all_rows
```

### 6.2 UseCase / Repository

ka10082 의 `IngestPeriodicOhlcvUseCase` + `StockPricePeriodicRepository` 의 **MONTHLY 분기 추가**. 본 endpoint 가 새 클래스 만들지 않음.

```python
# app/application/service/ohlcv_service.py (ka10082 와 같은 클래스)
class IngestPeriodicOhlcvUseCase:
    async def execute(self, stock_code, *, period: Period, ...) -> OhlcvIngestOutcome:
        # period dispatch 에 MONTHLY 추가
        if period is Period.MONTHLY:
            raw_rows = await self._client.fetch_monthly(...)
```

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **수동 단건** | on-demand | `POST /api/kiwoom/ohlcv/{stock_code}/monthly` |
| **수동 일괄** | on-demand | `POST /api/kiwoom/ohlcv/monthly/sync` |
| **월 1회 cron** | 매월 1일 KST 03:00 (또는 말일 19:00) | 직전 달의 OHLC 가 마감되어 안정 |
| **백필** | on-demand | `python scripts/backfill_ohlcv.py --period monthly --years 5` |

```python
# app/batch/monthly_ohlcv_job.py
scheduler.add_job(
    fire_monthly_ohlcv_sync,
    CronTrigger(day=1, hour=3, minute=0, timezone=KST),
    id="monthly_ohlcv",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
)
```

### 7.1 RPS / 시간 추정

ka10081 과 호출 수 동일 (4500 호출). 단 월 1회라 부담 1/22.

---

## 8. 에러 처리

ka10081 § 8 과 **완전 동일**.

---

## 9. 테스트

### 9.1 차이점만

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 응답 list 키 검증 | 200 + `stk_mth_pole_chart_qry` 5건 | parse 정상 |
| 영속화 테이블 분리 | KRX 호출 후 select | stock_price_monthly_krx |
| period dispatch | UseCase.execute(period=MONTHLY) | KiwoomChartClient.fetch_monthly 호출 |
| 휴장 달 처리 | 거래일 0일인 달 (이론상 없음) | 응답 0 row, error 없음 |
| 분기 경계 | 분기 마지막 달 (3/6/9/12월) 응답 | 일반 달과 동일 처리 |

### 9.2 ka10081 의 14 시나리오 공유

페이지네이션 / NXT / mock / dt 빈값 / 부호 / 자격증명 / 5xx 등 동일.

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `KiwoomChartClient.fetch_monthly`
- [ ] `MonthlyChartRow`, `MonthlyChartResponse` Pydantic
- [ ] `StockPriceMonthlyKrx`, `StockPriceMonthlyNxt` ORM
- [ ] `StockPricePeriodicRepository` 의 MONTHLY 분기
- [ ] `IngestPeriodicOhlcvUseCase` 의 MONTHLY 분기
- [ ] 라우터 `POST /api/kiwoom/ohlcv/monthly/sync`
- [ ] APScheduler 등록 (매월 1일 KST 03:00)
- [ ] Migration 003/004 의 monthly 테이블 추가

### 10.2 테스트

- [ ] ka10081 시나리오 14건 + 본 endpoint 차이점 5건 PASS
- [ ] coverage `fetch_monthly` ≥ 80%

### 10.3 운영 검증

- [ ] `dt` 가 달의 첫 거래일인지 (`20250901`) 마지막 거래일인지 확정
- [ ] 3년 백필 페이지네이션 (~36 월봉 → 1 페이지 확실)
- [ ] 일봉 합성한 월봉 high/low/volume vs 키움 월봉 일치 검증
- [ ] 부분 거래월 (월 중 상장된 종목의 첫 달) OHLC 처리 패턴
- [ ] 분기 마지막 달 vs 그 외 달 응답 차이 없음 확인

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10083 monthly OHLCV ingest`
- [ ] `master.md` § 12: `dt` 의미 (월 시작/종료) 확정

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | 일봉 합성 vs 키움 월봉 | ka10082 와 동일 결정 | 운영 검증 후 |
| 2 | 호출 빈도 | (a) 월 1회 (현재) / (b) 일 1회 (당월 OHLC 갱신 추적) | Phase D 후반 |
| 3 | 신규 상장 종목 부분 월 | (a) 적재 (현재) / (b) skip (월 거래일 < N) | 운영 1주 모니터 후 |

### 11.2 알려진 위험

- **`stk_mth_pole_chart_qry` 키 명**: Excel R31 표기. 응답 키와 일치 검증
- **달의 시작/종료 의미**: 1일 휴장 시 첫 거래일이 dt 가 되는지, 1일이 그대로 dt 가 되는지 운영 검증
- **분기 결산 영향**: 분기 마지막 달의 거래량 폭증 (배당락/결산 효과) — 이상치 처리는 백테스팅 엔진의 책임 (본 endpoint 는 raw 적재)
- **일봉 합성 검증의 의미**: 키움 월봉 high 가 그 달 일봉 max(high) 와 일치하지 않으면 어느 source 가 정답인가? — 키움 자체 데이터 신뢰. 단 계측치는 master.md § 12 에 기록
- 나머지 위험은 ka10081 § 11.2 동일

### 11.3 ka10082 와의 비교

| 항목 | ka10082 주봉 | ka10083 월봉 |
|------|--------|--------|
| 응답 필드 수 | 10 | 10 (동일) |
| 영속화 mixin | _DailyOhlcvMixin | 동일 |
| Repository | StockPricePeriodicRepository (공유) | 동일 |
| UseCase | IngestPeriodicOhlcvUseCase (공유) | 동일 |
| 라우터 prefix | `/api/kiwoom/ohlcv/weekly` | `/api/kiwoom/ohlcv/monthly` |
| cron | 금 19:00 | 매월 1일 03:00 |
| 백필 페이지네이션 | 1 페이지 (~156 주봉) | 1 페이지 (~36 월봉) |

→ 본 endpoint 의 코드량은 ka10082 보다도 적음 (cron 시간 + period enum 값 추가 + 메서드 1개).

---

_ka10081/82 의 패턴 복제. 응답 list 키 + cron 시간만 다름. 4 endpoint 가 같은 KiwoomChartClient + Mixin + Repository + UseCase 공유._
