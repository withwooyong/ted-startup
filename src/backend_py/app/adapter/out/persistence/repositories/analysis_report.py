"""AnalysisReport Repository — 24h 캐시 키 기반 조회·저장."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import AnalysisReport


class AnalysisReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_cache_key(self, stock_code: str, report_date: date) -> AnalysisReport | None:
        stmt = (
            select(AnalysisReport)
            .where(
                AnalysisReport.stock_code == stock_code,
                AnalysisReport.report_date == report_date,
            )
            .execution_options(populate_existing=True)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def save(
        self,
        *,
        stock_code: str,
        report_date: date,
        provider: str,
        model_id: str,
        content: dict[str, Any],
        sources: list[dict[str, Any]],
        token_in: int | None = None,
        token_out: int | None = None,
        elapsed_ms: int | None = None,
    ) -> AnalysisReport:
        """force_refresh 경로에서는 동일 (stock_code, report_date) 가 이미 있을 수 있으므로
        upsert 동작: 존재하면 덮어쓰기, 없으면 insert."""
        existing = await self.find_by_cache_key(stock_code, report_date)
        if existing is None:
            row = AnalysisReport(
                stock_code=stock_code,
                report_date=report_date,
                provider=provider,
                model_id=model_id,
                content=content,
                sources=sources,
                token_in=token_in,
                token_out=token_out,
                elapsed_ms=elapsed_ms,
            )
            self._session.add(row)
            await self._session.flush()
            await self._session.refresh(row)
            return row
        existing.provider = provider
        existing.model_id = model_id
        existing.content = content
        existing.sources = sources
        existing.token_in = token_in
        existing.token_out = token_out
        existing.elapsed_ms = elapsed_ms
        await self._session.flush()
        return existing
