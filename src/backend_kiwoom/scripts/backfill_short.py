#!/usr/bin/env python
"""공매도 추이 (ka10014) 백필 CLI — Phase E.

설계: endpoint-15-ka10014.md § 12 + plan § 12.2 #7 (3년 백필 통일).

backfill_ohlcv.py 패턴 1:1 응용. active 종목 bulk 백필 (KRX + NXT 분기).

사용 예:
    # 환경변수 (.env.prod 가 backend_kiwoom/ 또는 루트에 있으면 자동 로드 — export 불필요)
    #   KIWOOM_DATABASE_URL='postgresql+asyncpg://kiwoom:kiwoom@localhost:5433/kiwoom_db'
    #   KIWOOM_CREDENTIAL_MASTER_KEY='Fernet32B...'

    # 3년 백필
    python scripts/backfill_short.py --start 2023-01-01 --end 2026-05-12 --alias prod

    # 종료 코드:
    #   0: 모든 종목 success (failed = 0)
    #   1: 부분 실패 (failed > 0)
    #   2: 인자 검증 실패
    #   3: 시스템 오류 (DB 연결 / settings 누락)
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
from app.adapter.out.kiwoom.shsa import KiwoomShortSellingClient  # noqa: E402
from app.adapter.out.persistence.session import get_engine, get_sessionmaker  # noqa: E402
from app.application.service.short_selling_service import (  # noqa: E402
    IngestShortSellingBulkUseCase,
    IngestShortSellingUseCase,
)
from app.application.service.token_service import TokenManager  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.security.kiwoom_credential_cipher import KiwoomCredentialCipher  # noqa: E402

logger = logging.getLogger("backfill_short")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="공매도 추이 (ka10014) 백필 CLI — Phase E"
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
        help="logger 레벨",
    )
    return parser


@asynccontextmanager
async def _build_use_case(*, alias: str) -> AsyncIterator[IngestShortSellingBulkUseCase]:
    """TokenManager + KiwoomClient + ShortSellingBulk UseCase 빌드."""
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
        shsa = KiwoomShortSellingClient(kiwoom_client)
        single = IngestShortSellingUseCase(
            session_provider=_session_provider,
            shsa_client=shsa,
            env=settings.kiwoom_default_env,
        )
        use_case = IngestShortSellingBulkUseCase(
            session_provider=_session_provider,
            single_use_case=single,
        )
        yield use_case
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
        "공매도 백필 시작: alias=%s range=%s~%s",
        args.alias,
        start_date,
        end_date,
    )

    started = time.monotonic()
    try:
        async with _build_use_case(alias=args.alias) as use_case:
            # Phase F-2: CLI 는 filter_alphanumeric=True 로 alphanumeric 종목
            # 호출 자체 skip — 73s budget 절감 + summary 가시성 (ADR § 44.9).
            # scheduler 는 기본값 False 유지 (변경 0).
            result = await use_case.execute(
                start_date=start_date,
                end_date=end_date,
                filter_alphanumeric=True,
            )
    except Exception:
        logger.exception("공매도 백필 실행 중 시스템 예외")
        return 3

    elapsed = time.monotonic() - started
    total_outcomes = len(result.krx_outcomes) + len(result.nxt_outcomes)
    failure_ratio = (
        (result.total_failed / total_outcomes) if total_outcomes > 0 else 0.0
    )
    print(  # noqa: T201 — CLI 출력
        "\n".join(
            [
                "===== ShortSelling Backfill Summary =====",
                f"date range:    {start_date} ~ {end_date}",
                f"total_stocks:  {result.total_stocks}",
                f"krx_outcomes:  {len(result.krx_outcomes)}",
                f"nxt_outcomes:  {len(result.nxt_outcomes)}",
                f"total_upserted:{result.total_upserted}",
                f"total_failed:  {result.total_failed} (ratio {failure_ratio:.2%})",
                f"alphanumeric_skipped:{result.total_skipped}",
                f"elapsed:       {elapsed:.1f}s",
            ]
        )
    )
    return 1 if result.total_failed > 0 else 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    sys.exit(main())
