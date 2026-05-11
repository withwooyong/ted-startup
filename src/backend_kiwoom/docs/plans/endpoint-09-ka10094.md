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

---

## 12. Phase C-4 — Migration 014 + ka10094 인프라 + 자동화 (통합 chunk)

> **추가일**: 2026-05-11 (C-2δ Migration 013 직후, Phase C 종결 chunk)
> **선행 조건**: C-3α/β (`8fcabe4` / `2d4e2ae`) + C-2δ (`8dd5727`) 완료
> **분류**: feat (신규 endpoint 도입 + Migration 1 + 응답 DTO 신규). UseCase YEARLY NotImplementedError 제거 — 기존 가드 분기 활성화
> **scheduler_enabled 상태**: 사용자 결정으로 활성 보류 — Scheduler job 등록 코드만, 실 가동은 모든 작업 완료 후

### 12.1 배경 (Phase C 종결)

10 endpoint (au/ka 2+8) 완료 후 Phase C chart 카테고리 마지막 endpoint = ka10094 (년봉). C-3α/β 의 `IngestPeriodicOhlcvUseCase` 가 Period 3값 (WEEKLY/MONTHLY/YEARLY) 분기 중 YEARLY 만 `NotImplementedError("period=YEARLY (ka10094) 는 P2 chunk — Migration 미작성")` 로 명시적 가드 — 본 chunk 에서 활성화.

C-3 패턴 1:1 응용 + 응답 7 필드 (10 → 7) + NXT skip 정책 차이만 핵심.

### 12.2 결정 (ADR-0001 § 29 신규)

| # | 사안 | 결정 |
|---|------|------|
| 1 | 마이그레이션 번호 | **014** (C-2δ Migration 013 직후). revision id = `014_stock_price_yearly` (22 chars — VARCHAR(32) 안전) |
| 2 | 테이블 분리 | **KRX / NXT 분리** — C-1α/3α 일관 (운영 동일성 검증 미완료 시점이라 분리 보존) |
| 3 | NXT 호출 정책 | **skip** (plan doc § 11.1 #1 옵션 a) — UseCase 에서 `OhlcvIngestOutcome(skipped=True, reason="yearly_nxt_disabled")` 반환. NXT 운영 1년 후 재검토 |
| 4 | 부분 년 OHLC 처리 (신규 상장) | **그대로 적재** (plan doc § 11.1 #2 옵션 a) — 키움 raw 의도 보존 |
| 5 | 호출 빈도 | **연 1회** (plan doc § 11.1 #3 옵션 a) — 매년 1월 5일 KST 03:00 cron 등록 (실 활성은 scheduler_enabled 일괄 활성 시점) |
| 6 | 응답 7 필드 처리 | `NormalizedDailyOhlcv` 의 `prev_compare_amount` / `prev_compare_sign` / `turnover_rate` 는 None 영속화 — DB NULL. ka10082/83 mixin 재사용 (None 필드 다수 plan doc § 11.4) |

### 12.3 영향 범위 (10 코드 + 5 테스트)

**코드 (10 files)**:

| # | 파일 | 변경 |
|---|------|------|
| 1 | `migrations/versions/014_stock_price_yearly.py` (신규) | `stock_price_yearly_krx` + `stock_price_yearly_nxt` 2 테이블 신규. DDL 패턴 = 011/012 (월봉) 1:1 응용 |
| 2 | `app/adapter/out/persistence/models/stock_price_yearly_krx.py` (신규) | ORM (mixin 재사용) |
| 3 | `app/adapter/out/persistence/models/stock_price_yearly_nxt.py` (신규) | ORM (mixin 재사용) |
| 4 | `app/adapter/out/persistence/models/__init__.py` | export 추가 |
| 5 | `app/adapter/out/kiwoom/chart.py` | `fetch_yearly` 메서드 신규 + 빈 응답 sentinel break (C-flow-empty-fix 패턴 1:1) |
| 6 | `app/adapter/out/kiwoom/_records.py` | `YearlyChartRow` / `YearlyChartResponse` Pydantic 7 필드 신규 |
| 7 | `app/adapter/out/persistence/repositories/stock_price_periodic.py` | YEARLY 분기 활성 (KRX/NXT ORM dispatch table 등록) |
| 8 | `app/application/service/ohlcv_periodic_service.py` | `_validate_period` YEARLY NotImplementedError 제거 + NXT skip 가드 (`OhlcvIngestOutcome(skipped=True, reason="yearly_nxt_disabled")`) |
| 9 | `app/adapter/web/routers/ohlcv_periodic.py` | `POST /api/kiwoom/ohlcv/yearly/sync` + `POST /api/kiwoom/stocks/{code}/ohlcv/yearly/refresh` — C-3β 와 일관 (GET 시계열 endpoint 는 별도 chunk, ohlcv_periodic.py 헤더 § 정책 유지) |
| 10 | `app/scheduler.py` | `yearly_ohlcv_sync_yearly` job 신규 (CronTrigger month=1 day=5 hour=3 minute=0 KST). settings + lifespan alias 등록 |

**Pydantic + Settings (보조)**:
- `app/config/settings.py` — `scheduler_yearly_ohlcv_sync_alias` 추가 (B/C 일관 fail-fast)

**테스트 (4 갱신 + 2 신규)**:

| # | 파일 | 변경 |
|---|------|------|
| 1 | `tests/test_migration_014.py` (신규) | 008/013 패턴 1:1 — yearly_krx / yearly_nxt 테이블 생성 / 컬럼 타입 / UNIQUE / FK / 인덱스 검증 |
| 2 | `tests/test_kiwoom_chart_client.py` | `fetch_yearly` 시나리오 (mock 응답 30 row 단일 페이지, 빈 응답 break, 7 필드 normalize, ka10081 의 14 시나리오 중 페이지네이션/dt 빈/부호/자격증명/5xx 5개 응용) |
| 3 | `tests/test_ohlcv_periodic_service.py` 또는 `test_ohlcv_periodic_use_case.py` | YEARLY 분기 활성 / NXT skip 가드 (`yearly_nxt_disabled`) / NotImplementedError 부재 단언 |
| 4 | `tests/test_stock_price_periodic_repository.py` | YEARLY ORM dispatch table 활성 / upsert KRX 만 |
| 5 | `tests/test_ohlcv_router.py` (또는 신규) | yearly path 3개 (sync / refresh / GET 시계열) — C-3β 패턴 1:1 |
| 6 | `tests/test_scheduler_yearly_ohlcv.py` (신규 or 통합) | yearly job 등록 / CronTrigger month=1 day=5 03:00 KST / alias fail-fast |

**문서**:
- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 29 신규 (C-4 결과)
- `CHANGELOG.md` / `STATUS.md` / `HANDOFF.md` / 본 doc § 12 (자기 참조)

### 12.4 적대적 이중 리뷰 — 사전 self-check (ted-run 진입 전)

| # | 위험 | 완화 |
|---|------|------|
| H-1 | VARCHAR(32) revision id (C-2δ 경험) | `014_stock_price_yearly` = 22 chars 안전 마진 10 chars. 008 답습 위험 없음 |
| H-2 | NXT 운영 시작일 (2024-03) 이전 base_dt 호출 응답 불확실 (plan doc § 11.2) | UseCase NXT skip 가드로 호출 자체 차단 → 운영 응답 패턴 미확정 영향 0. 향후 NXT skip 해제 chunk 진입 전 별도 검증 |
| H-3 | 응답 7 필드 가정 (plan doc § 11.2) — 운영에서 추가 필드 등장 | `YearlyChartRow` `extra="ignore"` 로 safe. 추가 필드 발견 시 영속화는 별도 chunk |
| H-4 | 액면분할 30년 보정 (plan doc § 11.2) — `upd_stkpc_tp=1` 정확성 | 백테스팅 가치 평가 시 raw mode 별도 비교 권고. 본 chunk 는 일관성 위해 adjust mode (=1) 사용 |
| H-5 | `prev_compare_amount` / `prev_compare_sign` / `turnover_rate` NULL 영속화 | DB NULL 허용 (ORM mixin 의 nullable=True). 응답 모델에서 None 정규화 |
| H-6 | C-flow-empty-fix sentinel 패턴 적용 누락 | `fetch_yearly` 도 chart.py 일관 — `if not <list>: break` (mrkcond/chart 4곳 패턴 1:1) |
| H-7 | 매년 cron 동작 verification 어려움 (1년 1회) | testcontainers / mock 으로 CronTrigger 파라미터 검증만. 실 fire 는 testcontainers 시간 조작 또는 trigger.get_next_fire_time() 검증 |
| H-8 | Repository dispatch table (Period → ORM) 가 YEARLY 누락 (NotImplementedError) | 본 chunk 의 핵심 변경 = dispatch 활성. 누락 시 KeyError 발생하므로 test_stock_price_periodic_repository.py 가 즉시 발견 |
| H-9 | Scheduler alias 누락 시 lifespan fail-fast | settings.scheduler_yearly_ohlcv_sync_alias 추가 + lifespan validation. C-1β/2β/3β 동일 패턴 |
| H-10 | 응답 list key `stk_yr_pole_chart_qry` 가 Excel 표기만 (운영 검증 미완) | mock 테스트로 parser 검증. 운영 첫 호출 시 ka10082/83 의 `stk_stk_pole_chart_qry` / `stk_mth_pole_chart_qry` 패턴 확인 결과로 신뢰성 확보됨 — 빈 list 인 경우 sentinel 처리 |

### 12.5 DoD (C-4)

**코드**:
- [ ] Migration 014 (yearly_krx + yearly_nxt 2 테이블)
- [ ] ORM 2 (StockPriceYearlyKrx / StockPriceYearlyNxt)
- [ ] Pydantic 2 (YearlyChartRow / YearlyChartResponse — 7 필드)
- [ ] `KiwoomChartClient.fetch_yearly` + sentinel break
- [ ] Repository YEARLY 분기 활성
- [ ] UseCase YEARLY NotImplementedError 제거 + NXT skip 가드
- [ ] Router 3 path (sync / refresh / GET 시계열)
- [ ] Scheduler yearly_ohlcv_sync_yearly job 등록 (매년 1월 5일 KST 03:00)
- [ ] Settings + lifespan alias

**테스트** (목표: 1030 → ~1050~1060 cases / coverage 유지 ≥ 93%):
- [ ] `test_migration_014.py` 신규 (8/13 패턴)
- [ ] `test_kiwoom_chart_client.py` yearly 시나리오 추가
- [ ] `test_ohlcv_periodic_*.py` YEARLY 분기 활성 + NXT skip
- [ ] `test_stock_price_periodic_repository.py` YEARLY dispatch
- [ ] yearly router / scheduler 테스트
- [ ] `ruff check` + `mypy --strict` PASS

**이중 리뷰**:
- [ ] 1R PASS (Reviewer: 스키마/마이그레이션 + UseCase 분기 활성 정확성 + NXT skip 정책 일관성)

**문서**:
- [ ] ADR-0001 § 29 추가 (C-4 결과)
- [ ] STATUS.md § 0 / § 3 / § 4 / § 5 갱신 (chunk → 완료, 다음 chunk = refactor R2)
- [ ] CHANGELOG: `feat(kiwoom): Phase C-4 — ka10094 yearly OHLCV (Migration 014, KRX only, NXT skip, 11/25 endpoint)`
- [ ] HANDOFF.md 갱신

### 12.6 다음 chunk (C-4 이후)

1. **refactor R2 (1R Defer 일괄 정리)** — L-2 / E-1 / M-3 / E-2 / gap detection (1일)
2. **follow-up F6/F7/F8 + daily_flow 빈 응답 1건** (LOW / 0.5일)
3. **ETF/ETN OHLCV 별도 endpoint** (옵션 c, 신규 도메인)
4. **Phase D 진입** — ka10080 분봉 / ka20006 업종일봉 (대용량 파티션 결정 선행)
5. **Phase E/F/G** (공매도 / 대차 / 순위 / 투자자별 — 신규 endpoint wave)
6. **(최종) scheduler_enabled 일괄 활성 + 1주 모니터** — 사용자 결정 (모든 작업 완료 후)
7. **KOSCOM cross-check 수동** — 가설 B 최종 확정
