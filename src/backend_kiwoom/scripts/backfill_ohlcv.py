#!/usr/bin/env python
"""OHLCV 통합 백필 CLI — daily/weekly/monthly period dispatch (C-backfill).

설계: phase-c-backfill-ohlcv.md.

`/api/kiwoom/ohlcv/{period}/sync` 라우터의 1년 cap 을 우회해 3년 백필 + 운영 실측 도구.
ka10081 (일봉) + ka10082/83 (주/월봉) 의 IngestUseCase 를 그대로 재사용 + period dispatch.

사용 예:
    # 환경변수 (.env.prod 가 backend_kiwoom/ 또는 루트에 있으면 자동 로드 — export 불필요)
    #   KIWOOM_DATABASE_URL='postgresql+asyncpg://kiwoom:kiwoom@localhost:5433/kiwoom_db'
    #   KIWOOM_CREDENTIAL_MASTER_KEY='Fernet32B...'

    # dry-run — 종목 수 + 호출 수 + 시간 추정만 (DB 적재 X)
    python scripts/backfill_ohlcv.py --period daily --years 3 --alias prod --dry-run

    # 실제 백필 (3년)
    python scripts/backfill_ohlcv.py --period daily --years 3 --alias prod

    # KOSPI 100 종목만 (디버그)
    python scripts/backfill_ohlcv.py --period weekly --years 1 --alias prod \\
        --only-market-codes 0 --max-stocks 100

    # 특정 기간
    python scripts/backfill_ohlcv.py --period monthly \\
        --start-date 2022-01-01 --end-date 2024-12-31 --alias prod

    # resume — 이미 적재된 종목 skip
    python scripts/backfill_ohlcv.py --period daily --years 3 --alias prod --resume

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

# scripts/ → backend_kiwoom/ 루트 import 보장
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# .env.prod 자동 로드 — backend_kiwoom/.env.prod (symlink 또는 cp) → 루트 ../../.env.prod 순서.
# pydantic-settings 가 cwd 기준 로드라서 backend_kiwoom 외부에서 실행 시 KIWOOM_DATABASE_URL 등 누락 방지.
for candidate in (ROOT / ".env.prod", ROOT.parent.parent / ".env.prod", ROOT / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=False)

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.adapter.out.kiwoom._client import KiwoomClient  # noqa: E402
from app.adapter.out.kiwoom.auth import KiwoomAuthClient  # noqa: E402
from app.adapter.out.kiwoom.chart import KiwoomChartClient  # noqa: E402
from app.adapter.out.persistence.models import Stock  # noqa: E402
from app.adapter.out.persistence.session import get_engine, get_sessionmaker  # noqa: E402
from app.application.constants import Period  # noqa: E402
from app.application.service.ohlcv_daily_service import (  # noqa: E402
    IngestDailyOhlcvUseCase,
    OhlcvSyncResult,
)
from app.application.service.ohlcv_periodic_service import (  # noqa: E402
    IngestPeriodicOhlcvUseCase,
)
from app.application.service.token_service import TokenManager  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.security.kiwoom_credential_cipher import KiwoomCredentialCipher  # noqa: E402

logger = logging.getLogger("backfill_ohlcv")


# =============================================================================
# 인자 파서
# =============================================================================


def build_parser() -> argparse.ArgumentParser:
    """argparse 의 ArgumentParser 빌드. 테스트용으로 분리."""
    parser = argparse.ArgumentParser(
        description="OHLCV 통합 백필 CLI — daily/weekly/monthly period dispatch (C-backfill)",
    )
    parser.add_argument(
        "--period",
        required=True,
        choices=["daily", "weekly", "monthly"],
        help="백필 대상 시계열 period",
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


# =============================================================================
# date range / period dispatch / 시간 추정
# =============================================================================


def resolve_date_range(
    *,
    years: int,
    start_date: date | None,
    end_date: date | None,
) -> tuple[date, date]:
    """--years 또는 --start-date/--end-date 입력에서 (start, end) 결정.

    명시 start_date/end_date 가 우선. start > end 면 ValueError.
    """
    end = end_date or date.today()
    start = start_date if start_date is not None else end - timedelta(days=365 * years)
    if start > end:
        raise ValueError(f"start ({start}) must be <= end ({end})")
    return start, end


def use_case_class_for_period(
    period: str,
) -> type[IngestDailyOhlcvUseCase] | type[IngestPeriodicOhlcvUseCase]:
    """period → UseCase 클래스. CLI 진입점에서 dispatch."""
    if period == "daily":
        return IngestDailyOhlcvUseCase
    return IngestPeriodicOhlcvUseCase


def estimate_seconds(
    *,
    stocks: int,
    exchanges_per_stock: int,
    pages_per_call: int,
    rate_limit_seconds: float,
) -> float:
    """dry-run 시간 추정 (lower-bound). H-3 — ±50% margin 명시 필요.

    실제 시간은 네트워크 RTT / DB upsert 시간 / KRX 5xx 재시도로 더 길어질 수 있음.
    """
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


# period → KRX 영속화 테이블 매핑 (resume 시 trading_date 조회용)
_RESUME_TABLE_BY_PERIOD: dict[str, str] = {
    "daily": "kiwoom.stock_price_krx",
    "weekly": "kiwoom.stock_price_weekly_krx",
    "monthly": "kiwoom.stock_price_monthly_krx",
    "yearly": "kiwoom.stock_price_yearly_krx",
}


async def compute_resume_remaining_codes(
    session: AsyncSession,
    *,
    period: str,
    start_date: date,
    end_date: date,
    candidate_codes: list[str],
) -> list[str]:
    """resume mode (R2 gap detection) — candidate_codes 중 [start_date, end_date] 의 영업일
    set 와 비교해 gap 1+ 또는 적재 0 인 종목만 반환.

    영업일 calendar = SELECT DISTINCT trading_date FROM <period 별 KRX 테이블> WHERE trading_date
    BETWEEN start AND end (시장 전체 종목 union). 외부 패키지 의존성 0.

    가드 (H-8): 영업일 set = ∅ (DB 0 rows in 범위) → 모든 candidate 진행. 첫 적재 시나리오.

    R1 시점에는 `max(trading_date) >= end_date` 만 검사 — 부분 적재 (gap) 종목을 잘못 skip
    하던 한계를 R2 에서 일자별 차집합으로 정밀화.

    Returns:
        진행 대상 종목 코드 list. 모두 완전 적재면 빈 list.
    """
    from sqlalchemy import text

    table = _RESUME_TABLE_BY_PERIOD[period]

    # 1. 영업일 calendar — 시장 전체 종목 union (stock_price_*_krx 테이블은 KRX 전용,
    #    exchange 컬럼 자체 없음 → 별도 필터 불필요. daily_flow 와 패턴 차이 의도적)
    business_days_sql = text(
        f"""
        SELECT DISTINCT trading_date
        FROM {table}
        WHERE trading_date BETWEEN :start AND :end
        """
    )
    bd_result = await session.execute(
        business_days_sql.bindparams(start=start_date, end=end_date)
    )
    business_days: set[date] = {row[0] for row in bd_result.fetchall()}

    if not business_days:
        # 영업일 set = ∅ — 첫 적재. 모든 candidate 진행
        logger.info(
            "[resume] 영업일 calendar 비어있음 (start=%s end=%s) — %d 종목 모두 진행",
            start_date,
            end_date,
            len(candidate_codes),
        )
        return list(candidate_codes)

    # 2. 종목별 trading_date set
    per_stock_sql = text(
        f"""
        SELECT s.stock_code, p.trading_date
        FROM kiwoom.stock s
        LEFT JOIN {table} p ON p.stock_id = s.id
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


def summary_to_exit_code(result: OhlcvSyncResult) -> int:
    """failed = 0 → exit 0 (success), > 0 → exit 1 (partial). H-5."""
    return 1 if result.failed > 0 else 0


def format_summary(
    *,
    period: str,
    start: date,
    end: date,
    result: OhlcvSyncResult,
    elapsed_seconds: float,
) -> str:
    """summary 출력 포맷."""
    avg_per_stock = (elapsed_seconds / result.total) if result.total > 0 else 0.0
    failure_ratio = (result.failed / result.total) if result.total > 0 else 0.0
    lines = [
        "===== Backfill Summary =====",
        f"period:        {period}",
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
    period: str,
    active_stocks_count: int,
    nxt_enabled: bool,
    end_date: date,
    start_date: date,
    rate_limit_seconds: float,
) -> str:
    """dry-run 모드 — UseCase.execute 호출 안 함. 추정값만 반환."""
    days = (end_date - start_date).days

    # period 별 페이지 추정 (휴리스틱)
    if period == "daily":
        # ka10081: 1 페이지 ~600 거래일 가정 — 3년 (~750 거래일) → 2 페이지
        pages_per_call = max(1, (days // 600) + (1 if days % 600 else 0))
    elif period == "weekly":
        # ka10082: 1 페이지 ~600 주 가정 — 3년 (156 주) → 1 페이지
        pages_per_call = 1
    else:  # monthly
        # ka10083: 36 월봉 → 1 페이지
        pages_per_call = 1

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
            f"period:        {period}",
            f"date range:    {start_date} ~ {end_date} ({days} days)",
            f"active stocks: {active_stocks_count}",
            f"NXT collection: {'enabled' if nxt_enabled else 'disabled'}",
            f"exchanges/stock: {exchanges}",
            f"pages/call:    {pages_per_call}",
            f"total calls:   {active_stocks_count * exchanges * pages_per_call}",
            f"rate limit:    {rate_limit_seconds}s/call",
            f"estimated:     {format_duration(seconds)} (실측 ±50% margin)",
            "",
            "[dry-run] DB 미적재. 실제 백필은 --dry-run 제거 후 재실행.",
        ]
    )


# =============================================================================
# main 진입점
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


@asynccontextmanager
async def _build_use_case(
    *,
    period: str,
    alias: str,
) -> AsyncIterator[Any]:
    """lifespan 외부 — TokenManager + KiwoomClient + UseCase 빌드.

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
        chart = KiwoomChartClient(kiwoom_client)
        cls = use_case_class_for_period(period)
        use_case = cls(
            session_provider=_session_provider,
            chart_client=chart,
            nxt_collection_enabled=settings.nxt_collection_enabled,
        )
        yield use_case
    finally:
        await kiwoom_client.close()
        await get_engine().dispose()


async def async_main(argv: Sequence[str] | None = None) -> int:
    """async 진입점. 테스트에서 직접 호출 가능."""
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 인자 검증
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

    settings = get_settings()
    nxt_enabled = settings.nxt_collection_enabled

    # active stock count + resume / max_stocks 시 명시 종목 list 산출 (1 세션에 통합)
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
                # 1차 후보 코드 조회 (only_market_codes / only_stock_codes / max_stocks 반영)
                candidate_codes = await _list_active_stock_codes(
                    session,
                    only_market_codes=only_market_codes,
                    only_stock_codes=only_stock_codes,
                    max_stocks=args.max_stocks,
                )
                if args.resume:
                    explicit_stock_codes = await compute_resume_remaining_codes(
                        session,
                        period=args.period,
                        start_date=start_date,
                        end_date=end_date,
                        candidate_codes=candidate_codes,
                    )
                    active_count = len(explicit_stock_codes)
                else:
                    # --max-stocks 단독 — UseCase 에 limit 적용 종목 list 명시 전달.
                    # active_count 는 _count_active_stocks 가 이미 max_stocks 반영.
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

    # dry-run mode
    if args.dry_run:
        logger.info("dry-run: period=%s alias=%s stocks=%d", args.period, args.alias, active_count)
        # use_case 빌드 안 해도 추정 가능 — None 전달
        output = await run_dry_run(
            use_case=None,
            period=args.period,
            active_stocks_count=active_count,
            nxt_enabled=nxt_enabled,
            end_date=end_date,
            start_date=start_date,
            rate_limit_seconds=settings.kiwoom_min_request_interval_seconds,
        )
        print(output)  # noqa: T201 — CLI 출력
        return 0

    # 실제 백필
    logger.info(
        "백필 시작: period=%s alias=%s stocks=%d range=%s~%s",
        args.period,
        args.alias,
        active_count,
        start_date,
        end_date,
    )
    # only_stock_codes 결정: resume / --max-stocks 시 산출된 explicit list 가 우선, 없으면 CLI 인자
    effective_stock_codes: list[str] | None = (
        explicit_stock_codes if explicit_stock_codes is not None else (only_stock_codes or None)
    )

    started = time.monotonic()
    try:
        async with _build_use_case(period=args.period, alias=args.alias) as use_case:
            # period 별 execute 호출 (1년 cap 우회). 빈 list 는 None 으로 변환 — UseCase 의
            # `if only_*_codes:` 분기가 None/빈list 모두 false 처리하나 명시적 변환으로 의도 분명.
            if args.period == "daily":
                result = await use_case.execute(
                    base_date=end_date,
                    only_market_codes=only_market_codes or None,
                    only_stock_codes=effective_stock_codes,
                    _skip_base_date_validation=True,
                    since_date=start_date,
                )
            else:
                period_enum = Period.WEEKLY if args.period == "weekly" else Period.MONTHLY
                result = await use_case.execute(
                    period=period_enum,
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
            period=args.period,
            start=start_date,
            end=end_date,
            result=result,
            elapsed_seconds=elapsed,
        )
    )
    return summary_to_exit_code(result)


def main() -> int:
    """sync 진입점 — `python scripts/backfill_ohlcv.py ...`."""
    return asyncio.run(async_main())


if __name__ == "__main__":
    sys.exit(main())
