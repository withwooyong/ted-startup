"""kiwoom.sector_price_daily 테이블 — ka20006 업종 일봉 OHLCV (D-1).

Revision ID: 015_sector_price_daily
Revises: 014_stock_price_yearly
Create Date: 2026-05-12

설계: endpoint-13-ka20006.md § 5 + § 12.

014 (yearly KRX/NXT) 패턴 1:1 응용 — 단, 본 chunk 는 단일 테이블 (NXT 미지원, plan
§ 12.2 #4 — 업종 지수는 KRX/NXT 분리 없음).

특징 (plan § 12.2):
- #1 revision id = `015_sector_price_daily` (22 chars — VARCHAR(32) 안전)
- #2 sector_id FK = BIGINT REFERENCES kiwoom.sector(id) ON DELETE CASCADE.
  UNIQUE (sector_id, trading_date) — sector.py L31 `uq_sector_market_code (market_code,
  sector_code)` 페어이므로 sector_code 단독 lookup 불가 → sector_id PK 사용.
  **1R HIGH #4 fix**: kiwoom.sector.id 는 BIGSERIAL (BIGINT) — INTEGER 가 아닌 BIGINT 사용해 타입 일치.
- #3 100배 값 = 4 centi BIGINT (open/high/low/close_index_centi). read property
  `.close_index = close_index_centi / 100` 는 ORM 모델 측에서 제공
- #12 비파괴 — CREATE TABLE 만 (DROP/ALTER 없음). downgrade 가드 (row 1건 이상 RAISE).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "015_sector_price_daily"
down_revision: str | Sequence[str] | None = "014_stock_price_yearly"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
CREATE TABLE kiwoom.sector_price_daily (
    id                   BIGSERIAL       PRIMARY KEY,
    sector_id            BIGINT          NOT NULL REFERENCES kiwoom.sector(id) ON DELETE CASCADE,
    trading_date         DATE            NOT NULL,

    open_index_centi     BIGINT,
    high_index_centi     BIGINT,
    low_index_centi      BIGINT,
    close_index_centi    BIGINT,
    trade_volume         BIGINT,
    trade_amount         BIGINT,

    fetched_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_sector_price_daily UNIQUE (sector_id, trading_date)
);

COMMENT ON TABLE kiwoom.sector_price_daily IS 'ka20006 업종 일봉 OHLCV — 백테스팅 섹터 회전/시장 비교 (D-1, KRX only)';
COMMENT ON COLUMN kiwoom.sector_price_daily.sector_id IS 'kiwoom.sector(id) FK — UseCase 입력 (plan § 12.2 #2/#9)';
COMMENT ON COLUMN kiwoom.sector_price_daily.open_index_centi IS '시가 지수 × 100 (centi BIGINT, plan § 12.2 #3)';
COMMENT ON COLUMN kiwoom.sector_price_daily.high_index_centi IS '고가 지수 × 100 (centi BIGINT)';
COMMENT ON COLUMN kiwoom.sector_price_daily.low_index_centi IS '저가 지수 × 100 (centi BIGINT)';
COMMENT ON COLUMN kiwoom.sector_price_daily.close_index_centi IS '종가 지수 × 100 (centi BIGINT). 예: KOSPI 2521.27 → 252127';
COMMENT ON COLUMN kiwoom.sector_price_daily.trade_volume IS '거래량 (BIGINT)';
COMMENT ON COLUMN kiwoom.sector_price_daily.trade_amount IS '거래대금 — 백만원 추정 (운영 검증 필요)';

CREATE INDEX idx_sector_price_daily_trading_date ON kiwoom.sector_price_daily(trading_date);
CREATE INDEX idx_sector_price_daily_sector_id    ON kiwoom.sector_price_daily(sector_id);
"""


DOWNGRADE_SQL = r"""
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM kiwoom.sector_price_daily;
    IF v_count > 0 THEN
        RAISE EXCEPTION 'sector_price_daily 데이터(%건) 가 있어 downgrade 차단. 수동 삭제 후 재시도.', v_count;
    END IF;
END $$;

DROP TABLE IF EXISTS kiwoom.sector_price_daily CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
