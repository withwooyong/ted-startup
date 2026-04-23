'use client';

import Link from 'next/link';
import {
  GRADE_COLORS,
  SIGNAL_TYPE_ICONS,
  SIGNAL_TYPE_LABELS,
  SignalResult,
  detailNumber,
} from '@/types/signal';

const TYPE_BG: Record<string, string> = {
  RAPID_DECLINE: 'bg-[#FF8B3E]/10',
  TREND_REVERSAL: 'bg-[#6395FF]/10',
  SHORT_SQUEEZE: 'bg-[#FF4D6A]/10',
};

export default function SignalCard({ signal }: { signal: SignalResult }) {
  const s = signal;
  const balanceRate = detailNumber(s.detail, 'balanceChangeRate');
  const volumeRate = detailNumber(s.detail, 'volumeChangeRate');
  const consecutive = detailNumber(s.detail, 'consecutiveDecreaseDays');
  const stockCode = s.stock_code ?? '';
  const stockName = s.stock_name ?? '(이름 없음)';
  return (
    <Link
      href={`/stocks/${stockCode}`}
      aria-label={`${stockName} ${stockCode} — ${SIGNAL_TYPE_LABELS[s.signal_type]} 스코어 ${s.score}점 ${s.grade}등급, 상세 보기`}
      className={`
        group grid grid-cols-[40px_1fr_auto] items-center gap-3 sm:gap-4
        bg-[#131720] border border-white/[0.06] rounded-[14px] p-3 sm:p-4
        transition-all duration-200
        hover:border-[#6395FF]/30 hover:bg-[#1E2538] hover:translate-x-1
        focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50
        ${s.grade === 'A' ? 'animate-pulse-glow' : ''}
      `}
    >
        <div className={`w-10 h-10 rounded-[10px] flex items-center justify-center text-lg ${TYPE_BG[s.signal_type]}`} aria-hidden="true">
          {SIGNAL_TYPE_ICONS[s.signal_type]}
        </div>

        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold">{stockName}</span>
            <span className="font-[family-name:var(--font-mono)] text-[0.72rem] text-[#7A8699]">
              {stockCode}
            </span>
          </div>
          <div className="flex items-center gap-1 mt-1 flex-wrap">
            {balanceRate !== 0 && (
              <span className="text-[0.65rem] px-2 py-0.5 rounded bg-[#FF4D6A]/10 text-[#FF4D6A] font-[family-name:var(--font-mono)] font-medium">
                {balanceRate.toFixed(1)}%
              </span>
            )}
            {volumeRate !== 0 && (
              <span className="text-[0.65rem] px-2 py-0.5 rounded bg-[#00D68F]/10 text-[#00D68F] font-[family-name:var(--font-mono)] font-medium">
                VOL +{volumeRate.toFixed(0)}%
              </span>
            )}
            {consecutive > 0 && (
              <span className="text-[0.65rem] px-2 py-0.5 rounded bg-white/[0.04] text-[#6B7A90] font-medium">
                {consecutive}일 연속
              </span>
            )}
          </div>
        </div>

        <div className="text-right">
          <div className="font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight leading-none">
            {s.score}
          </div>
          <span className={`inline-block mt-1 px-2 py-0.5 rounded-md text-[0.65rem] font-bold font-[family-name:var(--font-display)] ${GRADE_COLORS[s.grade]}`}>
            {s.grade} · {SIGNAL_TYPE_LABELS[s.signal_type]}
          </span>
        </div>
    </Link>
  );
}
