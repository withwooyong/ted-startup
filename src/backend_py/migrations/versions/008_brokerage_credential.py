"""brokerage_account_credential — KIS 실계정 자격증명 암호화 저장소

설계: docs/kis-real-account-sync-plan.md § 3.2. Fernet 대칭 암호화 후 BYTEA 저장.
계좌당 1 레코드 (UNIQUE), 계좌 삭제 시 CASCADE.

Revision ID: 008_brokerage_credential
Revises: 007_kis_real_connection
Create Date: 2026-04-21
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "008_brokerage_credential"
down_revision: str | Sequence[str] | None = "007_kis_real_connection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
CREATE TABLE brokerage_account_credential (
    id                  BIGSERIAL       PRIMARY KEY,
    account_id          BIGINT          NOT NULL UNIQUE
                            REFERENCES brokerage_account(id) ON DELETE CASCADE,
    app_key_cipher      BYTEA           NOT NULL,
    app_secret_cipher   BYTEA           NOT NULL,
    account_no_cipher   BYTEA           NOT NULL,
    key_version         INTEGER         NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE brokerage_account_credential IS 'KIS 실계정 자격증명 Fernet 암호화 저장소';
COMMENT ON COLUMN brokerage_account_credential.key_version IS '마스터키 회전 대비. 현재 v1 만 사용';
"""


DOWNGRADE_SQL = r"""
-- 운영 환경 downgrade 안전망: 데이터가 있으면 DROP 하지 않고 실패로 유도.
-- 실수로 자격증명 전체가 복구 불가 상태로 사라지는 시나리오 방어.
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM brokerage_account_credential;
    IF v_count > 0 THEN
        RAISE EXCEPTION '자격증명 데이터(%건) 가 있어 downgrade 차단. 수동 삭제 후 재시도.', v_count;
    END IF;
END $$;

DROP TABLE IF EXISTS brokerage_account_credential CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
