"""3종 시그널 탐지 — Java 로직 1:1 포팅, pandas 벡터화.

- RAPID_DECLINE: 대차잔고 change_rate <= -12% → base(abs*2.5) + consec(*5) + 10, cap 100
- TREND_REVERSAL: 대차잔고 5MA vs 20MA 골든→데드 크로스 검출(어제 >= 오늘 <), score >= 50
- SHORT_SQUEEZE: balance+volume+price+short_ratio 부분점수 합이 60 이상

2026-04-20 임계값 튜닝: 3년 백필 결과(70,609건, hit_rate ~45%)에서 저등급 비중이 과도.
SHORT_SQUEEZE C-grade 81%, TREND_REVERSAL D-grade 22%, RAPID_DECLINE A-grade 62% —
각 타입별 기준치를 재정비해 상위 신호만 남도록 조정했다.
"""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import Signal, SignalGrade, SignalType
from app.adapter.out.persistence.repositories import (
    LendingBalanceRepository,
    ShortSellingRepository,
    SignalRepository,
    StockPriceRepository,
    StockRepository,
)
from app.application.dto.results import DetectionResult

logger = logging.getLogger(__name__)

RAPID_DECLINE_THRESHOLD = Decimal("-12.0")
TREND_MA_SHORT = 5
TREND_MA_LONG = 20
TREND_HISTORY_DAYS = TREND_MA_LONG + 10
TREND_REVERSAL_MIN_SCORE = 50
VOLUME_HISTORY_DAYS = 30
SHORT_SQUEEZE_MIN_SCORE = 60


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _grade(score: int) -> str:
    return SignalGrade.from_score(score).value


class SignalDetectionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def detect_all(self, trading_date: date) -> DetectionResult:
        start = time.monotonic()
        logger.info("시그널 탐지 시작 date=%s", trading_date)

        stock_repo = StockRepository(self._session)
        price_repo = StockPriceRepository(self._session)
        short_repo = ShortSellingRepository(self._session)
        lending_repo = LendingBalanceRepository(self._session)
        signal_repo = SignalRepository(self._session)

        stocks = list(await stock_repo.list_active())
        if not stocks:
            return DetectionResult(rapid_decline=0, trend_reversal=0, short_squeeze=0, elapsed_ms=0)

        stock_ids = [s.id for s in stocks]

        prices_today = await price_repo.list_by_trading_date(trading_date)
        shorts_today = await short_repo.list_by_trading_date(trading_date)
        lendings_today = await lending_repo.list_by_trading_date(trading_date)

        price_by_stock = {p.stock_id: p for p in prices_today}
        short_by_stock = {s.stock_id: s for s in shorts_today}
        lending_by_stock = {lb.stock_id: lb for lb in lendings_today}

        # 추세전환용 히스토리(lending_balance 수량)
        trend_from = trading_date - timedelta(days=TREND_HISTORY_DAYS)
        lending_hist = await lending_repo.list_by_stocks_between(
            stock_ids, trend_from, trading_date
        )
        trend_df = pd.DataFrame(
            [
                {"stock_id": lb.stock_id, "date": lb.trading_date, "qty": int(lb.balance_quantity)}
                for lb in lending_hist
            ]
        )

        # 숏스퀴즈용 볼륨 히스토리 (당일 제외)
        vol_from = trading_date - timedelta(days=VOLUME_HISTORY_DAYS)
        vol_hist = await price_repo.list_by_stocks_between(
            stock_ids, vol_from, trading_date - timedelta(days=1)
        )
        vol_df = pd.DataFrame(
            [{"stock_id": sp.stock_id, "volume": int(sp.volume)} for sp in vol_hist]
        )
        avg_volume_by_stock: dict[int, float] = {}
        if not vol_df.empty:
            # groupby().mean().to_dict() 는 Hashable/Any 키로 좁혀지지 않아 cast.
            raw_mean: dict[Any, Any] = vol_df.groupby("stock_id")["volume"].mean().to_dict()
            for k, v in raw_mean.items():
                avg_volume_by_stock[int(k)] = float(v)

        # 기존 시그널 중복 방지
        existing = await signal_repo.list_by_date(trading_date)
        existing_keys = {(s.stock_id, s.signal_type) for s in existing}

        to_save: list[Signal] = []

        for stock in stocks:
            sid = stock.id
            lb = lending_by_stock.get(sid)
            sp = price_by_stock.get(sid)
            ss = short_by_stock.get(sid)
            hist = trend_df[trend_df["stock_id"] == sid] if not trend_df.empty else None

            sig = self._rapid_decline(stock.id, trading_date, lb, existing_keys)
            if sig:
                to_save.append(sig)

            sig = self._trend_reversal(stock.id, trading_date, hist, existing_keys)
            if sig:
                to_save.append(sig)

            sig = self._short_squeeze(
                stock.id, trading_date, lb, sp, ss,
                avg_volume_by_stock.get(sid, 0.0), existing_keys,
            )
            if sig:
                to_save.append(sig)

        await signal_repo.add_many(to_save)

        rapid = sum(1 for s in to_save if s.signal_type == SignalType.RAPID_DECLINE.value)
        trend = sum(1 for s in to_save if s.signal_type == SignalType.TREND_REVERSAL.value)
        squeeze = sum(1 for s in to_save if s.signal_type == SignalType.SHORT_SQUEEZE.value)
        elapsed = int((time.monotonic() - start) * 1000)
        logger.info(
            "시그널 탐지 완료 rapid=%d trend=%d squeeze=%d elapsed=%dms",
            rapid, trend, squeeze, elapsed,
        )
        return DetectionResult(
            rapid_decline=rapid, trend_reversal=trend, short_squeeze=squeeze, elapsed_ms=elapsed
        )

    # ------------------------------------------------------------------
    # 개별 탐지 로직
    # ------------------------------------------------------------------

    @staticmethod
    def _rapid_decline(
        stock_id: int, trading_date: date, lb: Any, existing: set[tuple[int, str]]
    ) -> Signal | None:
        if lb is None or lb.change_rate is None:
            return None
        if Decimal(lb.change_rate) > RAPID_DECLINE_THRESHOLD:
            return None
        key = (stock_id, SignalType.RAPID_DECLINE.value)
        if key in existing:
            return None
        existing.add(key)

        abs_change = abs(float(lb.change_rate))
        base = min(60, int(abs_change * 2.5))
        consec = min(20, int(lb.consecutive_decrease_days or 0) * 5)
        score = min(100, base + consec + 10)
        detail = {
            "balanceChangeRate": str(lb.change_rate),
            "changeQuantity": int(lb.change_quantity or 0),
            "consecutiveDecreaseDays": int(lb.consecutive_decrease_days or 0),
        }
        return Signal(
            stock_id=stock_id, signal_date=trading_date,
            signal_type=SignalType.RAPID_DECLINE.value,
            score=score, grade=_grade(score), detail=detail,
        )

    @staticmethod
    def _trend_reversal(
        stock_id: int, trading_date: date, hist: pd.DataFrame | None,
        existing: set[tuple[int, str]],
    ) -> Signal | None:
        if hist is None or len(hist) < TREND_MA_LONG + 1:
            return None
        sorted_hist = hist.sort_values("date").reset_index(drop=True)
        qty = sorted_hist["qty"]

        ma_short = qty.rolling(TREND_MA_SHORT, min_periods=TREND_MA_SHORT).mean()
        ma_long = qty.rolling(TREND_MA_LONG, min_periods=TREND_MA_LONG).mean()
        # rolling 결과는 NaN 이 나올 수 있고 None 은 절대 나오지 않음 — pd.isna 로 통일 검증.
        if pd.isna(ma_short.iloc[-1]) or pd.isna(ma_long.iloc[-1]):
            return None
        if pd.isna(ma_short.iloc[-2]) or pd.isna(ma_long.iloc[-2]):
            return None
        short_today = float(ma_short.iloc[-1])
        long_today = float(ma_long.iloc[-1])
        short_yest = float(ma_short.iloc[-2])
        long_yest = float(ma_long.iloc[-2])

        cross = short_yest >= long_yest and short_today < long_today  # Java 동일 조건
        if not cross:
            return None

        divergence = abs(short_today - long_today) / long_today * 100 if long_today else 0
        divergence_score = min(40, int(divergence * 10))
        speed = (
            abs((short_today - short_yest) / short_yest * 100) if short_yest else 0
        )
        speed_score = min(30, int(speed * 15))
        score = min(100, divergence_score + speed_score + 30)
        if score < TREND_REVERSAL_MIN_SCORE:
            return None

        key = (stock_id, SignalType.TREND_REVERSAL.value)
        if key in existing:
            return None
        existing.add(key)
        detail = {
            "maShort": round(short_today, 2),
            "maLong": round(long_today, 2),
            "crossType": "GOLDEN_CROSS",  # Java 용어 보존
        }
        return Signal(
            stock_id=stock_id, signal_date=trading_date,
            signal_type=SignalType.TREND_REVERSAL.value,
            score=score, grade=_grade(score), detail=detail,
        )

    @staticmethod
    def _short_squeeze(
        stock_id: int, trading_date: date, lb: Any, sp: Any, ss: Any,
        avg_volume: float, existing: set[tuple[int, str]],
    ) -> Signal | None:
        if lb is None or sp is None:
            return None

        # balance score
        change_rate = _to_decimal(lb.change_rate) or Decimal(0)
        balance_score = min(30, int(abs(float(change_rate)) * 1.5))

        # volume score
        today_vol = int(sp.volume or 0)
        ratio = (today_vol / avg_volume) if avg_volume > 0 and today_vol > 0 else 0.0
        volume_score = max(0, min(25, int((ratio - 1) * 12.5))) if ratio > 0 else 0

        # price score
        price_change = _to_decimal(sp.change_rate) or Decimal(0)
        price_val = float(price_change)
        price_score = min(25, int(price_val * 5)) if price_val > 0 else 0

        # short ratio score
        short_ratio = _to_decimal(ss.short_ratio) if ss else None
        short_score = min(20, int(float(short_ratio) * 2)) if short_ratio else 0

        total = balance_score + volume_score + price_score + short_score
        if total < SHORT_SQUEEZE_MIN_SCORE:
            return None

        key = (stock_id, SignalType.SHORT_SQUEEZE.value)
        if key in existing:
            return None
        existing.add(key)

        detail = {
            "balanceChangeRate": str(change_rate),
            "balanceScore": balance_score,
            "volumeChangeRate": round(ratio, 4),
            "volumeScore": volume_score,
            "priceChangeRate": str(price_change),
            "priceScore": price_score,
            "shortRatioScore": short_score,
            "consecutiveDecreaseDays": int(lb.consecutive_decrease_days or 0),
        }
        return Signal(
            stock_id=stock_id, signal_date=trading_date,
            signal_type=SignalType.SHORT_SQUEEZE.value,
            score=total, grade=_grade(total), detail=detail,
        )
