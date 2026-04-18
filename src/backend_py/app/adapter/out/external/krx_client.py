"""KRX 공개 데이터 수집 어댑터 (pykrx 기반).

배경:
- KRX 정보데이터시스템은 2026년 초 익명 접근을 차단했다.
- 인증 경로는 data.krx.co.kr 회원 ID/PW 세션이며, pykrx 라이브러리가 이 흐름을 래핑한다.
- pykrx 는 동기 API → asyncio.to_thread 로 감싸서 FastAPI async 핸들러와 배치 잡에서 재사용.

설계 포인트:
- 요청 간 최소 간격(rate limit) 을 프로세스 전역 락으로 강제해 IP 차단을 예방.
- pykrx 의 내부 print/logging 은 stdout 으로 ID 를 노출하므로 stdout/stderr 을 캡처해 버린다.
- 대차잔고(get_shorting_balance_by_ticker)는 현재 pykrx 스키마 불일치 이슈가 있어
  실패 시 빈 리스트 + 경고 로그만 남기고 UseCase 가 나머지 스텝을 진행할 수 있게 한다.
"""
from __future__ import annotations

import asyncio
import contextlib
import io
import logging
import os
import time
from datetime import date
from decimal import Decimal
from typing import Any

import pandas as pd
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.adapter.out.external._records import (
    LendingBalanceRow,
    ShortSellingRow,
    StockPriceRow,
)
from app.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def _dec(val: Any) -> Decimal:
    """pykrx 가 반환하는 float/str/NaN 을 Decimal 로 안전 변환."""
    if val is None:
        return Decimal(0)
    s = str(val).strip().replace(",", "")
    if not s or s.lower() in ("nan", "none", "-"):
        return Decimal(0)
    try:
        return Decimal(s)
    except Exception:
        return Decimal(0)


def _int(val: Any) -> int:
    return int(_dec(val))


class KrxClient:
    """pykrx 를 async 어댑터로 감싼 클라이언트. 프로세스당 1 인스턴스 권장."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._lock = asyncio.Lock()
        self._min_interval = self._settings.krx_request_interval_seconds
        self._last_call_ts: float = 0.0
        # pykrx 는 환경변수로 자격증명을 읽음 — 우리 Settings 값으로 주입해 일원화
        if self._settings.krx_id and not os.environ.get("KRX_ID"):
            os.environ["KRX_ID"] = self._settings.krx_id
        if self._settings.krx_pw and not os.environ.get("KRX_PW"):
            os.environ["KRX_PW"] = self._settings.krx_pw

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_stock_prices(self, trading_date: date) -> list[StockPriceRow]:
        """전 종목 OHLCV + 시가총액을 합쳐 반환.

        pykrx 1.2.x 부터 `get_market_ohlcv_by_ticker` 가 '시가총액' 을 직접 반환하므로,
        `get_market_cap_by_ticker` 로 별도 조회할 필요는 없다. 구버전 호환을 위해
        ohlcv 에 컬럼이 없을 때만 cap 조회로 보강.
        """
        date_str = trading_date.strftime("%Y%m%d")
        # market="ALL" 은 KOSPI+KOSDAQ+KONEX 합집합을 한 번에 반환한다. 기본값은 "KOSPI"
        # 이라 생략하면 KOSDAQ 누락. 시장구분 컬럼이 자동으로 채워져 _to_stock_price_row
        # 의 market_type 매핑이 그대로 동작.
        ohlcv = await self._call_pykrx("get_market_ohlcv_by_ticker", date_str, market="ALL")
        if ohlcv is None or ohlcv.empty:
            return []
        if "시가총액" not in ohlcv.columns:
            cap = await self._call_pykrx(
                "get_market_cap_by_ticker", date_str, market="ALL"
            )
            if cap is not None and not cap.empty and "시가총액" in cap.columns:
                ohlcv = ohlcv.join(cap[["시가총액"]], how="left")
        # pandas Index 는 Hashable — pykrx 는 항상 종목코드 str 이지만 정적으로는 narrow.
        return [self._to_stock_price_row(str(code), row) for code, row in ohlcv.iterrows()]

    async def fetch_short_selling(self, trading_date: date) -> list[ShortSellingRow]:
        """전 종목 공매도 거래 현황."""
        date_str = trading_date.strftime("%Y%m%d")
        df = await self._call_pykrx("get_shorting_volume_by_ticker", date_str)
        if df is None or df.empty:
            return []
        return [self._to_short_selling_row(str(code), row) for code, row in df.iterrows()]

    async def fetch_lending_balance(self, trading_date: date) -> list[LendingBalanceRow]:
        """전 종목 대차잔고. pykrx 현재 버전에 스키마 불일치 이슈가 있어 실패 시 빈 리스트."""
        date_str = trading_date.strftime("%Y%m%d")
        try:
            df = await self._call_pykrx("get_shorting_balance_by_ticker", date_str)
        except Exception as e:  # noqa: BLE001 — 의도적으로 광범위 캐치
            logger.warning("KRX 대차잔고 수집 실패(%s): %s", type(e).__name__, e)
            return []
        if df is None or df.empty:
            logger.warning("KRX 대차잔고 응답이 비어 있음 (trading_date=%s)", date_str)
            return []
        return [self._to_lending_balance_row(str(code), row) for code, row in df.iterrows()]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
    )
    async def _call_pykrx(self, func_name: str, *args: Any, **kwargs: Any) -> pd.DataFrame | None:
        """pykrx 함수 호출을 rate-limit + stdout 차폐 + 재시도로 감싼다."""
        async with self._lock:
            await self._throttle()
            return await asyncio.to_thread(self._invoke_silent, func_name, *args, **kwargs)

    @staticmethod
    def _invoke_silent(func_name: str, *args: Any, **kwargs: Any) -> pd.DataFrame | None:
        """pykrx 내부 print 를 버퍼로 가두고 함수 호출."""
        from pykrx import stock  # 지연 임포트 — 테스트 시 monkeypatch 용이

        fn = getattr(stock, func_name)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            result: pd.DataFrame | None = fn(*args, **kwargs)
            return result

    async def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call_ts
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_call_ts = time.monotonic()

    # ------------------------------------------------------------------
    # DataFrame → 값 객체 매핑 (pykrx 한국어 컬럼 → 영문 필드)
    # ------------------------------------------------------------------

    @staticmethod
    def _to_stock_price_row(code: str, row: Any) -> StockPriceRow:
        return StockPriceRow(
            stock_code=str(code),
            stock_name=str(row.get("종목명", "")),
            market_type=str(row.get("시장구분", "KOSPI")),
            close_price=_int(row.get("종가")),
            open_price=_int(row.get("시가")),
            high_price=_int(row.get("고가")),
            low_price=_int(row.get("저가")),
            volume=_int(row.get("거래량")),
            market_cap=_int(row.get("시가총액")),
            change_rate=_dec(row.get("등락률")),
        )

    @staticmethod
    def _to_short_selling_row(code: str, row: Any) -> ShortSellingRow:
        # pykrx 컬럼명: '공매도', '거래량', '비중' — 버전에 따라 다르므로 방어적으로 조회
        short_vol = row.get("공매도", row.get("공매도거래량", 0))
        total_vol = row.get("거래량", 0)
        short_amt = row.get("공매도거래대금", row.get("거래대금", 0))
        ratio = row.get("비중", row.get("공매도비중", 0))
        if (not ratio or _dec(ratio) == 0) and _int(total_vol) > 0:
            ratio = (_dec(short_vol) / _dec(total_vol)) * Decimal(100)
        return ShortSellingRow(
            stock_code=str(code),
            stock_name=str(row.get("종목명", "")),
            short_volume=_int(short_vol),
            short_amount=_int(short_amt),
            short_ratio=_dec(ratio),
        )

    @staticmethod
    def _to_lending_balance_row(code: str, row: Any) -> LendingBalanceRow:
        return LendingBalanceRow(
            stock_code=str(code),
            stock_name=str(row.get("종목명", "")),
            balance_quantity=_int(row.get("잔고수량", row.get("BAL_QTY", 0))),
            balance_amount=_int(row.get("잔고금액", row.get("BAL_AMT", 0))),
        )
