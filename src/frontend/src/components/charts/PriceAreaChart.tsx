'use client';

import { useEffect, useRef } from 'react';
import {
  AreaSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
} from 'lightweight-charts';

export interface PricePoint {
  date: string;
  price: number;
}

export interface SignalMarker {
  date: string;
  price: number;
  label?: string;
}

interface Props {
  data: PricePoint[];
  markers?: SignalMarker[];
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

function toTime(date: string): Time {
  // lightweight-charts 는 'YYYY-MM-DD' 만 BusinessDay 로 해석. 다른 포맷이면 조용히 실패하므로 사전 검증.
  if (!ISO_DATE.test(date)) {
    throw new Error(`PriceAreaChart: invalid date format "${date}" (expected YYYY-MM-DD)`);
  }
  return date as Time;
}

function mapPricePoint(p: PricePoint) {
  return { time: toTime(p.date), value: p.price };
}

function mapMarker(m: SignalMarker): SeriesMarker<Time> {
  return {
    time: toTime(m.date),
    position: 'inBar',
    color: '#FF4D6A',
    shape: 'circle',
    size: 1,
    text: m.label,
  };
}

export default function PriceAreaChart({ data, markers = [] }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Area'> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // clientHeight=0 방어: aspect-ratio 부모가 레이아웃 계산 전 단계일 수 있음
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
      handleScroll: false,
      handleScale: false,
      width: initialWidth,
      height: initialHeight,
    });

    const series = chart.addSeries(AreaSeries, {
      lineColor: '#6395FF',
      topColor: 'rgba(99,149,255,0.2)',
      bottomColor: 'rgba(99,149,255,0.02)',
      lineWidth: 2,
      priceFormat: { type: 'price', precision: 0, minMove: 1 },
    });

    chartRef.current = chart;
    seriesRef.current = series;
    markersRef.current = createSeriesMarkers(series);

    const resizeObserver = new ResizeObserver(() => {
      chart.applyOptions({
        width: container.clientWidth || initialWidth,
        height: container.clientHeight || initialHeight,
      });
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      markersRef.current = null;
    };
  }, []);

  // data/markers 업데이트 effect — Strict Mode 재마운트 시에도 deps 가 보존되어 있으면
  // 이 effect 가 재실행돼 새 chart 에 데이터가 즉시 주입됨 (React 가 remount 시 모든 effect 재실행).
  useEffect(() => {
    seriesRef.current?.setData(data.map(mapPricePoint));
    chartRef.current?.timeScale().fitContent();
  }, [data]);

  useEffect(() => {
    markersRef.current?.setMarkers(markers.map(mapMarker));
  }, [markers]);

  return <div ref={containerRef} className="h-full w-full" />;
}
