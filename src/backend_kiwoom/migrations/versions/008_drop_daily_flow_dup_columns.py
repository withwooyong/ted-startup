"""kiwoom.stock_daily_flow — D-E 중복 컬럼 3개 DROP (C-2γ).

Revision ID: 008_drop_daily_flow_dup_columns
Revises: 007_kiwoom_stock_daily_flow
Create Date: 2026-05-09

설계: endpoint-10-ka10086.md § 12.

배경 (운영 dry-run § 20.2 #1):
- D 카테고리 ↔ E 카테고리 3 컬럼 쌍이 1,200/1,200 row 100% 동일값
  - `individual_net` ≡ `individual_net_purchase`
  - `institutional_net` ≡ `institutional_net_purchase`
  - `foreign_volume` ≡ `foreign_net_purchase`
- D 카테고리 (개인/기관/외국계 + 외인 거래량) 만 의미 있음
- E 카테고리 3 컬럼 (개인/기관/외인 순매수) 은 D 의 중복 → DROP

13 → 10 컬럼.

DOWNGRADE 가드: 007 동일 패턴 — 데이터 1건이라도 있으면 RAISE EXCEPTION.
NULL 컬럼 복원이라 데이터 의미 보존 불가능 → 빈 테이블에서만 허용.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "008_drop_daily_flow_dup_columns"
down_revision: str | Sequence[str] | None = "007_kiwoom_stock_daily_flow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
ALTER TABLE kiwoom.stock_daily_flow
    DROP COLUMN IF EXISTS individual_net_purchase,
    DROP COLUMN IF EXISTS institutional_net_purchase,
    DROP COLUMN IF EXISTS foreign_net_purchase;
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
    ADD COLUMN foreign_net_purchase BIGINT,
    ADD COLUMN institutional_net_purchase BIGINT,
    ADD COLUMN individual_net_purchase BIGINT;

COMMENT ON COLUMN kiwoom.stock_daily_flow.foreign_net_purchase IS '외인 순매수 — R15: 항상 수량 (indc_mode 무시) — C-2γ DROP 대상 (D 카테고리 foreign_volume 와 동일값)';
COMMENT ON COLUMN kiwoom.stock_daily_flow.institutional_net_purchase IS '기관 순매수 — C-2γ DROP 대상 (D 카테고리 institutional_net 와 동일값)';
COMMENT ON COLUMN kiwoom.stock_daily_flow.individual_net_purchase IS '개인 순매수 — C-2γ DROP 대상 (D 카테고리 individual_net 와 동일값)';
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
