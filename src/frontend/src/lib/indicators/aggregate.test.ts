import { describe, expect, it } from 'vitest';
import { aggregateWeekly, aggregateMonthly, type DailyCandle } from './aggregate';

function c(date: string, open: number, high: number, low: number, close: number, volume: number): DailyCandle {
  return { date, open, high, low, close, volume };
}

describe('aggregateWeekly', () => {
  it('returns empty for empty input', () => {
    expect(aggregateWeekly([])).toEqual([]);
  });

  it('groups Monday-Friday into one weekly candle', () => {
    // 2026-04-20 (Mon) ~ 2026-04-24 (Fri) — same ISO week
    const input: DailyCandle[] = [
      c('2026-04-20', 100, 110, 95, 105, 1000),
      c('2026-04-21', 105, 115, 100, 110, 1100),
      c('2026-04-22', 110, 120, 105, 115, 1200),
      c('2026-04-23', 115, 125, 110, 120, 1300),
      c('2026-04-24', 120, 130, 115, 125, 1400),
    ];
    const out = aggregateWeekly(input);
    expect(out).toHaveLength(1);
    expect(out[0]).toEqual({
      date: '2026-04-20',
      open: 100,
      high: 130,
      low: 95,
      close: 125,
      volume: 6000,
    });
  });

  it('splits across ISO week boundaries', () => {
    // 2026-04-17 (Fri) is W16, 2026-04-20 (Mon) is W17
    const input: DailyCandle[] = [
      c('2026-04-17', 50, 55, 45, 52, 500),
      c('2026-04-20', 100, 110, 95, 105, 1000),
    ];
    const out = aggregateWeekly(input);
    expect(out).toHaveLength(2);
    expect(out[0].date).toBe('2026-04-17');
    expect(out[1].date).toBe('2026-04-20');
  });

  it('keeps groups in chronological order even with shuffled input', () => {
    const input: DailyCandle[] = [
      c('2026-04-22', 110, 120, 105, 115, 1200),
      c('2026-04-20', 100, 110, 95, 105, 1000),
      c('2026-04-21', 105, 115, 100, 110, 1100),
    ];
    const out = aggregateWeekly(input);
    expect(out).toHaveLength(1);
    // Uses the earliest date's open (sorted within group)
    expect(out[0].open).toBe(100);
    expect(out[0].close).toBe(115);
    expect(out[0].date).toBe('2026-04-20');
  });
});

describe('aggregateMonthly', () => {
  it('returns empty for empty input', () => {
    expect(aggregateMonthly([])).toEqual([]);
  });

  it('groups by YYYY-MM', () => {
    const input: DailyCandle[] = [
      c('2026-03-30', 10, 12, 9, 11, 100),
      c('2026-03-31', 11, 13, 10, 12, 110),
      c('2026-04-01', 20, 25, 18, 22, 500),
      c('2026-04-02', 22, 28, 20, 26, 600),
    ];
    const out = aggregateMonthly(input);
    expect(out).toHaveLength(2);
    expect(out[0]).toEqual({ date: '2026-03-30', open: 10, high: 13, low: 9, close: 12, volume: 210 });
    expect(out[1]).toEqual({ date: '2026-04-01', open: 20, high: 28, low: 18, close: 26, volume: 1100 });
  });

  it('single day in a month → same as input', () => {
    const input: DailyCandle[] = [c('2026-05-01', 50, 60, 40, 55, 999)];
    expect(aggregateMonthly(input)).toEqual(input);
  });
});
