"""portfolio_transaction.source CHECK 에 'excel_import' 추가

P10 온보딩 1단계: 증권사 엑셀 거래내역 import 를 별도 source 로 구분.
기존 ('manual', 'kis_sync') 에 'excel_import' 추가 — 기존 행 영향 없음.

Revision ID: 006_portfolio_excel_source
Revises: 005_analysis_report
Create Date: 2026-04-20
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "006_portfolio_excel_source"
down_revision: str | Sequence[str] | None = "005_analysis_report"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
ALTER TABLE portfolio_transaction
    DROP CONSTRAINT portfolio_transaction_source_check;
ALTER TABLE portfolio_transaction
    ADD CONSTRAINT portfolio_transaction_source_check
        CHECK (source IN ('manual', 'kis_sync', 'excel_import'));
"""


DOWNGRADE_SQL = r"""
-- 'excel_import' 행이 있으면 downgrade 불가 — 먼저 삭제 필요.
ALTER TABLE portfolio_transaction
    DROP CONSTRAINT portfolio_transaction_source_check;
ALTER TABLE portfolio_transaction
    ADD CONSTRAINT portfolio_transaction_source_check
        CHECK (source IN ('manual', 'kis_sync'));
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
