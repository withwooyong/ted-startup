"""NotificationService — N+1 방어 + HTML 이스케이프 + 라벨 매핑 회귀 테스트."""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

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


@pytest.mark.asyncio
async def test_notify_signals_bulk_fetches_stocks_once(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    stock = await StockRepository(session).add(
        Stock(stock_code="123456", stock_name="A<b>&조작", market_type="KOSPI")
    )
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
    stock = await StockRepository(session).add(
        Stock(stock_code="654321", stock_name="테스트종목", market_type="KOSPI")
    )
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
