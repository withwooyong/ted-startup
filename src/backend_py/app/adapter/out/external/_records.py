"""외부 수집 결과 값 객체(원천 데이터).

어댑터 경계에서 프레임워크·드라이버에 독립된 Pydantic 모델을 주고받아
이후 Repository 업서트 단계에서 dict 로 변환한다(ORM 메타데이터 의존 제거).
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class _BaseRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StockPriceRow(_BaseRow):
    stock_code: str = Field(min_length=6, max_length=6)
    stock_name: str
    market_type: str
    close_price: int = Field(ge=0)
    open_price: int = Field(ge=0)
    high_price: int = Field(ge=0)
    low_price: int = Field(ge=0)
    volume: int = Field(ge=0)
    market_cap: int = Field(ge=0)
    change_rate: Decimal


class ShortSellingRow(_BaseRow):
    stock_code: str = Field(min_length=6, max_length=6)
    stock_name: str
    short_volume: int = Field(ge=0)
    short_amount: int = Field(ge=0)
    short_ratio: Decimal


class LendingBalanceRow(_BaseRow):
    stock_code: str = Field(min_length=6, max_length=6)
    stock_name: str
    balance_quantity: int = Field(ge=0)
    balance_amount: int = Field(ge=0)
