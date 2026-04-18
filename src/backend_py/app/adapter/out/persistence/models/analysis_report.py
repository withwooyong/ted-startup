"""AI 분석 리포트 ORM 모델."""
from __future__ import annotations

from datetime import date as date_t
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base


class AnalysisReport(Base):
    __tablename__ = "analysis_report"
    __table_args__ = (
        UniqueConstraint("stock_code", "report_date", name="analysis_report_stock_date_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(6), nullable=False)
    report_date: Mapped[date_t] = mapped_column(Date, nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model_id: Mapped[str] = mapped_column(String(60), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    token_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
