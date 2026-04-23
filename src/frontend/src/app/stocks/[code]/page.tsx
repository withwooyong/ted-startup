'use client';

import { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import { useParams, useRouter } from 'next/navigation';
import { getStockDetail } from '@/lib/api/client';
import ErrorBoundary from '@/components/ErrorBoundary';
import {
  StockDetail,
  SIGNAL_TYPE_LABELS,
  GRADE_COLORS,
} from '@/types/signal';
import type {
  CandlePoint,
  MACDSeriesProp,
  MALine,
  RSISeriesProp,
  SignalMarker,
  VolumePoint,
} from '@/components/charts/PriceAreaChart';
import IndicatorTogglePanel from '@/components/charts/IndicatorTogglePanel';
import {
  aggregateMonthly,
  aggregateWeekly,
  macd as calcMacd,
  rsi as calcRsi,
  sma,
  type DailyCandle,
} from '@/lib/indicators';
import { useIndicatorPreferences } from '@/lib/hooks/useIndicatorPreferences';

const PriceAreaChart = dynamic(
  () => import('@/components/charts/PriceAreaChart'),
  {
    ssr: false,
    loading: () => (
      <div className="h-full w-full bg-[#131720]/60 rounded animate-pulse" />
    ),
  }
);

// v1.1 B0: 기간 버튼을 봉 주기로 재정의.
// 1D=일봉 (3 개월치 fetch), 1W=주봉 (1 년치 fetch → 주봉 재집계), 1M=월봉 (3 년치 fetch → 월봉 재집계).
type PeriodKey = 'day' | 'week' | 'month';

const PERIODS: ReadonlyArray<{
  key: PeriodKey;
  label: string;
  monthsFetch: number;
}> = [
  { key: 'day', label: '1D', monthsFetch: 3 },
  { key: 'week', label: '1W', monthsFetch: 12 },
  { key: 'month', label: '1M', monthsFetch: 36 },
];

export default function StockDetailPage() {
  const params = useParams();
  const router = useRouter();
  const rawCode = params.code;
  const code = Array.isArray(rawCode) ? rawCode[0] : rawCode ?? '';
  const [data, setData] = useState<StockDetail | null>(null);
  const [period, setPeriod] = useState<PeriodKey>('day');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [prevKey, setPrevKey] = useState(`${code}:${period}`);
  const { prefs, setPref } = useIndicatorPreferences();

  // fetch 파라미터 변경 시 loading 재진입 (render 중 리셋 패턴)
  const currentKey = `${code}:${period}`;
  if (currentKey !== prevKey) {
    setPrevKey(currentKey);
    setLoading(true);
    setError(null);
  }

  useEffect(() => {
    // 기간 버튼 빠른 전환 시 stale response 가 최신 state 를 덮어쓰는 것을 막기 위해
    // AbortController 로 이전 요청을 실제 네트워크 레벨에서 취소한다.
    const controller = new AbortController();
    const cfg = PERIODS.find(p => p.key === period) ?? PERIODS[0];
    const to = new Date().toISOString().split('T')[0];
    const fromDate = new Date();
    fromDate.setMonth(fromDate.getMonth() - cfg.monthsFetch);
    const from = fromDate.toISOString().split('T')[0];

    getStockDetail(code, from, to, { signal: controller.signal })
      .then((d: StockDetail) => {
        setData(d);
        setLoading(false);
      })
      .catch((err: unknown) => {
        // abort 된 요청은 정상적인 cleanup — state 를 건드리지 않음.
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      });

    return () => controller.abort();
  }, [code, period]);

  // lightweight-charts 는 'YYYY-MM-DD' 풀 포맷 요구 (slice 금지).
  // Rules-of-Hooks: early return 앞에서 호출되도록 위치 고정.
  // v1.1: 단일 패스로 일봉 OHLCV 배열 생성. 0값/null 레코드(부분 수집 실패, 공휴일 등)는 사전 제거.
  const dailyCandles = useMemo<DailyCandle[]>(() => {
    if (!data) return [];
    const candles: DailyCandle[] = [];
    for (const p of data.prices) {
      if (
        p.open_price == null ||
        p.high_price == null ||
        p.low_price == null ||
        p.open_price <= 0 ||
        p.high_price <= 0 ||
        p.low_price <= 0 ||
        p.close_price <= 0
      ) {
        continue;
      }
      candles.push({
        date: p.trading_date,
        open: p.open_price,
        high: p.high_price,
        low: p.low_price,
        close: p.close_price,
        volume: p.volume,
      });
    }
    return candles;
  }, [data]);

  // v1.1 B0: period 에 따라 일봉/주봉/월봉 재집계. chartData 는 volume 을 뺀 CandlePoint.
  const aggregated = useMemo<DailyCandle[]>(() => {
    if (dailyCandles.length === 0) return [];
    if (period === 'day') return dailyCandles;
    if (period === 'week') return aggregateWeekly(dailyCandles);
    return aggregateMonthly(dailyCandles);
  }, [dailyCandles, period]);

  const chartData = useMemo<CandlePoint[]>(
    () =>
      aggregated.map(c => ({
        date: c.date,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    [aggregated]
  );

  const volumeData = useMemo<VolumePoint[]>(
    () =>
      aggregated
        .filter(c => c.volume > 0)
        .map(c => ({ date: c.date, value: c.volume, isUp: c.close >= c.open })),
    [aggregated]
  );

  // 현재 period 의 closes — MA/RSI/MACD 공통 입력.
  const closes = useMemo(() => chartData.map(c => c.close), [chartData]);

  // MA(5/20/60/120) visible 은 사용자 토글 상태.
  const maLines = useMemo<MALine[]>(() => {
    if (closes.length === 0) return [];
    return [
      { window: 5, values: sma(closes, 5), color: '#FFCC00', visible: prefs.ma5 },
      { window: 20, values: sma(closes, 20), color: '#FF8B3E', visible: prefs.ma20 },
      { window: 60, values: sma(closes, 60), color: '#00D68F', visible: prefs.ma60 },
      { window: 120, values: sma(closes, 120), color: '#A78BFA', visible: prefs.ma120 },
    ];
  }, [closes, prefs.ma5, prefs.ma20, prefs.ma60, prefs.ma120]);

  // RSI(14) + MACD(12,26,9) — 표시 여부는 PriceAreaChart 에서 prefs.rsi/macd 로 제어.
  const rsiSeries = useMemo<RSISeriesProp>(
    () => ({
      values: closes.length > 0 ? calcRsi(closes, 14) : [],
      color: '#00BCFF',
      visible: prefs.rsi,
    }),
    [closes, prefs.rsi],
  );

  const macdSeries = useMemo<MACDSeriesProp>(() => {
    if (closes.length === 0) {
      return {
        macd: [],
        signal: [],
        histogram: [],
        visible: prefs.macd,
        colors: { macd: '#00BCFF', signal: '#FF80EC', up: '#FF4D6A', down: '#6395FF' },
      };
    }
    const r = calcMacd(closes, 12, 26, 9);
    return {
      macd: r.macd,
      signal: r.signal,
      histogram: r.histogram,
      visible: prefs.macd,
      colors: { macd: '#00BCFF', signal: '#FF80EC', up: '#FF4D6A', down: '#6395FF' },
    };
  }, [closes, prefs.macd]);

  // Volume 토글 OFF 시 PriceAreaChart 에 아예 전달하지 않아 pane 제거.
  const volumeProp = prefs.volume ? volumeData : undefined;
  const signalMarkers = useMemo<SignalMarker[]>(() => {
    if (!data) return [];
    const priceByDate = new Map(
      data.prices.map(p => [p.trading_date, p.close_price])
    );
    return data.signals.flatMap(s => {
      const price = priceByDate.get(s.signal_date);
      return price != null && price > 0 ? [{ date: s.signal_date, price, label: s.grade }] : [];
    });
  }, [data]);

  if (loading) {
    return (
      <main
        className="max-w-6xl mx-auto px-4 sm:px-5 py-5 sm:py-7 min-h-[calc(100dvh-8rem)]"
        aria-busy="true"
        aria-live="polite"
      >
        <div className="h-5 w-24 bg-[#131720] rounded animate-pulse mb-5" />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
          <div className="h-32 bg-[#131720] rounded-[14px] animate-pulse" />
          <div className="h-32 bg-[#131720] rounded-[14px] animate-pulse" />
        </div>
        <div className="flex gap-1 mb-4">
          <div className="h-7 w-10 bg-[#131720] rounded-lg animate-pulse" />
          <div className="h-7 w-10 bg-[#131720] rounded-lg animate-pulse" />
          <div className="h-7 w-10 bg-[#131720] rounded-lg animate-pulse" />
          <div className="h-7 w-10 bg-[#131720] rounded-lg animate-pulse" />
        </div>
        <div className="aspect-[1.4/1] sm:aspect-[2/1] bg-[#131720] rounded-[14px] animate-pulse mb-6" />
      </main>
    );
  }

  if (error || !data) {
    return (
      <main
        className="max-w-6xl mx-auto px-4 sm:px-5 py-5 sm:py-7 min-h-[calc(100dvh-8rem)] text-center"
        role="alert"
      >
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
  const changeColor = changeRateNum > 0 ? '#FF4D6A' : changeRateNum < 0 ? '#6395FF' : '#7A8699';

  return (
    <main className="max-w-6xl mx-auto px-4 sm:px-5 py-5 sm:py-7 min-h-[calc(100dvh-8rem)]">
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
            <span className="font-[family-name:var(--font-mono)] text-sm text-[#7A8699]">{data.stock.stock_code}</span>
          </div>
          <div className="grid grid-cols-3 gap-2 sm:gap-4">
            <div>
              <div className="text-[0.6rem] sm:text-[0.7rem] text-[#7A8699] font-[family-name:var(--font-display)] uppercase">현재가</div>
              <div className="font-[family-name:var(--font-display)] text-base sm:text-xl font-semibold mt-0.5 tabular-nums">
                {latestPrice ? latestPrice.close_price.toLocaleString() : '-'}
              </div>
            </div>
            <div>
              <div className="text-[0.6rem] sm:text-[0.7rem] text-[#7A8699] font-[family-name:var(--font-display)] uppercase">전일비</div>
              <div className="font-[family-name:var(--font-mono)] text-base sm:text-xl font-medium mt-0.5 tabular-nums" style={{ color: changeColor }}>
                {changeRateNum > 0 ? '+' : ''}{changeRateNum.toFixed(2)}%
              </div>
            </div>
            <div>
              <div className="text-[0.6rem] sm:text-[0.7rem] text-[#7A8699] font-[family-name:var(--font-display)] uppercase">거래량</div>
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
                <div className="text-[0.7rem] text-[#7A8699] font-[family-name:var(--font-display)] uppercase">
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

      {/* Period selector — v1.1 B0: 봉 주기 (일봉/주봉/월봉) */}
      <div className="flex gap-1 mb-3" role="group" aria-label="차트 봉 주기 선택">
        {PERIODS.map(p => (
          <button
            key={p.key}
            type="button"
            aria-pressed={period === p.key}
            onClick={() => setPeriod(p.key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-[#6395FF]/50 ${
              period === p.key
                ? 'text-[#0B0E11] bg-[#6395FF] font-semibold'
                : 'text-[#6B7A90] hover:text-[#E8ECF1]'
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Indicator toggles — v1.1 체크포인트 3 */}
      <IndicatorTogglePanel prefs={prefs} onToggle={setPref} />

      {/* Chart */}
      <ErrorBoundary resetKeys={[period, chartData.length]}>
      <div className="bg-[#131720] border border-white/[0.06] rounded-[14px] p-3 sm:p-4 mb-6">
        {chartData.length > 0 ? (
          <div className="aspect-[1.4/1] sm:aspect-[2/1]">
            <PriceAreaChart
              data={chartData}
              markers={signalMarkers}
              maLines={maLines}
              volume={volumeProp}
              rsi={rsiSeries}
              macd={macdSeries}
            />
          </div>
        ) : (
          <div className="text-center py-16 text-[#6B7A90]">차트 데이터가 없어요</div>
        )}
      </div>
      </ErrorBoundary>
    </main>
  );
}
