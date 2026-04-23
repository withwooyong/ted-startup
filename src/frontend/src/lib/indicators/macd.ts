/**
 * Moving Average Convergence Divergence (MACD).
 *
 * 표준 파라미터: fast=12, slow=26, signal=9.
 *   - `macd`  = EMA(values, fast) − EMA(values, slow)
 *   - `signal` = EMA(macd, signal)
 *   - `histogram` = macd − signal
 *
 * 각 배열은 입력 길이와 동일. 산출 불가 구간은 NaN.
 */

/** EMA with SMA seed — `values` 의 첫 `period` 구간 평균을 seed 로 잡고, 이후 `k = 2/(p+1)` 계수 적용. */
function emaSeriesSmaSeed(values: readonly number[], period: number): number[] {
  const n = values.length;
  const out = new Array<number>(n).fill(NaN);
  if (n < period || period <= 0) return out;

  // SMA seed — 첫 period 개 평균을 index=(period-1) 에 기록.
  let sum = 0;
  for (let i = 0; i < period; i++) sum += values[i];
  out[period - 1] = sum / period;

  const k = 2 / (period + 1);
  for (let i = period; i < n; i++) {
    out[i] = values[i] * k + out[i - 1] * (1 - k);
  }
  return out;
}

/** MACD 라인의 EMA(signal). macd 배열 내 첫 유한값 위치부터 SMA seed → EMA 적용. */
function signalSeriesFromMacd(macdLine: readonly number[], signalPeriod: number): number[] {
  const n = macdLine.length;
  const out = new Array<number>(n).fill(NaN);
  let start = -1;
  for (let i = 0; i < n; i++) {
    if (Number.isFinite(macdLine[i])) {
      start = i;
      break;
    }
  }
  if (start < 0 || start + signalPeriod > n) return out;

  let sum = 0;
  for (let i = start; i < start + signalPeriod; i++) sum += macdLine[i];
  out[start + signalPeriod - 1] = sum / signalPeriod;

  const k = 2 / (signalPeriod + 1);
  for (let i = start + signalPeriod; i < n; i++) {
    out[i] = macdLine[i] * k + out[i - 1] * (1 - k);
  }
  return out;
}

export interface MACDResult {
  macd: number[];
  signal: number[];
  histogram: number[];
}

export function macd(
  values: readonly number[],
  fast: number = 12,
  slow: number = 26,
  signalPeriod: number = 9,
): MACDResult {
  if (!Number.isInteger(fast) || fast <= 0) {
    throw new Error(`macd: fast must be positive integer (got ${fast})`);
  }
  if (!Number.isInteger(slow) || slow <= fast) {
    throw new Error(`macd: slow must be integer > fast (got fast=${fast}, slow=${slow})`);
  }
  if (!Number.isInteger(signalPeriod) || signalPeriod <= 0) {
    throw new Error(`macd: signalPeriod must be positive integer (got ${signalPeriod})`);
  }

  const n = values.length;
  const fastEma = emaSeriesSmaSeed(values, fast);
  const slowEma = emaSeriesSmaSeed(values, slow);

  const macdLine = new Array<number>(n).fill(NaN);
  for (let i = 0; i < n; i++) {
    const f = fastEma[i];
    const s = slowEma[i];
    if (Number.isFinite(f) && Number.isFinite(s)) macdLine[i] = f - s;
  }

  const signal = signalSeriesFromMacd(macdLine, signalPeriod);

  const histogram = new Array<number>(n).fill(NaN);
  for (let i = 0; i < n; i++) {
    const m = macdLine[i];
    const sig = signal[i];
    if (Number.isFinite(m) && Number.isFinite(sig)) histogram[i] = m - sig;
  }

  return { macd: macdLine, signal, histogram };
}
