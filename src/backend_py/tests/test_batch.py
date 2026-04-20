"""배치 파이프라인 테스트 — 거래일 필터 + 각 Step 격리 + 실패 전파.

KRX/Telegram 은 MagicMock/stub 으로 대체. DB 는 testcontainers PG16(conftest 공용).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapter.out.external import TelegramClient
from app.adapter.out.external._records import (
    LendingBalanceRow,
    ShortSellingRow,
    StockPriceRow,
)
from app.adapter.out.persistence.models import (
    BacktestResult,
    Signal,
    SignalType,
    Stock,
    StockPrice,
)
from app.batch.backtest_job import run_backtest_pipeline
from app.batch.market_data_job import run_market_data_pipeline
from app.batch.scheduler import build_scheduler
from app.batch.trading_day import is_trading_day
from app.config.settings import Settings


@pytest.fixture
def db_cleaner(database_url: str):  # type: ignore[no-untyped-def]
    """파이프라인이 Step 단위로 commit 하므로 테스트 종료 후 TRUNCATE 로 격리 복구.

    비동기 엔진을 쓰면 pytest-asyncio 루프 수명과 엮여 복잡해지므로 sync psycopg2 로 처리.
    """
    from sqlalchemy import create_engine

    yield
    sync_url = database_url.replace("+asyncpg", "+psycopg2")
    sync_engine = create_engine(sync_url)
    try:
        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    "TRUNCATE TABLE signal, backtest_result, "
                    "lending_balance, short_selling, stock_price, "
                    "notification_preference, stock "
                    "RESTART IDENTITY CASCADE"
                )
            )
            # V2 migration 의 기본 row 복구(다른 테스트의 get_or_create 기대값)
            conn.execute(
                text("INSERT INTO notification_preference (id) VALUES (1) ON CONFLICT DO NOTHING")
            )
    finally:
        sync_engine.dispose()


# -----------------------------------------------------------------------------
# is_trading_day
# -----------------------------------------------------------------------------


def test_is_trading_day_weekday_true() -> None:
    assert is_trading_day(date(2026, 4, 17)) is True  # 금


def test_is_trading_day_saturday_false() -> None:
    assert is_trading_day(date(2026, 4, 18)) is False


def test_is_trading_day_sunday_false() -> None:
    assert is_trading_day(date(2026, 4, 19)) is False


# -----------------------------------------------------------------------------
# Pipeline — 주말 skip / 거래일 3-step 성공 / detect 실패 시 notify skip
# -----------------------------------------------------------------------------


def _tele_stub_always_ok() -> TelegramClient:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
    return TelegramClient(
        Settings(telegram_bot_token="fake", telegram_chat_id="-1001"),
        transport=httpx.MockTransport(handler),
    )


class _FakeKrx:
    """pandas/pykrx 없이도 테스트 가능한 최소 KRX 스텁."""

    def __init__(self, prices=None, shorts=None, lendings=None, raise_on: str | None = None) -> None:
        self._prices = prices or []
        self._shorts = shorts or []
        self._lendings = lendings or []
        self._raise_on = raise_on

    async def fetch_stock_prices(self, _: date) -> list[StockPriceRow]:
        if self._raise_on == "prices":
            raise RuntimeError("KRX prices 실패")
        return list(self._prices)

    async def fetch_short_selling(self, _: date) -> list[ShortSellingRow]:
        if self._raise_on == "shorts":
            raise RuntimeError("KRX shorts 실패")
        return list(self._shorts)

    async def fetch_lending_balance(self, _: date) -> list[LendingBalanceRow]:
        if self._raise_on == "lending":
            raise RuntimeError("KRX lending 실패")
        return list(self._lendings)


@pytest.mark.asyncio
async def test_pipeline_skips_on_weekend() -> None:
    result = await run_market_data_pipeline(trading_date=date(2026, 4, 18))  # 토요일
    assert result.skipped is True
    assert result.steps == []


@pytest.mark.asyncio
async def test_pipeline_runs_three_steps_on_trading_day(
    engine, database_url, apply_migrations, db_cleaner  # noqa: ARG001  — 픽스처 의존
) -> None:
    # 파이프라인은 자체 세션 팩토리를 사용하므로 testcontainers 엔진을 직접 주입
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    fake_prices = [
        StockPriceRow(
            stock_code="005930", stock_name="삼성전자", market_type="KOSPI",
            close_price=78_500, open_price=78_000, high_price=79_200, low_price=77_800,
            volume=15_234_567, market_cap=468_500_000_000_000, change_rate="0.64",
        )
    ]
    fake_shorts = [
        ShortSellingRow(
            stock_code="005930", stock_name="삼성전자",
            short_volume=1_234_567, short_amount=98_765_432_100, short_ratio="8.1",
        )
    ]
    fake_lendings = [
        LendingBalanceRow(
            stock_code="005930", stock_name="삼성전자",
            balance_quantity=12_345_678, balance_amount=987_654_321_000,
        )
    ]

    result = await run_market_data_pipeline(
        trading_date=date(2026, 4, 17),
        krx_client=_FakeKrx(fake_prices, fake_shorts, fake_lendings),  # type: ignore[arg-type]
        telegram_client=_tele_stub_always_ok(),
        session_factory=factory,
    )

    assert result.skipped is False
    names = [s.name for s in result.steps]
    assert names == ["collect", "detect", "notify"]
    assert all(s.succeeded for s in result.steps), [
        (s.name, s.error) for s in result.steps if not s.succeeded
    ]
    collect = next(s for s in result.steps if s.name == "collect")
    assert collect.summary and collect.summary.get("prices") == 1


@pytest.mark.asyncio
async def test_pipeline_step3_dispatches_seeded_signal_to_telegram(
    engine, database_url, apply_migrations, db_cleaner  # noqa: ARG001
) -> None:
    """Step 3(notify) 배선 회귀 가드.

    trading_date 에 시그널 1건을 사전 seed 하고, KRX 는 빈 응답이라 collect/detect 는 새 데이터 없음.
    이 상황에서도 Step 3 이 DB 에서 기존 시그널을 읽어 Telegram 으로 발송하는지 검증.
    리팩터로 `_notify` 콜백이 미배선되면 sent=0 으로 조용히 실패 → 이 테스트가 감지.
    """
    import json

    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    trading_date = date(2026, 4, 17)

    # 사전 seed — 같은 날짜에 stock + notification_preference + signal 1건
    async with factory() as session:
        stock = Stock(stock_code="035420", stock_name="NAVER", market_type="KOSPI")
        session.add(stock)
        await session.flush()
        session.add(Signal(
            stock_id=stock.id, signal_date=trading_date,
            signal_type=SignalType.RAPID_DECLINE.value,
            score=90, grade="A", detail={"seed": True},
        ))
        await session.commit()

    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    telegram = TelegramClient(
        Settings(telegram_bot_token="fake", telegram_chat_id="-1001"),
        transport=httpx.MockTransport(handler),
    )

    result = await run_market_data_pipeline(
        trading_date=trading_date,
        krx_client=_FakeKrx(),  # type: ignore[arg-type]
        telegram_client=telegram,
        session_factory=factory,
    )

    assert result.skipped is False
    outcomes = {s.name: s for s in result.steps}
    assert outcomes["notify"].succeeded is True
    assert outcomes["notify"].summary == {"sent": 1}, \
        f"seed 된 시그널이 Telegram 으로 발송돼야 함. 실제: {outcomes['notify'].summary}"
    assert len(captured) == 1, "Telegram 호출 정확히 1회"
    body = captured[0]
    assert body["parse_mode"] == "HTML"
    assert "대차잔고 급감" in str(body["text"]), "한글 라벨이 메시지에 포함돼야 함"
    assert "NAVER" in str(body["text"])


@pytest.mark.asyncio
async def test_pipeline_collect_failure_is_isolated(
    engine, database_url, apply_migrations, db_cleaner  # noqa: ARG001
) -> None:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    # KRX 가 한 단계라도 던지면 collect 전체 실패 → detect 는 진행하되 빈 상태, notify 는 detect 성공 시에만
    fake_krx = _FakeKrx(raise_on="prices")

    result = await run_market_data_pipeline(
        trading_date=date(2026, 4, 17),
        krx_client=fake_krx,  # type: ignore[arg-type]
        telegram_client=_tele_stub_always_ok(),
        session_factory=factory,
    )

    outcomes = {s.name: s for s in result.steps}
    assert outcomes["collect"].succeeded is False
    assert outcomes["collect"].error is not None
    # detect 는 독립 세션이므로 실행됐으나 데이터가 없어 0 건이지만 성공으로 판정됨
    assert outcomes["detect"].succeeded is True
    # notify 는 detect 성공이므로 진행되지만 대상 시그널 0 → sent=0
    assert outcomes["notify"].succeeded is True
    assert outcomes["notify"].summary == {"sent": 0}
    assert result.succeeded is False  # collect 실패로 전체는 false


# -----------------------------------------------------------------------------
# Scheduler build
# -----------------------------------------------------------------------------


def test_build_scheduler_registers_weekday_cron() -> None:
    # backtest 는 별도 테스트에서 검증 — 여기서는 market_data 단독 등록만 확인
    settings = Settings(
        scheduler_hour_kst=6, scheduler_minute_kst=30, backtest_enabled=False,
    )
    scheduler = build_scheduler(settings)
    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == "market_data_pipeline"
    # CronTrigger fields dump
    trigger_fields = {f.name: str(f) for f in job.trigger.fields}
    assert trigger_fields["day_of_week"] == "mon-fri"
    assert trigger_fields["hour"] == "6"
    assert trigger_fields["minute"] == "30"


def test_build_scheduler_registers_backtest_cron_when_enabled() -> None:
    settings = Settings(
        backtest_enabled=True,
        backtest_cron_day_of_week="mon",
        backtest_cron_hour_kst=7,
        backtest_cron_minute_kst=15,
    )
    scheduler = build_scheduler(settings)
    jobs = {j.id: j for j in scheduler.get_jobs()}
    assert "market_data_pipeline" in jobs
    assert "backtest_pipeline" in jobs
    fields = {f.name: str(f) for f in jobs["backtest_pipeline"].trigger.fields}
    assert fields["day_of_week"] == "mon"
    assert fields["hour"] == "7"
    assert fields["minute"] == "15"


def test_build_scheduler_skips_backtest_when_disabled() -> None:
    settings = Settings(backtest_enabled=False)
    scheduler = build_scheduler(settings)
    jobs = {j.id for j in scheduler.get_jobs()}
    assert jobs == {"market_data_pipeline"}


# -----------------------------------------------------------------------------
# Backtest Pipeline — 시그널/가격 시드 → backtest_result 적재
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backtest_pipeline_persists_result_rows(
    engine, database_url, apply_migrations, db_cleaner  # noqa: ARG001
) -> None:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    base_date = date(2026, 1, 5)

    async with factory() as session:
        stock = Stock(stock_code="005930", stock_name="삼성전자", market_type="KOSPI")
        session.add(stock)
        await session.flush()

        # 40 영업일치 우상향 가격 (+1%/day) — 5/10/20일 수익률 모두 양수
        for i in range(40):
            session.add(StockPrice(
                stock_id=stock.id,
                trading_date=base_date + timedelta(days=i),
                close_price=int(10_000 * (1.01 ** i)),
            ))
        # 시그널 1건 (RAPID_DECLINE) seed
        session.add(Signal(
            stock_id=stock.id,
            signal_date=base_date,
            signal_type=SignalType.RAPID_DECLINE.value,
            score=85, grade="A", detail={"seed": True},
        ))
        await session.commit()

    result = await run_backtest_pipeline(
        period_end=base_date, period_years=1, session_factory=factory,
    )

    assert result.succeeded is True
    assert result.execution is not None
    assert result.execution.signals_processed == 1
    assert result.execution.returns_calculated == 1
    assert result.execution.result_rows == 1
    assert result.period_end == base_date
    # period_start 는 period_end - 1 year
    assert result.period_start == date(2025, 1, 5)

    # DB 확인 — backtest_result 에 RAPID_DECLINE 1건 append
    async with factory() as session:
        rows = (await session.execute(
            select(BacktestResult).where(
                BacktestResult.signal_type == SignalType.RAPID_DECLINE.value
            )
        )).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        assert row.total_signals == 1
        # 우상향 시드 → 5일 적중률 100% 기대
        assert row.hit_count_5d == 1
        assert row.hit_rate_5d == Decimal("100.0000")


@pytest.mark.asyncio
async def test_backtest_pipeline_handles_empty_period(
    engine, database_url, apply_migrations, db_cleaner  # noqa: ARG001
) -> None:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    # 시그널 0 건 — 엔진은 signals_processed=0 으로 조기 종료, result_rows=0
    result = await run_backtest_pipeline(
        period_end=date(2020, 6, 30), period_years=1, session_factory=factory,
    )
    assert result.succeeded is True
    assert result.execution is not None
    assert result.execution.signals_processed == 0
    assert result.execution.result_rows == 0
