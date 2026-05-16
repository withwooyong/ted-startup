"""kiwoom.investor_flow_daily / stock_investor_breakdown / frgn_orgn_consecutive 3 테이블 — Phase G (ka10058/10059/10131).

Revision ID: 019_investor_flow
Revises: 018_ranking_snapshot
Create Date: 2026-05-16

설계: phase-g-investor-flow.md § 5.1 + endpoint-23/24/25.

사용자 확정 (D-1~D-17):
- D-2 단일 Migration 019 + 3 테이블
- D-8 / D-17 stock lookup miss → stock_id=NULL (ON DELETE SET NULL)
- D-15 amt_qty_tp 반대 의미 — ka10059 ('1'/'2') vs ka10131 ('0'/'1') — 컬럼 그대로 raw 저장

특징 (018 ranking_snapshot 패턴 1:1 미러):
- revision id = ``019_investor_flow`` (≤32자 VARCHAR 안전)
- 1 마이그레이션 + 3 테이블 + UNIQUE × 3 + INDEX × 8 + COMMENT ON
- ON DELETE SET NULL — stock 마스터 삭제 시에도 row 보존 + raw 보관
- partial index ``WHERE stock_id IS NOT NULL`` — lookup miss row 진입 차단 (인덱스 크기 절감)
- downgrade 가드 — 3 테이블 모두 빈 상태에서만 DROP (016 row count 가드 패턴 일관)
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "019_investor_flow"
down_revision: str | Sequence[str] | None = "018_ranking_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
-- ============================================================================
-- investor_flow_daily — ka10058 (투자자별 일별 매매 종목 ranking)
-- ============================================================================
CREATE TABLE kiwoom.investor_flow_daily (
    id                          BIGSERIAL       PRIMARY KEY,
    as_of_date                  DATE            NOT NULL,
    market_type                 VARCHAR(3)      NOT NULL,
    exchange_type               VARCHAR(1)      NOT NULL,
    investor_type               VARCHAR(4)      NOT NULL,
    trade_type                  VARCHAR(1)      NOT NULL,
    rank                        INTEGER         NOT NULL,

    stock_id                    BIGINT          REFERENCES kiwoom.stock(id) ON DELETE SET NULL,
    stock_code_raw              VARCHAR(20)     NOT NULL,
    stock_name                  VARCHAR(100),

    net_volume                  BIGINT,
    net_amount                  BIGINT,
    estimated_avg_price         BIGINT,
    current_price               BIGINT,
    prev_compare_sign           CHAR(1),
    prev_compare_amount         BIGINT,
    avg_price_compare           BIGINT,
    prev_compare_rate           NUMERIC(8, 4),
    period_volume               BIGINT,

    fetched_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_investor_flow_daily UNIQUE (
        as_of_date, market_type, exchange_type,
        investor_type, trade_type, rank
    )
);

COMMENT ON TABLE kiwoom.investor_flow_daily IS
    'ka10058 투자자별 일별 매매 종목 ranking — (investor_type, trade_type, market_type) 단위 종목 list.';
COMMENT ON COLUMN kiwoom.investor_flow_daily.investor_type IS
    '8000=개인 / 9000=외국인 / 9999=기관계 / 1000=금융투자 / 2000=보험 / 3000=투신 / 3100=사모펀드 / '
    '4000=은행 / 5000=기타금융 / 6000=연기금 / 7000=국가 / 7100=기타법인 (12 카테고리).';
COMMENT ON COLUMN kiwoom.investor_flow_daily.trade_type IS '1=순매도 / 2=순매수.';
COMMENT ON COLUMN kiwoom.investor_flow_daily.net_volume IS
    'netslmt_qty raw — 부호 의미 trde_tp 따라 변경 (운영 검증 1순위, master.md § 12).';

CREATE INDEX idx_ifd_date_investor
    ON kiwoom.investor_flow_daily(as_of_date, investor_type, trade_type, market_type);

CREATE INDEX idx_ifd_stock
    ON kiwoom.investor_flow_daily(stock_id)
    WHERE stock_id IS NOT NULL;


-- ============================================================================
-- stock_investor_breakdown — ka10059 (종목별 투자자 wide breakdown, 12 net)
-- ============================================================================
CREATE TABLE kiwoom.stock_investor_breakdown (
    id                          BIGSERIAL       PRIMARY KEY,
    stock_id                    BIGINT          REFERENCES kiwoom.stock(id) ON DELETE SET NULL,
    trading_date                DATE            NOT NULL,
    amt_qty_tp                  VARCHAR(1)      NOT NULL,
    trade_type                  VARCHAR(1)      NOT NULL,
    unit_tp                     VARCHAR(4)      NOT NULL,
    exchange_type               VARCHAR(1)      NOT NULL,

    current_price               BIGINT,
    prev_compare_sign           CHAR(1),
    prev_compare_amount         BIGINT,
    change_rate                 NUMERIC(8, 4),
    acc_trade_volume            BIGINT,
    acc_trade_amount            BIGINT,

    -- 12 투자자 카테고리 net (부호 포함)
    net_individual              BIGINT,
    net_foreign                 BIGINT,
    net_institution_total       BIGINT,
    net_financial_inv           BIGINT,
    net_insurance               BIGINT,
    net_investment_trust        BIGINT,
    net_other_financial         BIGINT,
    net_bank                    BIGINT,
    net_pension_fund            BIGINT,
    net_private_fund            BIGINT,
    net_nation                  BIGINT,
    net_other_corp              BIGINT,
    net_dom_for                 BIGINT,

    fetched_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_stock_investor_breakdown UNIQUE (
        stock_id, trading_date, amt_qty_tp, trade_type, unit_tp, exchange_type
    )
);

COMMENT ON TABLE kiwoom.stock_investor_breakdown IS
    'ka10059 종목별 투자자/기관별 wide breakdown — (종목, 일자) 단위 12 투자자 net 카테고리.';
COMMENT ON COLUMN kiwoom.stock_investor_breakdown.amt_qty_tp IS
    'ka10059 amt_qty_tp: 1=금액 / 2=수량 (★ ka10131 의 amt_qty_tp 와 반대 의미 — master.md § 12).';
COMMENT ON COLUMN kiwoom.stock_investor_breakdown.trade_type IS '0=순매수 / 1=매수 / 2=매도.';
COMMENT ON COLUMN kiwoom.stock_investor_breakdown.change_rate IS
    'flu_rt 정규화 — raw "+698" → 6.98 (우측 2자리 소수점, _to_decimal_div_100 헬퍼).';

CREATE INDEX idx_sib_stock_date
    ON kiwoom.stock_investor_breakdown(stock_id, trading_date)
    WHERE stock_id IS NOT NULL;

CREATE INDEX idx_sib_date
    ON kiwoom.stock_investor_breakdown(trading_date);


-- ============================================================================
-- frgn_orgn_consecutive — ka10131 (기관/외국인 연속매매 ranking, 15 metric)
-- ============================================================================
CREATE TABLE kiwoom.frgn_orgn_consecutive (
    id                              BIGSERIAL       PRIMARY KEY,
    as_of_date                      DATE            NOT NULL,
    period_type                     VARCHAR(3)      NOT NULL,
    market_type                     VARCHAR(3)      NOT NULL,
    amt_qty_tp                      VARCHAR(1)      NOT NULL,
    stk_inds_tp                     VARCHAR(1)      NOT NULL,
    exchange_type                   VARCHAR(1)      NOT NULL,
    rank                            INTEGER         NOT NULL,

    stock_id                        BIGINT          REFERENCES kiwoom.stock(id) ON DELETE SET NULL,
    stock_code_raw                  VARCHAR(20)     NOT NULL,
    stock_name                      VARCHAR(100),

    period_stock_price_flu_rt       NUMERIC(8, 4),

    -- 기관 5 metric
    orgn_net_amount                 BIGINT,
    orgn_net_volume                 BIGINT,
    orgn_cont_days                  INTEGER,
    orgn_cont_volume                BIGINT,
    orgn_cont_amount                BIGINT,

    -- 외국인 5 metric
    frgnr_net_volume                BIGINT,
    frgnr_net_amount                BIGINT,
    frgnr_cont_days                 INTEGER,
    frgnr_cont_volume               BIGINT,
    frgnr_cont_amount               BIGINT,

    -- 합계 5 metric (기관 + 외국인)
    total_net_volume                BIGINT,
    total_net_amount                BIGINT,
    total_cont_days                 INTEGER,
    total_cont_volume               BIGINT,
    total_cont_amount               BIGINT,

    fetched_at                      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at                      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_frgn_orgn_consecutive UNIQUE (
        as_of_date, period_type, market_type, amt_qty_tp,
        stk_inds_tp, exchange_type, rank
    )
);

COMMENT ON TABLE kiwoom.frgn_orgn_consecutive IS
    'ka10131 기관/외국인 연속매매 ranking — N일 연속순매수 강조 시그널.';
COMMENT ON COLUMN kiwoom.frgn_orgn_consecutive.period_type IS
    'dt: 1=최근일 / 3/5/10/20/120=N일 / 0=strt~end 기간.';
COMMENT ON COLUMN kiwoom.frgn_orgn_consecutive.amt_qty_tp IS
    'ka10131 amt_qty_tp: 0=금액 / 1=수량 (★ ka10059 의 amt_qty_tp 와 반대 의미 — master.md § 12).';
COMMENT ON COLUMN kiwoom.frgn_orgn_consecutive.total_cont_days IS
    'tot_cont_netprps_dys raw — orgn + frgnr 합산 정합성 운영 검증 (master.md § 12).';

CREATE INDEX idx_foc_date_market
    ON kiwoom.frgn_orgn_consecutive(as_of_date, market_type, period_type);

CREATE INDEX idx_foc_stock
    ON kiwoom.frgn_orgn_consecutive(stock_id)
    WHERE stock_id IS NOT NULL;

CREATE INDEX idx_foc_total_cont_days
    ON kiwoom.frgn_orgn_consecutive(as_of_date, total_cont_days DESC NULLS LAST);
"""


DOWNGRADE_SQL = r"""
DO $$
DECLARE
    v_count_ifd INTEGER;
    v_count_sib INTEGER;
    v_count_foc INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count_ifd FROM kiwoom.investor_flow_daily;
    SELECT COUNT(*) INTO v_count_sib FROM kiwoom.stock_investor_breakdown;
    SELECT COUNT(*) INTO v_count_foc FROM kiwoom.frgn_orgn_consecutive;
    IF v_count_ifd > 0 OR v_count_sib > 0 OR v_count_foc > 0 THEN
        RAISE EXCEPTION
            'Phase G 데이터(investor_flow_daily=% / stock_investor_breakdown=% / frgn_orgn_consecutive=%) 가 있어 downgrade 차단. 수동 삭제 후 재시도.',
            v_count_ifd, v_count_sib, v_count_foc;
    END IF;
END $$;

DROP TABLE IF EXISTS kiwoom.frgn_orgn_consecutive CASCADE;
DROP TABLE IF EXISTS kiwoom.stock_investor_breakdown CASCADE;
DROP TABLE IF EXISTS kiwoom.investor_flow_daily CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
