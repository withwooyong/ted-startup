"""KisClient 단위 테스트 — httpx.MockTransport 로 네트워크 없이 검증."""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest

from app.adapter.out.external import (
    KisClient,
    KisCredentialRejectedError,
    KisCredentials,
    KisEnvironment,
    KisNotConfiguredError,
    KisUpstreamError,
)
from app.config.settings import Settings


def _settings(
    app_key: str = "MOCK-APP-KEY",
    app_secret: str = "MOCK-APP-SECRET",
    account_no: str = "12345678-01",
) -> Settings:
    return Settings(
        kis_app_key_mock=app_key,
        kis_app_secret_mock=app_secret,
        kis_account_no_mock=account_no,
    )


def _ok_token_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "access_token": "FAKE_TOKEN_ABC",
            "token_type": "Bearer",
            "expires_in": 86400,
        },
    )


def _balance_response(*rows: dict[str, object]) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "rt_cd": "0",
            "msg_cd": "MCA00000",
            "msg1": "정상처리 되었습니다.",
            "output1": list(rows),
            "output2": [{"tot_evlu_amt": "1000000", "dnca_tot_amt": "500000"}],
        },
    )


# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_balance_parses_output1_rows_and_skips_zero_qty() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/oauth2/tokenP":
            return _ok_token_response()
        if request.url.path.endswith("/inquire-balance"):
            return _balance_response(
                {
                    "pdno": "005930",
                    "prdt_name": "삼성전자",
                    "hldg_qty": "10",
                    "pchs_avg_pric": "70000.50",
                },
                {
                    "pdno": "000660",
                    "prdt_name": "SK하이닉스",
                    "hldg_qty": "3",
                    "pchs_avg_pric": "215000",
                },
                {
                    "pdno": "033780",
                    "prdt_name": "KT&G",
                    "hldg_qty": "0",  # 수량 0은 건너뜀
                    "pchs_avg_pric": "0",
                },
            )
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    async with KisClient(_settings(), transport=transport) as client:
        rows = await client.fetch_balance()

    assert len(rows) == 2
    samsung = next(r for r in rows if r.stock_code == "005930")
    assert samsung.stock_name == "삼성전자"
    assert samsung.quantity == 10
    assert samsung.avg_buy_price == Decimal("70000.50")

    sk = next(r for r in rows if r.stock_code == "000660")
    assert sk.quantity == 3
    assert sk.avg_buy_price == Decimal("215000.00")

    # 토큰 요청 1 + 잔고조회 1
    assert [c.url.path for c in calls][:2] == [
        "/oauth2/tokenP",
        "/uapi/domestic-stock/v1/trading/inquire-balance",
    ]


@pytest.mark.asyncio
async def test_balance_request_uses_mock_tr_id_and_account_parts() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return _ok_token_response()
        captured["headers"] = dict(request.headers)
        captured["params"] = dict(request.url.params)
        return _balance_response()

    transport = httpx.MockTransport(handler)
    async with KisClient(_settings(account_no="12345678-01"), transport=transport) as client:
        await client.fetch_balance()

    headers = captured["headers"]
    params = captured["params"]
    assert headers["tr_id"] == "VTTC8434R"  # 모의 전용
    assert headers["custtype"] == "P"
    assert headers["authorization"].startswith("Bearer FAKE_TOKEN_ABC")
    assert params["CANO"] == "12345678"
    assert params["ACNT_PRDT_CD"] == "01"


@pytest.mark.asyncio
async def test_token_is_cached_across_calls() -> None:
    token_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            token_calls["n"] += 1
            return _ok_token_response()
        return _balance_response()

    transport = httpx.MockTransport(handler)
    async with KisClient(_settings(), transport=transport) as client:
        await client.fetch_balance()
        await client.fetch_balance()
        await client.fetch_balance()

    assert token_calls["n"] == 1


@pytest.mark.asyncio
async def test_raises_auth_error_when_token_endpoint_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(401, json={"error_description": "invalid appkey"})
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    async with KisClient(_settings(), transport=transport) as client:
        # 서브클래스도 KisUpstreamError 로 잡히므로 이 테스트는 회귀 안전장치 성격으로 보존.
        with pytest.raises(KisUpstreamError):
            await client.fetch_balance()


@pytest.mark.parametrize("status_code", [401, 403])
@pytest.mark.asyncio
async def test_token_401_or_403_raises_credential_rejected(status_code: int) -> None:
    """KIS 가 토큰 발급 시 4xx 로 자격증명을 거부 → KisCredentialRejectedError.

    업스트림 장애(5xx) 와 의미론적으로 구분되어 라우터에서 4xx 로 매핑 가능해야 함.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(status_code, json={"error_description": "invalid"})
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    async with KisClient(_settings(), transport=transport) as client:
        with pytest.raises(KisCredentialRejectedError):
            await client.fetch_balance()


@pytest.mark.asyncio
async def test_token_500_raises_base_auth_error_not_rejection() -> None:
    """KIS 가 5xx 를 반환 → KisUpstreamError 만 해당. KisCredentialRejectedError 는 아님.

    credential 은 유효할 수 있고 KIS 서버가 일시 장애인 상황. 라우터에서 502 로 매핑.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(500, json={"error": "internal"})
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    async with KisClient(_settings(), transport=transport) as client:
        with pytest.raises(KisUpstreamError) as exc_info:
            await client.fetch_balance()
        # 서브클래스가 아닌 base 타입 정확히 검증 — 의미 분리 보장.
        assert not isinstance(exc_info.value, KisCredentialRejectedError)


@pytest.mark.parametrize("status_code", [401, 403])
@pytest.mark.asyncio
async def test_balance_401_or_403_raises_credential_rejected(status_code: int) -> None:
    """토큰은 발급됐으나 잔고조회 시점에 4xx 로 자격증명이 거부되는 드문 경로."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return _ok_token_response()
        return httpx.Response(status_code, json={"error_description": "revoked"})

    transport = httpx.MockTransport(handler)
    async with KisClient(_settings(), transport=transport) as client:
        with pytest.raises(KisCredentialRejectedError):
            await client.fetch_balance()


@pytest.mark.asyncio
async def test_raises_when_rt_cd_is_not_zero() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return _ok_token_response()
        return httpx.Response(
            200,
            json={"rt_cd": "1", "msg1": "권한이 없습니다.", "output1": []},
        )

    transport = httpx.MockTransport(handler)
    async with KisClient(_settings(), transport=transport) as client:
        with pytest.raises(KisUpstreamError):
            await client.fetch_balance()


# -----------------------------------------------------------------------------
# in-memory mock 모드 (settings 플래그 기반 자동 주입)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_in_memory_mock_mode_skips_real_http() -> None:
    # 빈 자격증명 + in-memory 플래그만 True — 외부 호출 없이 3건 반환해야 함.
    settings = Settings(
        kis_app_key_mock="",
        kis_app_secret_mock="",
        kis_account_no_mock="",
        kis_use_in_memory_mock=True,
    )
    async with KisClient(settings) as client:
        rows = await client.fetch_balance()

    assert len(rows) == 3
    codes = {r.stock_code for r in rows}
    assert codes == {"005930", "000660", "035420"}
    samsung = next(r for r in rows if r.stock_code == "005930")
    assert samsung.quantity == 10
    assert samsung.avg_buy_price == Decimal("72000.00")


@pytest.mark.asyncio
async def test_explicit_transport_overrides_in_memory_flag() -> None:
    # 테스트에서 주입한 transport 는 in-memory 플래그보다 우선해야 한다 (기존 테스트 불변).
    handler_called: list[bool] = []

    def handler(request: httpx.Request) -> httpx.Response:
        handler_called.append(True)
        if request.url.path == "/oauth2/tokenP":
            return _ok_token_response()
        return _balance_response()

    transport = httpx.MockTransport(handler)
    settings = Settings(
        kis_app_key_mock="K",
        kis_app_secret_mock="S",
        kis_account_no_mock="12345678-01",
        kis_use_in_memory_mock=True,  # 플래그 켜져 있어도 transport 가 우선
    )
    async with KisClient(settings, transport=transport) as client:
        await client.fetch_balance()

    assert handler_called, "명시적 transport 가 우선 적용되어야 함"


# -----------------------------------------------------------------------------
# PR 2 — kis_rest_real 환경 분기 (외부 호출 0, MockTransport 로 URL·TR_ID 검증)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_environment_uses_prod_url_and_tr_id() -> None:
    """REAL 환경: base_url = openapi.koreainvestment.com:9443, TR_ID = TTTC8434R."""
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            # 실 호스트로 향하는지 검증 — scheme/host/port 모두 확인.
            captured["token_host"] = request.url.host
            captured["token_port"] = request.url.port
            captured["token_scheme"] = request.url.scheme
            return _ok_token_response()
        if request.url.path.endswith("/inquire-balance"):
            captured["balance_tr_id"] = request.headers.get("tr_id")
            captured["balance_host"] = request.url.host
            captured["balance_port"] = request.url.port
            return _balance_response()
        return httpx.Response(500)

    real_creds = KisCredentials(
        app_key="REAL-APP-KEY",
        app_secret="REAL-APP-SECRET",
        account_no="99998888-01",
    )
    transport = httpx.MockTransport(handler)
    async with KisClient(
        _settings(),
        environment=KisEnvironment.REAL,
        credentials=real_creds,
        transport=transport,
    ) as client:
        await client.fetch_balance()

    assert captured["token_scheme"] == "https"
    assert captured["token_host"] == "openapi.koreainvestment.com"
    assert captured["token_port"] == 9443
    assert captured["balance_tr_id"] == "TTTC8434R"
    assert captured["balance_host"] == "openapi.koreainvestment.com"


@pytest.mark.asyncio
async def test_real_environment_requires_credentials() -> None:
    """REAL 환경에서 credentials 미주입 → KisNotConfiguredError 로 loud fail."""
    with pytest.raises(KisNotConfiguredError, match="credentials 주입 필수"):
        KisClient(_settings(), environment=KisEnvironment.REAL, credentials=None)


@pytest.mark.asyncio
async def test_mock_environment_accepts_explicit_credentials() -> None:
    """MOCK 환경에서도 credentials 주입 가능 — Settings 값을 override."""
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return _ok_token_response()
        captured["appkey"] = request.headers.get("appkey")
        captured["tr_id"] = request.headers.get("tr_id")
        return _balance_response()

    injected = KisCredentials(
        app_key="INJECTED-KEY",
        app_secret="INJECTED-SECRET",
        account_no="11112222-03",
    )
    transport = httpx.MockTransport(handler)
    async with KisClient(
        _settings(app_key="FROM-SETTINGS"),
        environment=KisEnvironment.MOCK,
        credentials=injected,
        transport=transport,
    ) as client:
        await client.fetch_balance()

    # 주입 값이 Settings 을 오버라이드 + MOCK 은 여전히 VTTC8434R
    assert captured["appkey"] == "INJECTED-KEY"
    assert captured["tr_id"] == "VTTC8434R"


def test_valid_connection_types_matches_db_check_constraint() -> None:
    """`VALID_CONNECTION_TYPES` (Python) 와 migration 007 의 DB CHECK 리스트가 동기화되어 있는지 assert.

    PR 4+ 에서 새 connection_type 을 추가할 때 한 쪽만 고치면 런타임에서야 CheckViolation
    이 드러나는 경로를 조기에 잡는다.
    """
    from app.adapter.out.persistence.models.portfolio import VALID_CONNECTION_TYPES

    assert set(VALID_CONNECTION_TYPES) == {"manual", "kis_rest_mock", "kis_rest_real"}


def test_kis_credentials_repr_masks_secret() -> None:
    """KisCredentials.__repr__ 는 app_secret/account_no 를 마스킹, app_key 는 끝 4자리만."""
    creds = KisCredentials(
        app_key="ABCDEFGHIJKL3456",
        app_secret="super-secret-value",
        account_no="99998888-01",
    )
    rendered = repr(creds)
    assert "3456" in rendered  # 끝 4자리 노출
    assert "super-secret-value" not in rendered
    assert "99998888" not in rendered
    assert "<masked>" in rendered
