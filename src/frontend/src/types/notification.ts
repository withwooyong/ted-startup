import type { SignalType } from './signal';

// 백엔드 API 가 snake_case 로 응답하므로 프로젝트 전역 컨벤션에 맞춰 필드명을 snake_case 로 유지.
// (StockSummary, StockPricePoint 등 다른 타입과 동일한 규약.)
export interface NotificationPreference {
  daily_summary_enabled: boolean;
  urgent_alert_enabled: boolean;
  batch_failure_enabled: boolean;
  weekly_report_enabled: boolean;
  min_score: number;
  signal_types: SignalType[];
  updated_at: string;
}

export type NotificationPreferenceUpdate = Omit<NotificationPreference, 'updated_at'>;

export const NOTIFICATION_CHANNEL_LABELS: Record<
  keyof Pick<
    NotificationPreference,
    'daily_summary_enabled' | 'urgent_alert_enabled' | 'batch_failure_enabled' | 'weekly_report_enabled'
  >,
  { title: string; desc: string }
> = {
  daily_summary_enabled: {
    title: '일일 요약',
    desc: '매일 아침 08:30 — 당일 시그널 리스트와 상위 3건',
  },
  urgent_alert_enabled: {
    title: '긴급 알림 (A등급)',
    desc: '스코어 80+ 시그널을 탐지 즉시 개별 발송',
  },
  batch_failure_enabled: {
    title: '배치 실패',
    desc: 'KRX 크롤러 / 시그널 탐지 배치가 실패하면 알림',
  },
  weekly_report_enabled: {
    title: '주간 리포트',
    desc: '매주 토요일 10:00 — 지난주 시그널 성과',
  },
};
