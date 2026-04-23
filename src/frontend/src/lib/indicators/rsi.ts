/**
 * Relative Strength Index (Wilder's RSI).
 *
 * J. Welles Wilder 원식에 따른 스무딩: 초기 `period` 구간은 단순 평균,
 * 이후는 `(prev * (period - 1) + current) / period` 로 EMA-유사 이동평균.
 *
 * 반환 길이는 입력 길이와 동일. 산출 불가한 앞쪽 (`period` + 1) 개 인덱스는 NaN.
 * avgLoss 가 0 인 구간은 RSI = 100 (전 구간 상승).
 */
export function rsi(values: readonly number[], period: number = 14): number[] {
  if (!Number.isInteger(period) || period <= 0) {
    throw new Error(`rsi: period must be a positive integer (got ${period})`);
  }
  const n = values.length;
  const result = new Array<number>(n).fill(NaN);
  if (n <= period) return result;

  let gainSum = 0;
  let lossSum = 0;
  for (let i = 1; i <= period; i++) {
    const diff = values[i] - values[i - 1];
    if (diff > 0) gainSum += diff;
    else lossSum -= diff;
  }
  let avgGain = gainSum / period;
  let avgLoss = lossSum / period;
  result[period] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);

  for (let i = period + 1; i < n; i++) {
    const diff = values[i] - values[i - 1];
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? -diff : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    result[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  }

  return result;
}
