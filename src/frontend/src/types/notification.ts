import type { SignalType } from './signal';

export interface NotificationPreference {
  dailySummaryEnabled: boolean;
  urgentAlertEnabled: boolean;
  batchFailureEnabled: boolean;
  weeklyReportEnabled: boolean;
  minScore: number;
  signalTypes: SignalType[];
  updatedAt: string;
}

export type NotificationPreferenceUpdate = Omit<NotificationPreference, 'updatedAt'>;

export const NOTIFICATION_CHANNEL_LABELS: Record<
  keyof Pick<
    NotificationPreference,
    'dailySummaryEnabled' | 'urgentAlertEnabled' | 'batchFailureEnabled' | 'weeklyReportEnabled'
  >,
  { title: string; desc: string }
> = {
  dailySummaryEnabled: {
    title: '일일 요약',
    desc: '매일 아침 08:30 — 당일 시그널 리스트와 상위 3건',
  },
  urgentAlertEnabled: {
    title: '긴급 알림 (A등급)',
    desc: '스코어 80+ 시그널을 탐지 즉시 개별 발송',
  },
  batchFailureEnabled: {
    title: '배치 실패',
    desc: 'KRX 크롤러 / 시그널 탐지 배치가 실패하면 알림',
  },
  weeklyReportEnabled: {
    title: '주간 리포트',
    desc: '매주 토요일 10:00 — 지난주 시그널 성과',
  },
};
