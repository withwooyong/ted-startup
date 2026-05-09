#!/usr/bin/env python
"""키움 자격증명 등록/갱신 admin 도구.

`kiwoom.kiwoom_credential` 에 alias 등록 — Fernet 암호화 후 BYTEA 컬럼 upsert.

사용 예:
    # 환경변수 로드 (운영)
    export KIWOOM_APPKEY='...'
    export KIWOOM_SECRETKEY='...'
    export KIWOOM_CREDENTIAL_MASTER_KEY='Fernet32B...'
    export KIWOOM_DATABASE_URL='postgresql+asyncpg://kiwoom:kiwoom@localhost:5433/kiwoom_db'

    # 등록
    uv run python scripts/register_credential.py --alias prod --env prod

    # 갱신 (같은 alias 재호출 = upsert)
    uv run python scripts/register_credential.py --alias prod --env prod

종료 코드:
    0: 등록/갱신 성공
    2: 인자 / 환경변수 검증 실패
    3: 시스템 오류 (DB / 마스터키 형식)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path

# scripts/ → backend_kiwoom/ 루트 import 보장
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.adapter.out.persistence.repositories.kiwoom_credential import (  # noqa: E402
    KiwoomCredentialRepository,
)
from app.adapter.out.persistence.session import get_engine, get_sessionmaker  # noqa: E402
from app.application.dto.kiwoom_auth import KiwoomCredentials, mask_appkey  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.security.kiwoom_credential_cipher import (  # noqa: E402
    KiwoomCredentialCipher,
    MasterKeyNotConfiguredError,
)

logger = logging.getLogger("register_credential")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="키움 자격증명 alias 등록/갱신 (kiwoom.kiwoom_credential upsert)",
    )
    parser.add_argument("--alias", required=True, help="자격증명 별칭 (UNIQUE)")
    parser.add_argument(
        "--env",
        required=True,
        choices=["prod", "mock"],
        help="대상 환경 — prod (api.kiwoom.com) / mock (mockapi.kiwoom.com)",
    )
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING"])
    return parser


def read_credentials_from_env() -> tuple[str, str] | None:
    """환경변수에서 (appkey, secretkey) 읽기. 둘 다 비어있지 않아야."""
    appkey = os.environ.get("KIWOOM_APPKEY", "").strip()
    secretkey = os.environ.get("KIWOOM_SECRETKEY", "").strip()
    if not appkey or not secretkey:
        return None
    return appkey, secretkey


async def async_main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    creds_pair = read_credentials_from_env()
    if creds_pair is None:
        logger.error(
            "KIWOOM_APPKEY / KIWOOM_SECRETKEY 환경변수 둘 다 필요. "
            "쉘 history 보호를 위해 export 또는 .env.prod 사용 권장."
        )
        return 2

    appkey, secretkey = creds_pair

    settings = get_settings()
    try:
        cipher = KiwoomCredentialCipher(master_key=settings.kiwoom_credential_master_key)
    except MasterKeyNotConfiguredError as exc:
        logger.error("마스터키 검증 실패: %s", exc)
        return 3

    sessionmaker = get_sessionmaker()
    credentials = KiwoomCredentials(appkey=appkey, secretkey=secretkey)

    try:
        async with sessionmaker() as session, session.begin():
            repo = KiwoomCredentialRepository(session=session, cipher=cipher)
            row = await repo.upsert(alias=args.alias, env=args.env, credentials=credentials)
        logger.info(
            "등록 완료: alias=%s env=%s id=%d masked_appkey=%s key_version=%d",
            args.alias,
            args.env,
            row.id,
            mask_appkey(appkey),
            row.key_version,
        )
        return 0
    except Exception:
        logger.exception("DB upsert 실패")
        return 3
    finally:
        await get_engine().dispose()


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    sys.exit(main())
