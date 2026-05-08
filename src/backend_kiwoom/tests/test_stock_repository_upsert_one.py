"""StockRepository.upsert_one (B-β 추가) — 단건 upsert + RETURNING.

기존 upsert_many 가 "다건 + 영향받은 row 수" 를 반환하는 반면, upsert_one 은 단건
보강용으로 **갱신된 Stock ORM row 자체를 반환**해야 한다 (id, fetched_at, updated_at
포함). ka10100 의 lazy fetch / refresh 흐름이 caller 에 즉시 row 를 돌려주기 위함.

검증:
1. INSERT 시 id 채워진 Stock 반환
2. UPDATE 시 같은 id, 모든 도메인 필드 갱신, fetched_at >= 이전
3. is_active=False 행이 등장 → is_active=True 복원
4. 같은 stock_code 두 번 호출 → 같은 row 반환 (race 시 ON CONFLICT 흡수 시뮬)
5. NormalizedStock dataclass 직접 입력 (시그니처 검증)
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom.stkinfo import NormalizedStock
from app.adapter.out.persistence.repositories.stock import StockRepository


def _normalized(
    stock_code: str = "005930",
    stock_name: str = "삼성전자",
    market_code: str = "0",
    *,
    nxt_enable: bool = True,
    last_price: int | None = 70000,
    list_count: int | None = 5969782550,
) -> NormalizedStock:
    return NormalizedStock(
        stock_code=stock_code,
        stock_name=stock_name,
        list_count=list_count,
        audit_info="정상",
        listed_date=date(1975, 6, 11),
        last_price=last_price,
        state="정상",
        market_code=market_code,
        market_name="거래소",
        up_name="전기전자",
        up_size_name="대형주",
        company_class_name="",
        order_warning="0",
        nxt_enable=nxt_enable,
        requested_market_type=market_code,
    )


@pytest.mark.asyncio
async def test_upsert_one_inserts_returns_stock_with_id(session: AsyncSession) -> None:
    repo = StockRepository(session)
    stock = await repo.upsert_one(_normalized("005930"))

    assert stock.id is not None
    assert stock.stock_code == "005930"
    assert stock.stock_name == "삼성전자"
    assert stock.is_active is True
    assert stock.nxt_enable is True
    assert stock.list_count == 5969782550


@pytest.mark.asyncio
async def test_upsert_one_updates_existing_returns_same_id(session: AsyncSession) -> None:
    repo = StockRepository(session)
    initial = await repo.upsert_one(_normalized("005930", last_price=70000))
    initial_id = initial.id
    initial_fetched = initial.fetched_at

    updated = await repo.upsert_one(_normalized("005930", stock_name="삼성전자(갱신)", last_price=75800))

    assert updated.id == initial_id, "같은 row — UPDATE"
    assert updated.stock_name == "삼성전자(갱신)"
    assert updated.last_price == 75800
    assert updated.fetched_at >= initial_fetched


@pytest.mark.asyncio
async def test_upsert_one_reactivates_inactive_stock(session: AsyncSession) -> None:
    """비활성화된 row 가 다시 등장하면 is_active=TRUE 복원."""
    repo = StockRepository(session)
    await repo.upsert_one(_normalized("005930"))
    await repo.deactivate_missing("0", {"000660"})  # 005930 비활성화

    inactive_rows = await repo.list_by_filters(market_code="0", only_active=False)
    assert inactive_rows[0].is_active is False

    refreshed = await repo.upsert_one(_normalized("005930"))
    assert refreshed.is_active is True


@pytest.mark.asyncio
async def test_upsert_one_idempotent_double_call(session: AsyncSession) -> None:
    """같은 입력 두 번 호출 → 같은 row, 두 번째 호출도 같은 row 반환."""
    repo = StockRepository(session)
    first = await repo.upsert_one(_normalized("005930"))
    second = await repo.upsert_one(_normalized("005930"))

    assert first.id == second.id

    all_rows = await repo.list_by_filters(only_active=False)
    assert len(all_rows) == 1


@pytest.mark.asyncio
async def test_upsert_one_persists_all_domain_fields(session: AsyncSession) -> None:
    """14 도메인 필드 모두 영속화 — null 안전."""
    repo = StockRepository(session)
    n = NormalizedStock(
        stock_code="000660",
        stock_name="SK하이닉스",
        list_count=728002365,
        audit_info=None,
        listed_date=None,
        last_price=None,
        state=None,
        market_code="0",
        market_name=None,
        up_name=None,
        up_size_name=None,
        company_class_name=None,
        order_warning="0",
        nxt_enable=False,
        requested_market_type="0",
    )

    stock = await repo.upsert_one(n)

    assert stock.stock_code == "000660"
    assert stock.list_count == 728002365
    assert stock.audit_info is None
    assert stock.listed_date is None
    assert stock.last_price is None
    assert stock.state is None
    assert stock.nxt_enable is False
