"""Telegram Bot API 어댑터.

- 토큰/채팅ID 중 하나라도 비어 있으면 어떤 호출이든 **no-op** 으로 동작(로컬/테스트 안전).
- HTML parse_mode 는 현 Java TelegramClient 와 동일한 계약 유지.
- httpx.AsyncClient 를 재사용하되 테스트에서 MockTransport 주입 가능.
"""
from __future__ import annotations

import logging

import httpx

from app.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramClient:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        s = settings or get_settings()
        self._bot_token = s.telegram_bot_token
        self._chat_id = s.telegram_chat_id
        self._enabled = bool(self._bot_token and self._chat_id)
        timeout = httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0)
        self._client = httpx.AsyncClient(timeout=timeout, transport=transport)

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def send_message(self, text: str, *, parse_mode: str = "HTML") -> bool:
        """메시지 전송. 비활성 상태면 False, 성공 시 True. 전송 실패는 로깅 후 False 반환(UseCase 비차단)."""
        if not self._enabled:
            logger.debug("Telegram 비활성 — 메시지 전송 생략")
            return False
        url = f"{TELEGRAM_API_BASE}/bot{self._bot_token}/sendMessage"
        payload = {"chat_id": self._chat_id, "text": text, "parse_mode": parse_mode}
        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            body = resp.json()
            if not body.get("ok", False):
                logger.warning("Telegram API 응답 ok=false: %s", body)
                return False
            return True
        except httpx.HTTPError as e:
            logger.warning("Telegram 발송 실패: %s", e)
            return False

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> TelegramClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()
