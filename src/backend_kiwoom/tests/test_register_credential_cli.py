"""scripts/register_credential.py CLI — argparse + env 검증.

본 테스트는 CLI 진입점 — argparse / env 검증 + masked 출력. DB / Cipher 통합은 별도 e2e 검증.
"""

from __future__ import annotations

import pytest

# ---------- argparse ----------


def test_parse_args_alias_required() -> None:
    """--alias 필수."""
    from scripts.register_credential import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--env", "prod"])


def test_parse_args_env_required() -> None:
    """--env 필수."""
    from scripts.register_credential import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--alias", "x"])


def test_parse_args_env_choices() -> None:
    """--env 는 prod/mock 만."""
    from scripts.register_credential import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--alias", "x", "--env", "stage"])


# ---------- env 검증 ----------


def test_read_credentials_from_env_missing_both(monkeypatch: pytest.MonkeyPatch) -> None:
    """KIWOOM_APPKEY / KIWOOM_SECRETKEY 둘 다 비어있으면 None."""
    from scripts.register_credential import read_credentials_from_env

    monkeypatch.delenv("KIWOOM_APPKEY", raising=False)
    monkeypatch.delenv("KIWOOM_SECRETKEY", raising=False)
    assert read_credentials_from_env() is None


def test_read_credentials_from_env_missing_secretkey(monkeypatch: pytest.MonkeyPatch) -> None:
    """secretkey 만 누락이어도 None."""
    from scripts.register_credential import read_credentials_from_env

    monkeypatch.setenv("KIWOOM_APPKEY", "AKxxxx")
    monkeypatch.delenv("KIWOOM_SECRETKEY", raising=False)
    assert read_credentials_from_env() is None


def test_read_credentials_from_env_both_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """둘 다 채워지면 (appkey, secretkey) 튜플 반환."""
    from scripts.register_credential import read_credentials_from_env

    monkeypatch.setenv("KIWOOM_APPKEY", "AKxxxx")
    monkeypatch.setenv("KIWOOM_SECRETKEY", "SKyyyy")
    pair = read_credentials_from_env()
    assert pair == ("AKxxxx", "SKyyyy")


def test_read_credentials_strips_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """앞뒤 공백은 strip — 빈 문자열로 취급된 경우 None."""
    from scripts.register_credential import read_credentials_from_env

    monkeypatch.setenv("KIWOOM_APPKEY", "   ")
    monkeypatch.setenv("KIWOOM_SECRETKEY", "SKyyyy")
    assert read_credentials_from_env() is None
