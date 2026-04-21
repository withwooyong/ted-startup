"""Service 계층 통합 테스트 — testcontainers 세션 위에서 실제 ORM·SQL 경로까지 포함."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import (
    Signal,
    SignalType,
    Stock,
)
from app.adapter.out.persistence.repositories import (
    BacktestResultRepository,
    LendingBalanceRepository,
    SignalRepository,
    StockPriceRepository,
    StockRepository,
)
from app.application.service import (
    BacktestEngineService,
    SignalDetectionService,
)
from app.application.service.backtest_service import _dec


async def _seed_stock(session: AsyncSession, code: str = "005930", name: str = "삼성전자") -> Stock:
    return await StockRepository(session).add(
        Stock(stock_code=code, stock_name=name, market_type="KOSPI")
    )


@pytest.mark.asyncio
async def test_rapid_decline_signal_generated_when_change_rate_below_threshold(
    session: AsyncSession,
) -> None:
    stock = await _seed_stock(session)
    today = date(2026, 4, 17)

    await LendingBalanceRepository(session).upsert_many(
        [
            {
                "stock_id": stock.id,
                "trading_date": today,
                "balance_quantity": 1_000_000,
                "balance_amount": 10_000_000_000,
                "change_rate": "-15.5",
                "change_quantity": -100_000,
                "consecutive_decrease_days": 3,
            }
        ]
    )

    svc = SignalDetectionService(session)
    result = await svc.detect_all(today)

    assert result.rapid_decline == 1
    signals = await SignalRepository(session).list_by_date(today)
    rapid = [s for s in signals if s.signal_type == SignalType.RAPID_DECLINE.value]
    assert len(rapid) == 1
    # 15.5 * 2.5 = 38.75 → base 38, consec 15, +10 → 63 (B 등급)
    assert rapid[0].score == 63
    assert rapid[0].grade == "B"


@pytest.mark.asyncio
async def test_no_signal_when_change_rate_above_threshold(session: AsyncSession) -> None:
    stock = await _seed_stock(session, "000660", "SK하이닉스")
    today = date(2026, 4, 17)
    await LendingBalanceRepository(session).upsert_many(
        [
            {
                "stock_id": stock.id,
                "trading_date": today,
                "balance_quantity": 1_000_000,
                "balance_amount": 10_000_000_000,
                "change_rate": "-5.0",  # 임계 초과 못함
                "change_quantity": -50_000,
                "consecutive_decrease_days": 1,
            }
        ]
    )
    result = await SignalDetectionService(session).detect_all(today)
    assert result.rapid_decline == 0


@pytest.mark.asyncio
async def test_rapid_decline_ignores_minus_eleven_percent(session: AsyncSession) -> None:
    """2026-04-20 튜닝: 임계값 -10% → -12%. -11% 는 더 이상 신호로 잡히지 않음."""
    stock = await _seed_stock(session, "051910", "LG화학")
    today = date(2026, 4, 17)
    await LendingBalanceRepository(session).upsert_many(
        [
            {
                "stock_id": stock.id,
                "trading_date": today,
                "balance_quantity": 2_000_000,
                "balance_amount": 20_000_000_000,
                "change_rate": "-11.0",
                "change_quantity": -220_000,
                "consecutive_decrease_days": 2,
            }
        ]
    )
    result = await SignalDetectionService(session).detect_all(today)
    assert result.rapid_decline == 0


@pytest.mark.asyncio
async def test_trend_reversal_detected_on_dead_cross(session: AsyncSession) -> None:
    """5MA 가 어제까지 20MA 이상이었다가 오늘 아래로 뚫고 내려가는 전환 검출."""
    stock = await _seed_stock(session, "035720", "카카오")
    today = date(2026, 4, 17)

    # 24일간 선형 상승으로 5MA > 20MA 를 유지시키고, 마지막 날(오늘)만 큰 폭 급락으로 5MA<20MA 전환
    rows = []
    for i in range(24):
        d = today - timedelta(days=24 - i)
        qty = 1_000_000 + i * 10_000
        rows.append(
            {
                "stock_id": stock.id,
                "trading_date": d,
                "balance_quantity": qty,
                "balance_amount": qty * 1000,
                "change_rate": "0.0",
            }
        )
    rows.append(
        {
            "stock_id": stock.id,
            "trading_date": today,
            "balance_quantity": 500_000,  # 급락 → 5MA 를 20MA 아래로 밀어내림
            "balance_amount": 500_000 * 1000,
            "change_rate": "-58.3",
        }
    )
    await LendingBalanceRepository(session).upsert_many(rows)

    result = await SignalDetectionService(session).detect_all(today)
    assert result.trend_reversal >= 1


@pytest.mark.asyncio
async def test_backtest_engine_computes_returns_and_aggregates(session: AsyncSession) -> None:
    stock = await _seed_stock(session, "207940", "삼성바이오로직스")

    # 40영업일치 가격: signal_date=day 5, 가격 우상향
    base_date = date(2026, 1, 5)
    price_rows = []
    for i in range(40):
        d = base_date + timedelta(days=i)
        # 매일 +1% 정도 상승 → 5일 후 ~+5%, 20일 후 ~+20%
        close = int(10_000 * (1.01 ** i))
        price_rows.append(
            {"stock_id": stock.id, "trading_date": d, "close_price": close}
        )
    await StockPriceRepository(session).upsert_many(price_rows)

    # 시그널 1개 seed
    signal = Signal(
        stock_id=stock.id,
        signal_date=base_date,
        signal_type=SignalType.RAPID_DECLINE.value,
        score=85,
        grade="A",
        detail={"seed": True},
    )
    await SignalRepository(session).add(signal)

    result = await BacktestEngineService(session).execute(
        period_start=base_date, period_end=base_date
    )
    assert result.signals_processed == 1
    assert result.returns_calculated == 1
    assert result.result_rows == 1

    refreshed = (await SignalRepository(session).list_by_date(base_date))[0]
    # 5일 후 가격 ≈ 10000 * 1.01^5 / 10000 - 1 ≈ 0.0510 → 5.10%
    assert refreshed.return_5d is not None
    assert Decimal("4") < refreshed.return_5d < Decimal("6")
    # 20일 후 ≈ 1.01^20 - 1 ≈ 0.2202 → 22.02%
    assert refreshed.return_20d is not None
    assert Decimal("20") < refreshed.return_20d < Decimal("25")


@pytest.mark.asyncio
async def test_backtest_no_signals_returns_empty_result(session: AsyncSession) -> None:
    result = await BacktestEngineService(session).execute(
        period_start=date(2020, 1, 1), period_end=date(2020, 1, 31)
    )
    assert result.signals_processed == 0
    assert result.result_rows == 0


@pytest.mark.asyncio
async def test_backtest_handles_zero_close_price_without_infinity(session: AsyncSession) -> None:
    """상장폐지/정지 종목의 close_price=0 이 있어도 Infinity 발생 없이 정상 집계.

    2026-04-20 베이스라인 측정에서 TREND_REVERSAL avg_return=Infinity 로 INSERT 실패가
    재현된 케이스. close_price=0 은 NaN 마스킹으로 걸러져 해당 signal 의 return_Nd 는 None,
    집계 avg_return 은 유한 Decimal 로 저장돼야 한다.
    """
    stock = await _seed_stock(session, "900999", "테스트폐지주")

    base_date = date(2026, 1, 5)
    # 40 영업일치 가격 — 기준일(index 0) 만 close=0, 나머지는 정상 10_000 +i
    prices = []
    for i in range(40):
        d = base_date + timedelta(days=i)
        close = 0 if i == 0 else 10_000 + i * 100
        prices.append({"stock_id": stock.id, "trading_date": d, "close_price": close})
    await StockPriceRepository(session).upsert_many(prices)

    # 시그널은 기준일(close=0) 에 발생 — 분모 0 이라 과거 로직은 Infinity 산출
    await SignalRepository(session).add(Signal(
        stock_id=stock.id, signal_date=base_date,
        signal_type=SignalType.TREND_REVERSAL.value,
        score=85, grade="A", detail={"zero": True},
    ))

    result = await BacktestEngineService(session).execute(
        period_start=base_date, period_end=base_date
    )
    # INSERT 성공 (NumericValueOutOfRangeError 미발생) 이 핵심 회귀 방어
    assert result.signals_processed == 1
    assert result.result_rows == 1

    refreshed = (await SignalRepository(session).list_by_date(base_date))[0]
    # close=0 기준일은 분모로 못 써 return 은 None 이어야 함
    assert refreshed.return_5d is None
    assert refreshed.return_10d is None
    assert refreshed.return_20d is None


@pytest.mark.asyncio
async def test_backtest_preserves_minus_hundred_when_future_close_zero(
    session: AsyncSession,
) -> None:
    """기준일 가격은 정상이고 미래 시점에 종가가 0(전손)으로 찍힌 경우 -100% 로 기록돼야 한다.

    단순히 분자·분모 둘 다 마스킹하면 이 케이스가 None 으로 사라져 승률·평균수익 집계가
    왜곡된다. 분모만 가드하는 구현이 제대로 작동하는지 고정한다.
    """
    stock = await _seed_stock(session, "900888", "전손주")
    base_date = date(2026, 2, 1)

    # 기준일 = 10_000, +5 영업일 후 = 0 (전손), 그 뒤는 0 유지
    rows = [
        {"stock_id": stock.id, "trading_date": base_date, "close_price": 10_000},
    ]
    for i in range(1, 5):
        rows.append({
            "stock_id": stock.id, "trading_date": base_date + timedelta(days=i),
            "close_price": 9_000 - i * 500,
        })
    # 5일째부터 20일까지 전부 0 — 전손 상태 유지
    for i in range(5, 21):
        rows.append({
            "stock_id": stock.id, "trading_date": base_date + timedelta(days=i),
            "close_price": 0,
        })
    await StockPriceRepository(session).upsert_many(rows)

    await SignalRepository(session).add(Signal(
        stock_id=stock.id, signal_date=base_date,
        signal_type=SignalType.SHORT_SQUEEZE.value,
        score=75, grade="B", detail={"delisted": True},
    ))

    result = await BacktestEngineService(session).execute(
        period_start=base_date, period_end=base_date
    )
    assert result.signals_processed == 1
    assert result.result_rows == 1

    refreshed = (await SignalRepository(session).list_by_date(base_date))[0]
    # base=10000, future=0 → (0/10000 - 1) * 100 = -100.0
    assert refreshed.return_5d is not None
    assert Decimal("-100.01") < refreshed.return_5d < Decimal("-99.99")
    assert refreshed.return_20d is not None
    assert Decimal("-100.01") < refreshed.return_20d < Decimal("-99.99")


def test_dec_always_returns_decimal_and_rejects_nan() -> None:
    """`_dec` 의 contract 고정 — 리뷰 MEDIUM #2 사전 부채 청산 회귀 방어.

    구 구현은 `Decimal | None` 을 돌려줄 수 있어 호출자가 `_dec(x) or Decimal("0")`
    같은 도달불가 fallback 에 의존하는 안티패턴이 있었다. 새 contract 는
    1) float 입력은 항상 Decimal 반환,
    2) NaN 은 ValueError 로 loud fail (caller 의 pre-guard 강제) 이다.

    참고: `round(float, 4)` 는 입력의 자연 스케일을 그대로 보존한다.
    `_dec(0.0) == Decimal('0.0')` (exp=-1), `_dec(12.34567) == Decimal('12.3457')`
    (exp=-4) — DB 에 저장될 때 NUMERIC(10,4) 가 스케일을 정규화한다.
    """
    zero = _dec(0.0)
    assert isinstance(zero, Decimal)
    assert zero == Decimal("0")  # 값 비교는 스케일 무관

    # places=4 반올림 동작 — half-to-even
    assert _dec(12.34567) == Decimal("12.3457")
    assert _dec(-100.0) == Decimal("-100.0")

    with pytest.raises(ValueError, match="pre-guard"):
        _dec(float("nan"))


@pytest.mark.asyncio
async def test_backtest_aggregation_stores_zero_as_decimal(session: AsyncSession) -> None:
    """집계 `BacktestResult.hit_rate_5d`/`avg_return_5d` 가 Decimal(0) 로 저장 —
    리팩터된 `_dec` 경로에서 None 이 새지 않음을 고정.

    `BacktestResult.*` 컬럼은 nullable NUMERIC(10,4) 이라 만약 `_dec` 가 None 을
    돌려주고 `or Decimal("0")` fallback 이 지워지면 NULL 로 저장될 수 있는 구조.
    호출 컨텍스트에서 `_dec` 가 None 을 반환할 수 없다는 불변을 통합 경로로 검증.
    """
    stock = await _seed_stock(session, "905555", "제로수익주")
    base_date = date(2026, 3, 10)

    # 기준일부터 40일간 가격 일정 — 어느 N-영업일 shift 에도 return=0 이 나오는 구성
    flat_rows = [
        {"stock_id": stock.id, "trading_date": base_date + timedelta(days=i), "close_price": 10_000}
        for i in range(40)
    ]
    await StockPriceRepository(session).upsert_many(flat_rows)

    await SignalRepository(session).add(Signal(
        stock_id=stock.id, signal_date=base_date,
        signal_type=SignalType.RAPID_DECLINE.value,
        score=70, grade="B", detail={"flat": True},
    ))

    outcome = await BacktestEngineService(session).execute(
        period_start=base_date, period_end=base_date
    )
    assert outcome.signals_processed == 1
    assert outcome.result_rows == 1

    bt_results = await BacktestResultRepository(session).list_by_signal_type(
        SignalType.RAPID_DECLINE.value
    )
    # 기간이 단일일이라 1행만 생성된 것이 정상. 여러 period 로 늘어나는 회귀가 있으면 바로 드러남.
    assert len(bt_results) == 1
    bt = bt_results[0]

    # hit_rate = 0/1 * 100 = 0.0, avg_return = 0.0 — 둘 다 None 이 아닌 Decimal(0) 으로 저장
    assert bt.hit_rate_5d is not None
    assert isinstance(bt.hit_rate_5d, Decimal)
    assert bt.hit_rate_5d == Decimal("0")
    assert bt.avg_return_5d is not None
    assert isinstance(bt.avg_return_5d, Decimal)
    assert bt.avg_return_5d == Decimal("0")
