"""app.application.exceptions — 애플리케이션 레이어 공유 예외 (Phase C R1).

설계: phase-c-refactor-r1-error-handling.md § 3.1.

3 도메인 (fundamental / OHLCV / daily_flow) 가 공유하는 예외만 본 모듈에 둔다.
domain-specific 예외 (예: TokenManager 의 CredentialNotFoundError) 는 해당 service
파일 안에 inline 정의 (token_service.py 패턴 일관).

설계 원칙:
- ValueError 상속 — 기존 `except ValueError` 를 호환 (router 가 점진적으로 새
  분기로 이동 중에도 기존 코드 깨지지 않음)
- `stock_code` 속성 노출 — 호출자가 메시지 파싱 없이 종목 코드 접근
- str(exc) 메시지 형식 안정 — 로그·테스트 회귀 보호 (`stock master not found: <code>`)
"""

from __future__ import annotations


class StockMasterNotFoundError(ValueError):
    """Stock 마스터에 존재하지 않는 stock_code 로 조회·갱신 시도.

    backward compat: ValueError 상속이라 기존 `except ValueError` 가 그대로 캐치.
    신규 분기는 `except StockMasterNotFoundError` 를 사용 (subclass first 순서).

    Attributes:
        stock_code: 미존재 종목 코드. 읽기 전용 권고 (Exception 클래스라
            __slots__ / frozen 강제 안 됨, 외부 mutation 가능하나 의도 외).
    """

    __slots__ = ("stock_code",)

    def __init__(self, stock_code: str) -> None:
        self.stock_code = stock_code
        super().__init__(f"stock master not found: {stock_code}")


__all__ = ["StockMasterNotFoundError"]
