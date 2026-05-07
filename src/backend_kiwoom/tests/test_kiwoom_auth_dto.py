"""KiwoomCredentials / IssuedToken / Mask 함수 단위 테스트."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.application.dto.kiwoom_auth import (
    IssuedToken,
    KiwoomCredentials,
    MaskedKiwoomCredentialView,
    mask_appkey,
    mask_secretkey,
)

KST = ZoneInfo("Asia/Seoul")


# -----------------------------------------------------------------------------
# KiwoomCredentials
# -----------------------------------------------------------------------------


def test_kiwoom_credentials_repr_masks_secretkey() -> None:
    creds = KiwoomCredentials(appkey="AxserEsdcredca12345678", secretkey="SUPER-SECRET-VALUE-123")
    rep = repr(creds)
    assert "SUPER-SECRET-VALUE-123" not in rep
    assert "AxserEsdcredca12345678" not in rep
    assert "<masked>" in rep
    assert "••••5678" in rep  # 마지막 4 글자만 노출, 앞은 마스킹


def test_kiwoom_credentials_repr_with_short_appkey() -> None:
    """appkey 가 4자 미만이면 '****' 로 마스킹."""
    creds = KiwoomCredentials(appkey="abc", secretkey="x" * 16)
    rep = repr(creds)
    assert "****" in rep


def test_kiwoom_credentials_equality() -> None:
    """frozen dataclass — 값 동등성."""
    a = KiwoomCredentials(appkey="k", secretkey="s")
    b = KiwoomCredentials(appkey="k", secretkey="s")
    assert a == b
    c = KiwoomCredentials(appkey="k2", secretkey="s")
    assert a != c


# -----------------------------------------------------------------------------
# IssuedToken
# -----------------------------------------------------------------------------


def test_issued_token_requires_tz_aware_expires_at() -> None:
    """tz-naive datetime 이면 ValueError — KST 응답 파싱 시 tzinfo 누락 방어."""
    naive = datetime(2026, 5, 7, 9, 0, 0)
    with pytest.raises(ValueError, match="tz-aware"):
        IssuedToken(token="t", token_type="bearer", expires_at=naive)


def test_issued_token_accepts_kst() -> None:
    expires = datetime(2026, 5, 7, 9, 0, 0, tzinfo=KST)
    token = IssuedToken(token="t", token_type="bearer", expires_at=expires)
    assert token.expires_at == expires


def test_issued_token_accepts_utc() -> None:
    expires = datetime(2026, 5, 7, 0, 0, 0, tzinfo=UTC)
    token = IssuedToken(token="t", token_type="bearer", expires_at=expires)
    assert token.is_expired() is True  # 과거 시각


def test_issued_token_is_expired_with_margin() -> None:
    """만료 5분 전부터 expired=True."""
    soon = datetime.now(KST) + timedelta(seconds=60)  # 1분 후
    token = IssuedToken(token="t", token_type="bearer", expires_at=soon)
    assert token.is_expired(margin_seconds=300.0) is True
    assert token.is_expired(margin_seconds=10.0) is False


def test_issued_token_authorization_header_capitalize() -> None:
    expires = datetime.now(KST) + timedelta(hours=23)
    token = IssuedToken(token="WQJCwyqInph", token_type="bearer", expires_at=expires)
    assert token.authorization_header() == "Bearer WQJCwyqInph"

    token2 = IssuedToken(token="x", token_type="BEARER", expires_at=expires)
    assert token2.authorization_header() == "Bearer x"


def test_issued_token_repr_masks_token() -> None:
    expires = datetime.now(KST) + timedelta(hours=23)
    token = IssuedToken(token="REAL-TOKEN-12345", token_type="bearer", expires_at=expires)
    rep = repr(token)
    assert "REAL-TOKEN-12345" not in rep
    assert "<masked>" in rep


# -----------------------------------------------------------------------------
# Mask functions
# -----------------------------------------------------------------------------


def test_mask_appkey_keeps_tail_4() -> None:
    assert mask_appkey("AxserEsdcredca-FULL-APPKEY-1234") == "•••••••••••••••••••••••••••" + "1234"


def test_mask_appkey_short_input() -> None:
    """길이가 keep 보다 짧거나 같으면 전체 마스킹."""
    assert mask_appkey("abc") == "•••"
    assert mask_appkey("abcd") == "••••"


def test_mask_appkey_custom_keep() -> None:
    assert mask_appkey("ABCDEFGH", keep=2) == "••••••GH"


def test_mask_secretkey_returns_fixed_length() -> None:
    """secretkey 는 어떤 입력이든 고정 길이 마스킹."""
    assert mask_secretkey("a") == "•" * 16
    assert mask_secretkey("very-long-secret-12345678") == "•" * 16
    assert mask_secretkey("") == "•" * 16


# -----------------------------------------------------------------------------
# MaskedKiwoomCredentialView
# -----------------------------------------------------------------------------


def test_masked_view_dataclass() -> None:
    view = MaskedKiwoomCredentialView(
        alias="prod-main",
        env="prod",
        appkey_masked="••••••••1234",
        secretkey_masked="•" * 16,
        is_active=True,
        key_version=1,
    )
    assert view.alias == "prod-main"
    assert view.env == "prod"
    assert view.is_active is True
