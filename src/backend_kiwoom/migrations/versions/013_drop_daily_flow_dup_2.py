"""kiwoom.stock_daily_flow — C/E 중복 컬럼 2개 DROP (C-2δ).

Revision ID: 013_drop_daily_flow_dup_2
Revises: 012_stock_price_monthly_nxt
Create Date: 2026-05-11

운영 메모: VARCHAR(32) alembic_version.version_num 한도 — 008
(`008_drop_daily_flow_dup_columns` 31 chars) 패턴 + `_2` 접미사가
33 chars 로 truncation 발생. `columns` 제거 25 chars 로 축약.

설계: endpoint-10-ka10086.md § 13.

배경 (운영 실측 § 5.6 IS DISTINCT FROM SQL — 2,879,500 rows):
- C 페어: `credit_rate` ≡ `credit_balance_rate` (`credit_diff=0`)
- E 페어: `foreign_rate` ≡ `foreign_weight` (`foreign_diff=0`)
- vendor 가 두 raw 필드 (`crd_rt` ≡ `crd_remn_rt` / `for_rt` ≡ `for_wght`) 를
  동일값으로 채움 → 어댑터가 두 컬럼에 각각 적재 → DB 도 동일값
- 잔존 (`credit_rate` / `foreign_rate`) 만 의미 있음 → 중복 2 컬럼 DROP

10 → 8 도메인 컬럼 (메타 5 포함 총 13).

DOWNGRADE 가드: 007/008 동일 패턴 — 데이터 1건이라도 있으면 RAISE EXCEPTION.
NULL 컬럼 복원이라 데이터 의미 보존 불가능 → 빈 테이블에서만 허용.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "013_drop_daily_flow_dup_2"
down_revision: str | Sequence[str] | None = "012_stock_price_monthly_nxt"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
ALTER TABLE kiwoom.stock_daily_flow
    DROP COLUMN IF EXISTS credit_balance_rate,
    DROP COLUMN IF EXISTS foreign_weight;
"""


DOWNGRADE_SQL = r"""
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM kiwoom.stock_daily_flow;
    IF v_count > 0 THEN
        RAISE EXCEPTION 'stock_daily_flow 데이터(%건) 가 있어 downgrade 차단. NULL 복원이라 의미 보존 불가능 — 수동 백업 후 재시도.', v_count;
    END IF;
END $$;

ALTER TABLE kiwoom.stock_daily_flow
    ADD COLUMN foreign_weight NUMERIC(8, 4),
    ADD COLUMN credit_balance_rate NUMERIC(8, 4);

COMMENT ON COLUMN kiwoom.stock_daily_flow.foreign_weight IS '외인 비중 % — C-2δ DROP 대상 (E 카테고리 foreign_rate 와 동일값)';
COMMENT ON COLUMN kiwoom.stock_daily_flow.credit_balance_rate IS '신용 잔고율 % — C-2δ DROP 대상 (C 카테고리 credit_rate 와 동일값)';
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
