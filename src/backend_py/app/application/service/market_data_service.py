"""KRX 데이터 수집 + 영속화 오케스트레이터.

Phase 1: HTTP 수집(어댑터) — 트랜잭션 밖
Phase 2: DB upsert — 호출자가 세션 트랜잭션을 관리(Hexagonal: 서비스는 경계 밖 트랜잭션)
"""
from __future__ import annotations

import logging
import time
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.external import KrxClient
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
        logger.info(
            "KRX 수신: prices=%d short=%d lending=%d", len(prices), len(shorts), len(lendings)
        )

        # 1) 종목 마스터 upsert — 이후 단계의 stock_id 매핑 확보
        stock_repo = StockRepository(self._session)
        code_to_id: dict[str, int] = {}
        stocks_upserted = 0
        for row in prices:
            stock = await stock_repo.upsert_by_code(
                row.stock_code, row.stock_name, row.market_type
            )
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

        # 대차잔고 upsert
        lending_repo = LendingBalanceRepository(self._session)
        lending_rows = [
            {
                "stock_id": code_to_id[lb.stock_code],
                "trading_date": trading_date,
                "balance_quantity": lb.balance_quantity,
                "balance_amount": lb.balance_amount,
            }
            for lb in lendings
            if lb.stock_code in code_to_id
        ]
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
