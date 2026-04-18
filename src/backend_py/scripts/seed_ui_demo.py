#!/usr/bin/env python3
"""UI 회귀 검증용 stock + stock_price 시드 — **운영 데이터 아님**.

KRX 익명 차단(2026-04 전면화) 때문에 프로덕션 경로로 stock 마스터와
stock_price 시계열을 채우지 못하는 상황에서, 포트폴리오 페이지의 파생
지표(누적 수익률 3M, MDD 3M) 와 AI 리포트 경로가 데이터가 있을 때
실제로 그려지는지 확인하기 위한 데모 시드.

특징
  - 대표 5개 종목(삼성전자/SK하이닉스/NAVER/카카오/셀트리온)을 `stock` 에 upsert
  - 최근 N 영업일치 OHLCV 를 결정론적 난수(seed 고정)로 생성해 `stock_price` 에 upsert
  - 활성 계좌 × 날짜별 `portfolio_snapshot` 생성 — 현재 보유수량 × 해당일 종가
    기반으로 total_value 재구성(보유 이력이 과거에도 유지됐다고 가정하는 허구 추정).
    이는 UI 의 수익률/MDD 카드가 **값이 있을 때** 그려지는지 확인하기 위한 용도.
  - 운영 배치(KRX sync)와 분리된 CLI 스크립트 — 의도적으로 실행하지 않으면 DB 에 영향 없음

주의: 시드된 주가와 스냅샷은 허구 수치입니다. 실투자 판단에 사용 금지.

사용 예:
  docker compose exec backend python -m scripts.seed_ui_demo
  docker compose exec backend python -m scripts.seed_ui_demo --days 60 --wipe
"""
from __future__ import annotations

import argparse
import asyncio
import random
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.adapter.out.persistence.models import (
    BrokerageAccount,
    PortfolioHolding,
    PortfolioSnapshot,
    Stock,
    StockPrice,
)
from app.adapter.out.persistence.repositories import (
    PortfolioSnapshotRepository,
    StockPriceRepository,
    StockRepository,
)
from app.config.settings import get_settings

# ---------------------------------------------------------------------------
# 데모 데이터 정의
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class DemoStock:
    stock_code: str
    stock_name: str
    market_type: str
    sector: str
    base_price: int  # 시작일 종가


DEMO_STOCKS: tuple[DemoStock, ...] = (
    DemoStock("005930", "삼성전자",   "KOSPI",  "반도체",   72_000),
    DemoStock("000660", "SK하이닉스", "KOSPI",  "반도체",  150_000),
    DemoStock("035420", "NAVER",      "KOSPI",  "인터넷",  205_000),
    DemoStock("035720", "카카오",     "KOSPI",  "인터넷",   55_000),
    DemoStock("068270", "셀트리온",   "KOSPI",  "바이오",  175_000),
)


# ---------------------------------------------------------------------------
# 가격 시계열 생성
# ---------------------------------------------------------------------------


def business_days_back(today: date, count: int) -> list[date]:
    """오늘(포함)에서 거꾸로 `count` 영업일을 오름차순으로 반환."""
    out: list[date] = []
    cur = today
    while len(out) < count:
        if cur.weekday() < 5:  # Mon..Fri
            out.append(cur)
        cur -= timedelta(days=1)
    return list(reversed(out))


def generate_price_series(
    stock: DemoStock, days: list[date], *, seed: int
) -> list[dict[str, object]]:
    """결정론적 random-walk 로 OHLCV 생성. stock_id 는 호출부에서 주입."""
    rng = random.Random(seed)
    close = stock.base_price
    rows: list[dict[str, object]] = []
    prev_close = close
    for d in days:
        # 일일 변동: 정규분포 근사(±2% 대부분, 드물게 ±5% 이벤트)
        drift = rng.gauss(mu=0.0005, sigma=0.015)
        if rng.random() < 0.05:
            drift *= 2.5  # 이벤트일
        close = max(1, int(prev_close * (1.0 + drift)))
        # 시가/고가/저가는 종가 주변 ±1% 변동
        open_ = int(prev_close * (1.0 + rng.gauss(0, 0.005)))
        high = max(open_, close, int(close * (1.0 + abs(rng.gauss(0, 0.006)))))
        low = min(open_, close, int(close * (1.0 - abs(rng.gauss(0, 0.006)))))
        volume = int(rng.uniform(1e6, 1e7))
        rows.append({
            "trading_date": d,
            "close_price": close,
            "open_price": open_,
            "high_price": high,
            "low_price": low,
            "volume": volume,
            "market_cap": close * volume * 10,  # 허구치
            "change_rate": Decimal(
                f"{((close - prev_close) / prev_close) * 100:.4f}"
            ) if prev_close else Decimal("0"),
        })
        prev_close = close
    return rows


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def run(*, days: int, wipe: bool, seed: int) -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    today = date.today()
    trading_days = business_days_back(today, days)
    print(
        f"[seed-ui] 대상 종목 {len(DEMO_STOCKS)}건 × {days} 영업일 "
        f"({trading_days[0]} ~ {trading_days[-1]})",
        flush=True,
    )

    stock_ids: dict[str, int] = {}
    total_prices = 0
    total_snapshots = 0
    try:
        async with factory() as session, session.begin():
            stock_repo = StockRepository(session)
            price_repo = StockPriceRepository(session)
            snapshot_repo = PortfolioSnapshotRepository(session)

            if wipe:
                # stock 자체는 portfolio_holding 이 참조하므로 삭제 금지.
                # stock_price 기간내 데이터와 portfolio_snapshot 기간내 데이터만 지우고,
                # stock 은 upsert 경로로 최신 메타 반영.
                demo_codes = [s.stock_code for s in DEMO_STOCKS]
                existing = (await session.execute(
                    select(Stock).where(Stock.stock_code.in_(demo_codes))
                )).scalars().all()
                existing_ids = [s.id for s in existing]
                if existing_ids:
                    await session.execute(
                        delete(StockPrice).where(
                            StockPrice.stock_id.in_(existing_ids),
                            StockPrice.trading_date >= trading_days[0],
                            StockPrice.trading_date <= trading_days[-1],
                        )
                    )
                await session.execute(
                    delete(PortfolioSnapshot).where(
                        PortfolioSnapshot.snapshot_date >= trading_days[0],
                        PortfolioSnapshot.snapshot_date <= trading_days[-1],
                    )
                )
                print(
                    "[seed-ui]   wipe: 기간 내 stock_price/portfolio_snapshot 삭제 "
                    "(stock 마스터는 holding 참조로 보존)",
                    flush=True,
                )

            # Stock upsert
            for s in DEMO_STOCKS:
                stock = await stock_repo.upsert_by_code(
                    stock_code=s.stock_code,
                    stock_name=s.stock_name,
                    market_type=s.market_type,
                )
                # sector 는 upsert_by_code 가 다루지 않으므로 직접 업데이트
                if stock.sector != s.sector:
                    stock.sector = s.sector
                    await session.flush()
                stock_ids[s.stock_code] = stock.id

            # StockPrice 일괄 upsert
            for s in DEMO_STOCKS:
                rows = generate_price_series(s, trading_days, seed=seed + hash(s.stock_code) % 1000)
                # stock_id 주입
                for r in rows:
                    r["stock_id"] = stock_ids[s.stock_code]
                n = await price_repo.upsert_many(rows)
                total_prices += n
                print(
                    f"[seed-ui]   {s.stock_code} {s.stock_name:<10} "
                    f"시작가 {s.base_price:>8,} → 최종 {rows[-1]['close_price']:>8,} "
                    f"(rows={n})",
                    flush=True,
                )
            # portfolio_snapshot 생성 — 활성 계좌의 현재 보유 × 날짜별 종가 로 total_value 재구성
            accounts = (await session.execute(
                select(BrokerageAccount).where(BrokerageAccount.is_active.is_(True))
            )).scalars().all()

            # 날짜별 stock_id → close_price 룩업 테이블
            price_by_date: dict[date, dict[int, int]] = {d: {} for d in trading_days}
            for s in DEMO_STOCKS:
                sid = stock_ids[s.stock_code]
                price_rows = await price_repo.list_between(
                    sid, trading_days[0], trading_days[-1]
                )
                for pr in price_rows:
                    price_by_date[pr.trading_date][sid] = pr.close_price

            for acc in accounts:
                holdings = (await session.execute(
                    select(PortfolioHolding).where(
                        PortfolioHolding.account_id == acc.id
                    )
                )).scalars().all()
                if not holdings:
                    continue
                total_cost_dec = sum(
                    (h.quantity * h.avg_buy_price for h in holdings), start=Decimal("0")
                )
                for d in trading_days:
                    closes = price_by_date[d]
                    # 보유 중 시드 주가가 없는 종목(=비-데모 종목)은 평단으로 대체
                    total_value_dec = sum(
                        (
                            Decimal(closes.get(h.stock_id, int(h.avg_buy_price))) * h.quantity
                            for h in holdings
                        ),
                        start=Decimal("0"),
                    )
                    snap = PortfolioSnapshot(
                        account_id=acc.id,
                        snapshot_date=d,
                        total_value=total_value_dec,
                        total_cost=total_cost_dec,
                        unrealized_pnl=total_value_dec - total_cost_dec,
                        realized_pnl=Decimal("0"),
                        holdings_count=len(holdings),
                    )
                    await snapshot_repo.upsert(snap)
                    total_snapshots += 1
                print(
                    f"[seed-ui]   계좌 {acc.id} ({acc.account_alias}): "
                    f"holdings={len(holdings)} · snapshots={len(trading_days)}",
                    flush=True,
                )
    finally:
        await engine.dispose()

    print(
        f"[seed-ui] 완료 — stock {len(DEMO_STOCKS)} · "
        f"stock_price {total_prices:,} · "
        f"portfolio_snapshot {total_snapshots:,}",
        flush=True,
    )
    print("[seed-ui] 주의: 시드된 주가·스냅샷은 허구 수치입니다. 투자 판단 금지.", flush=True)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="UI 회귀 검증용 stock + stock_price 데모 시드 (운영 데이터 아님)",
    )
    parser.add_argument(
        "--days", type=int, default=90,
        help="생성할 영업일 개수 (기본 90일)",
    )
    parser.add_argument(
        "--wipe", action="store_true",
        help="시드 전 데모 종목의 기존 stock/stock_price 를 먼저 삭제",
    )
    parser.add_argument(
        "--seed", type=int, default=20260419,
        help="난수 시드 — 결정론적 생성. 기본 2026-04-19 기반",
    )
    args = parser.parse_args()
    rc = asyncio.run(run(days=args.days, wipe=args.wipe, seed=args.seed))
    sys.exit(rc)


if __name__ == "__main__":
    main()
