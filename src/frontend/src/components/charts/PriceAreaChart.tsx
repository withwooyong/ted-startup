'use client';

import { useEffect, useRef, useState } from 'react';
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type IPaneApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type MouseEventParams,
  type SeriesMarker,
  type Time,
} from 'lightweight-charts';

// v1.1: 파일명은 PriceAreaChart 유지(리네임은 별도 PR) — 내부는 CandlestickSeries + MA overlay + Volume pane + OHLCV 툴팁 + 줌/팬.
// 0 값 / null OHLC 레코드는 상위(page.tsx)에서 사전 제거한다.

export interface CandlePoint {
  date: string; // YYYY-MM-DD
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface SignalMarker {
  date: string;
  price: number;
  label?: string;
}

export interface MALine {
  window: number;
  values: ReadonlyArray<number>; // length == data.length, NaN 허용
  color: string;
  visible: boolean;
}

export interface VolumePoint {
  date: string;
  value: number;
  isUp: boolean;
}

interface Props {
  data: CandlePoint[];
  markers?: SignalMarker[];
  maLines?: ReadonlyArray<MALine>;
  volume?: ReadonlyArray<VolumePoint>;
}

interface HoverTooltip {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
  isUp: boolean;
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const VOLUME_UP_COLOR = 'rgba(255,77,106,0.6)';
const VOLUME_DOWN_COLOR = 'rgba(99,149,255,0.6)';
const VOLUME_PANE_HEIGHT_PX = 96;

function toTime(date: string): Time {
  if (!ISO_DATE.test(date)) {
    throw new Error(`PriceAreaChart: invalid date format "${date}" (expected YYYY-MM-DD)`);
  }
  return date as Time;
}

function mapCandle(p: CandlePoint) {
  return { time: toTime(p.date), open: p.open, high: p.high, low: p.low, close: p.close };
}

function mapMarker(m: SignalMarker): SeriesMarker<Time> {
  return {
    time: toTime(m.date),
    position: 'aboveBar',
    color: '#FFCC00',
    shape: 'circle',
    size: 1,
    text: m.label,
  };
}

function formatVolume(v: number): string {
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(2)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return v.toLocaleString();
}

export default function PriceAreaChart({
  data,
  markers = [],
  maLines = [],
  volume,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const maSeriesMapRef = useRef<Map<number, ISeriesApi<'Line'>>>(new Map());
  const volumePaneRef = useRef<IPaneApi<Time> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);

  const [tooltip, setTooltip] = useState<HoverTooltip | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // cleanup 에서 .clear() 호출용 — effect 시점의 Map 을 로컬 변수에 고정.
    const maSeriesMap = maSeriesMapRef.current;

    const initialWidth = container.clientWidth || 300;
    const initialHeight = container.clientHeight || 200;

    const chart = createChart(container, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#6B7A90',
        fontSize: 11,
        fontFamily:
          'var(--font-mono), ui-monospace, SFMono-Regular, Menlo, monospace',
      },
      grid: {
        vertLines: { color: 'rgba(255,255,255,0.04)' },
        horzLines: { color: 'rgba(255,255,255,0.04)' },
      },
      rightPriceScale: { borderVisible: false, textColor: '#4A5568' },
      timeScale: {
        borderVisible: false,
        timeVisible: false,
        secondsVisible: false,
      },
      crosshair: {
        vertLine: { color: '#3D4A5C', labelBackgroundColor: '#1A1F28' },
        horzLine: { color: '#3D4A5C', labelBackgroundColor: '#1A1F28' },
      },
      // A6: 줌/팬 활성화 — 모바일 핀치 줌은 라이브러리가 자동 처리.
      handleScroll: true,
      handleScale: true,
      width: initialWidth,
      height: initialHeight,
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#FF4D6A',
      downColor: '#6395FF',
      borderUpColor: '#FF4D6A',
      borderDownColor: '#6395FF',
      wickUpColor: '#FF4D6A',
      wickDownColor: '#6395FF',
      priceFormat: { type: 'price', precision: 0, minMove: 1 },
    });

    chartRef.current = chart;
    seriesRef.current = series;
    markersRef.current = createSeriesMarkers(series);

    // A7: OHLCV 툴팁 — CrosshairMove 구독 후 React state 로 오버레이 렌더.
    const crosshairHandler = (param: MouseEventParams) => {
      const cs = seriesRef.current;
      if (!param.time || !param.point || !cs) {
        setTooltip(null);
        return;
      }
      const candleData = param.seriesData.get(cs);
      if (!candleData || !('open' in candleData)) {
        setTooltip(null);
        return;
      }
      const d = candleData as { open: number; high: number; low: number; close: number };

      let volumeValue: number | undefined;
      const vs = volumeSeriesRef.current;
      if (vs) {
        const vd = param.seriesData.get(vs);
        if (vd && 'value' in vd) {
          volumeValue = (vd as { value: number }).value;
        }
      }

      setTooltip({
        time: String(param.time),
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
        volume: volumeValue,
        isUp: d.close >= d.open,
      });
    };
    chart.subscribeCrosshairMove(crosshairHandler);

    const resizeObserver = new ResizeObserver(() => {
      chart.applyOptions({
        width: container.clientWidth || initialWidth,
        height: container.clientHeight || initialHeight,
      });
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.unsubscribeCrosshairMove(crosshairHandler);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      markersRef.current = null;
      maSeriesMap.clear();
      volumePaneRef.current = null;
      volumeSeriesRef.current = null;
      setTooltip(null);
    };
  }, []);

  useEffect(() => {
    seriesRef.current?.setData(data.map(mapCandle));
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  useEffect(() => {
    markersRef.current?.setMarkers(markers.map(mapMarker));
  }, [markers]);

  // MA overlay — window 별 LineSeries 를 Map 으로 유지. 입력 변경 시 생성/삭제/업데이트.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const map = maSeriesMapRef.current;
    const incoming = new Set(maLines.map(ma => ma.window));

    for (const [win, lineSeries] of map) {
      if (!incoming.has(win)) {
        chart.removeSeries(lineSeries);
        map.delete(win);
      }
    }

    for (const ma of maLines) {
      let lineSeries = map.get(ma.window);
      if (!lineSeries) {
        lineSeries = chart.addSeries(LineSeries, {
          color: ma.color,
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        map.set(ma.window, lineSeries);
      }
      lineSeries.applyOptions({ color: ma.color, visible: ma.visible });

      const points: Array<{ time: Time; value: number }> = [];
      for (let i = 0; i < ma.values.length; i++) {
        const v = ma.values[i];
        if (v == null || !Number.isFinite(v)) continue;
        const dp = data[i];
        if (!dp) continue;
        points.push({ time: toTime(dp.date), value: v });
      }
      lineSeries.setData(points);
    }
  }, [maLines, data]);

  // Volume pane — 전달 시 pane + HistogramSeries 생성, 데이터 없을 때 시리즈만 비움.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    if (volume == null || volume.length === 0) {
      volumeSeriesRef.current?.setData([]);
      return;
    }

    if (!volumePaneRef.current) {
      const pane = chart.addPane();
      pane.setHeight(VOLUME_PANE_HEIGHT_PX);
      volumePaneRef.current = pane;
    }
    if (!volumeSeriesRef.current && volumePaneRef.current) {
      volumeSeriesRef.current = volumePaneRef.current.addSeries(HistogramSeries, {
        priceFormat: { type: 'volume' },
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }

    volumeSeriesRef.current?.setData(
      volume.map(v => ({
        time: toTime(v.date),
        value: v.value,
        color: v.isUp ? VOLUME_UP_COLOR : VOLUME_DOWN_COLOR,
      })),
    );
  }, [volume]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />
      {tooltip && (
        <div
          className="absolute top-2 right-2 z-10 bg-[#131720]/90 border border-white/10 rounded-lg px-3 py-2 text-[0.7rem] font-[family-name:var(--font-mono)] pointer-events-none backdrop-blur-sm"
          role="status"
          aria-live="polite"
        >
          <div className="text-[#7A8699] mb-1">{tooltip.time}</div>
          <div className="flex gap-2 tabular-nums">
            <span className="text-[#7A8699]">O</span>
            <span>{tooltip.open.toLocaleString()}</span>
            <span className="text-[#7A8699]">H</span>
            <span>{tooltip.high.toLocaleString()}</span>
            <span className="text-[#7A8699]">L</span>
            <span>{tooltip.low.toLocaleString()}</span>
            <span className="text-[#7A8699]">C</span>
            <span className={tooltip.isUp ? 'text-[#FF4D6A]' : 'text-[#6395FF]'}>
              {tooltip.close.toLocaleString()}
            </span>
          </div>
          {tooltip.volume !== undefined && (
            <div className="flex gap-2 mt-1 tabular-nums">
              <span className="text-[#7A8699]">V</span>
              <span>{formatVolume(tooltip.volume)}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
