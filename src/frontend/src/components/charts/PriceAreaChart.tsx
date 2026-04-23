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

// v1.1 Sprint B: CandlestickSeries + MA overlay + Volume/RSI/MACD pane + 토글 visible + OHLCV 툴팁.
// 0 값 / null OHLC 레코드는 상위(page.tsx)에서 사전 제거한다.

export interface CandlePoint {
  date: string;
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
  values: ReadonlyArray<number>;
  color: string;
  visible: boolean;
}

export interface VolumePoint {
  date: string;
  value: number;
  isUp: boolean;
}

export interface RSISeriesProp {
  values: ReadonlyArray<number>; // length == data.length, NaN 허용
  color: string;
  visible: boolean;
}

export interface MACDSeriesProp {
  macd: ReadonlyArray<number>;
  signal: ReadonlyArray<number>;
  histogram: ReadonlyArray<number>;
  visible: boolean;
  colors: { macd: string; signal: string; up: string; down: string };
}

interface Props {
  data: CandlePoint[];
  markers?: SignalMarker[];
  maLines?: ReadonlyArray<MALine>;
  volume?: ReadonlyArray<VolumePoint>; // 전달 시 pane 표시, null/빈 배열 시 pane 제거
  rsi?: RSISeriesProp;
  macd?: MACDSeriesProp;
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
const VOLUME_PANE_HEIGHT_PX = 80;
const RSI_PANE_HEIGHT_PX = 80;
const MACD_PANE_HEIGHT_PX = 80;
const RSI_GUIDE_COLOR = 'rgba(255,255,255,0.15)';

// v1.1 Sprint B: 시그널 grade(A/B/C/D) 별 색 구분. enums.py SignalGrade.from_score 기준 동기.
const GRADE_COLOR: Record<string, string> = {
  A: '#FFCC00',
  B: '#00D68F',
  C: '#FF8B3E',
  D: '#6B7A90',
};

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
  const color = (m.label && GRADE_COLOR[m.label]) || '#FFCC00';
  return {
    time: toTime(m.date),
    position: 'aboveBar',
    color,
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

/** NaN 을 whitespace 로 걸러 `{time, value}` 포인트만 남긴다. */
function toLinePoints(
  data: ReadonlyArray<CandlePoint>,
  values: ReadonlyArray<number>,
): Array<{ time: Time; value: number }> {
  const out: Array<{ time: Time; value: number }> = [];
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (!Number.isFinite(v)) continue;
    const dp = data[i];
    if (!dp) continue;
    out.push({ time: toTime(dp.date), value: v });
  }
  return out;
}

export default function PriceAreaChart({
  data,
  markers = [],
  maLines = [],
  volume,
  rsi,
  macd,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const maSeriesMapRef = useRef<Map<number, ISeriesApi<'Line'>>>(new Map());

  const volumePaneRef = useRef<IPaneApi<Time> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);

  const rsiPaneRef = useRef<IPaneApi<Time> | null>(null);
  const rsiSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const rsiOverboughtRef = useRef<ISeriesApi<'Line'> | null>(null);
  const rsiOversoldRef = useRef<ISeriesApi<'Line'> | null>(null);

  const macdPaneRef = useRef<IPaneApi<Time> | null>(null);
  const macdLineRef = useRef<ISeriesApi<'Line'> | null>(null);
  const macdSignalRef = useRef<ISeriesApi<'Line'> | null>(null);
  const macdHistRef = useRef<ISeriesApi<'Histogram'> | null>(null);

  const [tooltip, setTooltip] = useState<HoverTooltip | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

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
      rsiPaneRef.current = null;
      rsiSeriesRef.current = null;
      rsiOverboughtRef.current = null;
      rsiOversoldRef.current = null;
      macdPaneRef.current = null;
      macdLineRef.current = null;
      macdSignalRef.current = null;
      macdHistRef.current = null;
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

  // MA overlay — window 별 LineSeries 를 Map 으로 유지. visible=false 는 applyOptions 로 숨김(오버레이라 pane 제거 불필요).
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
      lineSeries.setData(toLinePoints(data, ma.values));
    }
  }, [maLines, data]);

  // Volume pane — 토글 OFF(volume undefined/빈배열) 시 pane 제거, ON 시 생성·갱신.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const shouldShow = volume != null && volume.length > 0;

    if (!shouldShow) {
      if (volumeSeriesRef.current) {
        chart.removeSeries(volumeSeriesRef.current);
        volumeSeriesRef.current = null;
      }
      if (volumePaneRef.current) {
        chart.removePane(volumePaneRef.current.paneIndex());
        volumePaneRef.current = null;
      }
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

    volumeSeriesRef.current!.setData(
      volume!.map(v => ({
        time: toTime(v.date),
        value: v.value,
        color: v.isUp ? VOLUME_UP_COLOR : VOLUME_DOWN_COLOR,
      })),
    );
  }, [volume]);

  // RSI pane — visible 토글에 따라 pane 생성/제거. 70/30 과매수/과매도 가이드 포함.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const shouldShow = rsi != null && rsi.visible && rsi.values.length > 0;

    if (!shouldShow) {
      for (const ref of [rsiSeriesRef, rsiOverboughtRef, rsiOversoldRef]) {
        if (ref.current) {
          chart.removeSeries(ref.current);
          ref.current = null;
        }
      }
      if (rsiPaneRef.current) {
        chart.removePane(rsiPaneRef.current.paneIndex());
        rsiPaneRef.current = null;
      }
      return;
    }

    if (!rsiPaneRef.current) {
      const pane = chart.addPane();
      pane.setHeight(RSI_PANE_HEIGHT_PX);
      rsiPaneRef.current = pane;
    }
    const pane = rsiPaneRef.current;
    if (!pane) return;

    if (!rsiSeriesRef.current) {
      rsiSeriesRef.current = pane.addSeries(LineSeries, {
        color: rsi!.color,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
    }
    if (!rsiOverboughtRef.current) {
      rsiOverboughtRef.current = pane.addSeries(LineSeries, {
        color: RSI_GUIDE_COLOR,
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
    }
    if (!rsiOversoldRef.current) {
      rsiOversoldRef.current = pane.addSeries(LineSeries, {
        color: RSI_GUIDE_COLOR,
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
    }

    rsiSeriesRef.current!.applyOptions({ color: rsi!.color });
    rsiSeriesRef.current!.setData(toLinePoints(data, rsi!.values));

    // 가이드 라인: 데이터 전 구간 x 위에 y=70 / y=30 평행선.
    const guideOverbought = data.map(d => ({ time: toTime(d.date), value: 70 }));
    const guideOversold = data.map(d => ({ time: toTime(d.date), value: 30 }));
    rsiOverboughtRef.current!.setData(guideOverbought);
    rsiOversoldRef.current!.setData(guideOversold);
  }, [rsi, data]);

  // MACD pane — MACD/Signal 라인 + Histogram (양/음 색 분리).
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const shouldShow =
      macd != null && macd.visible && macd.macd.length > 0;

    if (!shouldShow) {
      for (const ref of [macdLineRef, macdSignalRef, macdHistRef]) {
        if (ref.current) {
          chart.removeSeries(ref.current);
          ref.current = null;
        }
      }
      if (macdPaneRef.current) {
        chart.removePane(macdPaneRef.current.paneIndex());
        macdPaneRef.current = null;
      }
      return;
    }

    if (!macdPaneRef.current) {
      const pane = chart.addPane();
      pane.setHeight(MACD_PANE_HEIGHT_PX);
      macdPaneRef.current = pane;
    }
    const pane = macdPaneRef.current;
    if (!pane) return;

    if (!macdHistRef.current) {
      macdHistRef.current = pane.addSeries(HistogramSeries, {
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }
    if (!macdLineRef.current) {
      macdLineRef.current = pane.addSeries(LineSeries, {
        color: macd!.colors.macd,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
    }
    if (!macdSignalRef.current) {
      macdSignalRef.current = pane.addSeries(LineSeries, {
        color: macd!.colors.signal,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
    }

    macdLineRef.current!.applyOptions({ color: macd!.colors.macd });
    macdSignalRef.current!.applyOptions({ color: macd!.colors.signal });
    macdLineRef.current!.setData(toLinePoints(data, macd!.macd));
    macdSignalRef.current!.setData(toLinePoints(data, macd!.signal));

    // Histogram 은 포인트별로 양/음 색 분리.
    const histPoints: Array<{ time: Time; value: number; color: string }> = [];
    for (let i = 0; i < macd!.histogram.length; i++) {
      const v = macd!.histogram[i];
      if (!Number.isFinite(v)) continue;
      const dp = data[i];
      if (!dp) continue;
      histPoints.push({
        time: toTime(dp.date),
        value: v,
        color: v >= 0 ? macd!.colors.up : macd!.colors.down,
      });
    }
    macdHistRef.current!.setData(histPoints);
  }, [macd, data]);

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
