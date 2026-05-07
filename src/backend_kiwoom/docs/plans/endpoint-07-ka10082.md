# endpoint-07-ka10082.md — 주식주봉차트조회요청

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10082` |
| API 명 | 주식주봉차트조회요청 |
| 분류 | Tier 3 (백테스팅 OHLCV — 주봉) |
| Phase | **C** |
| 우선순위 | **P1** |
| Method | `POST` |
| URL | `/api/dostk/chart` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX 만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| 의존 endpoint | `au10001`, `ka10099`(stock + nxt_enable) |
| 관련 endpoint | `ka10081`(일봉) — 본 계획서는 **ka10081 의 패턴 복제** |

> **본 계획서는 차이점만 기술**. 공통 사항은 [`endpoint-06-ka10081.md`](./endpoint-06-ka10081.md) 참조.

---

## 1. 목적

**주봉 OHLCV** 시계열 적재. 백테스팅의 중장기 시그널(20주 이동평균, 52주 신고가 등) 의 입력.

**ka10081 과의 차이**:
- 응답 list 키만 다름 (`stk_stk_pole_chart_qry`)
- 영속화 테이블이 별도 (`stock_price_weekly_krx` / `stock_price_weekly_nxt`)
- 호출 빈도 일 1회 (주중 매일 호출 — 가장 최근 주의 OHLC 가 갱신되므로 멱등 upsert)
- 백필 시 1 페이지에 더 많은 기간 포함 (3년 = ~156 주봉 → 1 페이지로 충분 추정)

**왜 P1**: 일봉으로 주봉 합성이 가능하지만 키움 자체 주봉 기준 (월~금 주간 OHLC 정의) 이 백테스팅 정합성에 유리.

---

## 2. Request 명세

ka10081 과 **완전 동일**: stk_cd / base_dt / upd_stkpc_tp.

### 2.1 Pydantic 모델

```python
# app/adapter/out/kiwoom/chart.py
class WeeklyChartRequest(DailyChartRequest):
    """동일 스키마. 클래스 분리는 의도 명확화 + 추후 변동성 흡수용."""
```

---

## 3. Response 명세

### 3.1 ka10081 과의 차이

| 항목 | ka10081 | ka10082 |
|------|---------|---------|
| 응답 list 키 | `stk_dt_pole_chart_qry` | **`stk_stk_pole_chart_qry`** |
| 필드 수 | 10 | 10 (동일) |
| `dt` 의미 | 거래일 | **주의 시작일 (월요일 가정 — 운영 검증)** |
| `cur_prc` 의미 | 그 일자 종가 | **그 주 종가 (금요일 종가 가정)** |

### 3.2 Response 예시 (Excel R45)

```json
{
    "stk_cd": "005930",
    "stk_stk_pole_chart_qry": [
        {
            "cur_prc": "69500",
            "trde_qty": "56700518",
            "trde_prica": "3922030535087",
            "dt": "20250901",
            "open_pric": "68400",
            "high_pric": "70400",
            "low_pric": "67500",
            "pred_pre": "-200",
            "pred_pre_sig": "5",
            "trde_tern_rt": "..."
        }
    ]
}
```

### 3.3 Pydantic 모델

```python
# app/adapter/out/kiwoom/_records.py
class WeeklyChartRow(DailyChartRow):
    """ka10081 의 row 와 동일 필드. 영속화 시 trading_date = 주의 시작일로 매핑."""
    pass


class WeeklyChartResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    stk_cd: str = ""
    stk_stk_pole_chart_qry: list[WeeklyChartRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""
```

---

## 4. NXT 처리

ka10081 과 **완전 동일**: stk_cd `_NX` suffix + nxt_enable 게이팅 + mock 도메인 NXT 차단. § 4 참조.

---

## 5. DB 스키마

### 5.1 신규 테이블 — Migration 003 + 004 의 일부

```sql
-- Migration 003 (KRX)
CREATE TABLE kiwoom.stock_price_weekly_krx (
    -- stock_price_krx 와 컬럼 구조 100% 동일
    id, stock_id, trading_date, adjusted, open_price, high_price, low_price,
    close_price, trade_volume, trade_amount, prev_compare_amount, prev_compare_sign,
    turnover_rate, fetched_at, created_at, updated_at
    -- (생략)
    CONSTRAINT uq_price_weekly_krx_stock_date UNIQUE (stock_id, trading_date, adjusted)
);

-- Migration 004 (NXT)
CREATE TABLE kiwoom.stock_price_weekly_nxt (...);
```

### 5.2 ORM 모델

```python
# app/adapter/out/persistence/models/stock_price_weekly.py
class StockPriceWeeklyKrx(Base, _DailyOhlcvMixin):
    __tablename__ = "stock_price_weekly_krx"
    __table_args__ = (
        UniqueConstraint("stock_id", "trading_date", "adjusted",
                          name="uq_price_weekly_krx_stock_date"),
        {"schema": "kiwoom"},
    )


class StockPriceWeeklyNxt(Base, _DailyOhlcvMixin):
    __tablename__ = "stock_price_weekly_nxt"
    __table_args__ = (
        UniqueConstraint("stock_id", "trading_date", "adjusted",
                          name="uq_price_weekly_nxt_stock_date"),
        {"schema": "kiwoom"},
    )
```

> `_DailyOhlcvMixin` 는 ka10081 계획서 § 5.2 에서 정의. 4 컬럼 차원 (KRX/NXT × 일/주/월/년) 모두 같은 mixin 재사용.

### 5.3 trading_date 의미

- ka10081: 일자 단위
- ka10082: 주의 **첫 거래일** (보통 월요일, 휴일이면 화요일). 운영 검증으로 `dt` 가 시작일인지 종료일인지 확정 필요

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter

```python
# app/adapter/out/kiwoom/chart.py (ka10081 의 KiwoomChartClient 에 메서드 추가)
class KiwoomChartClient:
    PATH = "/api/dostk/chart"

    async def fetch_weekly(
        self,
        stock_code: str,
        *,
        base_date: date,
        exchange: ExchangeType = ExchangeType.KRX,
        adjusted: bool = True,
        max_pages: int = 5,
    ) -> list[WeeklyChartRow]:
        """ka10081 패턴 복제. api_id="ka10082", 응답 list 키만 다름."""
        if not (len(stock_code) == 6 and stock_code.isdigit()):
            raise ValueError(f"stock_code 6자리 숫자만: {stock_code}")
        stk_cd = build_stk_cd(stock_code, exchange)
        body = {
            "stk_cd": stk_cd,
            "base_dt": base_date.strftime("%Y%m%d"),
            "upd_stkpc_tp": "1" if adjusted else "0",
        }
        all_rows: list[WeeklyChartRow] = []
        async for page in self._client.call_paginated(
            api_id="ka10082",
            endpoint=self.PATH,
            body=body,
            max_pages=max_pages,
        ):
            parsed = WeeklyChartResponse.model_validate(page.body)
            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id="ka10082",
                    return_code=parsed.return_code,
                    return_msg=parsed.return_msg,
                )
            all_rows.extend(parsed.stk_stk_pole_chart_qry)
        return all_rows
```

### 6.2 Repository

```python
# app/adapter/out/persistence/repositories/stock_price_periodic.py
class StockPricePeriodicRepository:
    """주봉/월봉/년봉 통합 Repository. period 파라미터로 4 테이블 분기.

    ka10081 의 StockPriceRepository 와 분리된 이유:
    - 일봉은 호출 빈도 + row 수가 압도적 → 별도 캐시/인덱스 정책 가능
    - 주/월/년봉은 동일 인터페이스로 묶여 중복 코드 방지
    """

    _MODEL_BY_PERIOD_AND_EXCHANGE = {
        (Period.WEEKLY, ExchangeType.KRX): StockPriceWeeklyKrx,
        (Period.WEEKLY, ExchangeType.NXT): StockPriceWeeklyNxt,
        (Period.MONTHLY, ExchangeType.KRX): StockPriceMonthlyKrx,
        (Period.MONTHLY, ExchangeType.NXT): StockPriceMonthlyNxt,
        (Period.YEARLY, ExchangeType.KRX): StockPriceYearlyKrx,
        (Period.YEARLY, ExchangeType.NXT): StockPriceYearlyNxt,
    }

    async def upsert_many(
        self,
        rows: Sequence[NormalizedDailyOhlcv],
        *,
        period: Period,
        exchange: ExchangeType,
    ) -> int:
        # ka10081 의 StockPriceRepository.upsert_many 패턴 복제
        # ...
```

```python
class Period(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
```

### 6.3 UseCase — `IngestPeriodicOhlcvUseCase`

```python
# app/application/service/ohlcv_service.py
class IngestPeriodicOhlcvUseCase:
    """주/월/년봉 통합 적재 UseCase.

    ka10082/83/94 가 동일 패턴이라 4번째 파라미터 period 로 분기.
    """

    _API_BY_PERIOD = {
        Period.WEEKLY: "ka10082",
        Period.MONTHLY: "ka10083",
        Period.YEARLY: "ka10094",
    }

    async def execute(
        self,
        stock_code: str,
        *,
        period: Period,
        base_date: date,
        exchange: ExchangeType = ExchangeType.KRX,
        adjusted: bool = True,
    ) -> OhlcvIngestOutcome:
        # mock + NXT 가드 / inactive / nxt_enable 가드는 ka10081 UseCase 와 동일
        # ...

        # period 에 맞는 fetch 메서드 dispatch
        if period is Period.WEEKLY:
            raw_rows = await self._client.fetch_weekly(
                stock_code, base_date=base_date, exchange=exchange, adjusted=adjusted,
            )
        elif period is Period.MONTHLY:
            raw_rows = await self._client.fetch_monthly(...)
        elif period is Period.YEARLY:
            raw_rows = await self._client.fetch_yearly(...)
        else:
            raise ValueError(f"period={period} 은 본 UseCase 범위 외 (DAILY 는 IngestDailyOhlcvUseCase)")

        normalized = [
            r.to_normalized(stock_id=stock.id, exchange=exchange, adjusted=adjusted)
            for r in raw_rows
        ]
        upserted = await self._repo.upsert_many(normalized, period=period, exchange=exchange)
        # ...
```

→ ka10082/83/94 가 본 UseCase 의 다른 period 파라미터로 처리. 4 endpoint 가 거의 같은 코드 흐름.

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **수동 단건** | on-demand | `POST /api/kiwoom/ohlcv/{stock_code}/weekly` |
| **수동 일괄** | on-demand | `POST /api/kiwoom/ohlcv/weekly/sync` |
| **주 1회 cron** | 금요일 KST 19:00 | 그 주 마감 후 — 일별 ohlcv (18:30) 후 |
| **백필** | on-demand | `python scripts/backfill_ohlcv.py --period weekly --years 3` |

```python
# app/batch/weekly_ohlcv_job.py
scheduler.add_job(
    fire_weekly_ohlcv_sync,
    CronTrigger(day_of_week="fri", hour=19, minute=0, timezone=KST),
    id="weekly_ohlcv",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
)
```

### 7.1 RPS / 시간 추정

ka10081 과 호출 수 동일 (active 3000 + NXT 1500 = 4500 호출). 단 주 1회라 부담 1/5.

---

## 8. 에러 처리

ka10081 과 **완전 동일** (§ 8 참조).

---

## 9. 테스트

### 9.1 차이점만

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 응답 list 키 검증 | 200 + `stk_stk_pole_chart_qry` 5건 | parse 정상 (다른 키 `stk_dt_pole_chart_qry` 면 빈 list) |
| 영속화 테이블 분리 | KRX 호출 후 select | stock_price_weekly_krx 에서 row 조회됨 (stock_price_krx 아님) |
| period dispatch | UseCase.execute(period=WEEKLY) | KiwoomChartClient.fetch_weekly 호출 (fetch_daily 아님) |
| 잘못된 period | UseCase.execute(period=DAILY) | ValueError (DAILY 는 별도 UseCase) |

### 9.2 ka10081 의 14 시나리오와 공유되는 항목 100%

페이지네이션 / NXT / mock / dt 빈값 / 부호 처리 / 자격증명 / 5xx 등 ka10081 시나리오 그대로.

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `KiwoomChartClient.fetch_weekly` (ka10082)
- [ ] `WeeklyChartRow`, `WeeklyChartResponse` Pydantic
- [ ] `StockPriceWeeklyKrx`, `StockPriceWeeklyNxt` ORM
- [ ] `StockPricePeriodicRepository.upsert_many` 의 WEEKLY 분기
- [ ] `IngestPeriodicOhlcvUseCase` 의 WEEKLY 분기
- [ ] `Period` StrEnum
- [ ] 라우터 `POST /api/kiwoom/ohlcv/weekly/sync`
- [ ] APScheduler 등록 (금 KST 19:00)
- [ ] Migration 003/004 의 weekly 테이블 추가

### 10.2 테스트

- [ ] ka10081 시나리오 14건 + 본 endpoint 차이점 4건 PASS
- [ ] coverage `fetch_weekly`, `Period dispatch` ≥ 80%

### 10.3 운영 검증

- [ ] `dt` 가 주 시작일(월) 인지 종료일(금) 인지 확정
- [ ] 3년 백필 시 페이지네이션 발생 여부 (~156 주봉 — 1 페이지 충분 추정)
- [ ] 응답 list 키가 정말 `stk_stk_pole_chart_qry` 인지 (Excel 오타 가능성)
- [ ] 일봉을 합성한 주봉 vs 키움 주봉 OHLC 차이 (특히 high/low — 일봉 max/min 과 키움 주봉 high/low 일치 확인)

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10082 weekly OHLCV ingest (KRX + NXT)`
- [ ] `master.md` § 12: `dt` 의미 (주 시작/종료) 확정 + 페이지네이션 발생 여부

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | 일봉 합성 vs 키움 주봉 | (a) 키움 주봉 적재 (현재) / (b) 일봉으로 합성 + 검증 / (c) 둘 다 + 비교 | 운영 검증 후 |
| 2 | dt 시작/종료 의미 | 키움 응답 검증 | 운영 첫 호출 후 |
| 3 | 호출 빈도 | (a) 주 1회 (현재) / (b) 일 1회 (현재 주의 OHLC 갱신 추적) | Phase D 후반 |

### 11.2 알려진 위험

- **`stk_stk_pole_chart_qry` 키 명**: Excel R31 표기. 키움 응답의 실제 키와 일치 검증 필요. 만약 다르면 Pydantic alias 추가
- **주의 시작일 의미**: 월~금 한 주의 OHLC 라면 보통 시작일(월요일) 또는 종료일(금요일)이 dt. 휴일 처리 (월요일이 휴일이면?) 운영 검증
- **연휴 주 처리**: 추석/설날 처럼 거래일이 0~2일인 주의 OHLC 가 어떻게 응답되는지 (빈 주 skip? 0 row? 부분 OHLC?)
- **일봉 vs 주봉 정합성**: 같은 주의 일봉 high 가 키움 주봉 high 와 일치해야 정상. 불일치 시 데이터 source 신뢰도 의심
- 나머지 위험은 ka10081 § 11.2 와 동일 (NXT 운영 시작일, 부호 처리, 단위 등)

### 11.3 ka10081/82/83/94 코드 공유 비율

| 자산 | 공유 |
|------|------|
| `KiwoomChartClient` 클래스 | **Y** (메서드 4개) |
| `_DailyOhlcvMixin` ORM mixin | **Y** (4쌍 × 거래소 2 = 8 테이블 모두 공유) |
| `NormalizedDailyOhlcv` dataclass | **Y** (period 무관) |
| `to_normalized` 메서드 | **Y** (DailyChartRow 부모 클래스 메서드) |
| `_to_int` / `_parse_yyyymmdd` helper | **Y** (Phase B 의 helper) |
| Repository 패턴 | **분리** (Daily 는 일별 hot path, Periodic 은 통합) |
| UseCase | **분리** (Daily 는 일 1회 hot, Periodic 은 다른 cron) |
| 라우터 | **공유 prefix** `/api/kiwoom/ohlcv/...` |

→ ka10082/83/94 의 코드량은 ka10081 의 **~20%** (메서드 추가 + ORM 정의만). 본 계획서가 짧은 이유.

---

_ka10081 의 패턴 복제. dt 의미 + list 키 검증이 운영 first call 의 핵심._
