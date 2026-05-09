"""kiwoom.stock_price_weekly_nxt 테이블 — ka10082 NXT 주봉 OHLCV (C-3α)

Revision ID: 010_stock_price_weekly_nxt
Revises: 009_stock_price_weekly_krx
Create Date: 2026-05-09

설계: phase-c-3-weekly-monthly-ohlcv.md § 3.1 + endpoint-07-ka10082.md § 5.1.

stock_price_weekly_krx 와 컬럼 구조 동일 — KRX/NXT 분리 정책 (C-1α 패턴 일관).
호출 게이팅: NXT 호출 전 stock.nxt_enable=true 검증 (Phase B-α 정책 일관).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "010_stock_price_weekly_nxt"
down_revision: str | Sequence[str] | None = "009_stock_price_weekly_krx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
CREATE TABLE kiwoom.stock_price_weekly_nxt (
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

    CONSTRAINT uq_price_weekly_nxt_stock_date UNIQUE (stock_id, trading_date, adjusted)
);

COMMENT ON TABLE kiwoom.stock_price_weekly_nxt IS 'ka10082 NXT 주봉 OHLCV — 거래소 분리 (C-3α)';
COMMENT ON COLUMN kiwoom.stock_price_weekly_nxt.trading_date IS '주의 첫 거래일 (가설 — 운영 first-call 후 확정)';
COMMENT ON COLUMN kiwoom.stock_price_weekly_nxt.adjusted IS '수정주가 여부 — TRUE=upd_stkpc_tp=1';
COMMENT ON COLUMN kiwoom.stock_price_weekly_nxt.prev_compare_amount IS '직전 주 대비 (period=weekly 의미)';
COMMENT ON COLUMN kiwoom.stock_price_weekly_nxt.prev_compare_sign IS '1:상한/2:상승/3:보합/4:하한/5:하락';

CREATE INDEX idx_price_weekly_nxt_trading_date ON kiwoom.stock_price_weekly_nxt(trading_date);
CREATE INDEX idx_price_weekly_nxt_stock_id     ON kiwoom.stock_price_weekly_nxt(stock_id);
"""


DOWNGRADE_SQL = r"""
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM kiwoom.stock_price_weekly_nxt;
    IF v_count > 0 THEN
        RAISE EXCEPTION 'stock_price_weekly_nxt 데이터(%건) 가 있어 downgrade 차단. 수동 삭제 후 재시도.', v_count;
    END IF;
END $$;

DROP TABLE IF EXISTS kiwoom.stock_price_weekly_nxt CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
