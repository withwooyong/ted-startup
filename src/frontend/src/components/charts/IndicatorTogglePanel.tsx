'use client';

import type { IndicatorToggles } from '@/lib/hooks/useIndicatorPreferences';

interface ToggleItem {
  key: keyof IndicatorToggles;
  label: string;
  color: string;
}

// 색은 PriceAreaChart 의 각 시리즈 색과 동기. 바뀌면 한 곳에서 맞춰 업데이트.
// label 은 시각 기본값 표기 — 실제 파라미터는 prefs.params 에서 사용자 편집 가능 (v1.2 Cp 2β 편집 UI 에서).
const ITEMS: ReadonlyArray<ToggleItem> = [
  { key: 'ma5', label: 'MA5', color: '#FFCC00' },
  { key: 'ma20', label: 'MA20', color: '#FF8B3E' },
  { key: 'ma60', label: 'MA60', color: '#00D68F' },
  { key: 'ma120', label: 'MA120', color: '#A78BFA' },
  { key: 'volume', label: '거래량', color: '#FF4D6A' },
  { key: 'rsi', label: 'RSI', color: '#00BCFF' },
  { key: 'macd', label: 'MACD', color: '#FF80EC' },
  { key: 'bb', label: 'BB', color: '#6FD4D4' },
];

interface Props {
  toggles: IndicatorToggles;
  onToggle: <K extends keyof IndicatorToggles>(key: K, value: boolean) => void;
  onOpenSettings?: () => void;
}

export default function IndicatorTogglePanel({ toggles, onToggle, onOpenSettings }: Props) {
  return (
    <div
      className="flex flex-wrap items-center gap-1.5 mb-3"
      role="group"
      aria-label="차트 지표 토글"
    >
      {ITEMS.map(it => {
        const active = toggles[it.key];
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
      {onOpenSettings && (
        <button
          type="button"
          onClick={onOpenSettings}
          aria-label="지표 파라미터 설정 열기"
          className="ml-auto flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium text-[#7A8699] hover:text-[#E8ECF1] border border-white/[0.06] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50"
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
          설정
        </button>
      )}
    </div>
  );
}
