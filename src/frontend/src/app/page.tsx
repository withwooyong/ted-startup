'use client';

import { useEffect, useState } from 'react';
import SignalCard from '@/components/features/SignalCard';
import { getSignals } from '@/lib/api/client';
import { SignalResult } from '@/types/signal';

const FILTERS = [
  { key: 'all', label: '전체' },
  { key: 'RAPID_DECLINE', label: '급감' },
  { key: 'TREND_REVERSAL', label: '추세전환' },
  { key: 'SHORT_SQUEEZE', label: '숏스퀴즈' },
];

export default function DashboardPage() {
  const [signals, setSignals] = useState<SignalResult[]>([]);
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState<'score' | 'change'>('score');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    getSignals()
      .then((data: SignalResult[]) => {
        setSignals(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const filtered = filter === 'all'
    ? signals
    : signals.filter(s => s.signalType === filter);

  const sorted = [...filtered].sort((a, b) =>
    sort === 'score' ? b.score - a.score : a.balanceChangeRate - b.balanceChangeRate
  );

  const counts: Record<string, number> = {
    all: signals.length,
    RAPID_DECLINE: signals.filter(s => s.signalType === 'RAPID_DECLINE').length,
    TREND_REVERSAL: signals.filter(s => s.signalType === 'TREND_REVERSAL').length,
    SHORT_SQUEEZE: signals.filter(s => s.signalType === 'SHORT_SQUEEZE').length,
  };

  return (
    <main className="max-w-6xl mx-auto px-5 py-7">
      {/* Header */}
      <div className="flex items-center justify-between mb-7">
        <h1 className="font-[family-name:var(--font-display)] text-xl font-bold bg-gradient-to-r from-[#6395FF] to-[#a78bfa] bg-clip-text text-transparent">
          SIGNAL<span className="text-[#3D4A5C] text-xs font-normal ml-2">v1.0</span>
        </h1>
        <span className="font-[family-name:var(--font-mono)] text-xs text-[#3D4A5C]">
          {new Date().toISOString().split('T')[0]}
        </span>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-7">
        {[
          { label: 'Total Signals', value: counts.all, color: '' },
          { label: 'Rapid Decline', value: counts.RAPID_DECLINE, color: 'text-[#FF4D6A]' },
          { label: 'Trend Reversal', value: counts.TREND_REVERSAL, color: 'text-[#6395FF]' },
          { label: 'Short Squeeze', value: counts.SHORT_SQUEEZE, color: 'text-[#FF8B3E]' },
        ].map(m => (
          <div key={m.label} className="bg-[#131720] border border-white/[0.06] rounded-[14px] p-4 hover:border-[#6395FF]/30 transition-colors">
            <div className="text-[0.7rem] text-[#3D4A5C] uppercase tracking-wider font-[family-name:var(--font-display)] font-medium mb-2">
              {m.label}
            </div>
            <div className={`font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight ${m.color}`}>
              {m.value}
            </div>
          </div>
        ))}
      </div>

      {/* Filter + Sort */}
      <div className="flex items-center justify-between gap-3 mb-5 flex-wrap">
        <div className="flex gap-1 bg-[#131720] rounded-[10px] p-0.5 border border-white/[0.06]">
          {FILTERS.map(f => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`px-4 py-1.5 rounded-lg text-[0.78rem] font-medium transition-all ${
                filter === f.key
                  ? 'text-white bg-[#6395FF] shadow-[0_2px_8px_rgba(99,149,255,0.3)]'
                  : 'text-[#6B7A90] hover:text-[#E8ECF1]'
              }`}
            >
              {f.label}
              <span className="text-[0.65rem] opacity-60 ml-1 font-[family-name:var(--font-mono)]">
                {counts[f.key]}
              </span>
            </button>
          ))}
        </div>
        <select
          value={sort}
          onChange={e => setSort(e.target.value as 'score' | 'change')}
          className="px-3 py-1.5 rounded-lg text-xs bg-[#131720] border border-white/[0.06] text-[#6B7A90] focus:outline-none focus:border-[#6395FF]/30"
        >
          <option value="score">스코어순</option>
          <option value="change">감소율순</option>
        </select>
      </div>

      {/* Signal List */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-20 bg-[#131720] rounded-[14px] animate-pulse" />
          ))}
        </div>
      )}

      {error && (
        <div className="text-center py-16">
          <p className="text-[#6B7A90] mb-4">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 rounded-lg bg-[#6395FF] text-white text-sm"
          >
            다시 시도
          </button>
        </div>
      )}

      {!loading && !error && sorted.length === 0 && (
        <div className="text-center py-16">
          <div className="text-4xl mb-4 opacity-30">📊</div>
          <p className="text-[#6B7A90]">오늘은 탐지된 시그널이 없어요</p>
          <p className="text-[#3D4A5C] text-sm mt-1">내일 다시 확인해 보세요</p>
        </div>
      )}

      {!loading && !error && sorted.length > 0 && (
        <div className="space-y-2">
          {sorted.map(s => (
            <SignalCard key={s.signalId} signal={s} />
          ))}
        </div>
      )}
    </main>
  );
}
