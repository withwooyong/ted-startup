"""kiwoom.stock_price_nxt 테이블 — ka10081 NXT 일봉 OHLCV (C-1α)

Revision ID: 006_kiwoom_stock_price_nxt
Revises: 005_kiwoom_stock_price_krx
Create Date: 2026-05-08

설계: endpoint-06-ka10081.md § 5.1.

stock_price_krx 와 같은 컬럼 구조 — 운영 중 NXT 활성화/비활성화 토글 가능하게 분리 마이그레이션.
KRX/NXT 가격은 같은 종목·같은 날도 다를 수 있음 (계획서 § 4.2 KRX/NXT 시세 분리).

호출 게이팅: NXT 호출 전 `stock.nxt_enable=true` 검증 (Phase B-α 정책 일관).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "006_kiwoom_stock_price_nxt"
down_revision: str | Sequence[str] | None = "005_kiwoom_stock_price_krx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
CREATE TABLE kiwoom.stock_price_nxt (
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

    CONSTRAINT uq_price_nxt_stock_date UNIQUE (stock_id, trading_date, adjusted)
);

COMMENT ON TABLE kiwoom.stock_price_nxt IS 'ka10081 NXT 일봉 OHLCV — 거래소 분리 (C-1α)';
COMMENT ON COLUMN kiwoom.stock_price_nxt.adjusted IS '수정주가 여부 — TRUE=upd_stkpc_tp=1 (백테스팅 디폴트), FALSE=원본';

CREATE INDEX idx_price_nxt_trading_date ON kiwoom.stock_price_nxt(trading_date);
CREATE INDEX idx_price_nxt_stock_id     ON kiwoom.stock_price_nxt(stock_id);
"""


DOWNGRADE_SQL = r"""
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM kiwoom.stock_price_nxt;
    IF v_count > 0 THEN
        RAISE EXCEPTION 'stock_price_nxt 데이터(%건) 가 있어 downgrade 차단. 수동 삭제 후 재시도.', v_count;
    END IF;
END $$;

DROP TABLE IF EXISTS kiwoom.stock_price_nxt CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
