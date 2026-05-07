# endpoint-05-ka10001.md — 주식기본정보요청 (펀더멘털)

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10001` |
| API 명 | 주식기본정보요청 |
| 분류 | Tier 2 (펀더멘털 스냅샷) |
| Phase | **B** |
| 우선순위 | **P1** (백테스팅 시그널 보강) |
| Method | `POST` |
| URL | `/api/dostk/stkinfo` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX 만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| 의존 endpoint | `au10001` (토큰), `ka10099` (stock 마스터 — FK source) |
| 후속 endpoint | Phase C 의 ka10081 (가격 시계열과 결합) |

---

## 1. 목적

종목 한 건의 **펀더멘털 + 일중 시세 + 250일 통계** 를 한 응답으로 가져와 일별 스냅샷으로 적재한다. 키움이 한 endpoint 에 4가지 성격의 데이터를 묶어둔 형태:

1. **재무 펀더멘털** (PER, EPS, ROE, PBR, EV, BPS, 매출액/영업이익/당기순이익) — 시그널 필터링
2. **시가총액 / 유통주식 / 외인소진률 / 신용비율** — 종목 규모 / 수급 시그널
3. **연중/250일 최고·최저** — 추세 / 상대 위치 시그널
4. **현재가 / 시가 / 고가 / 저가 / 거래량 / 등락율** — 일중 시세 (단, 실시간성은 약함 — Phase C 의 ka10081/86 이 정확)

**왜 P1 (P0 아님)**:
- Phase C 의 일봉 시계열로 백테스팅의 코어가 동작
- 펀더멘털은 "백테스팅 진입 종목 필터링" 시점에 필요 — 1차 백테스팅 후 시나리오 보강 단계
- 그러나 Phase B 에 포함시킨 이유: stock 마스터(ka10099/ka10100) 와 함께 종목 단위 메타를 한 번에 적재해 Phase C 일봉 수집 큐에 풀 메타 동반 가능

**핵심 특성**: 응답이 **45 필드** 로 가장 큰 spec. PER/ROE 는 외부 벤더 데이터로 **주 1회 또는 실적발표 시즌에만 갱신** (Excel R41/R43 주의 사항). 따라서 일별 적재해도 같은 값이 며칠 반복 — 변경 감지 컬럼 추가 권장.

---

## 2. Request 명세

### 2.1 Header

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `api-id` | TR 명 | String | Y | 10 | `"ka10001"` 고정 |
| `authorization` | 접근토큰 | String | Y | 1000 | `Bearer <token>` |
| `cont-yn` | 연속조회 여부 | String | N | 1 | (단건 — 거의 안 씀) |
| `next-key` | 연속조회 키 | String | N | 50 | (단건 — 거의 안 씀) |

### 2.2 Body

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `stk_cd` | 종목코드 | String | Y | **20** | 거래소별 종목코드 — KRX `005930`, NXT `005930_NX`, SOR `005930_AL` |

> **차이점**: ka10100 의 stk_cd Length=6 (suffix 거부) 와 달리 ka10001 은 **Length=20 + `_NX`/`_AL` 허용**. NXT 시세 펀더멘털을 별도로 받아볼 수 있는 구조.

### 2.3 Request 예시

```json
POST https://api.kiwoom.com/api/dostk/stkinfo
Content-Type: application/json;charset=UTF-8
api-id: ka10001
authorization: Bearer WQJCwyqInphKnR3bSRtB9NE1lv...

{
    "stk_cd": "005930"
}
```

### 2.4 Pydantic 모델 — exchange 별 호출 헬퍼

```python
# app/adapter/out/kiwoom/stkinfo.py
class StockBasicInfoRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    stk_cd: Annotated[str, Field(min_length=6, max_length=20)]


def build_stk_cd(stock_code: str, exchange: ExchangeType) -> str:
    """master.md § 3.4 의 to_kiwoom_code 와 동일 — 의존 분리 위해 본 모듈에도 helper.

    KRX:  '005930'      → '005930'
    NXT:  '005930'      → '005930_NX'
    SOR:  '005930'      → '005930_AL'
    """
    if exchange is ExchangeType.KRX:
        return stock_code
    if exchange is ExchangeType.NXT:
        return f"{stock_code}_NX"
    if exchange is ExchangeType.SOR:
        return f"{stock_code}_AL"
    raise ValueError(f"unknown exchange: {exchange}")
```

---

## 3. Response 명세

### 3.1 Header

| Element | Type | Description |
|---------|------|-------------|
| `api-id` | String | `"ka10001"` 에코 |
| `cont-yn` | String | (단건 — N) |
| `next-key` | String | (단건 — 빈값) |

### 3.2 Body — 45 필드 (4 카테고리)

키움 응답 필드를 카테고리 별로 묶음. Excel R28~R72 원문:

#### A. 종목 기본 (3)

| Element | 한글명 | 영속화 컬럼 | 메모 |
|---------|-------|-------------|------|
| `stk_cd` | 종목코드 | (FK lookup) | 거래소 suffix 포함 가능 — split 후 base code 로 stock 매핑 |
| `stk_nm` | 종목명 | (검증 only) | stock 마스터의 stock_name 과 일치해야 함. 불일치 시 alert |
| `setl_mm` | 결산월 | `settlement_month` (CHAR(2)) | "12", "03" 등 |

#### B. 자본 / 시가총액 / 외인 (8)

| Element | 한글명 | 영속화 컬럼 | 단위 / 메모 |
|---------|-------|-------------|-------------|
| `fav` | 액면가 | `face_value` (BIGINT) | KRW |
| `fav_unit` | 액면가단위 | `face_value_unit` (VARCHAR(10)) | "원", "달러" 등 |
| `cap` | 자본금 | `capital_won` (BIGINT) | 백만원 추정 — 운영 검증 필요 |
| `flo_stk` | 상장주식 | `listed_shares` (BIGINT) | 천주 추정 — Excel 예시 "25527" |
| `mac` | 시가총액 | `market_cap` (BIGINT) | 억원 추정 — Excel 예시 "24352" |
| `mac_wght` | 시가총액비중 | `market_cap_weight` (NUMERIC(8,4)) | % |
| `for_exh_rt` | 외인소진률 | `foreign_holding_rate` (NUMERIC(8,4)) | % |
| `repl_pric` | 대용가 | `replacement_price` (BIGINT) | KRW |
| `crd_rt` | 신용비율 | `credit_rate` (NUMERIC(8,4)) | % — Excel `"+0.08"` 부호 포함 |
| `dstr_stk` | 유통주식 | `circulating_shares` (BIGINT) | 천주 |
| `dstr_rt` | 유통비율 | `circulating_rate` (NUMERIC(8,4)) | % |

#### C. 펀더멘털 (재무 비율) — 9 필드 ★

> ⚠️ Excel R41/R43: **PER, ROE 는 외부 벤더 제공 — 주 1회 또는 실적발표 시즌에만 갱신**. 일별 적재 시 며칠 반복 가능.

| Element | 한글명 | 영속화 컬럼 | 단위 |
|---------|-------|-------------|------|
| `per` | PER | `per_ratio` (NUMERIC(10,2)) | 배 |
| `eps` | EPS | `eps_won` (BIGINT) | KRW |
| `roe` | ROE | `roe_pct` (NUMERIC(8,2)) | % |
| `pbr` | PBR | `pbr_ratio` (NUMERIC(10,2)) | 배 |
| `ev` | EV | `ev_ratio` (NUMERIC(10,2)) | EV/EBITDA 추정 — 운영 검증 |
| `bps` | BPS | `bps_won` (BIGINT) | KRW |
| `sale_amt` | 매출액 | `revenue_amount` (BIGINT) | 억원 추정 |
| `bus_pro` | 영업이익 | `operating_profit` (BIGINT) | 억원 |
| `cup_nga` | 당기순이익 | `net_profit` (BIGINT) | 억원 |

#### D. 250일 통계 (4)

| Element | 한글명 | 영속화 컬럼 | 메모 |
|---------|-------|-------------|------|
| `250hgst` | 250최고 | `high_250d` (BIGINT) | KRW |
| `250hgst_pric_dt` | 250최고가일 | `high_250d_date` (DATE) | YYYYMMDD |
| `250hgst_pric_pre_rt` | 250최고가대비율 | `high_250d_pre_rate` (NUMERIC(8,4)) | % |
| `250lwst` | 250최저 | `low_250d` (BIGINT) | KRW |
| `250lwst_pric_dt` | 250최저가일 | `low_250d_date` (DATE) | YYYYMMDD |
| `250lwst_pric_pre_rt` | 250최저가대비율 | `low_250d_pre_rate` (NUMERIC(8,4)) | % |
| `oyr_hgst` | 연중최고 | `year_high` (BIGINT) | KRW — Excel 예시 `"+181400"` 부호 |
| `oyr_lwst` | 연중최저 | `year_low` (BIGINT) | KRW — Excel 예시 `"-91200"` 부호 (음수가 가능?) |

> Excel 의 `oyr_hgst="+181400"`, `oyr_lwst="-91200"` 의 부호는 의미 불명 (단순 표기 vs 전일 대비?). 운영 검증 필수.

#### E. 일중 시세 (10)

| Element | 한글명 | 영속화 컬럼 | 메모 |
|---------|-------|-------------|------|
| `cur_prc` | 현재가 | `current_price` (BIGINT) | KRW |
| `pre_sig` | 대비기호 | `prev_compare_sign` (CHAR(1)) | `1`=상한, `2`=상승, `3`=보합, `4`=하한, `5`=하락 (운영 검증) |
| `pred_pre` | 전일대비 | `prev_compare_amount` (BIGINT) | KRW |
| `flu_rt` | 등락율 | `change_rate` (NUMERIC(8,4)) | % |
| `trde_qty` | 거래량 | `trade_volume` (BIGINT) | 주 |
| `trde_pre` | 거래대비 | `trade_compare_rate` (NUMERIC(8,4)) | % |
| `open_pric` | 시가 | `open_price` (BIGINT) | KRW |
| `high_pric` | 고가 | `high_price` (BIGINT) | KRW |
| `low_pric` | 저가 | `low_price` (BIGINT) | KRW |
| `upl_pric` | 상한가 | `upper_limit_price` (BIGINT) | KRW |
| `lst_pric` | 하한가 | `lower_limit_price` (BIGINT) | KRW |
| `base_pric` | 기준가 | `base_price` (BIGINT) | KRW (전일 종가 기반) |
| `exp_cntr_pric` | 예상체결가 | `expected_match_price` (BIGINT) | KRW (장외 시간대 only) |
| `exp_cntr_qty` | 예상체결수량 | `expected_match_volume` (BIGINT) | 주 |

### 3.3 Response 예시 (Excel R76 — 일부)

```json
{
    "stk_cd": "005930",
    "stk_nm": "삼성전자",
    "setl_mm": "12",
    "fav": "5000",
    "cap": "1311",
    "flo_stk": "25527",
    "crd_rt": "+0.08",
    "oyr_hgst": "+181400",
    "oyr_lwst": "-91200",
    "mac": "24352",
    "mac_wght": "",
    "for_exh_rt": "0.00",
    "repl_pric": "66780",
    "per": "",
    "eps": "",
    "roe": "",
    "pbr": "",
    "ev": "",
    "bps": "-75300",
    "sale_amt": "...",
    ...
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다"
}
```

> Excel 예시에서 PER/EPS/ROE/PBR/EV 가 모두 빈값 — 외부 벤더 공급 시점에 따라 빈값일 수 있음. 컬럼은 **NULL 허용** 필수.

### 3.4 Pydantic 모델

```python
# app/adapter/out/kiwoom/_records.py
class StockBasicInfoResponse(BaseModel):
    """ka10001 응답 — 45 필드 flat object."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    # A. 기본
    stk_cd: Annotated[str, Field(min_length=1, max_length=20)]
    stk_nm: Annotated[str, Field(max_length=40)] = ""
    setl_mm: str = ""

    # B. 자본 / 시총 / 외인
    fav: str = ""
    fav_unit: str = ""
    cap: str = ""
    flo_stk: str = ""
    mac: str = ""
    mac_wght: str = ""
    for_exh_rt: str = ""
    repl_pric: str = ""
    crd_rt: str = ""
    dstr_stk: str = ""
    dstr_rt: str = ""

    # C. 펀더멘털 (재무 비율)
    per: str = ""
    eps: str = ""
    roe: str = ""
    pbr: str = ""
    ev: str = ""
    bps: str = ""
    sale_amt: str = ""
    bus_pro: str = ""
    cup_nga: str = ""

    # D. 250일 / 연중 통계
    # Pydantic 필드명은 식별자 첫 글자가 숫자 불가 → alias 매핑
    high_250d: str = Field(default="", alias="250hgst")
    high_250d_date: str = Field(default="", alias="250hgst_pric_dt")
    high_250d_pre_rate: str = Field(default="", alias="250hgst_pric_pre_rt")
    low_250d: str = Field(default="", alias="250lwst")
    low_250d_date: str = Field(default="", alias="250lwst_pric_dt")
    low_250d_pre_rate: str = Field(default="", alias="250lwst_pric_pre_rt")
    oyr_hgst: str = ""
    oyr_lwst: str = ""

    # E. 일중 시세
    cur_prc: str = ""
    pre_sig: str = ""
    pred_pre: str = ""
    flu_rt: str = ""
    trde_qty: str = ""
    trde_pre: str = ""
    open_pric: str = ""
    high_pric: str = ""
    low_pric: str = ""
    upl_pric: str = ""
    lst_pric: str = ""
    base_pric: str = ""
    exp_cntr_pric: str = ""
    exp_cntr_qty: str = ""

    # 처리 결과
    return_code: int = 0
    return_msg: str = ""

    @model_validator(mode="after")
    def _trim_strings(self) -> "StockBasicInfoResponse":
        """모든 string 필드의 zero-padding / 부호 보존 (캐스팅은 to_normalized 에서)."""
        return self
```

> Pydantic v2 의 alias 로 `250hgst` 같은 비-식별자 키 처리. populate_by_name 옵션은 model_config 에 추가:

```python
    model_config = ConfigDict(frozen=True, extra="ignore", populate_by_name=True)
```

### 3.5 정규화 (string → BIGINT/NUMERIC/DATE)

```python
@dataclass(frozen=True, slots=True)
class NormalizedFundamental:
    stock_code: str             # base code (suffix 제거)
    exchange: ExchangeType      # 어느 거래소로 호출했는지
    asof_date: date             # 응답 시점 (KST 오늘 — 응답에는 날짜 필드 없음)
    stock_name: str
    settlement_month: str | None

    # B
    face_value: int | None
    face_value_unit: str | None
    capital_won: int | None
    listed_shares: int | None
    market_cap: int | None
    market_cap_weight: Decimal | None
    foreign_holding_rate: Decimal | None
    replacement_price: int | None
    credit_rate: Decimal | None
    circulating_shares: int | None
    circulating_rate: Decimal | None

    # C
    per_ratio: Decimal | None
    eps_won: int | None
    roe_pct: Decimal | None
    pbr_ratio: Decimal | None
    ev_ratio: Decimal | None
    bps_won: int | None
    revenue_amount: int | None
    operating_profit: int | None
    net_profit: int | None

    # D
    high_250d: int | None
    high_250d_date: date | None
    high_250d_pre_rate: Decimal | None
    low_250d: int | None
    low_250d_date: date | None
    low_250d_pre_rate: Decimal | None
    year_high: int | None
    year_low: int | None

    # E
    current_price: int | None
    prev_compare_sign: str | None
    prev_compare_amount: int | None
    change_rate: Decimal | None
    trade_volume: int | None
    trade_compare_rate: Decimal | None
    open_price: int | None
    high_price: int | None
    low_price: int | None
    upper_limit_price: int | None
    lower_limit_price: int | None
    base_price: int | None
    expected_match_price: int | None
    expected_match_volume: int | None


def _to_int(s: str) -> int | None:
    """zero-padded 또는 부호 포함 → int. 빈값/공백/'-'/잘못된 값은 None."""
    if not s or s in ("-", "+"):
        return None
    s = s.strip().replace(",", "")
    try:
        return int(s)        # "+181400" → 181400, "-91200" → -91200, "00136000" → 136000
    except ValueError:
        return None


def _to_decimal(s: str) -> Decimal | None:
    if not s or s in ("-", "+"):
        return None
    try:
        return Decimal(s.strip())
    except (InvalidOperation, ValueError):
        return None


def normalize_basic_info(
    response: StockBasicInfoResponse,
    *,
    exchange: ExchangeType,
    asof_date: date,
) -> NormalizedFundamental:
    base_code = strip_kiwoom_suffix(response.stk_cd)    # "005930_NX" → "005930"

    return NormalizedFundamental(
        stock_code=base_code,
        exchange=exchange,
        asof_date=asof_date,
        stock_name=response.stk_nm,
        settlement_month=response.setl_mm or None,

        face_value=_to_int(response.fav),
        face_value_unit=response.fav_unit or None,
        capital_won=_to_int(response.cap),
        listed_shares=_to_int(response.flo_stk),
        market_cap=_to_int(response.mac),
        market_cap_weight=_to_decimal(response.mac_wght),
        foreign_holding_rate=_to_decimal(response.for_exh_rt),
        replacement_price=_to_int(response.repl_pric),
        credit_rate=_to_decimal(response.crd_rt),
        circulating_shares=_to_int(response.dstr_stk),
        circulating_rate=_to_decimal(response.dstr_rt),

        per_ratio=_to_decimal(response.per),
        eps_won=_to_int(response.eps),
        roe_pct=_to_decimal(response.roe),
        pbr_ratio=_to_decimal(response.pbr),
        ev_ratio=_to_decimal(response.ev),
        bps_won=_to_int(response.bps),
        revenue_amount=_to_int(response.sale_amt),
        operating_profit=_to_int(response.bus_pro),
        net_profit=_to_int(response.cup_nga),

        high_250d=_to_int(response.high_250d),
        high_250d_date=_parse_yyyymmdd(response.high_250d_date),
        high_250d_pre_rate=_to_decimal(response.high_250d_pre_rate),
        low_250d=_to_int(response.low_250d),
        low_250d_date=_parse_yyyymmdd(response.low_250d_date),
        low_250d_pre_rate=_to_decimal(response.low_250d_pre_rate),
        year_high=_to_int(response.oyr_hgst),
        year_low=_to_int(response.oyr_lwst),

        current_price=_to_int(response.cur_prc),
        prev_compare_sign=response.pre_sig or None,
        prev_compare_amount=_to_int(response.pred_pre),
        change_rate=_to_decimal(response.flu_rt),
        trade_volume=_to_int(response.trde_qty),
        trade_compare_rate=_to_decimal(response.trde_pre),
        open_price=_to_int(response.open_pric),
        high_price=_to_int(response.high_pric),
        low_price=_to_int(response.low_pric),
        upper_limit_price=_to_int(response.upl_pric),
        lower_limit_price=_to_int(response.lst_pric),
        base_price=_to_int(response.base_pric),
        expected_match_price=_to_int(response.exp_cntr_pric),
        expected_match_volume=_to_int(response.exp_cntr_qty),
    )


def strip_kiwoom_suffix(stk_cd: str) -> str:
    """'005930_NX' → '005930', '005930_AL' → '005930', '005930' → '005930'."""
    return stk_cd.split("_")[0]
```

---

## 4. NXT 처리

| 항목 | 적용 여부 |
|------|-----------|
| `stk_cd` 에 `_NX` suffix | **Y** (Length=20 + Excel R22 명시) |
| `nxt_enable` 게이팅 | **Y** (NXT 호출 전 stock.nxt_enable=true 검증) |
| `mrkt_tp` 별 분리 | N (단건이라 mrkt_tp 없음) |
| KRX 운영 / 모의 차이 | mock 도메인은 NXT 미지원 → mock 환경에서 `_NX` 호출 시 4xx 또는 빈 응답 추정 |

### 4.1 KRX vs NXT 호출 분기

```python
async def fetch_basic_info(
    self,
    stock_code: str,
    *,
    exchange: ExchangeType = ExchangeType.KRX,
) -> StockBasicInfoResponse:
    stk_cd = build_stk_cd(stock_code, exchange)    # "005930" or "005930_NX"
    return await self._call_basic_info(stk_cd)


# UseCase 의 호출 패턴:
# 1. KRX 펀더멘털: 모든 active 종목에 대해 호출
# 2. NXT 펀더멘털: nxt_enable=true 종목에 대해 추가 호출
```

### 4.2 KRX vs NXT 의 데이터 차이

| 필드 | KRX | NXT |
|------|-----|-----|
| 재무 펀더멘털 (PER/EPS/ROE/PBR/EV/BPS) | 동일 | 동일 (외부 벤더 데이터, 거래소 무관) |
| 시가총액 (mac) | 동일 | 동일 (상장주식 × 종가 — 어느 거래소 종가?) |
| **현재가 / 시가 / 고가 / 저가 / 거래량** | KRX 시세 | NXT 시세 (분리됨) |
| **상한가 / 하한가** | KRX 호가단위 | NXT 호가단위 (다를 수 있음) |
| **연중/250일 최고·최저** | KRX 시계열 | NXT 시계열 (NXT 운영 기간이 짧아 데이터 부족 가능) |

→ **펀더멘털 컬럼 중 일중 시세 영역(E) 만 거래소 분리 의미가 있음**. 재무 비율(C) 는 KRX 1회 호출로 충분.

### 4.3 권장 호출 정책 (Phase B 단계)

| 정책 | 설명 |
|------|------|
| **A. KRX 만 호출** (기본) | 모든 active 종목 1회 KRX 호출. NXT 는 호출 안 함. **Phase B 권장** |
| **B. KRX + NXT 둘 다** | nxt_enable 종목은 NXT 도 추가 호출 → row 2개 |
| **C. KRX 한정 + NXT 시세는 ka10086 에 위임** | Phase C 의 ka10086 (일별 + 투자자별) 가 KRX/NXT 시세 분리 — ka10001 은 펀더멘털만 |

→ **(C) 채택**. ka10001 은 KRX 만 호출 (펀더멘털 + 일중시세). NXT 시세는 Phase C 의 ka10086 이 책임.

---

## 5. DB 스키마

### 5.1 신규 테이블 (Migration 002 — `002_stock_fundamental_and_sector.py`)

```sql
CREATE TABLE kiwoom.stock_fundamental (
    id                       BIGSERIAL PRIMARY KEY,
    stock_id                 BIGINT NOT NULL REFERENCES kiwoom.stock(id) ON DELETE CASCADE,
    asof_date                DATE NOT NULL,
    exchange                 VARCHAR(4) NOT NULL DEFAULT 'KRX',     -- KRX / NXT / SOR

    -- A
    settlement_month         CHAR(2),

    -- B
    face_value               BIGINT,
    face_value_unit          VARCHAR(10),
    capital_won              BIGINT,
    listed_shares            BIGINT,
    market_cap               BIGINT,
    market_cap_weight        NUMERIC(8,4),
    foreign_holding_rate     NUMERIC(8,4),
    replacement_price        BIGINT,
    credit_rate              NUMERIC(8,4),
    circulating_shares       BIGINT,
    circulating_rate         NUMERIC(8,4),

    -- C (PER/EPS/ROE/PBR/EV/BPS + 손익)
    per_ratio                NUMERIC(10,2),
    eps_won                  BIGINT,
    roe_pct                  NUMERIC(8,2),
    pbr_ratio                NUMERIC(10,2),
    ev_ratio                 NUMERIC(10,2),
    bps_won                  BIGINT,
    revenue_amount           BIGINT,
    operating_profit         BIGINT,
    net_profit               BIGINT,

    -- D (250일 / 연중 통계)
    high_250d                BIGINT,
    high_250d_date           DATE,
    high_250d_pre_rate       NUMERIC(8,4),
    low_250d                 BIGINT,
    low_250d_date            DATE,
    low_250d_pre_rate        NUMERIC(8,4),
    year_high                BIGINT,
    year_low                 BIGINT,

    -- E (일중 시세 — 응답 시점 KST)
    current_price            BIGINT,
    prev_compare_sign        CHAR(1),
    prev_compare_amount      BIGINT,
    change_rate              NUMERIC(8,4),
    trade_volume             BIGINT,
    trade_compare_rate       NUMERIC(8,4),
    open_price               BIGINT,
    high_price               BIGINT,
    low_price                BIGINT,
    upper_limit_price        BIGINT,
    lower_limit_price        BIGINT,
    base_price               BIGINT,
    expected_match_price     BIGINT,
    expected_match_volume    BIGINT,

    -- 변경 감지용 hash (PER/EPS/ROE/PBR/EV/BPS 기준 — 외부 벤더 데이터 변경 검출)
    fundamental_hash         CHAR(32),

    fetched_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_fundamental_stock_date_exchange
        UNIQUE (stock_id, asof_date, exchange)
);

CREATE INDEX idx_fundamental_asof_date ON kiwoom.stock_fundamental(asof_date);
CREATE INDEX idx_fundamental_stock_id  ON kiwoom.stock_fundamental(stock_id);
```

### 5.2 ORM 모델

```python
# app/adapter/out/persistence/models/stock_fundamental.py
class StockFundamental(Base):
    __tablename__ = "stock_fundamental"
    __table_args__ = (
        UniqueConstraint("stock_id", "asof_date", "exchange",
                          name="uq_fundamental_stock_date_exchange"),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("kiwoom.stock.id", ondelete="CASCADE"), nullable=False
    )
    asof_date: Mapped[date] = mapped_column(Date, nullable=False)
    exchange: Mapped[str] = mapped_column(String(4), nullable=False, server_default="KRX")

    settlement_month: Mapped[str | None] = mapped_column(String(2), nullable=True)

    face_value: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    face_value_unit: Mapped[str | None] = mapped_column(String(10), nullable=True)
    capital_won: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    listed_shares: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    market_cap: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    market_cap_weight: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    foreign_holding_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    replacement_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    credit_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    circulating_shares: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    circulating_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    per_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    eps_won: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    roe_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    pbr_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    ev_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    bps_won: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    revenue_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    operating_profit: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_profit: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    high_250d: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    high_250d_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    high_250d_pre_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    low_250d: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    low_250d_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    low_250d_pre_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    year_high: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    year_low: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    current_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_compare_sign: Mapped[str | None] = mapped_column(String(1), nullable=True)
    prev_compare_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    change_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    trade_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    trade_compare_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    open_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    high_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    low_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    upper_limit_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    lower_limit_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    base_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expected_match_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expected_match_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    fundamental_hash: Mapped[str | None] = mapped_column(String(32), nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

### 5.3 `fundamental_hash` 변경 감지 (선택적 최적화)

PER/EPS/ROE/PBR/EV/BPS 6 필드를 sorted MD5 로 hash. 같은 종목의 같은 hash 가 며칠 반복되면 "외부 벤더 갱신 없음" 으로 판정. 실제 사용처:

- **백테스팅 시그널**: PER 변동일 = 실적 발표일 추정 → 시그널 강화
- **alert**: hash 가 30일 이상 변동 없는 종목 = 벤더 데이터 stale 가능성

→ Phase B 1차에는 컬럼만 추가, 활용은 Phase F 에서 결정.

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomStkInfoClient.fetch_basic_info`

```python
class KiwoomStkInfoClient:
    PATH = "/api/dostk/stkinfo"

    async def fetch_basic_info(
        self,
        stock_code: str,
        *,
        exchange: ExchangeType = ExchangeType.KRX,
    ) -> StockBasicInfoResponse:
        """단건 펀더멘털. _NX/_AL suffix 자동 합성."""
        if not (len(stock_code) == 6 and stock_code.isdigit()):
            raise ValueError(f"stock_code 6자리 숫자만: {stock_code}")
        stk_cd = build_stk_cd(stock_code, exchange)
        result = await self._client.call(
            api_id="ka10001",
            endpoint=self.PATH,
            body={"stk_cd": stk_cd},
        )
        parsed = StockBasicInfoResponse.model_validate(result.body)
        if parsed.return_code != 0:
            raise KiwoomBusinessError(
                api_id="ka10001",
                return_code=parsed.return_code,
                return_msg=parsed.return_msg,
            )
        return parsed
```

### 6.2 Repository

```python
# app/adapter/out/persistence/repositories/stock_fundamental.py
class StockFundamentalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_one(self, row: NormalizedFundamental, *, stock_id: int) -> StockFundamental:
        """ON CONFLICT (stock_id, asof_date, exchange) UPDATE.

        - 같은 날 여러 번 호출되면 마지막 호출의 일중 시세로 갱신 (멱등 보장)
        - fundamental_hash 도 갱신 — 변경 감지용
        """
        f_hash = _compute_fundamental_hash(row)
        values = {
            "stock_id": stock_id,
            "asof_date": row.asof_date,
            "exchange": row.exchange.value,
            "settlement_month": row.settlement_month,
            "face_value": row.face_value,
            # ... 모든 컬럼
            "fundamental_hash": f_hash,
        }
        stmt = pg_insert(StockFundamental).values(values)
        update_set = {col: stmt.excluded[col] for col in values if col not in
                      ("stock_id", "asof_date", "exchange")}
        update_set["fetched_at"] = func.now()
        update_set["updated_at"] = func.now()
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_id", "asof_date", "exchange"],
            set_=update_set,
        ).returning(StockFundamental)
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one()

    async def find_latest(self, stock_id: int, *, exchange: str = "KRX") -> StockFundamental | None:
        stmt = (
            select(StockFundamental)
            .where(
                StockFundamental.stock_id == stock_id,
                StockFundamental.exchange == exchange,
            )
            .order_by(StockFundamental.asof_date.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()


def _compute_fundamental_hash(row: NormalizedFundamental) -> str:
    """PER/EPS/ROE/PBR/EV/BPS 6 필드 hash. 일중 시세는 제외 (매번 변동)."""
    parts = [
        f"{row.per_ratio}",
        f"{row.eps_won}",
        f"{row.roe_pct}",
        f"{row.pbr_ratio}",
        f"{row.ev_ratio}",
        f"{row.bps_won}",
    ]
    return hashlib.md5("|".join(parts).encode()).hexdigest()
```

### 6.3 UseCase — `SyncStockFundamentalUseCase`

```python
# app/application/service/stock_fundamental_service.py
class SyncStockFundamentalUseCase:
    """active 종목 전체에 대해 ka10001 호출 → stock_fundamental 일별 적재.

    호출 패턴:
    - exchange=KRX 만 호출 (NXT 시세는 ka10086 의 책임 — § 4.3 결정)
    - active stock 한 건당 1회 호출 → RPS 4 + 250ms 인터벌로 직렬
    - 한 종목 실패가 다른 종목을 막지 않음 (per-stock try/except)

    예상 호출 수:
    - active 종목 ~3000개 (KOSPI 900 + KOSDAQ 1700 + KONEX 200 + ETN 100 + REIT 100)
    - 호출 1건당 ~250ms → 750초 = 12.5분 / sync 1회
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
        self._stock_repo = StockRepository(session)
        self._fundamental_repo = StockFundamentalRepository(session)
        self._env = env

    async def execute(
        self,
        *,
        target_date: date | None = None,
        only_market_codes: Sequence[str] | None = None,
    ) -> FundamentalSyncResult:
        asof = target_date or date.today()

        stmt = select(Stock).where(Stock.is_active.is_(True))
        if only_market_codes:
            stmt = stmt.where(Stock.market_code.in_(only_market_codes))
        active_stocks = list((await self._session.execute(stmt)).scalars())

        success = 0
        failed = 0
        errors: list[tuple[str, str]] = []

        for stock in active_stocks:
            try:
                response = await self._client.fetch_basic_info(
                    stock.stock_code, exchange=ExchangeType.KRX,
                )
                normalized = normalize_basic_info(
                    response, exchange=ExchangeType.KRX, asof_date=asof,
                )
                # 종목명 mismatch 검증 — alert only, 적재는 진행
                if normalized.stock_name and normalized.stock_name != stock.stock_name:
                    logger.warning(
                        "stock_name mismatch %s: master=%s, ka10001=%s",
                        stock.stock_code, stock.stock_name, normalized.stock_name,
                    )
                await self._fundamental_repo.upsert_one(normalized, stock_id=stock.id)
                success += 1
            except (KiwoomBusinessError, KiwoomError) as exc:
                failed += 1
                errors.append((stock.stock_code, f"{type(exc).__name__}: {exc}"))
                logger.warning("ka10001 sync 실패 %s: %s", stock.stock_code, exc)
            except Exception:
                failed += 1
                logger.exception("ka10001 sync 예상치 못한 예외 %s", stock.stock_code)
                errors.append((stock.stock_code, "unexpected"))

        return FundamentalSyncResult(
            asof_date=asof,
            total=len(active_stocks),
            success=success,
            failed=failed,
            errors=errors,
        )


@dataclass(frozen=True, slots=True)
class FundamentalSyncResult:
    asof_date: date
    total: int
    success: int
    failed: int
    errors: list[tuple[str, str]]
```

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **수동 단건** | on-demand | `POST /api/kiwoom/stocks/{code}/fundamental` (admin) |
| **수동 전체** | on-demand | `POST /api/kiwoom/fundamentals/sync` (admin) |
| **일 1회 cron** | KST 17:45 평일 | ka10099 (17:30) 직후. 약 12분 소요 |
| **백필** | on-demand | `python scripts/backfill_fundamentals.py --start 2026-04-01 --end 2026-04-30` (과거 일자 — 단, 키움이 과거 펀더멘털을 응답하는지 운영 검증 필요) |

### 7.1 라우터

```python
# app/adapter/web/routers/fundamentals.py
router = APIRouter(prefix="/api/kiwoom/fundamentals", tags=["kiwoom-fundamentals"])


@router.post(
    "/sync",
    response_model=FundamentalSyncResultOut,
    dependencies=[Depends(require_admin_key)],
)
async def sync_fundamentals(
    body: FundamentalSyncRequestIn = Body(default_factory=FundamentalSyncRequestIn),
    use_case: SyncStockFundamentalUseCase = Depends(get_sync_fundamental_use_case),
) -> FundamentalSyncResultOut:
    result = await use_case.execute(
        target_date=body.target_date,
        only_market_codes=body.only_market_codes or None,
    )
    return FundamentalSyncResultOut.model_validate(asdict(result))


@router.get(
    "/{stock_code}/latest",
    response_model=StockFundamentalOut,
)
async def get_latest_fundamental(
    stock_code: str,
    exchange: Literal["KRX", "NXT", "SOR"] = Query(default="KRX"),
    session: AsyncSession = Depends(get_session),
) -> StockFundamentalOut:
    stock_repo = StockRepository(session)
    stock = await stock_repo.find_by_code(stock_code)
    if stock is None:
        raise HTTPException(status_code=404, detail=f"stock not found: {stock_code}")
    fundamental_repo = StockFundamentalRepository(session)
    f = await fundamental_repo.find_latest(stock.id, exchange=exchange)
    if f is None:
        raise HTTPException(status_code=404, detail="no fundamental data")
    return StockFundamentalOut.model_validate(f)
```

### 7.2 APScheduler Job

```python
# app/batch/daily_fundamental_job.py
async def fire_daily_fundamental_sync() -> None:
    """매 평일 17:45 KST — 펀더멘털 동기화."""
    if not is_trading_day(date.today()):
        return
    try:
        async with get_sessionmaker()() as session:
            kiwoom_client = build_kiwoom_client_for("prod-main")
            stkinfo = KiwoomStkInfoClient(kiwoom_client)
            uc = SyncStockFundamentalUseCase(
                session, stkinfo_client=stkinfo, env=settings.kiwoom_default_env,
            )
            result = await uc.execute()
            await session.commit()
        logger.info(
            "fundamental sync 완료 asof=%s total=%d success=%d failed=%d",
            result.asof_date, result.total, result.success, result.failed,
        )
        if result.failed > result.total * 0.1:    # 10% 초과 실패 alert
            logger.error("fundamental sync 실패율 과다 — 키움 자격증명/RPS 점검 필요")
    except Exception:
        logger.exception("fundamental sync 콜백 예외")


scheduler.add_job(
    fire_daily_fundamental_sync,
    CronTrigger(day_of_week="mon-fri", hour=17, minute=45, timezone=KST),
    id="fundamental_daily",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
    misfire_grace_time=60 * 30,    # 30분 grace — 12분 작업이라 여유
)
```

### 7.3 RPS / 시간 추정

| 파라미터 | 값 |
|----------|----|
| active 종목 수 (Phase B 5시장) | ~3,000 |
| 호출 간 인터벌 | 250ms (Semaphore=4 + interval) |
| 동시성 | 4 |
| 1회 sync 소요 | 3000 / 4 × 0.25 = 187초 ≈ 3분 (이론) |
| 실측 추정 | 키움 응답 50~150ms + 네트워크 → 5~12분 |
| 일 1회 17:45 cron grace | 30분 |

→ 3분 ~ 12분 범위. 실측 후 cron interval 조정.

---

## 8. 에러 처리

| HTTP / 응답 | 도메인 예외 | 라우터 매핑 | UseCase 정책 |
|-------------|-------------|-------------|--------------|
| 400 (잘못된 stock_code) | `ValueError` | 400 | 호출 전 차단 |
| 401 / 403 | `KiwoomCredentialRejectedError` | 400 | UseCase 가 다음 종목으로 진행 (단, 자격증명 문제면 모두 실패하므로 outcome 으로 노출) |
| 429 | tenacity 재시도 → `KiwoomRateLimitedError` | 503 | UseCase 가 다음 종목 진행 (RPS 가드 동작 검증) |
| 5xx, 네트워크 | `KiwoomUpstreamError` | 502 | 다음 종목 진행 |
| `return_code != 0` | `KiwoomBusinessError` | 400 + detail | 다음 종목 진행 |
| Pydantic 검증 실패 | `KiwoomResponseValidationError` | 502 | 다음 종목 진행 |
| `_to_int(stk_cd)` failure | (변환 None) | — | NULL 저장 (적재는 진행) |
| `stk_nm` mismatch with stock master | (warning only) | — | adapt 후 적재. 별도 alert 로그 |
| FK 위반 (stock 미등록) | `IntegrityError` | 502 | UseCase 가 ensure_exists (ka10100) lazy 호출 후 재시도 권장 |

### 8.1 partial 실패 정책

3000 종목 중 일부 실패 시 정책:

- **< 1% 실패** (~30종목): 정상. errors 리스트만 로그
- **1~10% 실패** (30~300종목): warning 로그 + alert
- **> 10% 실패**: error 로그 + 다음 sync 자동 retry 검토 필요. 자격증명 / 키움 장애 의심

---

## 9. 테스트

### 9.1 Unit (MockTransport)

`tests/adapter/kiwoom/test_stkinfo_basic_info.py`:

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 — 모든 필드 채워짐 | 200 + 45 필드 | `StockBasicInfoResponse` 정상 파싱 |
| 외부 벤더 데이터 빈값 | per/eps/roe/pbr/ev=빈 문자열 | normalized 의 해당 필드 None |
| 부호 포함 | crd_rt="+0.08" | `_to_decimal` → `Decimal("0.08")` |
| 부호 음수 | oyr_lwst="-91200" | `_to_int` → -91200 |
| zero-padded | listCount="00136000" | `_to_int` → 136000 |
| `250hgst` alias | 응답 `"250hgst": "150000"` | Pydantic alias 매핑 → `high_250d="150000"` |
| `_NX` suffix | exchange=NXT, stk_cd="005930_NX" | 호출 + 응답 stk_cd `_NX` 보존, normalized.stock_code base="005930", exchange=NXT |
| `_AL` suffix | exchange=SOR | 동일 처리 |
| 빈 stk_cd | response `stk_cd=""` | `KiwoomResponseValidationError` (min_length=1) |
| `return_code=1` | 비즈니스 에러 | `KiwoomBusinessError` |
| 401 | 자격증명 거부 | `KiwoomCredentialRejectedError` |
| stock_code "00593" | 호출 차단 | `ValueError` |
| `regDay`/`250hgst_pric_dt` 잘못된 형식 | "abc" | `_parse_yyyymmdd` → None |
| Pydantic extra 필드 | 신규 필드 응답에 등장 | `extra="ignore"` 통과 |

### 9.2 Integration (testcontainers)

`tests/application/test_fundamental_service.py`:

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| 첫 sync (3 종목) | stock 3건 활성, 응답 정상 | `success=3, failed=0`, fundamental row 3개 |
| 같은 날 두 번 sync (멱등성) | sync 후 즉시 재 sync | UNIQUE 제약 통과, row 3개 유지, `updated_at` 갱신 |
| 다음 날 sync | 다음 일자로 sync | row 6개 (날짜별 분리) |
| FK 미존재 종목 | stock 없는 stock_id 시도 | (UseCase 는 active stock 만 순회하므로 발생하지 않아야 함) |
| 한 종목 비즈니스 에러 | 3건 중 1건 return_code=1 | success=2, failed=1, errors 1건 |
| 한 종목 5xx | 3건 중 1건 502 | success=2, failed=1 |
| stock_name mismatch | 응답 stk_nm != stock.stock_name | warning 로그 + 적재는 정상 |
| KRX + NXT 분리 적재 (옵션) | KRX exchange + NXT exchange 두 번 sync | row 6개 (3종목 × 2거래소) |
| fundamental_hash 변경 감지 | 두 sync 의 PER 다름 | 두 row 의 fundamental_hash 다름 |
| fundamental_hash 동일 | 두 sync 의 PER/EPS/ROE/PBR/EV/BPS 동일 | hash 동일 |
| only_market_codes 필터 | KOSPI 만 sync 요청 | KOSDAQ active 종목 적재 안 됨 |
| 빈 응답 (벤더 데이터 0) | per/eps/.../bps 모두 빈값 + stk_nm 정상 | row 적재됨 (모두 NULL) |

### 9.3 E2E (요청 시 1회)

```python
@pytest.mark.requires_kiwoom_real
async def test_real_basic_info():
    creds = KiwoomCredentials(
        appkey=os.environ["KIWOOM_PROD_APPKEY"],
        secretkey=os.environ["KIWOOM_PROD_SECRETKEY"],
    )
    async with KiwoomAuthClient(base_url="https://api.kiwoom.com") as auth:
        token = await auth.issue_token(creds)
    try:
        kiwoom_client = KiwoomClient(
            base_url="https://api.kiwoom.com", token=token.token,
        )
        stkinfo = KiwoomStkInfoClient(kiwoom_client)

        # 삼성전자 KRX
        krx = await stkinfo.fetch_basic_info("005930", exchange=ExchangeType.KRX)
        assert krx.stk_cd == "005930"
        assert krx.return_code == 0
        assert krx.stk_nm == "삼성전자"
        # 거래일이면 cur_prc 채워져 있어야 함
        if is_trading_day(date.today()):
            assert krx.cur_prc != ""

        # 삼성전자 NXT (NXT 가능 종목 가정)
        nxt = await stkinfo.fetch_basic_info("005930", exchange=ExchangeType.NXT)
        assert nxt.stk_cd == "005930_NX" or nxt.stk_cd == "005930"  # 응답이 어떻게 오는지
        assert nxt.return_code == 0

        # 펀더멘털 비교 — 외부 벤더 데이터는 KRX/NXT 동일해야 함
        if krx.per and nxt.per:
            assert krx.per == nxt.per
        if krx.eps and nxt.eps:
            assert krx.eps == nxt.eps
    finally:
        async with KiwoomAuthClient(base_url="https://api.kiwoom.com") as auth:
            await auth.revoke_token(creds, token.token)
```

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `app/adapter/out/kiwoom/_records.py` 의 `StockBasicInfoResponse`, `NormalizedFundamental`, `_to_int`, `_to_decimal`, `normalize_basic_info`, `strip_kiwoom_suffix`, `build_stk_cd`
- [ ] `app/application/constants.py` 의 `ExchangeType` StrEnum (KRX/NXT/SOR)
- [ ] `app/adapter/out/kiwoom/stkinfo.py` 의 `KiwoomStkInfoClient.fetch_basic_info`
- [ ] `app/adapter/out/persistence/models/stock_fundamental.py` — `StockFundamental` ORM
- [ ] `app/adapter/out/persistence/repositories/stock_fundamental.py` — `StockFundamentalRepository.upsert_one` / `find_latest`
- [ ] `app/application/service/stock_fundamental_service.py` — `SyncStockFundamentalUseCase`
- [ ] `app/adapter/web/routers/fundamentals.py` — `POST /sync` + `GET /{code}/latest`
- [ ] `app/batch/daily_fundamental_job.py` — APScheduler 등록 (KST mon-fri 17:45)
- [ ] `migrations/versions/002_stock_fundamental_and_sector.py` — `stock_fundamental` 테이블 (sector 와 동일 마이그레이션 파일)

### 10.2 테스트

- [ ] Unit 14 시나리오 (§9.1) PASS
- [ ] Integration 12 시나리오 (§9.2) PASS
- [ ] coverage `KiwoomStkInfoClient.fetch_basic_info`, `SyncStockFundamentalUseCase`, `StockFundamentalRepository`, `normalize_basic_info` ≥ 80%

### 10.3 운영 검증

- [ ] 삼성전자 KRX 호출 → 45 필드 채워짐 (특히 PER/EPS/ROE/BPS)
- [ ] 코스닥 종목 호출 → KOSPI 와 응답 스키마 동일한지 확인
- [ ] ETF 호출(`069500`) — 펀더멘털 필드(per/eps/roe) 가 모두 빈값 추정 — 정상 동작 확인
- [ ] NXT 호출(`005930_NX`) — 응답 stk_cd 가 `005930_NX` 인지 / 응답에서 `_NX` suffix 가 stripped 되어 오는지 확인
- [ ] 단위 검증: market_cap (`mac`) 단위가 억원인지 백만원인지 (Excel 예시 "24352" 가 24,352 억원이면 삼성전자 = 2.4 조원? 너무 적음 → 단위 재확인 필요)
- [ ] 단위 검증: capital_won (`cap`) Excel 예시 "1311" 이 백만원이면 = 13.1 억 (삼성전자 자본금 8,975 억) → **운영 단위 명확화 필수**
- [ ] 부호 의미: `oyr_hgst="+181400"`, `oyr_lwst="-91200"` 의 부호가 단순 표기인지 전일 대비 인지
- [ ] PER/ROE 가 며칠 동일 값으로 반복되는지 (외부 벤더 주 1회 갱신 확인)
- [ ] active 3000 종목 sync 실측 시간 (예상 5~12분)
- [ ] sync 1회 RPS 폭주 없는지 (Semaphore=4, 250ms interval)

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10001 stock fundamental daily snapshot (45 fields)`
- [ ] `master.md` § 12 결정 기록에:
  - market_cap / capital_won / listed_shares 단위 확정
  - oyr_hgst/oyr_lwst 부호 의미 확정
  - PER/ROE 갱신 주기 확정 (벤더 → 키움 → 우리)
  - active 3000 종목 sync 실측 소요 시간

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | KRX vs NXT vs SOR 호출 정책 | (a) KRX only — 펀더멘털 충분 (권장, § 4.3) / (b) KRX + NXT — row 2개 / (c) 동적 — 시그널이 NXT 시세 의존시 NXT 도 호출 | Phase C 후 결정 |
| 2 | 단위 (mac, cap, listed_shares 등) | DoD § 10.3 운영 검증 후 컬럼 주석에 명시 | 본 endpoint 코드화 시점 |
| 3 | `oyr_hgst`/`oyr_lwst` 부호 의미 | 단순 표기 / 전일 대비 부호 | 운영 검증 후 |
| 4 | fundamental_hash 활용 | (a) 컬럼만 두고 미사용 (현재) / (b) hash 변경 시 별도 trigger | Phase F 시그널 단계 |
| 5 | 일 1회 cron 시간 | (a) 17:45 KST (현재) / (b) 18:00 (ka10099 18:00 cron 후) | Phase B 후반 |
| 6 | 백필 가능 여부 (과거 일자) | 키움이 과거 펀더멘털 응답하는지 | 운영 검증 후 |
| 7 | partial 실패 alert 기준 | 1% / 5% / 10% (현재 10%) | 운영 1주 모니터 후 |

### 11.2 알려진 위험

- **단위 불명확** (DoD § 10.3): Excel 에 명시 단위 없음. mac="24352" 가 억원이면 삼성전자 = 2.4 조원 (시총 약 400조원과 100배 차이). **단위가 백만원이면** = 24,352 백만원 = 243억 → 너무 적음. 운영 호출 후 cur_prc × listed_shares 와 비교해 단위 도출 필수
- **부호 포함 string** (`crd_rt="+0.08"`, `oyr_lwst="-91200"`): `_to_int` 가 부호 자동 처리 (`int("+181400")` 동작). 단 Decimal 도 동일 — 운영에서 부호 의미 파악 필요
- **외부 벤더 PER/ROE 의존성**: Excel R41/R43 명시 — 주 1회 또는 실적발표 시즌만 갱신. 백테스팅에서 PER 시그널을 "최근 3일 PER" 으로 잡으면 항상 같은 값. 시그널은 "최근 분기 발표" 단위가 적합
- **NXT 응답이 KRX 와 정말 동일한지**: 외부 벤더 데이터(C 카테고리)는 동일해야 하지만, 일중 시세(E)는 KRX/NXT 분리 가격일 가능성. 운영 검증 필수
- **응답 stk_cd 가 요청 그대로 메아리치는지**: 요청 `005930_NX` → 응답 `005930` 으로 stripped 되어 올 수도. parsing 시 base code 추출 안전망 필수 (`strip_kiwoom_suffix`)
- **45 필드 중 일부만 채워지는 종목**: ETF, ETN, ELW, 신주인수권 등은 펀더멘털 필드(C) 가 모두 빈값일 것. 컬럼 NULL 허용 필수
- **3000 종목 sync 의 실패율**: tenacity 재시도 후에도 일부 종목은 실패 가능 (장 마감 직후 키움 점검 / 일시 timeout). errors 리스트 누적 → 다음 sync 에서 retry 큐 운영 검토
- **`fundamental_hash` 가 string 비교에 의존**: PER 이 `"15.20"` vs `"15.2"` 면 hash 다름 — 정규화 필요할 수도. 실측 후 결정
- **시간대 (KST)**: 응답에 timestamp 없음. 호출 시점 KST 가 asof_date 가정. 자정 직전 호출이면 실제 시세는 전일이고 fetched_at 은 다음날 — 백테스팅 시점 매핑 주의

### 11.3 ka10099/ka10100/ka10001 비교

| 항목 | ka10099 | ka10100 | ka10001 |
|------|---------|---------|---------|
| 호출 단위 | 시장 (mrkt_tp) | 종목 (단건) | 종목 (단건) |
| stk_cd Length | — | 6 | 20 (`_NX`/`_AL` 허용) |
| 응답 필드 수 | 14 (per row) | 14 + return_* | 45 + return_* |
| 응답 구조 | list[] | flat object | flat object |
| 영속화 테이블 | stock | stock | stock_fundamental |
| 호출 빈도 | 일 1회 (시장×5) | on-demand | 일 1회 (종목×3000) |
| Phase B 코드 책임 | SyncStockMasterUseCase | LookupStockUseCase | SyncStockFundamentalUseCase |
| RPS 부담 | 5 시장 × 페이지 ~ 50 호출 | 보통 0~5 호출/시간 | 일 1회 3000 호출 (5~12분) |

→ Phase B 가 끝나면 stock 마스터 + 일별 펀더멘털이 모두 적재되고, Phase C 의 시계열 수집이 종목 큐(`SELECT FROM stock WHERE is_active=true`) + NXT 큐(`+ AND nxt_enable=true`) 로 즉시 시작 가능.

### 11.4 향후 확장

- **분기/연간 재무 별도 테이블**: ka10001 의 sale_amt/bus_pro/cup_nga 는 누적치인지 분기치인지 운영 검증. 별도 `stock_financial_quarterly` 테이블이 필요할 수도
- **`dstr_stk` (유통주식) 시계열**: 유통주식 변동(전환사채 행사 / 자기주식 매입) 추적이 시그널에 유용. 본 테이블의 일별 row 가 자연스러운 시계열
- **외부 벤더 데이터 vs 키움 자체 데이터 분리**: PER/ROE 컬럼에 source 표기 (`vendor_per` / `kiwoom_per`) 가 향후 정확도 분석에 유용
- **`stock_intraday_snapshot` 분리**: E 카테고리(일중 시세 14필드) 를 별도 테이블로 분리해 stock_fundamental 은 펀더멘털만. 단 같은 호출의 응답이라 분리 ROI 약함

---

_Phase B 의 세 번째 endpoint. 종목 메타(stock) + 일별 펀더멘털(stock_fundamental) 의 짝꿍. PER/EPS/ROE 외부 벤더 갱신 주기와 단위 모호성이 운영 시 가장 큰 검증 포인트. Phase B 완료 후 stock + stock_fundamental + sector 가 모두 채워져 있어야 Phase C 의 일봉 수집이 즉시 진입 가능._
