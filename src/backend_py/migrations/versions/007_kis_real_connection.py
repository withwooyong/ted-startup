"""brokerage_account.connection_type 에 'kis_rest_real' 추가

KIS sync PR 2 — 실거래 연결 타입 스캐폴딩. 이번 PR 에서는 외부 호출 0.
credential 저장소(`brokerage_account_credential`) 는 PR 3 에서 추가.

Revision ID: 007_kis_real_connection
Revises: 006_portfolio_excel_source
Create Date: 2026-04-21
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "007_kis_real_connection"
down_revision: str | Sequence[str] | None = "006_portfolio_excel_source"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
ALTER TABLE brokerage_account
    DROP CONSTRAINT brokerage_account_connection_type_check;
ALTER TABLE brokerage_account
    ADD CONSTRAINT brokerage_account_connection_type_check
        CHECK (connection_type IN ('manual', 'kis_rest_mock', 'kis_rest_real'));
"""


DOWNGRADE_SQL = r"""
-- 'kis_rest_real' 행이 있으면 downgrade 불가 — 먼저 삭제 또는 타입 변경 필요.
ALTER TABLE brokerage_account
    DROP CONSTRAINT brokerage_account_connection_type_check;
ALTER TABLE brokerage_account
    ADD CONSTRAINT brokerage_account_connection_type_check
        CHECK (connection_type IN ('manual', 'kis_rest_mock'));
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
