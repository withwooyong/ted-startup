"""TelegramClient 단위 테스트 — httpx.MockTransport 로 네트워크 없이 검증."""

from __future__ import annotations

import json

import httpx
import pytest

from app.adapter.out.external import TelegramClient
from app.config.settings import Settings


def _settings(token: str = "fake-token", chat_id: str = "-1001234567890") -> Settings:
    return Settings(telegram_bot_token=token, telegram_chat_id=chat_id)


@pytest.mark.asyncio
async def test_send_message_posts_correct_payload_and_returns_true() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    transport = httpx.MockTransport(handler)
    async with TelegramClient(_settings(), transport=transport) as client:
        ok = await client.send_message("<b>시그널</b>")

    assert ok is True
    assert "bot fake-token/sendMessage".replace(" ", "") in str(captured["url"]).replace("%20", "")
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["chat_id"] == "-1001234567890"
    assert body["text"] == "<b>시그널</b>"
    assert body["parse_mode"] == "HTML"


@pytest.mark.asyncio
async def test_send_message_no_op_when_token_missing() -> None:
    called = {"count": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        called["count"] += 1
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with TelegramClient(_settings(token="", chat_id="123"), transport=transport) as client:
        assert client.enabled is False
        ok = await client.send_message("ignored")

    assert ok is False
    assert called["count"] == 0


@pytest.mark.asyncio
async def test_send_message_returns_false_on_http_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"ok": False, "description": "Not Found"})

    transport = httpx.MockTransport(handler)
    async with TelegramClient(_settings(), transport=transport) as client:
        ok = await client.send_message("안녕")

    assert ok is False


@pytest.mark.asyncio
async def test_send_message_returns_false_when_api_returns_ok_false() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "description": "bot blocked"})

    transport = httpx.MockTransport(handler)
    async with TelegramClient(_settings(), transport=transport) as client:
        ok = await client.send_message("msg")

    assert ok is False
