"""ExchangeType StrEnum + build_stk_cd 헬퍼 (C-1α — Phase C 첫 도입).

설계: endpoint-06-ka10081.md § 2.4 / master.md § 3.4. B-γ-1 ADR § 14.5 deferred 결정.

검증:
1. ExchangeType StrEnum — KRX/NXT/SOR 3종 + value 일관
2. build_stk_cd — KRX `005930 → 005930` / NXT `005930 → 005930_NX` / SOR `005930 → 005930_AL`
3. build_stk_cd 가 잘못된 ExchangeType 입력 시 ValueError
4. build_stk_cd 가 빈 stock_code 거부
"""

from __future__ import annotations

import pytest

from app.adapter.out.kiwoom.stkinfo import build_stk_cd
from app.application.constants import ExchangeType


def test_exchange_type_has_three_members() -> None:
    """KRX/NXT/SOR 3종 — Phase C 진입 시 첫 도입."""
    assert ExchangeType.KRX.value == "KRX"
    assert ExchangeType.NXT.value == "NXT"
    assert ExchangeType.SOR.value == "SOR"


def test_exchange_type_is_str_enum() -> None:
    """StrEnum — `str(ExchangeType.KRX) == "KRX"` 는 아님 (Python 3.11+ StrEnum)."""
    assert isinstance(ExchangeType.KRX, str)
    assert ExchangeType.KRX == "KRX"


def test_build_stk_cd_krx_returns_base_code() -> None:
    """KRX: 005930 → 005930 (suffix 없음)."""
    assert build_stk_cd("005930", ExchangeType.KRX) == "005930"


def test_build_stk_cd_nxt_appends_nx_suffix() -> None:
    """NXT: 005930 → 005930_NX."""
    assert build_stk_cd("005930", ExchangeType.NXT) == "005930_NX"


def test_build_stk_cd_sor_appends_al_suffix() -> None:
    """SOR: 005930 → 005930_AL."""
    assert build_stk_cd("005930", ExchangeType.SOR) == "005930_AL"


def test_build_stk_cd_rejects_empty_stock_code() -> None:
    with pytest.raises(ValueError):
        build_stk_cd("", ExchangeType.KRX)


def test_build_stk_cd_rejects_invalid_format() -> None:
    """6자리 숫자 외 거부 (KRX-only 6자리 정책 일관, B-β 어댑터 패턴)."""
    for invalid in ("00593", "ABC123", "0059300", "005930_NX"):
        with pytest.raises(ValueError):
            build_stk_cd(invalid, ExchangeType.KRX)
