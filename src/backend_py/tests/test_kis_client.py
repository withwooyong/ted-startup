"""KisClient 단위 테스트 — httpx.MockTransport 로 네트워크 없이 검증."""
from __future__ import annotations

from decimal import Decimal

import httpx
import pytest

from app.adapter.out.external import KisAuthError, KisClient, KisClientError
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
            return httpx.Response(
                401, json={"error_description": "invalid appkey"}
            )
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    async with KisClient(_settings(), transport=transport) as client:
        with pytest.raises(KisAuthError):
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
        with pytest.raises(KisClientError):
            await client.fetch_balance()
