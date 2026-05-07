# endpoint-18-ka10027.md — 전일대비등락률상위요청 (Phase F reference)

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `ka10027` |
| API 명 | 전일대비등락률상위요청 |
| 분류 | Tier 6 (순위 — 시나리오 검증) |
| Phase | **F** |
| 우선순위 | **P2** |
| Method | `POST` |
| URL | `/api/dostk/rkinfo` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX 만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| 의존 endpoint | `au10001`, `ka10099` (stock 마스터 — FK 매핑) |
| 후속 endpoint | `ka10030`(거래량 상위), `ka10031`(전일 거래량), `ka10032`(거래대금), `ka10023`(거래량 급증) — 동일 URL `/api/dostk/rkinfo` 5 endpoint 공유 |

---

## 1. 목적

**시점 단위 종목 순위 스냅샷** 을 적재한다. ka10081 (일봉) 가 종목·일자 시계열이라면, 본 endpoint 는 **순위·시점** — 같은 일자 안에서 N분 단위 / 종가 후 / 시점별 순위 변화를 추적.

1. **시그널 검증** — 백테스팅 시그널이 실제 등락률 상위에 등장한 종목과 일치하는지
2. **시장 단위 흐름** — 코스피 / 코스닥 별 등락률 분포의 변화
3. **NXT 가격 반영** — KRX vs NXT 의 등락률 순위 차이로 거래소 간 가격 발견 패턴 추적
4. **시간대 별 순위 변화** — 장 시작 / 장중 / 종가 후 순위 비교 (운영 검증 후 시점 정책)

**왜 P2**:
- 백테스팅 1차에는 종목 OHLCV / 분봉 / 공매도 / 대차 만으로 시그널 가능
- 그러나 시그널 정합성 검증 / 시장 흐름 모니터링 / 알람 시스템에는 본 endpoint 들이 핵심
- 5 endpoint (ka10027/30/31/32/23) 가 동일 URL + 다른 응답 schema 라 **통합 저장** 패턴이 본 계획서의 핵심

**Phase F reference**: ka10030/31/32/23 은 본 계획서의 패턴 복제 (응답 list 키 + 응답 필드만 다름). 5 endpoint 의 공통 인프라 (`KiwoomRkInfoClient` / `ranking_snapshot` 테이블 / `IngestRankingUseCase`) 를 본 계획서가 정의.

---

## 2. Request 명세

### 2.1 Header

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `api-id` | TR 명 | String | Y | 10 | `"ka10027"` 고정 |
| `authorization` | 접근토큰 | String | Y | 1000 | `Bearer <token>` |
| `cont-yn` | 연속조회 여부 | String | N | 1 | 응답 헤더 그대로 전달 |
| `next-key` | 연속조회 키 | String | N | 50 | 응답 헤더 그대로 전달 |

### 2.2 Body (9 필드 — Phase F 중 가장 복잡)

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `mrkt_tp` | 시장구분 | String | Y | 3 | `000`:전체 / `001`:코스피 / `101`:코스닥 ★ ka10101 의 `mrkt_tp` 와 다른 의미 |
| `sort_tp` | 정렬구분 | String | Y | 1 | `1`:상승률 / `2`:상승폭 / `3`:하락률 / `4`:하락폭 / `5`:보합 |
| `trde_qty_cnd` | 거래량조건 | String | Y | 5 | `0000`:전체 / `0010`:만주 / `0050`:5만주 / `0100`:10만주 / `0150`/`0200`/`0300`/`0500`/`1000` |
| `stk_cnd` | 종목조건 | String | Y | 2 | `0`:전체 / `1`:관리제외 / `4`:우선주+관리 / `3`:우선주제외 / 외 (Excel 명세 13종) |
| `crd_cnd` | 신용조건 | String | Y | 1 | `0`:전체 / `1~4`:신용융자 A~D / `7`:E / `9`:전체 |
| `updown_incls` | 상하한포함 | String | Y | 2 | `0`:불포함 / `1`:포함 |
| `pric_cnd` | 가격조건 | String | Y | 2 | `0`:전체 / `1`:1천원미만 / `2`:1천~2천 / `3`/`4`/`5`/`8`/`10` |
| `trde_prica_cnd` | 거래대금조건 | String | Y | 4 | `0`:전체 / `3`:3천만 / `5`:5천만 / `10`/`30`/`50`/`100`/`300`/`500`/`1000`/`3000`/`5000` |
| `stex_tp` | 거래소구분 | String | Y | 1 | `1`:KRX / `2`:NXT / `3`:통합 ★ |

> **`mrkt_tp` 의미 충돌 (4번째 정의)**: ka10099 는 `0/10/30/50/60/70/80/90/...`, ka10101 은 `0/1/2/4/7`, ka10027~10032/10023 (본 카테고리) 는 `000/001/101`. 5 endpoint (ka10027/30/31/32/23) 의 `mrkt_tp` 는 같은 의미.
>
> **`stex_tp` 의미**: 1=KRX, 2=NXT, 3=통합. 5 ranking endpoint 모두 같은 의미. master.md § 11.3 의 `RankingExchangeType` enum.

### 2.3 Request 예시 (Excel 원문)

```json
POST https://api.kiwoom.com/api/dostk/rkinfo
Content-Type: application/json;charset=UTF-8
api-id: ka10027
authorization: Bearer Egicyx...

{
    "mrkt_tp": "000",
    "sort_tp": "1",
    "trde_qty_cnd": "0000",
    "stk_cnd": "0",
    "crd_cnd": "0",
    "updown_incls": "1",
    "pric_cnd": "0",
    "trde_prica_cnd": "0",
    "stex_tp": "3"
}
```

### 2.4 Pydantic 모델

```python
# app/adapter/out/kiwoom/rkinfo.py
class RankingMarketType(StrEnum):
    """ka10027~10032/10023 의 mrkt_tp. 다른 카테고리와 분리."""
    ALL = "000"
    KOSPI = "001"
    KOSDAQ = "101"


class RankingExchangeType(StrEnum):
    """5 ranking endpoint 의 stex_tp."""
    KRX = "1"
    NXT = "2"
    UNIFIED = "3"


class FluRtSortType(StrEnum):
    """ka10027 의 sort_tp."""
    UP_RATE = "1"          # 상승률
    UP_AMOUNT = "2"        # 상승폭
    DOWN_RATE = "3"        # 하락률
    DOWN_AMOUNT = "4"      # 하락폭
    UNCHANGED = "5"        # 보합


class FluRtUpperRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    mrkt_tp: RankingMarketType
    sort_tp: FluRtSortType
    trde_qty_cnd: Literal["0000", "0010", "0050", "0100",
                          "0150", "0200", "0300", "0500", "1000"]
    stk_cnd: str            # 13종 — Pydantic Literal 로 좁힐 수 있지만 운영 검증 후 결정
    crd_cnd: Literal["0", "1", "2", "3", "4", "7", "9"]
    updown_incls: Literal["0", "1"]
    pric_cnd: str           # 8종
    trde_prica_cnd: str     # 12종
    stex_tp: RankingExchangeType
```

---

## 3. Response 명세

### 3.1 Header

| Element | Type | Description |
|---------|------|-------------|
| `api-id` | String | `"ka10027"` 에코 |
| `cont-yn` | String | `Y` 면 다음 페이지 |
| `next-key` | String | 다음 호출 헤더에 세팅 |

### 3.2 Body (12 필드)

| Element | 한글명 | Type | Length | 영속화 | 메모 |
|---------|-------|------|--------|--------|------|
| `pred_pre_flu_rt_upper[]` | 등락률상위 list | LIST | — | (전체 row 적재) | **list key 명** — endpoint 별 다름 |
| `stk_cls` | 종목분류 | String | 20 | `payload.stk_cls` (JSONB) | 운영 검증 — 코드 의미 |
| `stk_cd` | 종목코드 | String | 20 | `stock_id` (FK lookup) | NXT `_NX` suffix 보존 여부 검증 |
| `stk_nm` | 종목명 | String | 40 | `payload.stk_nm` | 디버그용 |
| `cur_prc` | 현재가 | String | 20 | `payload.cur_prc` (BIGINT) | 부호 포함 (`+74800`) |
| `pred_pre_sig` | 전일대비기호 | String | 20 | `payload.pred_pre_sig` | 1~5 |
| `pred_pre` | 전일대비 | String | 20 | `payload.pred_pre` (BIGINT) | 부호 포함 |
| `flu_rt` | 등락률 | String | 20 | **`primary_metric` (NUMERIC(8,4))** | 부호 포함 (`+29.86`). 본 endpoint 의 정렬 기준 |
| `sel_req` | 매도잔량 | String | 20 | `payload.sel_req` (BIGINT) | |
| `buy_req` | 매수잔량 | String | 20 | `payload.buy_req` (BIGINT) | |
| `now_trde_qty` | 현재거래량 | String | 20 | `payload.now_trde_qty` (BIGINT) | |
| `cntr_str` | 체결강도 | String | 20 | `payload.cntr_str` (NUMERIC(8,2)) | 매수/매도 우세 지표 |
| `cnt` | 횟수 | String | 20 | `payload.cnt` (INTEGER) | 운영 검증 — 의미 |
| `return_code` | 처리코드 | Integer | — | (raw_response only) | 0 정상 |
| `return_msg` | 처리메시지 | String | — | (raw_response only) | |

### 3.3 Response 예시 (Excel 원문, 일부)

```json
{
    "pred_pre_flu_rt_upper": [
        {
            "stk_cls": "0",
            "stk_cd": "005930",
            "stk_nm": "삼성전자",
            "cur_prc": "+74800",
            "pred_pre_sig": "1",
            "pred_pre": "+17200",
            "flu_rt": "+29.86",
            "sel_req": "207",
            "buy_req": "3820638",
            "now_trde_qty": "446203",
            "cntr_str": "346.54",
            "cnt": "4"
        },
        {
            "stk_cls": "0",
            "stk_cd": "005930",
            "stk_nm": "삼성전자",
            "cur_prc": "+12000",
            "pred_pre_sig": "2",
            "pred_pre": "+2380",
            "flu_rt": "+24.74",
            "sel_req": "54",
            "buy_req": "0",
            "now_trde_qty": "6",
            "cntr_str": "500.00",
            "cnt": "1"
        }
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다"
}
```

> **응답 정렬은 sort_tp 순**: `sort_tp=1` (상승률) 호출 시 flu_rt 내림차순. 백테스팅 엔진 / 시그널 모니터링 시 응답 순서 = 순위.

### 3.4 Pydantic + 정규화

```python
# app/adapter/out/kiwoom/_records.py
class FluRtUpperRow(BaseModel):
    """ka10027 응답 row."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    stk_cls: str = ""
    stk_cd: str = ""
    stk_nm: str = ""
    cur_prc: str = ""
    pred_pre_sig: str = ""
    pred_pre: str = ""
    flu_rt: str = ""
    sel_req: str = ""
    buy_req: str = ""
    now_trde_qty: str = ""
    cntr_str: str = ""
    cnt: str = ""

    def to_payload(self) -> dict[str, Any]:
        """JSONB payload 로 직렬화 — 가변 컬럼 흡수.

        다음 endpoint (ka10030 등) 가 다른 필드를 응답해도 같은 컬럼 (payload) 에 들어감.
        """
        return {
            "stk_cls": self.stk_cls,
            "stk_nm": self.stk_nm,
            "cur_prc": _to_int(self.cur_prc),
            "pred_pre_sig": self.pred_pre_sig or None,
            "pred_pre": _to_int(self.pred_pre),
            "sel_req": _to_int(self.sel_req),
            "buy_req": _to_int(self.buy_req),
            "now_trde_qty": _to_int(self.now_trde_qty),
            "cntr_str": _to_decimal_str(self.cntr_str),       # JSONB 는 string 권장
            "cnt": _to_int(self.cnt),
        }


class FluRtUpperResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    pred_pre_flu_rt_upper: list[FluRtUpperRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: str = ""


class RankingType(StrEnum):
    """5 ranking endpoint 의 통합 식별자."""
    FLU_RT = "FLU_RT"                  # ka10027
    TODAY_VOLUME = "TODAY_VOLUME"       # ka10030
    PRED_VOLUME = "PRED_VOLUME"         # ka10031
    TRDE_PRICA = "TRDE_PRICA"           # ka10032
    VOLUME_SDNIN = "VOLUME_SDNIN"       # ka10023


@dataclass(frozen=True, slots=True)
class NormalizedRanking:
    snapshot_date: date
    snapshot_time: time
    ranking_type: RankingType            # FLU_RT / TODAY_VOLUME / ...
    sort_tp: str                         # ka10027 의 sort_tp 값 — 어느 정렬 기준인가
    market_type: str                     # mrkt_tp 값 (000/001/101)
    exchange_type: str                   # stex_tp 값 (1/2/3)
    rank: int                            # 응답 list 순서 (1-based)
    stock_id: int | None                 # FK (lookup 실패 시 NULL + payload 에 stk_cd 보관)
    primary_metric: Decimal | None       # 정렬 기준 값 (flu_rt, trde_qty, ...)
    payload: dict[str, Any]              # 그 row 의 raw 필드 JSONB
    request_filters: dict[str, Any]      # mrkt_tp/sort_tp/... 8 필터 보관 (재현)
```

---

## 4. NXT 처리

| 항목 | 적용 여부 |
|------|-----------|
| `stk_cd` 에 `_NX` suffix | (응답 row 의 stk_cd) — 응답에 NXT 코드 보존 여부 운영 검증 |
| `nxt_enable` 게이팅 | N (호출 시 stex_tp=2 로 NXT 분리) |
| `mrkt_tp` 별 분리 | **Y** (3 시장 × 3 거래소 = 9 호출 / sort_tp 분기 추가) |
| KRX 운영 / 모의 차이 | mockapi 는 KRX 전용 |

### 4.1 호출 매트릭스

본 endpoint 는 **시점 + 시장 + 거래소 + 정렬** 의 4차원 — 한 시점 sync 시 호출 수:

| 차원 | 값 수 | 비고 |
|------|-------|------|
| mrkt_tp | 3 (000/001/101) | 권장 = 001/101 만 (000 은 합산이라 중복 가능) |
| stex_tp | 3 (1/2/3) | 운영 default = 3 (통합) |
| sort_tp | 5 | 권장 = 1/3 만 (상승률 + 하락률) |
| 호출 수 | 2 × 1 × 2 = 4 (운영) | 5 ranking endpoint 합치면 ~20 호출 / 시점 |

→ **운영 default 권장**: `mrkt_tp ∈ {001, 101}` × `stex_tp = 3` × `sort_tp ∈ {1, 3}` = 4 호출 / 시점.

### 4.2 NXT 별도 호출

`stex_tp=2` 로 NXT 만 응답 — KRX 와 다른 가격 발견 패턴 추적. 단, NXT 거래량 작아 응답 row 수 KRX 보다 적음.

---

## 5. DB 스키마

### 5.1 신규 테이블 — Migration 007 (`007_rankings.py`)

> Phase F 5 endpoint 통합 테이블. JSONB payload 로 가변 스키마 흡수.

```sql
CREATE TABLE kiwoom.ranking_snapshot (
    id                  BIGSERIAL PRIMARY KEY,
    snapshot_date       DATE NOT NULL,
    snapshot_time       TIME NOT NULL,                       -- HH:MM:SS KST (호출 시각)
    ranking_type        VARCHAR(16) NOT NULL,                -- "FLU_RT" / "TODAY_VOLUME" / ...
    sort_tp             VARCHAR(2) NOT NULL,                 -- "1" / "2" / ... endpoint 별 의미 다름
    market_type         VARCHAR(3) NOT NULL,                 -- "000" / "001" / "101"
    exchange_type       VARCHAR(1) NOT NULL,                 -- "1" / "2" / "3"
    rank                INTEGER NOT NULL,                    -- 1-based (응답 순서)
    stock_id            BIGINT REFERENCES kiwoom.stock(id) ON DELETE SET NULL,
                                                              -- lookup 실패 시 NULL (payload 에 stk_cd 보관)
    stock_code_raw      VARCHAR(20) NOT NULL,                -- 응답 stk_cd raw (NXT _NX 보존)
    primary_metric      NUMERIC(20, 4),                       -- sort_tp 의 metric 값
    payload             JSONB NOT NULL,                      -- 가변 row 필드
    request_filters     JSONB NOT NULL,                      -- 호출 시 필터 (재현)
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_ranking_snapshot UNIQUE (
        snapshot_date, snapshot_time, ranking_type, sort_tp,
        market_type, exchange_type, rank
    )
);

CREATE INDEX idx_ranking_date_type
    ON kiwoom.ranking_snapshot(snapshot_date, ranking_type, market_type, exchange_type);
CREATE INDEX idx_ranking_stock
    ON kiwoom.ranking_snapshot(stock_id) WHERE stock_id IS NOT NULL;
CREATE INDEX idx_ranking_payload_gin
    ON kiwoom.ranking_snapshot USING GIN (payload);
```

> **JSONB GIN 인덱스**: `payload->>'cur_prc'` 같은 ad-hoc 쿼리 가속.
>
> **UNIQUE 키 6개**: 같은 시점·같은 endpoint·같은 sort_tp·같은 시장·같은 거래소·같은 rank 는 1 row.
>
> **5 endpoint 통합**: ka10030/31/32/23 도 같은 테이블, `ranking_type` 컬럼으로 분기. 새 ranking endpoint 추가 시 enum 만 확장.

### 5.2 ORM 모델

```python
# app/adapter/out/persistence/models/ranking_snapshot.py
class RankingSnapshot(Base):
    __tablename__ = "ranking_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_date", "snapshot_time", "ranking_type", "sort_tp",
            "market_type", "exchange_type", "rank",
            name="uq_ranking_snapshot",
        ),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    snapshot_time: Mapped[time] = mapped_column(Time, nullable=False)
    ranking_type: Mapped[str] = mapped_column(String(16), nullable=False)
    sort_tp: Mapped[str] = mapped_column(String(2), nullable=False)
    market_type: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange_type: Mapped[str] = mapped_column(String(1), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("kiwoom.stock.id", ondelete="SET NULL"), nullable=True
    )
    stock_code_raw: Mapped[str] = mapped_column(String(20), nullable=False)
    primary_metric: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    request_filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

### 5.3 row 수 추정

| 항목 | 값 |
|------|----|
| 시점 / 일 (운영) | 1 (종가 후 19:00) |
| 1 시점 호출 수 (5 endpoint × 4 호출 권장) | ~20 |
| 호출당 응답 row (운영 기본 100~200) | ~150 |
| 1일 row | 20 × 150 = 3,000 |
| 1년 (252 거래일) | ~756,000 |
| 3년 백필 | ~2.27M |

→ 단일 테이블, 파티션 불필요 (5년+ 시점 검토). JSONB 가 STRING 컬럼보다 무거우니 disk 사용량 별도 모니터.

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter — `KiwoomRkInfoClient` (5 endpoint 공유)

```python
# app/adapter/out/kiwoom/rkinfo.py
class KiwoomRkInfoClient:
    """`/api/dostk/rkinfo` 카테고리 — ka10027/30/31/32/23 공유."""

    PATH = "/api/dostk/rkinfo"

    def __init__(self, kiwoom_client: KiwoomClient) -> None:
        self._client = kiwoom_client

    async def fetch_flu_rt_upper(
        self,
        *,
        market_type: RankingMarketType = RankingMarketType.ALL,
        sort_tp: FluRtSortType = FluRtSortType.UP_RATE,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        trde_qty_cnd: str = "0000",
        stk_cnd: str = "0",
        crd_cnd: str = "0",
        updown_incls: str = "1",
        pric_cnd: str = "0",
        trde_prica_cnd: str = "0",
        max_pages: int = 5,
    ) -> tuple[list[FluRtUpperRow], dict[str, Any]]:
        """ka10027 — 등락률 상위. 응답 + 사용된 필터 반환."""
        body = {
            "mrkt_tp": market_type.value,
            "sort_tp": sort_tp.value,
            "trde_qty_cnd": trde_qty_cnd,
            "stk_cnd": stk_cnd,
            "crd_cnd": crd_cnd,
            "updown_incls": updown_incls,
            "pric_cnd": pric_cnd,
            "trde_prica_cnd": trde_prica_cnd,
            "stex_tp": exchange_type.value,
        }

        all_rows: list[FluRtUpperRow] = []
        async for page in self._client.call_paginated(
            api_id="ka10027",
            endpoint=self.PATH,
            body=body,
            max_pages=max_pages,
        ):
            parsed = FluRtUpperResponse.model_validate(page.body)
            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id="ka10027",
                    return_code=parsed.return_code,
                    return_msg=parsed.return_msg,
                )
            all_rows.extend(parsed.pred_pre_flu_rt_upper)

        return all_rows, body

    # fetch_today_volume_upper / fetch_pred_volume_upper /
    # fetch_trde_prica_upper / fetch_volume_sdnin 은 endpoint-19~22 참조
```

### 6.2 Repository — `RankingSnapshotRepository` (5 endpoint 공유)

```python
# app/adapter/out/persistence/repositories/ranking_snapshot.py
class RankingSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, rows: Sequence[NormalizedRanking]) -> int:
        if not rows:
            return 0

        values = [
            {
                "snapshot_date": r.snapshot_date,
                "snapshot_time": r.snapshot_time,
                "ranking_type": r.ranking_type.value,
                "sort_tp": r.sort_tp,
                "market_type": r.market_type,
                "exchange_type": r.exchange_type,
                "rank": r.rank,
                "stock_id": r.stock_id,
                "stock_code_raw": next(
                    (k for k, v in r.payload.items() if k == "stk_cd_raw"),
                    "",
                ) or "",
                "primary_metric": r.primary_metric,
                "payload": r.payload,
                "request_filters": r.request_filters,
            }
            for r in rows
        ]

        stmt = pg_insert(RankingSnapshot).values(values)
        update_set = {
            "stock_id": stmt.excluded.stock_id,
            "stock_code_raw": stmt.excluded.stock_code_raw,
            "primary_metric": stmt.excluded.primary_metric,
            "payload": stmt.excluded.payload,
            "request_filters": stmt.excluded.request_filters,
            "fetched_at": func.now(),
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                "snapshot_date", "snapshot_time", "ranking_type", "sort_tp",
                "market_type", "exchange_type", "rank",
            ],
            set_=update_set,
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return rowcount_of(result)

    async def get_at_snapshot(
        self,
        snapshot_date: date,
        snapshot_time: time,
        *,
        ranking_type: RankingType,
        sort_tp: str,
        market_type: str,
        exchange_type: str,
        limit: int = 50,
    ) -> list[RankingSnapshot]:
        stmt = (
            select(RankingSnapshot)
            .where(
                RankingSnapshot.snapshot_date == snapshot_date,
                RankingSnapshot.snapshot_time == snapshot_time,
                RankingSnapshot.ranking_type == ranking_type.value,
                RankingSnapshot.sort_tp == sort_tp,
                RankingSnapshot.market_type == market_type,
                RankingSnapshot.exchange_type == exchange_type,
            )
            .order_by(RankingSnapshot.rank)
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars())
```

### 6.3 UseCase — `IngestFluRtUpperUseCase`

```python
# app/application/service/ranking_service.py
class IngestFluRtUpperUseCase:
    """ka10027 등락률 상위 적재.

    한 호출 = 하나의 (snapshot_date, snapshot_time, sort_tp, market_type, exchange_type) 묶음.
    응답 row 들을 rank 1, 2, 3, ... 으로 적재.
    """

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
        sort_tp: FluRtSortType = FluRtSortType.UP_RATE,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        **filters: Any,
    ) -> RankingIngestOutcome:
        try:
            raw_rows, used_filters = await self._client.fetch_flu_rt_upper(
                market_type=market_type,
                sort_tp=sort_tp,
                exchange_type=exchange_type,
                **filters,
            )
        except KiwoomBusinessError as exc:
            return RankingIngestOutcome(
                ranking_type=RankingType.FLU_RT, snapshot_at=snapshot_at,
                upserted=0, error=f"business: {exc.return_code}",
            )

        # stk_cd → stock_id 매핑 (lookup miss 는 NULL)
        stock_codes_raw = [r.stk_cd for r in raw_rows]
        stock_codes_clean = [strip_kiwoom_suffix(c) for c in stock_codes_raw]
        stocks_by_code = await self._stock_repo.find_by_codes(stock_codes_clean)
        # → dict[str, Stock]

        normalized = []
        for rank, (raw_row, code_clean) in enumerate(
            zip(raw_rows, stock_codes_clean), start=1,
        ):
            stock = stocks_by_code.get(code_clean)
            payload = raw_row.to_payload()
            payload["stk_cd_raw"] = raw_row.stk_cd        # NXT _NX 보존

            normalized.append(NormalizedRanking(
                snapshot_date=snapshot_at.date(),
                snapshot_time=snapshot_at.time().replace(microsecond=0),
                ranking_type=RankingType.FLU_RT,
                sort_tp=sort_tp.value,
                market_type=market_type.value,
                exchange_type=exchange_type.value,
                rank=rank,
                stock_id=stock.id if stock else None,
                primary_metric=_to_decimal(raw_row.flu_rt),
                payload=payload,
                request_filters=used_filters,
            ))

        upserted = await self._repo.upsert_many(normalized)

        return RankingIngestOutcome(
            ranking_type=RankingType.FLU_RT,
            snapshot_at=snapshot_at,
            sort_tp=sort_tp.value,
            market_type=market_type.value,
            exchange_type=exchange_type.value,
            fetched=len(raw_rows), upserted=upserted,
        )


@dataclass(frozen=True, slots=True)
class RankingIngestOutcome:
    ranking_type: RankingType
    snapshot_at: datetime
    sort_tp: str = ""
    market_type: str = ""
    exchange_type: str = ""
    fetched: int = 0
    upserted: int = 0
    error: str | None = None
```

### 6.4 Bulk — `IngestFluRtUpperBulkUseCase`

```python
class IngestFluRtUpperBulkUseCase:
    """일 1회 sync — 4 호출 (2 mrkt_tp × 2 sort_tp).

    동시성: RPS 4 + 250ms = 4 × 0.25 = 1초 (이론).
    실측 1~5초.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        single_use_case: IngestFluRtUpperUseCase,
    ) -> None:
        self._session = session
        self._single = single_use_case

    async def execute(
        self,
        snapshot_at: datetime,
    ) -> list[RankingIngestOutcome]:
        outcomes: list[RankingIngestOutcome] = []
        for market_type in [RankingMarketType.KOSPI, RankingMarketType.KOSDAQ]:
            for sort_tp in [FluRtSortType.UP_RATE, FluRtSortType.DOWN_RATE]:
                try:
                    o = await self._single.execute(
                        snapshot_at=snapshot_at,
                        market_type=market_type,
                        sort_tp=sort_tp,
                        exchange_type=RankingExchangeType.UNIFIED,
                    )
                    outcomes.append(o)
                except Exception as exc:
                    logger.warning(
                        "fluRt upper 실패 market=%s sort=%s: %s",
                        market_type.value, sort_tp.value, exc,
                    )
                    outcomes.append(RankingIngestOutcome(
                        ranking_type=RankingType.FLU_RT,
                        snapshot_at=snapshot_at,
                        market_type=market_type.value,
                        sort_tp=sort_tp.value,
                        error=f"{type(exc).__name__}: {exc}",
                    ))
        await self._session.commit()
        return outcomes
```

---

## 7. 배치 / 트리거

| 트리거 | 빈도 | 비고 |
|--------|------|------|
| **수동** | on-demand | `POST /api/kiwoom/rankings/flu-rt?market_type=001&sort_tp=1&exchange_type=3` (admin) |
| **수동 bulk** | on-demand | `POST /api/kiwoom/rankings/flu-rt/sync` (admin) — 4 호출 |
| **일 1회 cron** | KST 19:30 평일 | 종가 후 1시간 — 일 마감 등락률 스냅샷 |
| **백필** | (제한적) | 키움이 과거 시점 스냅샷 응답 안 할 가능성 — 운영 검증 |

### 7.1 라우터

```python
# app/adapter/web/routers/rankings.py
router = APIRouter(prefix="/api/kiwoom/rankings", tags=["kiwoom-rankings"])


@router.post(
    "/flu-rt",
    response_model=RankingIngestOutcomeOut,
    dependencies=[Depends(require_admin_key)],
)
async def ingest_flu_rt(
    snapshot_at: datetime = Query(default_factory=lambda: datetime.now(KST)),
    market_type: Literal["000", "001", "101"] = Query(default="000"),
    sort_tp: Literal["1", "2", "3", "4", "5"] = Query(default="1"),
    exchange_type: Literal["1", "2", "3"] = Query(default="3"),
    use_case: IngestFluRtUpperUseCase = Depends(get_ingest_flu_rt_use_case),
) -> RankingIngestOutcomeOut:
    outcome = await use_case.execute(
        snapshot_at=snapshot_at,
        market_type=RankingMarketType(market_type),
        sort_tp=FluRtSortType(sort_tp),
        exchange_type=RankingExchangeType(exchange_type),
    )
    return RankingIngestOutcomeOut.model_validate(asdict(outcome))


@router.post(
    "/flu-rt/sync",
    response_model=list[RankingIngestOutcomeOut],
    dependencies=[Depends(require_admin_key)],
)
async def sync_flu_rt_bulk(
    snapshot_at: datetime = Query(default_factory=lambda: datetime.now(KST)),
    use_case: IngestFluRtUpperBulkUseCase = Depends(get_ingest_flu_rt_bulk_use_case),
) -> list[RankingIngestOutcomeOut]:
    outcomes = await use_case.execute(snapshot_at=snapshot_at)
    return [RankingIngestOutcomeOut.model_validate(asdict(o)) for o in outcomes]


@router.get(
    "/flu-rt",
    response_model=list[RankingSnapshotOut],
)
async def get_flu_rt_snapshot(
    snapshot_date: date = Query(...),
    snapshot_time: time = Query(...),
    market_type: Literal["000", "001", "101"] = Query(default="001"),
    sort_tp: Literal["1", "2", "3", "4", "5"] = Query(default="1"),
    exchange_type: Literal["1", "2", "3"] = Query(default="3"),
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[RankingSnapshotOut]:
    repo = RankingSnapshotRepository(session)
    rows = await repo.get_at_snapshot(
        snapshot_date, snapshot_time,
        ranking_type=RankingType.FLU_RT,
        sort_tp=sort_tp,
        market_type=market_type,
        exchange_type=exchange_type,
        limit=limit,
    )
    return [RankingSnapshotOut.model_validate(r) for r in rows]
```

### 7.2 APScheduler Job

```python
# app/batch/ranking_jobs.py
async def fire_flu_rt_sync() -> None:
    """매 평일 19:30 KST — 등락률 상위 스냅샷."""
    today = date.today()
    if not is_trading_day(today):
        return
    try:
        snapshot_at = datetime.now(KST)
        async with get_sessionmaker()() as session:
            kiwoom_client = build_kiwoom_client_for("prod-main")
            rkinfo = KiwoomRkInfoClient(kiwoom_client)
            stock_repo = StockRepository(session)
            single = IngestFluRtUpperUseCase(
                session, rkinfo_client=rkinfo, stock_repo=stock_repo,
            )
            bulk = IngestFluRtUpperBulkUseCase(session, single_use_case=single)
            outcomes = await bulk.execute(snapshot_at=snapshot_at)
        success = sum(1 for o in outcomes if o.error is None)
        logger.info(
            "flu rt upper sync 완료 success=%d/%d at=%s",
            success, len(outcomes), snapshot_at,
        )
    except Exception:
        logger.exception("flu rt upper sync 콜백 예외")


scheduler.add_job(
    fire_flu_rt_sync,
    CronTrigger(day_of_week="mon-fri", hour=19, minute=30, timezone=KST),
    id="flu_rt_sync",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
    misfire_grace_time=60 * 30,
)
```

> **5 ranking endpoint cron chain** (Phase F 전체):
> - 19:30 — ka10027 등락률 (본 endpoint)
> - 19:35 — ka10030 당일 거래량
> - 19:40 — ka10031 전일 거래량
> - 19:45 — ka10032 거래대금 (ka10014 공매도 와 시간 충돌 — 19:50 으로 조정)
> - 19:55 — ka10023 거래량 급증
>
> 각 endpoint 의 sync 시간 5초 미만이라 5분 간격으로 충분.

### 7.3 RPS / 시간

| 항목 | 값 |
|------|----|
| 1 시점 sync 호출 수 | 4 (2 market × 2 sort) |
| 호출당 인터벌 | 250ms |
| 동시성 | 4 |
| 이론 시간 | 4 / 4 × 0.25 = 0.25초 |
| 실측 추정 | 1~5초 |

→ cron 19:30 + 30분 grace.

---

## 8. 에러 처리

| HTTP / 응답 | 도메인 예외 | UseCase 정책 |
|-------------|-------------|--------------|
| 400 (잘못된 필터) | `ValueError` | 호출 전 차단 |
| 401 / 403 | `KiwoomCredentialRejectedError` | bubble up |
| 429 | `KiwoomRateLimitedError` | tenacity 재시도 |
| 5xx, 네트워크 | `KiwoomUpstreamError` | 다음 (market, sort_tp) 호출 |
| `return_code != 0` | `KiwoomBusinessError` | outcome.error 노출 |
| 응답 list 빈 | (정상) | upserted=0 |
| stk_cd lookup miss | (skip stock_id) | stock_id=NULL, stock_code_raw 만 보관 |
| 페이지네이션 폭주 | `KiwoomPaginationLimitError` | max_pages=5 도달 시 중단 |

### 8.1 lookup miss 처리

응답에 등장하는 `stk_cd` 가 `stock` 마스터에 없으면 → `stock_id=NULL` + `stock_code_raw` 보관. `LookupStockUseCase.ensure_exists` 호출은 **하지 않음** — 매 호출 lookup 비용 폭증 방지. 운영자가 별도 `seed_stock_master` 또는 `ka10100` lazy fetch 로 보강.

---

## 9. 테스트

### 9.1 Unit

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 단일 페이지 | 200 + list 50건 | 50건 반환 + filters dict |
| 페이지네이션 | 첫 cont-yn=Y, 둘째 N | 합쳐 N건 |
| 빈 list | 200 + `pred_pre_flu_rt_upper=[]` | 빈 list |
| `return_code=1` | 비즈니스 에러 | `KiwoomBusinessError` |
| sort_tp 분기 | UP_RATE | `sort_tp="1"` |
| market_type 분기 | KOSDAQ | `mrkt_tp="101"` |
| exchange_type 분기 | NXT | `stex_tp="2"` |
| 부호 포함 | flu_rt="+29.86" | `_to_decimal` → Decimal("29.86") |
| stk_cd raw 보존 | "005930_NX" | payload.stk_cd_raw="005930_NX" |
| 페이지네이션 폭주 | cont-yn=Y 무한 | `KiwoomPaginationLimitError` |

### 9.2 Integration

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| INSERT (DB 빈) | 응답 50 row | ranking_snapshot 50 row INSERT |
| UPDATE (멱등성) | 같은 호출 두 번 | row 50개 유지, fetched_at 갱신 |
| stock lookup match | stock 1건 + 응답 stk_cd 일치 | stock_id 매핑 |
| stock lookup miss | stock 마스터 비어있음 | stock_id=NULL, stock_code_raw 보관 |
| NXT _NX 보존 | 응답 stk_cd=005930_NX | payload.stk_cd_raw 보존 + stock_id 매핑 (strip 후) |
| 같은 시점 다른 sort_tp | sort=1 + sort=3 동시 | 2 묶음 row 분리 |
| 같은 시점 다른 market_type | KOSPI + KOSDAQ | 2 묶음 row 분리 |
| Bulk 4 호출 | 2 market × 2 sort | 4 outcome 반환 |
| 한 호출 실패 | 1개 KiwoomBusinessError | 다른 호출은 진행, outcome.error 노출 |
| JSONB payload 쿼리 | payload.cur_prc > 50000 | GIN index 활용 |

---

## 10. 완료 기준 (DoD)

### 10.1 코드 (Phase F 5 endpoint 공유 인프라)

- [ ] `app/adapter/out/kiwoom/rkinfo.py` — `KiwoomRkInfoClient` (5 endpoint 메서드 묶음)
- [ ] `app/adapter/out/kiwoom/_records.py` — `FluRtUpperRow/Response`, `RankingMarketType`, `RankingExchangeType`, `FluRtSortType`, `RankingType` enum, `NormalizedRanking`
- [ ] `app/adapter/out/persistence/models/ranking_snapshot.py` — `RankingSnapshot` (JSONB payload)
- [ ] `app/adapter/out/persistence/repositories/ranking_snapshot.py` — `RankingSnapshotRepository.upsert_many` / `get_at_snapshot`
- [ ] `app/application/service/ranking_service.py` — `IngestFluRtUpperUseCase`, `IngestFluRtUpperBulkUseCase`
- [ ] `app/adapter/web/routers/rankings.py` — POST/GET endpoints (5 endpoint 라우터의 본 endpoint)
- [ ] `app/batch/ranking_jobs.py` — APScheduler 등록 (KST mon-fri 19:30)
- [ ] `migrations/versions/007_rankings.py` — `ranking_snapshot` (5 endpoint 통합 테이블)

### 10.2 테스트

- [ ] Unit 10 시나리오 PASS
- [ ] Integration 10 시나리오 PASS
- [ ] coverage `KiwoomRkInfoClient.fetch_flu_rt_upper`, `IngestFluRtUpperUseCase`, `RankingSnapshotRepository` ≥ 80%

### 10.3 운영 검증

- [ ] **`stk_cls` 코드 의미** — Excel 명세 없음. 응답 분포 확인 후 master.md § 12 기록
- [ ] **`cnt` (횟수) 의미** — 운영 검증
- [ ] **`cntr_str` (체결강도) 의미** — 매수/매도 우세 산식
- [ ] 응답 row 수 (한 페이지 ~100? 200?)
- [ ] NXT 응답에서 stk_cd 가 `_NX` 보존인지 stripped 인지
- [ ] `mrkt_tp=000` (전체) vs `001`+`101` 합 — 정합성
- [ ] `pred_pre_sig` 분포 (1~5)
- [ ] 같은 종목·같은 시점이 다른 sort_tp 응답에 등장하는 빈도

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): ka10027 flu rt upper ranking + ranking_snapshot 통합 테이블`
- [ ] `master.md` § 12 결정 기록에:
  - `stk_cls`, `cntr_str`, `cnt` 의미
  - 응답 row 수 / 페이지네이션 빈도
  - NXT stk_cd 형식 (5 endpoint 공통)

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | 운영 default sort_tp | UP_RATE + DOWN_RATE 둘 (현재) / 5 sort 모두 | Phase F 코드화 |
| 2 | 운영 default market_type | KOSPI + KOSDAQ (현재) / ALL 추가 | Phase F 코드화 |
| 3 | sync 시점 | 19:30 (종가 후 1시간) / 다중 시점 (장중 + 장후) | Phase F 후반 |
| 4 | filters default 정책 | 0 (전체) / 거래량 1만주 이상 등 좁히기 | 운영 검증 후 |
| 5 | 5 endpoint 통합 테이블 | **현재 (JSONB payload)** / endpoint 별 분리 | Phase F 코드화 |
| 6 | snapshot_time precision | 초 단위 / 분 단위 | 운영 검증 |
| 7 | stock lookup miss 처리 | NULL 허용 (현재) / lazy fetch | 운영 1주 모니터 후 |
| 8 | 백필 정책 | 운영 검증 후 (키움이 과거 시점 스냅샷 응답 가능 여부) | DoD § 10.3 |

### 11.2 알려진 위험

- **5 endpoint 통합 테이블의 JSONB 부담**: 가변 스키마 흡수 vs 인덱스/쿼리 비용. 운영 1년 후 disk + 쿼리 시간 측정해 분리 검토
- **`mrkt_tp` 의미 4번째 정의**: ka10099 (0/10/30/...), ka10101 (0/1/2/4/7), 본 카테고리 (000/001/101). UseCase enum 분리 필수 — 같은 파라미터 이름의 다른 의미 (Phase D 의 `tic_scope` 와 같은 패턴)
- **stock lookup miss 빈번 가능**: 신규 상장 / ETF / ETN / 스펙 / 우선주 등 ka10099 동기화 lag 사이에 응답에 등장 가능. NULL 허용 정책 + 별도 alert 로 lookup miss 비율 모니터
- **NXT 응답 row 수 작음 (KRX 보다)**: NXT 거래량이 KRX 의 ~10% 이라 응답 row 수도 적음. 백테스팅 시그널 정합성 검증 시 분포 차이 주의
- **응답 정렬 가정**: list 순서가 sort_tp 순위 (1, 2, 3, ...) — 응답 정렬 미확정 시 `rank` 컬럼 의미 깨짐. 첫 호출 검증
- **백필 미지원 가능성**: 키움이 과거 시점 스냅샷을 응답하지 않을 가능성 — base_dt 같은 파라미터 없음. 본 endpoint 는 forward-only ingest. 과거 분석은 자체 적재 데이터로만
- **순위 변동 알람 시그널**: 같은 종목이 어제 5위 → 오늘 50위 같은 변화 탐지 derived feature — Phase H
- **`updown_incls=1` (상하한 포함)**: 0 (불포함) 사용 시 상한가/하한가 종목이 응답에서 제외 — 시그널 누락. 운영 default 1 권장
- **`stk_cnd` 13종 필터의 default**: 0 (전체) 가 가장 단순. 단, 우선주 / 스펙 / ETF 가 상위에 등장하면 노이즈 — 운영 1주 후 결정

### 11.3 ka10027 vs ka10030/31/32/23 비교

| 항목 | ka10027 (본) | ka10030 (당일거래량) | ka10031 (전일거래량) | ka10032 (거래대금) | ka10023 (거래량 급증) |
|------|---------|--------|--------|--------|--------|
| URL | /api/dostk/rkinfo | 동일 | 동일 | 동일 | 동일 |
| Body 필드 수 | 9 | 9 | 5 | 3 | 8 |
| sort_tp 의미 | 5종 (등락률) | 3종 (거래량/회전율/대금) | qry_tp (1/2) | (없음) | 4종 (급증량/률/감량/감률) |
| 응답 list 키 | `pred_pre_flu_rt_upper` | `tdy_trde_qty_upper` | `pred_trde_qty_upper` | `trde_prica_upper` | `trde_qty_sdnin` |
| 응답 필드 수 | 12 | **23** (장중/장후/장전 분리) | **6** (단순) | 13 | 10 |
| 응답 정렬 기준 | flu_rt | trde_qty / pred_rt | trde_qty | trde_prica | sdnin_qty |
| primary_metric | flu_rt | trde_qty | trde_qty | trde_prica | sdnin_qty (또는 sdnin_rt) |
| RankingType enum | FLU_RT | TODAY_VOLUME | PRED_VOLUME | TRDE_PRICA | VOLUME_SDNIN |

→ 5 endpoint 의 공통 = `/api/dostk/rkinfo` URL + `mrkt_tp/stex_tp` 필터 + `stk_cd/stk_nm/cur_prc` 응답 핵심.
→ 다른 점 = sort_tp 의미 / 응답 필드 / list 키.
→ **JSONB payload 통합** 으로 5 endpoint 가 같은 테이블 사용. 새 ranking endpoint 추가 시 enum + UseCase 만 작성.

### 11.4 향후 확장

- **derived feature: 순위 변동 시그널** — 같은 종목의 N일 순위 변화 → 시그널
- **다중 시점 sync**: 장 시작 (09:30) + 장중 (13:00) + 종가 후 (19:30) 3 시점
- **ranking_type cross-reference**: 같은 시점에 등락률 상위 + 거래량 상위 둘 다 등장한 종목 → 강한 시그널
- **응답 row 수 monitor**: 일별 응답 row 수의 추세 — 거래소 정책 변경 / 응답 limit 변경 detect
- **JSONB payload 의 typed view**: `payload->'cur_prc'::bigint` 같은 generated column 으로 자주 쓰는 필드는 indexed column 화 — Phase H

---

_Phase F 의 reference 계획서. 5 ranking endpoint 의 통합 테이블 (`ranking_snapshot`) + JSONB payload + 5 endpoint 공유 클라이언트 (`KiwoomRkInfoClient`) 패턴 정의. ka10030/31/32/23 은 본 계획서의 패턴 복제 — 응답 schema + sort_tp 분기만 다름._
