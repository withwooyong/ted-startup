"""/api/reports/* — AI 분석 리포트 (§11.3 온디맨드)."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.external import DartClient
from app.adapter.web._deps import (
    get_dart_client,
    get_llm_provider,
    get_session,
    require_admin_key,
)
from app.adapter.web._rate_limit import limiter
from app.adapter.web._schemas import AnalysisReportResponse
from app.application.port.out.llm_provider import LLMProvider
from app.application.service.analysis_report_service import (
    AnalysisReportError,
    AnalysisReportService,
    CorpCodeNotMappedError,
    StockNotFoundError,
)
from app.config.settings import get_settings

router = APIRouter(
    prefix="/api/reports",
    tags=["reports"],
    dependencies=[Depends(require_admin_key)],
)


def _ai_report_limit() -> str:
    """슬로우api limit 값을 런타임에 조회 — 테스트가 settings override 할 여지 유지."""
    return get_settings().ai_report_rate_limit


@router.post("/{stock_code}", response_model=AnalysisReportResponse)
@limiter.limit(_ai_report_limit)
async def generate_report(
    request: Request,  # slowapi 가 요청 메타 접근에 필수
    stock_code: str = Path(..., pattern=r"^\d{6}$"),
    force_refresh: bool = Query(False),
    session: AsyncSession = Depends(get_session),
    provider: LLMProvider = Depends(get_llm_provider),
    dart: DartClient = Depends(get_dart_client),
) -> AnalysisReportResponse:
    service = AnalysisReportService(session, provider=provider, dart_client=dart)
    try:
        outcome = await service.generate(stock_code=stock_code, force_refresh=force_refresh)
    except StockNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CorpCodeNotMappedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AnalysisReportError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return AnalysisReportResponse.model_validate(asdict(outcome))
