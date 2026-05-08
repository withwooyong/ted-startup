"""StockFundamentalRepository — kiwoom.stock_fundamental upsert + 조회 (B-γ-1).

설계: endpoint-05-ka10001.md § 6.2.

책임:
- upsert_one(row, *, stock_id) — PG ON CONFLICT (stock_id, asof_date, exchange) UPDATE.
  같은 날 여러 번 호출되면 마지막 호출의 일중 시세로 갱신 (멱등 보장).
  fundamental_hash 도 갱신 — 변경 감지용.
- find_latest(stock_id, *, exchange='KRX') — 가장 최근 asof_date row.
- compute_fundamental_hash(row) — PER/EPS/ROE/PBR/EV/BPS 6 필드 MD5
  (일중 시세 변동은 hash 영향 없음 — 외부 벤더 갱신만 검출).

KRX-only (§ 4.3) — exchange 파라미터는 'KRX' 디폴트. NXT/SOR 추가 시 enum 도입.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import StockFundamental

if TYPE_CHECKING:
    from app.adapter.out.kiwoom.stkinfo import NormalizedFundamental


# 변경 감지 hash 산출 대상 — PER/EPS/ROE/PBR/EV/BPS 6 필드 (외부 벤더 데이터).
# 일중 시세(E 카테고리) 는 매 호출 변동하므로 hash 에서 제외.
_FUNDAMENTAL_HASH_FIELDS: tuple[str, ...] = (
    "per_ratio",
    "eps_won",
    "roe_pct",
    "pbr_ratio",
    "ev_ratio",
    "bps_won",
)


def _hash_part(value: Decimal | int | None) -> str:
    """hash 입력 정규화 — Decimal / int / None 을 같은 string 으로.

    `Decimal("15.20")` 과 `Decimal("15.2")` 는 다른 객체지만 같은 값 — `normalize()` +
    `format("f")` 로 표현 정규화 (§ 11.2 알려진 위험). `format("g")` 는 거대 값에서
    지수 표기 (`"1.5e+4"`) 가 나오므로 절대 사용 금지.

    finite 검증은 `_to_decimal` 단계에서 이미 통과 — sNaN/Infinity 는 여기까지 안 옴.
    """
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    return str(value)


def compute_fundamental_hash(row: NormalizedFundamental) -> str:
    """PER/EPS/ROE/PBR/EV/BPS 6 필드 MD5 (CHAR(32)).

    - 일중 시세 변경 → 같은 hash (외부 벤더 갱신만 검출)
    - PER 등 1개 필드 변경 → 다른 hash
    - 6 필드 모두 None → stable hash (외부 벤더 미공급 종목)
    """
    payload = "|".join(_hash_part(getattr(row, field)) for field in _FUNDAMENTAL_HASH_FIELDS)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


class StockFundamentalRepository:
    """ka10001 펀더멘털 영속 계층."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_one(
        self,
        row: NormalizedFundamental,
        *,
        stock_id: int,
        expected_stock_code: str | None = None,
    ) -> StockFundamental:
        """단건 upsert — RETURNING 으로 갱신된 StockFundamental 반환.

        ON CONFLICT (stock_id, asof_date, exchange) DO UPDATE — 같은 날 여러 호출도
        멱등. fundamental_hash 도 갱신. caller 가 즉시 row(.id, .fetched_at) 사용.

        populate_existing — UPDATE 시 session identity map 의 stale row 를
        RETURNING 값으로 덮어씀 (B-β `upsert_one` 패턴 일관).

        **invariant 검증 (B-γ-1 2R B-H2)**: caller 가 `expected_stock_code` 를 넘기면
        `row.stock_code` 와 일치 확인. caller 가 `Stock.find_by_code(suffix_stripped)`
        후 받은 stock_id 와 row 의 stock_code 가 어긋나면 orphaned/cross-link row
        생성 위험 — 본 cross-check 가 fail-closed 안전망. 미지정 시 caller 책임.

        **명시 update_set (B-γ-1 2R B-H3)**: 미래 컬럼 추가 시 silent contract change
        방지. 컬럼 추가 시 본 list 도 수동 갱신 강제 (Stock repository 패턴 일관).
        """
        if expected_stock_code is not None and expected_stock_code != row.stock_code:
            raise ValueError(
                f"stock_code mismatch — expected={expected_stock_code!r}, row={row.stock_code!r}. "
                "caller 가 Stock.find_by_code(strip_kiwoom_suffix(stk_cd)) 결과의 stock_id 를 사용하지 않음"
            )

        values: dict[str, Any] = asdict(row)
        # NormalizedFundamental.stock_code 는 영속화 안 함 (FK 는 stock_id 로 표현).
        # NormalizedFundamental.stock_name 도 영속화 안 함 (Stock 마스터에 존재 — § 6.3 mismatch alert).
        values.pop("stock_code", None)
        values.pop("stock_name", None)

        values["stock_id"] = stock_id
        values["fundamental_hash"] = compute_fundamental_hash(row)

        insert_stmt = pg_insert(StockFundamental).values(**values)

        # B-γ-1 2R B-H3 — 명시 update_set (Stock repository 패턴 일관).
        # ON CONFLICT 키 (stock_id, asof_date, exchange) 는 갱신 안 함 (불변).
        # 미래 NormalizedFundamental 필드 추가 시 본 list 도 수동 갱신 필수 — schema-drift 차단.
        update_set: dict[str, Any] = {
            "settlement_month": insert_stmt.excluded.settlement_month,
            "face_value": insert_stmt.excluded.face_value,
            "face_value_unit": insert_stmt.excluded.face_value_unit,
            "capital_won": insert_stmt.excluded.capital_won,
            "listed_shares": insert_stmt.excluded.listed_shares,
            "market_cap": insert_stmt.excluded.market_cap,
            "market_cap_weight": insert_stmt.excluded.market_cap_weight,
            "foreign_holding_rate": insert_stmt.excluded.foreign_holding_rate,
            "replacement_price": insert_stmt.excluded.replacement_price,
            "credit_rate": insert_stmt.excluded.credit_rate,
            "circulating_shares": insert_stmt.excluded.circulating_shares,
            "circulating_rate": insert_stmt.excluded.circulating_rate,
            "per_ratio": insert_stmt.excluded.per_ratio,
            "eps_won": insert_stmt.excluded.eps_won,
            "roe_pct": insert_stmt.excluded.roe_pct,
            "pbr_ratio": insert_stmt.excluded.pbr_ratio,
            "ev_ratio": insert_stmt.excluded.ev_ratio,
            "bps_won": insert_stmt.excluded.bps_won,
            "revenue_amount": insert_stmt.excluded.revenue_amount,
            "operating_profit": insert_stmt.excluded.operating_profit,
            "net_profit": insert_stmt.excluded.net_profit,
            "high_250d": insert_stmt.excluded.high_250d,
            "high_250d_date": insert_stmt.excluded.high_250d_date,
            "high_250d_pre_rate": insert_stmt.excluded.high_250d_pre_rate,
            "low_250d": insert_stmt.excluded.low_250d,
            "low_250d_date": insert_stmt.excluded.low_250d_date,
            "low_250d_pre_rate": insert_stmt.excluded.low_250d_pre_rate,
            "year_high": insert_stmt.excluded.year_high,
            "year_low": insert_stmt.excluded.year_low,
            "current_price": insert_stmt.excluded.current_price,
            "prev_compare_sign": insert_stmt.excluded.prev_compare_sign,
            "prev_compare_amount": insert_stmt.excluded.prev_compare_amount,
            "change_rate": insert_stmt.excluded.change_rate,
            "trade_volume": insert_stmt.excluded.trade_volume,
            "trade_compare_rate": insert_stmt.excluded.trade_compare_rate,
            "open_price": insert_stmt.excluded.open_price,
            "high_price": insert_stmt.excluded.high_price,
            "low_price": insert_stmt.excluded.low_price,
            "upper_limit_price": insert_stmt.excluded.upper_limit_price,
            "lower_limit_price": insert_stmt.excluded.lower_limit_price,
            "base_price": insert_stmt.excluded.base_price,
            "expected_match_price": insert_stmt.excluded.expected_match_price,
            "expected_match_volume": insert_stmt.excluded.expected_match_volume,
            "fundamental_hash": insert_stmt.excluded.fundamental_hash,
            "fetched_at": func.now(),
            "updated_at": func.now(),
        }

        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["stock_id", "asof_date", "exchange"],
            set_=update_set,
        ).returning(StockFundamental)

        result = await self._session.execute(
            upsert_stmt,
            execution_options={"populate_existing": True},
        )
        await self._session.flush()
        fundamental: StockFundamental = result.scalar_one()
        return fundamental

    async def find_latest(
        self,
        stock_id: int,
        *,
        exchange: str = "KRX",
    ) -> StockFundamental | None:
        """가장 최근 asof_date row — 백테스팅 진입점에서 종목 펀더멘털 조회용.

        exchange 파라미터 — 같은 종목의 KRX/NXT row 분리. B-γ-1 KRX-only 라
        디폴트는 'KRX' (Phase C 후 NXT 추가 시 caller 가 'NXT' 명시).
        """
        stmt = (
            select(StockFundamental)
            .where(
                StockFundamental.stock_id == stock_id,
                StockFundamental.exchange == exchange,
            )
            .order_by(StockFundamental.asof_date.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_by_stock_and_date(
        self,
        stock_id: int,
        asof_date: date,
        *,
        exchange: str = "KRX",
    ) -> StockFundamental | None:
        """특정 일자 row — backfill 멱등성 검증용."""
        stmt = (
            select(StockFundamental)
            .where(
                StockFundamental.stock_id == stock_id,
                StockFundamental.asof_date == asof_date,
                StockFundamental.exchange == exchange,
            )
            .execution_options(populate_existing=True)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
