"""KrxClient 단위 테스트 — pykrx 함수 monkeypatch 로 실망 없이 빠르게."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd
import pytest

from app.adapter.out.external import KrxClient
from app.config.settings import Settings


def _make_client() -> KrxClient:
    # 간격 0으로 낮춰 테스트 속도 확보
    settings = Settings(krx_id="tester", krx_pw="pw", krx_request_interval_seconds=0.0)
    return KrxClient(settings=settings)


def _fake_ohlcv() -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "종목명": ["삼성전자", "SK하이닉스"],
            "시가": [78_000, 243_500],
            "고가": [79_200, 247_000],
            "저가": [77_800, 242_000],
            "종가": [78_500, 245_000],
            "거래량": [15_234_567, 3_456_789],
            "등락률": [0.64, -1.21],
            "시장구분": ["KOSPI", "KOSPI"],
        },
        index=pd.Index(["005930", "000660"], name="티커"),
    )
    return df


def _fake_cap() -> pd.DataFrame:
    return pd.DataFrame(
        {"시가총액": [468_500_000_000_000, 178_300_000_000_000]},
        index=pd.Index(["005930", "000660"], name="티커"),
    )


def _fake_short() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "종목명": ["삼성전자"],
            "공매도": [1_234_567],
            "거래량": [15_234_567],
            "공매도거래대금": [98_765_432_100],
            "비중": [8.1],
        },
        index=pd.Index(["005930"], name="티커"),
    )


@pytest.mark.asyncio
async def test_fetch_stock_prices_joins_ohlcv_and_market_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    from pykrx import stock as pykrx_stock

    monkeypatch.setattr(pykrx_stock, "get_market_ohlcv_by_ticker", lambda *a, **k: _fake_ohlcv())
    monkeypatch.setattr(pykrx_stock, "get_market_cap_by_ticker", lambda *a, **k: _fake_cap())

    client = _make_client()
    rows = await client.fetch_stock_prices(date(2026, 4, 17))

    assert len(rows) == 2
    first = next(r for r in rows if r.stock_code == "005930")
    assert first.stock_name == "삼성전자"
    assert first.market_type == "KOSPI"
    assert first.close_price == 78_500
    assert first.market_cap == 468_500_000_000_000
    assert first.change_rate == Decimal("0.64")


@pytest.mark.asyncio
async def test_fetch_stock_prices_uses_ohlcv_inline_market_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pykrx 1.2.x: get_market_ohlcv_by_ticker 가 시가총액을 직접 반환.

    이 경우 get_market_cap_by_ticker 를 호출하면 '시가총액' 컬럼 충돌로
    pandas join 이 ValueError 를 던진다. 어댑터는 ohlcv 에 이미 컬럼이
    있으면 별도 조회를 건너뛰어야 한다.
    """
    from pykrx import stock as pykrx_stock

    # ohlcv 에 시가총액이 포함된 신버전 스키마
    ohlcv = _fake_ohlcv().assign(시가총액=[468_500_000_000_000, 178_300_000_000_000])
    called_cap = {"count": 0}

    def _cap(*_a: object, **_k: object) -> pd.DataFrame:
        called_cap["count"] += 1
        return _fake_cap()

    monkeypatch.setattr(pykrx_stock, "get_market_ohlcv_by_ticker", lambda *a, **k: ohlcv)
    monkeypatch.setattr(pykrx_stock, "get_market_cap_by_ticker", _cap)

    client = _make_client()
    rows = await client.fetch_stock_prices(date(2026, 4, 17))

    assert len(rows) == 2
    first = next(r for r in rows if r.stock_code == "005930")
    assert first.market_cap == 468_500_000_000_000
    # cap 조회는 호출되지 않아야 함
    assert called_cap["count"] == 0


@pytest.mark.asyncio
async def test_fetch_stock_prices_empty_dataframe(monkeypatch: pytest.MonkeyPatch) -> None:
    from pykrx import stock as pykrx_stock

    monkeypatch.setattr(pykrx_stock, "get_market_ohlcv_by_ticker", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(pykrx_stock, "get_market_cap_by_ticker", lambda *a, **k: pd.DataFrame())

    client = _make_client()
    rows = await client.fetch_stock_prices(date(2026, 4, 17))
    assert rows == []


@pytest.mark.asyncio
async def test_fetch_short_selling_calculates_ratio_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pykrx import stock as pykrx_stock

    # 비중 컬럼을 0으로 두면 short_volume/거래량 비율이 계산돼야 함
    df = _fake_short().copy()
    df["비중"] = 0.0
    monkeypatch.setattr(pykrx_stock, "get_shorting_volume_by_ticker", lambda *a, **k: df)

    client = _make_client()
    rows = await client.fetch_short_selling(date(2026, 4, 17))
    assert len(rows) == 1
    # 1234567 / 15234567 * 100 ≈ 8.10
    assert rows[0].short_ratio > Decimal("8.0")
    assert rows[0].short_ratio < Decimal("8.2")


@pytest.mark.asyncio
async def test_fetch_lending_balance_schema_mismatch_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pykrx import stock as pykrx_stock

    def _raise(*_: object, **__: object) -> pd.DataFrame:
        raise KeyError("None of [...] are in the [columns]")

    monkeypatch.setattr(pykrx_stock, "get_shorting_balance_by_ticker", _raise)

    client = _make_client()
    rows = await client.fetch_lending_balance(date(2026, 4, 17))
    # pykrx 스키마 불일치 시 예외 대신 빈 리스트 반환(UseCase 비차단)
    assert rows == []
