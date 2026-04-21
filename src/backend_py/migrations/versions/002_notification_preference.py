"""V2 알림 설정 테이블 (Java Flyway V2__notification_preference.sql 동일 이식)

Revision ID: 002_notification_preference
Revises: 001_init_schema
Create Date: 2026-04-18
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "002_notification_preference"
down_revision: str | Sequence[str] | None = "001_init_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
CREATE TABLE notification_preference (
    id                      BIGINT       PRIMARY KEY,
    daily_summary_enabled   BOOLEAN      NOT NULL DEFAULT TRUE,
    urgent_alert_enabled    BOOLEAN      NOT NULL DEFAULT TRUE,
    batch_failure_enabled   BOOLEAN      NOT NULL DEFAULT TRUE,
    weekly_report_enabled   BOOLEAN      NOT NULL DEFAULT TRUE,
    min_score               INTEGER      NOT NULL DEFAULT 60 CHECK (min_score BETWEEN 0 AND 100),
    signal_types            JSONB        NOT NULL DEFAULT '["RAPID_DECLINE","TREND_REVERSAL","SHORT_SQUEEZE"]'::jsonb,
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE notification_preference IS '사용자 알림 설정 (싱글 로우, id=1)';
COMMENT ON COLUMN notification_preference.min_score IS '필터 임계값 (이 스코어 미만 시그널은 알림 제외)';
COMMENT ON COLUMN notification_preference.signal_types IS '알림 대상 시그널 타입 배열';

INSERT INTO notification_preference (id) VALUES (1) ON CONFLICT (id) DO NOTHING;
"""


DOWNGRADE_SQL = "DROP TABLE IF EXISTS notification_preference CASCADE;"


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
