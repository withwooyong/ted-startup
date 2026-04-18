"""AI 분석 리포트 UseCase.

흐름(§11.3 실시간 온디맨드):
1. 캐시 조회: (stock_code, KST 00:00 기준 오늘) 이 있고 force_refresh=False 면 그대로 반환
2. corp_code 매핑 해결 (dart_corp_mapping). 미등록이면 LookupError → 라우터에서 400
3. Tier1 수집: DART 기업개황 + 공시목록(최근 90일) + 재무제표(최근 연도, CFS) + KRX 최근 시세·시그널
4. Tier2 수집(옵션): provider.collect_qualitative — 비활성이면 빈 리스트
5. provider.analyze → GeneratedReport
6. provider.repackage (MVP passthrough)
7. analysis_report upsert
8. 반환

실패 격리:
- DART 엔드포인트 부분 실패는 경고 로그 후 빈 데이터로 진행
- 분석 단계 실패는 예외 전파(호출자가 500/502 매핑)
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.external import (
    DartClient,
    DartClientError,
)
from app.adapter.out.persistence.models import AnalysisReport, Stock
from app.adapter.out.persistence.repositories import (
    AnalysisReportRepository,
    DartCorpMappingRepository,
    SignalRepository,
    StockPriceRepository,
    StockRepository,
)
from app.application.port.out.llm_provider import (
    DEFAULT_DISCLAIMER,
    GeneratedReport,
    LLMProvider,
    ReportSource,
    Tier1CompanyInfo,
    Tier1DisclosureItem,
    Tier1FinancialItem,
    Tier1Payload,
    Tier1PricePoint,
    Tier1SignalItem,
    is_safe_public_url,
)

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


class AnalysisReportError(Exception):
    pass


class CorpCodeNotMappedError(AnalysisReportError):
    pass


class StockNotFoundError(AnalysisReportError):
    pass


@dataclass(slots=True)
class ReportOutcome:
    stock_code: str
    report_date: date
    provider: str
    model_id: str
    content: dict[str, Any]
    sources: list[dict[str, Any]]
    cache_hit: bool
    token_in: int | None = None
    token_out: int | None = None
    elapsed_ms: int | None = None


class AnalysisReportService:
    """제네릭 AnalysisReport UseCase — DART + KRX(DB) Tier1 수집 후 LLMProvider 위임."""

    DISCLOSURE_WINDOW_DAYS = 90
    PRICE_WINDOW_DAYS = 30
    SIGNAL_WINDOW_DAYS = 60

    def __init__(
        self,
        session: AsyncSession,
        *,
        provider: LLMProvider,
        dart_client: DartClient,
    ) -> None:
        self._session = session
        self._provider = provider
        self._dart = dart_client
        self._report_repo = AnalysisReportRepository(session)
        self._mapping_repo = DartCorpMappingRepository(session)
        self._stock_repo = StockRepository(session)
        self._price_repo = StockPriceRepository(session)
        self._signal_repo = SignalRepository(session)

    # ------------------------------------------------------------------

    async def generate(
        self, *, stock_code: str, force_refresh: bool = False
    ) -> ReportOutcome:
        today_kst = datetime.now(KST).date()

        if not force_refresh:
            cached = await self._report_repo.find_by_cache_key(stock_code, today_kst)
            if cached is not None:
                return self._to_outcome(cached, cache_hit=True)

        stock = await self._stock_repo.find_by_code(stock_code)
        if stock is None:
            raise StockNotFoundError(f"종목 마스터 미등록: {stock_code}")

        mapping = await self._mapping_repo.find_by_stock_code(stock_code)
        if mapping is None:
            raise CorpCodeNotMappedError(
                f"dart_corp_mapping 미등록: stock_code={stock_code}. "
                "DART bulk sync 를 먼저 수행하세요."
            )

        tier1 = await self._collect_tier1(stock, mapping.corp_code, today_kst)
        tier2 = await self._provider.collect_qualitative(
            stock_code=stock_code,
            stock_name=stock.stock_name,
            bgn_de=(today_kst - timedelta(days=self.DISCLOSURE_WINDOW_DAYS)).strftime("%Y%m%d"),
            end_de=today_kst.strftime("%Y%m%d"),
        )

        generated = await self._provider.analyze(tier1=tier1, tier2=tier2)
        generated = await self._provider.repackage(generated)

        # 공식 출처 링크를 Tier1 에서 자동 보강 — 모델이 sources 에 누락해도 최소치 보장
        merged_sources = self._merge_tier1_sources(generated, tier1)

        saved = await self._report_repo.save(
            stock_code=stock_code,
            report_date=today_kst,
            provider=generated.provider,
            model_id=generated.model_id,
            content={
                "summary": generated.content.summary,
                "strengths": generated.content.strengths,
                "risks": generated.content.risks,
                "outlook": generated.content.outlook,
                "opinion": generated.content.opinion,
                "disclaimer": generated.content.disclaimer or DEFAULT_DISCLAIMER,
            },
            sources=[asdict(s) for s in merged_sources],
            token_in=generated.token_in,
            token_out=generated.token_out,
            elapsed_ms=generated.elapsed_ms,
        )
        return self._to_outcome(saved, cache_hit=False)

    # ------------------------------------------------------------------
    # Tier1 collection
    # ------------------------------------------------------------------

    async def _collect_tier1(
        self, stock: Stock, corp_code: str, today: date
    ) -> Tier1Payload:
        company = await self._fetch_company_safe(corp_code)
        disclosures = await self._fetch_disclosures_safe(corp_code, today)
        financials = await self._fetch_financials_safe(corp_code, today)
        prices = await self._fetch_prices(stock.id, today)
        signals = await self._fetch_signals(stock.id, today)

        return Tier1Payload(
            stock_code=stock.stock_code,
            stock_name=stock.stock_name,
            company=company,
            disclosures=disclosures,
            financials=financials,
            prices=prices,
            signals=signals,
        )

    async def _fetch_company_safe(self, corp_code: str) -> Tier1CompanyInfo | None:
        try:
            info = await self._dart.fetch_company(corp_code)
        except DartClientError as exc:
            logger.warning("DART company 조회 실패(corp=%s): %s", corp_code, exc)
            return None
        if info is None:
            return None
        return Tier1CompanyInfo(
            corp_code=info.corp_code,
            corp_name=info.corp_name,
            ceo_nm=info.ceo_nm,
            corp_cls=info.corp_cls,
            induty_code=info.induty_code,
            est_dt=info.est_dt,
            hm_url=info.hm_url,
        )

    async def _fetch_disclosures_safe(
        self, corp_code: str, today: date
    ) -> list[Tier1DisclosureItem]:
        bgn = (today - timedelta(days=self.DISCLOSURE_WINDOW_DAYS)).strftime("%Y%m%d")
        end = today.strftime("%Y%m%d")
        try:
            rows = await self._dart.fetch_disclosures(
                corp_code, bgn_de=bgn, end_de=end, page_count=30
            )
        except DartClientError as exc:
            logger.warning("DART disclosures 조회 실패(corp=%s): %s", corp_code, exc)
            return []
        return [
            Tier1DisclosureItem(
                report_nm=r.report_nm,
                rcept_dt=r.rcept_dt,
                rcept_no=r.rcept_no,
                viewer_url=r.dart_viewer_url,
            )
            for r in rows
        ]

    async def _fetch_financials_safe(
        self, corp_code: str, today: date
    ) -> list[Tier1FinancialItem]:
        # 사업보고서 기준 연도 추정 — 보고서 공시 지연을 고려해 전년도
        bsns_year = today.year - 1
        try:
            stmt = await self._dart.fetch_financial_summary(
                corp_code, bsns_year=bsns_year, reprt_code="11011", fs_div="CFS"
            )
        except DartClientError as exc:
            logger.warning(
                "DART fnlttSinglAcntAll 조회 실패(corp=%s, year=%d): %s",
                corp_code, bsns_year, exc,
            )
            return []
        return [
            Tier1FinancialItem(
                account_nm=r.account_nm,
                sj_nm=r.sj_nm,
                thstrm_nm=r.thstrm_nm,
                thstrm_amount=r.thstrm_amount,
                frmtrm_amount=r.frmtrm_amount,
                currency=r.currency,
            )
            for r in stmt.rows
        ]

    async def _fetch_prices(
        self, stock_id: int, today: date
    ) -> list[Tier1PricePoint]:
        start = today - timedelta(days=self.PRICE_WINDOW_DAYS)
        rows = await self._price_repo.list_between(stock_id, start, today)
        return [
            Tier1PricePoint(
                trading_date=r.trading_date,
                close_price=r.close_price,
                change_rate=r.change_rate,
            )
            for r in rows
        ]

    async def _fetch_signals(
        self, stock_id: int, today: date
    ) -> list[Tier1SignalItem]:
        rows = await self._signal_repo.list_by_stock(stock_id, limit=20)
        return [
            Tier1SignalItem(
                signal_date=r.signal_date,
                signal_type=r.signal_type,
                score=r.score,
                grade=r.grade,
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Source merging / Output
    # ------------------------------------------------------------------

    def _merge_tier1_sources(
        self, generated: GeneratedReport, tier1: Tier1Payload
    ) -> list[ReportSource]:
        """모델이 빠뜨린 공식 링크를 Tier1 최상단 공시 / 기업홈 순으로 보강.
        저장 직전 is_safe_public_url 로 스킴 재검증해 javascript:/file: 등 차단.
        """
        auto: list[ReportSource] = []
        if tier1.company is not None and tier1.company.hm_url:
            url = tier1.company.hm_url.strip()
            # DART 기업개황 hm_url 은 종종 스킴이 생략된 "www.samsung.com" 형태 → https 우선 prepend.
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            if is_safe_public_url(url):
                auto.append(_official_source(url, f"{tier1.company.corp_name} 공식 홈페이지"))
        # 최근 공시 최대 3건
        for d in tier1.disclosures[:3]:
            if is_safe_public_url(d.viewer_url):
                auto.append(_dart_source(d.viewer_url, f"{d.report_nm} ({d.rcept_dt})", d.rcept_dt))
        # 기존 sources + 자동보강 합쳐 URL 중복 제거 + 스킴 최종 필터
        seen: set[str] = set()
        merged: list[ReportSource] = []
        for s in [*generated.sources, *auto]:
            if not is_safe_public_url(s.url):
                continue
            if s.url in seen:
                continue
            seen.add(s.url)
            merged.append(s)
        return merged

    def _to_outcome(self, row: AnalysisReport, *, cache_hit: bool) -> ReportOutcome:
        return ReportOutcome(
            stock_code=row.stock_code,
            report_date=row.report_date,
            provider=row.provider,
            model_id=row.model_id,
            content=dict(row.content or {}),
            sources=list(row.sources or []),
            cache_hit=cache_hit,
            token_in=row.token_in,
            token_out=row.token_out,
            elapsed_ms=row.elapsed_ms,
        )


def _dart_source(url: str, label: str, published_at: str | None = None) -> ReportSource:
    return ReportSource(tier=1, type="dart", url=url, label=label, published_at=published_at)


def _official_source(url: str, label: str) -> ReportSource:
    return ReportSource(tier=1, type="official", url=url, label=label)
