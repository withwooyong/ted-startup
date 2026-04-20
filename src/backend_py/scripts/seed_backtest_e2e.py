#!/usr/bin/env python3
"""E2E 용 시그널 3건 시드 + 백테스트 1회 실행 — 운영 데이터 아님.

목적:
  - CI E2E 에서 /backtest 페이지가 **실데이터** 로 렌더되게 만든다.
  - H3/H4 는 여전히 stub 경로(future-proof) 이지만, H5 는 이 시드를 전제로 한다.

전제:
  - seed_ui_demo 가 선행돼 005930(삼성전자) stock 과 90 영업일치 stock_price 존재.
  - 없으면 시그널 insert 는 skip 하고 경고만 출력 → backtest 도 빈 결과.

수행 내용:
  1) SignalType 3종(RAPID_DECLINE, TREND_REVERSAL, SHORT_SQUEEZE) × 삼성전자 기준 시그널 1건씩 insert.
     signal_date 는 stock_price 최신 trading_date - 30 영업일(대략) 로 잡아 5/10/20일 후 가격 커버.
     (stock_id, signal_date, signal_type) 중복 시 skip(멱등).
  2) run_backtest_pipeline(period_years=1) 호출 → backtest_result 에 SignalType 별 1행 append.

사용:
  docker compose exec backend python -m scripts.seed_backtest_e2e
"""
from __future__ import annotations

import asyncio
import sys
from datetime import date


async def run() -> int:
    from sqlalchemy import select

    from app.adapter.out.persistence.models import Signal, SignalType, Stock, StockPrice
    from app.adapter.out.persistence.session import get_engine, get_sessionmaker
    from app.batch.backtest_job import run_backtest_pipeline

    sm = get_sessionmaker()

    seeded = 0
    signal_date: date | None = None
    period_end: date | None = None

    async with sm() as session, session.begin():
        samsung = (await session.execute(
            select(Stock).where(Stock.stock_code == "005930")
        )).scalar_one_or_none()
        if samsung is None:
            print(
                "[seed-backtest] 경고: 005930 stock 미존재 → 시그널 시드 skip. "
                "seed_ui_demo 선행 필요.",
                file=sys.stderr, flush=True,
            )
            return 0

        # 최신/최저 trading_date 구간 확인 — seed_ui_demo 가 90 영업일 생성했다고 가정.
        dates = (await session.execute(
            select(StockPrice.trading_date)
            .where(StockPrice.stock_id == samsung.id)
            .order_by(StockPrice.trading_date)
        )).scalars().all()
        if len(dates) < 40:
            print(
                f"[seed-backtest] 경고: 005930 stock_price {len(dates)}건 < 40 → "
                "5/10/20일 커버 부족. 그대로 진행하되 수익률은 일부 누락 가능.",
                flush=True,
            )
        if not dates:
            return 0

        # signal_date: 최신일 기준 30 영업일 이전(리스트 끝에서 30번째). 부족하면 첫날.
        signal_date = dates[-30] if len(dates) >= 30 else dates[0]
        period_end = dates[-1]

        for sig_type in (
            SignalType.RAPID_DECLINE,
            SignalType.TREND_REVERSAL,
            SignalType.SHORT_SQUEEZE,
        ):
            existing = (await session.execute(
                select(Signal).where(
                    Signal.stock_id == samsung.id,
                    Signal.signal_date == signal_date,
                    Signal.signal_type == sig_type.value,
                )
            )).scalar_one_or_none()
            if existing is not None:
                continue
            session.add(Signal(
                stock_id=samsung.id,
                signal_date=signal_date,
                signal_type=sig_type.value,
                score=80, grade="A",
                detail={"seed": "e2e"},
            ))
            seeded += 1

    print(
        f"[seed-backtest] 시그널 시드 완료 — +{seeded}건 (signal_date={signal_date})",
        flush=True,
    )

    # 백테스트 실행 — period_end 는 stock_price 최신일, 1년 구간이면 signal 포함.
    # 엔진은 signal_date 주변 ±40 달력일 가격만 쓰므로 1년 구간 충분.
    assert period_end is not None
    result = await run_backtest_pipeline(period_end=period_end, period_years=1)
    await get_engine().dispose()

    if not result.succeeded:
        print(
            f"[seed-backtest] 백테스트 실패: {result.error}",
            file=sys.stderr, flush=True,
        )
        return 1

    exe = result.execution
    assert exe is not None
    print(
        f"[seed-backtest] 백테스트 완료 {result.period_start} ~ {result.period_end} "
        f"signals={exe.signals_processed} returns={exe.returns_calculated} "
        f"rows={exe.result_rows} elapsed={result.elapsed_ms}ms",
        flush=True,
    )
    return 0


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
