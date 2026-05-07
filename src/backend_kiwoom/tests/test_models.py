"""ORM 모델 schema 검증 — Migration 001 의 3 테이블이 모델과 일치하는지.

검증:
- KiwoomCredential: alias UNIQUE, env CHECK, BYTEA 컬럼, key_version default
- KiwoomToken: credential_id FK + UNIQUE, BYTEA token_cipher, expires_at TZ
- RawResponse: api_id, request_hash, JSONB 컬럼, http_status
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import (
    KiwoomCredential,
    KiwoomToken,
    RawResponse,
)


@pytest.mark.asyncio
async def test_kiwoom_credential_table_columns(session: AsyncSession) -> None:
    cred = KiwoomCredential(
        alias="test-prod-main",
        env="prod",
        appkey_cipher=b"\x80abc-cipher-bytes",
        secretkey_cipher=b"\x80def-cipher-bytes",
        key_version=1,
    )
    session.add(cred)
    await session.flush()
    await session.refresh(cred)

    assert cred.id is not None
    assert cred.alias == "test-prod-main"
    assert cred.env == "prod"
    assert cred.is_active is True
    assert cred.created_at is not None
    assert cred.updated_at is not None


@pytest.mark.asyncio
async def test_kiwoom_credential_alias_unique(session: AsyncSession) -> None:
    session.add(
        KiwoomCredential(
            alias="dup-alias",
            env="prod",
            appkey_cipher=b"a",
            secretkey_cipher=b"b",
        )
    )
    await session.flush()
    session.add(
        KiwoomCredential(
            alias="dup-alias",
            env="prod",
            appkey_cipher=b"c",
            secretkey_cipher=b"d",
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_kiwoom_credential_env_check_constraint(session: AsyncSession) -> None:
    """env 컬럼은 'prod' / 'mock' 만 허용."""
    session.add(
        KiwoomCredential(
            alias="bad-env",
            env="real",  # 잘못된 값
            appkey_cipher=b"x",
            secretkey_cipher=b"y",
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_kiwoom_token_fk_to_credential(session: AsyncSession) -> None:
    cred = KiwoomCredential(
        alias="token-fk-test",
        env="mock",
        appkey_cipher=b"a",
        secretkey_cipher=b"b",
    )
    session.add(cred)
    await session.flush()

    token = KiwoomToken(
        credential_id=cred.id,
        token_cipher=b"\x80token-cipher-bytes",
        token_type="bearer",
        expires_at=datetime.now(UTC) + timedelta(hours=23),
    )
    session.add(token)
    await session.flush()
    await session.refresh(token)

    assert token.id is not None
    assert token.credential_id == cred.id
    assert token.issued_at is not None


@pytest.mark.asyncio
async def test_kiwoom_token_unique_per_credential(session: AsyncSession) -> None:
    """자격증명당 활성 토큰 1개만."""
    cred = KiwoomCredential(
        alias="token-unique-test",
        env="mock",
        appkey_cipher=b"a",
        secretkey_cipher=b"b",
    )
    session.add(cred)
    await session.flush()

    expires = datetime.now(UTC) + timedelta(hours=23)
    session.add(KiwoomToken(credential_id=cred.id, token_cipher=b"t1", expires_at=expires))
    await session.flush()
    session.add(KiwoomToken(credential_id=cred.id, token_cipher=b"t2", expires_at=expires))
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_raw_response_jsonb_columns(session: AsyncSession) -> None:
    raw = RawResponse(
        api_id="ka10081",
        request_hash="a" * 64,
        request_payload={"stk_cd": "005930", "base_dt": "20250507"},
        response_payload={"return_code": 0, "list": [{"close": 70000}]},
        http_status=200,
    )
    session.add(raw)
    await session.flush()
    await session.refresh(raw)

    assert raw.id is not None
    assert raw.request_payload == {"stk_cd": "005930", "base_dt": "20250507"}
    assert raw.response_payload["return_code"] == 0
    assert raw.fetched_at is not None


@pytest.mark.asyncio
async def test_raw_response_query_by_api_id(session: AsyncSession) -> None:
    """api_id 인덱스로 조회 가능."""
    for i in range(3):
        session.add(
            RawResponse(
                api_id="ka10086",
                request_hash=f"{i}" * 64,
                request_payload={"i": i},
                response_payload={"i": i},
                http_status=200,
            )
        )
    await session.flush()

    rows = (
        (await session.execute(select(RawResponse).where(RawResponse.api_id == "ka10086")))
        .scalars()
        .all()
    )
    assert len(rows) == 3
