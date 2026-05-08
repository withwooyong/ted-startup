"""kiwoom.stock 테이블 — ka10099 종목 마스터 (B-α)

Revision ID: 003_kiwoom_stock
Revises: 002_kiwoom_sector
Create Date: 2026-05-08

설계: endpoint-03-ka10099.md § 5.1.

UNIQUE: stock_code 단일 — sector 의 복합키와 다름.
인덱스 4개:
- idx_stock_market_code: 시장 단위 조회 (full)
- idx_stock_nxt_enable: NXT 호출 큐 source (partial WHERE nxt_enable=true)
- idx_stock_active: 활성 종목 조회 (partial WHERE is_active=true)
- idx_stock_up_name: 업종별 분석 (partial WHERE up_name IS NOT NULL)
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "003_kiwoom_stock"
down_revision: str | Sequence[str] | None = "002_kiwoom_sector"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
CREATE TABLE kiwoom.stock (
    id                   BIGSERIAL       PRIMARY KEY,
    stock_code           VARCHAR(20)     NOT NULL,
    stock_name           VARCHAR(40)     NOT NULL,
    list_count           BIGINT,
    audit_info           VARCHAR(40),
    listed_date          DATE,
    last_price           BIGINT,
    state                VARCHAR(255),
    market_code          VARCHAR(4)      NOT NULL,
    market_name          VARCHAR(40),
    up_name              VARCHAR(40),
    up_size_name         VARCHAR(20),
    company_class_name   VARCHAR(40),
    order_warning        VARCHAR(1)      NOT NULL DEFAULT '0',
    nxt_enable           BOOLEAN         NOT NULL DEFAULT FALSE,
    is_active            BOOLEAN         NOT NULL DEFAULT TRUE,
    fetched_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_stock_code UNIQUE (stock_code)
);
COMMENT ON TABLE kiwoom.stock IS 'ka10099 종목 마스터 — 5 시장 (KOSPI/KOSDAQ/KONEX/ETN/REIT) 디폴트 sync';
COMMENT ON COLUMN kiwoom.stock.stock_code IS '종목 단축코드 (예: 005930). NXT/SOR suffix 는 영속화 안 함';
COMMENT ON COLUMN kiwoom.stock.market_code IS '요청 mrkt_tp 권위 있는 source (16종) — 응답 marketCode 는 영속화 안 함 (1R H1)';
COMMENT ON COLUMN kiwoom.stock.list_count IS '상장주식수 — 응답에서 zero-padded string → int 정규화';
COMMENT ON COLUMN kiwoom.stock.last_price IS '전일 종가 (KRW) — 응답에서 zero-padded string → int 정규화';
COMMENT ON COLUMN kiwoom.stock.state IS '종목상태 — 다중값 (예: ''증거금20%|담보대출|신용가능'')';
COMMENT ON COLUMN kiwoom.stock.order_warning IS '0:해당없음/1:ETF투자주의/2:정리매매/3:단기과열/4:투자위험/5:투자경과';
COMMENT ON COLUMN kiwoom.stock.nxt_enable IS 'NXT 가능여부 (응답 nxtEnable=Y → TRUE) — Phase C NXT 호출 큐 source';
COMMENT ON COLUMN kiwoom.stock.is_active IS '응답에 등장 시 TRUE, 같은 mrkt_tp sync 응답에서 누락 시 FALSE';

CREATE INDEX idx_stock_market_code ON kiwoom.stock(market_code);
CREATE INDEX idx_stock_nxt_enable  ON kiwoom.stock(nxt_enable) WHERE nxt_enable = TRUE;
CREATE INDEX idx_stock_active      ON kiwoom.stock(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_stock_up_name     ON kiwoom.stock(up_name)   WHERE up_name IS NOT NULL;
"""


DOWNGRADE_SQL = r"""
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM kiwoom.stock;
    IF v_count > 0 THEN
        RAISE EXCEPTION 'stock 데이터(%건) 가 있어 downgrade 차단. 수동 삭제 후 재시도.', v_count;
    END IF;
END $$;

DROP TABLE IF EXISTS kiwoom.stock CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
