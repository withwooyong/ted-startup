"""KRX 데이터 수집 + 영속화 오케스트레이터.

Phase 1: HTTP 수집(어댑터) — 트랜잭션 밖
Phase 2: DB upsert — 호출자가 세션 트랜잭션을 관리(Hexagonal: 서비스는 경계 밖 트랜잭션)
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.external import KrxClient
from app.adapter.out.persistence.models import LendingBalance
from app.adapter.out.persistence.repositories import (
    LendingBalanceRepository,
    ShortSellingRepository,
    StockPriceRepository,
    StockRepository,
)
from app.application.dto.results import CollectionResult

logger = logging.getLogger(__name__)


class MarketDataCollectionService:
    def __init__(self, krx_client: KrxClient, session: AsyncSession) -> None:
        self._krx = krx_client
        self._session = session

    async def collect_all(self, trading_date: date) -> CollectionResult:
        start = time.monotonic()
        logger.info("KRX 수집 시작 date=%s", trading_date)

        prices = await self._krx.fetch_stock_prices(trading_date)
        shorts = await self._krx.fetch_short_selling(trading_date)
        lendings = await self._krx.fetch_lending_balance(trading_date)
        logger.info("KRX 수신: prices=%d short=%d lending=%d", len(prices), len(shorts), len(lendings))

        # 1) 종목 마스터 upsert — 이후 단계의 stock_id 매핑 확보
        stock_repo = StockRepository(self._session)
        code_to_id: dict[str, int] = {}
        stocks_upserted = 0
        for row in prices:
            stock = await stock_repo.upsert_by_code(row.stock_code, row.stock_name, row.market_type)
            code_to_id[row.stock_code] = stock.id
            stocks_upserted += 1

        # 시가총액·시세 upsert
        price_repo = StockPriceRepository(self._session)
        price_rows = [
            {
                "stock_id": code_to_id[p.stock_code],
                "trading_date": trading_date,
                "close_price": p.close_price,
                "open_price": p.open_price,
                "high_price": p.high_price,
                "low_price": p.low_price,
                "volume": p.volume,
                "market_cap": p.market_cap,
                "change_rate": p.change_rate,
            }
            for p in prices
            if p.stock_code in code_to_id
        ]
        stock_prices_n = await price_repo.upsert_many(price_rows)

        # 공매도 upsert (종목 마스터에 없는 코드는 skip)
        short_repo = ShortSellingRepository(self._session)
        short_rows = [
            {
                "stock_id": code_to_id[s.stock_code],
                "trading_date": trading_date,
                "short_volume": s.short_volume,
                "short_amount": s.short_amount,
                "short_ratio": s.short_ratio,
            }
            for s in shorts
            if s.stock_code in code_to_id
        ]
        shorts_n = await short_repo.upsert_many(short_rows)

        # 대차잔고 upsert (전일 대비 변동률·연속 감소일수 계산)
        lending_repo = LendingBalanceRepository(self._session)
        prev_by_stock = await _fetch_prev_lending(lending_repo, trading_date)
        lending_rows = []
        for lb in lendings:
            if lb.stock_code not in code_to_id:
                continue
            sid = code_to_id[lb.stock_code]
            change_q, change_r, consec = _compute_lending_deltas(
                today_qty=lb.balance_quantity, prev=prev_by_stock.get(sid)
            )
            lending_rows.append(
                {
                    "stock_id": sid,
                    "trading_date": trading_date,
                    "balance_quantity": lb.balance_quantity,
                    "balance_amount": lb.balance_amount,
                    "change_quantity": change_q,
                    "change_rate": change_r,
                    "consecutive_decrease_days": consec,
                }
            )
        lendings_n = await lending_repo.upsert_many(lending_rows)

        elapsed = int((time.monotonic() - start) * 1000)
        logger.info(
            "KRX 수집 완료 stocks=%d prices=%d short=%d lending=%d elapsed=%dms",
            stocks_upserted,
            stock_prices_n,
            shorts_n,
            lendings_n,
            elapsed,
        )
        return CollectionResult(
            stocks_upserted=stocks_upserted,
            stock_prices_upserted=stock_prices_n,
            short_selling_upserted=shorts_n,
            lending_balance_upserted=lendings_n,
            elapsed_ms=elapsed,
        )


async def _fetch_prev_lending(repo: LendingBalanceRepository, trading_date: date) -> dict[int, LendingBalance]:
    """직전 영업일의 대차잔고를 stock_id 기준 dict 로 반환.

    주말·공휴일 대응을 위해 최대 5일 전까지 역방향 스캔한다 (주말 포함 최대 3일).
    모듈 레벨 함수 — 외부 repo 의존만 있고 서비스 상태는 쓰지 않음.
    """
    for delta in range(1, 6):
        cand = trading_date - timedelta(days=delta)
        rows = await repo.list_by_trading_date(cand)
        if rows:
            return {r.stock_id: r for r in rows}
    return {}


def _compute_lending_deltas(*, today_qty: int, prev: LendingBalance | None) -> tuple[int | None, Decimal | None, int]:
    """오늘 잔고수량 vs 전일 행 → (change_quantity, change_rate, consecutive_decrease_days).

    - 전일이 없으면 (None, None, 0): 최초 수집일 또는 장기 결측 후 복귀
    - 전일 balance_quantity 가 0 이면 change_rate 는 None (0 으로 나눌 수 없음)
    - change_quantity < 0 일 때만 consecutive_decrease_days += 1, 아니면 0 으로 리셋 (Java 원본 일치)
    """
    if prev is None:
        return None, None, 0
    prev_qty = int(prev.balance_quantity)
    change_q = today_qty - prev_qty
    change_r: Decimal | None
    if prev_qty > 0:
        change_r = (Decimal(change_q) / Decimal(prev_qty) * Decimal(100)).quantize(Decimal("0.0001"))
    else:
        change_r = None
    prev_consec = int(prev.consecutive_decrease_days or 0)
    consec = prev_consec + 1 if change_q < 0 else 0
    return change_q, change_r, consec
