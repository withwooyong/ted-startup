"""P13b AI 분석 리포트 저장 테이블

§11.2 실시간 온디맨드 + 24h 캐시 정책의 저장 계층. (stock_code,
report_date) 복합 유니크로 동일 일자 중복 생성을 DB 레벨에서 차단.

Revision ID: 005_analysis_report
Revises: 004_dart_corp_mapping
Create Date: 2026-04-18
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "005_analysis_report"
down_revision: str | Sequence[str] | None = "004_dart_corp_mapping"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
CREATE TABLE analysis_report (
    id              BIGSERIAL     PRIMARY KEY,
    stock_code      VARCHAR(6)    NOT NULL,
    report_date     DATE          NOT NULL,
    provider        VARCHAR(30)   NOT NULL,
    model_id        VARCHAR(60)   NOT NULL,
    content         JSONB         NOT NULL,
    sources         JSONB         NOT NULL DEFAULT '[]'::jsonb,
    token_in        INTEGER,
    token_out       INTEGER,
    elapsed_ms      INTEGER,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (stock_code, report_date)
);
COMMENT ON TABLE analysis_report IS 'AI 생성 종목 분석 리포트 (KST 일 단위 캐시)';
COMMENT ON COLUMN analysis_report.sources IS '[{tier:1|2, type, url, label, published_at?}]';
COMMENT ON COLUMN analysis_report.content IS 'summary/strengths/risks/outlook/opinion/disclaimer';

CREATE INDEX idx_analysis_report_stock_date
    ON analysis_report(stock_code, report_date DESC);
"""


DOWNGRADE_SQL = "DROP TABLE IF EXISTS analysis_report CASCADE;"


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
