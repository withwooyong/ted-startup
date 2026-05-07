# endpoint-03-ka10099.md — 종목정보 리스트

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10099` |
| API 명 | 종목정보 리스트 |
| 분류 | Tier 2 (종목 마스터 — NXT 가능여부 source ★) |
| Phase | **B** |
| 우선순위 | **P0** (백테스팅 진입점) |
| Method | `POST` |
| URL | `/api/dostk/stkinfo` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX 만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| 의존 endpoint | `au10001` (토큰), `ka10101` (sector_code 매핑 — soft 의존) |
| 후속 endpoint | `ka10100`(단건 보강), `ka10001`(펀더멘털), `ka10081`(일봉) — 모든 종목 단위 수집의 source |

---

## 1. 목적

키움이 거래 가능한 모든 종목의 **마스터 데이터**를 시장(`mrkt_tp`) 별로 가져와 `stock` 테이블에 적재한다. **Phase B 의 핵심**:

1. **NXT 거래 가능 종목 식별** — 응답 row 의 `nxtEnable="Y"` 필드가 NXT 호출 큐(Phase C 일봉 NXT 수집)의 source. 이 정보 없이는 어떤 종목에 `_NX` suffix 를 붙여 호출할지 알 수 없다.
2. **종목 마스터 baseline** — Phase C 이후 모든 시계열 endpoint(ka10081/82/86/...) 의 `stock_id` FK 가 본 테이블에 의존.
3. **시장 분류 / 업종 / 회사규모** — 백테스팅 시나리오 그루핑(KOSPI vs KOSDAQ, 대형주 vs 소형주 등) 의 분류 축.
4. **상장폐지·정리매매 추적** — `state`, `orderWarning` 필드로 백테스팅에서 제외할 종목 식별.

**왜 P0**:
- Phase C 일봉 수집(`ka10081`) 호출의 종목 큐가 본 endpoint 의 응답에서 만들어진다
- `nxt_enable=Y` 필터 없이 NXT 호출하면 4xx + 무의미한 RPS 소비
- 이 endpoint 가 정상 작동하지 않으면 백테스팅 본체가 시작 불가

**ka10101 와의 차이**:
- ka10101 (Phase A): 업종 마스터 — 5개 시장의 **업종 코드** dictionary
- ka10099 (본 endpoint): 종목 마스터 — 16개 시장의 **개별 종목** list (수만 row)

---

## 2. Request 명세

### 2.1 Header

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `api-id` | TR 명 | String | Y | 10 | `"ka10099"` 고정 |
| `authorization` | 접근토큰 | String | Y | 1000 | `Bearer <token>` |
| `cont-yn` | 연속조회 여부 | String | N | 1 | 응답 헤더 그대로 다음 호출에 전달 |
| `next-key` | 연속조회 키 | String | N | 50 | 응답 헤더 그대로 다음 호출에 전달 |

### 2.2 Body

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `mrkt_tp` | 시장구분 | String | Y | 2 | (값표 §2.3) |

### 2.3 mrkt_tp 값 (16종)

키움 Excel R22 원문 — 단순 enum 이 아니라 **숫자 의미가 endpoint 별로 다름** (master.md § 12 결정 기록 참조):

| Value | 시장 | Phase B 수집 우선순위 | 비고 |
|-------|------|---------------------|------|
| `0` | 코스피 (KOSPI) | **P0** | 백테스팅 주력 |
| `10` | 코스닥 (KOSDAQ) | **P0** | 백테스팅 주력 |
| `30` | K-OTC | P3 | 비상장 — 보류 |
| `50` | 코넥스 (KONEX) | P2 | 소량 |
| `60` | ETN | P2 | 분리 분석 가능성 |
| `70` | 손실제한 ETN | P3 | |
| `80` | 금현물 | P3 (보류) | master.md 범위 외 |
| `90` | 변동성 ETN | P3 | |
| `2` | 인프라투융자 | P3 | |
| `3` | ELW | P3 (보류) | master.md 범위 외 |
| `4` | 뮤추얼펀드 | P3 | |
| `5` | 신주인수권 | P3 | |
| `6` | 리츠종목 | P2 | 백테스팅 시나리오 후보 |
| `7` | 신주인수권증서 | P3 | |
| `8` | ETF | P2 (보류 권장) | master.md 범위 외, 다만 대량 — 별도 Phase 결정 |
| `9` | 하이일드펀드 | P3 | |

**Phase B 수집 범위 (P0 + P1)**: `0`, `10`, `50`, `60`, `6` — 5개. 나머지는 향후 Phase 에서 결정.

> **혼동 주의**: master.md § 12 와 endpoint-14 § 11.3 에서 확정한 대로 `ka10099` 의 mrkt_tp 는 `ka10101`(업종) 의 `0:코스피, 1:코스닥, 2:KOSPI200, 4:KOSPI100, 7:KRX100` 와 의미 완전히 다르다. `StockListMarketType` enum 분리 필수.

### 2.4 Request 예시

```json
POST https://api.kiwoom.com/api/dostk/stkinfo
Content-Type: application/json;charset=UTF-8
api-id: ka10099
authorization: Bearer WQJCwyqInphKnR3bSRtB9NE1lv...

{
    "mrkt_tp": "0"
}
```

### 2.5 Pydantic 모델

```python
# app/adapter/out/kiwoom/stkinfo.py
class StockListRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    mrkt_tp: StockListMarketType   # constants.py 의 StrEnum
```

```python
# app/application/constants.py
class StockListMarketType(StrEnum):
    KOSPI = "0"
    KOSDAQ = "10"
    K_OTC = "30"
    KONEX = "50"
    ETN = "60"
    ETN_LOSS_LIMIT = "70"
    GOLD_SPOT = "80"
    ETN_VOLATILITY = "90"
    INFRA_FUND = "2"
    ELW = "3"
    MUTUAL_FUND = "4"
    SUBSCRIPTION_RIGHT = "5"
    REIT = "6"
    SUBSCRIPTION_CERT = "7"
    ETF = "8"
    HIGH_YIELD_FUND = "9"
```

---

## 3. Response 명세

### 3.1 Header

| Element | Type | Description |
|---------|------|-------------|
| `api-id` | String | `"ka10099"` 에코 |
| `cont-yn` | String | `Y` 면 다음 페이지 존재 |
| `next-key` | String | 다음 호출 헤더에 세팅 |

### 3.2 Body (14 필드 per row)

| Element | 한글명 | Type | Length | 영속화 컬럼 | 메모 |
|---------|-------|------|--------|-------------|------|
| `list[]` | 종목리스트 | LIST | — | — | 페이지 단위 array |
| `code` | 종목코드 | String | 20 | `stock_code` (CHAR(6)) | 단축코드. 예: `"005930"`. zero-pad 없음 |
| `name` | 종목명 | String | 40 | `stock_name` | 한글 |
| `listCount` | 상장주식수 | String | 20 | `list_count` (BIGINT) | **zero-padded** 16자리 (예: `"0000000123759593"`). int 변환 시 leading zero 처리 |
| `auditInfo` | 감리구분 | String | 20 | `audit_info` (VARCHAR(40)) | 예: `"정상"`, `"투자주의환기종목"` |
| `regDay` | 상장일 | String | 20 | `listed_date` (DATE) | `YYYYMMDD` (예: `"20091204"`) |
| `lastPrice` | 전일종가 | String | 20 | `last_price` (BIGINT) | **zero-padded**. 단위 KRW |
| `state` | 종목상태 | String | 20 | `state` (VARCHAR(80)) | 예: `"증거금20%|담보대출|신용가능"` (`|` 구분 다중값) |
| `marketCode` | 시장구분코드 | String | 20 | `market_code` (VARCHAR(4)) | 응답 코드. 예: `"0"`(거래소), `"10"`(코스닥) — Excel 예시상 mrkt_tp 와 일치하지 않을 수도 있음 (R36 검증 필요) |
| `marketName` | 시장명 | String | 20 | `market_name` (VARCHAR(40)) | 예: `"거래소"`, `"코스닥"` |
| `upName` | 업종명 | String | 20 | `up_name` (VARCHAR(40)) | 예: `"금융업"` (코스닥은 빈 문자열 가능) |
| `upSizeName` | 회사크기분류 | String | 20 | `up_size_name` (VARCHAR(20)) | 예: `"대형주"`, `"중형주"`, `"소형주"` |
| `companyClassName` | 회사분류 | String | 20 | `company_class_name` (VARCHAR(40)) | 코스닥 only — 예: `"외국기업"` |
| `orderWarning` | 투자유의종목여부 | String | 20 | `order_warning` (CHAR(1)) | `0`: 해당없음 / `2`: 정리매매 / `3`: 단기과열 / `4`: 투자위험 / `5`: 투자경과 / `1`: ETF투자주의요망 |
| `nxtEnable` | NXT가능여부 | String | 20 | `nxt_enable` (BOOL) | `"Y"` → True / `""` 또는 `"N"` → False |
| `return_code` | 처리코드 | Integer | — | (raw_response only) | `0` 정상 |
| `return_msg` | 처리메시지 | String | — | (raw_response only) | `"정상적으로 처리되었습니다"` |

### 3.3 Response 예시 (Excel R46 — 5 rows, 동일 종목 코드 005930 반복은 Excel 샘플 단순화)

```json
{
    "return_msg": "정상적으로 처리되었습니다",
    "return_code": 0,
    "list": [
        {
            "code": "005930",
            "name": "삼성전자",
            "listCount": "0000000123759593",
            "auditInfo": "투자주의환기종목",
            "regDay": "20091204",
            "lastPrice": "00000197",
            "state": "관리종목",
            "marketCode": "10",
            "marketName": "코스닥",
            "upName": "",
            "upSizeName": "",
            "companyClassName": "",
            "orderWarning": "0",
            "nxtEnable": "Y"
        }
    ]
}
```

### 3.4 Pydantic 모델 — raw row → 정규화 변환

```python
# app/adapter/out/kiwoom/_records.py
class StockListRow(BaseModel):
    """ka10099 응답 row — 키움 응답 그대로 (camelCase + zero-padded string)."""
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

    def to_normalized(self, requested_market_code: str) -> "NormalizedStock":
        """zero-padded 문자열 → BIGINT/DATE/BOOL 정규화."""
        return NormalizedStock(
            stock_code=self.code,
            stock_name=self.name,
            list_count=int(self.listCount.lstrip("0") or "0") if self.listCount else None,
            audit_info=self.auditInfo or None,
            listed_date=_parse_yyyymmdd(self.regDay),
            last_price=int(self.lastPrice.lstrip("0") or "0") if self.lastPrice else None,
            state=self.state or None,
            market_code=self.marketCode or requested_market_code,
            market_name=self.marketName or None,
            up_name=self.upName or None,
            up_size_name=self.upSizeName or None,
            company_class_name=self.companyClassName or None,
            order_warning=self.orderWarning or "0",
            nxt_enable=(self.nxtEnable.upper() == "Y"),
            requested_market_type=requested_market_code,
        )


class StockListResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    list: list[StockListRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""


def _parse_yyyymmdd(value: str) -> date | None:
    if not value or len(value) != 8:
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class NormalizedStock:
    stock_code: str
    stock_name: str
    list_count: int | None
    audit_info: str | None
    listed_date: date | None
    last_price: int | None
    state: str | None
    market_code: str
    market_name: str | None
    up_name: str | None
    up_size_name: str | None
    company_class_name: str | None
    order_warning: str
    nxt_enable: bool
    requested_market_type: str   # 호출 시 mrkt_tp 값 (예: "0")
```

> **camelCase → snake_case 변환은 Adapter 경계에서**. Application/Repository 레이어는 항상 `NormalizedStock` 만 본다.

---

## 4. NXT 처리

| 항목 | 적용 여부 |
|------|-----------|
| `stk_cd` 에 `_NX` suffix | N (본 endpoint 는 list 조회, stk_cd 파라미터 없음) |
| `nxt_enable` 게이팅 | **N (본 endpoint 가 게이팅 정보의 source)** |
| `mrkt_tp` 별 분리 호출 | **Y (5~16 시장 각각 호출)** |
| KRX 운영 / 모의 차이 | mockapi.kiwoom.com 도 호출 가능. 단 `nxtEnable` 필드는 prod 에서만 신뢰 가능 (모의는 NXT 미지원 — 빈 문자열 가능성) |

### 4.1 게이팅 source 의미

본 endpoint 응답에서 `nxt_enable=True` 로 추출된 종목만이 다음 단계의 `_NX` suffix 호출 큐에 등록된다:

```
ka10099 응답 row.nxtEnable="Y"
   └→ stock.nxt_enable=true UPDATE
       └→ Phase C 의 ka10081 NXT 호출 큐에 stock 등록
           └→ ka10081 호출 시 stk_cd="005930_NX"
               └→ stock_price_nxt 테이블 row 적재
```

### 4.2 모의 환경 안전판

`Settings.kiwoom_default_env="mock"` 일 때 ka10099 호출은 **허용** 하나 응답의 `nxtEnable` 값을 무시하고 일률적으로 `nxt_enable=false` 처리한다 (mock 도메인은 NXT 미지원):

```python
if settings.kiwoom_default_env == "mock":
    nxt_enable = False   # mock 도메인 안전판 — 응답 값 무시
else:
    nxt_enable = (row.nxtEnable.upper() == "Y")
```

→ master.md § 7 의 `nxt_collection_enabled` 와 별개의 **응답 검증 layer**.

---

## 5. DB 스키마

### 5.1 신규 테이블 (Migration 001 — `001_init_kiwoom_schema.py` 의 일부)

```sql
CREATE TABLE kiwoom.stock (
    id                   BIGSERIAL PRIMARY KEY,
    stock_code           VARCHAR(20) NOT NULL,                -- "005930" (NXT/SOR suffix 는 영속화 안 함)
    stock_name           VARCHAR(40) NOT NULL,
    list_count           BIGINT,                              -- 상장주식수
    audit_info           VARCHAR(40),                          -- 감리구분
    listed_date          DATE,                                 -- 상장일
    last_price           BIGINT,                               -- 전일종가 (KRW)
    state                VARCHAR(120),                         -- "증거금20%|담보대출|..." 다중값
    market_code          VARCHAR(4) NOT NULL,                  -- "0"/"10"/"50"/"60"/"6"/...
    market_name          VARCHAR(40),                          -- "거래소"/"코스닥"/...
    up_name              VARCHAR(40),                          -- 업종명
    up_size_name         VARCHAR(20),                          -- "대형주"/"중형주"/"소형주"
    company_class_name   VARCHAR(40),                          -- 코스닥 only
    order_warning        CHAR(1) NOT NULL DEFAULT '0',         -- 0=해당없음
    nxt_enable           BOOLEAN NOT NULL DEFAULT false,
    is_active            BOOLEAN NOT NULL DEFAULT true,        -- 상장폐지/디액티베이션
    fetched_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_stock_code UNIQUE (stock_code)
);

CREATE INDEX idx_stock_market_code ON kiwoom.stock(market_code);
CREATE INDEX idx_stock_nxt_enable ON kiwoom.stock(nxt_enable) WHERE nxt_enable = true;
CREATE INDEX idx_stock_active ON kiwoom.stock(is_active) WHERE is_active = true;
CREATE INDEX idx_stock_up_name ON kiwoom.stock(up_name) WHERE up_name IS NOT NULL;
```

### 5.2 ORM 모델

```python
# app/adapter/out/persistence/models/stock.py
class Stock(Base):
    __tablename__ = "stock"
    __table_args__ = (
        UniqueConstraint("stock_code", name="uq_stock_code"),
        Index("idx_stock_nxt_enable", "nxt_enable", postgresql_where=text("nxt_enable = true")),
        Index("idx_stock_active", "is_active", postgresql_where=text("is_active = true")),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(40), nullable=False)
    list_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    audit_info: Mapped[str | None] = mapped_column(String(40), nullable=True)
    listed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    market_code: Mapped[str] = mapped_column(String(4), nullable=False)
    market_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    up_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    up_size_name: Mapped[str | None] = mapped_column(String(20), nullable=True)
    company_class_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    order_warning: Mapped[str] = mapped_column(String(1), nullable=False, server_default="0")
    nxt_enable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

### 5.3 디액티베이션 정책

`is_active=false` 처리 (sector 와 동일 정책 — endpoint-14 § 5.3):

| 트리거 | 처리 |
|--------|------|
| 응답 `list` 에 등장 | `is_active=true` 로 복원 (또는 유지) |
| 같은 시장 sync 에서 응답에 미등장 | `is_active=false` 로 마킹 (현시점 마지막 sync 의 missing) |
| 마이너 시장 (mrkt_tp 미수집) 만 sync 한 경우 | 다른 시장의 stock 은 건드리지 않음 |

→ `deactivate_missing(market_code, present_codes)` Repository 메서드. **반드시 같은 mrkt_tp 범위 내에서만 비활성화**. 그렇지 않으면 KOSPI 만 sync 했을 때 KOSDAQ 종목이 모두 비활성화되는 사고 발생.

### 5.4 인덱스 사용 시나리오

| 쿼리 | 사용 인덱스 |
|------|-------------|
| Phase C: NXT 호출 큐 만들기 (`SELECT WHERE nxt_enable=true AND is_active=true`) | `idx_stock_nxt_enable` |
| 백테스팅: 활성 종목 list (`SELECT WHERE is_active=true ORDER BY market_code`) | `idx_stock_active` + `idx_stock_market_code` |
| 업종별 분석 (`SELECT WHERE up_name='반도체' AND is_active=true`) | `idx_stock_up_name` |
| Repository upsert (`INSERT ... ON CONFLICT (stock_code)`) | `uq_stock_code` |

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomStkInfoClient.fetch_stock_list`

```python
# app/adapter/out/kiwoom/stkinfo.py
class KiwoomStkInfoClient:
    """`/api/dostk/stkinfo` 계열 묶음. ka10099/ka10100/ka10001/ka10101 공유."""

    PATH = "/api/dostk/stkinfo"

    def __init__(self, kiwoom_client: KiwoomClient) -> None:
        self._client = kiwoom_client

    async def fetch_stock_list(
        self,
        mrkt_tp: StockListMarketType,
        *,
        max_pages: int = 100,
    ) -> list[StockListRow]:
        """단일 시장의 종목 list. 페이지네이션 자동 처리 (cont_yn=Y → next_key 추적)."""
        all_rows: list[StockListRow] = []
        async for page in self._client.call_paginated(
            api_id="ka10099",
            endpoint=self.PATH,
            body={"mrkt_tp": mrkt_tp.value},
            max_pages=max_pages,
        ):
            parsed = StockListResponse.model_validate(page.body)
            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id="ka10099",
                    return_code=parsed.return_code,
                    return_msg=parsed.return_msg,
                )
            all_rows.extend(parsed.list)
        return all_rows
```

> KOSPI(`mrkt_tp=0`) 는 약 900~1000 종목, KOSDAQ(`10`) 은 1500~1700 종목 추정 — 페이지네이션 빈도 높음. Phase A 의 `call_paginated` 검증이 본 endpoint 에서 본격화.

### 6.2 Repository

```python
# app/adapter/out/persistence/repositories/stock.py
class StockRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, rows: list[NormalizedStock]) -> int:
        """ON CONFLICT (stock_code) UPDATE. nxt_enable / state / last_price 등 모두 갱신."""
        if not rows:
            return 0
        values = [
            {
                "stock_code": r.stock_code,
                "stock_name": r.stock_name,
                "list_count": r.list_count,
                "audit_info": r.audit_info,
                "listed_date": r.listed_date,
                "last_price": r.last_price,
                "state": r.state,
                "market_code": r.market_code,
                "market_name": r.market_name,
                "up_name": r.up_name,
                "up_size_name": r.up_size_name,
                "company_class_name": r.company_class_name,
                "order_warning": r.order_warning,
                "nxt_enable": r.nxt_enable,
                "is_active": True,                   # 응답에 등장하면 활성화
            }
            for r in rows
        ]
        stmt = pg_insert(Stock).values(values)
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
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return rowcount_of(result)

    async def deactivate_missing(
        self, market_code: str, present_codes: set[str]
    ) -> int:
        """**같은 market_code 내**에서 응답에 없는 stock_code 들을 is_active=false."""
        if not present_codes:
            return 0     # 빈 응답이면 비활성화 보수적으로 skip
        stmt = (
            update(Stock)
            .where(
                Stock.market_code == market_code,
                Stock.is_active.is_(True),
                Stock.stock_code.notin_(present_codes),
            )
            .values(is_active=False, updated_at=func.now())
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return rowcount_of(result)

    async def list_nxt_enabled(self, *, only_active: bool = True) -> list[Stock]:
        """Phase C 의 NXT 호출 큐 source."""
        stmt = select(Stock).where(Stock.nxt_enable.is_(True))
        if only_active:
            stmt = stmt.where(Stock.is_active.is_(True))
        return list((await self._session.execute(stmt)).scalars())

    async def find_by_code(self, stock_code: str) -> Stock | None:
        return (await self._session.execute(
            select(Stock).where(Stock.stock_code == stock_code)
        )).scalar_one_or_none()
```

### 6.3 UseCase — `SyncStockMasterUseCase`

```python
# app/application/service/stock_master_service.py
class SyncStockMasterUseCase:
    """Phase B 수집 시장 (`0`/`10`/`50`/`60`/`6`) 별로 ka10099 호출 → stock 마스터 동기화.

    - 시장 별 try/except 로 부분 실패 격리 (한 시장 호출 실패가 전체를 깨지 않음)
    - mock 도메인일 때 nxt_enable 강제 false (mock = KRX 전용)
    - 시장 단위 트랜잭션 — 한 시장 sync 성공 시 즉시 commit, 다음 시장 진입
    """

    DEFAULT_MARKETS: tuple[StockListMarketType, ...] = (
        StockListMarketType.KOSPI,
        StockListMarketType.KOSDAQ,
        StockListMarketType.KONEX,
        StockListMarketType.ETN,
        StockListMarketType.REIT,
    )

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

    async def execute(
        self,
        markets: Sequence[StockListMarketType] | None = None,
    ) -> StockMasterSyncResult:
        targets = list(markets) if markets is not None else list(self.DEFAULT_MARKETS)
        outcomes: list[MarketOutcome] = []

        for mrkt in targets:
            try:
                raw_rows = await self._client.fetch_stock_list(mrkt)
            except KiwoomError as exc:
                logger.warning("ka10099 sync 실패 mrkt_tp=%s: %s", mrkt.value, exc)
                outcomes.append(MarketOutcome(
                    market_code=mrkt.value,
                    fetched=0,
                    upserted=0,
                    deactivated=0,
                    nxt_enabled_count=0,
                    error=f"{type(exc).__name__}: {exc}",
                ))
                continue

            normalized = [r.to_normalized(mrkt.value) for r in raw_rows]
            if self._env == "mock":
                # mock 도메인 안전판: 응답 nxtEnable 무시
                normalized = [replace(n, nxt_enable=False) for n in normalized]

            upserted = await self._repo.upsert_many(normalized)
            present = {n.stock_code for n in normalized}
            deactivated = await self._repo.deactivate_missing(mrkt.value, present)
            nxt_count = sum(1 for n in normalized if n.nxt_enable)

            outcomes.append(MarketOutcome(
                market_code=mrkt.value,
                fetched=len(normalized),
                upserted=upserted,
                deactivated=deactivated,
                nxt_enabled_count=nxt_count,
            ))

        return StockMasterSyncResult(
            markets=outcomes,
            total_fetched=sum(o.fetched for o in outcomes),
            total_upserted=sum(o.upserted for o in outcomes),
            total_deactivated=sum(o.deactivated for o in outcomes),
            total_nxt_enabled=sum(o.nxt_enabled_count for o in outcomes),
        )


@dataclass(frozen=True, slots=True)
class MarketOutcome:
    market_code: str
    fetched: int
    upserted: int
    deactivated: int
    nxt_enabled_count: int
    error: str | None = None


@dataclass(frozen=True, slots=True)
class StockMasterSyncResult:
    markets: list[MarketOutcome]
    total_fetched: int
    total_upserted: int
    total_deactivated: int
    total_nxt_enabled: int
```

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **수동 동기화** | on-demand | `POST /api/kiwoom/stocks/sync` (admin) — 시장 선택 가능 |
| **일 1회 cron** | KST 17:30 평일 | 장 마감 후. 신규 상장/상장폐지 반영 |
| **운영 초기 1회** | seed | `python scripts/seed_stocks.py` |

### 7.1 라우터

```python
# app/adapter/web/routers/stocks.py
router = APIRouter(prefix="/api/kiwoom/stocks", tags=["kiwoom-stocks"])


@router.get("", response_model=list[StockOut])
async def list_stocks(
    market_code: str | None = Query(default=None),
    nxt_enable: bool | None = Query(default=None),
    only_active: bool = Query(default=True),
    session: AsyncSession = Depends(get_session),
) -> list[StockOut]:
    """저장된 종목 마스터 조회 (DB only)."""
    repo = StockRepository(session)
    # ... filter chain
    return [StockOut.model_validate(s) for s in stocks]


@router.post(
    "/sync",
    response_model=StockMasterSyncResultOut,
    dependencies=[Depends(require_admin_key)],
)
async def sync_stocks(
    body: StockSyncRequestIn = Body(default_factory=StockSyncRequestIn),
    use_case: SyncStockMasterUseCase = Depends(get_sync_stock_master_use_case),
) -> StockMasterSyncResultOut:
    """시장 별 종목 마스터 강제 동기화. body 의 markets 가 비어있으면 DEFAULT 사용."""
    markets = [StockListMarketType(m) for m in body.markets] if body.markets else None
    result = await use_case.execute(markets)
    return StockMasterSyncResultOut.model_validate(asdict(result))


@router.get("/nxt-eligible", response_model=list[StockOut])
async def list_nxt_eligible(session: AsyncSession = Depends(get_session)) -> list[StockOut]:
    """Phase C 가 사용할 NXT 호출 큐."""
    repo = StockRepository(session)
    rows = await repo.list_nxt_enabled(only_active=True)
    return [StockOut.model_validate(s) for s in rows]
```

### 7.2 APScheduler Job

```python
# app/batch/daily_master_job.py
async def fire_daily_stock_master_sync() -> None:
    """매 평일 17:30 KST — 종목 마스터 동기화."""
    if not is_trading_day(date.today()):
        logger.info("daily_stock_master_sync: 비거래일 skip")
        return
    try:
        async with get_sessionmaker()() as session:
            kiwoom_client = build_kiwoom_client_for("prod-main")
            stkinfo = KiwoomStkInfoClient(kiwoom_client)
            uc = SyncStockMasterUseCase(
                session, stkinfo_client=stkinfo, env=settings.kiwoom_default_env,
            )
            result = await uc.execute()
            await session.commit()
        logger.info(
            "stock_master sync 완료 fetched=%d upserted=%d nxt_enabled=%d deactivated=%d",
            result.total_fetched, result.total_upserted,
            result.total_nxt_enabled, result.total_deactivated,
        )
    except Exception:
        logger.exception("stock_master sync 콜백 예외")


# scheduler.py
scheduler.add_job(
    fire_daily_stock_master_sync,
    CronTrigger(day_of_week="mon-fri", hour=17, minute=30, timezone=KST),
    id="stock_master_daily",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
)
```

### 7.3 거래일 판정

`app/batch/trading_day.py` — 한국 공휴일 + 토/일 + 임시휴장 캘린더. backend_py 의 `holidays` 패키지 + 보강 패턴 복제 (코드 import 금지, 같은 라이브러리만 재사용).

---

## 8. 에러 처리

| HTTP / 응답 | 도메인 예외 | 라우터 매핑 | UseCase 정책 |
|-------------|-------------|-------------|--------------|
| 401 / 403 | `KiwoomCredentialRejectedError` | 400 | UseCase 가 다른 시장 호출 계속 (원인 자격증명 동일이면 모두 실패하지만 outcome.error 로 노출) |
| 429 | tenacity 재시도 → 한계 도달시 `KiwoomRateLimitedError` | 503 | 시장 별 격리, 다음 시장 진입 |
| 5xx, 네트워크 | `KiwoomUpstreamError` | 502 | 다음 시장 계속 |
| `return_code != 0` | `KiwoomBusinessError(return_code, return_msg)` | 400 + detail | 다음 시장 계속 |
| Pydantic 검증 실패 (필드 누락 / 타입 불일치) | `KiwoomResponseValidationError` | 502 | 다음 시장 계속 |
| 페이지네이션 무한 루프 (max_pages=100 도달) | `KiwoomPaginationLimitError` | 502 | 그 시장 fail, 다음 시장 계속 |
| 빈 응답 `list=[]` | (정상) | 200 | upserted=0, deactivated=0 (보수적으로 skip — `deactivate_missing` 호출 안 함) |
| `regDay` 가 `YYYYMMDD` 가 아님 | `_parse_yyyymmdd` 가 None 반환 | — | `listed_date=NULL` 로 저장 |
| `listCount` 가 비숫자 | `int()` 변환 실패 → `KiwoomResponseValidationError` | 502 | 그 시장 fail (방어적) |

### 8.1 시장 단위 트랜잭션 격리

```python
for mrkt in targets:
    try:
        async with session.begin_nested():    # SAVEPOINT
            await self._sync_one_market(mrkt)
    except Exception as exc:
        logger.warning("market %s sync 실패: %s", mrkt.value, exc)
        # outer 트랜잭션은 살아 있음 — 다음 시장 진입
```

→ 한 시장의 partial write 가 commit 되면 다른 시장 sync 결과도 함께 commit 되도록 outer 트랜잭션 끝에 1회 commit. 격리 boundary 는 SAVEPOINT (`begin_nested`).

---

## 9. 테스트

### 9.1 Unit (MockTransport)

`tests/adapter/kiwoom/test_stkinfo_stock_list.py`:

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 단일 페이지 | mrkt_tp=0 + 200 + list 5건 (cont-yn=N) | `fetch_stock_list` 5건 반환 |
| 다중 페이지 | 첫 응답 cont-yn=Y + next-key + list 100건, 두번째 N + list 50건 | call_paginated 2회, 합쳐서 150건 |
| 빈 list | 200 + `list=[]` | 빈 list 반환 (예외 안 던짐) |
| `return_code=1` | 비즈니스 에러 | `KiwoomBusinessError` |
| 401 | 자격증명 거부 | `KiwoomCredentialRejectedError` |
| 페이지네이션 폭주 | cont-yn=Y 무한 반복 | `max_pages=10` 도달시 `KiwoomPaginationLimitError` |
| 응답 row 의 `regDay="invalid"` | 정상 200 | `to_normalized()` 가 `listed_date=None` 반환 |
| 응답 row 의 `listCount="abc"` | 200 + 비숫자 | `int()` 변환 실패 — `KiwoomResponseValidationError` |
| `nxtEnable=""` | 빈 문자열 | `nxt_enable=False` |
| `nxtEnable="y"` (소문자) | 케이스 변동 | `nxt_enable=True` (upper() 처리) |
| Pydantic extra 필드 | 응답에 신규 필드 추가됨 | `extra="ignore"` 로 통과 |

### 9.2 Integration (testcontainers)

`tests/application/test_stock_master_service.py`:

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| 첫 sync (빈 DB) | 5 시장 모두 200 + 종목 | `total_upserted > 0`, `total_deactivated=0`, `total_nxt_enabled` 측정 |
| 재 sync (변경 없음) | 같은 응답 | `total_upserted=동일`, `total_deactivated=0` |
| 상장폐지 처리 | 첫 sync 후 응답에서 `005930` 빠짐 | `Stock(stock_code='005930').is_active=False` |
| 재상장 | 비활성 종목이 다시 응답에 등장 | `is_active=True` 복원 + 다른 필드 갱신 |
| 한 시장 호출 실패 | 시장 0 정상, 시장 10 이 502 | 시장 0 적재, 시장 10 outcome.error != None, 시장 0 의 deactivated 정상 |
| 시장 격리 (KOSPI sync 가 KOSDAQ 종목을 비활성화하지 않음) | 시장 0 만 sync | KOSDAQ 종목의 `is_active` 변동 없음 |
| nxt_enable 변경 | 첫 sync nxt_enable=true → 둘째 sync 응답에 `nxtEnable=""` | `Stock.nxt_enable=False` UPDATE |
| mock 도메인 강제 false | env="mock" + 응답 `nxtEnable="Y"` | DB `nxt_enable=False` (응답 무시) |
| 빈 응답일 때 deactivate skip | 시장 응답 `list=[]` | 그 시장 종목 비활성화하지 않음 (보수적) |
| 중복 `code` (Excel 샘플처럼 같은 코드 5회 등장) | 응답에 같은 stock_code 5번 | upsert 결과 1 row (마지막 값으로 덮어쓰기) |

### 9.3 E2E (요청 시 1회)

```python
@pytest.mark.requires_kiwoom_real
async def test_real_stock_master_sync():
    # 사전: 운영 자격증명 + 토큰 발급
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
        # KOSPI ~900~1000 종목 예상
        kospi = await stkinfo.fetch_stock_list(StockListMarketType.KOSPI)
        assert 800 <= len(kospi) <= 1200
        nxt_count = sum(1 for r in kospi if r.nxtEnable.upper() == "Y")
        # 가정: KOSPI 의 NXT 가능 종목은 100~500개 범위
        assert 50 <= nxt_count <= 800
        # KOSDAQ ~1500~1700
        kosdaq = await stkinfo.fetch_stock_list(StockListMarketType.KOSDAQ)
        assert 1300 <= len(kosdaq) <= 2000
    finally:
        async with KiwoomAuthClient(base_url="https://api.kiwoom.com") as auth:
            await auth.revoke_token(creds, token.token)
```

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `app/application/constants.py` — `StockListMarketType` StrEnum (16종)
- [ ] `app/adapter/out/kiwoom/_records.py` — `StockListRow`, `NormalizedStock`, `_parse_yyyymmdd`
- [ ] `app/adapter/out/kiwoom/stkinfo.py` — `KiwoomStkInfoClient.fetch_stock_list`
- [ ] `app/adapter/out/persistence/models/stock.py` — `Stock` ORM
- [ ] `app/adapter/out/persistence/repositories/stock.py` — `StockRepository.upsert_many` / `deactivate_missing` / `list_nxt_enabled`
- [ ] `app/application/service/stock_master_service.py` — `SyncStockMasterUseCase`
- [ ] `app/adapter/web/routers/stocks.py` — `GET/POST /api/kiwoom/stocks` + `/sync` + `/nxt-eligible`
- [ ] `app/batch/daily_master_job.py` — APScheduler 등록 (KST mon-fri 17:30)
- [ ] `migrations/versions/001_init_kiwoom_schema.py` — `stock` 테이블 정의 (Phase A 의 Migration 001 에 포함)

### 10.2 테스트

- [ ] Unit 11 시나리오 (§9.1) PASS
- [ ] Integration 10 시나리오 (§9.2) PASS
- [ ] coverage `KiwoomStkInfoClient`, `SyncStockMasterUseCase`, `StockRepository` ≥ 80%

### 10.3 운영 검증

- [ ] 5개 시장 모두 호출 성공 + 시장별 종목 수 확인 (KOSPI ≥ 800, KOSDAQ ≥ 1500 추정)
- [ ] `marketCode` 응답 값 ↔ 요청 `mrkt_tp` 일치 여부 확인 — Excel 예시는 mrkt_tp="0" 요청에 marketCode="10" 응답 (Excel 샘플 오류로 보이나 검증 필수)
- [ ] `code` 길이 분포 (예상: 6자리 numeric. 그 외 등장하면 schema 조정)
- [ ] `listCount` zero-padding 자릿수 검증 (16 자리 추정 — 다른 자릿수 등장하면 파서 보강)
- [ ] `regDay` 형식 (예상 YYYYMMDD. 빈 문자열 처리 필요한 종목 비율)
- [ ] `nxtEnable` 가 KRX/NXT 분리 + 코스닥/코스피 비율 확인 (예: KOSPI 30%, KOSDAQ 80% 가능?)
- [ ] 멱등성: 같은 sync 두 번 → `total_upserted=동일`, `total_deactivated=0`
- [ ] 페이지네이션 발생 확인 (KOSPI/KOSDAQ 둘 다 발생 추정)
- [ ] 같은 종목이 여러 시장에 등장하는지 (예: ETF 가 시장 60 + 시장 8 양쪽에) — UNIQUE 제약 위반 가능성. 위반시 `market_code` 갱신 정책 결정 필요

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10099 stock list sync (5 markets, NXT enable detection)`
- [ ] `master.md` § 12 결정 기록에 시장별 종목 수, NXT 가능 비율, 페이지네이션 동작 메모
- [ ] Phase B 후 `nxt-eligible` 큐 사이즈 확정값을 master.md 에 기록 (Phase C 부하 산정)

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | Phase B 수집 시장 범위 | (a) `0,10,50,60,6` 5개 / (b) + ETN_LOSS_LIMIT=70 / (c) ETF=8 도 포함 | Phase B 착수 직전 |
| 2 | 한 종목이 여러 시장에 등장하는 경우 | UNIQUE 제약 위반 → `market_code` 갱신 vs 시장별 별도 row | 운영 검증 후 |
| 3 | mock 환경 ka10099 호출 허용 여부 | (a) 허용 + nxt_enable 강제 false (권장) / (b) prod 만 허용 | Phase A 후반 |
| 4 | 디액티베이션 빈 응답 보호 | (a) 빈 응답이면 비활성화 skip (권장) / (b) 모두 비활성화 | 본 endpoint 내 (§5.3) |
| 5 | `regDay`/`listCount` 누락 종목 처리 | NULL 허용 (권장) / 그 row 자체를 skip | 본 endpoint 내 (§3.4) |
| 6 | 일 1회 cron alias | 단일 `prod-main` / 메타전용 `prod-meta` | Phase A 후반 |

### 11.2 알려진 위험

- **Excel 샘플 오류 의심**: R46 의 응답 예시는 모두 `code="005930"`, `marketCode="10"`(코스닥) 으로 동일 — 실제 운영 응답은 시장별로 다양한 종목이 들어올 것. 첫 호출에서 raw response 검증 필수
- **`marketCode` 값 ↔ 요청 `mrkt_tp` 일치 여부 불명**: 요청 mrkt_tp="0"(코스피) 인데 응답 marketCode="10"(코스닥)? Excel 샘플의 일관성 문제일 가능성. 만약 실제로 일치하지 않으면 `requested_market_type` 컬럼을 별도 보존
- **종목 코드 6자리 가정**: 일반 종목은 6자리지만 ETF(`0033..`), ELW, 신주인수권 등은 자릿수가 다를 수 있음 → `stock_code VARCHAR(20)` 로 여유
- **상장 종목 수 추정치 불확실**: KOSPI ~900, KOSDAQ ~1700 가정인데 실제 키움 응답이 더 클 가능성. `max_pages=100` 한계가 충분한지 첫 호출에서 확인
- **`nxt_enable` Y/N 외 다른 값**: Excel 은 `Y: 가능` 만 명시. `N`/공백/null 외에 다른 값 가능성 — 일률 `Y == True, else False`
- **종목 중복 (같은 code 가 여러 시장)**: ETF 가 시장 8(ETF) 와 시장 0(KOSPI) 양쪽에 등장하면 UNIQUE 제약 위반. UseCase 가 시장별로 별도 sync 하므로 두 번째 시장 sync 시 ON CONFLICT UPDATE 가 `market_code` 를 덮어씀 — 의도와 어긋날 수 있음
- **`state` 다중값 파싱 안 함**: `"증거금20%|담보대출|신용가능"` 그대로 저장. 시그널/필터링 시 LIKE `'%관리종목%'` 로 검색 — 검색 성능을 위해 별도 컬럼 분해는 검증 후 결정
- **외국기업 표기**: `companyClassName="외국기업"` 인 종목의 백테스팅 처리 정책 (배당 / 환율 영향 / 거래단위) 별도 결정 필요

### 11.3 ka10099 vs ka10100 역할 분담

| 항목 | ka10099 | ka10100 |
|------|---------|---------|
| 호출 단위 | 시장 (mrkt_tp) | 종목 (stk_cd) |
| 호출 빈도 | 일 1회 (전체 sync) | 신규 종목 발견 시 단건 보강 |
| 응답 row 수 | 시장당 수백~수천 | 1 |
| `nxtEnable` 필드 | ★ source | 보강 |
| 페이지네이션 | Y | N |
| Phase B 코드 책임 | `SyncStockMasterUseCase` | `LookupStockUseCase` (보강) |

→ ka10099 가 **bulk source**, ka10100 이 **gap-filler**. 두 endpoint 의 응답 row 가 사실상 동일 스키마이므로 `NormalizedStock` 변환 로직은 공유.

### 11.4 향후 확장

- **stock.sector_id FK** (Phase B 후속): ka10099 의 `up_name` 을 ka10101 sector 의 `sector_name` 으로 매핑. 한글 일치 보장 안 됨 — 별도 매핑 테이블 필요
- **stock_history 테이블**: `last_price`, `state`, `audit_info` 의 일별 변동을 추적하려면 본 테이블에 stamp 보관이 아닌 history 분리 필요. 백테스팅 1차에는 불필요
- **상장폐지 종목의 백테스팅 포함 여부**: `is_active=false` 종목도 과거 시계열은 살아있음 → 백테스팅 시점의 active 여부를 별도 join 필요
- **ETF/ELW 별도 처리**: 시장 8(ETF), 3(ELW) 는 회수율/만기일 등 추가 필드 필요 — Phase B 범위 외

---

_Phase B 의 첫 endpoint, 그리고 백테스팅의 진입점. 본 endpoint 응답이 Phase C 의 ka10081 NXT 호출 큐를 만들고, Phase F 순위 endpoint 의 종목명 lookup source 가 된다. ka10099 가 정확하지 않으면 모든 후속 시계열이 어긋난다._
