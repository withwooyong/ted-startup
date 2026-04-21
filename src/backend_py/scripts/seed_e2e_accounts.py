#!/usr/bin/env python3
"""E2E 테스트용 계좌·보유·거래 시드 — 운영 데이터 아님.

E2E 스펙이 기대하는 고정 상태:
  - brokerage_account: e2e-manual(id 낮음, manual/mock), e2e-kis(kis_rest_mock/mock)
  - portfolio_holding: e2e-manual 에 005930(삼성전자) 10주 @ 72,000
  - portfolio_transaction: 대응 BUY 거래 1건 (2026-04-01, memo="E2E")

seed_ui_demo.py 는 stock/stock_price/snapshot 만 다루므로,
CI 에서 E2E 가 요구하는 계좌·보유·거래는 이 스크립트로 별도 시드한다.

멱등: 동일 alias 계좌 존재 시 skip, 동일 holding 존재 시 skip.

사용:
  docker compose exec backend python -m scripts.seed_e2e_accounts
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from decimal import Decimal


async def run() -> int:
    from sqlalchemy import select

    from app.adapter.out.persistence.models import (
        BrokerageAccount,
        PortfolioHolding,
        PortfolioTransaction,
        Stock,
    )
    from app.adapter.out.persistence.session import get_engine, get_sessionmaker

    sm = get_sessionmaker()
    created_accounts = 0
    created_holdings = 0
    created_tx = 0

    async with sm() as session, session.begin():
        # 계좌 2개 — alias 로 멱등 체크
        wanted = [
            ("e2e-manual", "manual", "manual", "mock"),
            ("e2e-kis", "kis", "kis_rest_mock", "mock"),
        ]
        alias_to_id: dict[str, int] = {}
        for alias, broker, conn_type, env in wanted:
            existing = (
                await session.execute(select(BrokerageAccount).where(BrokerageAccount.account_alias == alias))
            ).scalar_one_or_none()
            if existing is None:
                acc = BrokerageAccount(
                    account_alias=alias,
                    broker_code=broker,
                    connection_type=conn_type,
                    environment=env,
                    is_active=True,
                )
                session.add(acc)
                await session.flush()
                alias_to_id[alias] = acc.id
                created_accounts += 1
            else:
                alias_to_id[alias] = existing.id

        # 삼성전자 holding — stock_code 로 stock 조회 후 holding 삽입
        samsung = (await session.execute(select(Stock).where(Stock.stock_code == "005930"))).scalar_one_or_none()
        if samsung is None:
            print(
                "[seed-e2e] 경고: 005930(삼성전자) stock 미존재 → "
                "보유·거래 시드 모두 skip. seed_ui_demo 또는 backfill 선행 필요.",
                file=sys.stderr,
                flush=True,
            )
        else:
            manual_id = alias_to_id["e2e-manual"]
            existing_h = (
                await session.execute(
                    select(PortfolioHolding).where(
                        PortfolioHolding.account_id == manual_id,
                        PortfolioHolding.stock_id == samsung.id,
                    )
                )
            ).scalar_one_or_none()
            if existing_h is None:
                session.add(
                    PortfolioHolding(
                        account_id=manual_id,
                        stock_id=samsung.id,
                        quantity=10,
                        avg_buy_price=Decimal("72000.00"),
                        first_bought_at=date(2026, 4, 1),
                        last_transacted_at=date(2026, 4, 1),
                    )
                )
                created_holdings += 1

            existing_tx = (
                await session.execute(
                    select(PortfolioTransaction).where(
                        PortfolioTransaction.account_id == manual_id,
                        PortfolioTransaction.stock_id == samsung.id,
                        PortfolioTransaction.memo == "E2E",
                    )
                )
            ).scalar_one_or_none()
            if existing_tx is None:
                session.add(
                    PortfolioTransaction(
                        account_id=manual_id,
                        stock_id=samsung.id,
                        transaction_type="BUY",
                        quantity=10,
                        price=Decimal("72000.00"),
                        executed_at=date(2026, 4, 1),
                        source="manual",
                        memo="E2E",
                    )
                )
                created_tx += 1

    await get_engine().dispose()
    print(
        f"[seed-e2e] 완료 — 계좌 +{created_accounts} · 보유 +{created_holdings} · 거래 +{created_tx}",
        flush=True,
    )
    return 0


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
