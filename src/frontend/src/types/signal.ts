export type SignalType = 'RAPID_DECLINE' | 'TREND_REVERSAL' | 'SHORT_SQUEEZE';
export type SignalGrade = 'A' | 'B' | 'C' | 'D';

export interface SignalResult {
  signalId: number;
  stockCode: string;
  stockName: string;
  marketType: string;
  signalType: SignalType;
  score: number;
  grade: SignalGrade;
  balanceChangeRate: number;
  volumeChangeRate: number;
  consecutiveDecreaseDays: number;
  signalDate: string;
}

export interface StockDetail {
  stockCode: string;
  stockName: string;
  marketType: string;
  latestPrice: {
    closePrice: number;
    changeRate: number | null;
    volume: number;
    marketCap: number;
  };
  timeSeries: TimeSeriesPoint[];
  signals: SignalMarker[];
}

export interface TimeSeriesPoint {
  date: string;
  price: number;
  lendingBalance: number;
}

export interface SignalMarker {
  date: string;
  signalType: SignalType;
  score: number;
  grade: SignalGrade;
  detail: Record<string, unknown>;
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

export interface BacktestSummary {
  signalType: string;
  periodStart: string;
  periodEnd: string;
  totalSignals: number;
  hitCount5d: number;
  hitRate5d: number;
  avgReturn5d: number;
  hitCount10d: number;
  hitRate10d: number;
  avgReturn10d: number;
  hitCount20d: number;
  hitRate20d: number;
  avgReturn20d: number;
}

export const GRADE_COLORS: Record<SignalGrade, string> = {
  A: 'text-[#FF4D6A] bg-[#FF4D6A]/10',
  B: 'text-[#FF8B3E] bg-[#FF8B3E]/10',
  C: 'text-[#FFCC00] bg-[#FFCC00]/10',
  D: 'text-[#4A5568] bg-white/5',
};
