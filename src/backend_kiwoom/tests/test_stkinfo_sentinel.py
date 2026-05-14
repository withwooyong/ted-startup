"""Phase F-1 — SentinelStockCodeError 신설 TDD (Step 0, red).

_validate_stk_cd_for_lookup 가 sentinel 종목코드 (0000D0 / 0000H0 / 0070X0 / 26490K 등) 에 대해
SentinelStockCodeError 를 raise 하고, SentinelStockCodeError 가 ValueError 를 상속하는지 검증.

본 테스트는 구현 전 의도적으로 실패 (red) — Step 1 구현 후 green 전환 대상.

계획서 § 4 결정 #4:
- sentinel detect → 새 exception type SentinelStockCodeError(ValueError)
- service layer 가드 분기 명확. ValueError 상속 → 기존 caller 호환 유지

계획서 § 5.1 변경:
- app/adapter/out/kiwoom/stkinfo.py — SentinelStockCodeError(ValueError) 추가,
  _validate_stk_cd_for_lookup 가 ValueError → SentinelStockCodeError 로 변경
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# 가드 — SentinelStockCodeError 는 아직 존재하지 않음 → import 실패 = red
# ---------------------------------------------------------------------------


def test_sentinel_stock_code_error_exists_in_stkinfo() -> None:
    """SentinelStockCodeError 가 stkinfo 모듈에 존재해야 함 (현재 미존재 → ImportError = red)."""
    from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError  # noqa: F401 — red


def test_sentinel_stock_code_error_is_subclass_of_value_error() -> None:
    """SentinelStockCodeError 는 ValueError 의 하위 클래스여야 함.

    기존 except ValueError: 블록이 SentinelStockCodeError 도 잡도록 보장 (caller 호환).
    """
    from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError

    assert issubclass(SentinelStockCodeError, ValueError), (
        "SentinelStockCodeError 는 ValueError 상속 필수 — 기존 caller except ValueError: 호환"
    )


def test_sentinel_stock_code_error_is_catchable_as_value_error() -> None:
    """SentinelStockCodeError 인스턴스를 except ValueError: 로 잡을 수 있어야 함."""
    from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError

    caught = False
    try:
        raise SentinelStockCodeError("0000D0")
    except ValueError:
        caught = True

    assert caught, "except ValueError: 로 SentinelStockCodeError 캐치 실패 — 상속 미설정"


# ---------------------------------------------------------------------------
# _validate_stk_cd_for_lookup — sentinel 패턴 거부 시 SentinelStockCodeError raise
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stk_cd",
    [
        "0000D0",  # NXT 우선주 sentinel — 5-13 18:00 cron 실패 확인
        "0000H0",  # NXT 우선주 sentinel — 5-13 18:00 cron 실패 확인
        "0000J0",  # NXT 우선주 sentinel 패턴 (plan § 2.3)
        "0000Y0",  # NXT 우선주 sentinel 패턴
        "0000Z0",  # NXT 우선주 sentinel 패턴
    ],
)
def test_validate_stk_cd_for_lookup_raises_sentinel_error_for_nxt_pattern(stk_cd: str) -> None:
    """NXT 우선주 sentinel (4자리 0 + 1문자 + 1자리 0) — SentinelStockCodeError raise.

    계획서 § 2.3: 0000D0 / 0000H0 / 0000J0 / 0000Y0 / 0000Z0 = sentinel pattern.
    현재 구현은 ValueError raise — SentinelStockCodeError 로 변경 필요 (Step 1).
    """
    from app.adapter.out.kiwoom.stkinfo import (
        SentinelStockCodeError,
        _validate_stk_cd_for_lookup,
    )

    with pytest.raises(SentinelStockCodeError, match=stk_cd[:6]):
        _validate_stk_cd_for_lookup(stk_cd)


@pytest.mark.parametrize(
    "stk_cd",
    [
        "26490K",  # KRX 우선주 K suffix (plan § 2.3)
        "28513K",  # KRX 우선주 K suffix
        "0070X0",  # ETN X suffix 종목 (5-13 cron 실패 확인 종목)
    ],
)
def test_validate_stk_cd_for_lookup_raises_sentinel_error_for_alpha_suffix(stk_cd: str) -> None:
    """영숫자 suffix 종목 (K/X suffix) — SentinelStockCodeError raise.

    계획서 § 2.3: 동일 ValueError → service layer 의도된 skip.
    현재 구현은 ValueError raise — SentinelStockCodeError 로 변경 필요 (Step 1).
    주의: 일반 ValueError 가 아닌 SentinelStockCodeError 임을 단언.
    """
    from app.adapter.out.kiwoom.stkinfo import (
        SentinelStockCodeError,
        _validate_stk_cd_for_lookup,
    )

    with pytest.raises(SentinelStockCodeError):
        _validate_stk_cd_for_lookup(stk_cd)


def test_validate_stk_cd_for_lookup_sentinel_error_carries_stock_code() -> None:
    """SentinelStockCodeError 는 sentinel 종목코드를 str() 메시지로 포함해야 함.

    운영자 로그 가시성: 어떤 sentinel 종목코드가 skip 됐는지 알 수 있어야 함.
    """
    from app.adapter.out.kiwoom.stkinfo import (
        SentinelStockCodeError,
        _validate_stk_cd_for_lookup,
    )

    with pytest.raises(SentinelStockCodeError) as exc_info:
        _validate_stk_cd_for_lookup("0000D0")

    # 예외 메시지에 종목코드 포함 확인
    assert "0000D0" in str(exc_info.value), (
        "SentinelStockCodeError 메시지에 sentinel 종목코드 포함 필요 (운영 로그 가시성)"
    )


# ---------------------------------------------------------------------------
# 정상 종목코드는 SentinelStockCodeError 가 아닌 정상 통과
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stk_cd",
    [
        "005930",  # 삼성전자 — 정상 6자리 숫자
        "000660",  # SK하이닉스
        "035720",  # 카카오
        "468760",  # 5-13 cron NUMERIC overflow 종목 (overflow 는 별개 문제)
    ],
)
def test_validate_stk_cd_for_lookup_does_not_raise_for_normal_stocks(stk_cd: str) -> None:
    """정상 6자리 숫자 종목코드 — SentinelStockCodeError / ValueError 미발생.

    회귀 보장: sentinel 감지 로직이 정상 종목을 오탐하지 않아야 함.
    """
    from app.adapter.out.kiwoom.stkinfo import _validate_stk_cd_for_lookup

    # 예외 없이 통과해야 함
    _validate_stk_cd_for_lookup(stk_cd)


# ---------------------------------------------------------------------------
# 기존 ValueError 호환 — 기존 테스트 패턴 회귀
# ---------------------------------------------------------------------------


def test_validate_stk_cd_for_lookup_still_raises_sentinel_error_as_value_error_for_short_code() -> None:
    """5자리 코드 — SentinelStockCodeError 또는 ValueError raise.

    기존 test_kiwoom_stkinfo_lookup 시나리오 7 (5자리 거부) 의 회귀.
    SentinelStockCodeError 가 ValueError 상속이라 except ValueError: 는 여전히 동작.
    단, 5자리는 sentinel 이 아니므로 일반 ValueError 일 수 있음 — 상속 관계만 단언.
    """
    from app.adapter.out.kiwoom.stkinfo import _validate_stk_cd_for_lookup

    with pytest.raises(ValueError):
        _validate_stk_cd_for_lookup("00593")
