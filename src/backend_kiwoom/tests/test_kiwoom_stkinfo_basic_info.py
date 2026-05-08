"""KiwoomStkInfoClient.fetch_basic_info (ka10001) — B-γ-1 어댑터 + Pydantic + 정규화.

KRX-only 결정 (계획서 § 4.3 권장 (a) 채택) — `_NX`/`_AL` suffix 미지원.
ka10100 의 `_validate_stk_cd_for_lookup` 재사용 (6자리 ASCII).

httpx.MockTransport 주입으로 외부 호출 0.

시나리오 (§ 9.1):
1. 정상 응답 → StockBasicInfoResponse (45 필드 + return_code)
2. 250hgst alias 매핑 — 비-식별자 키
3. return_code=1 → KiwoomBusinessError (트랜스포트가 raise)
4. 401 → KiwoomCredentialRejectedError
5. stk_cd 6자리 검증 (5자리 / suffix / 영문 → ValueError)
6. 응답 stk_cd 빈값 → KiwoomResponseValidationError (__context__ None)
7. 정규화 — zero-pad / 부호 / 빈값 / Decimal / yyyymmdd
8. PER/EPS/ROE 빈값 → None (외부 벤더 미공급 종목 — § 11.2)
9. exchange="KRX" 고정
10. Pydantic extra 필드 무시
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.adapter.out.kiwoom._client import KiwoomClient
from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomCredentialRejectedError,
    KiwoomResponseValidationError,
)
from app.adapter.out.kiwoom.stkinfo import (
    KiwoomStkInfoClient,
    NormalizedFundamental,
    StockBasicInfoResponse,
    normalize_basic_info,
    strip_kiwoom_suffix,
)

# ka10001 응답 예시 — Excel R76 기반. 일부 필드만 채움 (외부 벤더 PER/EPS/ROE 빈값 시뮬).
_SAMSUNG_BODY: dict[str, Any] = {
    "stk_cd": "005930",
    "stk_nm": "삼성전자",
    "setl_mm": "12",
    "fav": "5000",
    "fav_unit": "원",
    "cap": "1311",
    "flo_stk": "5969782",
    "mac": "4356400",
    "mac_wght": "12.3456",
    "for_exh_rt": "53.2100",
    "repl_pric": "66780",
    "crd_rt": "+0.0800",
    "dstr_stk": "5969782",
    "dstr_rt": "100.0000",
    # C — 외부 벤더 빈값 시뮬
    "per": "",
    "eps": "",
    "roe": "",
    "pbr": "",
    "ev": "",
    "bps": "-75300",
    "sale_amt": "300000000",
    "bus_pro": "50000000",
    "cup_nga": "30000000",
    # D
    "250hgst": "+181400",
    "250hgst_pric_dt": "20251215",
    "250hgst_pric_pre_rt": "-25.5000",
    "250lwst": "-91200",
    "250lwst_pric_dt": "20250612",
    "250lwst_pric_pre_rt": "+48.0000",
    "oyr_hgst": "+181400",
    "oyr_lwst": "-91200",
    # E
    "cur_prc": "75800",
    "pre_sig": "2",
    "pred_pre": "+200",
    "flu_rt": "+0.2640",
    "trde_qty": "1234567",
    "trde_pre": "+5.4321",
    "open_pric": "75600",
    "high_pric": "76000",
    "low_pric": "75400",
    "upl_pric": "98800",
    "lst_pric": "53000",
    "base_pric": "75600",
    "exp_cntr_pric": "75800",
    "exp_cntr_qty": "12345",
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다",
}


async def _const_token() -> str:
    return "FixedToken-" + "X" * 100


def _make_kiwoom_client(handler: Callable[[httpx.Request], httpx.Response]) -> KiwoomClient:
    return KiwoomClient(
        base_url="https://api.kiwoom.com",
        token_provider=_const_token,
        transport=httpx.MockTransport(handler),
        max_attempts=1,
        retry_min_wait=0.0,
        retry_max_wait=0.0,
        min_request_interval_seconds=0.0,
    )


# -----------------------------------------------------------------------------
# 1. 정상 호출 — 응답 파싱
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_basic_info_returns_response_for_samsung() -> None:
    captured_body: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured_body.update(json.loads(request.content))
        assert request.headers["api-id"] == "ka10001"
        assert request.url.path == "/api/dostk/stkinfo"
        return httpx.Response(200, json=_SAMSUNG_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        resp = await adapter.fetch_basic_info("005930")

    assert isinstance(resp, StockBasicInfoResponse)
    assert resp.stk_cd == "005930"
    assert resp.stk_nm == "삼성전자"
    assert resp.setl_mm == "12"
    assert resp.return_code == 0
    assert captured_body == {"stk_cd": "005930"}


# -----------------------------------------------------------------------------
# 2. 250hgst alias 매핑 (비-식별자 키)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_basic_info_250d_alias_mapping() -> None:
    """`250hgst` / `250lwst` 같은 비-식별자 키가 alias 로 매핑됨."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_SAMSUNG_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        resp = await adapter.fetch_basic_info("005930")

    assert resp.high_250d == "+181400"
    assert resp.high_250d_date == "20251215"
    assert resp.high_250d_pre_rate == "-25.5000"
    assert resp.low_250d == "-91200"
    assert resp.low_250d_date == "20250612"
    assert resp.low_250d_pre_rate == "+48.0000"


# -----------------------------------------------------------------------------
# 3-4. 에러 전파
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_basic_info_propagates_business_error() -> None:
    """return_code=1 (존재하지 않는 종목 등) — 트랜스포트가 KiwoomBusinessError raise."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"return_code": 1, "return_msg": "존재하지 않는 종목"},
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        with pytest.raises(KiwoomBusinessError) as exc_info:
            await adapter.fetch_basic_info("999999")

    assert exc_info.value.return_code == 1


@pytest.mark.asyncio
async def test_fetch_basic_info_propagates_credential_rejected() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        with pytest.raises(KiwoomCredentialRejectedError):
            await adapter.fetch_basic_info("005930")


# -----------------------------------------------------------------------------
# 5. stk_cd 사전 검증 — 호출 자체 차단 (KRX-only, ka10100 패턴 재사용)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_basic_info_rejects_short_stk_cd() -> None:
    """5자리 stk_cd → ValueError. 호출 안 함."""
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_SAMSUNG_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        with pytest.raises(ValueError):
            await adapter.fetch_basic_info("00593")

    assert call_count == 0


@pytest.mark.asyncio
async def test_fetch_basic_info_rejects_nx_suffix() -> None:
    """`_NX` suffix 거부 — KRX-only 결정 (계획서 § 4.3)."""
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_SAMSUNG_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        with pytest.raises(ValueError):
            await adapter.fetch_basic_info("005930_NX")

    assert call_count == 0


@pytest.mark.asyncio
async def test_fetch_basic_info_rejects_invalid_codes() -> None:
    """영문 / 빈값 / 공백 거부."""
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_SAMSUNG_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        for invalid in ("ABC123", "00593a", "      ", "", "0059300"):
            with pytest.raises(ValueError):
                await adapter.fetch_basic_info(invalid)

    assert call_count == 0


# -----------------------------------------------------------------------------
# 6. Pydantic 검증 실패 — __context__ None 보장
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_basic_info_raises_validation_when_stk_cd_empty() -> None:
    """응답 stk_cd 빈값 → KiwoomResponseValidationError + __context__ None.

    StockBasicInfoResponse.stk_cd 는 min_length=1.
    flag-then-raise-outside-except 패턴 (B-β 1R 2b-H2 회귀).
    """

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={**_SAMSUNG_BODY, "stk_cd": ""})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        with pytest.raises(KiwoomResponseValidationError) as exc_info:
            await adapter.fetch_basic_info("005930")

    err = exc_info.value
    assert err.__context__ is None, "Pydantic ValidationError context leak — except 밖 raise 회귀"
    assert err.__cause__ is None


# -----------------------------------------------------------------------------
# 7. 정규화 — _to_int / _to_decimal / _parse_yyyymmdd
# -----------------------------------------------------------------------------


def test_normalize_basic_info_full_response() -> None:
    """45 필드 정규화 — string → BIGINT/NUMERIC/DATE/None."""
    resp = StockBasicInfoResponse.model_validate(_SAMSUNG_BODY)
    asof = date(2026, 5, 8)
    n: NormalizedFundamental = normalize_basic_info(resp, asof_date=asof)

    assert isinstance(n, NormalizedFundamental)
    assert n.stock_code == "005930"
    assert n.exchange == "KRX"
    assert n.asof_date == asof
    assert n.stock_name == "삼성전자"
    assert n.settlement_month == "12"

    # B
    assert n.face_value == 5000
    assert n.face_value_unit == "원"
    assert n.capital_won == 1311
    assert n.listed_shares == 5969782
    assert n.market_cap == 4356400
    assert n.market_cap_weight == Decimal("12.3456")
    assert n.foreign_holding_rate == Decimal("53.2100")
    assert n.replacement_price == 66780
    assert n.credit_rate == Decimal("+0.0800")
    assert n.circulating_shares == 5969782
    assert n.circulating_rate == Decimal("100.0000")

    # C — PER/EPS/ROE/PBR/EV 빈값 → None (외부 벤더 미공급)
    assert n.per_ratio is None
    assert n.eps_won is None
    assert n.roe_pct is None
    assert n.pbr_ratio is None
    assert n.ev_ratio is None
    assert n.bps_won == -75300  # 음수 — 부호 보존
    assert n.revenue_amount == 300000000
    assert n.operating_profit == 50000000
    assert n.net_profit == 30000000

    # D
    assert n.high_250d == 181400  # `+` 부호 → int
    assert n.high_250d_date == date(2025, 12, 15)
    assert n.high_250d_pre_rate == Decimal("-25.5000")
    assert n.low_250d == -91200
    assert n.low_250d_date == date(2025, 6, 12)
    assert n.low_250d_pre_rate == Decimal("+48.0000")
    assert n.year_high == 181400
    assert n.year_low == -91200

    # E
    assert n.current_price == 75800
    assert n.prev_compare_sign == "2"
    assert n.prev_compare_amount == 200
    assert n.change_rate == Decimal("+0.2640")
    assert n.trade_volume == 1234567
    assert n.trade_compare_rate == Decimal("+5.4321")
    assert n.open_price == 75600
    assert n.high_price == 76000
    assert n.low_price == 75400
    assert n.upper_limit_price == 98800
    assert n.lower_limit_price == 53000
    assert n.base_price == 75600
    assert n.expected_match_price == 75800
    assert n.expected_match_volume == 12345


def test_normalize_basic_info_handles_empty_strings_as_none() -> None:
    """빈 문자열 / `-` / `+` → None. 잘못된 숫자 → None (raise 안 함)."""
    body = {
        "stk_cd": "000001",
        "stk_nm": "X",
        "fav": "",
        "cap": "-",
        "flo_stk": "+",
        "mac": "abc",  # 잘못된 숫자 → None
        "mac_wght": "",
        "for_exh_rt": "-",
        "per": "",
        "eps": "",
        "250hgst_pric_dt": "invalid",
        "250lwst_pric_dt": "",
        "return_code": 0,
    }
    resp = StockBasicInfoResponse.model_validate(body)
    n = normalize_basic_info(resp, asof_date=date(2026, 5, 8))

    assert n.face_value is None
    assert n.capital_won is None
    assert n.listed_shares is None
    assert n.market_cap is None
    assert n.market_cap_weight is None
    assert n.foreign_holding_rate is None
    assert n.high_250d_date is None
    assert n.low_250d_date is None
    assert n.settlement_month is None
    assert n.face_value_unit is None
    assert n.prev_compare_sign is None


def test_normalize_basic_info_strips_nx_suffix() -> None:
    """응답 stk_cd 가 `_NX`/`_AL` suffix 를 가지면 base code 로 정규화 (방어)."""
    body = {**_SAMSUNG_BODY, "stk_cd": "005930_NX"}
    resp = StockBasicInfoResponse.model_validate(body)
    n = normalize_basic_info(resp, asof_date=date(2026, 5, 8))
    assert n.stock_code == "005930"


# -----------------------------------------------------------------------------
# 8. exchange="KRX" 고정 — 본 chunk 의 KRX-only 결정
# -----------------------------------------------------------------------------


def test_normalize_basic_info_exchange_always_krx() -> None:
    """B-γ-1 KRX-only — exchange 필드는 항상 'KRX' 고정."""
    resp = StockBasicInfoResponse.model_validate(_SAMSUNG_BODY)
    n = normalize_basic_info(resp, asof_date=date(2026, 5, 8))
    assert n.exchange == "KRX"


# -----------------------------------------------------------------------------
# 9. Pydantic extra 필드 무시
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_basic_info_extra_fields_ignored() -> None:
    """키움이 신규 필드 추가해도 어댑터 안 깨짐."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={**_SAMSUNG_BODY, "newField2026": "value", "anotherField": 42},
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        resp = await adapter.fetch_basic_info("005930")

    assert resp.stk_cd == "005930"


# -----------------------------------------------------------------------------
# strip_kiwoom_suffix 단위 테스트
# -----------------------------------------------------------------------------


def test_strip_kiwoom_suffix_handles_nx() -> None:
    assert strip_kiwoom_suffix("005930_NX") == "005930"


def test_strip_kiwoom_suffix_handles_al() -> None:
    assert strip_kiwoom_suffix("005930_AL") == "005930"


def test_strip_kiwoom_suffix_returns_base_unchanged() -> None:
    assert strip_kiwoom_suffix("005930") == "005930"


def test_strip_kiwoom_suffix_empty_string() -> None:
    assert strip_kiwoom_suffix("") == ""


# =============================================================================
# 2R 회귀 — CRITICAL/HIGH 수정 검증
# =============================================================================


# A-C1 BIGINT 경계 가드 ----------------------------------------------------------


def test_to_int_returns_none_for_bigint_overflow() -> None:
    """A-C1 — BIGINT 한계 (2^63-1) 초과 → None. 트랜잭션 abort 차단."""
    from app.adapter.out.kiwoom.stkinfo import _to_int

    assert _to_int("9" * 30) is None  # 거대 양수
    assert _to_int("-" + "9" * 30) is None  # 거대 음수
    assert _to_int(str(2**63)) is None  # 정확히 BIGINT_MAX + 1
    assert _to_int(str(-(2**63) - 1)) is None  # BIGINT_MIN - 1


def test_to_int_accepts_bigint_boundaries() -> None:
    """경계값은 통과 — BIGINT_MIN 과 BIGINT_MAX."""
    from app.adapter.out.kiwoom.stkinfo import _to_int

    assert _to_int(str(2**63 - 1)) == 2**63 - 1
    assert _to_int(str(-(2**63))) == -(2**63)


# A-C2 NaN/Infinity/sNaN 가드 ----------------------------------------------------


def test_to_decimal_rejects_nan() -> None:
    """A-C2 — NaN 거부. PG NUMERIC 받지만 다운스트림 산술 폭발."""
    from app.adapter.out.kiwoom.stkinfo import _to_decimal

    assert _to_decimal("NaN") is None
    assert _to_decimal("nan") is None
    assert _to_decimal("-NaN") is None


def test_to_decimal_rejects_infinity() -> None:
    """A-C2 — Infinity / -Infinity 거부."""
    from app.adapter.out.kiwoom.stkinfo import _to_decimal

    assert _to_decimal("Infinity") is None
    assert _to_decimal("-Infinity") is None
    assert _to_decimal("inf") is None
    assert _to_decimal("-inf") is None


def test_to_decimal_rejects_signaling_nan() -> None:
    """A-C2 / A-H4 — sNaN (signaling NaN) 거부. format() 에서 InvalidOperation 차단."""
    from app.adapter.out.kiwoom.stkinfo import _to_decimal

    assert _to_decimal("sNaN") is None
    assert _to_decimal("-sNaN") is None


# M-2 _to_decimal 쉼표 처리 (M-2 대칭) -----------------------------------------


def test_to_decimal_strips_commas() -> None:
    """M-2 — _to_int 와 비대칭 해소: 천단위 콤마 제거."""
    from app.adapter.out.kiwoom.stkinfo import _to_decimal

    assert _to_decimal("1,234.56") == Decimal("1234.56")
    assert _to_decimal("+1,234,567") == Decimal("1234567")
    assert _to_decimal("-1,000.00") == Decimal("-1000.00")


# A-H1 Pydantic max_length 강제 -------------------------------------------------


def test_response_rejects_oversized_setl_mm() -> None:
    """A-H1 — setl_mm 가 길이 위반 시 ValidationError. Pydantic 단계 차단."""
    from pydantic import ValidationError

    body = {**_SAMSUNG_BODY, "setl_mm": "X" * 100}
    with pytest.raises(ValidationError):
        StockBasicInfoResponse.model_validate(body)


def test_response_rejects_oversized_pre_sig() -> None:
    """A-H1 — pre_sig CHAR(1) 컬럼 — Pydantic max_length=1."""
    from pydantic import ValidationError

    body = {**_SAMSUNG_BODY, "pre_sig": "!" * 9999}
    with pytest.raises(ValidationError):
        StockBasicInfoResponse.model_validate(body)


def test_response_rejects_oversized_fav_unit() -> None:
    """A-H1 — fav_unit VARCHAR(10) 컬럼 — Pydantic max_length=10."""
    from pydantic import ValidationError

    body = {**_SAMSUNG_BODY, "fav_unit": "X" * 5000}
    with pytest.raises(ValidationError):
        StockBasicInfoResponse.model_validate(body)


def test_response_rejects_oversized_numeric_strings() -> None:
    """A-H1 — 숫자 string 도 32자 cap (BIGINT 19자 + 부호/콤마 여유)."""
    from pydantic import ValidationError

    body = {**_SAMSUNG_BODY, "mac": "9" * 100}
    with pytest.raises(ValidationError):
        StockBasicInfoResponse.model_validate(body)


@pytest.mark.asyncio
async def test_fetch_basic_info_oversized_response_maps_to_validation_error() -> None:
    """A-H1 — 거대 string 응답 → KiwoomResponseValidationError + __context__ None."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={**_SAMSUNG_BODY, "setl_mm": "X" * 100})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        with pytest.raises(KiwoomResponseValidationError) as exc_info:
            await adapter.fetch_basic_info("005930")

    err = exc_info.value
    assert err.__context__ is None, "Pydantic ValidationError context leak"
    assert err.__cause__ is None


# A-L1 _validate_stk_cd 메시지 cap ---------------------------------------------


def test_validate_stk_cd_message_capped_at_50_chars() -> None:
    """A-L1 — 거대 입력 시 메시지의 입력값은 50자 cap (log line 폭주 차단)."""
    from app.adapter.out.kiwoom.stkinfo import _validate_stk_cd_for_lookup

    huge_input = "X" * 10_000
    with pytest.raises(ValueError) as exc_info:
        _validate_stk_cd_for_lookup(huge_input)

    msg = str(exc_info.value)
    # 메시지 자체가 거대해지면 안 됨 — 입력값 부분이 50자 cap
    assert len(msg) < 200, f"메시지가 길이 cap 안 됨 (len={len(msg)})"


# C-M4 normalize_basic_info exchange 인자 BC 보존 -----------------------------


def test_normalize_basic_info_accepts_exchange_kwarg() -> None:
    """C-M4 — exchange 인자로 NXT/SOR 명시 가능 (Phase C 진입 시 BC 보존)."""
    resp = StockBasicInfoResponse.model_validate(_SAMSUNG_BODY)
    n = normalize_basic_info(resp, asof_date=date(2026, 5, 8), exchange="NXT")
    assert n.exchange == "NXT"

    n2 = normalize_basic_info(resp, asof_date=date(2026, 5, 8))
    assert n2.exchange == "KRX", "디폴트는 KRX (KRX-only 결정)"
