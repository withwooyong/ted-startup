"""kiwoom.stock_price_weekly_krx 테이블 — ka10082 KRX 주봉 OHLCV (C-3α)

Revision ID: 009_stock_price_weekly_krx
Revises: 008_drop_daily_flow_dup_columns
Create Date: 2026-05-09

설계: phase-c-3-weekly-monthly-ohlcv.md § 3.1 + endpoint-07-ka10082.md § 5.1.

stock_price_krx (Migration 005) 와 컬럼 구조 100% 동일 — `_DailyOhlcvMixin` 재사용.
trading_date 의미만 다름 (주의 첫 거래일 — 가설, 운영 검증 후 확정).

UNIQUE: (stock_id, trading_date, adjusted).
FK: stock_id → kiwoom.stock(id) ON DELETE CASCADE.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "009_stock_price_weekly_krx"
down_revision: str | Sequence[str] | None = "008_drop_daily_flow_dup_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
CREATE TABLE kiwoom.stock_price_weekly_krx (
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

    CONSTRAINT uq_price_weekly_krx_stock_date UNIQUE (stock_id, trading_date, adjusted)
);

COMMENT ON TABLE kiwoom.stock_price_weekly_krx IS 'ka10082 KRX 주봉 OHLCV — 백테스팅 중장기 시그널 (C-3α)';
COMMENT ON COLUMN kiwoom.stock_price_weekly_krx.trading_date IS '주의 첫 거래일 (가설 — 운영 first-call 후 확정)';
COMMENT ON COLUMN kiwoom.stock_price_weekly_krx.adjusted IS '수정주가 여부 — TRUE=upd_stkpc_tp=1 (백테스팅 디폴트)';
COMMENT ON COLUMN kiwoom.stock_price_weekly_krx.prev_compare_amount IS '직전 주 대비 (period=weekly 의미)';
COMMENT ON COLUMN kiwoom.stock_price_weekly_krx.prev_compare_sign IS '1:상한/2:상승/3:보합/4:하한/5:하락';
COMMENT ON COLUMN kiwoom.stock_price_weekly_krx.turnover_rate IS '거래회전율 % — 부호 보존 가능';

CREATE INDEX idx_price_weekly_krx_trading_date ON kiwoom.stock_price_weekly_krx(trading_date);
CREATE INDEX idx_price_weekly_krx_stock_id     ON kiwoom.stock_price_weekly_krx(stock_id);
"""


DOWNGRADE_SQL = r"""
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM kiwoom.stock_price_weekly_krx;
    IF v_count > 0 THEN
        RAISE EXCEPTION 'stock_price_weekly_krx 데이터(%건) 가 있어 downgrade 차단. 수동 삭제 후 재시도.', v_count;
    END IF;
END $$;

DROP TABLE IF EXISTS kiwoom.stock_price_weekly_krx CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
