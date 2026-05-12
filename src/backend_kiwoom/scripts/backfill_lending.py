#!/usr/bin/env python
"""시장 대차거래 (ka10068) 백필 CLI — Phase E.

설계: endpoint-16-ka10068.md § 12 + plan § 12.2 #7 (3년 백필 통일).

backfill_ohlcv.py 패턴 1:1 응용. 단일 호출 (시장 단위 — 종목 iterate 없음).

사용 예:
    python scripts/backfill_lending.py --start 2023-01-01 --end 2026-05-12 --alias prod

종료 코드:
    0: success
    1: 비즈니스 에러 (return_code != 0)
    2: 인자 검증 실패
    3: 시스템 오류 (DB 연결 / settings 누락)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

for candidate in (ROOT / ".env.prod", ROOT.parent.parent / ".env.prod", ROOT / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=False)

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.adapter.out.kiwoom._client import KiwoomClient  # noqa: E402
from app.adapter.out.kiwoom.auth import KiwoomAuthClient  # noqa: E402
from app.adapter.out.kiwoom.slb import KiwoomLendingClient  # noqa: E402
from app.adapter.out.persistence.session import get_engine, get_sessionmaker  # noqa: E402
from app.application.service.lending_service import IngestLendingMarketUseCase  # noqa: E402
from app.application.service.token_service import TokenManager  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.security.kiwoom_credential_cipher import KiwoomCredentialCipher  # noqa: E402

logger = logging.getLogger("backfill_lending")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="시장 대차거래 (ka10068) 백필 CLI — Phase E"
    )
    parser.add_argument("--alias", required=True, help="키움 자격증명 alias")
    parser.add_argument(
        "--start",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        required=True,
        help="시작일 YYYY-MM-DD",
    )
    parser.add_argument(
        "--end",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=None,
        help="종료일 YYYY-MM-DD (디폴트 today)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING"],
    )
    return parser


@asynccontextmanager
async def _build_use_case(*, alias: str) -> AsyncIterator[IngestLendingMarketUseCase]:
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
        slb = KiwoomLendingClient(kiwoom_client)
        async with sessionmaker() as session:
            use_case = IngestLendingMarketUseCase(
                session=session,
                slb_client=slb,
            )
            yield use_case
            await session.commit()
    finally:
        await kiwoom_client.close()
        await get_engine().dispose()


async def async_main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    start_date: date = args.start
    end_date: date = args.end or date.today()
    if start_date > end_date:
        logger.error("start (%s) must be <= end (%s)", start_date, end_date)
        return 2

    logger.info(
        "시장 대차거래 백필 시작: alias=%s range=%s~%s",
        args.alias,
        start_date,
        end_date,
    )

    started = time.monotonic()
    try:
        async with _build_use_case(alias=args.alias) as use_case:
            outcome = await use_case.execute(start_date=start_date, end_date=end_date)
    except Exception:
        logger.exception("시장 대차거래 백필 실행 중 시스템 예외")
        return 3

    elapsed = time.monotonic() - started
    print(  # noqa: T201
        "\n".join(
            [
                "===== LendingMarket Backfill Summary =====",
                f"date range: {start_date} ~ {end_date}",
                f"fetched:    {outcome.fetched}",
                f"upserted:   {outcome.upserted}",
                f"error:      {outcome.error or '<none>'}",
                f"elapsed:    {elapsed:.1f}s",
            ]
        )
    )
    return 1 if outcome.error is not None else 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    sys.exit(main())
