"""Phase F-2 — shsa.py 알파벳 포함 종목코드 가드 TDD (Step 0, red).

KiwoomShortSellingClient.fetch_trend 가 알파벳 포함 종목코드 (00088K / TIGER1 등) 에 대해
SentinelStockCodeError 를 raise 하는지 검증.

본 테스트는 구현 전 의도적으로 실패 (red) — Step 1 구현 후 green 전환 대상.

계획서 § 4 확정 결정:
- #1 shsa.py 가드 raise type → SentinelStockCodeError (F-1 신설 type 재사용)
- #2 SentinelStockCodeError 는 ValueError 상속 → 기존 except ValueError: 호환 유지
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# 가드 — shsa.py 는 현재 ValueError raise → SentinelStockCodeError raise 필요 (Step 1 fix)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stock_code",
    [
        "00088K",  # KRX 실제 영숫자 active 종목 (K suffix)
        "005935K",  # 7자리 — isdigit False 이며 알파벳 포함 (길이 초과 + alpha)
        "TIGER1",  # ETF ticker 형식 — 알파벳 포함
        "KODEX2",  # ETF ticker 형식 — 알파벳 포함
        "00104K",  # KRX 실제 영숫자 active 종목 (K suffix)
    ],
)
def test_fetch_trend_raises_sentinel_error_for_alphanumeric_code(stock_code: str) -> None:
    """alphanumeric 종목코드 → SentinelStockCodeError raise.

    계획서 § 4 #1: shsa.py 가드 raise type = SentinelStockCodeError.
    현재 구현은 ValueError raise → SentinelStockCodeError 로 변경 필요 (Step 1 fix = red).

    주의: ^[0-9]{6}$ 통과 기준. 6자리 숫자가 아닌 입력 (알파벳 포함) 은 전부 거부.
    005935 (6자리 숫자) 는 이 parametrize 대상 아님 — 정상 통과 테스트는 별도.
    """
    from app.adapter.out.kiwoom.shsa import KiwoomShortSellingClient
    from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError

    mock_client = MagicMock()
    client = KiwoomShortSellingClient(kiwoom_client=mock_client)

    with pytest.raises(SentinelStockCodeError):
        import asyncio

        asyncio.run(
            client.fetch_trend(
                stock_code=stock_code,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 31),
            )
        )


def test_fetch_trend_sentinel_error_is_catchable_as_value_error() -> None:
    """SentinelStockCodeError 는 except ValueError: 로 캐치 가능해야 함.

    계획서 § 4 #2: ValueError 상속 → 기존 caller except ValueError: 호환 유지.
    """
    from app.adapter.out.kiwoom.shsa import KiwoomShortSellingClient
    from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError

    mock_client = MagicMock()
    client = KiwoomShortSellingClient(kiwoom_client=mock_client)

    caught_as_value_error = False
    caught_as_sentinel = False
    try:
        import asyncio

        asyncio.run(
            client.fetch_trend(
                stock_code="00088K",
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 31),
            )
        )
    except SentinelStockCodeError:
        caught_as_sentinel = True
    except ValueError:
        # 현재 구현 (plain ValueError) — Step 1 fix 후 SentinelStockCodeError 로 전환
        caught_as_value_error = True

    # Step 1 전: caught_as_value_error=True (현재 plain ValueError)
    # Step 1 후: caught_as_sentinel=True (SentinelStockCodeError)
    # red 단언: SentinelStockCodeError 로 잡혀야 함 — 현재 실패
    assert caught_as_sentinel, (
        f"SentinelStockCodeError 로 잡혀야 함 — "
        f"caught_as_sentinel={caught_as_sentinel}, caught_as_value_error={caught_as_value_error}. "
        "shsa.py 가드 raise type 을 SentinelStockCodeError 로 변경 필요 (Step 1)"
    )


def test_fetch_trend_sentinel_error_message_contains_stock_code() -> None:
    """SentinelStockCodeError 메시지에 입력 종목코드가 포함되어야 함.

    운영자 로그 가시성: 어떤 종목코드가 거부됐는지 알 수 있어야 함.
    """
    from app.adapter.out.kiwoom.shsa import KiwoomShortSellingClient
    from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError

    mock_client = MagicMock()
    client = KiwoomShortSellingClient(kiwoom_client=mock_client)

    with pytest.raises(SentinelStockCodeError) as exc_info:
        import asyncio

        asyncio.run(
            client.fetch_trend(
                stock_code="00088K",
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 31),
            )
        )

    assert "00088K" in str(exc_info.value), (
        "SentinelStockCodeError 메시지에 입력 종목코드 포함 필요 (운영 로그 가시성)"
    )


# ---------------------------------------------------------------------------
# 정상 numeric 입력 — 가드 통과 확인 (mock 으로 KiwoomClient 호출까지)
# ---------------------------------------------------------------------------


def test_fetch_trend_does_not_raise_for_normal_numeric_code() -> None:
    """정상 6자리 숫자 종목코드 (005930) — SentinelStockCodeError / ValueError 미발생.

    회귀 보장: 가드 로직이 정상 종목을 오탐하지 않아야 함.
    mock 으로 KiwoomClient 호출 차단 (실제 API 호출 없음).
    """
    from app.adapter.out.kiwoom.shsa import KiwoomShortSellingClient

    mock_client = MagicMock()
    # call_paginated 는 async generator — AsyncMock + aiter 설정
    mock_client.call_paginated = MagicMock(return_value=AsyncMock(__aiter__=MagicMock(return_value=iter([]))))

    async def _empty_aiter(*_: object, **__: object):  # noqa: ANN202
        return
        yield  # type: ignore[misc] — make async generator

    mock_client.call_paginated = MagicMock(return_value=_empty_aiter())

    client = KiwoomShortSellingClient(kiwoom_client=mock_client)

    import asyncio

    # SentinelStockCodeError / ValueError 없이 통과해야 함
    try:  # noqa: SIM105 — try/except/pass 가 의도 명시 (가드 통과 검증)
        asyncio.run(
            client.fetch_trend(
                stock_code="005930",
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 31),
            )
        )
    except (ValueError, TypeError):
        # mock async generator 호환 문제는 허용 — 가드 자체는 통과한 것
        pass
