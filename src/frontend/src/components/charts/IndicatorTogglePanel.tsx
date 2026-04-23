'use client';

import type { IndicatorPrefs } from '@/lib/hooks/useIndicatorPreferences';

interface ToggleItem {
  key: keyof IndicatorPrefs;
  label: string;
  color: string;
}

// 색은 PriceAreaChart 의 각 시리즈 색과 동기. 바뀌면 한 곳에서 맞춰 업데이트.
const ITEMS: ReadonlyArray<ToggleItem> = [
  { key: 'ma5', label: 'MA5', color: '#FFCC00' },
  { key: 'ma20', label: 'MA20', color: '#FF8B3E' },
  { key: 'ma60', label: 'MA60', color: '#00D68F' },
  { key: 'ma120', label: 'MA120', color: '#A78BFA' },
  { key: 'volume', label: '거래량', color: '#FF4D6A' },
  { key: 'rsi', label: 'RSI(14)', color: '#00BCFF' },
  { key: 'macd', label: 'MACD', color: '#FF80EC' },
];

interface Props {
  prefs: IndicatorPrefs;
  onToggle: <K extends keyof IndicatorPrefs>(key: K, value: boolean) => void;
}

export default function IndicatorTogglePanel({ prefs, onToggle }: Props) {
  return (
    <div
      className="flex flex-wrap gap-1.5 mb-3"
      role="group"
      aria-label="차트 지표 토글"
    >
      {ITEMS.map(it => {
        const active = prefs[it.key];
        return (
          <button
            key={it.key}
            type="button"
            aria-pressed={active}
            onClick={() => onToggle(it.key, !active)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50 ${
              active
                ? 'bg-white/10 text-[#E8ECF1]'
                : 'text-[#6B7A90] hover:text-[#E8ECF1]'
            }`}
          >
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: active ? it.color : '#3D4A5C' }}
              aria-hidden="true"
            />
            {it.label}
          </button>
        );
      })}
    </div>
  );
}
