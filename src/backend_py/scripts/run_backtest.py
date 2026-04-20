#!/usr/bin/env python3
"""백테스트 수동 실행 CLI.

app.batch.backtest_job.run_backtest_pipeline 를 직접 호출해
SignalType 별 적중률/평균수익을 재계산하고 backtest_result 에 append 한다.

사용:
  docker compose exec backend python -m scripts.run_backtest
  docker compose exec backend python -m scripts.run_backtest --years 1
  docker compose exec backend python -m scripts.run_backtest --from 2024-01-01 --to 2026-04-20

기본값: period_end=오늘(KST), years=Settings.backtest_period_years (기본 3).
--from/--to 를 명시하면 years 는 무시.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date


async def _run(
    *,
    period_start: date | None,
    period_end: date | None,
    years: int | None,
) -> int:
    from app.adapter.out.persistence.session import get_engine
    from app.batch.backtest_job import run_backtest_pipeline
    from app.config.settings import get_settings

    settings = get_settings()
    effective_years = years if years is not None else settings.backtest_period_years

    if period_start is not None and period_end is not None:
        # 명시 구간: run_backtest_pipeline 은 period_years 로만 계산하므로
        # 이 경우 BacktestEngineService 를 직접 호출하려 해도 좋지만,
        # 동일 경로 유지를 위해 years 를 역산해 사용.
        # 단순화: period_end 고정, years 는 필요 없음 → start 차이만큼의 years 는 정수가 아닐 수 있어
        # 래퍼를 쓰지 않고 엔진을 바로 호출한다.
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from app.adapter.out.persistence.session import get_sessionmaker
        from app.application.service import BacktestEngineService

        factory: async_sessionmaker[AsyncSession] = get_sessionmaker()
        async with factory() as session:
            execution = await BacktestEngineService(session).execute(period_start, period_end)
            await session.commit()
        print(
            f"[run-backtest] 완료 {period_start} ~ {period_end} "
            f"signals={execution.signals_processed} returns={execution.returns_calculated} "
            f"rows={execution.result_rows} elapsed={execution.elapsed_ms}ms",
            flush=True,
        )
        await get_engine().dispose()
        return 0

    effective_end = period_end or date.today()
    result = await run_backtest_pipeline(
        period_end=effective_end, period_years=effective_years
    )
    await get_engine().dispose()

    if not result.succeeded:
        print(
            f"[run-backtest] 실패 {result.period_start} ~ {result.period_end} — {result.error}",
            file=sys.stderr, flush=True,
        )
        return 1

    exe = result.execution
    assert exe is not None  # succeeded=True 면 항상 채워짐
    print(
        f"[run-backtest] 완료 {result.period_start} ~ {result.period_end} "
        f"signals={exe.signals_processed} returns={exe.returns_calculated} "
        f"rows={exe.result_rows} elapsed={result.elapsed_ms}ms",
        flush=True,
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="백테스트 수동 실행 — backtest_result 에 append",
    )
    parser.add_argument("--from", dest="period_from", type=str, default=None,
                        help="시작일 YYYY-MM-DD (기본: period_end - years)")
    parser.add_argument("--to", dest="period_to", type=str, default=None,
                        help="종료일 YYYY-MM-DD (기본: 오늘)")
    parser.add_argument("--years", type=int, default=None,
                        help="직전 N년 (기본: Settings.backtest_period_years). --from 지정 시 무시")
    args = parser.parse_args()

    period_from = date.fromisoformat(args.period_from) if args.period_from else None
    period_to = date.fromisoformat(args.period_to) if args.period_to else None

    if (period_from is None) ^ (period_to is None):
        parser.error("--from / --to 는 둘 다 명시하거나 둘 다 생략해야 합니다")

    rc = asyncio.run(_run(
        period_start=period_from, period_end=period_to, years=args.years,
    ))
    sys.exit(rc)


if __name__ == "__main__":
    main()
