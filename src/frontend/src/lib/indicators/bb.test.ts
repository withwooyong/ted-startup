import { describe, expect, it } from 'vitest';
import { bb } from './bb';

describe('bb', () => {
  it('throws on invalid period', () => {
    expect(() => bb([1, 2, 3], 1, 2)).toThrow(/period/);
    expect(() => bb([1, 2, 3], 0, 2)).toThrow(/period/);
    expect(() => bb([1, 2, 3], -1, 2)).toThrow(/period/);
    expect(() => bb([1, 2, 3], 2.5, 2)).toThrow(/period/);
  });

  it('throws on invalid k', () => {
    expect(() => bb([1, 2, 3], 3, 0)).toThrow(/k/);
    expect(() => bb([1, 2, 3], 3, -1)).toThrow(/k/);
    expect(() => bb([1, 2, 3], 3, NaN)).toThrow(/k/);
  });

  it('returns empty arrays for empty input', () => {
    const { upper, middle, lower } = bb([], 20, 2);
    expect(upper).toEqual([]);
    expect(middle).toEqual([]);
    expect(lower).toEqual([]);
  });

  it('all three bands have input length', () => {
    const values = Array.from({ length: 30 }, (_, i) => 100 + i);
    const { upper, middle, lower } = bb(values, 20, 2);
    expect(upper).toHaveLength(30);
    expect(middle).toHaveLength(30);
    expect(lower).toHaveLength(30);
  });

  it('first (period - 1) indices are NaN', () => {
    const values = Array.from({ length: 30 }, (_, i) => i + 1);
    const { upper, middle, lower } = bb(values, 5, 2);
    for (let i = 0; i < 4; i++) {
      expect(upper[i]).toBeNaN();
      expect(middle[i]).toBeNaN();
      expect(lower[i]).toBeNaN();
    }
    expect(Number.isFinite(middle[4])).toBe(true);
  });

  it('all NaN when input shorter than period', () => {
    const { upper, middle, lower } = bb([1, 2, 3], 5, 2);
    expect(upper.every(Number.isNaN)).toBe(true);
    expect(middle.every(Number.isNaN)).toBe(true);
    expect(lower.every(Number.isNaN)).toBe(true);
  });

  it('constant series → zero std → upper = middle = lower', () => {
    const { upper, middle, lower } = bb([7, 7, 7, 7, 7, 7, 7, 7], 4, 2);
    for (let i = 3; i < 8; i++) {
      expect(middle[i]).toBe(7);
      expect(upper[i]).toBe(7);
      expect(lower[i]).toBe(7);
    }
  });

  it('computes known sample (period=4, k=2, window [2,4,4,4])', () => {
    // sum=14, sumSq=52, mean=3.5, sample variance = (52 - 14²/4)/3 = 3/3 = 1, σ=1
    // upper = 3.5 + 2 = 5.5, lower = 3.5 - 2 = 1.5
    const { upper, middle, lower } = bb([2, 4, 4, 4], 4, 2);
    expect(middle[3]).toBeCloseTo(3.5, 10);
    expect(upper[3]).toBeCloseTo(5.5, 10);
    expect(lower[3]).toBeCloseTo(1.5, 10);
  });

  it('band is symmetric around middle (upper - middle == middle - lower)', () => {
    const values = [10, 12, 11, 14, 13, 15, 14, 16, 18, 17, 19, 20];
    const { upper, middle, lower } = bb(values, 5, 2);
    for (let i = 4; i < values.length; i++) {
      expect(upper[i] - middle[i]).toBeCloseTo(middle[i] - lower[i], 10);
    }
  });

  it('k scales the band width linearly', () => {
    const values = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21];
    const { upper: u1, middle: m1 } = bb(values, 5, 1);
    const { upper: u2 } = bb(values, 5, 2);
    const { upper: u3 } = bb(values, 5, 3);
    for (let i = 4; i < values.length; i++) {
      const band1 = u1[i] - m1[i];
      const band2 = u2[i] - m1[i];
      const band3 = u3[i] - m1[i];
      expect(band2).toBeCloseTo(band1 * 2, 10);
      expect(band3).toBeCloseTo(band1 * 3, 10);
    }
  });

  it('uses default (20, 2) when omitted', () => {
    const values = Array.from({ length: 25 }, (_, i) => 100 + i);
    const r1 = bb(values);
    const r2 = bb(values, 20, 2);
    expect(r1.upper).toEqual(r2.upper);
    expect(r1.middle).toEqual(r2.middle);
    expect(r1.lower).toEqual(r2.lower);
  });

  it('sliding window produces same result as fresh slice (no stale accumulator)', () => {
    // 100 포인트 × period=10 - sliding 결과가 각 지점 slice 기반 재계산과 일치해야.
    const values = Array.from({ length: 100 }, (_, i) => Math.sin(i / 5) * 10 + 100);
    const { upper, middle, lower } = bb(values, 10, 2);

    for (let i = 9; i < 100; i += 13) {
      const window = values.slice(i - 9, i + 1);
      const mean = window.reduce((a, b) => a + b, 0) / 10;
      const variance = window.reduce((a, v) => a + (v - mean) ** 2, 0) / (10 - 1);
      const sigma = Math.sqrt(variance);
      expect(middle[i]).toBeCloseTo(mean, 8);
      expect(upper[i]).toBeCloseTo(mean + 2 * sigma, 8);
      expect(lower[i]).toBeCloseTo(mean - 2 * sigma, 8);
    }
  });
});
