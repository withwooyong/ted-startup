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


def _clear_credential_envs(monkeypatch: pytest.MonkeyPatch) -> None:
    """4 명명 모두 격리 — 실 환경의 .env.prod 가 dotenv autoload 로 들어와 있을 수 있음."""
    for name in ("KIWOOM_APPKEY", "KIWOOM_SECRETKEY", "KIWOOM_API_KEY", "KIWOOM_API_SECRET"):
        monkeypatch.delenv(name, raising=False)


def test_read_credentials_from_env_missing_both(monkeypatch: pytest.MonkeyPatch) -> None:
    """4 환경변수 모두 비어있으면 None."""
    from scripts.register_credential import read_credentials_from_env

    _clear_credential_envs(monkeypatch)
    assert read_credentials_from_env() is None


def test_read_credentials_from_env_missing_secretkey(monkeypatch: pytest.MonkeyPatch) -> None:
    """secretkey 만 누락이어도 None."""
    from scripts.register_credential import read_credentials_from_env

    _clear_credential_envs(monkeypatch)
    monkeypatch.setenv("KIWOOM_APPKEY", "AKxxxx")
    assert read_credentials_from_env() is None


def test_read_credentials_from_env_both_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """둘 다 채워지면 (appkey, secretkey) 튜플 반환."""
    from scripts.register_credential import read_credentials_from_env

    _clear_credential_envs(monkeypatch)
    monkeypatch.setenv("KIWOOM_APPKEY", "AKxxxx")
    monkeypatch.setenv("KIWOOM_SECRETKEY", "SKyyyy")
    pair = read_credentials_from_env()
    assert pair == ("AKxxxx", "SKyyyy")


def test_read_credentials_strips_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """앞뒤 공백은 strip — 빈 문자열로 취급된 경우 None."""
    from scripts.register_credential import read_credentials_from_env

    _clear_credential_envs(monkeypatch)
    monkeypatch.setenv("KIWOOM_APPKEY", "   ")
    monkeypatch.setenv("KIWOOM_SECRETKEY", "SKyyyy")
    assert read_credentials_from_env() is None


def test_read_credentials_api_key_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """KIWOOM_API_KEY / KIWOOM_API_SECRET (공식 명명) fallback 동작."""
    from scripts.register_credential import read_credentials_from_env

    _clear_credential_envs(monkeypatch)
    monkeypatch.setenv("KIWOOM_API_KEY", "AKfromOfficial")
    monkeypatch.setenv("KIWOOM_API_SECRET", "SKfromOfficial")
    pair = read_credentials_from_env()
    assert pair == ("AKfromOfficial", "SKfromOfficial")


def test_read_credentials_appkey_takes_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    """KIWOOM_APPKEY 가 KIWOOM_API_KEY 보다 우선."""
    from scripts.register_credential import read_credentials_from_env

    _clear_credential_envs(monkeypatch)
    monkeypatch.setenv("KIWOOM_APPKEY", "preferred")
    monkeypatch.setenv("KIWOOM_API_KEY", "fallback")
    monkeypatch.setenv("KIWOOM_SECRETKEY", "preferred-sk")
    monkeypatch.setenv("KIWOOM_API_SECRET", "fallback-sk")
    pair = read_credentials_from_env()
    assert pair == ("preferred", "preferred-sk")
