'use client';

import { useEffect, useState } from 'react';
import { getBacktestResults } from '@/lib/api/client';
import ErrorBoundary from '@/components/ErrorBoundary';
import { BacktestSummary } from '@/types/signal';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';

const SIGNAL_TYPE_NAMES: Record<string, string> = {
  RAPID_DECLINE: '대차 급감',
  TREND_REVERSAL: '추세 전환',
  SHORT_SQUEEZE: '숏스퀴즈',
};

function hitRateColor(rate: number): string {
  if (rate >= 60) return 'text-[#00D68F]';
  if (rate >= 50) return 'text-[#FFCC00]';
  return 'text-[#FF4D6A]';
}

function returnColor(val: number): string {
  return val > 0 ? 'text-[#FF4D6A]' : val < 0 ? 'text-[#6395FF]' : 'text-[#6B7A90]';
}

export default function BacktestPage() {
  const [results, setResults] = useState<BacktestSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getBacktestResults()
      .then(data => { setResults(data); setLoading(false); })
      .catch(err => { setError(err.message); setLoading(false); });
  }, []);

  // 차트 데이터 변환
  const chartData = results.map(r => ({
    name: SIGNAL_TYPE_NAMES[r.signalType] || r.signalType,
    '5일': r.avgReturn5d ?? 0,
    '10일': r.avgReturn10d ?? 0,
    '20일': r.avgReturn20d ?? 0,
  }));

  const periodStr = results.length > 0
    ? `${results[0].periodStart} — ${results[0].periodEnd}`
    : '';

  return (
    <main className="max-w-6xl mx-auto px-4 sm:px-5 py-5 sm:py-7">
      {/* Header */}
      <div className="mb-2">
        <h1 className="font-[family-name:var(--font-display)] text-xl font-bold">
          Backtest Results
        </h1>
      </div>
      {periodStr && (
        <p className="font-[family-name:var(--font-mono)] text-xs text-[#3D4A5C] mb-6">
          {periodStr}
        </p>
      )}

      {loading && (
        <div className="space-y-4" aria-busy="true" aria-live="polite">
          <div className="h-48 bg-[#131720] rounded-[14px] animate-pulse" />
          <div className="h-64 bg-[#131720] rounded-[14px] animate-pulse" />
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

      {!loading && !error && results.length === 0 && (
        <div className="text-center py-16">
          <div className="text-4xl mb-4 opacity-30">📈</div>
          <p className="text-[#6B7A90]">백테스팅을 아직 실행하지 않았어요</p>
          <p className="text-[#3D4A5C] text-sm mt-1">데이터 수집 후 자동으로 실행됩니다</p>
        </div>
      )}

      {!loading && !error && results.length > 0 && (
        <>
          {/* Summary — Table (desktop) */}
          <div className="hidden sm:block bg-[#131720] border border-white/[0.06] rounded-[14px] overflow-x-auto mb-6">
            <table className="w-full text-sm">
              <caption className="sr-only">시그널 타입별 백테스팅 결과</caption>
              <thead>
                <tr className="bg-[#0B0E11] text-left">
                  <th className="px-4 py-3 text-[0.7rem] text-[#3D4A5C] uppercase tracking-wider font-[family-name:var(--font-display)] font-semibold" scope="col">시그널</th>
                  <th className="px-4 py-3 text-right text-[0.7rem] text-[#3D4A5C] uppercase tracking-wider font-[family-name:var(--font-display)] font-semibold" scope="col">발생</th>
                  <th className="px-4 py-3 text-right text-[0.7rem] text-[#3D4A5C] uppercase tracking-wider font-[family-name:var(--font-display)] font-semibold" scope="col">적중률(5d)</th>
                  <th className="px-4 py-3 text-right text-[0.7rem] text-[#3D4A5C] uppercase tracking-wider font-[family-name:var(--font-display)] font-semibold" scope="col">적중률(10d)</th>
                  <th className="px-4 py-3 text-right text-[0.7rem] text-[#3D4A5C] uppercase tracking-wider font-[family-name:var(--font-display)] font-semibold" scope="col">적중률(20d)</th>
                  <th className="px-4 py-3 text-right text-[0.7rem] text-[#3D4A5C] uppercase tracking-wider font-[family-name:var(--font-display)] font-semibold" scope="col">수익률(5d)</th>
                </tr>
              </thead>
              <tbody>
                {results.map(r => (
                  <tr key={r.signalType} className="border-t border-white/[0.06] hover:bg-[#1E2538] transition-colors">
                    <th className="px-4 py-3 font-medium text-left" scope="row">{SIGNAL_TYPE_NAMES[r.signalType] || r.signalType}</th>
                    <td className="px-4 py-3 text-right font-[family-name:var(--font-mono)]">{r.totalSignals}</td>
                    <td className={`px-4 py-3 text-right font-semibold font-[family-name:var(--font-mono)] ${hitRateColor(r.hitRate5d ?? 0)}`}>
                      {(r.hitRate5d ?? 0).toFixed(1)}%
                    </td>
                    <td className={`px-4 py-3 text-right font-[family-name:var(--font-mono)] ${hitRateColor(r.hitRate10d ?? 0)}`}>
                      {(r.hitRate10d ?? 0).toFixed(1)}%
                    </td>
                    <td className={`px-4 py-3 text-right font-[family-name:var(--font-mono)] ${hitRateColor(r.hitRate20d ?? 0)}`}>
                      {(r.hitRate20d ?? 0).toFixed(1)}%
                    </td>
                    <td className={`px-4 py-3 text-right font-semibold font-[family-name:var(--font-mono)] ${returnColor(r.avgReturn5d ?? 0)}`}>
                      {(r.avgReturn5d ?? 0) > 0 ? '+' : ''}{(r.avgReturn5d ?? 0).toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Summary — Card list (mobile) */}
          <ul className="sm:hidden space-y-3 mb-6" aria-label="시그널 타입별 백테스팅 결과">
            {results.map(r => (
              <li key={r.signalType} className="bg-[#131720] border border-white/[0.06] rounded-[14px] p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="font-semibold text-sm">{SIGNAL_TYPE_NAMES[r.signalType] || r.signalType}</span>
                  <span className="font-[family-name:var(--font-mono)] text-xs text-[#6B7A90]">
                    발생 {r.totalSignals}
                  </span>
                </div>
                <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
                  <div className="flex justify-between">
                    <dt className="text-[#6B7A90]">적중 5d</dt>
                    <dd className={`font-[family-name:var(--font-mono)] font-semibold ${hitRateColor(r.hitRate5d ?? 0)}`}>
                      {(r.hitRate5d ?? 0).toFixed(1)}%
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-[#6B7A90]">수익 5d</dt>
                    <dd className={`font-[family-name:var(--font-mono)] font-semibold ${returnColor(r.avgReturn5d ?? 0)}`}>
                      {(r.avgReturn5d ?? 0) > 0 ? '+' : ''}{(r.avgReturn5d ?? 0).toFixed(1)}%
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-[#6B7A90]">적중 10d</dt>
                    <dd className={`font-[family-name:var(--font-mono)] ${hitRateColor(r.hitRate10d ?? 0)}`}>
                      {(r.hitRate10d ?? 0).toFixed(1)}%
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-[#6B7A90]">적중 20d</dt>
                    <dd className={`font-[family-name:var(--font-mono)] ${hitRateColor(r.hitRate20d ?? 0)}`}>
                      {(r.hitRate20d ?? 0).toFixed(1)}%
                    </dd>
                  </div>
                </dl>
              </li>
            ))}
          </ul>

          {/* Return Chart */}
          <ErrorBoundary resetKeys={[chartData.length]}>
          <div className="bg-[#131720] border border-white/[0.06] rounded-[14px] p-3 sm:p-4">
            <h2 className="text-[0.78rem] font-semibold text-[#6B7A90] font-[family-name:var(--font-display)] mb-4">
              보유기간별 평균 수익률
            </h2>
            <ResponsiveContainer width="100%" aspect={2.2}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="name" tick={{ fill: '#4A5568', fontSize: 11 }} tickLine={false} />
                <YAxis
                  tick={{ fill: '#4A5568', fontSize: 10 }}
                  tickFormatter={v => `${v > 0 ? '+' : ''}${v}%`}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={{ background: '#1A1F28', border: 'none', borderRadius: 10, color: '#E8ECF1' }}
                  formatter={(value) => {
                    const v = Number(value);
                    return [`${v > 0 ? '+' : ''}${v.toFixed(1)}%`, ''];
                  }}
                />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 11, color: '#6B7A90' }} />
                <Bar dataKey="5일" fill="#6395FF" radius={[4, 4, 0, 0]} />
                <Bar dataKey="10일" fill="#a78bfa" radius={[4, 4, 0, 0]} />
                <Bar dataKey="20일" fill="rgba(99,149,255,0.2)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          </ErrorBoundary>
        </>
      )}
    </main>
  );
}
