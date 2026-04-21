#!/usr/bin/env python3
"""원타임 복구: stock 테이블의 빈 stock_name 을 KRX 에서 일괄 복구.

배경:
- α 초기 수집부터 stock_name 이 거의 모두 공백 저장되어 있었음.
- get_market_ohlcv_by_ticker 는 종목명을 반환하지 않는다.
- get_market_price_change_by_ticker(from=to) 는 '종목명' 컬럼을 포함하므로
  1회 API 호출로 전종목 이름을 가져올 수 있다.

본 스크립트는 stock_name 이 NULL/빈 문자열인 레코드만 UPDATE (기존 값 보존).

사용:
  docker compose exec backend python -m scripts.fix_stock_names
  docker compose exec backend python -m scripts.fix_stock_names --date 2026-04-15
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date


async def run(target_date: date) -> int:
    from sqlalchemy import or_, select, update

    from app.adapter.out.external.krx_client import KrxClient
    from app.adapter.out.persistence.models import Stock
    from app.adapter.out.persistence.session import get_engine, get_sessionmaker

    client = KrxClient()
    date_str = target_date.strftime("%Y%m%d")
    name_map = await client.build_stock_name_map(date_str)
    if not name_map:
        print(f"[fix-names] KRX 종목명 맵이 비어있음 (date={target_date})", file=sys.stderr)
        return 1
    print(f"[fix-names] KRX 에서 {len(name_map)} 종목 이름 확보", flush=True)

    sessionmaker = get_sessionmaker()
    updated = 0
    async with sessionmaker() as session, session.begin():
        stmt = select(Stock).where(or_(Stock.stock_name.is_(None), Stock.stock_name == ""))
        rows = (await session.execute(stmt)).scalars().all()
        print(f"[fix-names] DB 에서 빈 이름 {len(rows)} 건 발견", flush=True)
        for r in rows:
            new_name = name_map.get(r.stock_code)
            if new_name:
                await session.execute(update(Stock).where(Stock.id == r.id).values(stock_name=new_name))
                updated += 1

    await get_engine().dispose()
    print(f"[fix-names] 완료 — {updated} 건 업데이트 (미매칭 {len(rows) - updated})", flush=True)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="stock 테이블의 빈 stock_name 일괄 복구")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="KRX 조회 기준일 YYYY-MM-DD (기본: 오늘)",
    )
    args = parser.parse_args()
    target = date.fromisoformat(args.date) if args.date else date.today()
    rc = asyncio.run(run(target))
    sys.exit(rc)


if __name__ == "__main__":
    main()
