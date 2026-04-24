import { describe, expect, it } from 'vitest';
import * as barrel from './index';

describe('indicators barrel', () => {
  it('re-exports every indicator utility', () => {
    expect(typeof barrel.sma).toBe('function');
    expect(typeof barrel.rsi).toBe('function');
    expect(typeof barrel.macd).toBe('function');
    expect(typeof barrel.aggregateWeekly).toBe('function');
    expect(typeof barrel.aggregateMonthly).toBe('function');
  });

  it('sma from barrel matches direct call', () => {
    expect(barrel.sma([1, 2, 3, 4, 5], 2)[4]).toBe(4.5);
  });
});
