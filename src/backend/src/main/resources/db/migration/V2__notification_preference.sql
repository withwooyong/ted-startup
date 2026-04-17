-- =============================================================
-- V2 — 알림 설정 테이블 (Sprint 4 Task 4)
-- =============================================================
-- 싱글 로우 설계: 1인 운영 MVP 기준 (id=1 고정). 향후 user_id FK 도입 시 확장.
-- 참고: 현재 Flyway 미도입 → Hibernate `create-drop`(테스트/로컬)이 실 스키마 생성.
--       프로덕션 전환 시 이 파일을 V1 이후 순서로 수동 실행하거나 Flyway 도입.

CREATE TABLE notification_preference (
    id                      BIGINT       PRIMARY KEY,
    daily_summary_enabled   BOOLEAN      NOT NULL DEFAULT TRUE,
    urgent_alert_enabled    BOOLEAN      NOT NULL DEFAULT TRUE,
    batch_failure_enabled   BOOLEAN      NOT NULL DEFAULT TRUE,
    weekly_report_enabled   BOOLEAN      NOT NULL DEFAULT TRUE,
    min_score               INTEGER      NOT NULL DEFAULT 60 CHECK (min_score BETWEEN 0 AND 100),
    signal_types            JSONB        NOT NULL DEFAULT '["RAPID_DECLINE","TREND_REVERSAL","SHORT_SQUEEZE"]'::jsonb,
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE notification_preference IS '사용자 알림 설정 (싱글 로우, id=1)';
COMMENT ON COLUMN notification_preference.min_score IS '필터 임계값 (이 스코어 미만 시그널은 알림 제외)';
COMMENT ON COLUMN notification_preference.signal_types IS '알림 대상 시그널 타입 배열';

-- 기본 row 삽입 (존재하지 않을 때만)
INSERT INTO notification_preference (id)
VALUES (1)
ON CONFLICT (id) DO NOTHING;
