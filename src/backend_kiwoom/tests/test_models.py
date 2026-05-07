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
    Sector,
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

    rows = (await session.execute(select(RawResponse).where(RawResponse.api_id == "ka10086"))).scalars().all()
    assert len(rows) == 3


# =============================================================================
# Sector — Migration 002 / ka10101 업종 마스터
# =============================================================================


@pytest.mark.asyncio
async def test_sector_table_columns(session: AsyncSession) -> None:
    sec = Sector(
        market_code="0",
        sector_code="001",
        sector_name="종합(KOSPI)",
        group_no="1",
    )
    session.add(sec)
    await session.flush()
    await session.refresh(sec)

    assert sec.id is not None
    assert sec.market_code == "0"
    assert sec.sector_code == "001"
    assert sec.sector_name == "종합(KOSPI)"
    assert sec.group_no == "1"
    assert sec.is_active is True  # server_default true
    assert sec.fetched_at is not None
    assert sec.created_at is not None
    assert sec.updated_at is not None


@pytest.mark.asyncio
async def test_sector_unique_market_code_sector_code(session: AsyncSession) -> None:
    """동일 (market_code, sector_code) 중복 INSERT 시 IntegrityError."""
    session.add(Sector(market_code="0", sector_code="dup", sector_name="첫번째"))
    await session.flush()
    session.add(Sector(market_code="0", sector_code="dup", sector_name="중복"))
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_sector_market_code_check_constraint(session: AsyncSession) -> None:
    """market_code 는 ('0','1','2','4','7') 만 허용 — '3' 거부."""
    session.add(Sector(market_code="3", sector_code="001", sector_name="무효시장"))
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_sector_same_code_across_different_markets_allowed(session: AsyncSession) -> None:
    """동일 sector_code 라도 market_code 가 다르면 OK — UNIQUE 는 (market_code, sector_code) 복합."""
    session.add(Sector(market_code="0", sector_code="001", sector_name="KOSPI 종합"))
    session.add(Sector(market_code="1", sector_code="001", sector_name="KOSDAQ 종합"))
    await session.flush()  # 예외 X

    rows = (await session.execute(select(Sector).where(Sector.sector_code == "001"))).scalars().all()
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_sector_group_no_nullable(session: AsyncSession) -> None:
    """group_no 는 NULL 허용 — 응답에 group 필드가 빈 문자열일 때 None 매핑."""
    sec = Sector(market_code="0", sector_code="002", sector_name="대형주", group_no=None)
    session.add(sec)
    await session.flush()
    await session.refresh(sec)
    assert sec.group_no is None
