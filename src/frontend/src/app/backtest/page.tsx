'use client';

import { useEffect, useMemo, useState } from 'react';
import { getBacktestResults } from '@/lib/api/client';
import ErrorBoundary from '@/components/ErrorBoundary';
import { BacktestSummary } from '@/types/signal';
import GroupedBarChart, {
  type CategoryRow,
  type SeriesDef,
} from '@/components/charts/GroupedBarChart';

const RETURN_SERIES: SeriesDef[] = [
  { key: '5d', label: '5일', color: '#6395FF' },
  { key: '10d', label: '10일', color: '#a78bfa' },
  { key: '20d', label: '20일', color: 'rgba(163,175,200,0.55)' },
];

const returnFormatter = (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(1)}%`;

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

  // 백엔드가 Decimal 을 string 으로 직렬화 — 안전 변환 헬퍼.
  const num = (v: string | null | undefined): number => (v ? Number(v) : 0);

  // 그룹 막대 차트 데이터 (전략 × 5/10/20일 수익률)
  const chartData = useMemo<CategoryRow[]>(
    () =>
      results.map(r => ({
        name: SIGNAL_TYPE_NAMES[r.signal_type] || r.signal_type,
        values: {
          '5d': num(r.avg_return_5d),
          '10d': num(r.avg_return_10d),
          '20d': num(r.avg_return_20d),
        },
      })),
    [results]
  );

  const periodStr = results.length > 0
    ? `${results[0].period_start} — ${results[0].period_end}`
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
                {results.map(r => {
                  const h5 = num(r.hit_rate_5d);
                  const h10 = num(r.hit_rate_10d);
                  const h20 = num(r.hit_rate_20d);
                  const ar5 = num(r.avg_return_5d);
                  return (
                    <tr key={r.signal_type} className="border-t border-white/[0.06] hover:bg-[#1E2538] transition-colors">
                      <th className="px-4 py-3 font-medium text-left" scope="row">{SIGNAL_TYPE_NAMES[r.signal_type] || r.signal_type}</th>
                      <td className="px-4 py-3 text-right font-[family-name:var(--font-mono)]">{r.total_signals}</td>
                      <td className={`px-4 py-3 text-right font-semibold font-[family-name:var(--font-mono)] ${hitRateColor(h5)}`}>
                        {h5.toFixed(1)}%
                      </td>
                      <td className={`px-4 py-3 text-right font-[family-name:var(--font-mono)] ${hitRateColor(h10)}`}>
                        {h10.toFixed(1)}%
                      </td>
                      <td className={`px-4 py-3 text-right font-[family-name:var(--font-mono)] ${hitRateColor(h20)}`}>
                        {h20.toFixed(1)}%
                      </td>
                      <td className={`px-4 py-3 text-right font-semibold font-[family-name:var(--font-mono)] ${returnColor(ar5)}`}>
                        {ar5 > 0 ? '+' : ''}{ar5.toFixed(1)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Summary — Card list (mobile) */}
          <ul className="sm:hidden space-y-3 mb-6" aria-label="시그널 타입별 백테스팅 결과">
            {results.map(r => {
              const h5 = num(r.hit_rate_5d);
              const h10 = num(r.hit_rate_10d);
              const h20 = num(r.hit_rate_20d);
              const ar5 = num(r.avg_return_5d);
              return (
                <li key={r.signal_type} className="bg-[#131720] border border-white/[0.06] rounded-[14px] p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-semibold text-sm">{SIGNAL_TYPE_NAMES[r.signal_type] || r.signal_type}</span>
                    <span className="font-[family-name:var(--font-mono)] text-xs text-[#6B7A90]">
                      발생 {r.total_signals}
                    </span>
                  </div>
                  <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
                    <div className="flex justify-between">
                      <dt className="text-[#6B7A90]">적중 5d</dt>
                      <dd className={`font-[family-name:var(--font-mono)] font-semibold ${hitRateColor(h5)}`}>
                        {h5.toFixed(1)}%
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-[#6B7A90]">수익 5d</dt>
                      <dd className={`font-[family-name:var(--font-mono)] font-semibold ${returnColor(ar5)}`}>
                        {ar5 > 0 ? '+' : ''}{ar5.toFixed(1)}%
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-[#6B7A90]">적중 10d</dt>
                      <dd className={`font-[family-name:var(--font-mono)] ${hitRateColor(h10)}`}>
                        {h10.toFixed(1)}%
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-[#6B7A90]">적중 20d</dt>
                      <dd className={`font-[family-name:var(--font-mono)] ${hitRateColor(h20)}`}>
                        {h20.toFixed(1)}%
                      </dd>
                    </div>
                  </dl>
                </li>
              );
            })}
          </ul>

          {/* Return Chart */}
          <ErrorBoundary resetKeys={[chartData.length]}>
            <div className="bg-[#131720] border border-white/[0.06] rounded-[14px] p-3 sm:p-4">
              <h2 className="text-[0.78rem] font-semibold text-[#6B7A90] font-[family-name:var(--font-display)] mb-4">
                보유기간별 평균 수익률
              </h2>
              <div className="aspect-[1.4/1] sm:aspect-[2.2/1]">
                <GroupedBarChart
                  data={chartData}
                  series={RETURN_SERIES}
                  valueFormatter={returnFormatter}
                  ariaLabel="시그널 타입별 보유기간(5·10·20일) 평균 수익률"
                />
              </div>
            </div>
          </ErrorBoundary>
        </>
      )}
    </main>
  );
}
