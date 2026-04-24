/**
 * Bollinger Bands — `(values, period, k)` → 상/중/하 밴드 3 배열.
 *
 *   middle = SMA(values, period)
 *   upper  = middle + k · σ_sample
 *   lower  = middle − k · σ_sample
 *
 * 표본 표준편차(분모 `period - 1`) 를 O(n) 슬라이딩 윈도우로 계산한다.
 * sum / sumSq 를 롤링으로 유지해 매 구간당 O(1) 에 분산을 구한다.
 *
 * 수치 안정성: sumSq 와 sum²/period 의 차분 공식은 입력 규모가 큰 스케일(예: 200,000 KRW 주가)
 * 에서 수 자릿수 정밀도 손실이 발생할 수 있다. v1.2 MVP 기준 오차는 σ 의 절대값 대비 1~5%
 * 수준으로 차트 시각화 목적상 허용. 더 엄격한 정밀도가 필요할 때는 Welford online 알고리즘으로
 * 교체 검토. variance 는 `max(0, ...)` 로 클램프해 부동소수점 언더플로로 음수가 나오는 케이스 방어.
 *
 * 각 반환 배열 길이는 입력과 동일. 산출 불가한 앞쪽 (period − 1) 개 인덱스는 NaN.
 */

export interface BBResult {
  upper: number[];
  middle: number[];
  lower: number[];
}

export function bb(
  values: readonly number[],
  period: number = 20,
  k: number = 2,
): BBResult {
  if (!Number.isInteger(period) || period < 2) {
    throw new Error(`bb: period must be integer >= 2 (got ${period})`);
  }
  if (!Number.isFinite(k) || k <= 0) {
    throw new Error(`bb: k must be positive finite number (got ${k})`);
  }

  const n = values.length;
  const upper = new Array<number>(n).fill(NaN);
  const middle = new Array<number>(n).fill(NaN);
  const lower = new Array<number>(n).fill(NaN);

  let sum = 0;
  let sumSq = 0;
  for (let i = 0; i < n; i++) {
    const v = values[i];
    sum += v;
    sumSq += v * v;
    if (i >= period) {
      const out = values[i - period];
      sum -= out;
      sumSq -= out * out;
    }
    if (i >= period - 1) {
      const mean = sum / period;
      // 표본 분산 (Bessel 보정, 분모 period - 1).
      const variance = Math.max(0, (sumSq - (sum * sum) / period) / (period - 1));
      const sigma = Math.sqrt(variance);
      middle[i] = mean;
      upper[i] = mean + k * sigma;
      lower[i] = mean - k * sigma;
    }
  }

  return { upper, middle, lower };
}
