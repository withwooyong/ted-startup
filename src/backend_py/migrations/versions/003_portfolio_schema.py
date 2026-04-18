"""P10 포트폴리오 도메인 — 4 테이블

계좌(brokerage_account) · 보유 스냅샷(portfolio_holding) · 거래 이력(portfolio_transaction)
· 일별 평가(portfolio_snapshot). MVP는 수동 등록(manual) + KIS 모의(kis_rest_mock) 만.

Revision ID: 003_portfolio_schema
Revises: 002_notification_preference
Create Date: 2026-04-18
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "003_portfolio_schema"
down_revision: str | Sequence[str] | None = "002_notification_preference"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
-- 계좌 마스터
CREATE TABLE brokerage_account (
    id                  BIGSERIAL       PRIMARY KEY,
    account_alias       VARCHAR(50)     NOT NULL UNIQUE,
    broker_code         VARCHAR(20)     NOT NULL CHECK (broker_code IN ('manual', 'kis', 'kiwoom')),
    connection_type     VARCHAR(20)     NOT NULL CHECK (connection_type IN ('manual', 'kis_rest_mock')),
    environment         VARCHAR(10)     NOT NULL DEFAULT 'mock' CHECK (environment IN ('mock', 'real')),
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE brokerage_account IS '증권사 계좌 메타 (수동/KIS 모의 연결)';
COMMENT ON COLUMN brokerage_account.environment IS 'MVP 는 mock 고정. real 진입은 코드 레벨에서 차단';

-- 보유 종목 스냅샷(현재 잔고) — 거래 이력 파생의 캐시
CREATE TABLE portfolio_holding (
    id                  BIGSERIAL       PRIMARY KEY,
    account_id          BIGINT          NOT NULL REFERENCES brokerage_account(id) ON DELETE CASCADE,
    stock_id            BIGINT          NOT NULL REFERENCES stock(id),
    quantity            INTEGER         NOT NULL CHECK (quantity >= 0),
    avg_buy_price       NUMERIC(15, 2)  NOT NULL CHECK (avg_buy_price >= 0),
    first_bought_at     DATE            NOT NULL,
    last_transacted_at  DATE,
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (account_id, stock_id)
);
COMMENT ON TABLE portfolio_holding IS '계좌별 보유 종목 현재 상태 (가중평균 평단가)';

CREATE INDEX idx_portfolio_holding_account ON portfolio_holding(account_id)
    WHERE quantity > 0;

-- 거래 이력 — 매수/매도 개별 레코드
CREATE TABLE portfolio_transaction (
    id                  BIGSERIAL       PRIMARY KEY,
    account_id          BIGINT          NOT NULL REFERENCES brokerage_account(id) ON DELETE CASCADE,
    stock_id            BIGINT          NOT NULL REFERENCES stock(id),
    transaction_type    VARCHAR(10)     NOT NULL CHECK (transaction_type IN ('BUY', 'SELL')),
    quantity            INTEGER         NOT NULL CHECK (quantity > 0),
    price               NUMERIC(15, 2)  NOT NULL CHECK (price >= 0),
    executed_at         DATE            NOT NULL,
    source              VARCHAR(20)     NOT NULL CHECK (source IN ('manual', 'kis_sync')),
    memo                TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE portfolio_transaction IS '매수/매도 거래 이력 — 수동 입력 또는 API 동기화';

CREATE INDEX idx_portfolio_transaction_account_date
    ON portfolio_transaction(account_id, executed_at DESC);
CREATE INDEX idx_portfolio_transaction_stock
    ON portfolio_transaction(stock_id, executed_at DESC);

-- 일별 평가 스냅샷 — 성과 그래프·MDD 계산
CREATE TABLE portfolio_snapshot (
    id                  BIGSERIAL       PRIMARY KEY,
    account_id          BIGINT          NOT NULL REFERENCES brokerage_account(id) ON DELETE CASCADE,
    snapshot_date       DATE            NOT NULL,
    total_value         NUMERIC(15, 2)  NOT NULL CHECK (total_value >= 0),
    total_cost          NUMERIC(15, 2)  NOT NULL CHECK (total_cost >= 0),
    unrealized_pnl      NUMERIC(15, 2)  NOT NULL,
    realized_pnl        NUMERIC(15, 2)  NOT NULL DEFAULT 0,
    holdings_count      INTEGER         NOT NULL CHECK (holdings_count >= 0),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (account_id, snapshot_date)
);
COMMENT ON TABLE portfolio_snapshot IS '계좌 일별 평가금액/손익 — 수익률·MDD·샤프 산출 원천';

CREATE INDEX idx_portfolio_snapshot_date
    ON portfolio_snapshot(account_id, snapshot_date DESC);
"""


DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS portfolio_snapshot CASCADE;
DROP TABLE IF EXISTS portfolio_transaction CASCADE;
DROP TABLE IF EXISTS portfolio_holding CASCADE;
DROP TABLE IF EXISTS brokerage_account CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
