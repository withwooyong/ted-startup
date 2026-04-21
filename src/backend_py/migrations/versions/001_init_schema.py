"""V1 초기 스키마 (Java Flyway V1__init_schema.sql 동일 이식)

Revision ID: 001_init_schema
Revises:
Create Date: 2026-04-18
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "001_init_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
CREATE TABLE stock (
    id              BIGSERIAL       PRIMARY KEY,
    stock_code      VARCHAR(6)      NOT NULL UNIQUE,
    stock_name      VARCHAR(100)    NOT NULL,
    market_type     VARCHAR(10)     NOT NULL CHECK (market_type IN ('KOSPI', 'KOSDAQ')),
    sector          VARCHAR(100),
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);
COMMENT ON TABLE stock IS '종목 마스터 테이블';
COMMENT ON COLUMN stock.stock_code IS 'KRX 종목코드 (6자리)';
COMMENT ON COLUMN stock.market_type IS '시장 구분 (KOSPI/KOSDAQ)';

CREATE TABLE stock_price (
    id              BIGSERIAL,
    stock_id        BIGINT          NOT NULL,
    trading_date    DATE            NOT NULL,
    close_price     BIGINT          NOT NULL,
    open_price      BIGINT,
    high_price      BIGINT,
    low_price       BIGINT,
    volume          BIGINT          NOT NULL DEFAULT 0,
    market_cap      BIGINT,
    change_rate     NUMERIC(10, 4),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, trading_date),
    UNIQUE (stock_id, trading_date)
) PARTITION BY RANGE (trading_date);
COMMENT ON TABLE stock_price IS '일별 주가 시세 (월별 파티셔닝)';

CREATE TABLE short_selling (
    id              BIGSERIAL,
    stock_id        BIGINT          NOT NULL,
    trading_date    DATE            NOT NULL,
    short_volume    BIGINT          NOT NULL DEFAULT 0,
    short_amount   BIGINT           NOT NULL DEFAULT 0,
    short_ratio     NUMERIC(10, 4),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, trading_date),
    UNIQUE (stock_id, trading_date)
) PARTITION BY RANGE (trading_date);
COMMENT ON TABLE short_selling IS '일별 공매도 거래 현황 (월별 파티셔닝)';

CREATE TABLE lending_balance (
    id                          BIGSERIAL,
    stock_id                    BIGINT          NOT NULL,
    trading_date                DATE            NOT NULL,
    balance_quantity            BIGINT          NOT NULL DEFAULT 0,
    balance_amount              BIGINT          NOT NULL DEFAULT 0,
    change_rate                 NUMERIC(10, 4),
    change_quantity             BIGINT          DEFAULT 0,
    consecutive_decrease_days   INTEGER         DEFAULT 0,
    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, trading_date),
    UNIQUE (stock_id, trading_date)
) PARTITION BY RANGE (trading_date);
COMMENT ON TABLE lending_balance IS '일별 대차잔고 (월별 파티셔닝)';
COMMENT ON COLUMN lending_balance.consecutive_decrease_days IS '대차잔고 연속 감소 일수';

CREATE TABLE signal (
    id              BIGSERIAL       PRIMARY KEY,
    stock_id        BIGINT          NOT NULL,
    signal_date     DATE            NOT NULL,
    signal_type     VARCHAR(30)     NOT NULL CHECK (signal_type IN ('RAPID_DECLINE', 'TREND_REVERSAL', 'SHORT_SQUEEZE')),
    score           INTEGER         NOT NULL CHECK (score BETWEEN 0 AND 100),
    grade           VARCHAR(1)      NOT NULL CHECK (grade IN ('A', 'B', 'C', 'D')),
    detail          JSONB,
    return_5d       NUMERIC(10, 4),
    return_10d      NUMERIC(10, 4),
    return_20d      NUMERIC(10, 4),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (stock_id, signal_date, signal_type)
);
COMMENT ON TABLE signal IS '시그널 탐지 결과';
COMMENT ON COLUMN signal.detail IS '스코어 산출 근거 (JSON)';
COMMENT ON COLUMN signal.return_5d IS '시그널 발생 후 5거래일 수익률';

CREATE TABLE backtest_result (
    id              BIGSERIAL       PRIMARY KEY,
    signal_type     VARCHAR(30)     NOT NULL,
    period_start    DATE            NOT NULL,
    period_end      DATE            NOT NULL,
    total_signals   INTEGER         NOT NULL DEFAULT 0,
    hit_count_5d    INTEGER         DEFAULT 0,
    hit_rate_5d     NUMERIC(10, 4),
    avg_return_5d   NUMERIC(10, 4),
    hit_count_10d   INTEGER         DEFAULT 0,
    hit_rate_10d    NUMERIC(10, 4),
    avg_return_10d  NUMERIC(10, 4),
    hit_count_20d   INTEGER         DEFAULT 0,
    hit_rate_20d    NUMERIC(10, 4),
    avg_return_20d  NUMERIC(10, 4),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE backtest_result IS '백테스팅 결과 요약';

CREATE TABLE batch_job_log (
    id              BIGSERIAL       PRIMARY KEY,
    job_name        VARCHAR(50)     NOT NULL,
    status          VARCHAR(20)     NOT NULL CHECK (status IN ('SUCCESS', 'FAILED', 'RUNNING')),
    started_at      TIMESTAMPTZ     NOT NULL,
    finished_at     TIMESTAMPTZ,
    total_count     INTEGER         DEFAULT 0,
    success_count   INTEGER         DEFAULT 0,
    fail_count      INTEGER         DEFAULT 0,
    error_message   TEXT
);
COMMENT ON TABLE batch_job_log IS '배치 작업 실행 이력';

DO $$
DECLARE
    start_date DATE := '2023-01-01';
    end_date DATE;
    partition_name TEXT;
BEGIN
    WHILE start_date < '2027-01-01' LOOP
        end_date := start_date + INTERVAL '1 month';
        partition_name := 'stock_price_' || TO_CHAR(start_date, 'YYYY_MM');
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF stock_price FOR VALUES FROM (%L) TO (%L)',
            partition_name, start_date, end_date
        );
        start_date := end_date;
    END LOOP;
END $$;

DO $$
DECLARE
    start_date DATE := '2023-01-01';
    end_date DATE;
    partition_name TEXT;
BEGIN
    WHILE start_date < '2027-01-01' LOOP
        end_date := start_date + INTERVAL '1 month';
        partition_name := 'short_selling_' || TO_CHAR(start_date, 'YYYY_MM');
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF short_selling FOR VALUES FROM (%L) TO (%L)',
            partition_name, start_date, end_date
        );
        start_date := end_date;
    END LOOP;
END $$;

DO $$
DECLARE
    start_date DATE := '2023-01-01';
    end_date DATE;
    partition_name TEXT;
BEGIN
    WHILE start_date < '2027-01-01' LOOP
        end_date := start_date + INTERVAL '1 month';
        partition_name := 'lending_balance_' || TO_CHAR(start_date, 'YYYY_MM');
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF lending_balance FOR VALUES FROM (%L) TO (%L)',
            partition_name, start_date, end_date
        );
        start_date := end_date;
    END LOOP;
END $$;

ALTER TABLE signal
    ADD CONSTRAINT fk_signal_stock FOREIGN KEY (stock_id) REFERENCES stock(id);
"""


DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS signal CASCADE;
DROP TABLE IF EXISTS backtest_result CASCADE;
DROP TABLE IF EXISTS batch_job_log CASCADE;
DROP TABLE IF EXISTS lending_balance CASCADE;
DROP TABLE IF EXISTS short_selling CASCADE;
DROP TABLE IF EXISTS stock_price CASCADE;
DROP TABLE IF EXISTS stock CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
