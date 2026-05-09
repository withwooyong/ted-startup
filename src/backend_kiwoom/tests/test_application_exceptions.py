"""app.application.exceptions — 공유 예외 회귀 테스트 (Phase C R1).

설계: phase-c-refactor-r1-error-handling.md § 3.1.

검증:
- StockMasterNotFoundError 가 ValueError 의 subclass — 기존 except ValueError 호환
- stock_code 속성 노출
- str(exc) 가 stock_code 포함 + 일관된 메시지 형식
"""

from __future__ import annotations

import pytest

from app.application.exceptions import StockMasterNotFoundError


def test_stock_master_not_found_is_value_error_subclass() -> None:
    """StockMasterNotFoundError 가 ValueError 의 subclass — 기존 except ValueError 호환."""
    exc = StockMasterNotFoundError("005930")
    assert isinstance(exc, ValueError)
    assert isinstance(exc, StockMasterNotFoundError)


def test_stock_master_not_found_exposes_stock_code() -> None:
    """stock_code 속성으로 종목 코드 노출."""
    exc = StockMasterNotFoundError("000660")
    assert exc.stock_code == "000660"


def test_stock_master_not_found_str_contains_stock_code() -> None:
    """str(exc) 가 stock_code 포함 + 안정 메시지 형식 (로그·테스트 회귀 보호)."""
    exc = StockMasterNotFoundError("035720")
    assert "035720" in str(exc)
    assert "stock master not found" in str(exc).lower()


def test_stock_master_not_found_caught_by_value_error() -> None:
    """except ValueError 가 StockMasterNotFoundError 를 캐치 (backward compat)."""
    caught: ValueError | None = None
    try:
        raise StockMasterNotFoundError("999999")
    except ValueError as exc:
        caught = exc

    assert caught is not None
    assert isinstance(caught, StockMasterNotFoundError)


def test_stock_master_not_found_raise_pattern() -> None:
    """pytest.raises 매칭 — 신규 분기 표준 패턴."""
    with pytest.raises(StockMasterNotFoundError) as ei:
        raise StockMasterNotFoundError("123456")
    assert ei.value.stock_code == "123456"


def test_value_error_first_except_swallows_subclass() -> None:
    """역방향 위험 회귀 — `except ValueError` 가 `except StockMasterNotFoundError` 보다
    먼저 오면 subclass 분기가 죽는다는 invariant 의 단위 증명.

    이 테스트는 router 의 except 순서 (subclass first) 가 깨지면 어떻게 되는지
    역방향으로 시뮬레이션한다. router 코드 변경 시 본 테스트는 그대로 PASS 하지만,
    리뷰어에게 "왜 subclass first 가 필수인가" 의 명시적 근거를 제공.
    """
    branch_taken: str = ""
    try:
        raise StockMasterNotFoundError("000000")
    except ValueError:
        branch_taken = "value_error"
    except StockMasterNotFoundError:  # type: ignore[unreachable]
        branch_taken = "stock_master"  # 도달 불가 — 위 ValueError 가 먼저 매칭

    # subclass 분기가 죽고 base 분기가 캐치됨을 단언 (역방향 invariant)
    assert branch_taken == "value_error"
