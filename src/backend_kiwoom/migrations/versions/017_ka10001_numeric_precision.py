"""kiwoom.stock_fundamental NUMERIC 확대 — Phase F-1 ka10001 overflow 대응.

Revision ID: 017_ka10001_numeric_precision
Revises: 016_short_lending
Create Date: 2026-05-14

설계: phase-f-1-ka10001-numeric-sentinel.md § 4 결정 #1/#2/#7 + § 5.2.

5-13 18:00 cron 결과 (success=4063 / failed=316 / fail-ratio 7.2%) 중
ASYNCPG NumericValueOutOfRangeError 11건 — Numeric(8,4) precision 한계 (9999.9999) 초과.

upgrade:
- ``trade_compare_rate`` Numeric(8,4) → Numeric(12,4) — max 99,999,999.9999.
  5-13 실측 max=8950 의 약 10,000배 여유 (테마주 거래량 비율 급등 대응).
- ``low_250d_pre_rate`` Numeric(8,4) → Numeric(10,4) — max 999,999.9999.
  5-13 실측 max=5745.71 의 약 175배 여유 (250일 저가 대비 100만% 까지 대응).

downgrade 가드 (§ 5.2 — 데이터 손실 차단):
- 9999 초과 row 존재 시 RAISE EXCEPTION → alembic downgrade fail.
- 9999 이하 또는 빈 테이블이면 원래 Numeric(8,4) 로 복원.

특징 (016 short_lending 패턴 1:1 응용):
- #1 revision id = ``017_ka10001_numeric_precision`` (≤32자 VARCHAR 안전)
- #2 ALTER COLUMN TYPE — Postgres metadata-only operation (rewrite 불필요)
- #3 downgrade DO $$ ... $$ 가드 패턴 (016 의 row count 가드 응용)
- #4 over-engineering 회피 — 다른 NUMERIC 컬럼 (change_rate / market_cap_weight 등)
  은 안전권 (실측 magnitude < 0.3% 사용) → 손대지 않음 (§ 4 결정 #8)
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "017_ka10001_numeric_precision"
down_revision: str | Sequence[str] | None = "016_short_lending"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
-- ============================================================================
-- stock_fundamental NUMERIC 확대 — Phase F-1 ka10001 overflow 대응
-- ============================================================================

ALTER TABLE kiwoom.stock_fundamental
    ALTER COLUMN trade_compare_rate TYPE NUMERIC(12, 4);

ALTER TABLE kiwoom.stock_fundamental
    ALTER COLUMN low_250d_pre_rate TYPE NUMERIC(10, 4);

COMMENT ON COLUMN kiwoom.stock_fundamental.trade_compare_rate
    IS 'trde_pre — 거래량 비율 (%). Phase F-1: Numeric(12,4). max 99,999,999.9999';
COMMENT ON COLUMN kiwoom.stock_fundamental.low_250d_pre_rate
    IS '250lwst_pric_pre_rt — 250일 저가 대비 비율 (%). Phase F-1: Numeric(10,4). max 999,999.9999';
"""


DOWNGRADE_SQL = r"""
-- 9999 초과 row 존재 시 RAISE EXCEPTION — 데이터 손실 차단 가드 (§ 5.2).
DO $$
DECLARE
    v_trade_overflow_count INTEGER;
    v_low_overflow_count   INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_trade_overflow_count
    FROM kiwoom.stock_fundamental
    WHERE trade_compare_rate IS NOT NULL
      AND (trade_compare_rate > 9999.9999 OR trade_compare_rate < -9999.9999);

    SELECT COUNT(*) INTO v_low_overflow_count
    FROM kiwoom.stock_fundamental
    WHERE low_250d_pre_rate IS NOT NULL
      AND (low_250d_pre_rate > 9999.9999 OR low_250d_pre_rate < -9999.9999);

    IF v_trade_overflow_count > 0 THEN
        RAISE EXCEPTION 'trade_compare_rate overflow row(%건) > 9999.9999 — downgrade 차단. 9999 이하로 클램프 후 재시도.', v_trade_overflow_count;
    END IF;
    IF v_low_overflow_count > 0 THEN
        RAISE EXCEPTION 'low_250d_pre_rate overflow row(%건) > 9999.9999 — downgrade 차단.', v_low_overflow_count;
    END IF;
END $$;

ALTER TABLE kiwoom.stock_fundamental
    ALTER COLUMN trade_compare_rate TYPE NUMERIC(8, 4);

ALTER TABLE kiwoom.stock_fundamental
    ALTER COLUMN low_250d_pre_rate TYPE NUMERIC(8, 4);
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
