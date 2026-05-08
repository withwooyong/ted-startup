"""kiwoom.stock_price_krx 테이블 — ka10081 KRX 일봉 OHLCV (C-1α)

Revision ID: 005_kiwoom_stock_price_krx
Revises: 004_kiwoom_stock_fundamental
Create Date: 2026-05-08

설계: endpoint-06-ka10081.md § 5.1.

UNIQUE: (stock_id, trading_date, adjusted) — 같은 종목/일자/수정주가 1행.
FK: stock_id → kiwoom.stock(id) ON DELETE CASCADE.

분리 정책 (master.md § 3.1): KRX/NXT 가격이 같은 종목·같은 날에도 다를 수 있고, 수집 실패
격리·재현성 추적·백테스팅 시나리오 분기를 위해 stock_price_nxt 와 별도 테이블.

raw vs adjusted 분리: `adjusted` boolean PK 일부 — `upd_stkpc_tp=1` (수정주가, 백테스팅 디폴트)
와 `upd_stkpc_tp=0` (원본) 두 row 동시 보유 가능.

인덱스 2개:
- idx_price_krx_trading_date: 백테스팅 시점 조회 (전체 종목 같은 날)
- idx_price_krx_stock_id: 종목 단위 시계열 조회
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "005_kiwoom_stock_price_krx"
down_revision: str | Sequence[str] | None = "004_kiwoom_stock_fundamental"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
CREATE TABLE kiwoom.stock_price_krx (
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

    CONSTRAINT uq_price_krx_stock_date UNIQUE (stock_id, trading_date, adjusted)
);

COMMENT ON TABLE kiwoom.stock_price_krx IS 'ka10081 KRX 일봉 OHLCV — 백테스팅 코어 (C-1α)';
COMMENT ON COLUMN kiwoom.stock_price_krx.adjusted IS '수정주가 여부 — TRUE=upd_stkpc_tp=1 (백테스팅 디폴트), FALSE=원본';
COMMENT ON COLUMN kiwoom.stock_price_krx.prev_compare_sign IS '1:상한/2:상승/3:보합/4:하한/5:하락';
COMMENT ON COLUMN kiwoom.stock_price_krx.turnover_rate IS '거래회전율 % — 부호 보존 가능 (Decimal 정규화)';

CREATE INDEX idx_price_krx_trading_date ON kiwoom.stock_price_krx(trading_date);
CREATE INDEX idx_price_krx_stock_id     ON kiwoom.stock_price_krx(stock_id);
"""


DOWNGRADE_SQL = r"""
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM kiwoom.stock_price_krx;
    IF v_count > 0 THEN
        RAISE EXCEPTION 'stock_price_krx 데이터(%건) 가 있어 downgrade 차단. 수동 삭제 후 재시도.', v_count;
    END IF;
END $$;

DROP TABLE IF EXISTS kiwoom.stock_price_krx CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
