import { describe, expect, it } from 'vitest';
import { sma } from './sma';

describe('sma', () => {
  it('throws on non-positive or non-integer window', () => {
    expect(() => sma([1, 2, 3], 0)).toThrow(/positive integer/);
    expect(() => sma([1, 2, 3], -1)).toThrow(/positive integer/);
    expect(() => sma([1, 2, 3], 1.5)).toThrow(/positive integer/);
  });

  it('returns empty array for empty input', () => {
    expect(sma([], 5)).toEqual([]);
  });

  it('preserves input length', () => {
    const out = sma([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 3);
    expect(out).toHaveLength(10);
  });

  it('leaves first (window - 1) entries as NaN', () => {
    const out = sma([10, 20, 30, 40, 50], 3);
    expect(out[0]).toBeNaN();
    expect(out[1]).toBeNaN();
    expect(out[2]).toBe(20); // (10+20+30)/3
  });

  it('computes known sliding-window means', () => {
    // window=3 over [1,2,3,4,5] → NaN, NaN, 2, 3, 4
    const out = sma([1, 2, 3, 4, 5], 3);
    expect(out[2]).toBe(2);
    expect(out[3]).toBe(3);
    expect(out[4]).toBe(4);
  });

  it('window=1 returns identity', () => {
    expect(sma([3, 1, 4, 1, 5], 1)).toEqual([3, 1, 4, 1, 5]);
  });

  it('window larger than input yields all NaN', () => {
    const out = sma([1, 2], 5);
    expect(out.every(Number.isNaN)).toBe(true);
  });

  it('handles constant series (avg == value)', () => {
    const out = sma([7, 7, 7, 7, 7], 3);
    expect(out.slice(2)).toEqual([7, 7, 7]);
  });

  it('handles negative values', () => {
    // [-3, -1, 2, 4] window=2 → NaN, -2, 0.5, 3
    const out = sma([-3, -1, 2, 4], 2);
    expect(out[0]).toBeNaN();
    expect(out[1]).toBe(-2);
    expect(out[2]).toBeCloseTo(0.5, 10);
    expect(out[3]).toBe(3);
  });
});
