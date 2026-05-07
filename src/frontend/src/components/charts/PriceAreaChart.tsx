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
  overbought: number;
  oversold: number;
}

export interface MACDSeriesProp {
  macd: ReadonlyArray<number>;
  signal: ReadonlyArray<number>;
  histogram: ReadonlyArray<number>;
  visible: boolean;
  colors: { macd: string; signal: string; up: string; down: string };
}

export interface BBSeriesProp {
  upper: ReadonlyArray<number>;
  middle: ReadonlyArray<number>;
  lower: ReadonlyArray<number>;
  visible: boolean;
  colors: { upper: string; middle: string; lower: string };
}

interface Props {
  data: CandlePoint[];
  markers?: SignalMarker[];
  maLines?: ReadonlyArray<MALine>;
  volume?: ReadonlyArray<VolumePoint>; // 전달 시 pane 표시, null/빈 배열 시 pane 제거
  rsi?: RSISeriesProp;
  macd?: MACDSeriesProp;
  bb?: BBSeriesProp;
  /** 가시영역 좌측 끝(< THRESHOLD) 도달 시 호출. 호출자가 debounce/dedupe. */
  onReachLeftEdge?: () => void;
  /** true 면 좌측으로 더 이상 panning 불가 — 과거 데이터 소진 후 호출자가 true. */
  lockLeftEdge?: boolean;
  /** true 면 우측으로 더 이상 panning 불가 — 미래 데이터 없으므로 보통 true. */
  lockRightEdge?: boolean;
}

const LEFT_EDGE_THRESHOLD = 5; // 좌측 logical from < 5 candle 진입 시 prefetch trigger

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
  bb,
  onReachLeftEdge,
  lockLeftEdge,
  lockRightEdge,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const maSeriesMapRef = useRef<Map<number, ISeriesApi<'Line'>>>(new Map());
  const bbUpperRef = useRef<ISeriesApi<'Line'> | null>(null);
  const bbMiddleRef = useRef<ISeriesApi<'Line'> | null>(null);
  const bbLowerRef = useRef<ISeriesApi<'Line'> | null>(null);

  // 콜백을 ref 로 안정화 — chart init useEffect 의 의존성을 빈 배열로 유지하기 위해.
  const onReachLeftEdgeRef = useRef(onReachLeftEdge);
  onReachLeftEdgeRef.current = onReachLeftEdge;
  // setData 시 prepend 감지용 — 이전 첫 candle 의 date / 길이.
  const prevFirstDateRef = useRef<string | undefined>(undefined);
  const prevLenRef = useRef(0);

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

    // 좌측 가시영역 진입 감지 — logical from 이 임계 미만이면 호출.
    // logical 좌표는 data 인덱스 기준이며 음수도 가능 (왼쪽 빈 영역). from < THRESHOLD 시 prefetch.
    const visibleRangeHandler = (range: { from: number; to: number } | null) => {
      if (!range) return;
      if (range.from < LEFT_EDGE_THRESHOLD) {
        onReachLeftEdgeRef.current?.();
      }
    };
    chart.timeScale().subscribeVisibleLogicalRangeChange(visibleRangeHandler);

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
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(visibleRangeHandler);
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
      bbUpperRef.current = null;
      bbMiddleRef.current = null;
      bbLowerRef.current = null;
      prevFirstDateRef.current = undefined;
      prevLenRef.current = 0;
      setTooltip(null);
    };
  }, []);

  // setData + 가시영역 보존:
  //   - 첫 렌더 (prevLen=0): fitContent 로 전체 보임
  //   - prepend (첫 candle date 변경 + 길이 증가): visible logical range 를 added 만큼 시프트해
  //     사용자가 보던 위치를 유지. 시프트 안 하면 lazy load 후 갑자기 좌측으로 점프하는 UX.
  //   - 그 외 (지표 등 동일 data 재할당, append, 길이 감소): 시프트 없이 그대로 두면 차트가 자체 보존.
  useEffect(() => {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series) return;

    const newFirst = data[0]?.date;
    const wasFirst = prevFirstDateRef.current;
    const wasLen = prevLenRef.current;
    const isInitial = wasLen === 0;
    const added = data.length - wasLen;
    const isPrepend = !isInitial && newFirst !== wasFirst && added > 0;

    series.setData(data.map(mapCandle));

    if (isInitial) {
      chart.timeScale().fitContent();
    } else if (isPrepend) {
      const ts = chart.timeScale();
      const r = ts.getVisibleLogicalRange();
      if (r) {
        ts.setVisibleLogicalRange({ from: r.from + added, to: r.to + added });
      }
    }

    prevFirstDateRef.current = newFirst;
    prevLenRef.current = data.length;
  }, [data]);

  // 좌/우 panning lock — fixLeftEdge/fixRightEdge 는 lightweight-charts v5 의 timeScale 옵션.
  // true 면 해당 방향으로 데이터 끝을 넘는 panning 을 차단.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    chart.timeScale().applyOptions({
      fixLeftEdge: !!lockLeftEdge,
      fixRightEdge: !!lockRightEdge,
    });
  }, [lockLeftEdge, lockRightEdge]);

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

    // 가이드 라인: 데이터 전 구간 x 위에 overbought / oversold 평행선 (파라미터 편집 가능).
    const ob = rsi!.overbought;
    const os = rsi!.oversold;
    rsiOverboughtRef.current!.setData(data.map(d => ({ time: toTime(d.date), value: ob })));
    rsiOversoldRef.current!.setData(data.map(d => ({ time: toTime(d.date), value: os })));
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

  // Bollinger Bands — 가격 페인 오버레이. visible=false 시 3 LineSeries 제거.
  // lightweight-charts v5 는 두 선 사이 band 채움을 네이티브 지원하지 않아 v1.2 는 3 선만(v1.3 custom primitive 고려).
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const shouldShow = bb != null && bb.visible && bb.upper.length > 0;

    if (!shouldShow) {
      for (const ref of [bbUpperRef, bbMiddleRef, bbLowerRef]) {
        if (ref.current) {
          chart.removeSeries(ref.current);
          ref.current = null;
        }
      }
      return;
    }

    if (!bbUpperRef.current) {
      bbUpperRef.current = chart.addSeries(LineSeries, {
        color: bb!.colors.upper,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
    }
    if (!bbMiddleRef.current) {
      bbMiddleRef.current = chart.addSeries(LineSeries, {
        color: bb!.colors.middle,
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
    }
    if (!bbLowerRef.current) {
      bbLowerRef.current = chart.addSeries(LineSeries, {
        color: bb!.colors.lower,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
    }

    bbUpperRef.current!.applyOptions({ color: bb!.colors.upper });
    bbMiddleRef.current!.applyOptions({ color: bb!.colors.middle });
    bbLowerRef.current!.applyOptions({ color: bb!.colors.lower });

    bbUpperRef.current!.setData(toLinePoints(data, bb!.upper));
    bbMiddleRef.current!.setData(toLinePoints(data, bb!.middle));
    bbLowerRef.current!.setData(toLinePoints(data, bb!.lower));
  }, [bb, data]);

  return (
    <div className="relative h-full w-full">
      {/* canvas/table 이 내부에 있어 aria-hidden 은 aria-hidden-focus 규칙을 건드림.
          role="img" + aria-label 로 차트를 이미지로 취급하고, 상세 수치는 sr-only 테이블로 전달. */}
      <div
        ref={containerRef}
        className="h-full w-full"
        role="img"
        aria-label="가격 캔들 차트 (상세 수치는 아래 표 참조)"
      />
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
