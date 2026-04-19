// 백엔드(FastAPI + Pydantic) 응답 스키마를 그대로 반영 — snake_case.
// 이전 camelCase 타입은 백엔드 SignalResponse 와 필드가 달라 런타임에 undefined
// 참조가 다수 있었음. P14 의 portfolio.ts/report.ts 와 정합성 유지.

export type SignalType = 'RAPID_DECLINE' | 'TREND_REVERSAL' | 'SHORT_SQUEEZE';
export type SignalGrade = 'A' | 'B' | 'C' | 'D';

// SignalDetectionService 가 detail JSONB 에 저장하는 서브필드.
// 시그널 타입별로 포함 필드가 다르므로 모두 optional.
export interface SignalDetail {
  balanceChangeRate?: string | number;
  volumeChangeRate?: string | number;
  consecutiveDecreaseDays?: number;
  balanceScore?: number;
  volumeScore?: number;
  priceChangeRate?: string | number;
  priceScore?: number;
  changeQuantity?: number;
  // 타입별 추가 필드는 unknown 으로 허용
  [key: string]: unknown;
}

export interface SignalResult {
  id: number;
  stock_id: number;
  stock_code: string | null;
  stock_name: string | null;
  signal_date: string;
  signal_type: SignalType;
  score: number;
  grade: SignalGrade;
  detail: SignalDetail | null;
  return_5d: string | null;
  return_10d: string | null;
  return_20d: string | null;
}

export interface LatestSignalsResult {
  signal_date: string | null;
  signals: SignalResult[];
}

export interface StockSummary {
  stock_code: string;
  stock_name: string;
  market_type: string;
}

export interface StockPricePoint {
  trading_date: string;
  close_price: number;
  open_price: number | null;
  high_price: number | null;
  low_price: number | null;
  volume: number;
  change_rate: string | null;
}

export interface StockDetail {
  stock: StockSummary;
  prices: StockPricePoint[];
  signals: SignalResult[];
}

export interface BacktestSummary {
  id: number;
  signal_type: string;
  period_start: string;
  period_end: string;
  total_signals: number;
  hit_count_5d: number | null;
  hit_rate_5d: string | null;
  avg_return_5d: string | null;
  hit_count_10d: number | null;
  hit_rate_10d: string | null;
  avg_return_10d: string | null;
  hit_count_20d: number | null;
  hit_rate_20d: string | null;
  avg_return_20d: string | null;
  created_at: string;
}

export const SIGNAL_TYPE_LABELS: Record<SignalType, string> = {
  RAPID_DECLINE: '급감',
  TREND_REVERSAL: '추세전환',
  SHORT_SQUEEZE: '숏스퀴즈',
};

export const SIGNAL_TYPE_ICONS: Record<SignalType, string> = {
  RAPID_DECLINE: '↘',
  TREND_REVERSAL: '↗',
  SHORT_SQUEEZE: '⚡',
};

export const GRADE_COLORS: Record<SignalGrade, string> = {
  A: 'text-[#FF4D6A] bg-[#FF4D6A]/10',
  B: 'text-[#FF8B3E] bg-[#FF8B3E]/10',
  C: 'text-[#FFCC00] bg-[#FFCC00]/10',
  D: 'text-[#4A5568] bg-white/5',
};

// detail 숫자 필드를 안전하게 number 로 변환하는 헬퍼.
// 백엔드가 Decimal 을 string 으로 직렬화하는 경우가 있어 통일 처리.
export function detailNumber(detail: SignalDetail | null | undefined, key: keyof SignalDetail): number {
  if (!detail) return 0;
  const raw = detail[key];
  if (typeof raw === 'number') return raw;
  if (typeof raw === 'string') {
    const n = Number(raw);
    return Number.isFinite(n) ? n : 0;
  }
  return 0;
}
