"""거래일 판정 — 주말 제외.

공휴일은 별도 라이브러리 없이 KRX 빈 응답으로 자연 폴백(Java 원본과 동일 전략).
향후 정밀 관리가 필요하면 `holidays` 패키지 도입하거나 KRX 공식 캘린더 엔드포인트 연동.
"""

from __future__ import annotations

from datetime import date


def is_trading_day(d: date) -> bool:
    """월(0)~금(4)만 True. 공휴일은 KRX 호출 결과로 자연 처리."""
    return d.weekday() < 5
