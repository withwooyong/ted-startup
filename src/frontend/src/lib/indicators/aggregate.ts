/**
 * OHLCV 봉 주기 재집계 — 일봉을 주봉/월봉으로.
 *
 * 입력 배열은 `trading_date` 오름차순 가정 (백엔드 기본). 동일 그룹 내 레코드는
 * (first.open, max.high, min.low, last.close, sum.volume) 규칙으로 합친다.
 * date 는 그룹 첫 거래일을 사용해 x축 시점이 직관적 (주 시작일 / 월 시작일).
 */

export interface DailyCandle {
  date: string; // YYYY-MM-DD
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

function aggregate(candles: readonly DailyCandle[], keyOf: (date: string) => string): DailyCandle[] {
  if (candles.length === 0) return [];
  const groups = new Map<string, DailyCandle[]>();
  for (const c of candles) {
    const k = keyOf(c.date);
    const arr = groups.get(k);
    if (arr) arr.push(c);
    else groups.set(k, [c]);
  }
  const result: DailyCandle[] = [];
  for (const key of [...groups.keys()].sort()) {
    const g = groups.get(key)!;
    g.sort((a, b) => a.date.localeCompare(b.date));
    const first = g[0];
    const last = g[g.length - 1];
    let high = first.high;
    let low = first.low;
    let volume = 0;
    for (const c of g) {
      if (c.high > high) high = c.high;
      if (c.low < low) low = c.low;
      volume += c.volume;
    }
    result.push({
      date: first.date,
      open: first.open,
      high,
      low,
      close: last.close,
      volume,
    });
  }
  return result;
}

/** ISO 8601 week key — `'YYYY-Www'` (월요일 시작). */
function isoWeekKey(dateStr: string): string {
  // UTC 로 파싱. KST 차이는 일봉 단위라 영향 없음.
  const [y, m, d] = dateStr.split('-').map(Number);
  const date = new Date(Date.UTC(y, m - 1, d));
  const day = date.getUTCDay() || 7; // Sunday=0 → 7 로 치환해 월요일 기준으로 보정
  date.setUTCDate(date.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil((((date.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
  return `${date.getUTCFullYear()}-W${String(weekNo).padStart(2, '0')}`;
}

/** 일봉 → 주봉. */
export function aggregateWeekly(candles: readonly DailyCandle[]): DailyCandle[] {
  return aggregate(candles, isoWeekKey);
}

/** 일봉 → 월봉. key = 'YYYY-MM'. */
export function aggregateMonthly(candles: readonly DailyCandle[]): DailyCandle[] {
  return aggregate(candles, d => d.slice(0, 7));
}
