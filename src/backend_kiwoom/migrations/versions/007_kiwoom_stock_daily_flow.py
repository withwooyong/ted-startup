"""kiwoom.stock_daily_flow 테이블 — ka10086 일별 수급 (C-2α)

Revision ID: 007_kiwoom_stock_daily_flow
Revises: 006_kiwoom_stock_price_nxt
Create Date: 2026-05-09

설계: endpoint-10-ka10086.md § 5.1.

UNIQUE: (stock_id, trading_date, exchange) — KRX/NXT 분리 row.
FK: stock_id → kiwoom.stock(id) ON DELETE CASCADE.

13 도메인 컬럼 + 2 메타 (exchange / indc_mode):
- C. 신용 (2): credit_rate / credit_balance_rate
- D. 투자자별 net (4): individual_net / institutional_net / foreign_brokerage_net / program_net
- E. 외인 + 순매수 (7): foreign_volume / foreign_rate / foreign_holdings / foreign_weight
                        / foreign_net_purchase / institutional_net_purchase / individual_net_purchase

OHLCV 8 필드 (open_price ~ amt_mn) 는 ka10081 stock_price_krx/nxt 가 정답 — 본 테이블 미적재.

인덱스 3개:
- idx_daily_flow_trading_date: 백테스팅 시점 조회 (전체 종목 같은 날)
- idx_daily_flow_stock_id: 종목 단위 시계열 조회
- idx_daily_flow_exchange: 거래소 분리 집계
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "007_kiwoom_stock_daily_flow"
down_revision: str | Sequence[str] | None = "006_kiwoom_stock_price_nxt"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
CREATE TABLE kiwoom.stock_daily_flow (
    id                          BIGSERIAL       PRIMARY KEY,
    stock_id                    BIGINT          NOT NULL REFERENCES kiwoom.stock(id) ON DELETE CASCADE,
    trading_date                DATE            NOT NULL,
    exchange                    VARCHAR(4)      NOT NULL,
    indc_mode                   CHAR(1)         NOT NULL,

    -- C. 신용
    credit_rate                 NUMERIC(8, 4),
    credit_balance_rate         NUMERIC(8, 4),

    -- D. 투자자별 net (단위 indc_mode 따름)
    individual_net              BIGINT,
    institutional_net           BIGINT,
    foreign_brokerage_net       BIGINT,
    program_net                 BIGINT,

    -- E. 외인 + 순매수 (foreign_*_purchase 는 R15 가정 — 항상 수량)
    foreign_volume              BIGINT,
    foreign_rate                NUMERIC(8, 4),
    foreign_holdings            BIGINT,
    foreign_weight              NUMERIC(8, 4),
    foreign_net_purchase        BIGINT,
    institutional_net_purchase  BIGINT,
    individual_net_purchase     BIGINT,

    fetched_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_daily_flow_stock_date_exchange
        UNIQUE (stock_id, trading_date, exchange)
);

COMMENT ON TABLE kiwoom.stock_daily_flow IS 'ka10086 일별 수급 — 신용/투자자별/외인 (C-2α)';
COMMENT ON COLUMN kiwoom.stock_daily_flow.exchange IS '거래소 — KRX/NXT';
COMMENT ON COLUMN kiwoom.stock_daily_flow.indc_mode IS 'indc_tp 표시구분 — 0=수량 / 1=백만원';
COMMENT ON COLUMN kiwoom.stock_daily_flow.foreign_net_purchase IS '외인 순매수 — R15: 항상 수량 (indc_mode 무시)';
COMMENT ON COLUMN kiwoom.stock_daily_flow.institutional_net_purchase IS '기관 순매수 — R15 가정: 항상 수량';
COMMENT ON COLUMN kiwoom.stock_daily_flow.individual_net_purchase IS '개인 순매수 — R15 가정: 항상 수량';

CREATE INDEX idx_daily_flow_trading_date ON kiwoom.stock_daily_flow(trading_date);
CREATE INDEX idx_daily_flow_stock_id     ON kiwoom.stock_daily_flow(stock_id);
CREATE INDEX idx_daily_flow_exchange     ON kiwoom.stock_daily_flow(exchange);
"""


DOWNGRADE_SQL = r"""
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM kiwoom.stock_daily_flow;
    IF v_count > 0 THEN
        RAISE EXCEPTION 'stock_daily_flow 데이터(%건) 가 있어 downgrade 차단. 수동 삭제 후 재시도.', v_count;
    END IF;
END $$;

DROP TABLE IF EXISTS kiwoom.stock_daily_flow CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
