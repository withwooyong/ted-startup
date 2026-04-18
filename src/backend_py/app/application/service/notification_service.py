"""시그널 알림 오케스트레이터.

NotificationPreference 에 따라 대상 시그널을 필터링(min_score, signal_types)하고
Telegram 으로 발송한다. Telegram 비활성 시 no-op 반환.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.external import TelegramClient
from app.adapter.out.persistence.models import Signal
from app.adapter.out.persistence.repositories import (
    NotificationPreferenceRepository,
    StockRepository,
)

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, session: AsyncSession, telegram: TelegramClient) -> None:
        self._session = session
        self._telegram = telegram

    async def notify_signals(self, signals: Sequence[Signal]) -> int:
        """설정을 반영해 필터링한 시그널을 개별 메시지로 전송. 성공 건수 반환."""
        if not signals or not self._telegram.enabled:
            return 0
        pref_repo = NotificationPreferenceRepository(self._session)
        stock_repo = StockRepository(self._session)
        pref = await pref_repo.get_or_create()

        enabled_types = set(pref.signal_types or [])
        filtered = [
            s for s in signals
            if s.score >= pref.min_score and s.signal_type in enabled_types
        ]
        if not filtered:
            return 0

        sent = 0
        for sig in filtered:
            stock = await stock_repo.get(sig.stock_id)
            text = self._format(sig, stock.stock_name if stock else str(sig.stock_id))
            if await self._telegram.send_message(text):
                sent += 1
        logger.info("알림 발송: 대상=%d 성공=%d", len(filtered), sent)
        return sent

    @staticmethod
    def _format(signal: Signal, stock_name: str) -> str:
        return (
            f"<b>[{signal.signal_type}] {stock_name}</b>\n"
            f"등급 {signal.grade} · 점수 {signal.score}\n"
            f"날짜 {signal.signal_date.isoformat()}"
        )
