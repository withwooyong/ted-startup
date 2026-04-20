"""백테스트 — vectorbt + pandas 벡터 연산 기반 전면 리라이트.

Java 버전(BacktestEngineService)은 TreeMap 순회로 각 시그널마다 N영업일 후 종가를
개별 lookup 했다. Python 버전은:

1. price_panel: (stock_id, trading_date) → close_price 를 와이드 피벗 테이블로 구성
2. 각 보유일(N=5/10/20)에 대해 pct_change(N) 을 한 번에 계산한 수익률 DataFrame 생성
3. 시그널 발생일 × stock_id 교차점에서 벡터 lookup

vectorbt 는 Portfolio.from_signals 도 지원하지만 본 도메인은 "개별 시그널의 고정 보유기간
수익률"이라 pandas shift/pct_change 로 충분하다. vectorbt 는 적중률/평균수익 집계에
동일하게 제공하는 통계 편의 기능을 위해 도입해 두고, 이후 Sharpe·MDD 등 확장 시 활용한다.
"""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import BacktestResult, SignalType
from app.adapter.out.persistence.repositories import (
    BacktestResultRepository,
    SignalRepository,
    StockPriceRepository,
)
from app.application.dto.results import BacktestExecutionResult

logger = logging.getLogger(__name__)

HOLDING_PERIODS = (5, 10, 20)
FUTURE_BUFFER_DAYS = 40  # 영업일 20일 ≈ 달력일 30일 + 여유


def _dec(val: float | None, places: int = 4) -> Decimal | None:
    if val is None or pd.isna(val):
        return None
    return Decimal(str(round(float(val), places)))


class BacktestEngineService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, period_start: date, period_end: date) -> BacktestExecutionResult:
        start = time.monotonic()
        logger.info("백테스팅 시작 %s ~ %s", period_start, period_end)

        signal_repo = SignalRepository(self._session)
        price_repo = StockPriceRepository(self._session)
        result_repo = BacktestResultRepository(self._session)

        signals = list(await signal_repo.list_between(period_start, period_end))
        if not signals:
            elapsed = int((time.monotonic() - start) * 1000)
            return BacktestExecutionResult(
                signals_processed=0, returns_calculated=0, result_rows=0, elapsed_ms=elapsed
            )

        # 1. 시세 벌크 로드 → 피벗 테이블 (index=trading_date, columns=stock_id, values=close_price)
        stock_ids = sorted({s.stock_id for s in signals})
        price_from = min(s.signal_date for s in signals)
        price_to = max(s.signal_date for s in signals) + timedelta(days=FUTURE_BUFFER_DAYS)
        prices = await price_repo.list_by_stocks_between(stock_ids, price_from, price_to)
        if not prices:
            logger.warning("백테스트 구간 내 주가 데이터 없음")
            elapsed = int((time.monotonic() - start) * 1000)
            return BacktestExecutionResult(
                signals_processed=len(signals), returns_calculated=0, result_rows=0,
                elapsed_ms=elapsed,
            )

        price_df = pd.DataFrame(
            [
                {"stock_id": p.stock_id, "date": p.trading_date, "close": int(p.close_price)}
                for p in prices
            ]
        )
        price_wide = price_df.pivot(index="date", columns="stock_id", values="close").sort_index()
        # 모든 거래일이 인덱스 — 영업일 단위 shift 계산(행 기준)이 그대로 "N영업일 후"
        price_wide = price_wide.astype("float64")
        # 분모(기준일 가격)만 NaN 마스킹. 상장폐지/거래정지 종목은 일부 날짜에 close_price=0 인데
        # 기준일이 0 이면 (future/0-1)=Infinity 가 퍼져 INSERT 시 NumericValueOutOfRangeError 발생.
        # 분자는 마스킹하지 않음 — 미래 시점에 0 이 되면 (0/base-1)=-100% 라는 유효한 전손 수익률이
        # 그대로 기록돼야 집계가 왜곡되지 않는다.
        price_base = price_wide.where(price_wide > 0)

        # 2. N-영업일 후 종가 (price_wide.shift(-N)) → 수익률 = (future/base - 1) * 100
        returns: dict[int, pd.DataFrame] = {
            n: (price_wide.shift(-n) / price_base - 1.0) * 100.0 for n in HOLDING_PERIODS
        }
        # inf/-inf → NaN 필수 치환. 아래 집계 경로(`series.dropna().mean()`)는 NaN 만 제거하고
        # inf 는 남긴다 — 단일 inf 가 평균을 Decimal('Infinity') 로 만들어 DB INSERT 가 실패.
        returns = {n: df.where(np.isfinite(df)) for n, df in returns.items()}

        # 3. 시그널 발생일 × stock_id 교차점 벡터 lookup → 각 시그널의 수익률 기록
        returns_calculated = 0
        for sig in signals:
            r_by_n: dict[int, Decimal | None] = {}
            for n, rdf in returns.items():
                if sig.signal_date in rdf.index and sig.stock_id in rdf.columns:
                    val = rdf.at[sig.signal_date, sig.stock_id]
                    # rdf.at 반환 타입은 pandas-stubs 상 union 이 매우 넓음. 수치가 아니면 None.
                    if val is None or pd.isna(val):
                        r_by_n[n] = None
                    else:
                        r_by_n[n] = _dec(float(val))  # type: ignore[arg-type]
                else:
                    r_by_n[n] = None
            sig.return_5d = r_by_n[5]
            sig.return_10d = r_by_n[10]
            sig.return_20d = r_by_n[20]
            if any(v is not None for v in r_by_n.values()):
                returns_calculated += 1

        # 4. SignalType 별 집계 (vectorbt/pandas 벡터 연산)
        agg_results: list[BacktestResult] = []
        df = pd.DataFrame(
            [
                {
                    "signal_type": s.signal_type,
                    "r5": float(s.return_5d) if s.return_5d is not None else np.nan,
                    "r10": float(s.return_10d) if s.return_10d is not None else np.nan,
                    "r20": float(s.return_20d) if s.return_20d is not None else np.nan,
                }
                for s in signals
            ]
        )
        for sig_type in SignalType:
            sub = df[df["signal_type"] == sig_type.value]
            if sub.empty:
                continue
            total = len(sub)
            res = BacktestResult(
                signal_type=sig_type.value,
                period_start=period_start,
                period_end=period_end,
                total_signals=total,
            )
            for n, col in ((5, "r5"), (10, "r10"), (20, "r20")):
                series = sub[col].dropna()
                observed = len(series)
                hits = int((series > 0).sum()) if observed > 0 else 0
                hit_rate = (hits / observed * 100.0) if observed > 0 else 0.0
                avg_ret = float(series.mean()) if observed > 0 else 0.0
                setattr(res, f"hit_count_{n}d", hits)
                setattr(res, f"hit_rate_{n}d", _dec(hit_rate) or Decimal("0"))
                setattr(res, f"avg_return_{n}d", _dec(avg_ret) or Decimal("0"))
            agg_results.append(res)
            logger.info(
                "집계 %s: total=%d hit5=%s%% hit10=%s%% hit20=%s%%",
                sig_type.value, total, res.hit_rate_5d, res.hit_rate_10d, res.hit_rate_20d,
            )

        await result_repo.add_many(agg_results)
        await self._session.flush()

        elapsed = int((time.monotonic() - start) * 1000)
        logger.info(
            "백테스팅 완료 signals=%d returns=%d results=%d elapsed=%dms",
            len(signals), returns_calculated, len(agg_results), elapsed,
        )
        return BacktestExecutionResult(
            signals_processed=len(signals),
            returns_calculated=returns_calculated,
            result_rows=len(agg_results),
            elapsed_ms=elapsed,
        )
