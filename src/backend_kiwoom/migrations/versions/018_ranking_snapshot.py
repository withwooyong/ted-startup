"""kiwoom.ranking_snapshot 신규 — Phase F-4 5 ranking endpoint 통합 (ka10027/30/31/32/23).

Revision ID: 018_ranking_snapshot
Revises: 017_ka10001_numeric_precision
Create Date: 2026-05-15

설계: phase-f-4-rankings.md § 5.1 + endpoint-18-ka10027.md § 5.1.

사용자 확정 (D-1~D-14 권고 default 일괄 채택):
- D-2 단일 테이블 + JSONB payload + ranking_type 컬럼
- D-7 snapshot_time 초 단위 (HH:MM:SS) — TIME 타입 (PG default microsecond precision 호환)
- D-8 stock lookup miss → stock_id=NULL + stock_code_raw 보존 (ON DELETE SET NULL)
- D-9 ka10030 23 필드 nested payload ({opmr, af_mkrt, bf_mkrt} 분리)
- D-12 primary_metric NUMERIC(20, 4)
- D-13 GIN index payload 1개 (ad-hoc 쿼리)

특징 (016/017 패턴 1:1 응용):
- #1 revision id = ``018_ranking_snapshot`` (≤32자 VARCHAR 안전)
- #2 1 테이블 1 마이그레이션 + UNIQUE 7컬럼 + 3 인덱스 (date+type / stock partial / payload GIN)
- #3 ON DELETE SET NULL — stock 삭제 시 ranking_snapshot row 보존 (lookup miss 흔적 + 비파괴)
- #4 idx_ranking_stock = partial index WHERE stock_id IS NOT NULL — lookup miss row 진입 차단
- #5 downgrade 가드 (016 row count 가드 패턴) — 빈 테이블만 DROP
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "018_ranking_snapshot"
down_revision: str | Sequence[str] | None = "017_ka10001_numeric_precision"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPGRADE_SQL = r"""
-- ============================================================================
-- ranking_snapshot — 5 ranking endpoint 통합 (ka10027 등락률 / ka10030 당일거래량 /
-- ka10031 전일거래량 / ka10032 거래대금 / ka10023 거래량 급증)
-- 단일 테이블 + JSONB payload + ranking_type 컬럼 — 새 ranking 추가 시 enum + UseCase 만.
-- ============================================================================
CREATE TABLE kiwoom.ranking_snapshot (
    id                BIGSERIAL       PRIMARY KEY,
    snapshot_date     DATE            NOT NULL,
    snapshot_time     TIME            NOT NULL,
    ranking_type      VARCHAR(16)     NOT NULL,
    sort_tp           VARCHAR(2)      NOT NULL,
    market_type       VARCHAR(3)      NOT NULL,
    exchange_type     VARCHAR(1)      NOT NULL,
    rank              INTEGER         NOT NULL,

    -- lookup miss 시 stock_id=NULL + stock_code_raw 보존 (D-8). ON DELETE SET NULL —
    -- stock 마스터에서 종목 삭제돼도 본 row 의 stock_id 만 NULL 로 변환 + raw 보존.
    stock_id          BIGINT          REFERENCES kiwoom.stock(id) ON DELETE SET NULL,
    stock_code_raw    VARCHAR(20)     NOT NULL,

    primary_metric    NUMERIC(20, 4),

    -- D-9 nested payload — ka10030 23 필드 {opmr, af_mkrt, bf_mkrt} 분리.
    -- 기타 endpoint 의 도메인 별 필드도 본 컬럼에 nested 저장.
    payload           JSONB           NOT NULL,

    -- 호출 시 본 row 가 어떤 필터 조합으로 생성됐는지 재현용 (mrkt_tp/sort_tp/... 최대 9 필터).
    request_filters   JSONB           NOT NULL,

    fetched_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- 멱등 키 — 같은 (date+time+type+sort+market+exchange+rank) 재호출 시 UPDATE.
    CONSTRAINT uq_ranking_snapshot UNIQUE (
        snapshot_date, snapshot_time, ranking_type, sort_tp,
        market_type, exchange_type, rank
    )
);

COMMENT ON TABLE kiwoom.ranking_snapshot IS
    'Phase F-4 ka10027/30/31/32/23 5 ranking endpoint 통합 스냅샷. '
    '단일 테이블 + JSONB payload + ranking_type 컬럼 (D-2).';
COMMENT ON COLUMN kiwoom.ranking_snapshot.ranking_type IS
    'FLU_RT (ka10027) / TODAY_VOLUME (ka10030) / PRED_VOLUME (ka10031) / TRDE_PRICA (ka10032) / VOLUME_SDNIN (ka10023)';
COMMENT ON COLUMN kiwoom.ranking_snapshot.market_type IS
    '000=전체 / 001=KOSPI / 101=KOSDAQ (Phase F 5 endpoint 공통 — ka10099/ka10101 과 다름)';
COMMENT ON COLUMN kiwoom.ranking_snapshot.exchange_type IS
    '1=KRX / 2=NXT / 3=통합 (D-4 default 3)';
COMMENT ON COLUMN kiwoom.ranking_snapshot.primary_metric IS
    '각 endpoint 정렬 기준 — NUMERIC(20,4) (D-12). flu_rt / trde_qty / trde_prica / sdnin_qty 등.';
COMMENT ON COLUMN kiwoom.ranking_snapshot.payload IS
    'JSONB nested payload. ka10030 은 {opmr,af_mkrt,bf_mkrt} 3 그룹 분리 (D-9).';
COMMENT ON COLUMN kiwoom.ranking_snapshot.request_filters IS
    '호출 시 used_filters 보관 (재현용) — mrkt_tp/sort_tp/stex_tp/trde_qty_cnd/... 최대 9 필터.';
COMMENT ON COLUMN kiwoom.ranking_snapshot.stock_code_raw IS
    'NXT _NX suffix 보존 + lookup miss 시에도 raw 보관 (D-8).';

-- 일자별 type 조회 (Phase H derived feature) — (snapshot_date, ranking_type, market_type, exchange_type).
CREATE INDEX idx_ranking_date_type
    ON kiwoom.ranking_snapshot(snapshot_date, ranking_type, market_type, exchange_type);

-- stock 별 조회 — lookup miss row 는 stock_id NULL 이라 진입 안 함 (index 크기 절감).
CREATE INDEX idx_ranking_stock
    ON kiwoom.ranking_snapshot(stock_id)
    WHERE stock_id IS NOT NULL;

-- JSONB ad-hoc 쿼리 가속 (D-13) — `payload->>'cur_prc'`, `payload @> '{"stk_cls":"0"}'` 등.
CREATE INDEX idx_ranking_payload_gin
    ON kiwoom.ranking_snapshot USING GIN (payload);
"""


DOWNGRADE_SQL = r"""
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM kiwoom.ranking_snapshot;
    IF v_count > 0 THEN
        RAISE EXCEPTION 'ranking_snapshot 데이터(%건) 가 있어 downgrade 차단. 수동 삭제 후 재시도.', v_count;
    END IF;
END $$;

DROP TABLE IF EXISTS kiwoom.ranking_snapshot CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
