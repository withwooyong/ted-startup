"""Repository 공용 헬퍼."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


def rowcount_of(result: Any) -> int:
    """SQLAlchemy 2.0 async execute 결과에서 rowcount 안전 추출.

    반환형 `Result[Any]` 에는 .rowcount 가 없어 mypy attr-defined 에러가 난다.
    런타임은 INSERT/UPDATE/DELETE 시 CursorResult 를 반환하므로 getattr 로 우회.
    """
    try:
        return int(getattr(result, "rowcount", 0) or 0)
    except (TypeError, ValueError):
        return 0


async def _chunked_upsert(
    session: AsyncSession,
    statement_factory: Callable[[list[dict[str, Any]]], Any],
    rows: Sequence[dict[str, Any]],
    *,
    chunk_size: int = 1000,
) -> int:
    """bulk INSERT 를 `chunk_size` 단위로 split 후 합산 rowcount 반환.

    설계 근거 (plan doc § 13.2 #3·#5, 2026-05-13 D-1 follow-up):
    PostgreSQL wire protocol 의 query parameter 한도는 int16 = 32767 개.
    `INSERT ... VALUES (..), (..), ..` 로 N rows × M columns 를 한 번에 보내면
    `asyncpg.exceptions._base.InterfaceError: the number of query arguments cannot
    exceed 32767` 가 발생한다 (운영 ka20006 sector_daily 5-12 백필 8건 reproduce).
    본 helper 는 `chunk_size` 만큼씩 잘라 statement_factory 로 statement 를 만들고
    `session.execute` 로 실행. 모든 chunk 가 단일 caller session 안에서 수행되므로
    `session.begin()` 트랜잭션 경계는 caller 가 통제 — partial 실패 시 caller 가
    rollback 결정.

    Parameters:
        session: caller 가 관리하는 AsyncSession (트랜잭션 경계 유지).
        statement_factory: `list[dict]` (chunk) 를 받아 `Executable` (예:
            `pg_insert(...).values(chunk).on_conflict_do_update(...)`) 를 반환.
            **stateless 보장 필수** (2a 2R M-2): factory 가 외부 상태를 캡처하지 않고
            매 호출마다 입력 chunk 만으로 statement 를 새로 생성해야 함. `excluded`
            바인딩 등 chunk 별로 다시 묶여야 하는 SQLAlchemy 객체는 factory 내부에서
            `pg_insert(...).values(chunk)` 새로 호출.
        rows: 전체 normalized row sequence. 빈 sequence 면 즉시 0 반환.
        chunk_size: 각 chunk 의 row 수. 디폴트 1000 — 평균 13 col 기준
            1000 × 13 = 13000 < 32767 안전 마진. column 수가 많은 모델 (예:
            stock_daily_flow 12 col / sector_price_daily 8 col) 도 1000 × 22 =
            22000 < 32767 안전.

    Raises:
        ValueError: `n_cols × chunk_size > 32767` (2b 2R M-1) — 미래 schema growth
            로 col 수가 33+ 가 되면 chunk_size=1000 으로도 한도 초과. silent
            breakage 차단 — fail-fast 로 caller 가 chunk_size 를 낮추도록 강제.

    반환: 모든 chunk 의 rowcount 합산.
    """
    if not rows:
        return 0

    # 2b 2R M-1 — column 수 × chunk_size 가 PostgreSQL int16 한도 초과 시 fail-fast.
    # docstring 가정 ("13 col / 22 col 까지 안전") 을 강제하여 미래 schema growth 시
    # 동일 InterfaceError 가 silently 재발하는 것을 차단.
    n_cols = len(rows[0])
    if n_cols * chunk_size > 32767:
        raise ValueError(
            f"_chunked_upsert: n_cols={n_cols} × chunk_size={chunk_size} = "
            f"{n_cols * chunk_size} > 32767 (PostgreSQL wire protocol int16 한도). "
            f"chunk_size 를 {32767 // n_cols} 이하로 낮추거나 schema 검토 필요."
        )

    total = 0
    for offset in range(0, len(rows), chunk_size):
        chunk = list(rows[offset : offset + chunk_size])
        stmt = statement_factory(chunk)
        result = await session.execute(stmt)
        total += rowcount_of(result)
    return total
