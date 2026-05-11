"""kiwoom.stock_price_yearly_{krx,nxt} 테이블 — ka10094 년봉 OHLCV (C-4).

Revision ID: 014_stock_price_yearly
Revises: 013_drop_daily_flow_dup_2
Create Date: 2026-05-11

설계: endpoint-09-ka10094.md § 12.

011 (월봉 KRX) + 012 (월봉 NXT) 패턴 1:1 응용. 컬럼 구조 4 테이블 동일 (`_DailyOhlcvMixin`).
trading_date = 그 해의 첫 거래일 (가설 — 운영 first-call 후 확정).

NXT 테이블은 정책 (plan doc § 12.2 #3) 으로 영속화 안 함 — 테이블만 존재 (향후 NXT skip
해제 chunk 시 활용). KRX/NXT 분리 (#2) 일관성 유지.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "014_stock_price_yearly"
down_revision: str | Sequence[str] | None = "013_drop_daily_flow_dup_2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
CREATE TABLE kiwoom.stock_price_yearly_krx (
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

    CONSTRAINT uq_price_yearly_krx_stock_date UNIQUE (stock_id, trading_date, adjusted)
);

COMMENT ON TABLE kiwoom.stock_price_yearly_krx IS 'ka10094 KRX 년봉 OHLCV — 백테스팅 초장기 시그널 (C-4)';
COMMENT ON COLUMN kiwoom.stock_price_yearly_krx.trading_date IS '해의 첫 거래일 (가설 — 운영 first-call 후 확정)';
COMMENT ON COLUMN kiwoom.stock_price_yearly_krx.adjusted IS '수정주가 여부 — TRUE=upd_stkpc_tp=1';
COMMENT ON COLUMN kiwoom.stock_price_yearly_krx.prev_compare_amount IS '직전 해 대비 (period=yearly 의미) — ka10094 응답에 없음, NULL 영속 (C-4)';
COMMENT ON COLUMN kiwoom.stock_price_yearly_krx.prev_compare_sign IS '직전 해 대비 부호 — ka10094 응답에 없음, NULL 영속 (C-4)';
COMMENT ON COLUMN kiwoom.stock_price_yearly_krx.turnover_rate IS '회전율 — ka10094 응답에 없음, NULL 영속 (C-4)';

CREATE INDEX idx_price_yearly_krx_trading_date ON kiwoom.stock_price_yearly_krx(trading_date);
CREATE INDEX idx_price_yearly_krx_stock_id     ON kiwoom.stock_price_yearly_krx(stock_id);


CREATE TABLE kiwoom.stock_price_yearly_nxt (
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

    CONSTRAINT uq_price_yearly_nxt_stock_date UNIQUE (stock_id, trading_date, adjusted)
);

COMMENT ON TABLE kiwoom.stock_price_yearly_nxt IS 'ka10094 NXT 년봉 OHLCV — 본 chunk 정책상 호출 안 함 (yearly_nxt_disabled, plan § 12.2 #3). 향후 NXT skip 해제 chunk 시 활용';

CREATE INDEX idx_price_yearly_nxt_trading_date ON kiwoom.stock_price_yearly_nxt(trading_date);
CREATE INDEX idx_price_yearly_nxt_stock_id     ON kiwoom.stock_price_yearly_nxt(stock_id);
"""


DOWNGRADE_SQL = r"""
DO $$
DECLARE
    v_krx INTEGER;
    v_nxt INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_krx FROM kiwoom.stock_price_yearly_krx;
    SELECT COUNT(*) INTO v_nxt FROM kiwoom.stock_price_yearly_nxt;
    IF v_krx > 0 OR v_nxt > 0 THEN
        RAISE EXCEPTION 'stock_price_yearly_krx(%건) / stock_price_yearly_nxt(%건) 데이터가 있어 downgrade 차단. 수동 삭제 후 재시도.', v_krx, v_nxt;
    END IF;
END $$;

DROP TABLE IF EXISTS kiwoom.stock_price_yearly_nxt CASCADE;
DROP TABLE IF EXISTS kiwoom.stock_price_yearly_krx CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
