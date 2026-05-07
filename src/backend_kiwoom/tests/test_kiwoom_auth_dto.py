"""KiwoomCredentials / IssuedToken / Mask 함수 단위 테스트."""

from __future__ import annotations

import copy
import json
import pickle
from dataclasses import asdict
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
# ADR-0001 § 3 #2 — 직렬화 우회 차단 (다층 방어)
# -----------------------------------------------------------------------------


def test_kiwoom_credentials_pickle_blocked() -> None:
    """pickle.dumps 가 secretkey 를 byte-stream 으로 평문 직렬화 — 차단 필수.

    `__reduce_ex__` raise 가 1차 방어. 디스크/네트워크 직렬화는 절대 허용 안 함.
    """
    creds = KiwoomCredentials(appkey="k", secretkey="REAL-SECRET-VALUE-12345")
    with pytest.raises(TypeError, match="serialization|직렬화"):
        pickle.dumps(creds)


def test_kiwoom_credentials_asdict_result_masked_by_logger() -> None:
    """asdict 호출은 dataclass 표준 인터페이스 — raise 하지 않음.
    하지만 결과 dict 가 logger 로 흘러가도 structlog `_scan` 이 secretkey 키를 [MASKED] 로 치환.

    2차 방어: 운영 환경의 모든 logger 호출이 mask_sensitive processor 를 거치므로
    asdict → logger 경로의 평문 누설을 차단.
    """
    from app.observability.logging import _scan

    creds = KiwoomCredentials(appkey="k-12345678", secretkey="REAL-SECRET-VALUE-12345")
    d = asdict(creds)
    # asdict 자체는 평문이 들어 있음 — 도메인 내부 사용 가능 (caller 책임)
    assert d["secretkey"] == "REAL-SECRET-VALUE-12345"
    # 그러나 logger 파이프라인 통과 시 자동 마스킹
    masked = _scan(d)
    assert masked["secretkey"] == "[MASKED]"
    assert "REAL-SECRET-VALUE-12345" not in repr(masked)


def test_kiwoom_credentials_copy_deepcopy_allowed() -> None:
    """copy/deepcopy 는 도메인 내부에서 정당한 복제 — 허용. `__copy__`/`__deepcopy__` 명시."""
    creds = KiwoomCredentials(appkey="k", secretkey="s")
    shallow = copy.copy(creds)
    deep = copy.deepcopy(creds)
    assert shallow == creds
    assert deep == creds


def test_kiwoom_credentials_str_does_not_expose_secret() -> None:
    """str() 결과에 secretkey 평문 없어야 함 (이미 __repr__ 마스킹 — 회귀 방어)."""
    creds = KiwoomCredentials(appkey="k", secretkey="VERY-REAL-SECRET-9999")
    assert "VERY-REAL-SECRET-9999" not in str(creds)


def test_kiwoom_credentials_json_dumps_default_blocked() -> None:
    """json.dumps(creds) 는 dataclass 를 직접 직렬화 못 해 TypeError."""
    creds = KiwoomCredentials(appkey="k", secretkey="REAL-SECRET-9999")
    with pytest.raises(TypeError):
        json.dumps(creds)


def test_kiwoom_credentials_vars_dict_blocked_by_slots() -> None:
    """vars(creds) 는 slots=True 인 dataclass 에서 TypeError — slots 의 자연 방어.

    회귀 방어: slots=True 옵션이 제거되면 이 테스트가 깨짐.
    """
    creds = KiwoomCredentials(appkey="k", secretkey="x")
    with pytest.raises(TypeError):
        vars(creds)


# -----------------------------------------------------------------------------
# CRITICAL-1 — __getstate__/__setstate__ 자동 생성 우회 차단 (Python 3.10+ slots)
# 적대적 리뷰 발견: dataclass(slots=True) 가 __getstate__ 를 자동 생성. jsonpickle/dill/Celery
# 같은 외부 직렬화 라이브러리가 __getstate__ 를 직접 호출하면 secretkey 평문 추출 가능.
# -----------------------------------------------------------------------------


def test_kiwoom_credentials_getstate_blocked() -> None:
    """`__getstate__()` 직접 호출 차단 — slots dataclass 자동 생성 메서드 우회 방어."""
    creds = KiwoomCredentials(appkey="k", secretkey="REAL-SECRET-VALUE-12345")
    with pytest.raises(TypeError, match="state extraction|state restoration|직렬화"):
        creds.__getstate__()


def test_kiwoom_credentials_setstate_blocked() -> None:
    """`__setstate__()` 직접 호출 차단 — 역직렬화 경로 객체 재구성 방어."""
    creds = KiwoomCredentials(appkey="k", secretkey="x")
    with pytest.raises(TypeError, match="state extraction|state restoration|직렬화"):
        creds.__setstate__(("k2", "s2"))


def test_kiwoom_credentials_copyreg_dispatch_table_known_limitation() -> None:
    """KNOWN LIMITATION: `copyreg.dispatch_table` 에 reducer 등록 시 직렬화 우회 가능.

    Pickler 는 type-level `dispatch_table` 을 인스턴스 `__reduce_ex__` 보다 우선 적용한다.
    운영 코드가 **의도적으로** dispatch_table 에 등록하는 경우만 발생 — 코드 리뷰에서 차단.
    위협 모델: 의도적 등록 시도는 본 PR 의 책임 영역 외 (외부 직렬화 사용 자체 금지).

    본 테스트는 한계를 회귀 표시 — Python pickle 동작이 변경되어 dispatch_table 보다
    `__reduce_ex__` 가 우선되면 이 테스트가 깨지고 limitation 해소를 알린다.
    """
    import copyreg

    creds = KiwoomCredentials(appkey="k", secretkey="REAL-SECRET")
    copyreg.dispatch_table[KiwoomCredentials] = lambda o: (
        KiwoomCredentials,
        (o.appkey, o.secretkey),
    )
    try:
        # 현재 동작: dispatch_table 우회로 pickle.dumps 성공. ADR-0001 § 3 known limitation.
        pickled = pickle.dumps(creds)
        assert pickled  # 우회됨을 명시 — Python 동작 변경 시 알림
    finally:
        copyreg.dispatch_table.pop(KiwoomCredentials, None)


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
