"""kiwoom.sector 테이블 — ka10101 업종 마스터

Revision ID: 002_kiwoom_sector
Revises: 001_init_kiwoom_schema
Create Date: 2026-05-08

설계: endpoint-14-ka10101.md § 5.1.

UNIQUE(market_code, sector_code) — upsert 키.
인덱스 2개 — market_code (시장 단위 조회) / is_active partial (활성 row 조회).

`fundamental` 테이블은 Phase B (ka10001) 로 분리 — 본 마이그레이션은 sector 단독.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "002_kiwoom_sector"
down_revision: str | Sequence[str] | None = "001_init_kiwoom_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
CREATE TABLE kiwoom.sector (
    id              BIGSERIAL       PRIMARY KEY,
    market_code     VARCHAR(2)      NOT NULL,
    sector_code     VARCHAR(10)     NOT NULL,
    sector_name     VARCHAR(100)    NOT NULL,
    group_no        VARCHAR(10),
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    fetched_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sector_market_code UNIQUE (market_code, sector_code),
    CONSTRAINT ck_sector_market_code CHECK (market_code IN ('0', '1', '2', '4', '7'))
);
COMMENT ON TABLE kiwoom.sector IS 'ka10101 업종 마스터 — 5 시장 (KOSPI/KOSDAQ/KOSPI200/KOSPI100/KRX100)';
COMMENT ON COLUMN kiwoom.sector.market_code IS '0:코스피 / 1:코스닥 / 2:KOSPI200 / 4:KOSPI100 / 7:KRX100';
COMMENT ON COLUMN kiwoom.sector.is_active IS '응답에 등장하면 TRUE, 폐지/제외 시 FALSE — 디액티베이션 정책 B';
COMMENT ON COLUMN kiwoom.sector.fetched_at IS '마지막 동기화 시각 — sync 진단';

CREATE INDEX idx_sector_market ON kiwoom.sector(market_code);
CREATE INDEX idx_sector_active ON kiwoom.sector(is_active) WHERE is_active = TRUE;
"""


DOWNGRADE_SQL = r"""
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM kiwoom.sector;
    IF v_count > 0 THEN
        RAISE EXCEPTION 'sector 데이터(%건) 가 있어 downgrade 차단. 수동 삭제 후 재시도.', v_count;
    END IF;
END $$;

DROP TABLE IF EXISTS kiwoom.sector CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
