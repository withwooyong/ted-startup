"""시그널 알림 오케스트레이터.

NotificationPreference 에 따라 대상 시그널을 필터링(min_score, signal_types)하고
Telegram 으로 발송한다. Telegram 비활성 시 no-op 반환.
"""
from __future__ import annotations

import html
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

# 사용자 노출용 한글 라벨(개발용 enum 문자열을 그대로 보여주지 않음).
_SIGNAL_TYPE_LABEL: dict[str, str] = {
    "RAPID_DECLINE": "대차잔고 급감",
    "TREND_REVERSAL": "추세전환",
    "SHORT_SQUEEZE": "숏스퀴즈",
}


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

        # 벌크 조회로 N+1 제거 — 시그널 수만큼 DB 왕복하던 패턴 교체
        stock_ids = list({s.stock_id for s in filtered})
        stocks_by_id = {s.id: s for s in await stock_repo.list_by_ids(stock_ids)}

        sent = 0
        for sig in filtered:
            stock = stocks_by_id.get(sig.stock_id)
            stock_name = stock.stock_name if stock else f"ID-{sig.stock_id}"
            text = self._format(sig, stock_name)
            if await self._telegram.send_message(text):
                sent += 1
        logger.info("알림 발송: 대상=%d 성공=%d", len(filtered), sent)
        return sent

    @staticmethod
    def _format(signal: Signal, stock_name: str) -> str:
        """Telegram HTML parse_mode 기준 안전 포매팅.
        사용자 데이터(종목명)는 html.escape 로 이스케이프해 parse 오류·인젝션 차단.
        """
        safe_name = html.escape(stock_name, quote=False)
        label = _SIGNAL_TYPE_LABEL.get(signal.signal_type, signal.signal_type)
        safe_label = html.escape(label, quote=False)
        return (
            f"<b>[{safe_label}] {safe_name}</b>\n"
            f"등급 {signal.grade} · 점수 {signal.score}\n"
            f"날짜 {signal.signal_date.isoformat()}"
        )
