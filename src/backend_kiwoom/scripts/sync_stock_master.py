#!/usr/bin/env python
"""ka10099 종목 마스터 1회 sync admin 도구.

5 시장 (KOSPI/KOSDAQ/KONEX/ETF/ETN) 종목 마스터를 키움에서 가져와 `kiwoom.stock` 동기화.
운영 라우터 `POST /api/kiwoom/stocks/sync` 와 동일 효과 — uvicorn 기동 없이 1회 호출용.

사용 예:
    export DATABASE_URL='postgresql+asyncpg://kiwoom:kiwoom@localhost:5433/kiwoom_db'
    export KIWOOM_CREDENTIAL_MASTER_KEY='Fernet32B...'

    # alias 가 register_credential.py 로 등록되어 있어야 함
    uv run python scripts/sync_stock_master.py --alias prod

종료 코드:
    0: 5 시장 모두 success (all_succeeded == True)
    1: 부분 실패 (한 시장 이상 error)
    2: alias 미등록 / 비활성 / 한도 초과 / 인자 검증 실패
    3: 시스템 오류 (DB / 마스터키 / 키움 호출 시스템 예외)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path

# scripts/ → backend_kiwoom/ 루트 import 보장
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.adapter.out.kiwoom._client import KiwoomClient  # noqa: E402
from app.adapter.out.kiwoom.auth import KiwoomAuthClient  # noqa: E402
from app.adapter.out.kiwoom.stkinfo import KiwoomStkInfoClient  # noqa: E402
from app.adapter.out.persistence.session import get_engine, get_sessionmaker  # noqa: E402
from app.application.service.stock_master_service import (  # noqa: E402
    StockMasterSyncResult,
    SyncStockMasterUseCase,
)
from app.application.service.token_service import (  # noqa: E402
    AliasCapacityExceededError,
    CredentialInactiveError,
    CredentialNotFoundError,
    TokenManager,
)
from app.config.settings import get_settings  # noqa: E402
from app.security.kiwoom_credential_cipher import (  # noqa: E402
    KiwoomCredentialCipher,
    MasterKeyNotConfiguredError,
)

logger = logging.getLogger("sync_stock_master")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ka10099 종목 마스터 1회 sync (5 시장)",
    )
    parser.add_argument("--alias", required=True, help="키움 자격증명 alias")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING"])
    return parser


@asynccontextmanager
async def _build_use_case(*, alias: str) -> AsyncIterator[SyncStockMasterUseCase]:
    """lifespan 외부 — TokenManager + KiwoomClient + UseCase 빌드.

    `try/finally` 로 KiwoomClient.close + engine.dispose 보장. main.py 의 sync_stock factory 패턴.
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
        stkinfo = KiwoomStkInfoClient(kiwoom_client)
        yield SyncStockMasterUseCase(
            session_provider=_session_provider,
            stkinfo_client=stkinfo,
            mock_env=(settings.kiwoom_default_env == "mock"),
        )
    finally:
        await kiwoom_client.close()


def format_summary(*, result: StockMasterSyncResult, elapsed_seconds: float) -> str:
    lines = [
        "===== Stock Master Sync Summary =====",
        f"elapsed:           {elapsed_seconds:.1f}s",
        f"total_fetched:     {result.total_fetched}",
        f"total_upserted:    {result.total_upserted}",
        f"total_deactivated: {result.total_deactivated}",
        f"total_nxt_enabled: {result.total_nxt_enabled}",
        f"all_succeeded:     {result.all_succeeded}",
        "--- markets ---",
    ]
    for m in result.markets:
        status = "OK" if m.succeeded else f"ERROR={m.error}"
        lines.append(
            f"  market={m.market_code:>3} fetched={m.fetched:>5} upserted={m.upserted:>5} "
            f"nxt_enabled={m.nxt_enabled_count:>5} deactivated={m.deactivated:>3}  {status}"
        )
    return "\n".join(lines)


async def async_main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    settings = get_settings()
    if not settings.kiwoom_credential_master_key:
        logger.error("KIWOOM_CREDENTIAL_MASTER_KEY 미설정 — 운영 환경은 env 주입 필수")
        return 3

    started = time.monotonic()
    try:
        async with _build_use_case(alias=args.alias) as use_case:
            result = await use_case.execute()
    except CredentialNotFoundError:
        logger.error("등록되지 않은 alias=%s — register_credential.py 로 먼저 등록", args.alias)
        return 2
    except CredentialInactiveError:
        logger.error("비활성 자격증명: alias=%s", args.alias)
        return 2
    except AliasCapacityExceededError:
        logger.error("alias 한도 초과: alias=%s", args.alias)
        return 2
    except MasterKeyNotConfiguredError:
        logger.exception("마스터키 검증 실패")
        return 3
    except Exception:
        logger.exception("sync 실행 중 시스템 예외")
        return 3
    finally:
        await get_engine().dispose()

    elapsed = time.monotonic() - started
    print(format_summary(result=result, elapsed_seconds=elapsed))  # noqa: T201
    return 0 if result.all_succeeded else 1


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    sys.exit(main())
