'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { getStockDetail } from '@/lib/api/client';
import ErrorBoundary from '@/components/ErrorBoundary';
import {
  StockDetail,
  SIGNAL_TYPE_LABELS,
  GRADE_COLORS,
} from '@/types/signal';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const PERIODS = [
  { label: '1M', months: 1 },
  { label: '3M', months: 3 },
  { label: '6M', months: 6 },
  { label: '1Y', months: 12 },
];

export default function StockDetailPage() {
  const params = useParams();
  const router = useRouter();
  const rawCode = params.code;
  const code = Array.isArray(rawCode) ? rawCode[0] : rawCode ?? '';
  const [data, setData] = useState<StockDetail | null>(null);
  const [period, setPeriod] = useState(3);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [prevKey, setPrevKey] = useState(`${code}:${period}`);

  // fetch 파라미터 변경 시 loading 재진입 (render 중 리셋 패턴)
  const currentKey = `${code}:${period}`;
  if (currentKey !== prevKey) {
    setPrevKey(currentKey);
    setLoading(true);
    setError(null);
  }

  useEffect(() => {
    const to = new Date().toISOString().split('T')[0];
    const fromDate = new Date();
    fromDate.setMonth(fromDate.getMonth() - period);
    const from = fromDate.toISOString().split('T')[0];

    getStockDetail(code, from, to)
      .then((d: StockDetail) => {
        setData(d);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [code, period]);

  if (loading) {
    return (
      <main className="max-w-6xl mx-auto px-4 sm:px-5 py-5 sm:py-7" aria-busy="true" aria-live="polite">
        <div className="h-8 w-32 bg-[#131720] rounded animate-pulse mb-6" />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
          <div className="h-32 bg-[#131720] rounded-[14px] animate-pulse" />
          <div className="h-32 bg-[#131720] rounded-[14px] animate-pulse" />
        </div>
        <div className="h-60 sm:h-72 bg-[#131720] rounded-[14px] animate-pulse" />
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="max-w-6xl mx-auto px-4 sm:px-5 py-5 sm:py-7 text-center" role="alert">
        <p className="text-[#6B7A90] py-16">{error || '데이터가 없어요'}</p>
        <button onClick={() => router.push('/')} className="px-4 py-2 rounded-lg bg-[#6395FF] text-white text-sm">
          대시보드로 이동
        </button>
      </main>
    );
  }

  const latestSignal = data.signals[0];
  // 백엔드는 prices[] 배열을 trading_date 오름차순으로 반환 — 마지막이 최신.
  const latestPrice = data.prices[data.prices.length - 1];
  const changeRateNum = latestPrice?.change_rate ? Number(latestPrice.change_rate) : 0;
  const changeColor = changeRateNum > 0 ? '#FF4D6A' : changeRateNum < 0 ? '#6395FF' : '#6B7A90';

  const chartData = data.prices.map(p => ({
    date: p.trading_date.slice(5),
    price: p.close_price,
  }));

  return (
    <main className="max-w-6xl mx-auto px-4 sm:px-5 py-5 sm:py-7">
      {/* Back */}
      <button
        onClick={() => router.push('/')}
        aria-label="대시보드로 돌아가기"
        className="flex items-center gap-1 text-sm text-[#6B7A90] hover:text-[#6395FF] mb-5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50 rounded"
      >
        <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg>
        대시보드
      </button>

      {/* Header Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
        <div className="bg-[#131720] border border-white/[0.06] rounded-[14px] p-5">
          <div className="flex items-center gap-2 mb-3">
            <span className="font-[family-name:var(--font-display)] text-xl font-bold">{data.stock.stock_name}</span>
            <span className="font-[family-name:var(--font-mono)] text-sm text-[#3D4A5C]">{data.stock.stock_code}</span>
          </div>
          <div className="grid grid-cols-3 gap-2 sm:gap-4">
            <div>
              <div className="text-[0.6rem] sm:text-[0.7rem] text-[#3D4A5C] font-[family-name:var(--font-display)] uppercase">현재가</div>
              <div className="font-[family-name:var(--font-display)] text-base sm:text-xl font-semibold mt-0.5 tabular-nums">
                {latestPrice ? latestPrice.close_price.toLocaleString() : '-'}
              </div>
            </div>
            <div>
              <div className="text-[0.6rem] sm:text-[0.7rem] text-[#3D4A5C] font-[family-name:var(--font-display)] uppercase">전일비</div>
              <div className="font-[family-name:var(--font-mono)] text-base sm:text-xl font-medium mt-0.5 tabular-nums" style={{ color: changeColor }}>
                {changeRateNum > 0 ? '+' : ''}{changeRateNum.toFixed(2)}%
              </div>
            </div>
            <div>
              <div className="text-[0.6rem] sm:text-[0.7rem] text-[#3D4A5C] font-[family-name:var(--font-display)] uppercase">거래량</div>
              <div className="font-[family-name:var(--font-mono)] text-base sm:text-xl font-medium mt-0.5 tabular-nums">
                {latestPrice ? `${(latestPrice.volume / 1000000).toFixed(1)}M` : '-'}
              </div>
            </div>
          </div>
        </div>

        {latestSignal && (
          <div className="bg-[#131720] border border-white/[0.06] rounded-[14px] p-5 flex flex-col justify-between">
            <div className="flex justify-between items-start">
              <div>
                <div className="text-[0.7rem] text-[#3D4A5C] font-[family-name:var(--font-display)] uppercase">
                  {SIGNAL_TYPE_LABELS[latestSignal.signal_type]} Score
                </div>
                <div className="font-[family-name:var(--font-display)] text-3xl sm:text-4xl font-extrabold mt-1 tabular-nums">
                  {latestSignal.score}
                </div>
              </div>
              <span className={`px-3 py-1 rounded-lg text-sm font-bold font-[family-name:var(--font-display)] ${GRADE_COLORS[latestSignal.grade]}`}>
                {latestSignal.grade}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Period selector */}
      <div className="flex gap-1 mb-4" role="group" aria-label="차트 기간 선택">
        {PERIODS.map(p => (
          <button
            key={p.label}
            type="button"
            aria-pressed={period === p.months}
            onClick={() => setPeriod(p.months)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50 ${
              period === p.months
                ? 'text-white bg-[#6395FF]'
                : 'text-[#6B7A90] hover:text-[#E8ECF1]'
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Chart */}
      <ErrorBoundary resetKeys={[period, chartData.length]}>
      <div className="bg-[#131720] border border-white/[0.06] rounded-[14px] p-3 sm:p-4 mb-6">
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" aspect={2}>
            <ComposedChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="date" tick={{ fill: '#4A5568', fontSize: 10 }} tickLine={false} />
              <YAxis
                yAxisId="price"
                tick={{ fill: '#4A5568', fontSize: 10 }}
                tickFormatter={v => `${(v / 1000).toFixed(0)}K`}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                contentStyle={{ background: '#1A1F28', border: 'none', borderRadius: 10, color: '#E8ECF1' }}
                labelStyle={{ color: '#6B7A90' }}
              />
              <Legend iconType="line" wrapperStyle={{ fontSize: 11, color: '#6B7A90' }} />
              <Area
                yAxisId="price"
                type="monotone"
                dataKey="price"
                name="주가"
                stroke="#6395FF"
                fill="rgba(99,149,255,0.06)"
                strokeWidth={2}
              />
              {data.signals.map((s, i) => {
                const point = chartData.find(c => c.date === s.signal_date.slice(5));
                if (!point) return null;
                return (
                  <ReferenceDot
                    key={s.id ?? i}
                    x={point.date}
                    y={point.price}
                    yAxisId="price"
                    r={6}
                    fill="#FF4D6A"
                    stroke="none"
                  />
                );
              })}
            </ComposedChart>
          </ResponsiveContainer>
        ) : (
          <div className="text-center py-16 text-[#6B7A90]">차트 데이터가 없어요</div>
        )}
      </div>
      </ErrorBoundary>
    </main>
  );
}
