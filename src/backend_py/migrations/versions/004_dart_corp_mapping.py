"""P13a DART 기업코드 매핑 테이블

DART OpenAPI 는 KRX 종목코드(6자리)가 아닌 고유 기업코드(8자리) 기준으로 요청한다.
전체 ~40,000 건은 DART 의 corpCode.xml 일괄 파일로 제공되며, 본 테이블이 캐시 역할.

Revision ID: 004_dart_corp_mapping
Revises: 003_portfolio_schema
Create Date: 2026-04-18
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "004_dart_corp_mapping"
down_revision: str | Sequence[str] | None = "003_portfolio_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
CREATE TABLE dart_corp_mapping (
    stock_code    VARCHAR(6)   PRIMARY KEY,
    corp_code     VARCHAR(8)   NOT NULL UNIQUE,
    corp_name     VARCHAR(100) NOT NULL,
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE dart_corp_mapping IS 'DART 기업코드(8자리) ↔ KRX 종목코드(6자리) 매핑';
COMMENT ON COLUMN dart_corp_mapping.corp_code IS 'DART 고유 기업코드';
CREATE INDEX idx_dart_corp_mapping_corp_code ON dart_corp_mapping(corp_code);
"""


DOWNGRADE_SQL = "DROP TABLE IF EXISTS dart_corp_mapping CASCADE;"


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
