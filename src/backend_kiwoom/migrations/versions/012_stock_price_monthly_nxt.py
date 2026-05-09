"""kiwoom.stock_price_monthly_nxt 테이블 — ka10083 NXT 월봉 OHLCV (C-3α)

Revision ID: 012_stock_price_monthly_nxt
Revises: 011_stock_price_monthly_krx
Create Date: 2026-05-09

설계: phase-c-3-weekly-monthly-ohlcv.md § 3.1 + endpoint-08-ka10083.md § 5.1.

stock_price_monthly_krx 와 컬럼 구조 동일 — KRX/NXT 분리 정책.
호출 게이팅: NXT 호출 전 stock.nxt_enable=true 검증.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "012_stock_price_monthly_nxt"
down_revision: str | Sequence[str] | None = "011_stock_price_monthly_krx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
CREATE TABLE kiwoom.stock_price_monthly_nxt (
    id                   BIGSERIAL       PRIMARY KEY,
    stock_id             BIGINT          NOT NULL REFERENCES kiwoom.stock(id) ON DELETE CASCADE,
    trading_date         DATE            NOT NULL,
    adjusted             BOOLEAN         NOT NULL DEFAULT TRUE,

    open_price           BIGINT,
    high_price           BIGINT,
    low_price            BIGINT,
    close_price          BIGINT,
    trade_volume         BIGINT,
    trade_amount         BIGINT,
    prev_compare_amount  BIGINT,
    prev_compare_sign    CHAR(1),
    turnover_rate        NUMERIC(8, 4),

    fetched_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_price_monthly_nxt_stock_date UNIQUE (stock_id, trading_date, adjusted)
);

COMMENT ON TABLE kiwoom.stock_price_monthly_nxt IS 'ka10083 NXT 월봉 OHLCV — 거래소 분리 (C-3α)';
COMMENT ON COLUMN kiwoom.stock_price_monthly_nxt.trading_date IS '달의 첫 거래일 (가설 — 운영 first-call 후 확정)';
COMMENT ON COLUMN kiwoom.stock_price_monthly_nxt.adjusted IS '수정주가 여부 — TRUE=upd_stkpc_tp=1';
COMMENT ON COLUMN kiwoom.stock_price_monthly_nxt.prev_compare_amount IS '직전 달 대비 (period=monthly 의미)';
COMMENT ON COLUMN kiwoom.stock_price_monthly_nxt.prev_compare_sign IS '1:상한/2:상승/3:보합/4:하한/5:하락';

CREATE INDEX idx_price_monthly_nxt_trading_date ON kiwoom.stock_price_monthly_nxt(trading_date);
CREATE INDEX idx_price_monthly_nxt_stock_id     ON kiwoom.stock_price_monthly_nxt(stock_id);
"""


DOWNGRADE_SQL = r"""
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM kiwoom.stock_price_monthly_nxt;
    IF v_count > 0 THEN
        RAISE EXCEPTION 'stock_price_monthly_nxt 데이터(%건) 가 있어 downgrade 차단. 수동 삭제 후 재시도.', v_count;
    END IF;
END $$;

DROP TABLE IF EXISTS kiwoom.stock_price_monthly_nxt CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
