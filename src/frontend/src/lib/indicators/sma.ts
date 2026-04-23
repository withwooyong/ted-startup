/**
 * Simple Moving Average (SMA) — 슬라이딩 윈도우 O(n) 단일 패스.
 *
 * 반환 길이는 입력 길이와 동일. 산출이 불가한 앞쪽 (window - 1) 구간은 NaN.
 * 차트 시리즈는 NaN / null 을 whitespace 로 인식해 자동 생략한다.
 */
export function sma(values: readonly number[], window: number): number[] {
  if (!Number.isInteger(window) || window <= 0) {
    throw new Error(`sma: window must be a positive integer (got ${window})`);
  }
  const n = values.length;
  const result = new Array<number>(n);
  let sum = 0;
  for (let i = 0; i < n; i++) {
    sum += values[i];
    if (i >= window) sum -= values[i - window];
    result[i] = i >= window - 1 ? sum / window : NaN;
  }
  return result;
}
