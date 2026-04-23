'use client';

import { useEffect, useRef, useState } from 'react';

export interface SeriesDef {
  key: string;
  label: string;
  color: string;
}

export interface CategoryRow {
  name: string;
  values: Record<string, number>;
}

interface Props {
  data: CategoryRow[];
  series: SeriesDef[];
  valueFormatter?: (v: number) => string;
  ariaLabel?: string;
}

const PAD_LEFT = 40;
const PAD_RIGHT = 8;
const PAD_TOP_LEGEND = 22;
const PAD_TOP_PLOT = 28;
const PAD_BOTTOM = 28;
const MIN_BAR_WIDTH = 6;
const GROUP_INNER_GAP = 2;
const TICK_COUNT_TARGET = 5;

function niceStep(range: number, tickTarget: number): number {
  if (range === 0) return 1;
  const rough = range / tickTarget;
  const mag = Math.pow(10, Math.floor(Math.log10(rough)));
  const norm = rough / mag;
  const step = norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10;
  return step * mag;
}

function buildTicks(min: number, max: number): number[] {
  const step = niceStep(max - min, TICK_COUNT_TARGET);
  const start = Math.floor(min / step) * step;
  const out: number[] = [];
  for (let v = start; v <= max + step / 2; v += step) {
    out.push(Number(v.toFixed(6)));
  }
  return out;
}

function defaultFormat(v: number): string {
  return `${v > 0 ? '+' : ''}${v.toFixed(1)}%`;
}

export default function GroupedBarChart({
  data,
  series,
  valueFormatter = defaultFormat,
  ariaLabel,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const [hoveredBar, setHoveredBar] = useState<string | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      const rect = entries[0]?.contentRect;
      if (rect) setSize({ w: rect.width, h: rect.height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const { w, h } = size;
  const ready = w > 0 && h > 0;

  const values = data.flatMap(d => series.map(s => d.values[s.key] ?? 0));
  const rawMin = values.length ? Math.min(0, ...values) : 0;
  const rawMax = values.length ? Math.max(0, ...values) : 1;
  const padding = (rawMax - rawMin) * 0.12 || 1;
  const yMin = rawMin - (rawMin < 0 ? padding : 0);
  const yMax = rawMax + (rawMax > 0 ? padding : 0);
  const yRange = yMax - yMin || 1; // 0 구간 방어
  const ticks = buildTicks(yMin, yMax);

  const plotTop = PAD_TOP_LEGEND + PAD_TOP_PLOT;
  const plotBottom = h - PAD_BOTTOM;
  const plotHeight = Math.max(0, plotBottom - plotTop);
  const plotLeft = PAD_LEFT;
  const plotRight = w - PAD_RIGHT;
  const plotWidth = Math.max(0, plotRight - plotLeft);

  const yScale = (v: number) =>
    plotTop + ((yMax - v) / yRange) * plotHeight;

  const categoryWidth = data.length ? plotWidth / data.length : 0;
  const groupWidth = categoryWidth * 0.68;
  const groupLeftPad = (categoryWidth - groupWidth) / 2;
  const barWidth = Math.max(
    MIN_BAR_WIDTH,
    (groupWidth - (series.length - 1) * GROUP_INNER_GAP) / series.length
  );

  const zeroY = yScale(0);

  return (
    <div ref={containerRef} className="relative h-full w-full">
      {/* sr-only 대체 테이블 — 스크린리더는 이 테이블로 데이터를 읽고, SVG 는 시각 사용자 전용 */}
      <table className="sr-only">
        <caption>{ariaLabel ?? '그룹 막대 차트'}</caption>
        <thead>
          <tr>
            <th scope="col">구분</th>
            {series.map(s => (
              <th key={s.key} scope="col">
                {s.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map(row => (
            <tr key={row.name}>
              <th scope="row">{row.name}</th>
              {series.map(s => (
                <td key={s.key}>{valueFormatter(row.values[s.key] ?? 0)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {ready && (
        <svg
          width={w}
          height={h}
          viewBox={`0 0 ${w} ${h}`}
          style={{ display: 'block' }}
          aria-hidden="true"
        >
          {/* Legend — label 길이 기반 간격 (magic 72 제거) */}
          <g transform={`translate(${plotLeft}, 0)`}>
            {(() => {
              let xCursor = 0;
              return series.map(s => {
                const width = 22 + s.label.length * 7; // dot+gap + approx text width
                const node = (
                  <g key={s.key} transform={`translate(${xCursor}, 6)`}>
                    <circle cx={4} cy={6} r={4} fill={s.color} />
                    <text
                      x={13}
                      y={10}
                      fill="#6B7A90"
                      fontSize={11}
                      fontFamily="var(--font-mono), ui-monospace, monospace"
                    >
                      {s.label}
                    </text>
                  </g>
                );
                xCursor += width;
                return node;
              });
            })()}
          </g>

          {/* Y-axis tick lines & labels */}
          {ticks.map(t => {
            const y = yScale(t);
            const isZero = t === 0;
            return (
              <g key={t}>
                <line
                  x1={plotLeft}
                  x2={plotRight}
                  y1={y}
                  y2={y}
                  stroke={isZero ? 'rgba(255,255,255,0.16)' : 'rgba(255,255,255,0.04)'}
                  strokeDasharray={isZero ? undefined : '3 3'}
                />
                <text
                  x={plotLeft - 6}
                  y={y + 3}
                  textAnchor="end"
                  fill="#4A5568"
                  fontSize={10}
                  fontFamily="var(--font-mono), ui-monospace, monospace"
                >
                  {valueFormatter(t)}
                </text>
              </g>
            );
          })}

          {/* Bars */}
          {data.map((row, ci) => {
            const categoryX = plotLeft + ci * categoryWidth;
            return (
              <g key={row.name}>
                {series.map((s, si) => {
                  const v = row.values[s.key] ?? 0;
                  const y = yScale(v);
                  const x = categoryX + groupLeftPad + si * (barWidth + GROUP_INNER_GAP);
                  const top = Math.min(y, zeroY);
                  const height = Math.abs(y - zeroY);
                  const id = `${ci}-${si}`;
                  const isHovered = hoveredBar === id;
                  return (
                    <g key={s.key}>
                      <rect
                        x={x}
                        y={top}
                        width={barWidth}
                        height={Math.max(1, height)}
                        fill={s.color}
                        rx={3}
                        ry={3}
                        opacity={isHovered ? 0.85 : 1}
                        onMouseEnter={() => setHoveredBar(id)}
                        onMouseLeave={() => setHoveredBar(null)}
                      >
                        <title>
                          {`${row.name} · ${s.label}: ${valueFormatter(v)}`}
                        </title>
                      </rect>
                      {isHovered && (() => {
                        // 차트 경계 clamp — 첫/마지막 bar 또는 큰 값에서 텍스트가 밖으로 넘치지 않게
                        const labelX = Math.min(
                          Math.max(x + barWidth / 2, plotLeft + 4),
                          plotRight - 4
                        );
                        const rawY = v >= 0 ? top - 6 : top + height + 12;
                        const labelY = Math.min(
                          Math.max(rawY, plotTop + 10),
                          plotBottom + 14
                        );
                        return (
                          <text
                            x={labelX}
                            y={labelY}
                            textAnchor="middle"
                            fill="#E8ECF1"
                            fontSize={11}
                            fontFamily="var(--font-mono), ui-monospace, monospace"
                          >
                            {valueFormatter(v)}
                          </text>
                        );
                      })()}
                    </g>
                  );
                })}
              </g>
            );
          })}

          {/* X-axis category labels */}
          {data.map((row, ci) => (
            <text
              key={row.name}
              x={plotLeft + ci * categoryWidth + categoryWidth / 2}
              y={plotBottom + 18}
              textAnchor="middle"
              fill="#4A5568"
              fontSize={11}
              fontFamily="var(--font-display), ui-sans-serif, system-ui"
            >
              {row.name}
            </text>
          ))}
        </svg>
      )}
    </div>
  );
}
