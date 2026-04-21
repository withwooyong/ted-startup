"""NotificationService — N+1 방어 + HTML 이스케이프 + 라벨 매핑 + 필터·실패·no-op 회귀 테스트."""

from __future__ import annotations

import json
from datetime import date

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.external import TelegramClient
from app.adapter.out.persistence.models import Signal, SignalType, Stock
from app.adapter.out.persistence.repositories import (
    NotificationPreferenceRepository,
    SignalRepository,
    StockRepository,
)
from app.application.service import NotificationService
from app.config.settings import Settings


def _tele(transport: httpx.MockTransport) -> TelegramClient:
    return TelegramClient(
        Settings(telegram_bot_token="fake", telegram_chat_id="-1001"),
        transport=transport,
    )


def _tele_disabled() -> TelegramClient:
    """토큰 없음 → enabled=False. transport 지정해도 호출 자체가 막혀야 함."""
    return TelegramClient(
        Settings(telegram_bot_token="", telegram_chat_id=""),
    )


@pytest.mark.asyncio
async def test_notify_signals_bulk_fetches_stocks_once(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """3개 시그널 발송 시 stock 조회가 '단일 list_by_ids 1회'로 수행되는지 검증 (N+1 금지)."""
    # 종목 3개 시드
    stock_repo = StockRepository(session)
    stocks = [
        await stock_repo.add(Stock(stock_code=f"00000{i}", stock_name=f"종목{i}", market_type="KOSPI"))
        for i in range(1, 4)
    ]
    # NotificationPreference 기본(min_score=60) — 시그널 score 를 60 이상으로
    await NotificationPreferenceRepository(session).get_or_create()

    sig_repo = SignalRepository(session)
    signals = []
    for stock in stocks:
        s = await sig_repo.add(
            Signal(
                stock_id=stock.id,
                signal_date=date(2026, 4, 17),
                signal_type=SignalType.RAPID_DECLINE.value,
                score=80,
                grade="A",
                detail={"test": True},
            )
        )
        signals.append(s)

    # list_by_ids 호출 수를 세기 위해 spy
    original = StockRepository.list_by_ids
    calls: list[int] = []

    async def spy(self: StockRepository, ids):  # type: ignore[no-untyped-def]
        calls.append(len(list(ids)))
        return await original(self, ids)

    monkeypatch.setattr(StockRepository, "list_by_ids", spy)

    # Telegram 항상 성공
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with _tele(httpx.MockTransport(handler)) as tele:
        svc = NotificationService(session, tele)
        sent = await svc.notify_signals(signals)

    assert sent == 3
    assert len(calls) == 1, f"종목 조회는 1회여야 함(N+1 금지). 실제: {calls}"
    assert calls[0] == 3, "요청된 stock_id 개수(3)가 한 번에 전달돼야 함"


@pytest.mark.asyncio
async def test_notify_signals_escapes_html_in_stock_name(session: AsyncSession) -> None:
    """종목명에 <, & 가 포함돼도 Telegram HTML parse 안전하게 이스케이프."""
    stock = await StockRepository(session).add(Stock(stock_code="123456", stock_name="A<b>&조작", market_type="KOSPI"))
    await NotificationPreferenceRepository(session).get_or_create()
    signal = await SignalRepository(session).add(
        Signal(
            stock_id=stock.id,
            signal_date=date(2026, 4, 17),
            signal_type=SignalType.SHORT_SQUEEZE.value,
            score=75,
            grade="B",
            detail={},
        )
    )

    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content)
        captured["text"] = body["text"]
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with _tele(httpx.MockTransport(handler)) as tele:
        await NotificationService(session, tele).notify_signals([signal])

    text = captured["text"]
    # 원문 <, & 는 이스케이프돼 있어야 하고 의도한 <b> 태그는 그대로
    assert "A&lt;b&gt;&amp;조작" in text
    assert text.startswith("<b>[")
    assert "</b>" in text


@pytest.mark.asyncio
async def test_notify_signals_uses_korean_label(session: AsyncSession) -> None:
    stock = await StockRepository(session).add(Stock(stock_code="654321", stock_name="테스트종목", market_type="KOSPI"))
    await NotificationPreferenceRepository(session).get_or_create()
    signal = await SignalRepository(session).add(
        Signal(
            stock_id=stock.id,
            signal_date=date(2026, 4, 17),
            signal_type=SignalType.TREND_REVERSAL.value,
            score=72,
            grade="B",
            detail={},
        )
    )

    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content)
        captured["text"] = body["text"]
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with _tele(httpx.MockTransport(handler)) as tele:
        await NotificationService(session, tele).notify_signals([signal])

    assert "추세전환" in captured["text"], "영문 enum 대신 한글 라벨이 노출돼야 함"
    assert "TREND_REVERSAL" not in captured["text"]


# -----------------------------------------------------------------------------
# 필터링 / 실패 / no-op 회귀 가드 (2026-04-20 추가)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_min_score_filter_drops_below_threshold(session: AsyncSession) -> None:
    """pref.min_score=60 일 때 score=55 는 드롭, score=80 은 발송 — 2건 중 1건만 Telegram 호출."""
    stock_repo = StockRepository(session)
    stock_low = await stock_repo.add(Stock(stock_code="111110", stock_name="저점수", market_type="KOSPI"))
    stock_high = await stock_repo.add(Stock(stock_code="111111", stock_name="고점수", market_type="KOSPI"))
    await NotificationPreferenceRepository(session).get_or_create()  # 기본 min_score=60

    sig_repo = SignalRepository(session)
    low = await sig_repo.add(
        Signal(
            stock_id=stock_low.id,
            signal_date=date(2026, 4, 17),
            signal_type=SignalType.RAPID_DECLINE.value,
            score=55,
            grade="C",
            detail={},
        )
    )
    high = await sig_repo.add(
        Signal(
            stock_id=stock_high.id,
            signal_date=date(2026, 4, 17),
            signal_type=SignalType.RAPID_DECLINE.value,
            score=80,
            grade="A",
            detail={},
        )
    )

    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured.append(body["text"])
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with _tele(httpx.MockTransport(handler)) as tele:
        sent = await NotificationService(session, tele).notify_signals([low, high])

    assert sent == 1
    assert len(captured) == 1, "Telegram 호출은 임계값 이상만 1회"
    assert "점수 80" in captured[0]
    assert "점수 55" not in captured[0]


@pytest.mark.asyncio
async def test_signal_types_filter_drops_disabled_types(session: AsyncSession) -> None:
    """pref.signal_types=[RAPID_DECLINE] 이면 TREND_REVERSAL/SHORT_SQUEEZE 는 드롭."""
    stock = await StockRepository(session).add(Stock(stock_code="222222", stock_name="타입필터", market_type="KOSPI"))
    pref = await NotificationPreferenceRepository(session).get_or_create()
    pref.signal_types = ["RAPID_DECLINE"]
    await NotificationPreferenceRepository(session).save(pref)

    sig_repo = SignalRepository(session)
    rapid = await sig_repo.add(
        Signal(
            stock_id=stock.id,
            signal_date=date(2026, 4, 17),
            signal_type=SignalType.RAPID_DECLINE.value,
            score=85,
            grade="A",
            detail={},
        )
    )
    trend = await sig_repo.add(
        Signal(
            stock_id=stock.id,
            signal_date=date(2026, 4, 17),
            signal_type=SignalType.TREND_REVERSAL.value,
            score=85,
            grade="A",
            detail={},
        )
    )
    squeeze = await sig_repo.add(
        Signal(
            stock_id=stock.id,
            signal_date=date(2026, 4, 17),
            signal_type=SignalType.SHORT_SQUEEZE.value,
            score=85,
            grade="A",
            detail={},
        )
    )

    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured.append(body["text"])
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    async with _tele(httpx.MockTransport(handler)) as tele:
        sent = await NotificationService(session, tele).notify_signals([rapid, trend, squeeze])

    assert sent == 1, "활성 타입 1건만 발송"
    assert len(captured) == 1
    assert "대차잔고 급감" in captured[0]


@pytest.mark.asyncio
async def test_telegram_disabled_skips_db_access(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """client.enabled=False 면 pref/stock 조회 자체를 수행하지 않아야 한다.

    의미 없는 DB 왕복 방지 — early return 이 pref_repo.get_or_create 앞에 있어야 함.
    """
    stock = await StockRepository(session).add(Stock(stock_code="333333", stock_name="비활성", market_type="KOSPI"))
    signal = await SignalRepository(session).add(
        Signal(
            stock_id=stock.id,
            signal_date=date(2026, 4, 17),
            signal_type=SignalType.RAPID_DECLINE.value,
            score=90,
            grade="A",
            detail={},
        )
    )

    pref_calls = {"count": 0}
    original = NotificationPreferenceRepository.get_or_create

    async def spy(self):  # type: ignore[no-untyped-def]
        pref_calls["count"] += 1
        return await original(self)

    monkeypatch.setattr(NotificationPreferenceRepository, "get_or_create", spy)

    sent = await NotificationService(session, _tele_disabled()).notify_signals([signal])

    assert sent == 0
    assert pref_calls["count"] == 0, "Telegram 비활성 시 pref 조회는 0회"


@pytest.mark.asyncio
async def test_partial_send_failure_counts_successes_only(session: AsyncSession) -> None:
    """3건 중 2번째만 Telegram API 실패 → sent=2, 모든 건 시도(루프 계속)."""
    stock_repo = StockRepository(session)
    stocks = [
        await stock_repo.add(Stock(stock_code=f"44000{i}", stock_name=f"부분실패{i}", market_type="KOSPI"))
        for i in range(3)
    ]
    await NotificationPreferenceRepository(session).get_or_create()

    sig_repo = SignalRepository(session)
    signals = [
        await sig_repo.add(
            Signal(
                stock_id=s.id,
                signal_date=date(2026, 4, 17),
                signal_type=SignalType.RAPID_DECLINE.value,
                score=85,
                grade="A",
                detail={},
            )
        )
        for s in stocks
    ]

    call_count = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] == 2:
            # 두 번째 호출만 500 — httpx.raise_for_status 가 HTTPError 로 처리
            return httpx.Response(500, json={"ok": False, "description": "server err"})
        return httpx.Response(200, json={"ok": True, "result": {"message_id": call_count["n"]}})

    async with _tele(httpx.MockTransport(handler)) as tele:
        sent = await NotificationService(session, tele).notify_signals(signals)

    assert sent == 2, "3건 중 2건 성공 (2번째만 실패)"
    assert call_count["n"] == 3, "실패해도 다음 시그널 계속 시도"


@pytest.mark.asyncio
async def test_empty_signals_short_circuits_before_db(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """signals=[] 면 pref/stock 조회 없이 0 반환 — DB 라운드트립 낭비 방지."""
    pref_calls = {"count": 0}
    original = NotificationPreferenceRepository.get_or_create

    async def spy(self):  # type: ignore[no-untyped-def]
        pref_calls["count"] += 1
        return await original(self)

    monkeypatch.setattr(NotificationPreferenceRepository, "get_or_create", spy)

    # Telegram 활성 상태이지만 signals 가 비어있으면 early return
    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("빈 signals 에서 Telegram 호출되면 안 됨")
        return httpx.Response(200)  # unreachable

    async with _tele(httpx.MockTransport(handler)) as tele:
        sent = await NotificationService(session, tele).notify_signals([])

    assert sent == 0
    assert pref_calls["count"] == 0
