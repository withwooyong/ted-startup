"""DartClient 단위 테스트 — httpx.MockTransport 로 네트워크 없이 검증."""
from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.external import (
    DartClient,
    DartNotConfiguredError,
    DartUpstreamError,
)
from app.adapter.out.persistence.repositories import DartCorpMappingRepository
from app.config.settings import Settings


def _settings(api_key: str = "FAKE-DART-KEY") -> Settings:
    return Settings(dart_api_key=api_key)


# -----------------------------------------------------------------------------
# fetch_company
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_company_parses_overview_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/company.json")
        assert request.url.params.get("corp_code") == "00126380"
        assert request.url.params.get("crtfc_key") == "FAKE-DART-KEY"
        return httpx.Response(200, json={
            "status": "000",
            "message": "정상",
            "corp_code": "00126380",
            "corp_name": "삼성전자",
            "corp_name_eng": "SAMSUNG ELECTRONICS CO,.LTD",
            "stock_code": "005930",
            "ceo_nm": "이재용",
            "corp_cls": "Y",
            "induty_code": "264",
            "est_dt": "19690113",
            "adres": "경기도 수원시",
            "hm_url": "www.samsung.com",
            "phn_no": "031-200-1114",
        })

    transport = httpx.MockTransport(handler)
    async with DartClient(_settings(), transport=transport) as client:
        info = await client.fetch_company("00126380")

    assert info is not None
    assert info.corp_name == "삼성전자"
    assert info.stock_code == "005930"
    assert info.corp_cls == "Y"
    assert info.ceo_nm == "이재용"


@pytest.mark.asyncio
async def test_fetch_company_returns_none_when_no_data() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "013", "message": "조회된 데이타가 없습니다"})

    transport = httpx.MockTransport(handler)
    async with DartClient(_settings(), transport=transport) as client:
        info = await client.fetch_company("99999999")
    assert info is None


@pytest.mark.asyncio
async def test_fetch_company_raises_on_error_status() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "010", "message": "미등록된 키"})

    transport = httpx.MockTransport(handler)
    async with DartClient(_settings(), transport=transport) as client:
        with pytest.raises(DartUpstreamError):
            await client.fetch_company("00126380")


# -----------------------------------------------------------------------------
# fetch_disclosures
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_disclosures_returns_list_with_viewer_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/list.json")
        p = request.url.params
        assert p.get("bgn_de") == "20260101"
        assert p.get("end_de") == "20260417"
        assert p.get("page_count") == "20"
        return httpx.Response(200, json={
            "status": "000",
            "page_no": 1,
            "page_count": 20,
            "total_count": 2,
            "list": [
                {
                    "corp_code": "00126380",
                    "corp_name": "삼성전자",
                    "stock_code": "005930",
                    "report_nm": "주요사항보고서(자기주식취득결정)",
                    "rcept_no": "20260201000001",
                    "rcept_dt": "20260201",
                    "flr_nm": "삼성전자",
                    "rm": "첨부정정",
                },
                {
                    "corp_code": "00126380",
                    "corp_name": "삼성전자",
                    "stock_code": "005930",
                    "report_nm": "사업보고서 (2025.12)",
                    "rcept_no": "20260301000002",
                    "rcept_dt": "20260301",
                    "flr_nm": "삼성전자",
                    "rm": None,
                },
            ],
        })

    transport = httpx.MockTransport(handler)
    async with DartClient(_settings(), transport=transport) as client:
        rows = await client.fetch_disclosures(
            "00126380", bgn_de="20260101", end_de="20260417"
        )
    assert len(rows) == 2
    assert rows[0].report_nm.startswith("주요사항")
    assert rows[0].dart_viewer_url.endswith("rcpNo=20260201000001")
    assert rows[1].rm is None


@pytest.mark.asyncio
async def test_fetch_disclosures_returns_empty_on_no_data() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "013", "message": "조회된 데이타가 없습니다"})

    transport = httpx.MockTransport(handler)
    async with DartClient(_settings(), transport=transport) as client:
        rows = await client.fetch_disclosures(
            "00126380", bgn_de="20260101", end_de="20260102"
        )
    assert rows == []


# -----------------------------------------------------------------------------
# fetch_financial_summary
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_financial_summary_parses_amounts_including_parentheses() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/fnlttSinglAcntAll.json")
        p = request.url.params
        assert p.get("bsns_year") == "2025"
        assert p.get("reprt_code") == "11011"
        assert p.get("fs_div") == "CFS"
        return httpx.Response(200, json={
            "status": "000",
            "list": [
                {
                    "account_nm": "매출액",
                    "account_id": "ifrs-full_Revenue",
                    "fs_div": "CFS",
                    "fs_nm": "연결재무제표",
                    "sj_div": "IS",
                    "sj_nm": "손익계산서",
                    "thstrm_nm": "제 56 기",
                    "thstrm_amount": "300,870,903,000,000",
                    "frmtrm_nm": "제 55 기",
                    "frmtrm_amount": "258,935,494,000,000",
                    "bfefrmtrm_nm": "제 54 기",
                    "bfefrmtrm_amount": "302,231,360,000,000",
                    "currency": "KRW",
                },
                {
                    # 음수(괄호 표기) 케이스
                    "account_nm": "영업손실",
                    "account_id": "ifrs-full_OperatingLoss",
                    "fs_div": "CFS",
                    "fs_nm": "연결재무제표",
                    "sj_div": "IS",
                    "sj_nm": "손익계산서",
                    "thstrm_nm": "제 56 기",
                    "thstrm_amount": "(1,234,000,000)",
                    "currency": "KRW",
                },
            ],
        })

    transport = httpx.MockTransport(handler)
    async with DartClient(_settings(), transport=transport) as client:
        stmt = await client.fetch_financial_summary(
            "00126380", bsns_year=2025, reprt_code="11011"
        )
    assert stmt.bsns_year == 2025
    assert stmt.fs_div == "CFS"
    assert len(stmt.rows) == 2
    assert stmt.rows[0].thstrm_amount == Decimal("300870903000000")
    assert stmt.rows[1].thstrm_amount == Decimal("-1234000000")


# -----------------------------------------------------------------------------
# Misconfiguration / HTTP errors
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raises_not_configured_when_api_key_missing() -> None:
    def handler(_: httpx.Request) -> httpx.Response:  # pragma: no cover
        return httpx.Response(200, json={"status": "000"})

    transport = httpx.MockTransport(handler)
    async with DartClient(_settings(api_key=""), transport=transport) as client:
        with pytest.raises(DartNotConfiguredError):
            await client.fetch_company("00126380")


@pytest.mark.asyncio
async def test_raises_upstream_error_on_http_500() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="DART down")

    transport = httpx.MockTransport(handler)
    async with DartClient(_settings(), transport=transport) as client:
        # HTTPError 기반 재시도가 아닌 503/500 같은 status 만 반환된 경우 바로 예외
        # (httpx 는 5xx 를 raise 하지 않음 → 우리 어댑터가 DartUpstreamError 승격)
        with pytest.raises(DartUpstreamError):
            await client.fetch_company("00126380")


# -----------------------------------------------------------------------------
# Repository
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_corp_mapping_upsert_and_lookup(session: AsyncSession) -> None:
    repo = DartCorpMappingRepository(session)
    n = await repo.upsert_many([
        ("005930", "00126380", "삼성전자"),
        ("000660", "00164779", "SK하이닉스"),
    ])
    assert n == 2

    row = await repo.find_by_stock_code("005930")
    assert row is not None and row.corp_code == "00126380"

    row2 = await repo.find_by_corp_code("00164779")
    assert row2 is not None and row2.stock_code == "000660"

    # idempotent upsert — name 변경 반영
    await repo.upsert_many([("005930", "00126380", "삼성전자(주)")])
    row = await repo.find_by_stock_code("005930")
    assert row.corp_name == "삼성전자(주)"
