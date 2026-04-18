"""P13b AI 분석 리포트 — OpenAIProvider·Service·Router 통합 테스트.

- OpenAIProvider: httpx.MockTransport 로 OpenAI API 응답 스텁.
- Service: FakeLLMProvider 로 외부 LLM 호출 제거하고 파이프라인·캐시·소스 보강 검증.
- Router: FakeLLMProvider + DART MockTransport 로 E2E 검증.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from typing import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.ai import OpenAIProvider, OpenAIProviderError
from app.adapter.out.external import DartClient
from app.adapter.out.persistence.models import Signal, SignalType, Stock, StockPrice
from app.adapter.out.persistence.repositories import (
    DartCorpMappingRepository,
    SignalRepository,
    StockPriceRepository,
    StockRepository,
)
from app.adapter.web._deps import (
    get_dart_client as prod_get_dart,
)
from app.adapter.web._deps import (
    get_llm_provider as prod_get_llm,
)
from app.adapter.web._deps import (
    get_session as prod_get_session,
)
from app.application.port.out.llm_provider import (
    DEFAULT_DISCLAIMER,
    GeneratedReport,
    LLMProvider,
    ReportContent,
    ReportSource,
    Tier1Payload,
    Tier2QualitativeItem,
    is_safe_public_url,
)
from app.application.service.analysis_report_service import (
    AnalysisReportService,
    CorpCodeNotMappedError,
    StockNotFoundError,
)
from app.config.settings import Settings, get_settings
from app.main import create_app


# -----------------------------------------------------------------------------
# Helpers / Fakes
# -----------------------------------------------------------------------------


class FakeLLMProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        sources: list[ReportSource] | None = None,
        raise_on_analyze: Exception | None = None,
    ) -> None:
        self.analyze_calls = 0
        self.collect_calls = 0
        self._sources = sources or []
        self._raise = raise_on_analyze

    async def collect_qualitative(
        self, *, stock_code: str, stock_name: str, bgn_de: str, end_de: str
    ) -> list[Tier2QualitativeItem]:
        self.collect_calls += 1
        return []

    async def analyze(
        self, *, tier1: Tier1Payload, tier2: list[Tier2QualitativeItem]
    ) -> GeneratedReport:
        self.analyze_calls += 1
        if self._raise is not None:
            raise self._raise
        return GeneratedReport(
            content=ReportContent(
                summary=f"{tier1.stock_name} 요약 — 시그널 {len(tier1.signals)}건",
                strengths=["재무 안정성", "시장 리더십"],
                risks=["경쟁 심화", "환율 변동"],
                outlook="향후 분기 견조한 실적 예상",
                opinion="HOLD",
                disclaimer=DEFAULT_DISCLAIMER,
            ),
            sources=self._sources,
            provider=self.provider_name,
            model_id="fake-flagship",
            token_in=100,
            token_out=200,
            elapsed_ms=50,
        )

    async def repackage(self, report: GeneratedReport) -> GeneratedReport:
        return report


def _dart_mock_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/company.json"):
            return httpx.Response(200, json={
                "status": "000",
                "corp_code": "00126380",
                "corp_name": "삼성전자",
                "stock_code": "005930",
                "ceo_nm": "이재용",
                "corp_cls": "Y",
                "hm_url": "www.samsung.com",
            })
        if path.endswith("/list.json"):
            return httpx.Response(200, json={
                "status": "000",
                "list": [
                    {
                        "corp_code": "00126380",
                        "corp_name": "삼성전자",
                        "stock_code": "005930",
                        "report_nm": "주요사항보고서(자기주식취득결정)",
                        "rcept_no": "20260301000001",
                        "rcept_dt": "20260301",
                        "flr_nm": "삼성전자",
                    },
                ],
            })
        if path.endswith("/fnlttSinglAcntAll.json"):
            return httpx.Response(200, json={
                "status": "000",
                "list": [
                    {
                        "account_nm": "매출액",
                        "fs_div": "CFS",
                        "fs_nm": "연결재무제표",
                        "sj_div": "IS",
                        "sj_nm": "손익계산서",
                        "thstrm_nm": "제 56 기",
                        "thstrm_amount": "300,000,000,000,000",
                        "currency": "KRW",
                    },
                ],
            })
        return httpx.Response(500)

    return httpx.MockTransport(handler)


async def _seed_stock_and_mapping(
    session: AsyncSession, *, stock_code: str = "005930", corp_code: str = "00126380"
) -> Stock:
    stock = await StockRepository(session).add(
        Stock(stock_code=stock_code, stock_name="삼성전자", market_type="KOSPI")
    )
    await DartCorpMappingRepository(session).upsert_many(
        [(stock_code, corp_code, "삼성전자")]
    )
    return stock


# -----------------------------------------------------------------------------
# OpenAIProvider unit tests
# -----------------------------------------------------------------------------


def _openai_settings(api_key: str = "sk-fake") -> Settings:
    return Settings(openai_api_key=api_key)


@pytest.mark.asyncio
async def test_openai_provider_analyze_parses_json_schema_output() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        captured["body"] = json.loads(request.content)
        content = {
            "summary": "삼성전자 분석 요약",
            "strengths": ["메모리 회복 사이클"],
            "risks": ["환율 변동"],
            "outlook": "우호적",
            "opinion": "BUY",
            "disclaimer": DEFAULT_DISCLAIMER,
            "sources": [
                {"tier": 1, "type": "dart", "url": "https://dart.fss.or.kr/x", "label": "공시"},
            ],
        }
        return httpx.Response(200, json={
            "id": "chatcmpl-fake",
            "choices": [
                {"message": {"role": "assistant", "content": json.dumps(content)}}
            ],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
        })

    transport = httpx.MockTransport(handler)
    async with OpenAIProvider(_openai_settings(), transport=transport) as provider:
        tier1 = Tier1Payload(stock_code="005930", stock_name="삼성전자", company=None)
        report = await provider.analyze(tier1=tier1, tier2=[])

    assert report.provider == "openai"
    assert report.content.opinion == "BUY"
    assert report.content.strengths == ["메모리 회복 사이클"]
    assert report.token_in == 1000
    assert report.token_out == 500
    assert report.sources[0].tier == 1
    # 요청 페이로드에 response_format json_schema 가 포함됐는지
    assert captured["body"]["response_format"]["type"] == "json_schema"
    messages = captured["body"]["messages"]
    assert messages[0]["role"] == "system"
    assert "역할 분리" in messages[0]["content"]


@pytest.mark.asyncio
async def test_openai_provider_raises_on_http_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error with secret-ish sk-FAKEPATTERN")

    transport = httpx.MockTransport(handler)
    async with OpenAIProvider(_openai_settings(), transport=transport) as provider:
        with pytest.raises(OpenAIProviderError) as exc_info:
            await provider.analyze(
                tier1=Tier1Payload(stock_code="005930", stock_name="X", company=None),
                tier2=[],
            )
    # 응답 body 가 예외 메시지로 누설되면 안 됨 (외부 detail 에 흘러가지 않도록 상태코드만)
    msg = str(exc_info.value)
    assert "secret-ish" not in msg
    assert "sk-FAKEPATTERN" not in msg
    assert "500" in msg


def test_is_safe_public_url_rejects_non_http_schemes() -> None:
    assert is_safe_public_url("https://dart.fss.or.kr/x")
    assert is_safe_public_url("http://krx.co.kr/y")
    # 스킴 차단
    assert not is_safe_public_url("javascript:alert(1)")
    assert not is_safe_public_url("file:///etc/passwd")
    assert not is_safe_public_url("ftp://example.com")
    assert not is_safe_public_url("data:text/html,<script>alert(1)</script>")
    # 빈 값·비문자열·스킴 누락
    assert not is_safe_public_url("")
    assert not is_safe_public_url("no-scheme-just-text")
    assert not is_safe_public_url("https://")  # hostname 부재


@pytest.mark.asyncio
async def test_openai_provider_filters_unsafe_source_urls() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        content = {
            "summary": "요약",
            "strengths": ["S"],
            "risks": ["R"],
            "outlook": "전망",
            "opinion": "HOLD",
            "disclaimer": DEFAULT_DISCLAIMER,
            "sources": [
                {"tier": 1, "type": "dart", "url": "https://dart.fss.or.kr/ok", "label": "공시"},
                {"tier": 1, "type": "dart", "url": "javascript:alert(1)", "label": "악성"},
                {"tier": 2, "type": "news", "url": "ftp://example.com/x", "label": "비허용 스킴"},
            ],
        }
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(content)}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        })

    transport = httpx.MockTransport(handler)
    async with OpenAIProvider(_openai_settings(), transport=transport) as provider:
        report = await provider.analyze(
            tier1=Tier1Payload(stock_code="005930", stock_name="X", company=None),
            tier2=[],
        )
    # javascript: / ftp: URL 은 버려지고 https 만 통과
    assert [s.url for s in report.sources] == ["https://dart.fss.or.kr/ok"]


def test_openai_provider_rejects_http_base_url() -> None:
    # SSRF 방어: http://169.254.169.254 같은 메타데이터 엔드포인트 진입 차단
    with pytest.raises(OpenAIProviderError):
        OpenAIProvider(Settings(
            openai_api_key="sk-x",
            openai_base_url="http://169.254.169.254/latest",
        ))


@pytest.mark.asyncio
async def test_openai_provider_collect_qualitative_no_op_when_disabled() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(500))
    async with OpenAIProvider(_openai_settings(), transport=transport) as provider:
        rows = await provider.collect_qualitative(
            stock_code="005930", stock_name="X", bgn_de="20260101", end_de="20260410"
        )
    assert rows == []


# -----------------------------------------------------------------------------
# AnalysisReportService
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_service_generates_and_caches_report(session: AsyncSession) -> None:
    stock = await _seed_stock_and_mapping(session)
    await StockPriceRepository(session).upsert_many([
        {"stock_id": stock.id, "trading_date": date.today() - timedelta(days=1), "close_price": 72000},
    ])
    await SignalRepository(session).add(Signal(
        stock_id=stock.id, signal_date=date.today() - timedelta(days=2),
        signal_type=SignalType.RAPID_DECLINE.value, score=80, grade="A", detail={},
    ))

    provider = FakeLLMProvider()
    transport = _dart_mock_transport()
    async with DartClient(Settings(dart_api_key="FAKE"), transport=transport) as dart:
        service = AnalysisReportService(session, provider=provider, dart_client=dart)
        first = await service.generate(stock_code="005930")
        second = await service.generate(stock_code="005930")

    assert first.cache_hit is False
    assert provider.analyze_calls == 1
    assert first.content["summary"].startswith("삼성전자")
    assert first.content["opinion"] == "HOLD"
    # 자동 소스 보강: DART 공시 + 공식 홈페이지
    types = {s["type"] for s in first.sources}
    assert {"dart", "official"} <= types

    assert second.cache_hit is True
    assert provider.analyze_calls == 1  # 캐시로 재호출 없음


@pytest.mark.asyncio
async def test_service_force_refresh_bypasses_cache(session: AsyncSession) -> None:
    await _seed_stock_and_mapping(session)
    provider = FakeLLMProvider()
    transport = _dart_mock_transport()
    async with DartClient(Settings(dart_api_key="FAKE"), transport=transport) as dart:
        service = AnalysisReportService(session, provider=provider, dart_client=dart)
        await service.generate(stock_code="005930")
        await service.generate(stock_code="005930", force_refresh=True)

    assert provider.analyze_calls == 2


@pytest.mark.asyncio
async def test_service_raises_when_stock_unknown(session: AsyncSession) -> None:
    provider = FakeLLMProvider()
    transport = _dart_mock_transport()
    async with DartClient(Settings(dart_api_key="FAKE"), transport=transport) as dart:
        service = AnalysisReportService(session, provider=provider, dart_client=dart)
        with pytest.raises(StockNotFoundError):
            await service.generate(stock_code="999999")


@pytest.mark.asyncio
async def test_service_raises_when_corp_code_not_mapped(session: AsyncSession) -> None:
    # 종목은 있지만 DART 매핑이 없는 케이스
    await StockRepository(session).add(
        Stock(stock_code="111111", stock_name="미매핑", market_type="KOSPI")
    )
    provider = FakeLLMProvider()
    transport = _dart_mock_transport()
    async with DartClient(Settings(dart_api_key="FAKE"), transport=transport) as dart:
        service = AnalysisReportService(session, provider=provider, dart_client=dart)
        with pytest.raises(CorpCodeNotMappedError):
            await service.generate(stock_code="111111")


# -----------------------------------------------------------------------------
# Router
# -----------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app_with_session(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[FastAPI]:
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    get_settings.cache_clear()
    app = create_app()

    async def _override_session() -> AsyncIterator[AsyncSession]:
        yield session

    async def _override_dart() -> AsyncIterator[DartClient]:
        client = DartClient(Settings(dart_api_key="FAKE"), transport=_dart_mock_transport())
        try:
            yield client
        finally:
            await client.close()

    async def _override_llm() -> AsyncIterator[LLMProvider]:
        yield FakeLLMProvider(sources=[
            ReportSource(tier=1, type="krx", url="https://krx.co.kr/x", label="KRX"),
        ])

    app.dependency_overrides[prod_get_session] = _override_session
    app.dependency_overrides[prod_get_dart] = _override_dart
    app.dependency_overrides[prod_get_llm] = _override_llm
    try:
        yield app
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_reports_endpoint_requires_admin_key(app_with_session: FastAPI) -> None:
    transport = httpx.ASGITransport(app=app_with_session)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/api/reports/005930")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reports_endpoint_generates_and_returns_404_for_unknown(
    app_with_session: FastAPI, session: AsyncSession
) -> None:
    await _seed_stock_and_mapping(session)
    transport = httpx.ASGITransport(app=app_with_session)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test",
        headers={"X-API-Key": "test-admin-key"},
    ) as c:
        resp = await c.post("/api/reports/005930")
        assert resp.status_code == 200
        body = resp.json()
        assert body["stock_code"] == "005930"
        assert body["content"]["opinion"] == "HOLD"
        assert body["cache_hit"] is False

        # 두 번째 호출 — 캐시 히트
        resp2 = await c.post("/api/reports/005930")
        assert resp2.status_code == 200
        assert resp2.json()["cache_hit"] is True

        # 존재하지 않는 종목 → 404
        resp3 = await c.post("/api/reports/999999")
        assert resp3.status_code == 404
