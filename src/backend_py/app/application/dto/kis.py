"""KIS 도메인 DTO — application layer.

Hexagonal 원칙상 infra 가 UseCase 로 전달하는 값 객체는 application layer 에 소유.
adapter(`app/adapter/out/external/kis_client.py`) 는 여기서 정의된 타입을 import 해서
반환하고, application(UseCase) 은 adapter 를 모른 채 port + dto 만 참조.

이전 위치: `app/adapter/out/external/kis_client.py` (2026-04-22 이동).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class KisEnvironment(StrEnum):
    """KIS OpenAPI 호출 환경.

    MOCK 은 모의투자(openapivts) — `VTTC*` TR_ID 계열.
    REAL 은 실거래(openapi) — `TTTC*` TR_ID 계열.
    """

    MOCK = "mock"
    REAL = "real"


@dataclass(frozen=True, slots=True)
class KisCredentials:
    """KIS API 자격증명 — 생성자에서 주입받는 값 객체.

    `brokerage_account_credential` DB 저장소에서 Fernet 복호화해 이 DTO 를 조립.

    `__repr__` 는 app_secret/account_no 를 마스킹해 실수로 로그에 직렬화돼도
    평문이 남지 않게 함. `app_key` 는 마지막 4자리만 노출 (masked view 와 일치).
    """

    app_key: str
    app_secret: str
    account_no: str

    def __repr__(self) -> str:
        tail = self.app_key[-4:] if len(self.app_key) >= 4 else "****"
        return f"KisCredentials(app_key=••••{tail}, app_secret=<masked>, account_no=<masked>)"


@dataclass(slots=True)
class KisHoldingRow:
    """KIS 잔고 조회 결과의 종목별 row."""

    stock_code: str
    stock_name: str
    quantity: int
    avg_buy_price: Decimal
