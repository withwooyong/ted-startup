"""kiwoom 스키마 + 자격증명/토큰/원본응답 3 테이블

Revision ID: 001_init_kiwoom_schema
Revises:
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "001_init_kiwoom_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
CREATE SCHEMA IF NOT EXISTS kiwoom;

CREATE TABLE kiwoom.kiwoom_credential (
    id                  BIGSERIAL       PRIMARY KEY,
    alias               VARCHAR(50)     NOT NULL UNIQUE,
    env                 VARCHAR(10)     NOT NULL,
    appkey_cipher       BYTEA           NOT NULL,
    secretkey_cipher    BYTEA           NOT NULL,
    key_version         INTEGER         NOT NULL DEFAULT 1,
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_kiwoom_credential_env CHECK (env IN ('prod', 'mock'))
);
COMMENT ON TABLE kiwoom.kiwoom_credential IS '키움 자격증명 — Fernet 암호화 BYTEA 저장';
COMMENT ON COLUMN kiwoom.kiwoom_credential.key_version IS '마스터키 회전 대비. 현재 v1 만 사용';
COMMENT ON COLUMN kiwoom.kiwoom_credential.env IS 'prod (api.kiwoom.com) | mock (mockapi.kiwoom.com)';

CREATE INDEX idx_kw_cred_env_active ON kiwoom.kiwoom_credential(env, is_active);

CREATE TABLE kiwoom.kiwoom_token (
    id              BIGSERIAL       PRIMARY KEY,
    credential_id   BIGINT          NOT NULL
                        REFERENCES kiwoom.kiwoom_credential(id) ON DELETE CASCADE,
    token_cipher    BYTEA           NOT NULL,
    token_type      VARCHAR(20)     NOT NULL DEFAULT 'bearer',
    expires_at      TIMESTAMPTZ     NOT NULL,
    issued_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_kiwoom_token_credential_id UNIQUE (credential_id)
);
COMMENT ON TABLE kiwoom.kiwoom_token IS '발급된 키움 접근토큰 캐시 (선택). 자격증명당 1 row.';

CREATE INDEX idx_kw_token_expires ON kiwoom.kiwoom_token(expires_at);

CREATE TABLE kiwoom.raw_response (
    id                  BIGSERIAL       PRIMARY KEY,
    api_id              VARCHAR(20)     NOT NULL,
    request_hash        VARCHAR(64)     NOT NULL,
    request_payload     JSONB           NOT NULL,
    response_payload    JSONB           NOT NULL,
    http_status         INTEGER         NOT NULL,
    fetched_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE kiwoom.raw_response IS '키움 API 응답 원본 JSON — 재처리·디버깅 용. 90일 retention 권장';

CREATE INDEX idx_kw_raw_api_id ON kiwoom.raw_response(api_id);
CREATE INDEX idx_kw_raw_request_hash ON kiwoom.raw_response(request_hash);
CREATE INDEX idx_kw_raw_fetched_at ON kiwoom.raw_response(fetched_at);
"""


DOWNGRADE_SQL = r"""
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM kiwoom.kiwoom_credential;
    IF v_count > 0 THEN
        RAISE EXCEPTION '자격증명 데이터(%건) 가 있어 downgrade 차단. 수동 삭제 후 재시도.', v_count;
    END IF;
END $$;

DROP TABLE IF EXISTS kiwoom.raw_response CASCADE;
DROP TABLE IF EXISTS kiwoom.kiwoom_token CASCADE;
DROP TABLE IF EXISTS kiwoom.kiwoom_credential CASCADE;
-- 스키마 자체는 보존. 다른 마이그레이션 (002~) 에서 동일 스키마 재사용.
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
