"""kiwoom.short_selling_kw + lending_balance_kw 신규 — Phase E ka10014 / ka10068 / ka20068 매도 측 시그널 wave.

Revision ID: 016_short_lending
Revises: 015_sector_price_daily
Create Date: 2026-05-12

설계: endpoint-15-ka10014.md § 12 + endpoint-16-ka10068.md § 5.1.

015 (sector_price_daily) 단일 테이블 패턴 1:1 응용 — 본 chunk 는 2 테이블 1 마이그레이션 (매도 측 시그널 통합 wave).

특징 (plan § 12.2):
- #1 revision id = `016_short_lending` (15 chars — VARCHAR(32) 안전)
- #2 2 테이블 통합 — short_selling_kw + lending_balance_kw (모두 매도 측 시그널)
- #3 lending scope 분기 — partial unique index 2 (uq_lending_market_date / uq_lending_stock_date)
  + CHECK constraint chk_lending_scope
- #12 비파괴 — CREATE TABLE 만 (DROP/ALTER 없음). downgrade 가드 (row 1건 이상 RAISE).

short_selling_kw 컬럼:
- UNIQUE (stock_id, trading_date, exchange) — 거래소 분리 (KRX/NXT)
- idx_short_selling_kw_weight_high partial — WHERE short_trade_weight IS NOT NULL
  (시그널 상위 종목 조회용)

lending_balance_kw 컬럼:
- scope VARCHAR(8) — "MARKET" (ka10068) / "STOCK" (ka20068)
- stock_id BIGINT nullable — MARKET 시 NULL, STOCK 시 FK to kiwoom.stock(id)
- CHECK constraint: (scope='MARKET' AND stock_id IS NULL) OR (scope='STOCK' AND stock_id IS NOT NULL)
- uq_lending_market_date — (scope, trading_date) WHERE scope='MARKET' AND stock_id IS NULL
- uq_lending_stock_date — (scope, stock_id, trading_date) WHERE scope='STOCK' AND stock_id IS NOT NULL
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "016_short_lending"
down_revision: str | Sequence[str] | None = "015_sector_price_daily"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
-- ============================================================================
-- short_selling_kw — ka10014 공매도 추이 (KRX/NXT 분리)
-- ============================================================================
CREATE TABLE kiwoom.short_selling_kw (
    id                       BIGSERIAL       PRIMARY KEY,
    stock_id                 BIGINT          NOT NULL REFERENCES kiwoom.stock(id) ON DELETE CASCADE,
    trading_date             DATE            NOT NULL,
    exchange                 VARCHAR(3)      NOT NULL,

    close_price              BIGINT,
    prev_compare_amount      BIGINT,
    prev_compare_sign        CHAR(1),
    change_rate              NUMERIC(8, 4),
    trade_volume             BIGINT,
    short_volume             BIGINT,
    cumulative_short_volume  BIGINT,
    short_trade_weight       NUMERIC(8, 4),
    short_trade_amount       BIGINT,
    short_avg_price          BIGINT,

    fetched_at               TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at               TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_short_selling_kw UNIQUE (stock_id, trading_date, exchange)
);

COMMENT ON TABLE kiwoom.short_selling_kw IS 'ka10014 공매도 추이 — 매도 측 시그널 raw (KRX + NXT 분리)';
COMMENT ON COLUMN kiwoom.short_selling_kw.exchange IS '"KRX" / "NXT" — VARCHAR(3)';
COMMENT ON COLUMN kiwoom.short_selling_kw.short_volume IS 'shrts_qty — 공매도 거래량 (시그널 핵심)';
COMMENT ON COLUMN kiwoom.short_selling_kw.cumulative_short_volume IS 'ovr_shrts_qty — 응답 기간 누적 공매도 거래량';
COMMENT ON COLUMN kiwoom.short_selling_kw.short_trade_weight IS 'trde_wght — 공매도 매매비중 (%)';
COMMENT ON COLUMN kiwoom.short_selling_kw.short_trade_amount IS 'shrts_trde_prica — 공매도 거래대금 (백만원 추정)';
COMMENT ON COLUMN kiwoom.short_selling_kw.short_avg_price IS 'shrts_avg_pric — 공매도 평균단가';

CREATE INDEX idx_short_selling_kw_date  ON kiwoom.short_selling_kw(trading_date);
CREATE INDEX idx_short_selling_kw_stock ON kiwoom.short_selling_kw(stock_id);
CREATE INDEX idx_short_selling_kw_weight_high
    ON kiwoom.short_selling_kw(trading_date, short_trade_weight DESC NULLS LAST)
    WHERE short_trade_weight IS NOT NULL;


-- ============================================================================
-- lending_balance_kw — ka10068 (시장) + ka20068 (종목) 대차거래 추이
-- scope 분기: MARKET (stock_id NULL) / STOCK (stock_id FK)
-- ============================================================================
CREATE TABLE kiwoom.lending_balance_kw (
    id                  BIGSERIAL       PRIMARY KEY,
    scope               VARCHAR(8)      NOT NULL,
    stock_id            BIGINT          REFERENCES kiwoom.stock(id) ON DELETE CASCADE,
    trading_date        DATE            NOT NULL,

    contracted_volume   BIGINT,
    repaid_volume       BIGINT,
    delta_volume        BIGINT,
    balance_volume      BIGINT,
    balance_amount      BIGINT,

    fetched_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_lending_scope CHECK (
        (scope = 'MARKET' AND stock_id IS NULL)
        OR (scope = 'STOCK' AND stock_id IS NOT NULL)
    )
);

COMMENT ON TABLE kiwoom.lending_balance_kw IS 'ka10068 (시장) + ka20068 (종목) 대차거래 추이 — scope 분기 통합';
COMMENT ON COLUMN kiwoom.lending_balance_kw.scope IS '"MARKET" (ka10068) / "STOCK" (ka20068) — VARCHAR(8)';
COMMENT ON COLUMN kiwoom.lending_balance_kw.stock_id IS 'STOCK 시 FK, MARKET 시 NULL (CHECK constraint 보장)';
COMMENT ON COLUMN kiwoom.lending_balance_kw.contracted_volume IS 'dbrt_trde_cntrcnt — 대차거래 체결주수';
COMMENT ON COLUMN kiwoom.lending_balance_kw.repaid_volume IS 'dbrt_trde_rpy — 대차거래 상환주수';
COMMENT ON COLUMN kiwoom.lending_balance_kw.delta_volume IS 'dbrt_trde_irds — 대차거래 증감 (체결 - 상환, 부호 가능)';
COMMENT ON COLUMN kiwoom.lending_balance_kw.balance_volume IS 'rmnd — 대차잔고 주수';
COMMENT ON COLUMN kiwoom.lending_balance_kw.balance_amount IS 'remn_amt — 대차잔고 금액 (백만원 추정)';

CREATE UNIQUE INDEX uq_lending_market_date
    ON kiwoom.lending_balance_kw(scope, trading_date)
    WHERE scope = 'MARKET' AND stock_id IS NULL;

CREATE UNIQUE INDEX uq_lending_stock_date
    ON kiwoom.lending_balance_kw(scope, stock_id, trading_date)
    WHERE scope = 'STOCK' AND stock_id IS NOT NULL;

CREATE INDEX idx_lending_trading_date ON kiwoom.lending_balance_kw(trading_date);
CREATE INDEX idx_lending_stock
    ON kiwoom.lending_balance_kw(stock_id)
    WHERE stock_id IS NOT NULL;
"""


DOWNGRADE_SQL = r"""
DO $$
DECLARE
    v_short_count   INTEGER;
    v_lending_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_short_count   FROM kiwoom.short_selling_kw;
    SELECT COUNT(*) INTO v_lending_count FROM kiwoom.lending_balance_kw;
    IF v_short_count > 0 THEN
        RAISE EXCEPTION 'short_selling_kw 데이터(%건) 가 있어 downgrade 차단. 수동 삭제 후 재시도.', v_short_count;
    END IF;
    IF v_lending_count > 0 THEN
        RAISE EXCEPTION 'lending_balance_kw 데이터(%건) 가 있어 downgrade 차단. 수동 삭제 후 재시도.', v_lending_count;
    END IF;
END $$;

DROP TABLE IF EXISTS kiwoom.lending_balance_kw CASCADE;
DROP TABLE IF EXISTS kiwoom.short_selling_kw CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
