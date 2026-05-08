"""kiwoom.stock_fundamental 테이블 — ka10001 펀더멘털 (B-γ-1)

Revision ID: 004_kiwoom_stock_fundamental
Revises: 003_kiwoom_stock
Create Date: 2026-05-08

설계: endpoint-05-ka10001.md § 5.1.

UNIQUE: (stock_id, asof_date, exchange) — 같은 종목/일자/거래소 1행.
FK: stock_id → kiwoom.stock(id) ON DELETE CASCADE.

5 카테고리 컬럼:
- A. 기본 (settlement_month)
- B. 자본/시총/외인 (face_value, market_cap, foreign_holding_rate ...)
- C. 재무 비율 (per_ratio, eps_won, roe_pct, pbr_ratio, ev_ratio, bps_won + 손익)
- D. 250일/연중 통계 (high_250d, low_250d, year_high, year_low)
- E. 일중 시세 (current_price, trade_volume, base_price ...)

변경 감지: fundamental_hash (CHAR(32)) — PER/EPS/ROE/PBR/EV/BPS 6 필드 MD5.

KRX-only 결정 (계획서 § 4.3 권장 (a)) — exchange 디폴트 'KRX'. NXT/SOR 추가는
Phase C 후 결정 — 컬럼은 미리 마련 (스키마 변경 회피).

인덱스 2개:
- idx_fundamental_asof_date: 백테스팅 시점 조회
- idx_fundamental_stock_id: 종목 단위 조회 (find_latest)
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "004_kiwoom_stock_fundamental"
down_revision: str | Sequence[str] | None = "003_kiwoom_stock"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
CREATE TABLE kiwoom.stock_fundamental (
    id                       BIGSERIAL       PRIMARY KEY,
    stock_id                 BIGINT          NOT NULL REFERENCES kiwoom.stock(id) ON DELETE CASCADE,
    asof_date                DATE            NOT NULL,
    exchange                 VARCHAR(4)      NOT NULL DEFAULT 'KRX',

    -- A. 기본
    settlement_month         CHAR(2),

    -- B. 자본 / 시총 / 외인
    face_value               BIGINT,
    face_value_unit          VARCHAR(10),
    capital_won              BIGINT,
    listed_shares            BIGINT,
    market_cap               BIGINT,
    market_cap_weight        NUMERIC(8, 4),
    foreign_holding_rate     NUMERIC(8, 4),
    replacement_price        BIGINT,
    credit_rate              NUMERIC(8, 4),
    circulating_shares       BIGINT,
    circulating_rate         NUMERIC(8, 4),

    -- C. 재무 비율 (외부 벤더 — 빈값 허용)
    per_ratio                NUMERIC(10, 2),
    eps_won                  BIGINT,
    roe_pct                  NUMERIC(8, 2),
    pbr_ratio                NUMERIC(10, 2),
    ev_ratio                 NUMERIC(10, 2),
    bps_won                  BIGINT,
    revenue_amount           BIGINT,
    operating_profit         BIGINT,
    net_profit               BIGINT,

    -- D. 250일 / 연중 통계
    high_250d                BIGINT,
    high_250d_date           DATE,
    high_250d_pre_rate       NUMERIC(8, 4),
    low_250d                 BIGINT,
    low_250d_date            DATE,
    low_250d_pre_rate        NUMERIC(8, 4),
    year_high                BIGINT,
    year_low                 BIGINT,

    -- E. 일중 시세 (응답 시점 KST)
    current_price            BIGINT,
    prev_compare_sign        CHAR(1),
    prev_compare_amount      BIGINT,
    change_rate              NUMERIC(8, 4),
    trade_volume             BIGINT,
    trade_compare_rate       NUMERIC(8, 4),
    open_price               BIGINT,
    high_price               BIGINT,
    low_price                BIGINT,
    upper_limit_price        BIGINT,
    lower_limit_price        BIGINT,
    base_price               BIGINT,
    expected_match_price     BIGINT,
    expected_match_volume    BIGINT,

    -- 변경 감지 hash — PER/EPS/ROE/PBR/EV/BPS 6 필드 MD5 (외부 벤더 갱신 검출)
    fundamental_hash         CHAR(32),

    fetched_at               TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at               TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_fundamental_stock_date_exchange
        UNIQUE (stock_id, asof_date, exchange)
);

COMMENT ON TABLE kiwoom.stock_fundamental IS 'ka10001 종목 펀더멘털 일별 스냅샷 — 45 필드 (B-γ-1, KRX-only)';
COMMENT ON COLUMN kiwoom.stock_fundamental.exchange IS 'KRX/NXT/SOR — Phase B-γ-1 은 KRX-only (계획서 § 4.3 (a))';
COMMENT ON COLUMN kiwoom.stock_fundamental.asof_date IS '응답 시점 KST 오늘 (응답에 timestamp 부재 — § 11.2)';
COMMENT ON COLUMN kiwoom.stock_fundamental.market_cap IS '시가총액 — 단위 운영 검증 후 명시 (§ 11.2)';
COMMENT ON COLUMN kiwoom.stock_fundamental.per_ratio IS '외부 벤더 PER — 주 1회 또는 실적발표 시즌만 갱신 (Excel R41/R43)';
COMMENT ON COLUMN kiwoom.stock_fundamental.fundamental_hash IS 'PER/EPS/ROE/PBR/EV/BPS 6 필드 MD5 — 변경 감지용 (Phase F 활용)';

CREATE INDEX idx_fundamental_asof_date ON kiwoom.stock_fundamental(asof_date);
CREATE INDEX idx_fundamental_stock_id  ON kiwoom.stock_fundamental(stock_id);
"""


DOWNGRADE_SQL = r"""
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM kiwoom.stock_fundamental;
    IF v_count > 0 THEN
        RAISE EXCEPTION 'stock_fundamental 데이터(%건) 가 있어 downgrade 차단. 수동 삭제 후 재시도.', v_count;
    END IF;
END $$;

DROP TABLE IF EXISTS kiwoom.stock_fundamental CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
