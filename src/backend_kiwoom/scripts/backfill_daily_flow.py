#!/usr/bin/env python
"""daily_flow (ka10086) 백필 CLI — IngestDailyFlowUseCase 1년 cap 우회 + 운영 차단 fix 패턴.

설계: phase-c-backfill-daily-flow.md.

`/api/kiwoom/daily-flow/sync` 라우터의 1년 cap 을 우회해 3년 백필 + NUMERIC magnitude 측정 도구.
OHLCV 백필 (`backfill_ohlcv.py`) 의 발견된 운영 차단 fix 3건 (since_date guard /
`--max-stocks` 정상 적용 / ETF 호환 가드) 을 처음부터 동일 패턴으로 내장.

사용 예:
    # 환경변수 (.env.prod 가 backend_kiwoom/ 또는 루트에 있으면 자동 로드)
    #   KIWOOM_DATABASE_URL='postgresql+asyncpg://kiwoom:kiwoom@localhost:5433/kiwoom_db'
    #   KIWOOM_CREDENTIAL_MASTER_KEY='Fernet32B...'

    # dry-run — 종목 수 + 호출 수 + 시간 추정만
    python scripts/backfill_daily_flow.py --years 3 --alias prod --dry-run

    # 실제 3년 백필
    python scripts/backfill_daily_flow.py --years 3 --alias prod

    # KOSPI 100 종목만 (디버그)
    python scripts/backfill_daily_flow.py --years 1 --alias prod \\
        --only-market-codes 0 --max-stocks 100

    # AMOUNT 모드 (백만원 단위 — 디폴트는 QUANTITY)
    python scripts/backfill_daily_flow.py --years 3 --alias prod --indc-mode amount

    # resume — 영업일 calendar 와 비교해 gap 0 (완전 적재) 인 종목 skip (R2)
    python scripts/backfill_daily_flow.py --years 3 --alias prod --resume

종료 코드:
    0: 모든 종목 success (failed = 0)
    1: 부분 실패 (failed > 0)
    2: 인자 검증 실패 / alias 미등록
    3: 시스템 오류 (DB 연결 실패 / settings 누락)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# .env.prod 자동 로드 — pydantic-settings 가 cwd 기준이라 backend_kiwoom 외부 실행 시 누락 방지.
for candidate in (ROOT / ".env.prod", ROOT.parent.parent / ".env.prod", ROOT / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=False)

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.adapter.out.kiwoom._client import KiwoomClient  # noqa: E402
from app.adapter.out.kiwoom.auth import KiwoomAuthClient  # noqa: E402
from app.adapter.out.kiwoom.mrkcond import KiwoomMarketCondClient  # noqa: E402
from app.adapter.out.persistence.models import Stock  # noqa: E402
from app.adapter.out.persistence.session import get_engine, get_sessionmaker  # noqa: E402
from app.application.constants import DailyMarketDisplayMode  # noqa: E402
from app.application.service.daily_flow_service import (  # noqa: E402
    DailyFlowSyncResult,
    IngestDailyFlowUseCase,
)
from app.application.service.token_service import TokenManager  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.security.kiwoom_credential_cipher import KiwoomCredentialCipher  # noqa: E402

logger = logging.getLogger("backfill_daily_flow")


# =============================================================================
# 인자 파서
# =============================================================================


def build_parser() -> argparse.ArgumentParser:
    """argparse 의 ArgumentParser 빌드 — 테스트용 분리."""
    parser = argparse.ArgumentParser(
        description="daily_flow (ka10086) 백필 CLI — IngestDailyFlowUseCase 1년 cap 우회",
    )
    parser.add_argument(
        "--alias",
        required=True,
        help="키움 자격증명 alias (DB 의 kiwoom_credential 에 등록된 값)",
    )
    parser.add_argument(
        "--years",
        type=int,
        default=3,
        help="백필 기간 (년). --start-date 명시 시 무시 (디폴트 3)",
    )
    parser.add_argument(
        "--start-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=None,
        help="시작일 YYYY-MM-DD. 명시 시 --years 무시",
    )
    parser.add_argument(
        "--end-date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=None,
        help="종료일 YYYY-MM-DD. 디폴트 today",
    )
    parser.add_argument(
        "--indc-mode",
        default="quantity",
        choices=["quantity", "amount"],
        help="ka10086 표시 단위 — quantity (수량, 디폴트) / amount (백만원)",
    )
    parser.add_argument(
        "--only-market-codes",
        type=str,
        default="",
        help="특정 시장만 sync (CSV, 예: '0,10'). 디폴트 전체 5 시장",
    )
    parser.add_argument(
        "--only-stock-codes",
        type=str,
        default="",
        help="특정 종목만 sync (CSV, 예: '005930,000660'). 디버그 용",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="추정값만 출력 (DB 적재 X)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="영업일 calendar 와 비교해 gap 0 (완전 적재) 인 종목 skip (R2)",
    )
    parser.add_argument(
        "--max-stocks",
        type=int,
        default=None,
        help="처음 N 종목만 처리 (디버그 용)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING"],
        help="logger 레벨",
    )
    return parser


def parse_csv_codes(value: str) -> list[str]:
    """CSV 문자열을 list[str] 로 — 빈 문자열은 빈 list."""
    if not value:
        return []
    return [c.strip() for c in value.split(",") if c.strip()]


def resolve_indc_mode(value: str) -> DailyMarketDisplayMode:
    """argparse string → DailyMarketDisplayMode."""
    if value == "quantity":
        return DailyMarketDisplayMode.QUANTITY
    if value == "amount":
        return DailyMarketDisplayMode.AMOUNT
    raise ValueError(f"invalid indc_mode: {value}")


# =============================================================================
# date range / 시간 추정 / format
# =============================================================================


def resolve_date_range(
    *,
    years: int,
    start_date: date | None,
    end_date: date | None,
) -> tuple[date, date]:
    """--years 또는 --start-date/--end-date 입력에서 (start, end) 결정.

    명시 start_date/end_date 가 우선. start > end 면 ValueError. OHLCV 백필 헬퍼와 동일.
    """
    end = end_date or date.today()
    start = start_date if start_date is not None else end - timedelta(days=365 * years)
    if start > end:
        raise ValueError(f"start ({start}) must be <= end ({end})")
    return start, end


def estimate_seconds(
    *,
    stocks: int,
    exchanges_per_stock: int,
    pages_per_call: int,
    rate_limit_seconds: float,
) -> float:
    """dry-run 시간 추정 (lower-bound). H-3 — ±50% margin 명시 필요."""
    total_calls = stocks * exchanges_per_stock * pages_per_call
    return total_calls * rate_limit_seconds


def format_duration(seconds: float) -> str:
    """0h 0m 0s 포맷."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours}h {minutes}m {secs}s"


# =============================================================================
# resume 판단
# =============================================================================


# daily_flow 영속화 테이블 (resume 시 trading_date 조회용)
_RESUME_TABLE: str = "kiwoom.stock_daily_flow"


async def compute_resume_remaining_codes(
    session: AsyncSession,
    *,
    start_date: date,
    end_date: date,
    candidate_codes: list[str],
) -> list[str]:
    """resume mode (R2 gap detection) — candidate_codes 중 [start_date, end_date] 의 영업일
    set 와 비교해 gap 1+ 또는 적재 0 인 종목만 반환.

    영업일 calendar = SELECT DISTINCT trading_date FROM kiwoom.stock_daily_flow (exchange='KRX')
    WHERE trading_date BETWEEN start AND end. NXT 는 KRX 와 일자 거의 동일하므로 KRX 기준.

    가드 (H-8): 영업일 set = ∅ → 모든 candidate 진행.

    R1 시점에는 `max(trading_date) >= end_date` 만 검사 — 부분 적재 (gap) 종목을 잘못 skip
    하던 한계를 R2 에서 일자별 차집합으로 정밀화.

    Returns:
        진행 대상 종목 코드 list. 모두 완전 적재면 빈 list.
    """
    from sqlalchemy import text

    # 1. 영업일 calendar — KRX 만 (NXT 는 KRX 와 일자 거의 동일)
    business_days_sql = text(
        f"""
        SELECT DISTINCT trading_date
        FROM {_RESUME_TABLE}
        WHERE exchange = 'KRX' AND trading_date BETWEEN :start AND :end
        """
    )
    bd_result = await session.execute(
        business_days_sql.bindparams(start=start_date, end=end_date)
    )
    business_days: set[date] = {row[0] for row in bd_result.fetchall()}

    if not business_days:
        logger.info(
            "[resume] 영업일 calendar 비어있음 (start=%s end=%s) — %d 종목 모두 진행",
            start_date,
            end_date,
            len(candidate_codes),
        )
        return list(candidate_codes)

    # 2. 종목별 trading_date set (KRX 만)
    per_stock_sql = text(
        f"""
        SELECT s.stock_code, p.trading_date
        FROM kiwoom.stock s
        LEFT JOIN {_RESUME_TABLE} p ON p.stock_id = s.id
            AND p.exchange = 'KRX'
            AND p.trading_date BETWEEN :start AND :end
        WHERE s.stock_code = ANY(:codes)
        """
    )
    ps_result = await session.execute(
        per_stock_sql.bindparams(codes=list(candidate_codes), start=start_date, end=end_date)
    )
    loaded_by_code: dict[str, set[date]] = {code: set() for code in candidate_codes}
    for row in ps_result.fetchall():
        code, td = row[0], row[1]
        if td is not None:
            loaded_by_code[code].add(td)

    remaining: list[str] = []
    skipped: list[str] = []
    for code in candidate_codes:
        loaded = loaded_by_code.get(code, set())
        gap = business_days - loaded
        if gap:
            remaining.append(code)
        else:
            skipped.append(code)

    if skipped:
        logger.info(
            "[resume] %d 종목 skip (gap 0 — 영업일 %d 모두 적재) — sample %s",
            len(skipped),
            len(business_days),
            skipped[:5],
        )
    return remaining


# =============================================================================
# Summary / exit code
# =============================================================================


def summary_to_exit_code(result: DailyFlowSyncResult) -> int:
    """failed = 0 → exit 0 (success), > 0 → exit 1 (partial)."""
    return 1 if result.failed > 0 else 0


def format_summary(
    *,
    indc_mode: DailyMarketDisplayMode,
    start: date,
    end: date,
    result: DailyFlowSyncResult,
    elapsed_seconds: float,
) -> str:
    """summary 출력 포맷."""
    avg_per_stock = (elapsed_seconds / result.total) if result.total > 0 else 0.0
    failure_ratio = (result.failed / result.total) if result.total > 0 else 0.0
    lines = [
        "===== Daily Flow Backfill Summary =====",
        f"indc_mode:     {indc_mode.name.lower()}",
        f"date range:    {start} ~ {end}",
        f"total:         {result.total} 종목",
        f"success_krx:   {result.success_krx}",
        f"success_nxt:   {result.success_nxt}",
        f"failed:        {result.failed} (ratio {failure_ratio:.2%})",
        f"elapsed:       {format_duration(elapsed_seconds)}",
        f"avg/stock:     {avg_per_stock:.1f}s",
    ]
    if result.errors:
        lines.append("errors (sample 10):")
        for err in result.errors[:10]:
            lines.append(f"  {err.stock_code} [{err.exchange}] {err.error_class}")
    return "\n".join(lines)


# =============================================================================
# dry-run
# =============================================================================


async def run_dry_run(
    *,
    use_case: Any,  # noqa: ANN401 — mock 또는 실제 UseCase
    active_stocks_count: int,
    nxt_enabled: bool,
    end_date: date,
    start_date: date,
    rate_limit_seconds: float,
) -> str:
    """dry-run 모드 — UseCase.execute 호출 안 함. 추정값만 반환.

    `use_case` 는 시그니처 호환 위해 받지만 사용 안 함 (테스트가 not_awaited 검증).
    """
    _ = use_case  # 명시적 미사용
    days = (end_date - start_date).days

    # ka10086: 22 필드라 페이지 row 수 ka10081 보다 적을 가능성 (~300 거래일 추정).
    # 3년 (~750 거래일) → 2~3 페이지
    pages_per_call = max(1, (days // 300) + (1 if days % 300 else 0))

    exchanges = 2 if nxt_enabled else 1
    seconds = estimate_seconds(
        stocks=active_stocks_count,
        exchanges_per_stock=exchanges,
        pages_per_call=pages_per_call,
        rate_limit_seconds=rate_limit_seconds,
    )

    return "\n".join(
        [
            "===== Dry-run 추정 (lower-bound, ±50% margin) =====",
            f"date range:    {start_date} ~ {end_date} ({days} days)",
            f"active stocks: {active_stocks_count}",
            f"NXT collection: {'enabled' if nxt_enabled else 'disabled'}",
            f"exchanges/stock: {exchanges}",
            f"pages/call:    {pages_per_call} (ka10086 1 page ~300 거래일 추정)",
            f"total calls:   {active_stocks_count * exchanges * pages_per_call}",
            f"rate limit:    {rate_limit_seconds}s/call",
            f"estimated:     {format_duration(seconds)} (실측 ±50% margin)",
            "",
            "[dry-run] DB 미적재. 실제 백필은 --dry-run 제거 후 재실행.",
        ]
    )


# =============================================================================
# active stock helpers
# =============================================================================


async def _count_active_stocks(
    session: AsyncSession,
    *,
    only_market_codes: list[str],
    only_stock_codes: list[str],
    max_stocks: int | None,
) -> int:
    """active stock 수 카운트 (dry-run + 실제 모두 사용)."""
    stmt = select(Stock).where(Stock.is_active.is_(True))
    if only_market_codes:
        stmt = stmt.where(Stock.market_code.in_(only_market_codes))
    if only_stock_codes:
        stmt = stmt.where(Stock.stock_code.in_(only_stock_codes))
    rows = (await session.execute(stmt)).scalars().all()
    if max_stocks is not None:
        return min(len(rows), max_stocks)
    return len(rows)


async def _list_active_stock_codes(
    session: AsyncSession,
    *,
    only_market_codes: list[str],
    only_stock_codes: list[str],
    max_stocks: int | None,
) -> list[str]:
    """active stock 의 stock_code list (resume 후보 조회)."""
    stmt = select(Stock.stock_code).where(Stock.is_active.is_(True))
    if only_market_codes:
        stmt = stmt.where(Stock.market_code.in_(only_market_codes))
    if only_stock_codes:
        stmt = stmt.where(Stock.stock_code.in_(only_stock_codes))
    stmt = stmt.order_by(Stock.market_code, Stock.stock_code)
    if max_stocks is not None:
        stmt = stmt.limit(max_stocks)
    return [row for row in (await session.execute(stmt)).scalars().all()]


# =============================================================================
# UseCase 빌드 (lifespan 외부)
# =============================================================================


@asynccontextmanager
async def _build_use_case(
    *,
    alias: str,
    indc_mode: DailyMarketDisplayMode,
) -> AsyncIterator[Any]:
    """TokenManager + KiwoomClient + KiwoomMarketCondClient + UseCase 빌드.

    `try/finally` 로 graceful close 보장 (H-6).
    """
    settings = get_settings()
    cipher = KiwoomCredentialCipher(master_key=settings.kiwoom_credential_master_key)
    sessionmaker = get_sessionmaker()

    @asynccontextmanager
    async def _session_provider() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as s:
            yield s

    def _auth_client_factory(base_url: str) -> KiwoomAuthClient:
        return KiwoomAuthClient(base_url=base_url)

    manager = TokenManager(
        session_provider=_session_provider,
        cipher=cipher,
        auth_client_factory=_auth_client_factory,
    )

    async def _token_provider() -> str:
        issued = await manager.get(alias=alias)
        return issued.token

    kiwoom_client = KiwoomClient(
        base_url=settings.kiwoom_base_url_prod,
        token_provider=_token_provider,
        timeout_seconds=settings.kiwoom_request_timeout_seconds,
        min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
        concurrent_requests=settings.kiwoom_concurrent_requests,
    )
    try:
        mrkcond = KiwoomMarketCondClient(kiwoom_client)
        use_case = IngestDailyFlowUseCase(
            session_provider=_session_provider,
            mrkcond_client=mrkcond,
            nxt_collection_enabled=settings.nxt_collection_enabled,
            indc_mode=indc_mode,
        )
        yield use_case
    finally:
        await kiwoom_client.close()
        await get_engine().dispose()


# =============================================================================
# main 진입점
# =============================================================================


async def async_main(argv: Sequence[str] | None = None) -> int:
    """async 진입점. 테스트에서 직접 호출 가능."""
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        start_date, end_date = resolve_date_range(
            years=args.years,
            start_date=args.start_date,
            end_date=args.end_date,
        )
    except ValueError as exc:
        logger.error("인자 검증 실패: %s", exc)
        return 2

    only_market_codes = parse_csv_codes(args.only_market_codes)
    only_stock_codes = parse_csv_codes(args.only_stock_codes)
    indc_mode = resolve_indc_mode(args.indc_mode)

    settings = get_settings()
    nxt_enabled = settings.nxt_collection_enabled

    # active stock count + resume / max_stocks 시 명시 종목 list 산출
    sessionmaker = get_sessionmaker()
    explicit_stock_codes: list[str] | None = None
    try:
        async with sessionmaker() as session:
            active_count = await _count_active_stocks(
                session,
                only_market_codes=only_market_codes,
                only_stock_codes=only_stock_codes,
                max_stocks=args.max_stocks,
            )
            if active_count > 0 and (args.resume or args.max_stocks is not None):
                candidate_codes = await _list_active_stock_codes(
                    session,
                    only_market_codes=only_market_codes,
                    only_stock_codes=only_stock_codes,
                    max_stocks=args.max_stocks,
                )
                if args.resume:
                    explicit_stock_codes = await compute_resume_remaining_codes(
                        session,
                        start_date=start_date,
                        end_date=end_date,
                        candidate_codes=candidate_codes,
                    )
                    active_count = len(explicit_stock_codes)
                else:
                    explicit_stock_codes = candidate_codes
    except Exception:
        logger.exception("DB 연결 실패")
        return 3

    if active_count == 0:
        if args.resume:
            logger.info("[resume] 모든 종목 완전 적재 (gap 0, %s ~ %s)", start_date, end_date)
        else:
            logger.warning("active stock 0 — 종료")
        return 0

    if args.dry_run:
        logger.info(
            "dry-run: alias=%s indc_mode=%s stocks=%d", args.alias, args.indc_mode, active_count
        )
        output = await run_dry_run(
            use_case=None,
            active_stocks_count=active_count,
            nxt_enabled=nxt_enabled,
            end_date=end_date,
            start_date=start_date,
            rate_limit_seconds=settings.kiwoom_min_request_interval_seconds,
        )
        print(output)  # noqa: T201 — CLI 출력
        return 0

    logger.info(
        "백필 시작: alias=%s indc_mode=%s stocks=%d range=%s~%s",
        args.alias,
        args.indc_mode,
        active_count,
        start_date,
        end_date,
    )
    effective_stock_codes: list[str] | None = (
        explicit_stock_codes if explicit_stock_codes is not None else (only_stock_codes or None)
    )

    started = time.monotonic()
    try:
        async with _build_use_case(alias=args.alias, indc_mode=indc_mode) as use_case:
            result = await use_case.execute(
                base_date=end_date,
                only_market_codes=only_market_codes or None,
                only_stock_codes=effective_stock_codes,
                _skip_base_date_validation=True,
                since_date=start_date,
            )
    except Exception:
        logger.exception("백필 실행 중 시스템 예외")
        return 3

    elapsed = time.monotonic() - started
    print(  # noqa: T201
        format_summary(
            indc_mode=indc_mode,
            start=start_date,
            end=end_date,
            result=result,
            elapsed_seconds=elapsed,
        )
    )
    return summary_to_exit_code(result)


def main() -> int:
    """sync 진입점 — `python scripts/backfill_daily_flow.py ...`."""
    return asyncio.run(async_main())


if __name__ == "__main__":
    sys.exit(main())
