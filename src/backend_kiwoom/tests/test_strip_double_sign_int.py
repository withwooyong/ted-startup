"""_strip_double_sign_int 헬퍼 (C-2α).

설계: endpoint-10-ka10086.md § 3.6 + § 11.1 #1.

가설 B 채택 (사용자 결정): `--714` → -714 (이중 음수 표시 부호 + 음수 값).
운영 검증 후 가설 A/B 확정 — 본 chunk 는 가설 B 구현.

검증:
- 정상 부호: "+693" → 693, "-714" → -714
- 이중 부호: "--714" → -714 (가설 B), "++714" → 714
- zero-padded: "00136000" → 136000
- 천단위 콤마: "1,234" → 1234
- 빈/잘못 입력: "", "-", "+", "--", "abc" → None
- BIGINT overflow: "9" * 30 → None (`_to_int` 가드 일관)
"""

from __future__ import annotations

import pytest

from app.adapter.out.kiwoom._records import _strip_double_sign_int


@pytest.mark.parametrize(
    ("inp", "expected"),
    [
        # 정상 단일 부호
        ("+693", 693),
        ("-714", -714),
        ("693", 693),
        # 가설 B — 이중 음수 = 음수
        ("--714", -714),
        ("--12345", -12345),
        # 이중 양수
        ("++714", 714),
        # zero-padded
        ("00136000", 136000),
        ("+00136000", 136000),
        # 콤마
        ("1,234", 1234),
        ("-1,234,567", -1234567),
        # 0
        ("0", 0),
        ("+0", 0),
        ("-0", 0),
        # 공백 trim
        ("  +693  ", 693),
    ],
)
def test_strip_double_sign_int_valid(inp: str, expected: int) -> None:
    assert _strip_double_sign_int(inp) == expected


@pytest.mark.parametrize(
    "inp",
    ["", "-", "+", "--", "++", "abc", "   ", "--abc"],
)
def test_strip_double_sign_int_returns_none(inp: str) -> None:
    assert _strip_double_sign_int(inp) is None


def test_strip_double_sign_int_bigint_overflow_returns_none() -> None:
    """`_to_int` BIGINT 가드 일관 — 거대 숫자 None."""
    huge = "9" * 30
    assert _strip_double_sign_int(huge) is None
    assert _strip_double_sign_int(f"--{huge}") is None
